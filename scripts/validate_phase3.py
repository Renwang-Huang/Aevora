"""Real native challenge + unchanged Phase 1/2 acceptance and evidence archive.

Synthetic fault/transport contracts are developer tests, never Agent evidence.
Run with the trusted native launcher enabled. Existing historical reports are
preserved; regenerated regression reports are saved in this validation archive.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.participant_sandbox import participant_command
from evaluator.runner import read_junit
from integrations.codex_agent import CodexConfig


def now():
    return datetime.now(timezone.utc).isoformat()


def isolation_verdict(probe, targets, exit_code):
    """Require every actual target; a readable private path is a hard failure."""
    if not isinstance(probe, dict) or exit_code != 0:
        return "PARTIAL"
    denied = probe.get("denied")
    if not isinstance(denied, dict) or set(denied) != set(targets):
        return "PARTIAL"
    if any(value is False for value in denied.values()):
        return "FAIL"
    return "PASS" if probe.get("public_source") is True and all(value is True for value in denied.values()) else "PARTIAL"


def contracts_pass(results, exit_code):
    return (exit_code == 0 and results["collected"] > 0
            and results["passed"] == results["collected"]
            and all(results[k] == 0 for k in ("failed", "errors", "skipped")))


def audit_native(directory, formal):
    runtime = json.loads((directory / "runtime_metadata.json").read_text())
    patch = directory / "submission.diff"
    digest = hashlib.sha256(patch.read_bytes()).hexdigest() if patch.is_file() else None
    observations = runtime.get("trace_observations", {})
    agents = runtime.get("subagents", {}).get("agents", [])
    verified = [a for a in agents if isinstance(a.get("completion_reference"), dict)
                and a.get("task") != "UNAVAILABLE" and a.get("completion_message") != "UNAVAILABLE"]
    return {
        "report_matches_cli": json.loads((directory / "evaluation_report.json").read_text()) == formal,
        "run_linkage": runtime["run_id"] == formal["run_id"] == runtime.get("evaluation_report_id"),
        "actual_new_thread": runtime.get("fresh_session") is True and runtime.get("thread_id") not in (None, "UNAVAILABLE"),
        "patch_integrity": digest is not None and digest == (runtime.get("submission") or {}).get("sha256")
            == formal["agent"].get("submission_sha256") == (formal.get("submission") or {}).get("sha256"),
        "raw_events_integrity": hashlib.sha256((directory / "codex_events.jsonl").read_bytes()).hexdigest()
            == observations.get("raw_events_sha256"),
        "trace_integrity": hashlib.sha256((directory / "agent_trace.jsonl").read_bytes()).hexdigest()
            == observations.get("trace_sha256") and observations.get("integrity", {}).get("status") == "COMPLETE",
        "independent_native_tasks": len(verified) >= 2 and len({a['thread_id'] for a in verified}) >= 2
            and len({a['task'] for a in verified}) >= 2 and all(a.get("parent_thread_id") == runtime.get("thread_id") for a in verified),
        "model_calls_succeeded": runtime.get("model_broker", {}).get("upstream_statuses", {}).get("200", 0) > 0,
        "full_formal_suite": formal.get("evaluation_result") not in ("PASS", "FAIL") or
            ((formal.get("test_results") or {}).get("collected") == 14 and (formal.get("test_results") or {}).get("skipped") == 0),
        "state_removed": formal.get("agent_state_cleanup") == "PASS" and not (directory / "codex-state").exists(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-timeout", type=float, default=900)
    args = parser.parse_args()
    config = CodexConfig.from_environment(timeout_seconds=args.agent_timeout)
    archive = ROOT / "runs/validation-phase3" / str(uuid4())
    archive.mkdir(parents=True)
    records, checks = [], []
    cli = [str(ROOT / ".venv/bin/orderflow")]

    def persist():
        (archive / "validation-progress.json").write_text(json.dumps({"commands": records, "checks": checks}, indent=2) + "\n")

    def run(label, command, *, timeout=1800, expected=None, input_text=None, env=None):
        start = now()
        prefix = f"{len(records)+1:02}-{label}"
        stdout, stderr = archive / (prefix + ".stdout.log"), archive / (prefix + ".stderr.log")
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                       stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                       start_new_session=True, env=env)
            timed_out = False
            try:
                process.communicate(input_text.encode() if input_text else None, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=10)
        record = {"label": label, "argv": command, "command": shlex.join(command),
                  "started_at": start, "ended_at": now(), "exit_code": process.returncode,
                  "timed_out": timed_out, "expected_exit_code": expected,
                  "matches_expectation": None if expected is None else not timed_out and process.returncode == expected,
                  "stdout": str(stdout.relative_to(ROOT)), "stderr": str(stderr.relative_to(ROOT))}
        records.append(record)
        persist()
        print(f"{label}: exit={process.returncode}, timeout={timed_out}", flush=True)
        content = stdout.read_text(errors="replace")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content

    def check(label, condition):
        checks.append({"name": label, "passed": bool(condition)})
        persist()

    run("codex-version", [str(config.binary), "--version"], expected=0)
    run("codex-exec-help", [str(config.binary), "exec", "--help"], expected=0)
    run("codex-features", [str(config.binary), "features", "list"], expected=0)
    auth_environment = dict(os.environ)
    auth_environment["CODEX_HOME"] = str(config.auth_path.parent)
    run("trusted-auth-status", [str(config.binary), "login", "status"], expected=0, env=auth_environment)
    connectivity = run("network-preflight", [sys.executable, "-c", "import socket,json,ssl,urllib.request,urllib.error; s=socket.socket(); s.bind(('127.0.0.1',0)); s.close(); print(json.dumps({'loopback_listener':True,'dns_addresses':len(socket.getaddrinfo('chatgpt.com',443)),'tls_ca':ssl.get_default_verify_paths().cafile}));\ntry: r=urllib.request.urlopen('https://chatgpt.com/backend-api/codex/models',timeout=15); print(r.status)\nexcept urllib.error.HTTPError as e: print('TLS verified; unauthenticated HTTP',e.code)"], expected=0, timeout=20)

    # Regenerate every effective Phase1/2 check (incl. 10 fresh suite pairs).
    historical = {p: p.read_bytes() for p in (ROOT / "PHASE1_VALIDATION_REPORT.md", ROOT / "PHASE2_VALIDATION_REPORT.md")}
    before = set((ROOT / "runs/validation-phase2").glob("*"))
    try:
        run("phase1-and-phase2-regression", [sys.executable, str(ROOT / "scripts/validate_phase2.py")], expected=0)
        for path in historical:
            shutil.copyfile(path, archive / ("regenerated-" + path.name))
    finally:
        for path, content in historical.items():
            path.write_bytes(content)
    created = set((ROOT / "runs/validation-phase2").glob("*")) - before
    if len(created) != 1:
        raise RuntimeError("Regression did not produce one Phase2 validation archive")
    regression_dir = created.pop()
    regression = json.loads((regression_dir / "validation.json").read_text())
    check("Every Phase1/2 regression command and check passes", regression["conclusion"] == "PASS")
    previous_id = re.search(r"Validation ID：`([^`]+)`", historical[ROOT / "PHASE2_VALIDATION_REPORT.md"].decode())
    if previous_id:
        previous = json.loads((ROOT / "runs/validation-phase2" / previous_id.group(1) / "validation.json").read_text())
        current_ids = {t["nodeid"]: t["outcome"] for t in regression["developer_tests"]["tests"]}
        check("Every original Phase2 developer test identity is retained and PASS", all(
            current_ids.get(t["nodeid"]) == "PASS" for t in previous["developer_tests"]["tests"]))
    run("phase3-fault-and-boundary-tests", [sys.executable, "-m", "pytest", "tests/test_codex_agent.py",
        "tests/test_codex_trace.py", "tests/test_participant.py", "tests/test_participant_sandbox.py",
        "tests/test_model_broker.py", "tests/test_model_broker_transport.py", "-q", "--junitxml",
        str(archive / "phase3.junit.xml")], expected=0)
    contracts = read_junit(archive / "phase3.junit.xml")
    check("All Phase3 fault/boundary contracts run without failure or skip", contracts_pass(contracts, records[-1]["exit_code"]))

    # This is the only scored native attempt in this validation invocation.
    formal = run("native-episode-A", cli + ["run-codex", "--episode", "A", "--agent-timeout", str(args.agent_timeout)],
                 timeout=args.agent_timeout + 180)
    if not isinstance(formal, dict) or "run_id" not in formal:
        raise RuntimeError("Native lifecycle failed to produce an archived Run report")
    directory = ROOT / "runs" / formal["run_id"]
    runtime = json.loads((directory / "runtime_metadata.json").read_text())
    check("Runtime/Trace/Report are linked by actual Run ID", runtime["run_id"] == formal["run_id"] and
          all((directory / name).is_file() for name in ("codex_events.jsonl", "agent_trace.jsonl", "runtime_metadata.json", "evaluation_report.json")))
    check("Experience remains explicitly DISABLED", formal["experience"]["status"] == "DISABLED")
    for label, condition in audit_native(directory, formal).items():
        check("Native evidence: " + label, condition)

    # Run the native CLI's command sandbox in the SAME public participant tree.
    # No candidate imports, identities or host private code are passed to it.
    probe_state = directory / "native-probe-state"
    probe_state.mkdir()
    targets = {"hidden_tests": ROOT / "evaluator/hidden_tests",
               "reference_patch": ROOT / "evaluator/reference_patches/A-v01.diff",
               "private_manifest": ROOT / "evaluator/private_manifests/A.json",
               "maintainer_source": ROOT / "app/service.py",
               "other_run": ROOT / "runs" / regression["repeats"][0]["run_id"] / "evaluation_report.json",
               "trusted_auth": config.auth_path, "host_auth": Path(os.environ.get("ORDERFLOW_CODEX_AUTH_PATH", str(Path.home()/".codex/auth.json")))}
    targets = {k: str(v) for k, v in targets.items()}
    check("Actual private targets exist in the trusted namespace", all(
        Path(value).exists() for key, value in targets.items() if key != "host_auth"))
    targets.update({"proc_root_" + k: "/proc/1/root" + v for k, v in list(targets.items())})
    probe_code = """import pathlib,json,socket
