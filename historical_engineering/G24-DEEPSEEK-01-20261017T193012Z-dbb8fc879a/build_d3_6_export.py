"""Build the D3.6 runtime-boundary and Pilot-admission review package."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from audit import E, sha, write


PACKAGE_NAME = "G24_D3_6_NATIVE_BOUNDARY_AND_SINGLE_AGENT_PILOT_PACKAGE_2026-10-18"
OUTPUT = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/"
    f"{PACKAGE_NAME}.zip"
)
NATIVE_RUN = E / "09_evidence/smoke_runs/890b8b07-7cbd-4a75-ad66-cfe9b47fec4b"
SINGLE_RUN = E / "09_evidence/smoke_runs/9529601b-2550-498a-be6b-96ce5eee3ee2"
ORACLE_RUN = (
    E
    / "09_evidence/native_oracle_diagnostic/runs/"
    "ff5ca3f3-317b-4eec-ab7d-fc492ad5230e"
)


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    selected: list[tuple[Path, str]] = []

    def add(source: Path, package_path: str | None = None):
        if source.is_file():
            selected.append((source, package_path or str(source.relative_to(E))))

    for relative in (
        "G24_D3_6_RUNTIME_BOUNDARY_REPORT.md",
        "PILOT_P01_P02_ADMISSION_REPORT_v1.3.md",
        "G24_D3_5_NATIVE_ADAPTER_REPORT.md",
        "PILOT_P01_P02_ADMISSION_REPORT.md",
        "09_evidence/G24_D3_6_GATE.json",
        "09_evidence/G24_D3_5_GATE.json",
        "09_evidence/NATIVE_DEPTH_ENFORCEMENT_AUDIT.json",
        "09_evidence/NATIVE_ADAPTER_SMOKE_RECEIPT.json",
        "09_evidence/native_oracle_diagnostic/NATIVE_ORACLE_DIAGNOSTIC.json",
        "09_evidence/CLI_EXEC_HELP_0.163.0.txt",
        "09_evidence/CLI_FEATURES_0.163.0.txt",
        "09_evidence/CLI_FEATURES_0.163.0.stderr.txt",
        "09_evidence/SOURCE_CHANGES_D3_5.patch",
        "09_evidence/SOURCE_COMMIT_D3_5.txt",
        "09_evidence/PAGINATION_RESULT.json",
        "09_evidence/PAGINATION_CLOSURE_EVIDENCE.json",
        "09_evidence/ORACLE_REFERENCE_PROBE.json",
        "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json",
        "01_protocol/PRE_REGISTERED_PROTOCOL_v1.3.json",
        "01_protocol/PRE_REGISTRATION_v1.3.md",
        "01_protocol/TASKS_FROZEN_v1.3.json",
        "01_protocol/EPISODE_MANIFEST_v1.3.csv",
        "01_protocol/FORMAL_ARM_ORDER_v1.3.json",
        "01_protocol/EXPERIMENT_PROTOCOL_CHANGELOG_v1.3.md",
        "01_protocol/PRE_REGISTERED_PROTOCOL_v1.2.json",
        "01_protocol/TASKS_FROZEN_v1.2.json",
        "01_protocol/FORMAL_ARM_ORDER.json",
        "01_protocol/memory/FAIRNESS_RECEIPT.json",
        "01_protocol/memory/FAIRNESS_VERIFICATION.json",
        "commands/g24-native-adapter-full-smoke-v1b/receipt.json",
        "commands/g24-native-adapter-full-smoke-v1b/stdout.log",
        "commands/g24-native-adapter-full-smoke-v1b/stderr.log",
        "commands/native-oracle-diagnostic/receipt.json",
        "commands/native-oracle-diagnostic/stdout.log",
        "commands/native-oracle-diagnostic/stderr.log",
        "commands/g24-native-adapter-tests-v4/receipt.json",
        "commands/g24-native-adapter-tests-v4/stdout.log",
        "commands/g24-native-adapter-tests-v4/stderr.log",
    ):
        add(E / relative)

    for relative in (
        "runtime_metadata.json",
        "evaluation_report.json",
        "native_rollout_summary.json",
        "submission.diff",
        "submission_metadata.json",
        "public_test_changes.diff",
        "codex_events.jsonl",
        "codex_stderr.log",
        "aevora_mcp_events.jsonl",
        "gateway_transport_events.jsonl",
        "participant/AGENTS.md",
        "participant/CHILD_TASK.md",
        "participant/ISSUE.md",
        "participant/TASK.md",
        "participant/public.json",
    ):
        add(NATIVE_RUN / relative, f"native_d3_5/{relative}")
    for source in sorted((NATIVE_RUN / "artifacts/native_rollouts").rglob("*.jsonl")):
        add(source, "native_d3_5/rollouts/" + source.name)

    for relative in (
        "runtime_metadata.json",
        "evaluation_report.json",
        "submission.diff",
        "submission_metadata.json",
        "public_test_changes.diff",
        "codex_events.jsonl",
        "aevora_mcp_events.jsonl",
        "gateway_transport_events.jsonl",
        "participant/AGENTS.md",
        "participant/ISSUE.md",
        "participant/TASK.md",
        "participant/public.json",
    ):
        add(SINGLE_RUN / relative, f"single_agent/{relative}")
    for source in sorted((SINGLE_RUN / "artifacts/native_rollouts").rglob("*.jsonl")):
        add(source, "single_agent/rollouts/" + source.name)
    add(SINGLE_RUN / "artifacts/junit.xml",
        "private_evidence/SINGLE_AGENT_ORACLE_JUNIT.xml")

    for relative in (
        "evaluation_report.json",
        "patch.diff",
        "artifacts/junit.xml",
        "artifacts/pytest.stdout.log",
        "artifacts/pytest.stderr.log",
    ):
        package_path = (
            "private_evidence/NATIVE_ORACLE_JUNIT.xml"
            if relative == "artifacts/junit.xml"
            else "oracle_diagnostic/" + relative
        )
        add(ORACLE_RUN / relative, package_path)

    private_notice = E / "09_evidence/PRIVATE_DO_NOT_PUBLISH_D3_6.txt"
    private_notice.write_text(
        "INTERNAL MAINTAINER REVIEW ONLY\n"
        "The private_evidence JUnit files contain hidden Oracle test identities "
        "and failure diagnostics. Do not mount or show them to any Participant.\n",
        encoding="utf-8",
    )
    add(private_notice, "PRIVATE_DO_NOT_PUBLISH.txt")

    write(E / "D3_6_FAILURE_LEDGER.json", {
        "schema": "aevora.g24.d3_6.failure_ledger/1.0",
        "status": "PRESERVED",
        "entries": [
            {
                "id": "F-D3_6-NATIVE-DEPTH",
                "status": "NATIVE_DEPTH_ENFORCEMENT_UNAVAILABLE",
                "run_id": NATIVE_RUN.name,
                "failure_kind": "DELEGATION_BOUNDARY_VIOLATION",
                "observed": "max_child_agents=1 but one direct child created a depth-2 child",
            },
            {
                "id": "F-D3_6-CHILD-WRITE-ROLE",
                "status": "CHILD_READ_ONLY_ENFORCEMENT_UNAVAILABLE",
                "run_id": NATIVE_RUN.name,
                "observed": "child sessions share the writable /workspace; nested child performed FileChange operations",
            },
            {
                "id": "F-D3_6-ORACLE",
                "status": "FAIL_RECORDED",
                "source": "post-run independent Oracle diagnostic",
                "passed": 0,
                "collected": 8,
            },
        ],
    })
    write(E / "D3_6_EXPORT_PROVENANCE.json", {
        "schema": "aevora.g24.d3_6.export_provenance/1.0",
        "status": "PASS",
        "package": f"{PACKAGE_NAME}.zip",
        "mapping_semantics": "source_path is the Full archive file; package_path is its review-package location; source/package SHA256 are recorded.",
        "included": [
            {
                "source_path": str(source.relative_to(E)),
                "package_path": package_path,
                "status": "INCLUDED_VERBATIM",
                "source_sha256": digest(source),
                "package_sha256": digest(source),
                "bytes": source.stat().st_size,
            }
            for source, package_path in selected
        ],
        "excluded": [
            {"source_path": "IDENTITY.json", "status": "EXCLUDED_PRIVATE"},
            {"source_path": str(NATIVE_RUN / "candidate"), "status": "EXCLUDED_FROM_LITE", "reason": "submitted patch and SHA are included instead"},
            {"source_path": str(NATIVE_RUN / "codex-state"), "status": "EXCLUDED_MUTABLE_STATE", "reason": "official rollouts are included instead"},
        ],
        "private_material": [
            {"package_path": "private_evidence/NATIVE_ORACLE_JUNIT.xml",
             "classification": "INTERNAL_MAINTAINER_ONLY"},
            {"package_path": "private_evidence/SINGLE_AGENT_ORACLE_JUNIT.xml",
             "classification": "INTERNAL_MAINTAINER_ONLY"},
        ],
    })
    write(E / "D3_6_RAW_LOG_INDEX.json", {
        "schema": "aevora.g24.d3_6.raw_log_index/1.0",
        "status": "PASS",
        "entries": [
            {"package_path": package_path, "sha256": digest(source),
             "bytes": source.stat().st_size}
            for source, package_path in selected
        ],
    })

    with tempfile.TemporaryDirectory(prefix="g24-d3-6-export-") as temporary:
        staging = Path(temporary) / PACKAGE_NAME
        staging.mkdir()
        for source, package_path in selected:
            target = staging / package_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in (
            "D3_6_FAILURE_LEDGER.json",
            "D3_6_EXPORT_PROVENANCE.json",
            "D3_6_RAW_LOG_INDEX.json",
        ):
            shutil.copy2(E / relative, staging / relative)
        (staging / "README.md").write_text(
            "# G24-D3.6 Native Boundary and Single-Agent Pilot Package\n\n"
            "This package contains the enforced-boundary audit, D3.5 native "
            "failure evidence, the append-only v1.3 Single-Agent Pilot "
            "candidate, Gate receipts, source diff, raw session rollouts, "
            "MCP traces, patches, and independent Oracle evidence.\n\n"
            "Native depth and child write-permission enforcement are not "
            "available in the inspected Codex runtime and are not claimed. "
            "The v1.3 profile is an adapted Single-Agent runtime, not a "
            "Native Multi-Agent result.\n\n"
            "The private_evidence JUnit files are internal maintainer-only "
            "and must not be mounted or shown to a Participant.\n",
            encoding="utf-8",
        )
        files = sorted(path for path in staging.rglob("*") if path.is_file())
        (staging / "SHA256SUMS").write_text(
            "\n".join(f"{digest(path)}  {path.relative_to(staging)}" for path in files)
            + "\n",
            encoding="utf-8",
        )
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{PACKAGE_NAME}/{path.relative_to(staging)}")
    print(json.dumps({
        "status": "PASS",
        "zip": str(OUTPUT),
        "zip_sha256": digest(OUTPUT),
        "zip_bytes": OUTPUT.stat().st_size,
        "files": len(selected) + 4,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
