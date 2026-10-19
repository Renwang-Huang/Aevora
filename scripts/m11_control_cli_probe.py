#!/usr/bin/env python3
"""Cross-PID-namespace status/cancel using real CLI and Participant processes.

No model request is made. Local computation is a runtime control fixture, not
a Codex challenge or an evaluated incident repair.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

OWNER = r'''
from dataclasses import replace
import json,os,signal,subprocess,sys,time
from pathlib import Path
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from benchmark.participant_sandbox import participant_command
from benchmark.resources import PARTICIPANT_LIMITS,CgroupScope,ResourceWatchdog
from integrations.runtime_control import RuntimeControl
archive=Path(sys.argv[1]);runs=archive/'runs'
prepared=BenchmarkRunner(runs).prepare('D','v01')
run=runs/prepared['run_id']; workspace=build_participant(run/'workspace',run/'participant',agent_mode='single')
state=run/'codex-state';state.mkdir()
control=RuntimeControl(run,run.name,completion_policy='completion-aware',agent_mode='single')
control.install_signals()
limits=replace(PARTICIPANT_LIMITS,wall_seconds=None)
scope=CgroupScope.create(limits)
worker=r"""import hashlib,os,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-I','-c',"import hashlib,time; value=b'child-public-computation';\nwhile True:\n value=hashlib.sha256(value).digest();time.sleep(.001)"])
value=open('/workspace/app/service.py','rb').read()
print('SYNTHETIC_CONTROL_WORK_STARTED_NOT_CODEX',flush=True)
while True:
 for i in range(1000):value=hashlib.sha256(value).digest()
 print('actual-local-work '+value.hex(),flush=True)
 time.sleep(.05)
