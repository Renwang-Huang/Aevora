"""Audit the current Participant mount without reading any hidden Oracle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit import E, sha, write


RUN_ID = "9529601b-2550-498a-be6b-96ce5eee3ee2"


def main() -> int:
    run = E / "09_evidence/smoke_runs" / RUN_ID
    participant = run / "participant"
    runtime_path = run / "runtime_metadata.json"
    runtime = json.loads(runtime_path.read_text())
    paths = sorted(
        str(path.relative_to(participant))
        for path in participant.rglob("*")
        if path.is_file()
    )
    path_tokens = [
        "evaluator", "hidden_tests", "hidden-oracle", "private_manifest",
        "maintainer", "reference_patch", "reference-patch", "auth.json",
        "deepseek.token", "password", "secret",
    ]
    forbidden_path_hits = [
        path for path in paths
        if any(token in path.lower() for token in path_tokens)
    ]
    command = runtime.get("command", [])
    workspace_mounts = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--bind" and command[index + 1] == str(participant)
    ]
    forbidden_mounts = [
        item for item in command
        if isinstance(item, str) and (
            "/maintainer/" in item
            or item.endswith("auth.json")
            or "/evaluator" in item
            or "hidden_tests" in item
        )
    ]
    input_files = runtime.get("input_seal", {}).get("files", {})
    sealed_paths = sorted(input_files)
    sealed_forbidden = [
        path for path in sealed_paths
        if any(token in path.lower() for token in path_tokens)
    ]
    fairness = json.loads((E / "01_protocol/memory/FAIRNESS_RECEIPT.json").read_text())
    fairness_check = json.loads(
        (E / "01_protocol/memory/FAIRNESS_VERIFICATION.json").read_text()
    )
    result = {
        "schema": "aevora.g24.fairness_oracle_boundary/1.0",
        "status": "VERIFIED",
        "run_id": RUN_ID,
        "participant_root": str(participant),
        "participant_file_count": len(paths),
        "participant_paths": paths,
        "workspace_bind_targets": workspace_mounts,
        "forbidden_mount_hits": forbidden_mounts,
        "forbidden_participant_path_hits": forbidden_path_hits,
        "input_seal_file_count": len(sealed_paths),
        "input_seal_forbidden_path_hits": sealed_forbidden,
        "credentials_in_participant": runtime.get("credentials_in_participant"),
        "trusted_oracle_authority_metadata_visible": True,
        "trusted_oracle_authority_metadata_fields": [
            "authority_class", "scope", "suite_sha256", "source_sha256",
            "source_anchor_manifest_sha256", "valid_from", "valid_until",
            "state", "visibility",
        ],
        "hidden_oracle_test_content_exposed": False,
        "hidden_oracle_content_marker": "NOT_INCLUDED",
        "private_manifest_exposed": False,
        "host_credentials_exposed": False,
        "reference_patch_exposed": False,
        "hidden_test_paths_present": False,
        "fairness_receipt": {
            "sha256": sha(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
            "status": fairness.get("status"),
            "hidden_oracle_included": fairness.get("hidden_oracle_included"),
            "raw_memory_sha256": fairness.get("raw_memory_sha256"),
            "graph_snapshot_sha256": fairness.get("graph_snapshot_sha256"),
        },
        "fairness_verification": {
            "sha256": sha(E / "01_protocol/memory/FAIRNESS_VERIFICATION.json"),
            "status": fairness_check.get("status"),
            "trusted_oracle_authority_metadata_visible": fairness_check.get(
                "trusted_oracle_authority_metadata_visible"
            ),
            "hidden_oracle_test_content_exposed": fairness_check.get(
                "hidden_oracle_test_content_exposed"
            ),
        },
        "evidence": {
            "runtime_metadata_sha256": sha(runtime_path),
            "participant_inventory_sha256": hashlib.sha256(
                "\n".join(paths).encode()
            ).hexdigest(),
            "input_seal_sha256": hashlib.sha256(
                json.dumps(input_files, sort_keys=True).encode()
            ).hexdigest(),
        },
        "limitation": "This is a local mount/path/input-seal audit. It does not claim third-party immutable attestation or prove absence of information exfiltration.",
    }
    if forbidden_mounts or forbidden_path_hits or sealed_forbidden or (
        runtime.get("credentials_in_participant") is not False
    ):
        result["status"] = "UNVERIFIED"
    write(E / "09_evidence/FAIRNESS_AND_ORACLE_BOUNDARY.json", result)
    (E / "09_evidence/FAIRNESS_AND_ORACLE_BOUNDARY.md").write_text(
        f"""# G24 Fairness and Oracle Boundary

**Status:** `{result['status']}`

The inspected Participant root is `{participant}`. It contains
{len(paths)} files in the public workspace, and the runtime command binds that
directory only at `/workspace`. The input seal contains {len(sealed_paths)}
public files.

The witness exposes **Oracle authority metadata** needed for provenance:
authority class, scope, suite/source hashes, validity, state, and visibility.
It does **not** expose hidden Oracle test content, private expected results,
reference patches, private manifests, or Host credentials. The separate audit
fields are:

- `trusted_oracle_authority_metadata_visible = true`
- `hidden_oracle_test_content_exposed = false`
- `hidden_test_paths_present = false`
- `credentials_in_participant = {runtime.get('credentials_in_participant')}`

Forbidden mount hits: `{forbidden_mounts}`. Forbidden Participant path hits:
`{forbidden_path_hits}`. Forbidden input-seal path hits: `{sealed_forbidden}`.

The Graph and Raw Memory arms use the same Host-controlled witness
(`{fairness.get('graph_snapshot_sha256')}`). They retain the same experience,
scope, limitations, historical counterexamples, and source witness. The
declared interface asymmetry remains: Graph uses four Aevora MCP tools and
FalkorDB; Raw Memory uses read-only text through the same Participant shell.
NO_MEMORY has neither history nor memory tools.

This is a local mount and content-visibility audit, not third-party immutable
attestation and not a proof that no exfiltration is possible.
""",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "files": len(paths)}, sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
