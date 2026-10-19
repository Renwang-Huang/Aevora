"""Three fresh blind sessions; delegation is performed only by native Codex."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.reproduce_episode_d import run_record
from benchmark.manifest import private_config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--gate",type=Path,required=True,help="trusted frozen M1 live admission receipt")
    args=parser.parse_args()
    gate=json.loads(args.gate.read_text())
    assert gate["mandatory_gate_result"]=="PASS", "Live admission gate is incomplete"
    assert gate["pilot_configuration"]=={"trials":3,"provider":"gateway","model":"gpt-5.6-terra",
        "reasoning_effort":"max","agent_timeout":1200,"request_budget":160,"parallel_trials":1}
    def verify_freeze():
        for relative,sha in gate["frozen_source_sha256"].items():
            assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==sha, f"Frozen source changed: {relative}"
    verify_freeze()
    archive=args.archive.resolve()
    archive.mkdir(parents=True,exist_ok=False)
    required=private_config("D")["expected_tests"]
    records=[]
    for index in range(1,4):
        verify_freeze()
        command=[sys.executable,"-m","benchmark.cli","--runs-root",str(archive/"runs"),
                 "run-codex","--episode","D","--variant","v01","--provider","gateway",
                 "--model","gpt-5.6-terra","--reasoning-effort","max",
                 "--agent-timeout","1200","--request-budget","160"]
        receipt,report=run_record(archive/f"pilot-{index}",command,timeout=1380)
        verify_freeze()
        tests=report.get("test_results") or {}
        record={"pilot":index,"command":receipt,
                **{key:report.get(key,"UNAVAILABLE") for key in (
                    "runtime_status","multi_agent_status","isolation_status","submission_integrity_status",
                    "evaluation_status","integration_status","submission_integrity","agent","runtime_metadata")},
                "suite_complete": sorted(t["name"] for t in tests.get("tests",[]))==sorted(required),
                "required_test_count":len(required),"execution_errors":report.get("execution_errors",[]),
                "live_gate_sha256":hashlib.sha256(args.gate.read_bytes()).hexdigest()}
        records.append(record)
        (archive/"summary.json").write_text(json.dumps(records,indent=2)+"\n")
        print(json.dumps({"pilot":index,"run_id":receipt["run_id"],"exit_code":receipt["exit_code"],
            "elapsed_seconds":receipt["elapsed_seconds"],"task_outcome":receipt["status"],
            **{k:record[k] for k in ("runtime_status","multi_agent_status","evaluation_status","integration_status")}}),flush=True)
        if receipt["collector_timeout"] or any("BLOCKED_SECURITY_GATE" in e for e in record["execution_errors"]):
            raise RuntimeError("Pilot collector/security gate blocked; unsafe continuation refused")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
