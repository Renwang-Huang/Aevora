#!/usr/bin/env python3
"""Aevora H2 maintainer Audit-Lite selection over the existing sealed exporter.

No model/database operations, secret discovery, source writes or new grades.
The old CAS, redaction, complete-line provenance and independent stdlib verifier
remain authoritative. Only selection is extended inside a disposable process.
Read-only observation sessions are supporting evidence, never scored Runs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark import evidence_export as legacy
from benchmark import evidence_verify

VERSION = "aevora.h2-audit-lite/1.0.1"
MAX_SUPPORT_BYTES = 2 * 1024**2
MAX_JUNIT_BYTES = 8 * 1024**2
MAX_WORKER_REPLY = 4 * 1024**2
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
FORBIDDEN_PARTS = frozenset({"hidden_tests", "reference_patches", "private_manifests",
    "frozen_private_manifests", "private_labels", "participant", "workspace", "candidate",
    "pytest-tmp", "codex-state", ".git", "__pycache__", ".venv", "node_modules"})
SECRET_NAME = re.compile(r"(?:^|[._-])(?:auth|password|passwd|credentials?|secrets?|api[_-]?key)(?:[._-]|$)", re.I)
RAW_GRAPH_NAMES = frozenset({"trusted_graph_commands.jsonl", "GRAPH_BEFORE.json", "GRAPH_AFTER.json",
    "CORPUS_MANIFEST.json", "HISTORICAL_VERIFICATION.json", "graph_snapshot.json"})
SUPPORT_TOKENS = ("GATE", "REPORT", "SUMMARY", "RESULT", "REVIEW", "EPOCH", "MANIFEST",
    "FINGERPRINT", "ADMISSION", "FREEZE", "VERIFICATION", "INTEGRITY", "PROTOCOL", "ATTEMPT",
    "RECOVERY", "SECURITY", "CHECKPOINT", "RESTORE", "AOF_REPLAY", "SAVE_BOUNDARY", "READBACK",
    "OBSERVATION", "VERDICT", "SOURCE_AFTER", "SOURCE_BEFORE", "CONTEXT", "RESOLVER", "COMPARISON",
    "QUERY", "DECISION", "TRUSTED_INGEST", "OUTCOME")
NATIVE_TOP_FILES = legacy._RUN_TOP_FILES | {"aevora_mcp_events.jsonl", "observation_report.json"}


class H2ExportError(ValueError):
    """Actual input/selection/verification failed; no fallback or grade rewrite."""


def require(condition, message):
    if not condition:
        raise H2ExportError(message)


def ordinary_path(value):
    path = Path(value).absolute()
    require(not any(part.is_symlink() for part in (path, *path.parents)), "Linked path components refused")
    return path


def _allowed(path):
    evidence_verify.safe_relative(path)
    parts = PurePosixPath(path).parts
    return not (any(part in FORBIDDEN_PARTS for part in parts) or
                any(SECRET_NAME.search(part) for part in parts) or
                any(part.endswith((".db", ".sqlite", ".sqlite3", ".rdb", ".aof", ".zip")) for part in parts))


def _inside_snapshot(path):
    return any(part in {"source_snapshot", "frozen_source_snapshot", "source", "frozen", "clone"}
               for part in PurePosixPath(path).parts)


def _public_core_source(path):
    parts = PurePosixPath(path).parts
    if "aevora_core" not in parts:
        return False
    local = parts[parts.index("aevora_core") + 1:]
    return (local[:2] == ("src", "aevora") and len(local) == 3 and local[-1].endswith(".py")) or (
        local and (local[0] == "docs" or local == ("README.md",)) and local[-1].endswith((".md", ".cypher")))


def _run_assets(indexed, prefix):
    """Complete actual Session raw evidence, excluding full execution topology."""
    result = set()
    for source in indexed:
        if not source.startswith(prefix + "/") or not _allowed(source):
            continue
        local = source[len(prefix) + 1:]
        parts = PurePosixPath(local).parts
        if len(parts) == 1 and local in NATIVE_TOP_FILES:
            result.add(source)
        elif parts[:2] == ("artifacts", "native_rollouts") and source.endswith(".jsonl"):
            result.add(source)
        elif parts[0] == "sealed_public_inputs":
            result.add(source)
        elif len(parts) == 2 and parts[0] == "artifacts" and source.endswith((".json", ".xml", ".log")):
            # Independent Oracle bytes must remain complete: the legacy verifier
            # compares them with embedded report facts. Large topology belongs
            # to Full, with its unchanged source-SHA pointer in NOT_INCLUDED.
            if not parts[-1].lower().startswith(("topology-", "concurrency-", "pool-resource-")):
                result.add(source)
    return result


def observation_roots(root, indexed, run_ids):
    result = {}
    for identifier in run_ids:
        matches = [str(PurePosixPath(path).parent) for path in indexed
                   if path.endswith("/observation_report.json") and PurePosixPath(path).parent.name == identifier]
        require(len(matches) == 1, "Observation Session is absent or ambiguous")
        prefix = matches[0]
        require(prefix + "/run_evidence_manifest.json" in indexed,
                "Observation Session needs its actual stopped Run seal")
        require(not (root / prefix / "codex-state").exists(), "Observation Session still has native state")
        seal = evidence_verify.load_json(legacy._read_regular(root, prefix + "/run_evidence_manifest.json"))
        require(isinstance(seal, dict) and seal.get("run_id") == identifier and isinstance(seal.get("files"), dict)
                and all(indexed.get(prefix + "/" + evidence_verify.safe_relative(path)) == digest
                        for path, digest in seal["files"].items()), "Observation Run seal differs from Full index")
        report = evidence_verify.load_json(legacy._read_regular(root, prefix + "/observation_report.json"))
        require(isinstance(report, dict) and report.get("run_id") == identifier
                and report.get("kind") == "NEW_SESSION_READ_ONLY_EVIDENCE_OBSERVATION"
                and report.get("evaluation_result") == "NOT_EXECUTED",
                "Observation must preserve its genuine read-only classification")
        prepared_path = prefix + "/evaluation_report.json"
        if prepared_path in indexed:
            # Runner.prepare keeps its unexecuted lifecycle under the standard
            # report filename. Presence is not an evaluation, and it is never
            # selected as a scored report. Accept only the actual sealed empty
            # preparation plus matching stopped NO_PATCH observation evidence.
            raw = legacy._read_regular(root, prepared_path)
            require(sha256(raw).hexdigest() == indexed[prepared_path]
                    and seal["files"].get("evaluation_report.json") == indexed[prepared_path],
                    "Observation preparation differs from its actual Run/Full seals")
            prepared = evidence_verify.load_json(raw)
            runtime_path = prefix + "/runtime_metadata.json"
            require(runtime_path in indexed, "Prepared observation needs actual runtime metadata")
            raw_runtime = legacy._read_regular(root, runtime_path)
            require(sha256(raw_runtime).hexdigest() == indexed[runtime_path],
                    "Observation runtime differs from the Full seal")
            runtime = evidence_verify.load_json(raw_runtime)
            empty_fields = ("test_results", "pytest_exit_code", "submission", "runtime_result",
                "evaluation_result", "evaluation_started_at", "evaluation_ended_at", "ended_at")
            require(isinstance(prepared, dict) and prepared.get("run_id") == identifier
                    and prepared.get("overall_status") == "PREPARED"
                    and prepared.get("lifecycle") == ["LOAD", "PREPARE"]
                    and all(prepared.get(field) is None for field in empty_fields)
                    and not prepared.get("database_oracle") and not prepared.get("execution_errors"),
                    "Observation cannot replace or disguise an executed/scored Run")
            require(isinstance(runtime, dict) and runtime.get("run_id") == identifier
                    and runtime.get("runtime_result") == "ERROR" and runtime.get("failure_kind") == "NO_PATCH"
                    and type(runtime.get("exit_code")) is int and runtime["exit_code"] == 0
                    and runtime.get("fresh_session") is True
                    and all(report.get(field) is True for field in
                            ("source_unchanged", "public_inputs_unchanged", "native_turn_complete")),
                    "Prepared observation lacks stopped, unchanged native NO_PATCH evidence")
        result[identifier] = prefix
    return result


def _support_size(root, source):
    """Inspect through descriptors; a linked/special file is an error, not omitted."""
    evidence_verify.safe_relative(source)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = source.split("/")
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        item = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(item)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Supporting source must be an ordinary single-link file")
            return info.st_size
        finally:
            os.close(item)
    finally:
        os.close(fd)


def h2_selection(root, indexed, roots, observations, explicit_paths):
    selected = set()
    for prefix in (*roots.values(), *observations.values()):
        selected.update(_run_assets(indexed, prefix))
    prepared_observation_reports = {prefix + "/evaluation_report.json" for prefix in observations.values()}
    selected.difference_update(prepared_observation_reports)
    selected.update(name for name in legacy._ARCHIVE_SUMMARIES if name in indexed and _allowed(name))
    required = set(explicit_paths)
    for source in explicit_paths:
        require(source not in prepared_observation_reports,
                "Unexecuted observation preparation stays a Full pointer, never a scored selection")
        require(source in indexed and _allowed(source), "Explicit supporting evidence is absent or private")
        require((PurePosixPath(source).name not in RAW_GRAPH_NAMES and not source.lower().endswith(".jsonl"))
                or PurePosixPath(source).name.upper() == "ATTEMPTS.JSONL",
                "Use Full pointers for raw topology/Cypher; Session JSONL selection is automatic")
        require(not source.endswith((".py", ".diff", ".sql")) or _public_core_source(source),
                "Explicit source inclusion is limited to Aevora core; private repair material is forbidden")
        selected.add(source)
    for source in indexed:
        if not _allowed(source):
            continue
        # Manual repeat Runs retain bounded original JUnit and method/window
        # coverage as supporting evidence. Their UUID paths join ATTEMPTS;
        # only explicitly selected Challenge reports enter scored RUN_INDEX.
        if any(UUID.fullmatch(part) for part in PurePosixPath(source).parts):
            if source.endswith(("/artifacts/junit.xml", "/artifacts/recovery-request-method-phase-matrix.json")):
                selected.add(source)
            continue
        name = PurePosixPath(source).name
        upper = name.upper()
        if name in RAW_GRAPH_NAMES or name.lower().startswith(("topology-", "concurrency-", "pool-resource-")):
            continue
        if _inside_snapshot(source):
            # Do not expose fixture builders that embed private repair variants,
            # Oracle/test implementations, or unrelated historic maintainer code.
            if _public_core_source(source) or ("docs" in PurePosixPath(source).parts and name.endswith(".md")):
                selected.add(source)
            continue
        command = bool(re.fullmatch(r"command(?:-\d+)?\.json", name))
        junit = name.lower().endswith(("junit.xml", ".junit.xml"))
        metadata = source.endswith((".json", ".md", ".csv")) and (any(token in upper for token in SUPPORT_TOKENS)
                    or name == "AUDIT_KEY_CYPHER.json")
        attempts = upper == "ATTEMPTS.JSONL"
        if command or junit or metadata or attempts:
            selected.add(source)
    # Supporting evidence stays small. Raw native/MCP/child files, selected
    # reports and Oracle evidence keep the unchanged legacy 128MiB/512MiB limits;
    # no partial JSONL, partial report or partial Oracle is emitted.
    session_assets = set().union(*(_run_assets(indexed, p) for p in (*roots.values(), *observations.values())))
    bounded = set()
    for source in selected:
        if source in session_assets:
            bounded.add(source)
            continue
        limit = MAX_JUNIT_BYTES if source.lower().endswith(".xml") else MAX_SUPPORT_BYTES
        if _support_size(root, source) > limit:
            if source in required:
                raise H2ExportError("Explicit supporting evidence exceeds its lightweight byte limit")
            # A large supporting document is still present in the sealed index;
            # the unchanged exporter lists its Full SHA as NOT_INCLUDED.
            continue
        legacy._read_regular(root, source, max_bytes=limit)
        bounded.add(source)
    require(len(bounded) <= 9900, "H2 selection exceeds conservative member budget")
    return bounded


def _validate_ids(run_ids, observation_run_ids):
    runs, observations = list(run_ids), list(observation_run_ids)
    require(bool(runs), "Select at least one genuine engineering Challenge Run")
    combined = runs + observations
    require(all(isinstance(value, str) and UUID.fullmatch(value) for value in combined)
            and len(set(combined)) == len(combined), "Distinct canonical Run IDs are required")
    return runs, observations


def _worker(full_archive, output_zip, run_ids, observation_run_ids, created_at, support_paths):
    root = ordinary_path(full_archive)
    output = ordinary_path(output_zip)
    require((root / "EVIDENCE_MANIFEST.json").is_file(), "H2 export requires the final Full Archive seal")
    require(not output.is_relative_to(root), "Audit-Lite output must be outside Full")
    indexed, provenance = legacy._source_index(root)
    require(provenance["index_type"] == "FULL_ARCHIVE_MANIFEST", "H2 collection is not finally sealed")
    runs, observations = _validate_ids(run_ids, observation_run_ids)
    observed = observation_roots(root, indexed, observations)
    for source in support_paths:
        evidence_verify.safe_relative(source)
    original = legacy._selection
    chosen = None

    def select(actual_root, actual_index, actual_roots):
        nonlocal chosen
        require(actual_root == root and actual_index == indexed, "Full index changed during adapter admission")
        chosen = h2_selection(root, indexed, actual_roots, observed, support_paths)
        return chosen

    try:
        legacy._selection = select
        receipt = legacy.export_archive(root, output, run_ids=runs, created_at=created_at)
    finally:
        legacy._selection = original
    receipt.update(adapter_version=VERSION, selected_observation_session_ids=observations,
        observation_qualification="SUPPORTING_SOURCE_ONLY; NOT_EXECUTED; NO_SYNTHETIC_EVALUATION_REPORT; SEALED_PREPARED_LIFECYCLE_NOT_INCLUDED",
        manual_repeat_qualification="BOUNDED_ORIGINAL_JUNIT_AND_RECOVERY_MATRIX_SUPPORT_ONLY; UUID_JOIN_TO_ATTEMPTS; NOT_SCORED_RUN_INDEX",
        selected_support_paths=sorted(support_paths), included_selection_count=len(chosen),
        omitted_heavy_evidence="FULL_ARCHIVE_SHA256_POINTERS_IN_NOT_INCLUDED; ORIGINAL_BYTES_UNVERIFIED",
        raw_native_and_mcp_files="COMPLETE_SELECTED_FILES_WITH_EXISTING_REDACTION_AND_LINE_SHA",
        selection_mutation_scope="DISPOSABLE_HOST_PROCESS_ONLY; NO_LEGACY_SOURCE_OR_VERIFIER_CHANGE")
    return receipt


def export_h2(full_archive, output_zip, *, run_ids, observation_run_ids=(), created_at,
              support_paths=(), timeout_seconds=600):
    """Run the thin selection adapter in a fresh interpreter, without secrets."""
    runs, observations = _validate_ids(run_ids, observation_run_ids)
    require(isinstance(created_at, str) and bool(created_at), "Explicit fixed created_at is required")
    require(type(timeout_seconds) is int and 0 < timeout_seconds <= 1800, "Offline export timeout must be bounded")
    root, output = ordinary_path(full_archive), ordinary_path(output_zip)
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "_worker", str(root), str(output),
               "--created-at", created_at]
    for value in runs:
        command += ["--run-id", value]
    for value in observations:
        command += ["--observation-run-id", value]
    for value in support_paths:
        evidence_verify.safe_relative(value)
        command += ["--include-relative", value]
    environment = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "LANG", "LC_ALL", "TZ", "TMPDIR"}}
    try:
        process = subprocess.run(command, capture_output=True, env=environment, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        raise H2ExportError("Offline export exceeded its explicit resource timeout") from error
    require(len(process.stdout) <= MAX_WORKER_REPLY and len(process.stderr) <= MAX_WORKER_REPLY,
            "Worker diagnostic byte limit exceeded")
    require(process.returncode == 0, "Isolated exporter failed; no source/result fallback applied")
    result = evidence_verify.load_json(process.stdout)
    require(isinstance(result, dict) and result.get("adapter_version") == VERSION
            and result.get("source_writes") is False, "Invalid actual exporter receipt")
    # Independent unchanged verifier runs again outside the selection child.
    verification = evidence_verify.verify_bundle(output)
    require(result.get("bundle_sha256") == verification["bundle_sha256"], "Export changed after worker verification")
    result["independent_parent_verification"] = verification
    result["worker_exit_code"] = process.returncode
    result["adapter_source_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("operation", choices=("export", "_worker"))
    cli.add_argument("full_archive", type=Path)
    cli.add_argument("output_zip", type=Path)
    cli.add_argument("--run-id", action="append", required=True)
    cli.add_argument("--observation-run-id", action="append", default=[])
    cli.add_argument("--include-relative", action="append", default=[])
    cli.add_argument("--created-at", required=True)
    args = cli.parse_args(argv)
    try:
        function = _worker if args.operation == "_worker" else export_h2
        result = function(args.full_archive, args.output_zip, run_ids=args.run_id,
            observation_run_ids=args.observation_run_id, created_at=args.created_at, support_paths=args.include_relative)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(json.dumps({"status": "ERROR", "adapter_version": VERSION, "error_type": type(error).__name__,
            "qualification": "No grade, source, seal or original evidence changed"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
