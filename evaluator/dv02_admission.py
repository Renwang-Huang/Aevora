"""D-v02-only recovery completeness, above the unchanged pytest harness."""
from __future__ import annotations
import json
from pathlib import Path
from evaluator.episode_d_v02_oracle import require_recovery_evidence, RecoveryEvidenceUnavailable


def recovery_matrix(result: dict, configuration: dict) -> dict:
    required = configuration.get("required_recovery_observations")
    if not isinstance(required, list) or not required:
        raise ValueError("D-v02 requires a versioned method/phase matrix")
    identities = [(row["method"], row["label"], row.get("phase", "operation")) for row in required]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate required recovery observation")
    observations = result.get("recovery_evidence", [])
    topologies = result.get("worker_topology_evidence", [])
    matrix = []
    for specification, (method, label, phase) in zip(required, identities):
        readonly = specification.get("readonly_stale_allowed", False)
        if type(readonly) is not bool or readonly and (method, label, phase) != ("complete_request", "before_response", "stale-cleanup"):
            raise ValueError("Read-only recovery exception is limited to stale cleanup before response")
        attempts = [row for row in observations if isinstance(row, dict) and row.get("label") == label
                    and row.get("event", {}).get("metadata", {}).get("method") == method
                    and row.get("phase", "operation") == phase
                    and "request_outcome" in row]
        verified = []
        for row in attempts:
            pid = (row.get("kill") or {}).get("identity", {}).get("host_pid")
            for topology in topologies:
                if not isinstance(topology, dict):
                    continue
                if not any(identity.get("host_pid") == pid for identity in topology.get("identity_generations", [])):
                    continue
                try:
                    proof = require_recovery_evidence(row, topology, method=method, label=label, readonly_stale=readonly)
                except RecoveryEvidenceUnavailable:
                    continue
                verified.append({"host_pid": pid, "supervisor_id": topology.get("supervisor_id"),
                                 "event": proof["event"], "kill": proof["kill"]})
                break
        matrix.append({"method": method, "label": label, "phase": phase, "readonly_stale_allowed": readonly,
                       "recorded_attempts": len(attempts),
                       "verified_interruptions": len(verified), "proofs": verified,
                       "availability": "AVAILABLE" if verified else "UNVERIFIED"})
    return {"version": "orderflow.dv02-recovery-admission/1.0", "matrix": matrix,
            "status": "COMPLETE" if all(row["verified_interruptions"] for row in matrix) else "PARTIAL",
            "source": "Independent method/phase cross-check of raw supervisor PIDFD/FD observations"}


def install_admission():
    import evaluator.runner as harness
    if getattr(harness.evaluate, "_dv02_admission", False):
        return
    original = harness.evaluate

    def evaluate(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("suite_id") != "episode_d_v02":
            return result
        path = Path(__file__).with_name("private_manifests") / "D-V02.json"
        try:
            result["request_recovery_coverage"] = recovery_matrix(result, json.loads(path.read_text()))
        except (OSError, ValueError, TypeError, KeyError) as error:
            result["request_recovery_coverage"] = {"status": "PARTIAL", "error_type": type(error).__name__,
                                                   "error": str(error), "matrix": []}
            result["status"] = "ERROR"
            result["errors"].append("REQUEST_RECOVERY_ADMISSION_ERROR: " + type(error).__name__ + ": " + str(error))
        artifacts = Path(args[1] if len(args) > 1 else kwargs["artifacts"])
        matrix_path = artifacts / "recovery-request-method-phase-matrix.json"
        matrix_path.write_text(json.dumps(result["request_recovery_coverage"], indent=2, sort_keys=True) + "\n")
        result["artifacts"]["request_recovery_matrix"] = str(matrix_path)
        if result["status"] in {"PASS", "FAIL"} and result["request_recovery_coverage"]["status"] != "COMPLETE":
            result["status"] = "ERROR"
            result["errors"].append("RECOVERY_EVIDENCE_UNVERIFIED: required request method/phase matrix incomplete")
        return result

    evaluate._dv02_admission = True
    harness.evaluate = evaluate
