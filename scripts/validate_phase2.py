"""Real Phase 2 acceptance, including ten fresh buggy/reference suite pairs.

Run with Python 3.12 in the same supported environment as orderflow. All
commands, exits and assertions are archived; expected negative verdicts are
kept as FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED, never relabelled candidate PASS.
"""
from collections import Counter
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.service import OrderFlow
from benchmark.episodes.episode_a import create_episode_a
from evaluator.runner import read_junit


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint_report_lines(evidence):
    runtime = evidence["runtime"]
    return ["## 本次实际版本与摘要", "",
            f"Python：`{runtime['python']}`；SQLite：`{runtime['sqlite']}`；pytest：`{runtime['packages']['pytest']}`；pluggy：`{runtime['packages']['pluggy']}`。",
            f"平台：`{runtime['platform']}`；`{runtime['tools']['bwrap']['version']}`；`{runtime['tools']['git']['version']}`。", "",
            "| 指纹 | 真实 SHA256 |", "|---|---|",
            *[f"| {key} / {evidence[key]['version']} | `{evidence[key]['sha256']}` |" for key in ("evaluator", "fixture", "test_suite")],
            f"| A private manifest | `{evidence['private_manifest_sha256']}` |", "",
            "各源码摘要的逐文件清单、Python/git/bwrap 二进制摘要与每 Run 提交摘要保存在实际 JSON Report 中；20 轮上述完整指纹相同。", ""]