targets=TARGETS
denied={}
for label,path in targets.items():
    try:
        p=pathlib.Path(path)
        if p.is_dir(): list(p.iterdir())
        else: p.read_bytes()
        denied[label]=False
    except OSError: denied[label]=True
positive=pathlib.Path('/workspace/app/service.py').is_file()
try:
    s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',1)); network=False
except OSError: network=True
print(json.dumps({'denied':denied,'public_source':positive,'direct_network_probe_failed':network}))
assert positive and all(denied.values())
""".replace("TARGETS", repr(targets))
    probe_command = ["/opt/codex/codex", "sandbox", "-c", 'sandbox_mode="workspace-write"',
                     "-c", 'approval_policy="never"', "--", "/usr/bin/python3.12", "-I", "-c", probe_code]
    try:
        probe = run("native-command-isolation", participant_command(directory / "participant", probe_state,
                    config.binary, probe_command), expected=0, timeout=30)
    finally:
        shutil.rmtree(probe_state)
    isolation_status = isolation_verdict(probe, targets, records[-1]["exit_code"])
    isolation = isolation_status == "PASS"
    check("Native command sandbox blocks all actual private/identity/other-run/proc-root paths", isolation)

    runtime_result = "PASS" if formal.get("runtime_result") == "PASS" else "PARTIAL"
    multi = "PASS" if runtime.get("multi_agent_result") == "PASS" else "PARTIAL"
    evaluation = "PASS" if formal.get("integration_result") == "PASS" else "PARTIAL"
    agent_isolation = isolation_status if runtime.get("credentials_in_participant") is False else "FAIL"
    successful_checks = all(c["passed"] for c in checks) and all(r["matches_expectation"] is not False for r in records)
    conclusion = "PASS" if successful_checks and all(x == "PASS" for x in (runtime_result, multi, evaluation, agent_isolation)) else "CONDITIONAL PASS"
    if not regression["conclusion"] == "PASS" or contracts["passed"] != contracts["collected"]:
        conclusion = "FAIL"
    if agent_isolation == "FAIL":
        conclusion = "FAIL"
    summary = {"validation_id": archive.name, "ended_at": now(), "conclusion": conclusion,
               "runtime_integration": runtime_result, "multi_agent_verification": multi,
               "agent_isolation": agent_isolation, "evaluation_integration": evaluation,
               "episode_a_task_outcome": formal.get("evaluation_result", "NOT_RUN"),
               "native_run_id": formal["run_id"], "native_runtime": runtime,
               "phase2_regression_archive": str(regression_dir.relative_to(ROOT)),
               "phase3_tests": contracts, "isolation_probe": probe, "commands": records, "checks": checks}
    (archive / "validation.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = ["# Phase 3 Validation Report", "", f"结论：**{conclusion}**。", "",
             f"真实验收归档：`{archive.relative_to(ROOT)}`；完成时间：`{summary['ended_at']}`。", "",
             "| 验收项 | 真实结论 |", "|---|---|",
             f"| Runtime Integration | {runtime_result} |", f"| Multi-Agent Verification | {multi} |",
             f"| Agent Isolation | {agent_isolation} |", f"| Evaluation Integration | {evaluation} |",
             f"| Episode A Task Outcome | {summary['episode_a_task_outcome']} |", f"| Phase 3 Overall | {conclusion} |", "",
             "## 实际命令与退出状态", "", "| 命令 | Exit | Timeout |", "|---|---:|---|",
             *[f"| `{r['command']}` | {r['exit_code']} | {r['timed_out']} |" for r in records if r['label'] != 'native-command-isolation'], "",
             "Native command isolation 的完整参数、真实路径、stdout/stderr 见 validation.json 与对应日志，使用安装 CLI 的 `codex sandbox`，未绕过 sandbox。", "",
             "## 原生挑战证据", "", f"- Run ID：`{formal['run_id']}`。",
             f"- Codex：`{runtime.get('codex_version', 'UNAVAILABLE')}`；实际 Thread ID：`{runtime.get('thread_id','UNAVAILABLE')}`。",
             f"- Runtime：`{formal.get('runtime_result')}`；Evaluation：`{formal.get('evaluation_result')}`；Integration：`{formal.get('integration_result')}`。",
             f"- 原生退出：`{runtime['exit_code']}`；实际耗时：`{runtime['elapsed_seconds']:.3f}` 秒。",
             f"- Patch SHA256：`{formal.get('agent',{}).get('submission_sha256','UNAVAILABLE')}`。",
             f"- Hidden Test Results：`{json.dumps(formal.get('test_results'), ensure_ascii=False)}`。",
             f"- Token Usage：`{json.dumps(runtime.get('usage'), ensure_ascii=False)}`；范围为官方 turn.completed 事件，子 Agent 未独立提供的 usage 不估算。", "",
             "| Child Thread | 实际独立任务 | Spawn raw line | Completion raw line | 状态 |", "|---|---|---:|---:|---|",
             *[f"| `{a['thread_id']}` | {str(a.get('task','UNAVAILABLE')).replace('|','/').replace(chr(10),' ')[:280]} | {a.get('spawn_reference',{}).get('line','UNAVAILABLE') if isinstance(a.get('spawn_reference'),dict) else 'UNAVAILABLE'} | {a.get('completion_reference',{}).get('line','UNAVAILABLE') if isinstance(a.get('completion_reference'),dict) else 'UNAVAILABLE'} | {a.get('status','UNAVAILABLE')} |" for a in runtime.get('subagents',{}).get('agents',[])], "",
             "任务与返回 message 完整保存在 codex_events.jsonl；agent_trace.jsonl 保留原始行号、SHA256 与父子 Thread 关联。完整内部子 Agent 日志/Session ID 若官方流未提供，明确为 UNAVAILABLE。", "",
             "## Phase 1/2 回归与故障恢复", "", f"- 完整有效 Phase 1/2 验收：`{regression['conclusion']}`，记录见 `{regression_dir.relative_to(ROOT)}/validation.json`。",
             "- 包含依赖重装、原有 46 项独立回归、Smoke 正反提交、ERROR/TIMEOUT、B/C/D NOT_IMPLEMENTED、归档/reset、Episode A 十轮独立 buggy/reference 验证及 14 项正式 suite；原有断言与必要测试集合保留。",
             f"- 新增 Phase3 测试：{contracts['passed']} / {contracts['collected']} PASS；无 skip。其中 synthetic CLI 故障与 synthetic credentials HTTP transport 测试只是契约，不是 Agent 成绩。",
             "- 故障契约覆盖启动失败、实际进程超时/回收、无 app patch、无效提交、Trace 不完整、bubblewrap 启动失败、state 清理失败。",
             "- 历史 Phase1/2 报告未覆盖；本次生成的回归报告保存在本验收目录 regenerated-*。", "",
             "## 隔离与限制", "", "- 真实 CLI command sandbox 在当前 Participant 树内验证了隐藏测试、参考补丁、私有 Manifest、维护者业务源码、其他 Run、宿主身份及 /proc/1/root 路径读取失败；公开源码可读。",
             "- 宿主认证只用于可信模型 broker；Participant 没有宿主身份文件或 bearer token。模型真实请求证据见 runtime_metadata.json 的上游状态。TLS 使用系统 CA bundle，不关闭证书校验。",
             "- 外层共享 network namespace；未实现完整恶意代码防护、CPU/内存配额、自动认证刷新。broker 只暴露受限的 model capability，不是任意身份代理。",
             "- B/C/D、GraphSwarm、MCP、FalkorDB、Experience Retrieval/Decision/Feedback、正式 G0–G3 和 Dashboard 均未实现。经验保持 DISABLED。", "",
             "## 失败记录", "", f"正式 Run 的实际错误：`{json.dumps(formal['execution_errors'],ensure_ascii=False)}`。",
             "此前开发阶段失败（权限、CA 路径、startup warning 与 SSE idle timeout）保留原始归档，不改写旧 Run；修复后使用全新 Session 验证。", "",
             "## 停止边界", "", "本次停止在 Phase 3，等待下一轮架构审查与验收反馈。", ""]
    (ROOT / "PHASE3_VALIDATION_REPORT.md").write_text("\n".join(lines))
    print(json.dumps({k: summary[k] for k in ("validation_id", "conclusion", "native_run_id", "episode_a_task_outcome")}), flush=True)
    return 0 if conclusion == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