"""
command=scope.wrap_command(participant_command(workspace,state,Path(os.environ['ORDERFLOW_CODEX_BINARY']),
 ['/usr/bin/python3.12','-I','-c',worker],network_isolated=True,resources=limits))
with (run/'local-worker.stdout.log').open('wb') as out,(run/'local-worker.stderr.log').open('wb') as err:
 process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
 watchdog=ResourceWatchdog(process.pid,limits,output_roots=(workspace,state,run)).start()
 while (run/'local-worker.stdout.log').stat().st_size == 0 and process.poll() is None:
  control.publish(watchdog=watchdog,workspace=workspace);time.sleep(.01)
 if process.poll() is not None:raise RuntimeError('Synthetic work process failed before readiness')
 control.publish(watchdog=watchdog,workspace=workspace)
 (archive/'ready.json').write_text(json.dumps({'run_id':run.name,'controller_pid_namespace':os.readlink('/proc/self/ns/pid'),
  'source':'SYNTHETIC_RUNTIME_CONTROL_NOT_CODEX','model_calls':0}))
 try:
  while process.poll() is None:
   if control.cancellation():break
   control.publish(watchdog=watchdog,workspace=workspace);time.sleep(.05)
 finally:
  if process.poll() is None:os.killpg(process.pid,signal.SIGKILL)
  process.wait(timeout=10)
  monitor=watchdog.close(cleanup=True);kernel=scope.close()
  cancellation=control.cancellation()
  terminal='CANCELLED' if cancellation else 'ERROR'
  classification=cancellation['classification'] if cancellation else 'PROCESS_EXITED_WITHOUT_CANCEL'
  control.finish(terminal,classification)
  import shutil
  shutil.rmtree(state)
  result={'run_id':run.name,'status':terminal,'failure_kind':classification,'evaluation_status':'NOT_RUN',
   'source':'SYNTHETIC_RUNTIME_CONTROL_NOT_CODEX','model_calls':0,'watchdog':monitor,'cgroup':kernel,
   'state_removed':not state.exists(),'cancel_request':control.cancellation(),'work_bytes':(run/'local-worker.stdout.log').stat().st_size}
  (archive/'owner_result.json').write_text(json.dumps(result,indent=2)+'\n')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.absolute()
    archive.mkdir(parents=True, exist_ok=False)
    owner_script = archive / "trusted_owner.py"
    owner_script.write_text(OWNER)
    records = []

    def execute(label, arguments, expected):
        target = archive / label
        target.mkdir()
        command = [str(ROOT / "scripts/orderflow"), "--runs-root", str(archive / "runs"), *arguments]
        start, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
        with (target / "stdout.log").open("wb") as out, (target / "stderr.log").open("wb") as err:
            process = subprocess.run(command, stdout=out, stderr=err, cwd=ROOT, timeout=20)
        record = {"argv": command, "started_at": start, "ended_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.monotonic() - clock, "exit_code": process.returncode,
            "expected_exit_code": expected,
            "stdout_sha256": hashlib.sha256((target / "stdout.log").read_bytes()).hexdigest(),
            "stderr_sha256": hashlib.sha256((target / "stderr.log").read_bytes()).hexdigest()}
        (target / "command.json").write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)
        assert process.returncode == expected, record
        return json.loads((target / "stdout.log").read_text()) if expected == 0 else None

    command = [str(ROOT / "scripts/python312"), str(owner_script), str(archive)]
    environment = {**os.environ, "ORDERFLOW_ENABLE_CODEX": "1"}
    with (archive / "owner.stdout.log").open("wb") as out, (archive / "owner.stderr.log").open("wb") as err:
        owner = subprocess.Popen(command, stdout=out, stderr=err, cwd=ROOT, env=environment, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while not (archive / "ready.json").exists() and owner.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert (archive / "ready.json").exists(), "Control fixture startup failed; this is not a live-model timeout"
            ready = json.loads((archive / "ready.json").read_text())
            run_id = ready["run_id"]
            status = execute("status", ["status", "--run-id", run_id], 0)
            assert status["run_id"] == run_id and status["status"] == "RUNNING"
            assert status["controller_pid_namespace"] != status["control_query"]["caller_pid_namespace"]
            snapshot = execute("snapshot", ["snapshot", "--run-id", run_id], 0)
            assert snapshot["evidence_status"] == "PARTIAL_SNAPSHOT"
            execute("wrong-run-cancel", ["cancel", "--run-id", "00000000-0000-4000-8000-000000000000"], 2)
            assert not (archive / "runs/00000000-0000-4000-8000-000000000000/operator_cancel.json").exists()
            cancellation = execute("cancel", ["cancel", "--run-id", run_id, "--reason", "M1.1 cross-namespace safety probe"], 0)
            assert cancellation["status"] == "CANCEL_REQUESTED"
            owner.wait(timeout=20)  # Bounded cleanup after explicit cancellation, not a run deadline.
            assert owner.returncode == 0
            terminal = execute("terminal-status", ["status", "--run-id", run_id], 0)
            assert terminal["status"] == "CANCELLED"
            execute("terminal-cancel-refused", ["cancel", "--run-id", run_id], 2)
        finally:
            if owner.poll() is None:
                owner.terminate()
                owner.wait(timeout=20)
    result = json.loads((archive / "owner_result.json").read_text())
    checks = {"actual_work_observed": result["work_bytes"] > 0,
        "process_tree_empty": result["watchdog"]["remaining_pids"] == [],
        "cgroup_cleanup": result["cgroup"]["cleanup_complete"] is True,
        "cgroup_removed": not Path(result["cgroup"]["path"]).exists(),
        "state_removed": result["state_removed"] is True,
        "cancel_distinct_from_timeout": result["failure_kind"] == "CANCELLED_BY_OPERATOR"}
    summary = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "run_id": run_id,
        "model_calls": 0, "source": "SYNTHETIC_CONTROL_FIXTURE_WITH_REAL_CLI_AND_PARTICIPANT_BOUNDARY",
        "controller_pid_namespace": ready["controller_pid_namespace"],
        "status_cli_pid_namespace": status["control_query"]["caller_pid_namespace"],
        "caller_host_pid_namespace": os.readlink("/proc/self/ns/pid"), "commands": records,
        "limitations": "Control proof only; official native transport and real blind sessions are separate gates"}
    (archive / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
