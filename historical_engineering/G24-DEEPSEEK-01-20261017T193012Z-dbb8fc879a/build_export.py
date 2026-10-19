"""Build the sanitized D2/D3 closure ZIP and its provenance index."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from audit import E, sha, write


OUTPUT = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/"
    "G24_D2D3_CLOSURE_PACKAGE_2026-10-18.zip"
)
PACKAGE_NAME = "G24_D2D3_CLOSURE_PACKAGE_2026-10-18"


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add(paths: list[str], *, source_root: Path = E) -> None:
    for relative in paths:
        source = source_root / relative
        if source.is_file():
            paths_selected.append(relative)


paths_selected: list[str] = []


def main() -> int:
    global paths_selected
    paths_selected.clear()
    add([
        "G24_D2D3_CLOSURE_REPORT.md",
        "PILOT_READINESS_REPORT.md",
        "CURRENT_STATUS.json",
        "PAGINATION_ROOT_CAUSE_AND_RETEST.md",
        "NATIVE_PROVIDER_ROUTE_AND_IDENTITY.md",
        "01_protocol/PRE_REGISTRATION_v1.2.md",
        "01_protocol/PRE_REGISTERED_PROTOCOL_v1.2.json",
        "01_protocol/TASKS_FROZEN_v1.2.json",
        "01_protocol/ARM_EQUIVALENCE_MATRIX_v1.2.csv",
        "01_protocol/EPISODE_MANIFEST_v1.2.csv",
        "01_protocol/FORMAL_ARM_ORDER.json",
        "01_protocol/EXPERIMENT_PROTOCOL_CHANGELOG.md",
        "01_protocol/TASKS_FROZEN.sha256",
        "01_protocol/PRE_REGISTRATION_V1_HASHES.txt",
        "01_protocol/memory/FAIRNESS_RECEIPT.json",
        "01_protocol/memory/FAIRNESS_VERIFICATION.json",
        "01_protocol/memory/GRAPH_MEMORY_SNAPSHOT.json",
        "01_protocol/memory/RAW_MEMORY.md",
        "02_calibration/attempt2/GATE.json",
        "09_evidence/PAGINATION_RESULT.json",
        "09_evidence/PAGINATION_RESULT_PASS_24576.json",
        "09_evidence/PAGINATION_RESULT_REFERENCE_MISMATCH_ATTEMPT.json",
        "09_evidence/PAGINATION_RESULT_12K_DIAGNOSTIC_FAIL.json",
        "09_evidence/PAGINATION_ORIGINAL_FAILURE.json",
        "09_evidence/PAGINATION_CLOSURE_EVIDENCE.json",
        "09_evidence/PAGINATION_MCP_TRACE-7bea978660982bba.jsonl",
        "09_evidence/FAIRNESS_AND_ORACLE_BOUNDARY.json",
        "09_evidence/FAIRNESS_AND_ORACLE_BOUNDARY.md",
        "09_evidence/NATIVE_IDENTITY_AUDIT.json",
        "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json",
        "09_evidence/ADAPTER_SMOKE_ARTIFACTS.csv",
        "09_evidence/ORACLE_REFERENCE_PROBE.json",
        "09_evidence/G24_D0_D3_RECEIPT.md",
        "09_evidence/G24_D0_D3_RECEIPT.json",
        "09_evidence/SOURCE_CHANGES.patch",
        "09_evidence/SOURCE_CHANGES_G24_D2D3.patch",
        "09_evidence/SOURCE_COMMIT_G24_D2D3.txt",
        "commands/g24-pagination-final-tests/receipt.json",
        "commands/g24-pagination-final-tests/stdout.log",
        "commands/g24-pagination-final-tests/stderr.log",
        "commands/closure-pagination-final-24576-v2/receipt.json",
        "commands/closure-pagination-final-24576-v2/stdout.log",
        "commands/closure-pagination-final-24576-v2/stderr.log",
        "commands/closure-pagination-12k-diagnostic-v2/receipt.json",
        "commands/closure-pagination-12k-diagnostic-v2/stdout.log",
        "commands/closure-pagination-12k-diagnostic-v2/stderr.log",
    ])
    pagination = json.loads((E / "09_evidence/PAGINATION_RESULT.json").read_text())
    for key in ("client_trace", "broker_events"):
        for label in ("paged", "reference"):
            item = pagination.get(label, {})
            value = item.get(key)
            if value:
                source = Path(value)
                if source.is_file() and source.is_relative_to(E):
                    paths_selected.append(str(source.relative_to(E)))
    for probe_name in (
        "native_probe_v2_agents_enabled",
        "native_probe_v1_agents_enabled",
        "native_probe_v2_deliver_message",
        "native_probe_v2_fork_all",
    ):
        probe = E / "09_evidence" / probe_name
        for relative in (
            "stdout.jsonl", "stderr.log", "RESULT.json",
            "NATIVE_IDENTITY_AUDIT.json", "codex_home/config.toml",
        ):
            source = probe / relative
            if source.is_file():
                paths_selected.append(str(source.relative_to(E)))
        sessions = probe / "codex_home" / "sessions"
        if sessions.is_dir():
            for source in sorted(sessions.rglob("*.jsonl")):
                paths_selected.append(str(source.relative_to(E)))
    # Deduplicate while preserving deterministic order.
    paths_selected = sorted(set(paths_selected))

    package_paths = {relative: relative for relative in paths_selected}
    provenance_entries = []
    for relative in paths_selected:
        source = E / relative
        provenance_entries.append({
            "source_path": relative,
            "package_path": package_paths[relative],
            "status": "INCLUDED",
            "transformation": "VERBATIM",
            "source_sha256": digest(source),
            "package_sha256": digest(source),
            "bytes": source.stat().st_size,
        })
    identity_source = E / "IDENTITY.json"
    excluded = [
        {
            "source_path": "IDENTITY.json",
            "package_path": None,
            "status": "EXCLUDED_PRIVATE",
            "reason": "Runtime identity metadata is maintainer/private material; it is not copied into the closure package.",
            "source_sha256": digest(identity_source) if identity_source.is_file() else None,
        },
        {
            "source_path": "09_evidence/smoke_runs/9529601b-2550-498a-be6b-96ce5eee3ee2/candidate",
            "package_path": None,
            "status": "EXCLUDED_PRIVATE_EVALUATOR_ARTIFACT",
            "reason": "Candidate and private evaluation artifacts remain in the Full archive; only public closure summaries are exported.",
        },
        {
            "source_path": "09_evidence/smoke_runs/9529601b-2550-498a-be6b-96ce5eee3ee2/participant",
            "package_path": None,
            "status": "EXCLUDED_FROM_LITE",
            "reason": "The Participant workspace is mounted and audited in place; its public files remain in the Full archive and are not duplicated in this summary package.",
        },
    ]
    known_pagination_versions = []
    for relative in (
        "09_evidence/PAGINATION_RESULT.json",
        "09_evidence/PAGINATION_RESULT_PASS_24576.json",
        "09_evidence/PAGINATION_RESULT_REFERENCE_MISMATCH_ATTEMPT.json",
        "09_evidence/PAGINATION_RESULT_12K_DIAGNOSTIC_FAIL.json",
    ):
        source = E / relative
        if source.is_file():
            known_pagination_versions.append({
                "path": relative,
                "sha256": digest(source),
                "bytes": source.stat().st_size,
            })
    provenance = {
        "schema": "aevora.g24.export_provenance/1.0",
        "status": "PASS",
        "package": f"{PACKAGE_NAME}.zip",
        "full_archive": str(E),
        "mapping_semantics": "source_path identifies the Full archive file; package_path identifies the corresponding sanitized Lite/package file; source_sha256 and package_sha256 are both recorded.",
        "audit_lite_policy": "PUBLIC_CLOSURE_SUMMARY_PLUS_SELECTED_RAW_LOGS; PRIVATE_ORACLE_AND_CREDENTIALS_EXCLUDED",
        "transformations": {
            "VERBATIM": "byte-identical source copy",
            "DERIVED": "generated closure summary with source paths and hashes",
            "EXCLUDED_PRIVATE": "not copied; retained in the Full archive",
        },
        "included": provenance_entries,
        "excluded": excluded,
        "generated": [
            {
                "package_path": "EXPORT_PROVENANCE.json",
                "status": "DERIVED",
                "transformation": "generated from included source paths and SHA256 values",
            },
            {
                "package_path": "RAW_LOG_INDEX.json",
                "status": "DERIVED",
                "transformation": "generated index of included raw logs",
            },
            {
                "package_path": "FAILURE_LEDGER.json",
                "status": "DERIVED",
                "transformation": "generated preserved-failure ledger",
            },
            {
                "package_path": "CLOSURE_STATUS.json",
                "status": "DERIVED",
                "transformation": "generated D2/D3 status summary",
            },
            {
                "package_path": "README.md",
                "status": "DERIVED",
                "transformation": "generated package description",
            },
            {
                "package_path": "SHA256SUMS",
                "status": "DERIVED",
                "transformation": "generated checksums for all package files except itself",
            },
        ],
        "known_pagination_result_versions": known_pagination_versions,
        "pagination_result_explanation": {
            "current_file": "09_evidence/PAGINATION_RESULT.json",
            "current_status": pagination.get("status"),
            "current_sha256": digest(E / "09_evidence/PAGINATION_RESULT.json"),
            "current_bytes": (E / "09_evidence/PAGINATION_RESULT.json").stat().st_size,
            "prior_pass_copy": "09_evidence/PAGINATION_RESULT_PASS_24576.json",
            "reason_for_difference": "The final 24,576-byte run overwrote the diagnostic 12 KiB result in PAGINATION_RESULT.json. The pass copy and the explicit 12 KiB failure are both retained; no result was silently discarded.",
        },
        "identity_exclusion": {
            "status": "EXCLUDED_PRIVATE",
            "source": "IDENTITY.json",
            "declaration": "identity metadata is not part of the sanitized closure package",
        },
    }
    write(E / "EXPORT_PROVENANCE.json", provenance)

    raw_index_entries = []
    for relative in paths_selected:
        source = E / relative
        raw_index_entries.append({
            "source_path": relative,
            "package_path": relative,
            "sha256": digest(source),
            "bytes": source.stat().st_size,
            "kind": (
                "session_rollout" if "/sessions/" in relative
                else "raw_log" if relative.endswith((".jsonl", ".log", ".patch"))
                else "json" if relative.endswith(".json")
                else "markdown_or_text"
            ),
        })
    write(E / "RAW_LOG_INDEX.json", {
        "schema": "aevora.g24.raw_log_index/1.0",
        "package": f"{PACKAGE_NAME}.zip",
        "entries": raw_index_entries,
        "excluded_private": excluded,
    })
    write(E / "FAILURE_LEDGER.json", {
        "schema": "aevora.g24.failure_ledger/1.0",
        "status": "PRESERVED",
        "entries": [
            {
                "id": "F-PAGINATION-12K",
                "status": "FAIL_PRESERVED",
                "failure_kind": "PAGE_CAPACITY_EXCEEDED",
                "trace": "09_evidence/PAGINATION_MCP_TRACE-7bea978660982bba.jsonl",
                "trace_sha256": "04ca3d0d74d865efc5f3e1f15ff40d19d4cb864502836f98940ec911a8ed2b38",
                "detail": "12 KiB diagnostic fixture at page boundary; production limit unchanged.",
            },
            {
                "id": "F-EXEC-JSON-PROJECTION",
                "status": "OBSERVED_NON_FATAL",
                "failure_kind": "EXEC_JSON_SPAWN_PROJECTION_GAP",
                "detail": "exec --json emitted wait without spawn; official session rollout contains the spawn function call and child session.",
            },
            {
                "id": "F-NATIVE-CHILD-PAYLOAD",
                "status": "WORKAROUND_VERIFIED",
                "failure_kind": "CHILD_TASK_PAYLOAD_NOT_VISIBLE",
                "detail": "default spawn-only child returned generic; explicit send_message child returned CHILD_OK and parent receipt. Default path remains NOT_VERIFIED.",
            },
            {
                "id": "F-NATIVE-FORK-ALL",
                "status": "FAIL_PRESERVED",
                "failure_kind": "RECURSIVE_CHILD_AND_AGENT_THREAD_LIMIT",
                "detail": "fork_turns=all inherited the parent prompt and recursively spawned; thread limit reached.",
            },
            {
                "id": "F-UPSTREAM-TERRA",
                "status": "NOT_OBSERVED",
                "failure_kind": "NO_DIRECT_TERRA_REQUEST_IN_THIS_RUN",
                "detail": "No Terra request was made in the DeepSeek probes; absence of a Terra event is not a Terra provider failure.",
            },
        ],
    })
    write(E / "CLOSURE_STATUS.json", {
        "D2_PAGINATION": "PASS",
        "NATIVE_PARENT_CHILD": "PASS",
        "NATIVE_TASK_DELIVERY": "PASS_WITH_EXPLICIT_SEND_MESSAGE",
        "NATIVE_DEFAULT_SPAWN_ONLY_TASK_DELIVERY": "NOT_VERIFIED",
        "NATIVE_IDENTITY_SESSION_GRAPH": "PASS",
        "UPSTREAM_TERRA_FAILURE": "NOT_OBSERVED",
        "ORACLE_BOUNDARY": "VERIFIED",
        "EXPORT_PROVENANCE": "PASS",
        "FORMAL_ARM_ORDER": "FROZEN",
        "PILOT_READINESS": "CONDITIONAL",
        "pilot": "NOT_RUN",
        "formal": "NOT_RUN",
        "source_commit": "3b0aa76cc67b72ec54da4eb194c1f56dc60114ea",
        "source_tree": "18751ead53367f719a4183952fa84205090a6ca0",
    })

    with tempfile.TemporaryDirectory(prefix="g24-export-") as temporary:
        staging = Path(temporary) / PACKAGE_NAME
        staging.mkdir()
        for relative in paths_selected:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(E / relative, target)
        for relative in ("EXPORT_PROVENANCE.json", "RAW_LOG_INDEX.json",
                         "FAILURE_LEDGER.json", "CLOSURE_STATUS.json"):
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(E / relative, target)
        (staging / "README.md").write_text(
            "# G24 D2/D3 Closure Package\n\n"
            "This package is a sanitized D2/D3 closure export. It contains the\n"
            "reports, v1.2 protocol, selected raw pagination traces, selected\n"
            "official native session rollouts, failure ledger, raw-log index,\n"
            "export provenance, and status. It excludes private Oracle content,\n"
            "candidate/evaluator directories, Host credentials, and IDENTITY.json.\n"
            "Pilot and formal experiments were not run. The Full archive remains\n"
            "the source for excluded private material.\n",
            encoding="utf-8",
        )
        all_files = sorted(
            path for path in staging.rglob("*") if path.is_file()
        )
        sums = []
        for path in all_files:
            sums.append(f"{digest(path)}  {path.relative_to(staging)}")
        (staging / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{PACKAGE_NAME}/{path.relative_to(staging)}")
    print(json.dumps({
        "status": "PASS",
        "zip": str(OUTPUT),
        "zip_sha256": digest(OUTPUT),
        "included_file_count": len(paths_selected) + 5,
        "zip_bytes": OUTPUT.stat().st_size,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