def main():
    archive = ROOT / "runs/validation-phase2" / str(uuid4())
    archive.mkdir(parents=True)
    cli = [str(ROOT / ".venv/bin/orderflow")]
    records, checks, reports, repeats = [], [], {}, []

    def persist():
        (archive / "validation-progress.json").write_text(json.dumps({
            "commands": records, "checks": checks, "repeats": repeats,
            "run_ids": {k: v["run_id"] for k, v in reports.items()},
        }, indent=2) + "\n")

    def check(label, condition):
        checks.append({"name": label, "passed": bool(condition)})
        persist()

    def run(label, command, expected=0, timeout=240):
        started = now()
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        prefix = f"{len(records)+1:02}-{label}"
        stdout, stderr = archive / (prefix + ".stdout.log"), archive / (prefix + ".stderr.log")
        stdout.write_text(completed.stdout)
        stderr.write_text(completed.stderr)
        records.append({"label": label, "argv": command, "command": shlex.join(command),
                        "started_at": started, "ended_at": now(), "exit_code": completed.returncode,
                        "expected_exit_code": expected, "matches_expectation": completed.returncode == expected,
                        "stdout": str(stdout.relative_to(ROOT)), "stderr": str(stderr.relative_to(ROOT))})
        persist()
        print(f"{label}: exit={completed.returncode}, expected={expected}", flush=True)
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return completed.stdout.strip()

    def evaluate(label, arguments, expected=0):
        result = run(label, cli + ["evaluate", "--episode", "A", *arguments], expected)
        reports[label] = result
        persist()
        return result

    def primary_evidence(report):
        directory = ROOT / "runs" / report["run_id"] / "artifacts"
        batch = json.loads((directory / "concurrency-test_concurrent_200_requests_with_50_stock-batch.json").read_text())
        oracle = json.loads((directory / "oracle-test_concurrent_200_requests_with_50_stock-batch.json").read_text())
        execution = batch["execution"]
        gate = execution["checkpoint"]
        inventory = oracle["inventory"][0]
        return {"successes": sum(item["ok"] for item in batch["results"]),
                "business_errors": dict(Counter(item["error"]["type"] for item in batch["results"] if not item["ok"])),
                "process_ids": sorted({item["pid"] for item in batch["results"]}),
                "threads": len({item["thread_id"] for item in batch["results"]}),
                "max_active": execution["max_active"], "gate_arrivals": gate["arrivals"],
                "gate_parties": gate["parties"], "gate_release": gate["released_by"],
                "available": inventory["available"], "reserved": inventory["reserved"],
                "orders": len(oracle["orders"]), "ledger": len(oracle["ledger"]),
                "oracle_consistent": oracle["consistent"], "violations": oracle["violations"]}

    # Retain and re-execute every applicable Phase 1 check, including installation,
    # actual ERROR/TIMEOUT, smoke positive/negative and B/C/D readiness handling.
    before = set((ROOT / "runs/validation").glob("*"))
    run("phase1-regression", [sys.executable, str(ROOT / "scripts/validate_phase1.py")])
    new_validations = set((ROOT / "runs/validation").glob("*")) - before
    if len(new_validations) != 1:
        raise RuntimeError("Phase 1 acceptance did not produce one new validation archive")
    phase1_dir = new_validations.pop()
    phase1 = json.loads((phase1_dir / "validation.json").read_text())
    check("Phase 1 acceptance commands and checks all pass", phase1["conclusion"] == "PASS")
    developer = read_junit(phase1_dir / "framework.junit.xml")
    check("Full developer tests have no failures/errors/skips", developer["collected"] >= 46 and
          developer["passed"] == developer["collected"])
    original_junit = archive / "original46.junit.xml"
    run("original-46-tests", [sys.executable, "-m", "pytest", "tests/test_business.py", "tests/test_adapters.py",
                             "tests/test_framework.py", "tests/test_evaluator.py", "tests/public/test_orders.py",
                             "-q", "--junitxml", str(original_junit)])
    original = read_junit(original_junit)
    check("All original 46 developer tests still run and pass", original["collected"] == original["passed"] == 46)
    check("Original test identities are retained in full suite", all(
        (t["nodeid"], t["outcome"]) in {(x["nodeid"], x["outcome"]) for x in developer["tests"]}
        for t in original["tests"]))

    manifest = run("validate-A", cli + ["validate", "--episode", "A", "--variant", "v01"])
    check("A manifest ready through CLI", manifest["manifest_valid"] and manifest["evaluation_status"] == "READY")
    prepared = run("prepare-A", cli + ["prepare", "--episode", "A", "--variant", "v01"])
    check("A independent fixture prepared", prepared["overall_status"] == "PREPARED" and prepared["scenario_variant"] == "v01")
    other = run("prepare-other-smoke", cli + ["prepare", "--episode", "SMOKE-001"])
    probes = [ROOT / "evaluator/hidden_tests", ROOT / "evaluator/reference_patches/A-v01.diff",
              ROOT / "evaluator/private_manifests/A.json", ROOT / "app/service.py",
              ROOT / "runs" / other["run_id"] / "evaluation_report.json"]
    paths = [str(p) for p in probes] + ["/proc/1/root" + str(p) for p in probes]
    code = "from pathlib import Path; import json; blocked=[not Path(p).exists() for p in " + repr(paths) + "]; print(json.dumps({'blocked':blocked,'candidate':Path('/workspace/app/service.py').is_file()})); assert all(blocked)"
    isolation = run("A-isolation", cli + ["shell", "--run-id", prepared["run_id"], "--", "/usr/bin/python3.12", "-I", "-c", code])
    check("Hidden/reference/private/host/other runs and proc escape inaccessible", all(isolation["blocked"]) and isolation["candidate"])
    run("A-single-thread-public", cli + ["shell", "--run-id", prepared["run_id"], "--", "/usr/bin/python3.12", "-m", "unittest", "discover", "-s", "tests/public"])
    run("reject-episode-mix", cli + ["evaluate", "--episode", "SMOKE-001", "--run-id", prepared["run_id"]], 2)
    run("reject-unknown-variant", cli + ["validate", "--episode", "A", "--variant", "missing"], 2)
    prepared_bug = evaluate("A-prepared-buggy", ["--run-id", prepared["run_id"]], 1)
    check("Prepared buggy receives actual FAIL", prepared_bug["overall_status"] == "FAIL" and prepared_bug["test_results"]["collected"] == 14)
    patch = ROOT / "evaluator/reference_patches/A-v01.diff"
    workspace_result = evaluate("A-reference-workspace", ["--submission", str(ROOT / "app")])
    check("Correct workspace submission PASS", workspace_result["overall_status"] == "PASS" and workspace_result["test_results"]["passed"] == 14)

    # Verify two genuinely different valid strategies through the ENTIRE suite.
    atomic = create_episode_a(archive / "atomic-submission")
    service = atomic / "app/service.py"
    service.write_text(service.read_text().replace("self.inventory.reserve(connection, order_id, snapshot=snapshot)",
                                                 "self.inventory.reserve(connection, order_id)"))
    locked = create_episode_a(archive / "lock-submission")
    service = locked / "app/service.py"
    service.write_text(service.read_text() + '''\nimport threading
_create_lock = threading.RLock()
_unlocked_create = OrderFlow.create_order
def _serialized_create(self, *args, **kwargs):
    with _create_lock:
        return _unlocked_create(self, *args, **kwargs)
OrderFlow.create_order = _serialized_create
''')
    for label, workspace in [("atomic", atomic), ("lock", locked)]:
        buggy = create_episode_a(archive / (label + "-original"))
        patch_text = "".join(difflib.unified_diff((buggy / "app/service.py").read_text().splitlines(True),
                              (workspace / "app/service.py").read_text().splitlines(True),
                              fromfile="a/app/service.py", tofile="b/app/service.py"))
        (archive / (label + "-repair.diff")).write_text(patch_text)
        result = evaluate("A-alternate-" + label, ["--submission", str(workspace)])
        evidence = primary_evidence(result)
        check(label + " alternate full suite PASS with real threaded ingress", result["overall_status"] == "PASS"
              and result["test_results"]["passed"] == 14 and evidence["threads"] == 200
              and evidence["max_active"] == 200 and evidence["oracle_consistent"])

    syntax = create_episode_a(archive / "syntax-submission", buggy=False)
    (syntax / "app/service.py").write_text("def broken(:\n")
    error = evaluate("A-syntax-error", ["--submission", str(syntax)], 2)
    check("A candidate exception is ERROR not PASS", error["overall_status"] == "ERROR" and error["test_results"]["errors"] == 14)
    hanging = create_episode_a(archive / "timeout-submission", buggy=False)
    (hanging / "app/service.py").write_text("while True:\n    pass\n")
    timeout = evaluate("A-timeout", ["--submission", str(hanging), "--timeout", "1"], 3)
    check("A evaluator deadline yields TIMEOUT", timeout["overall_status"] == "TIMEOUT")

    reproductions = {}
    for kind, arguments, expected in [("buggy", [], 1), ("reference", ["--submission", str(patch)], 0)]:
        reproductions[kind] = run("reproducer-" + kind, [sys.executable, str(ROOT / "scripts/reproduce_episode_a.py"), *arguments], expected)
        check("Reproducer " + kind + " executes real batch with independent Oracle", reproductions[kind]["concurrency"]["thread_count"] == 200
              and reproductions[kind]["status"] == ("FAIL" if kind == "buggy" else "PASS")
              and reproductions[kind]["full_hidden_evaluator"] is False)

    for number in range(1, 11):
        for kind, args, expected in [("buggy", [], 1), ("reference", ["--submission", str(patch)], 0)]:
            label = f"repeat-{number:02}-{kind}"
            report = evaluate(label, args, expected)
            tests = report["test_results"]
            evidence = primary_evidence(report)
            row = {"round": number, "kind": kind, "run_id": report["run_id"],
                   "status": report["overall_status"], "counts": {k: tests[k] for k in ("collected", "passed", "failed", "errors", "skipped")},
                   "failures": [{"name": t["name"], "reason": t["message"]} for t in tests["tests"] if t["outcome"] != "PASS"],
                   "primary_evidence": evidence, "fingerprints": report["fingerprints"]}
            repeats.append(row)
            check(label + " complete suite, no skipped or infrastructure errors", tests["collected"] == 14 and tests["errors"] == tests["skipped"] == 0)
            check(label + " one process with 200 real concurrent threads", len(evidence["process_ids"]) == 1 and evidence["threads"] == evidence["max_active"] == 200)
            if kind == "buggy":
                check(label + " controlled lost-update FAIL", report["overall_status"] == "FAIL" and tests["failed"] > 0
                      and evidence["gate_arrivals"] == evidence["gate_parties"] == 200 and evidence["gate_release"] == "all_arrived"
                      and evidence["successes"] == evidence["orders"] == evidence["ledger"] == 200
                      and evidence["business_errors"] == {} and evidence["available"] == 49 and evidence["reserved"] == 1
                      and evidence["oracle_consistent"] is False)
            else:
                check(label + " reference PASS with independent accounting", report["overall_status"] == "PASS" and tests["passed"] == 14
                      and evidence["successes"] == evidence["orders"] == evidence["ledger"] == 50
                      and evidence["business_errors"] == {"InsufficientInventory": 150}
                      and evidence["available"] == 0 and evidence["reserved"] == 50 and evidence["oracle_consistent"])
            flow = OrderFlow(ROOT / "runs" / report["run_id"] / "workspace/business.sqlite")
            check(label + " environment independently reset", report["environment_reset"] is True and
                  flow.get_inventory("SKU-1")["available"] == 50 and flow.audit()["orders"] == [])
    check("Twenty unique independent run IDs", len({r["run_id"] for r in repeats}) == 20)
    check("Repeat evaluator/private/fixture/suite/environment fingerprints identical", all(r["fingerprints"] == repeats[0]["fingerprints"] for r in repeats))
    for kind in ("buggy", "reference"):
        selected = [reports[f"repeat-{n:02}-{kind}"] for n in range(1, 11)]
        outcomes = lambda r: [(t["name"], t["outcome"]) for t in r["test_results"]["tests"]]
        check(kind + " full test verdict set stable across ten runs", all(outcomes(r) == outcomes(selected[0]) for r in selected))
    query = run("A-report-query", cli + ["report", "--run-id", repeats[-1]["run_id"]])
    check("Report read equals archived final result", query == reports["repeat-10-reference"])
    reset = run("A-explicit-reset", cli + ["reset", "--episode", "A"])
    check("A reset isolated from Smoke", reset["status"] == "RESET" and other["run_id"] not in reset["run_ids"])
    for label, report in reports.items():
        directory = ROOT / "runs" / report["run_id"]
        check(label + " archived JSON and events", (directory / "evaluation_report.json").is_file() and (directory / "execution_trace.jsonl").is_file())
        check(label + " no invented Agent or experience observations", report["agent"]["execution"] == "UNAVAILABLE" and report["experience"]["status"] == "DISABLED")

    success = all(r["matches_expectation"] for r in records) and all(c["passed"] for c in checks)
    summary = {"validation_id": archive.name, "conclusion": "PASS" if success else "FAIL", "commands": records,
               "checks": checks, "developer_tests": developer, "original_tests": original,
               "phase1_validation": str((phase1_dir / "validation.json").relative_to(ROOT)),
               "reproductions": reproductions, "repeats": repeats, "run_ids": {k: v["run_id"] for k, v in reports.items()}}
    (archive / "validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Phase 2 Validation Report", "", f"最终结论：**{summary['conclusion']}**", "",
             "范围：Episode A 与框架扩展性验证；停止在 Phase 2。B/C/D 仍 PLANNED / NOT_IMPLEMENTED。Codex 自动接入、GraphSwarm、MCP、FalkorDB、G0–G3、Dashboard、完整支付/异步 Worker 均未实现或未运行。", "",
             f"Validation ID：`{archive.name}`。全部命令为实际 subprocess，记录 UTC 时间、完整 argv、退出状态及 stdout/stderr。", "",
             f"[机器验收记录]({(archive / 'validation.json').relative_to(ROOT)}) · [Phase 1 回归记录]({summary['phase1_validation']})", "",
             "## 运行环境与测试数量", "",
             f"- 开发者测试：{developer['passed']} / {developer['collected']} PASS；原有 46 项另行实际执行：{original['passed']} / 46 PASS。",
             "- SMOKE-001：独立 8 项隐藏测试，正反验证、ERROR、TIMEOUT、归档、重置由 Phase 1 验收重跑。",
             "- Episode A：独立 14 项隐藏测试，库存/数量/线程数变化、多 SKU、异常、取消/预留幂等、回滚、重置和宿主数据库对账。",
             "- 每次主场景 200 个业务请求、200 个真实线程、一个 Worker 进程、独立 SQLite 数据库；记录 PID/thread IDs/monotonic 开始结束时间与 max_active。", "",
             "## 并发实现与真实缺陷", "",
             "通用 RPC batch 使用 ThreadPoolExecutor，首波 Barrier 同步入口；可选 inventory_read Event 在旧快照读取并关闭读连接后放行，最多等待 2 秒。正确修复不必调用 checkpoint；锁修复等待后放行而不死锁。Worker 不含库存答案或判分规则。",
             "缺陷是事务前读取库存，再在事务内用过期快照绝对覆写。原 BEGIN IMMEDIATE、行非负/守恒、唯一键和 FK 全保留；这些约束不能约束跨表丢失更新。200 个请求均旧读成功时，实际订单/账本 200 条而库存 49/1，Oracle 检出 ledger_matches/order_reservations_match 冲突。",
             "参考补丁恢复事务内条件相对 UPDATE；原 API/容量/线程入口保留。另用整段 RLock 与保留旧读取但采用条件原子 UPDATE 的提交实际运行完整 14 项，验证不限定修复策略。", "",
             "## 正反与错误验收", "", "| 提交 | Run ID | 判定 | passed / failed / errors / skipped |", "|---|---|---|---|"]
    for label, report in reports.items():
        if label.startswith("repeat-"):
            continue
        tests = report["test_results"]
        counts = " / ".join(str(tests[k]) for k in ("passed", "failed", "errors", "skipped")) if tests else "未执行"
        lines.append(f"| {label} | `{report['run_id']}` | {report['overall_status']} | {counts} |")
    lines += ["", "独立复现器（单个受控 batch；不冒充完整 14 项 Evaluator）：", ""]
    for kind, result in reproductions.items():
        lines.append(f"- {kind}：`{result['status']}`，Run `{result['run_id']}`，[实际复现报告]({result['report']})。")
    lines += ["", "## 连续 10 轮独立初始化", "",
              "每轮分别新建 Run UUID、候选目录和数据库，完整运行 14 项 suite；不是复用 pytest 结果或旧 DB。", "",
              "| 轮次 | 提交 | Run ID | 判定 | 总数/P/F/E/S | 主场景成功/不足 | available/reserved | 线程/max_active | Oracle |", "|---:|---|---|---|---|---|---|---|---|"]
    for row in repeats:
        evidence, counts = row["primary_evidence"], row["counts"]
        lines.append(f"| {row['round']} | {row['kind']} | `{row['run_id']}` | {row['status']} | " +
                     "/".join(str(counts[k]) for k in ("collected", "passed", "failed", "errors", "skipped")) +
                     f" | {evidence['successes']}/{evidence['business_errors'].get('InsufficientInventory',0)} | {evidence['available']}/{evidence['reserved']} | {evidence['threads']}/{evidence['max_active']} | {'一致' if evidence['oracle_consistent'] else '账本冲突'} |")
    lines += ["", "所有 buggy 主场景均须 gate arrivals=parties=200、all_arrived，实际成功 200、无锁超时；所有参考均须成功 50 / 不足 150、库存 0/50。每轮完整失败原因与证据在 validation.json 的 repeats 字段，JUnit/Oracle/batch/事件在对应 Run。",
              "补充的无 checkpoint 压力路径不固定线程写入次序，最终判据仍是业务不变量；上表与全 suite verdict-set 稳定性检查单独验证每轮是否一致，没有忽略非确定性失败。", "",
              "## 指纹与隔离", "",
              "Run 保存 Submission 与实际候选 SHA256、public manifest SHA256、private manifest 文件 SHA256、Evaluator version/SHA256、Fixture version/SHA256、Suite version/SHA256、Python/SQLite/pytest/pluggy 与 bwrap/git 的实际版本及二进制 SHA256。准备前后版本改变拒绝复用；评测期间可信源码变化判 ERROR。20 轮指纹必须完全一致。",
              "候选通过原 bubblewrap 物理挂载边界执行。A 验收实际探测 Hidden Tests、Reference Patch、Private Manifest、宿主 app、其他 Run 及 /proc/1/root 逃逸路径，并保留候选 app 存在的正控。Sandbox 无功能改动；完整隔离回归仍运行。宿主 Oracle 在 Worker 关闭后只读查询原 DB，并在独立副本上验证约束语义，不依赖 candidate audit。", "",
              "## 失败记录与修复", "",
              "- 开发首轮 buggy Run `f7dc4f95-86ff-4255-86a8-4390d9cf9c65`：FAIL，5/9/0/0；200 线程旧读后 SQLite 原 5 秒等待产生 96 个 OperationalError，104 个实际成功订单而库存49/1。该原始报告和堆栈保留；不是最终重复验收。",
              "- 根据实际锁竞争将连接有界 busy timeout 改为 30 秒；复查 Run `1a1f31d2-efe4-4c10-a8e0-5362a935ef5a`：200 个业务成功、0 OperationalError，库存49/1、订单和ledger200，仍 FAIL。未改库存容量、并发度、断言或 schema。",
              "- 初次复现器命令误填不存在的 `evaluator/reference_patches/A.diff`，Run `955ae4ac-307a-42d1-af7b-a29f47fd0db6` 实际 FileNotFoundError / ERROR / 退出2；修正为 A-v01.diff 后正反复现成功，旧错误记录保留。",
              "- 独立审查发现 Evaluator 重用 artifacts 会混入旧 batch/Oracle，已启动前清理并加入真实 TIMEOUT 旧证据回归；发现仅数 CHECK 无法判断部分约束移除，已加入可信副本语义探针及回归。",
              "- 上表缺陷 FAIL 为真实必要断言失败；语法错误 ERROR 和 1 秒 TIMEOUT 为独立负例。完整原始错误信息保留在每 Run 的 JUnit、pytest 日志和 execution_errors。", "",
              "## 实际命令与退出状态", "",
              "本机外层通过 `scripts/python312 scripts/validate_phase2.py` 使用 Python 3.12；内部完整命令如下。退出 1/2/3/4 分别代表候选 FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED，不应误读为对应候选 PASS。", ""]
    for record in records:
        lines += [f"### {record['label']}", "", f"UTC `{record['started_at']}` → `{record['ended_at']}`；实际退出 `{record['exit_code']}`，预期 `{record['expected_exit_code']}`。", "",
                  "```bash", record["command"], "```", "", f"[stdout]({record['stdout']}) · [stderr]({record['stderr']})", ""]
    lines += fingerprint_report_lines(repeats[0]["fingerprints"])
    lines += ["## 逐项验收", "", "| 检查 | 结果 |", "|---|---|"]
    lines += [f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in checks]
    lines += ["", "## 已知限制与下一阶段接口", "",
              "- 仅验证单进程、多线程、文件 SQLite 拓扑。多进程、多机、网络隔离、CPU/内存/seccomp 限制、敌对 RPC/反作弊与任意恶意 SQLite 文件防御不是本轮完成项。30 秒等待有边界，超出竞争能力仍由异常/超时判失败。",
              "- 场景正式故障 variant 仅 v01/stale-snapshot；多组参数与时序测试不宣称已实现新的正式 Episode。",
              "- Agent adapter 仍 manual，原生 Codex 自动启动/委派/trace 不可用；Experience adapter 四接口 Disabled，无经验命中、决策或反馈。",
              "- 后续 Episode 通过 registry/factory/private suite 接入，Runner 生命周期不改；Payment/Event 契约与经验接口留给后续阶段。",
              "- 源码、补丁、batch/Oracle、JUnit、报告和真实版本指纹提供未来经验产生的证据；本轮没有运行 Decision Trace、Experience Retrieval 或 Feedback Evolution。", "",
              f"最终验收：**{summary['conclusion']}**。停止在 Phase 2，等待下一轮架构审查。", ""]
    (archive / "PHASE2_VALIDATION_REPORT.md").write_text("\n".join(lines))
    print(f"{summary['conclusion']}: {len(records)} commands, {len(checks)} checks; {archive}", flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
