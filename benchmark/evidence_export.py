"""Read-only Full Archive to deterministic, content-addressed Audit-Lite ZIP.

The exporter selects evidence, never reruns an experiment or changes its score.
Exported material is maintainer audit data, not a Participant task package.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import cache
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Sequence
import zipfile

from benchmark import evidence_verify
from integrations.codex_trace import redact, redact_text


EXPORT_VERSION = "1.0.0"
MAX_SOURCE_BYTES = 128 * 1024**2
MAX_SELECTED_BYTES = 512 * 1024**2
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RUN_TOP_FILES = {"evaluation_report.json", "runtime_metadata.json", "public_manifest.json", "input_seal.json",
                  "run_evidence_manifest.json", "codex_events.jsonl", "native_rollout_summary.json",
                  "native_agent_trace.jsonl", "agent_trace.jsonl", "execution_trace.jsonl", "codex_stderr.log",
                  "exact_stdin.txt", "submission.diff", "patch.diff", "public_test_changes.diff", "submission_metadata.json",
                  "runtime_activity.jsonl", "runtime_status.json", "gateway_requests.jsonl", "gateway_transport_events.jsonl"}
_ARCHIVE_SUMMARIES = {"PILOT_RESULTS.json", "POSTMORTEM_RESULTS.json", "MULTI_AGENT_TIMELINE.json",
                      "MULTI_AGENT_TIMELINE.md", "PILOT_INPUT_COMPARISON.json", "FINAL_VERDICTS.json",
                      "FINAL_SEAL_SUMMARY.json", "SEAL_OUTPUTS_SHA256.json", "LIVE_GATE.json", "PROTOCOL.json", "summary.json"}


class EvidenceExportError(ValueError):
    """Evidence selection, safety or consistency failed; source stays untouched."""


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _read_regular(root: Path, relative: str, *, max_bytes=MAX_SOURCE_BYTES) -> bytes:
    """Read through directory descriptors, refusing linked/special components."""
    evidence_verify.safe_relative(relative)
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = relative.split("/")
        for component in parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > max_bytes:
                raise EvidenceExportError("Source must be a bounded regular single-link file")
            blocks, size = [], 0
            while block := os.read(fd, 1024 * 1024):
                size += len(block)
                if size > max_bytes:
                    raise EvidenceExportError("Source grew beyond byte limit")
                blocks.append(block)
            after = os.fstat(fd)
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
            ) or size != info.st_size:
                raise EvidenceExportError("Source changed during read")
            return b"".join(blocks)
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def _source_index(root: Path) -> tuple[dict[str, str], dict]:
    manifest = root / "EVIDENCE_MANIFEST.json"
    if manifest.exists() or manifest.is_symlink():
        raw = _read_regular(root, "EVIDENCE_MANIFEST.json")
        value = evidence_verify.load_json(raw)
        indexed = value.get("ordinary_files_sha256", value.get("files"))
        if not isinstance(indexed, dict) or not indexed:
            raise EvidenceExportError("Full Archive manifest has no file index")
        for path, digest in indexed.items():
            evidence_verify.safe_relative(path)
            if not isinstance(digest, str) or not _HEX.fullmatch(digest):
                raise EvidenceExportError("Invalid Full Archive source SHA")
        return indexed, {"index_type": "FULL_ARCHIVE_MANIFEST", "source_path": "EVIDENCE_MANIFEST.json",
                         "source_sha256": sha256(raw).hexdigest(), "indexed_file_count": len(indexed),
                         "indexed_total_bytes": value.get("total_bytes"),
                         "assurance": "selected source bytes verified; omitted source hash pointers not re-read"}
    # A new collection can export completed Run seals before the overall final seal.
    # Only stopped/sealed runs are eligible; unrelated in-progress files are ignored.
    indexed, seals = {}, []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {"participant", "workspace", "candidate", "pytest-tmp", "codex-state", ".git"}
                         and not (Path(directory) / d).is_symlink())
        if "run_evidence_manifest.json" not in names:
            continue
        run = Path(directory)
        if not _UUID.fullmatch(run.name) or (run / "codex-state").exists():
            raise EvidenceExportError("Eligible Run must be stopped and have an independent Run ID")
        relative = run.relative_to(root).as_posix()
        raw = _read_regular(root, relative + "/run_evidence_manifest.json")
        seal = evidence_verify.load_json(raw)
        if seal.get("run_id") != run.name or not isinstance(seal.get("files"), dict):
            raise EvidenceExportError("Invalid completed Run seal")
        indexed[relative + "/run_evidence_manifest.json"] = sha256(raw).hexdigest()
        for source, digest in seal["files"].items():
            path = relative + "/" + evidence_verify.safe_relative(source)
            if not _HEX.fullmatch(digest or "") or path in indexed:
                raise EvidenceExportError("Invalid or duplicate Run seal entry")
            indexed[path] = digest
        seals.append({"source_path": relative + "/run_evidence_manifest.json", "source_sha256": sha256(raw).hexdigest()})
    if not seals:
        raise EvidenceExportError("Full Archive or stopped Run seals are required")
    # Collection-level metadata is read at export time, not misrepresented as a
    # finally sealed collection. The actual selected bytes are still checked.
    supporting = [name for name in _ARCHIVE_SUMMARIES if (root / name).exists()]
    supporting += ["frozen_private_manifests/" + name for name in ("SMOKE-001.json", "A.json", "D.json")
                   if (root / "frozen_private_manifests" / name).exists()]
    for source in supporting:
        indexed[source] = sha256(_read_regular(root, source)).hexdigest()
    return indexed, {"index_type": "COMPLETED_RUN_SEALS", "seals": seals, "indexed_file_count": len(indexed),
                     "indexed_total_bytes": None, "supporting_metadata_index": "current bytes observed at export time",
                     "assurance": "completed Run selections only; collection not finally sealed"}


def _default_ids(root: Path, indexed: dict) -> list[str]:
    ids = []
    if "PILOT_RESULTS.json" in indexed:
        value = evidence_verify.load_json(_read_regular(root, "PILOT_RESULTS.json"))
        rows = value.get("pilots", []) if isinstance(value, dict) else value if isinstance(value, list) else None
        if rows is None:
            raise EvidenceExportError("Invalid Pilot summary")
        ids.extend(row["run_id"] for row in rows)
    if "POSTMORTEM_RESULTS.json" in indexed:
        value = evidence_verify.load_json(_read_regular(root, "POSTMORTEM_RESULTS.json"))
        if not isinstance(value, list):
            raise EvidenceExportError("Invalid postmortem summary")
        # An offline postmortem never travels without its original attempt.
        ids.extend(row["original_run_id"] for row in value)
        ids.extend(row["postmortem_run_id"] for row in value)
    if not ids:
        ids = [PurePosixPath(p).parent.name for p in indexed if p.endswith("/evaluation_report.json") and
               _UUID.fullmatch(PurePosixPath(p).parent.name)]
    return list(dict.fromkeys(ids))


def _run_roots(indexed, run_ids) -> dict[str, str]:
    if not run_ids or len(set(run_ids)) != len(run_ids):
        raise EvidenceExportError("Select distinct Run IDs")
    result = {}
    for run_id in run_ids:
        if not isinstance(run_id, str) or not _UUID.fullmatch(run_id):
            raise EvidenceExportError("Invalid selected Run ID")
        matches = [str(PurePosixPath(p).parent) for p in indexed if p.endswith("/evaluation_report.json") and
                   PurePosixPath(p).parent.name == run_id]
        if len(matches) != 1:
            raise EvidenceExportError("Selected Run is missing or ambiguous")
        result[run_id] = matches[0]
    return result


def _role(relative: str) -> str:
    name = PurePosixPath(relative).name
    if relative.endswith("/evaluation_report.json"):
        return "EVALUATION_REPORT"
    if name == "runtime_metadata.json":
        return "RUNTIME_METADATA"
    if name == "junit.xml":
        return "JUNIT"
    if name.startswith("oracle-") and name.endswith(".json"):
        return "HOST_DATABASE_ORACLE"
    if "native_rollouts" in PurePosixPath(relative).parts or name == "codex_events.jsonl":
        return "OFFICIAL_RAW_EVENT_FILE"
    if name.endswith("trace.jsonl") or name.startswith("MULTI_AGENT_TIMELINE") or name == "native_rollout_summary.json":
        return "NORMALIZED_TRACE_OR_COLLABORATION"
    if name.endswith(".diff"):
        return "SUBMISSION_OR_PUBLIC_TEST_DIFF"
    if name == "command.json":
        return "COMMAND_RECEIPT"
    if "sealed_public_inputs" in PurePosixPath(relative).parts or name in {"input_seal.json", "public_manifest.json", "exact_stdin.txt"}:
        return "SEALED_PUBLIC_INPUT"
    if name.startswith(("topology-", "recovery-", "pool-resource-", "concurrency-")):
        return "TRUSTED_EXECUTION_OR_RECOVERY_EVIDENCE"
    return "SUPPORTING_METADATA_OR_DIAGNOSTIC"


def _selection(root, indexed, roots):
    selected = set()
    for run_id, prefix in roots.items():
        for source in indexed:
            if not source.startswith(prefix + "/"):
                continue
            local = source[len(prefix) + 1:]
            parts = PurePosixPath(local).parts
            if len(parts) == 1 and local in _RUN_TOP_FILES:
                selected.add(source)
            elif parts[0] == "sealed_public_inputs" and not any(p in (".git", "__pycache__") for p in parts):
                selected.add(source)
            elif parts[:2] == ("artifacts", "native_rollouts") and source.endswith(".jsonl"):
                selected.add(source)
            elif len(parts) == 2 and parts[0] == "artifacts" and source.endswith((".json", ".xml", ".log")):
                selected.add(source)
    selected.update(p for p in _ARCHIVE_SUMMARIES if p in indexed)
    # Small command receipts are provenance, not their repeated multi-MB stdout.
    # Include every trusted collection command receipt; unrelated Run references
    # remain supporting archive metadata, never become selected score claims.
    for path in indexed:
        if path.endswith("/command.json") and not any(p in PurePosixPath(path).parts for p in (
            "participant", "workspace", "candidate", "pytest-tmp", ".git", "codex-state"
        )):
            selected.add(path)
    return selected


@cache
def _repository_prefix(root: Path) -> str | None:
    repository = root
    while repository.parent != repository and not (repository / "pyproject.toml").exists():
        repository = repository.parent
    return str(repository) if (repository / "pyproject.toml").exists() else None


def _portable_text(text: str, root: Path, *, redact_credentials=True) -> str:
    # Keep source references replayable without leaking maintainer absolute paths.
    value = text.replace(str(root) + "/", "archive://").replace(str(root), "archive://")
    repository = _repository_prefix(root)
    if repository:
        value = value.replace(repository + "/", "repository://").replace(repository, "repository://")
    value = re.sub(r"/home/[^/\s\"']+", "host://USER_HOME", value)
    return redact_text(value) if redact_credentials else value


def _portable(value, root):
    if isinstance(value, dict):
        return {k: _portable(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [_portable(v, root) for v in value]
    if isinstance(value, str):
        return _portable_text(value, root, redact_credentials=False)
    return value


def _transform(raw: bytes, path: str, root: Path) -> tuple[bytes, dict]:
    line_provenance = None
    if path.endswith(".jsonl"):
        outputs, line_provenance = [], []
        for n, line in enumerate(raw.splitlines(keepends=True), 1):
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            body = line[:-len(ending)] if ending else line
            try:
                old = evidence_verify.load_json(body)
                clean = _portable(redact(old), root)
                new = line if clean == old else json.dumps(clean, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode() + ending
            except evidence_verify.EvidenceVerifyError:
                new = _portable_text(body.decode("utf-8", errors="replace"), root).encode() + ending
            outputs.append(new)
            line_provenance.append({"line": n, "source_sha256": sha256(line).hexdigest(),
                                    "exported_sha256": sha256(new).hexdigest()})
        data = b"".join(outputs)
    elif path.endswith(".json"):
        old = evidence_verify.load_json(raw)
        clean = _portable(redact(old), root)
        data = raw if clean == old else _json(clean)
    else:
        # Evidence files selected here are UTF-8 text, not database or binary payload.
        try:
            data = _portable_text(raw.decode("utf-8"), root).encode("utf-8")
        except UnicodeError as error:
            raise EvidenceExportError("Selected evidence is not UTF-8 text") from error
    details = {"transformation": "NONE" if data == raw else "CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1"}
    if line_provenance is not None:
        details.update({"line_provenance": line_provenance, "line_range": [1, len(line_provenance)],
                        "slice_status": "COMPLETE_FILE", "source_line_bytes_verification": "original source only available in Full Archive"})
    return data, details


def _suite_expectation(root, indexed, report):
    expected_sha = (report.get("fingerprints") or {}).get("private_manifest_sha256")
    episode = report.get("episode_id")
    matches = [p for p, digest in indexed.items() if digest == expected_sha and "private_manifest" in p and p.endswith(".json")]
    if matches:
        path = sorted(matches)[0]
        raw = _read_regular(root, path)
        if sha256(raw).hexdigest() != expected_sha:
            raise EvidenceExportError("Private suite metadata differs from its frozen source SHA")
        config = evidence_verify.load_json(raw)
        if config.get("id") != episode:
            raise EvidenceExportError("Private suite metadata Episode differs")
        tests = config.get("expected_tests")
        count = config.get("expected_test_count")
        source = {"source_path": path, "source_sha256": expected_sha,
                  "source_included": False, "derivation": "necessary identities extracted from matched sealed private manifest"}
    elif "PROTOCOL.json" in indexed:
        raw = _read_regular(root, "PROTOCOL.json")
        if sha256(raw).hexdigest() != indexed["PROTOCOL.json"]:
            raise EvidenceExportError("Protocol changed after export indexing")
        protocol = evidence_verify.load_json(raw)
        candidates = protocol.get("suite_expectations", [])
        if isinstance(candidates, dict):
            candidates = list(candidates.values())
        match = next((v for v in candidates if isinstance(v, dict) and v.get("episode_id") == episode and
                      v.get("private_manifest_sha256") == expected_sha), None)
        if match is None:
            return {"availability": "UNVERIFIED", "reason": "No independently retained necessary-test specification matching report fingerprint"}
        tests, count = match.get("expected_tests"), match.get("expected_test_count")
        source = {"source_path": "PROTOCOL.json", "source_sha256": indexed["PROTOCOL.json"],
                  "private_manifest_sha256": expected_sha, "source_included": True,
                  "derivation": "frozen protocol metadata; private manifest original bytes not included"}
    else:
        return {"availability": "UNVERIFIED", "reason": "No independently retained necessary-test specification matching report fingerprint"}
    if not isinstance(tests, list) or not tests or any(not isinstance(v, str) or not v for v in tests) or len(set(tests)) != len(tests) or count != len(tests):
        raise EvidenceExportError("Invalid necessary test specification")
    kind = "nodeid" if all("::" in t for t in tests) else "test_name" if all("::" not in t for t in tests) else None
    if kind is None:
        raise EvidenceExportError("Mixed necessary-test identity conventions")
    return {"availability": "AVAILABLE", "identity_kind": kind, "expected_test_identities": tests,
            "expected_test_count": count, "private_manifest_sha256": expected_sha, **source}


def _run_index(roots, entries, objects, *, postmortems, root, indexed):
    rows = []
    def get(path):
        return evidence_verify.load_json(objects[entries[path]["object"]])
    for run_id, prefix in roots.items():
        report_path = prefix + "/evaluation_report.json"
        report = get(report_path)
        if report.get("run_id") != run_id:
            raise EvidenceExportError("Selected Report Run ID differs from directory")
        row = {"run_id": run_id, "source_run_path": prefix, "report": report_path,
               "sensitivity": "MAINTAINER_AUDIT", "evidence_kind": "HISTORICAL_RUN"}
        for key in ("overall_status", "runtime_status", "evaluation_status", "submission_integrity_status", "multi_agent_status",
                    "integration_status", "episode_id", "scenario_version", "scenario_variant", "fingerprints", "recovery_coverage"):
            row[key] = report.get(key)
        results = report.get("test_results")
        row["test_counts"] = {k: results.get(k) for k in ("collected", "passed", "failed", "errors", "skipped")} if isinstance(results, dict) else None
        runtime_path = prefix + "/runtime_metadata.json"
        row["runtime_metadata"] = runtime_path if runtime_path in entries else None
        runtime = get(runtime_path) if row["runtime_metadata"] else {}
        row["model"] = runtime.get("model")
        row["provider"] = runtime.get("provider", report.get("provider"))
        row["resource_policy"] = runtime.get("resource_watchdog")
        row["usage"] = runtime.get("usage", "UNAVAILABLE")
        row["completion_policy"] = runtime.get("completion_policy", "bounded" if runtime.get("timeout_seconds") else "UNAVAILABLE")
        row["agent_mode"] = runtime.get("agent_mode", report.get("agent_mode", "UNAVAILABLE"))
        row["failure_kind"] = runtime.get("failure_kind", report.get("failure_kind"))
        row["suite_expectation"] = _suite_expectation(root, indexed, report)
        row["subagents"] = get(prefix + "/native_rollout_summary.json").get("subagents") if prefix + "/native_rollout_summary.json" in entries else "UNAVAILABLE"
        row["junit"] = prefix + "/artifacts/junit.xml" if prefix + "/artifacts/junit.xml" in entries else None
        row["oracles"] = sorted(p for p in entries if p.startswith(prefix + "/artifacts/oracle-") and p.endswith(".json"))
        row["oracle_count"] = len(row["oracles"])
        row["traces"] = sorted(p for p in entries if p.startswith(prefix + "/") and PurePosixPath(p).name in (
            "native_agent_trace.jsonl", "agent_trace.jsonl", "execution_trace.jsonl"
        ))
        integrity = report.get("submission_integrity") or {}
        patch_path = next((prefix + "/" + name for name in ("submission.diff", "patch.diff") if prefix + "/" + name in entries), None)
        if integrity.get("patch_sha256") and patch_path:
            row["submission"] = {key: integrity.get(key) for key in (
                "patch_sha256", "baseline_tree_sha256", "expected_tree_sha256", "applied_candidate_tree_sha256", "status"
            )}
            row["submission"]["patch"] = patch_path
        else:
            row["submission"] = None
        pm = next((p for p in postmortems if p.get("postmortem_run_id") == run_id), None)
        row["postmortem_of"] = pm.get("original_run_id") if pm else None
        if pm:
            row["evidence_kind"] = "SEPARATE_OFFLINE_POSTMORTEM"
            row["qualification"] = "Independent new Run; original Runtime/Evaluation scores are not upgraded"
        rows.append(row)
    return {"schema_version": EXPORT_VERSION, "runs": rows,
            "denominator_policy": "all selected original attempts preserved; postmortems are separate, never automatic completions"}


def export_archive(full_archive: Path | str, output_zip: Path | str, *, run_ids: Sequence[str] | None = None,
                   created_at: str | None = None) -> dict:
    """Export stopped Run evidence outside Full Archive without any source write."""
    temporary = None
    try:
        supplied = Path(full_archive).absolute()
        if supplied.is_symlink() or not supplied.is_dir():
            raise EvidenceExportError("Full Archive must be a regular directory")
        root = supplied.resolve(strict=True)
        output = Path(output_zip).absolute()
        if output.exists() or output.is_symlink():
            raise EvidenceExportError("Output must be new; overwrite refused")
        parent = output.parent.resolve(strict=True)
        if parent == root or root in parent.parents:
            raise EvidenceExportError("Output cannot be inside Full Archive")
        output = parent / output.name
        created_at = created_at or datetime.now(timezone.utc).isoformat()
        try:
            stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise EvidenceExportError("created_at must be an ISO timestamp") from error
        if stamp.tzinfo is None:
            raise EvidenceExportError("Export timestamp must include timezone")
        indexed, provenance = _source_index(root)
        roots = _run_roots(indexed, list(run_ids) if run_ids is not None else _default_ids(root, indexed))
        if any((root / prefix / "codex-state").exists() for prefix in roots.values()):
            raise EvidenceExportError("Selected Run still has active native state")
        selected = _selection(root, indexed, roots)
        objects, entries, total_source = {}, {}, 0
        for source in sorted(selected):
            raw = _read_regular(root, source)
            if sha256(raw).hexdigest() != indexed[source]:
                raise EvidenceExportError(f"Source differs from frozen index: {source}")
            total_source += len(raw)
            if total_source > MAX_SELECTED_BYTES:
                raise EvidenceExportError("Selected evidence exceeds byte budget")
            data, details = _transform(raw, source, root)
            digest = sha256(data).hexdigest()
            obj = "objects/" + digest
            if obj in objects and objects[obj] != data:
                raise EvidenceExportError("CAS collision")
            objects[obj] = data
            owner = next((run_id for run_id, prefix in roots.items() if source.startswith(prefix + "/")), None)
            entries[source] = {"source_path": source, "source_sha256": indexed[source], "source_bytes": len(raw),
                               "exported_sha256": digest, "exported_bytes": len(data), "object": obj,
                               "run_id": owner, "role": _role(source), "sensitivity": "MAINTAINER_AUDIT",
                               "included": True, **details}
        postmortems = evidence_verify.load_json(objects[entries["POSTMORTEM_RESULTS.json"]["object"]]) if "POSTMORTEM_RESULTS.json" in entries else []
        run_index = _run_index(roots, entries, objects, postmortems=postmortems, root=root, indexed=indexed)
        omitted = [{"source_path": path, "source_sha256": digest, "included": False,
                    "status": "NOT_INCLUDED", "supports": "Full Archive replay or historical evidence outside this export"}
                   for path, digest in sorted(indexed.items()) if path not in entries]
        verifier_bytes = Path(evidence_verify.__file__).read_bytes()
        manifest = {"schema_version": EXPORT_VERSION, "kind": "ORDERFLOW_AUDIT_LITE", "created_at": created_at,
                    "sensitivity": "MAINTAINER_AUDIT", "full_archive": {"archive_id": root.name, **provenance},
                    "entries": list(entries.values()), "verifier_source_sha256": sha256(verifier_bytes).hexdigest(),
                    "qualification": "Local consistency and source pointers; omitted bytes and runtime origin remain UNVERIFIED",
                    "determinism": "explicit created_at; fixed ZIP timestamp, member ordering and compression settings"}
        readme = f"""# OrderFlow Audit-Lite\n\nExport {created_at}; source archive `{root.name}`.\n\nSensitivity: **MAINTAINER_AUDIT**. Do not provide this package to Benchmark Participants.\nNo Hidden Test source, Reference Patch source, credential file or business database is included.\n\n## Offline verification\n\nUse a verifier obtained independently from the maintainer repository, then run:\n\n```sh\npython3 -I verify_audit_bundle.py verify audit.zip --json\npython3 -I verify_audit_bundle.py inspect audit.zip --json\n```\n\nThe bundled verifier has SHA256 `{sha256(verifier_bytes).hexdigest()}`. Its inclusion is a portability convenience,\nnot independent authentication: replacing a package and its own verifier/checksums can evade an untrusted self-check.\nCompare the externally supplied ZIP digest and trusted verifier source before relying on a received package.\nThe verifier never executes package code, extracts files, calls a model or contacts the network.\n\n## Included and omitted evidence\n\n`MANIFEST.json` maps each original source path to a SHA256 content object. `RUN_INDEX.json` preserves\nactual original results; offline postmortems have separate Run IDs and never upgrade TIMEOUT or NOT_RUN.\nJSONL files are complete credential-redacted files, with original line numbers and separate source/export line hashes\nincluding their newline. Source-file hashes refer to Full Archive bytes, which may differ after path normalization.\n`NOT_INCLUDED.json` identifies omitted original evidence, its hash and supporting purpose. **The package cannot\nindependently verify those omitted original bytes or attest that historical execution actually happened.**\nRaw event references can be checked against included source-line hash pointers; redacted original bytes cannot be\nreconstructed, and hashes are not signatures or third-party immutable storage. Malformed official lines remain malformed.\n\n## Preservation and determinism\n\nExport only reads the stopped/sealed source files. It writes a new ZIP outside Full Archive and refuses overwrite.\nCAS removes duplicate exported content; DEFLATE compresses complete reports/Oracle evidence. Heavy workspaces,\nvirtual environments, business DBs and private answer source are pointers only. A fixed explicit export timestamp\nproduces identical bytes for identical source inputs and verifier version on the same compressor version.\n"""
        files = {**objects, "README_AUDIT.md": readme.encode(), "MANIFEST.json": _json(manifest),
                 "RUN_INDEX.json": _json(run_index), "NOT_INCLUDED.json": _json({"verification": "POINTERS_ONLY_ORIGINAL_BYTES_UNVERIFIED",
                                                                              "entries": omitted}),
                 "verify_audit_bundle.py": verifier_bytes}
        files["SHA256SUMS"] = "".join(f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())).encode("ascii")
        fd, temporary_name = tempfile.mkstemp(prefix=".orderflow-audit-", suffix=".zip", dir=parent)
        os.close(fd)
        temporary = Path(temporary_name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        verification = evidence_verify.verify_bundle(temporary)
        # Hard-link an already verified ordinary temporary file atomically. The
        # destination reservation is exclusive even if another exporter races.
        os.link(temporary, output, follow_symlinks=False)
        temporary.unlink()
        temporary = None
        source_total = provenance.get("indexed_total_bytes")
        result = {"status": "PASS", "output_zip": str(output), "bundle_sha256": verification["bundle_sha256"],
                  "bundle_bytes": output.stat().st_size, "full_archive_indexed_bytes": source_total,
                  "included_source_bytes": total_source, "included_exported_bytes": sum(e["exported_bytes"] for e in entries.values()),
                  "unique_exported_content_bytes": sum(len(b) for b in objects.values()),
                  "full_archive_size_reduction_fraction": 1 - output.stat().st_size / source_total if isinstance(source_total, int) and source_total else None,
                  "run_ids": list(roots), "created_at": created_at, "verification": verification,
                  "source_writes": False, "zip_determinism_scope": "same source/time/verifier/compressor version"}
        return result
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError, IndexError) as error:
        if isinstance(error, EvidenceExportError):
            raise
        raise EvidenceExportError(str(error)) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_bundle(bundle: Path | str) -> dict:
    try:
        return evidence_verify.verify_bundle(bundle)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError, IndexError) as error:
        raise EvidenceExportError(str(error)) from error


def inspect_bundle(bundle: Path | str) -> dict:
    try:
        return evidence_verify.inspect_bundle(bundle)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError, IndexError) as error:
        raise EvidenceExportError(str(error)) from error
