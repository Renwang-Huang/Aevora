#!/usr/bin/env python3
"""Create M1.1 live admission only from completed, rehashed dynamic receipts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.absolute()
    receipts = {}

    def completed(label, expected=0):
        path = archive / label / "command.json"
        value = json.loads(path.read_text())
        assert value["exit_code"] == expected, (label, value["exit_code"])
        outputs = {}
        for name in ("stdout", "stderr"):
            outputs[name] = digest(path.parent / (name + ".log"))
            if name + "_sha256" in value:
                assert outputs[name] == value[name + "_sha256"]
        receipts[label] = {"source_path": path.relative_to(archive).as_posix(), "sha256": digest(path),
            "argv": value["argv"], "exit_code": value["exit_code"], "started_at": value["started_at"],
            "ended_at": value["ended_at"], "outputs_sha256": outputs}
        return value

    for label in ("developer-integrated-command", "integrity-admission-command", "dependencies-command",
                  "cli-regression-command", "offline-regression-command", "isolation-command",
                  "cross-namespace-control-accepted-command", "gateway-connectivity-command",
                  "root-integration-accepted-command", "audit-cli-verify-command", "audit-cli-inspect-command"):
        completed(label)
    integrity = json.loads((archive / "INTEGRITY_ADMISSION.json").read_text())
    assert integrity["status"] == "PASS"
    assert integrity["checks"]["test_identities"]["original_required_count"] == 664
    assert integrity["checks"]["test_identities"]["retained"] == 664
    assert json.loads((archive / "cli-regression/summary.json").read_text())["result"] == "PASS"
    assert json.loads((archive / "offline-regression/summary.json").read_text())["result"] == "PASS"
    isolation = json.loads((archive / "isolation/summary.json").read_text())
    assert isolation["mandatory_boundary_result"] == "PASS" and isolation["model_calls"] == 0
    cancel = json.loads((archive / "cross-namespace-control-accepted/summary.json").read_text())
    assert cancel["status"] == "PASS" and all(cancel["checks"].values())
    assert cancel["controller_pid_namespace"] != cancel["status_cli_pid_namespace"]
    gateway = json.loads((archive / "gateway-connectivity/summary.json").read_text())
    assert gateway["status"] == "PASS" and gateway["tls"]["status"] == "PASS"
    assert gateway["terminal"]["actual_model"] == "gpt-5.6-terra" and gateway["terminal"]["actual_effort"] == "max"
    native = json.loads((archive / "R1_OFFICIAL_TRANSPORT_FINAL.json").read_text())
    assert native["result"] == "PASS" and len(native["probes"]) == 7
    for probe in native["probes"]:
        assert probe["cleanup_proven"] is True
        assert digest(archive / probe["result"]) == probe["result_sha256"]
        assert digest(archive / probe["receipt"]) == probe["receipt_sha256"]
    runtime_source = json.loads((archive / "R1_RUNTIME_SOURCE_FINAL.json").read_text())
    for row in runtime_source["files"]:
        assert digest(ROOT / row["path"]) == row["sha256"]
    r2 = json.loads((archive / "R2_GATE_FINAL.json").read_text())
    assert r2["result"] == "PASS"
    for relative, expected in r2["source_files_sha256"].items():
        assert digest(ROOT / relative) == expected
    offline = json.loads((archive / "R2_OFFLINE_DYNAMIC_FINAL.json").read_text())
    assert offline["status"] == "PASS" and offline["same_timestamp_exports_byte_equal"] is True
    assert digest(archive / "exports/M1-audit-lite.zip") == offline["bundle_sha256"]
    recorded_at = datetime.now(timezone.utc).isoformat()
    r1_gate = {"gate": "R1", "status": "PASS", "recorded_at": recorded_at,
        "developer_counts": integrity["checks"]["test_identities"]["counts"], "original_tests_retained": 664,
        "native_transport": {"source_path": "R1_OFFICIAL_TRANSPORT_FINAL.json", "sha256": digest(archive / "R1_OFFICIAL_TRANSPORT_FINAL.json"),
            "synthetic_gateway_cases": 7, "real_model_requests": 0},
        "operator_cancel": cancel, "command_receipts": receipts,
        "scope": "Dynamic bounded/completion-aware compatibility and declared isolation/control boundary; live six-session task is R3",
        "limitations": ["Official configured SSE idle limit remains finite and adjustable (default 600000 ms)",
            "CPU/output limits remain; no automatic resume or SIGKILL-finally guarantee",
            "Namespace/sampled CPU threat model remains CONDITIONAL; not third-party attestation"]}
    with (archive / "R1_GATE.json").open("x") as out:
        out.write(json.dumps(r1_gate, indent=2) + "\n")
    source_files = set()
    for directory in ("app", "benchmark", "evaluator", "integrations", "scripts", "tests"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix in {".py", ".json", ".md", ".diff", ".toml"}:
                source_files.add(path.relative_to(ROOT).as_posix())
    # Local environment/identity files are never copied or fingerprinted here.
    source_files.update({"scripts/python312", "scripts/orderflow", "pyproject.toml"})
    frozen = {name: digest(ROOT / name) for name in sorted(source_files)}
    snapshot = archive / "frozen_source_snapshot"
    snapshot.mkdir(exist_ok=False)
    for name in frozen:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        assert digest(target) == frozen[name]
    gate = {"gate": "R3_LIVE_ADMISSION", "mandatory_gate_result": "PASS", "recorded_at": recorded_at,
        "checks": {key: "PASS" for key in ("R1", "R2", "isolation", "submission_fidelity", "operator_cancel", "export_verifier")},
        "calibration_configuration": {"trials": 6, "order": ["single", "multi", "multi", "single", "single", "multi"],
            "provider": "gateway", "model": "gpt-5.6-terra", "reasoning_effort": "max", "completion_policy": "completion-aware",
            "agent_timeout": None, "request_budget": None, "parallel_trials": 1},
        "gateway_url": "https://api.renwang-huang.top/v1", "frozen_source_sha256": frozen,
        "r1_gate_sha256": digest(archive / "R1_GATE.json"), "r2_gate_sha256": digest(archive / "R2_GATE_FINAL.json"),
        "integrity_receipt_sha256": digest(archive / "INTEGRITY_ADMISSION.json"),
        "suite": {"episode": "D", "variant": "v01", "private_manifest_sha256": frozen["evaluator/private_manifests/D.json"],
            "required_test_count": 28},
        "scheduled_maintainer_load_policy": "All heavy tests/export tasks finished before live; serial six-session collector",
        "security_scope": "Preserved declared namespace/cgroup/model-channel boundary; not VM or absolute adversarial safety"}
    with (archive / "LIVE_GATE.json").open("x") as out:
        out.write(json.dumps(gate, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "source_files": len(frozen), "live_gate_sha256": digest(archive / "LIVE_GATE.json"),
        "r1_gate_sha256": digest(archive / "R1_GATE.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
