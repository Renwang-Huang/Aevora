"""Package the D3.5 native adapter review evidence with explicit provenance."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from audit import E, sha, write


PACKAGE_NAME = "G24_D3_5_NATIVE_ADAPTER_PACKAGE_2026-10-18"
OUTPUT = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/"
    f"{PACKAGE_NAME}.zip"
)
RUN = E / "09_evidence/smoke_runs/890b8b07-7cbd-4a75-ad66-cfe9b47fec4b"
ORACLE_RUN = (
    E
    / "09_evidence/native_oracle_diagnostic/runs/"
    "ff5ca3f3-317b-4eec-ab7d-fc492ad5230e"
)


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry(source: Path, package_path: str) -> dict:
    return {
        "source_path": str(source.relative_to(E)),
        "package_path": package_path,
        "status": "INCLUDED_VERBATIM",
        "source_sha256": digest(source),
        "package_sha256": digest(source),
        "bytes": source.stat().st_size,
    }


def main() -> int:
    selected: list[tuple[Path, str]] = []

    def add(source: Path, package_path: str | None = None):
        if source.is_file():
            selected.append((source, package_path or str(source.relative_to(E))))

    for relative in (
        "G24_D3_5_NATIVE_ADAPTER_REPORT.md",
        "PILOT_P01_P02_ADMISSION_REPORT.md",
        "09_evidence/G24_D3_5_GATE.json",
        "09_evidence/NATIVE_ADAPTER_SMOKE_RECEIPT.json",
        "09_evidence/SOURCE_CHANGES_D3_5.patch",
        "09_evidence/SOURCE_COMMIT_D3_5.txt",
        "09_evidence/native_oracle_diagnostic/NATIVE_ORACLE_DIAGNOSTIC.json",
        "01_protocol/PRE_REGISTERED_PROTOCOL_v1.2.json",
        "01_protocol/TASKS_FROZEN_v1.2.json",
        "01_protocol/EPISODE_MANIFEST_v1.2.csv",
        "01_protocol/FORMAL_ARM_ORDER.json",
        "01_protocol/memory/FAIRNESS_RECEIPT.json",
        "01_protocol/memory/FAIRNESS_VERIFICATION.json",
        "commands/g24-native-adapter-full-smoke-v1b/receipt.json",
        "commands/g24-native-adapter-full-smoke-v1b/stdout.log",
        "commands/g24-native-adapter-full-smoke-v1b/stderr.log",
        "commands/native-oracle-diagnostic/receipt.json",
        "commands/native-oracle-diagnostic/stdout.log",
        "commands/native-oracle-diagnostic/stderr.log",
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
        add(RUN / relative, f"native_run/{relative}")
    for source in sorted((RUN / "artifacts/native_rollouts").rglob("*.jsonl")):
        add(source, "native_run/rollouts/" + source.name)

    for relative in (
        "evaluation_report.json",
        "patch.diff",
        "artifacts/junit.xml",
        "artifacts/pytest.stdout.log",
        "artifacts/pytest.stderr.log",
    ):
        package_path = (
            "private_evidence/ORACLE_JUNIT.xml"
            if relative == "artifacts/junit.xml"
            else "oracle_diagnostic/" + relative
        )
        add(ORACLE_RUN / relative, package_path)

    # This is intentionally private maintainer evidence, not Participant input.
    (E / "09_evidence/PRIVATE_DO_NOT_PUBLISH_D3_5.txt").write_text(
        "INTERNAL MAINTAINER REVIEW ONLY\n"
        "private_evidence/ORACLE_JUNIT.xml contains hidden Oracle test identities "
        "and failure diagnostics. It is included for the authorized reviewer's "
        "traceability only and must not be mounted or shown to a Participant.\n",
        encoding="utf-8",
    )
    add(E / "09_evidence/PRIVATE_DO_NOT_PUBLISH_D3_5.txt",
        "PRIVATE_DO_NOT_PUBLISH.txt")

    provenance_entries = [entry(source, package_path) for source, package_path in selected]
    write(E / "D3_5_EXPORT_PROVENANCE.json", {
        "schema": "aevora.g24.d3_5.export_provenance/1.0",
        "status": "PASS",
        "package": f"{PACKAGE_NAME}.zip",
        "full_archive": str(E),
        "mapping_semantics": "source_path is the Full archive file; package_path is its review-package location; both hashes are recorded.",
        "included": provenance_entries,
        "excluded": [
            {
                "source_path": "IDENTITY.json",
                "status": "EXCLUDED_PRIVATE",
                "reason": "Runtime identity metadata is not copied; it is not needed for adapter review.",
            },
            {
                "source_path": "09_evidence/smoke_runs/890b8b07-7cbd-4a75-ad66-cfe9b47fec4b/candidate",
                "status": "EXCLUDED_FROM_LITE",
                "reason": "The candidate directory remains in the Full archive; the submitted patch and its hashes are exported instead.",
            },
            {
                "source_path": "09_evidence/smoke_runs/890b8b07-7cbd-4a75-ad66-cfe9b47fec4b/codex-state",
                "status": "EXCLUDED_MUTABLE_STATE",
                "reason": "Official session rollouts are exported; mutable Codex state and SQLite state are not.",
            },
        ],
        "private_material": [
            {
                "package_path": "private_evidence/ORACLE_JUNIT.xml",
                "classification": "INTERNAL_MAINTAINER_ONLY_DO_NOT_MOUNT_OR_SHARE",
            }
        ],
    })

    write(E / "D3_5_RAW_LOG_INDEX.json", {
        "schema": "aevora.g24.d3_5.raw_log_index/1.0",
        "entries": [
            {
                "package_path": package_path,
                "sha256": digest(source),
                "bytes": source.stat().st_size,
            }
            for source, package_path in selected
        ],
    })
    write(E / "D3_5_FAILURE_LEDGER.json", {
        "schema": "aevora.g24.d3_5.failure_ledger/1.0",
        "status": "PRESERVED",
        "entries": [
            {
                "id": "F-D3_5-DELEGATION-BOUNDARY",
                "status": "FAIL_PRESERVED",
                "run_id": RUN.name,
                "failure_kind": "DELEGATION_BOUNDARY_VIOLATION",
                "observed": "direct child created a depth-2 descendant",
            },
            {
                "id": "F-D3_5-PRIOR-NESTED-ATTEMPTS",
                "status": "FAIL_PRESERVED",
                "run_ids": [
                    "3ae24bb8-0e0b-4b93-9f8a-e055b4cfa8bb",
                    "0da8edcd-55d2-46a8-b826-693e164c6c6d",
                    "1f6c3100-7045-473c-ad48-9feeeea36db0",
                ],
                "failure_kind": "RECURSIVE_CHILD_OR_THREAD_LIMIT",
            },
            {
                "id": "F-D3_5-ORACLE",
                "status": "FAIL_RECORDED",
                "source": "independent post-run Oracle diagnostic",
                "passed": 0,
                "collected": 8,
            },
        ],
    })

    with tempfile.TemporaryDirectory(prefix="g24-d3-5-export-") as temporary:
        staging = Path(temporary) / PACKAGE_NAME
        staging.mkdir()
        for source, package_path in selected:
            target = staging / package_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in (
            "D3_5_EXPORT_PROVENANCE.json",
            "D3_5_RAW_LOG_INDEX.json",
            "D3_5_FAILURE_LEDGER.json",
        ):
            target = staging / relative
            shutil.copy2(E / relative, target)
        (staging / "README.md").write_text(
            "# G24-D3.5 Native Adapter Review Package\n\n"
            "This package preserves the actual native adapter run, parent/child "
            "rollouts, MCP event trace, patch, public-test evidence, independent "
            "Oracle diagnostic, failure ledger, source commits, and hashes.\n\n"
            "The run is CONDITIONAL, not PASS: the native child created a "
            "depth-2 descendant and the adapter correctly failed closed. The "
            "independent Oracle result is FAIL 0/8 and is not replaced by a "
            "reference patch.\n\n"
            "`private_evidence/ORACLE_JUNIT.xml` is internal maintainer-only "
            "evidence and must not be mounted or shown to a Participant.\n",
            encoding="utf-8",
        )
        checksum_files = sorted(path for path in staging.rglob("*") if path.is_file())
        (staging / "SHA256SUMS").write_text(
            "\n".join(
                f"{digest(path)}  {path.relative_to(staging)}"
                for path in checksum_files
            ) + "\n",
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
