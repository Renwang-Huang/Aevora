"""Execute real Phase 1 acceptance commands and archive their observed results."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.templates import create_template
from app.service import OrderFlow


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    validation_id = str(uuid4())
    archive = ROOT / "runs" / "validation" / validation_id
    archive.mkdir(parents=True)
    cli = [str(ROOT / ".venv" / "bin" / "orderflow")]
    records = []
    checks = []
    reports = {}

    def run(label, command, expected=0):
        number = len(records) + 1
        started = now()
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
        stdout = archive / f"{number:02}-{label}.stdout.log"
        stderr = archive / f"{number:02}-{label}.stderr.log"
        stdout.write_text(process.stdout)
        stderr.write_text(process.stderr)
        record = {"label": label, "command": shlex.join(command), "argv": command,
                  "started_at": started, "ended_at": now(), "exit_code": process.returncode,
                  "expected_exit_code": expected, "matches_expectation": process.returncode == expected,
                  "stdout": str(stdout.relative_to(ROOT)), "stderr": str(stderr.relative_to(ROOT))}
        records.append(record)
        print(f"{label}: exit={process.returncode} expected={expected}", flush=True)
        if process.stdout.strip().startswith(("{", "[")):
            return json.loads(process.stdout)
        return process.stdout.strip()

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})

    # Installation is repeated, not assumed from a previous environment.
    install = [sys.executable, "-m", "pip", "install"]
    if (ROOT / ".wheelhouse").exists():
        install += ["--no-index", "--find-links", str(ROOT / ".wheelhouse"), "--no-build-isolation"]
    run("dependency-install", install + ["-e", "."])
    run("dependency-check", [sys.executable, "-m", "pip", "check"])
    run("runtime", [sys.executable, "-c", "import sys,sqlite3,pytest; print(sys.version); print('SQLite',sqlite3.sqlite_version); print('pytest',pytest.__version__)"])
    run("framework-tests", [sys.executable, "-m", "pytest", "-q", "--junitxml", str(archive / "framework.junit.xml")])
    listing = run("episode-list", cli + ["list"])
    check("A implemented and B/C/D still PLANNED", {m["id"]: m["status"] for m in listing if m["id"] != "SMOKE-001"} == {"A": "IMPLEMENTED", **{x: "PLANNED" for x in "BCD"}})
    manifest = run("validate-smoke", cli + ["validate", "--episode", "SMOKE-001"])
    check("Scenario Manifest valid and SMOKE ready", manifest["manifest_valid"] and manifest["evaluation_status"] == "READY")

    business_code = '''import json,tempfile
from pathlib import Path
from app.service import OrderFlow
with tempfile.TemporaryDirectory() as d:
 f=OrderFlow(Path(d)/"business.sqlite"); f.initialize({"SKU-1":10})
 values=[f.get_inventory("SKU-1")["available"]]
 f.create_order("demo","SKU-1",3); values.append(f.get_inventory("SKU-1")["available"])
 f.cancel_order("demo"); values.append(f.get_inventory("SKU-1")["available"])
 f.cancel_order("demo"); values.append(f.get_inventory("SKU-1")["available"])
 print(json.dumps({"available":values,"audit":f.audit()["consistent"]}))
'''
    business = run("business-path", [sys.executable, "-c", business_code])
    check("Real business database and cancellation path", business == {"available": [10, 7, 10, 10], "audit": True})
    prepared = run("prepare-smoke", cli + ["prepare", "--episode", "SMOKE-001"])
    check("Runner loads and prepares SMOKE-001", prepared["overall_status"] == "PREPARED")
    run_id = prepared["run_id"]
    probes = [str(ROOT / "evaluator"), str(ROOT / "app"), str(ROOT / "docs"),
              "/proc/1/root" + str(ROOT / "evaluator")]
    boundary_code = "from pathlib import Path; import json; blocked=[not Path(p).exists() for p in " + repr(probes) + "]; print(json.dumps({'blocked':blocked})); assert all(blocked)"
    boundary = run("file-isolation", cli + ["shell", "--run-id", run_id, "--", "/usr/bin/python3.12", "-c", boundary_code])
    check("Agent sandbox cannot read hidden/reference/host baseline", all(boundary["blocked"]))
    run("public-smoke", cli + ["shell", "--run-id", run_id, "--", "/usr/bin/python3.12", "-m", "unittest", "discover", "-s", "tests/public"])
    defect_code = '''from app.service import OrderFlow
import json
f=OrderFlow('/tmp/defect.sqlite'); f.initialize({'SKU-1':10})
v=[f.get_inventory('SKU-1')['available']]
f.create_order('defect','SKU-1',3);v.append(f.get_inventory('SKU-1')['available'])
f.cancel_order('defect');v.append(f.get_inventory('SKU-1')['available'])
f.cancel_order('defect');v.append(f.get_inventory('SKU-1')['available'])
print(json.dumps({'available':v})); assert v==[10,7,10,13]
'''
    defect = run("actual-defect-path", cli + ["shell", "--run-id", run_id, "--", "/usr/bin/python3.12", "-c", defect_code])
    check("Defective implementation really releases stock twice", defect["available"] == [10, 7, 10, 13])
    reports["buggy"] = run("buggy-evaluation", cli + ["evaluate", "--episode", "SMOKE-001", "--run-id", run_id], 1)
    patch = ROOT / "evaluator" / "reference_patches" / "SMOKE-001.diff"
    reports["reference-patch"] = run("reference-patch", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(patch)])
    reports["reference-workspace"] = run("reference-workspace", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(ROOT / "app")])
    query = run("report-query", cli + ["report", "--run-id", reports["reference-patch"]["run_id"]])
    check("JSON report query returns archived result", query == reports["reference-patch"])
    reset = run("reset-smoke", cli + ["reset", "--episode", "SMOKE-001"])
    check("Environment explicitly reset", reset["status"] == "RESET" and run_id in reset["run_ids"])
    reports["buggy-repeat"] = run("buggy-repeat", cli + ["evaluate", "--episode", "SMOKE-001"], 1)
    reports["reference-repeat"] = run("reference-repeat", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(patch)])
    for key in ("reference-patch", "reference-workspace", "reference-repeat"):
        report = reports[key]
        check(f"{key} actually passes all hidden tests", report["overall_status"] == "PASS" and report["test_results"]["passed"] == 8 and report["pytest_exit_code"] == 0)
    for key in ("buggy", "buggy-repeat"):
        check(f"{key} actually fails hidden assertions", reports[key]["overall_status"] == "FAIL" and reports[key]["test_results"]["failed"] > 0 and reports[key]["pytest_exit_code"] == 1)
    outcomes = lambda r: [(t["nodeid"], t["outcome"]) for t in r["test_results"]["tests"]]
    check("Defect reproducible after reset", outcomes(reports["buggy"]) == outcomes(reports["buggy-repeat"]))
    check("Reference reproducible after reset", outcomes(reports["reference-patch"]) == outcomes(reports["reference-repeat"]))

    readiness_a = run("validate-implemented-A", cli + ["validate", "--episode", "A"])
    check("A readiness updated without conflating PLANNED Episodes", readiness_a["evaluation_status"] == "READY")
    for episode in "BCD":
        run(f"validate-planned-{episode}", cli + ["validate", "--episode", episode], 4)
        report = run(f"evaluate-planned-{episode}", cli + ["evaluate", "--episode", episode], 4)
        reports[f"planned-{episode}"] = report
        check(f"{episode} never reported as PASS", report["overall_status"] == "NOT_IMPLEMENTED" and report["test_results"] is None)
    syntax = create_template(archive / "syntax-submission", buggy=False)
    (syntax / "app" / "service.py").write_text("def broken(:\n")
    reports["syntax-error"] = run("syntax-error", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(syntax)], 2)
    check("Syntax error distinguished", reports["syntax-error"]["overall_status"] == "ERROR" and reports["syntax-error"]["test_results"]["errors"] == 8)
    hanging = create_template(archive / "timeout-submission", buggy=False)
    (hanging / "app" / "service.py").write_text("while True:\n    pass\n")
    reports["timeout"] = run("timeout", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(hanging), "--timeout", "1"], 3)
    check("Hanging submission distinguished", reports["timeout"]["overall_status"] == "TIMEOUT")
    reports["invalid-submission"] = run("invalid-submission", cli + ["evaluate", "--episode", "SMOKE-001", "--submission", str(archive / "missing.diff")], 2)
    check("Rejected submission archived with reference", reports["invalid-submission"]["overall_status"] == "ERROR" and reports["invalid-submission"]["submission"]["original_reference"].endswith("missing.diff"))
    for key, report in reports.items():
        directory = ROOT / "runs" / report["run_id"]
        check(f"{key}: report and trace exist", (directory / "evaluation_report.json").is_file() and (directory / "execution_trace.jsonl").is_file())
        check(f"{key}: mutable test databases removed", not (directory / "artifacts" / "pytest-tmp").exists())
        if report["episode_id"] == "SMOKE-001":
            flow = OrderFlow(directory / "workspace" / "business.sqlite")
            check(f"{key}: initial fixture restored", flow.get_inventory("SKU-1")["available"] == 10 and flow.audit()["orders"] == [])
    check("Run IDs unique", len({r["run_id"] for r in reports.values()}) == len(reports))
    check("No invented Agent or experience observations", all(r["experience"]["status"] == "DISABLED" and r["agent"]["execution"] == "UNAVAILABLE" for r in reports.values()))
    success = all(r["matches_expectation"] for r in records) and all(c["passed"] for c in checks)
    summary = {"validation_id": validation_id, "conclusion": "PASS" if success else "FAIL",
               "commands": records, "checks": checks, "run_ids": {k: r["run_id"] for k, r in reports.items()}}
    (archive / "validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Phase 1 Validation Report", "", f"验收结论：**{summary['conclusion']}**", "",
             "范围：Phase 1 回归验收（Phase 2 源码）。A 已接入；其完整验收另见 PHASE2_VALIDATION_REPORT.md。B/C/D、Codex 自动运行、GraphSwarm 和 G0–G3 未实现或未运行。", "",
             f"Validation ID：`{validation_id}`。命令均在项目根目录的实际 Python 3.12 环境执行；UTC 时间、argv、stdout/stderr 与退出状态来自 subprocess。", "",
             f"完整机器记录：[validation.json]({(archive / 'validation.json').relative_to(ROOT)})", "",
             "## 实际命令与退出状态", "",
             "退出 1/2/3/4 是针对缺陷、错误、超时、未实现的预期结果，不能当作对应任务 PASS。", "",
             "| 步骤 | 实际退出 | 预期退出 | 匹配 |", "|---|---:|---:|---|"]
    for record in records:
        lines.append(f"| {record['label']} | {record['exit_code']} | {record['expected_exit_code']} | {'是' if record['matches_expectation'] else '否'} |")
    lines += ["", "## 真实测试与执行结果", "", "| 提交/场景 | Run ID | 判定 | passed / failed / errors / skipped |", "|---|---|---|---|"]
    for key, report in reports.items():
        tests = report["test_results"]
        counts = "未执行" if tests is None else " / ".join(str(tests[x]) for x in ("passed", "failed", "errors", "skipped"))
        lines.append(f"| {key} | `{report['run_id']}` | {report['overall_status']} | {counts} |")
    lines += ["", "完整开发者测试 stdout：", "", "```text", (archive / "04-framework-tests.stdout.log").read_text().strip(), "```", "",
              "## 失败记录", "",
              "- 缺陷提交真实出现重复释放，库存序列为 `10 → 7 → 10 → 13`；两次独立 oracle 均 FAIL，原始断言/堆栈保存在对应 Run 的 JUnit 和 pytest 日志。",
              "- 语法错误提交的独立 worker 初始化失败，判定 ERROR；挂起提交达到 1 秒截止，判定 TIMEOUT；不存在的 patch 被拒绝并记录实际路径及事件。",
              "- B/C/D 均 PLANNED / NOT_IMPLEMENTED；无隐藏测试调用、无 PASS 记录。A 的 readiness 已检查为 READY，其实际并发验收单独记录。",
              "- 开发环境最初 `uv python install 3.12` 退出 1：下载域名 DNS 失败。该历史结果来自开发工具输出；验收采用本机 Flatpak Python 3.12.13 与离线依赖快照，实际重新安装及 pip check 见上表。",
              "- 独立审查发现 DB reset 跟随符号链接与临时 DB 清理路径问题，已修复并加入完整开发者回归；没有删除或放宽失败断言。", "",
              "## 验收检查", "", "| 检查 | 结果 |", "|---|---|"]
    lines += [f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in checks]
    lines += ["", "## 每条实际命令与原始日志", ""]
    for record in records:
        lines += [f"### {record['label']}", "", f"开始 `{record['started_at']}`，结束 `{record['ended_at']}`，实际退出 `{record['exit_code']}`。", "",
                  "```bash", record["command"], "```", "",
                  f"[stdout]({record['stdout']}) · [stderr]({record['stderr']})", ""]
    lines += ["## 限制与停止边界", "",
              "文件隔离、独立判分、数据库重置和手动提交流水线已验收；Phase 2 增加宿主数据库 Oracle。网络未隔离；CPU/内存/seccomp、敌对 RPC 限流、完整反作弊、原生 Windows、wheel 发布和同 Run 并发未验证或未实现。",
              "Payment/Event 是契约；Codex 自动接入未实现；经验四接口为 Disabled。无 Agent 运行指标、经验命中/决策/反馈或正式对照结果。",
              "本结论覆盖 Phase 1 回归。原始 Phase 1 验收记录保留在其 validation Run；Phase 2 结论见独立报告。", ""]
    (ROOT / "PHASE1_VALIDATION_REPORT.md").write_text("\n".join(lines))
    print(f"{summary['conclusion']}: {len(records)} commands, {len(checks)} checks; {archive}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
