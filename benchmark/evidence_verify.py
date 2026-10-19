"""Bounded, read-only OrderFlow Audit-Lite verifier using only the stdlib.

This file also runs directly outside the repository.  It never extracts a ZIP,
imports submitted code, contacts a service, or trusts a verifier inside a ZIP.
Checksums establish local consistency, not the origin of historical execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


SCHEMA_VERSION = "1.0.0"
MAX_ZIP_BYTES = 256 * 1024**2
MAX_MEMBERS = 10000
MAX_MEMBER_BYTES = 128 * 1024**2
MAX_TOTAL_BYTES = 512 * 1024**2
MAX_COMPRESSION_RATIO = 2000
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_ROOT_FILES = {"README_AUDIT.md", "MANIFEST.json", "RUN_INDEX.json", "NOT_INCLUDED.json",
               "SHA256SUMS", "verify_audit_bundle.py"}
_STATUSES = {"PASS", "FAIL", "ERROR", "TIMEOUT", "CANCELLED", "PARTIAL", "NOT_RUN", "NOT_IMPLEMENTED",
             "UNAVAILABLE", "UNVERIFIED", "DISABLED", "PREPARED", "BLOCKED", "PROVIDER_FAILURE", "RESOURCE_ERROR",
             "UPSTREAM_ERROR", "CONDITIONAL", "NOT_APPLICABLE"}


class EvidenceVerifyError(ValueError):
    """The package is unsafe, incomplete, or internally inconsistent."""


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1000:
        raise EvidenceVerifyError("Invalid relative path")
    if any(ord(c) < 32 for c in value) or "\\" in value or ":" in value:
        raise EvidenceVerifyError("Non-portable or control-character path")
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts) or PurePosixPath(value).is_absolute():
        raise EvidenceVerifyError("Absolute path or traversal refused")
    if unicodedata.normalize("NFC", value) != value:
        raise EvidenceVerifyError("Non-canonical Unicode path")
    if any(p.endswith((".", " ")) for p in parts):
        raise EvidenceVerifyError("Non-portable trailing path characters")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    if any(p.split(".")[0].casefold() in reserved for p in parts):
        raise EvidenceVerifyError("Reserved device path refused")
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise EvidenceVerifyError("Invalid SHA256")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise EvidenceVerifyError("Duplicate JSON key")
        result[key] = value
    return result


def load_json(data: bytes):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              EvidenceVerifyError("Non-finite JSON number")))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise EvidenceVerifyError(f"Invalid JSON: {type(error).__name__}") from error


def _read_package(path: Path) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ZIP_BYTES:
        raise EvidenceVerifyError("ZIP must be an ordinary bounded file")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                raise EvidenceVerifyError("ZIP member budget exceeded")
            names, folded, total = set(), set(), 0
            for info in infos:
                name = safe_relative(info.filename)
                if name in names or name.casefold() in folded:
                    raise EvidenceVerifyError("Duplicate ZIP member or case collision")
                names.add(name)
                folded.add(name.casefold())
                mode = info.external_attr >> 16
                if info.is_dir() or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                    raise EvidenceVerifyError("ZIP links, directories and special members refused")
                if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise EvidenceVerifyError("Encrypted or unsupported ZIP member")
                if info.file_size > MAX_MEMBER_BYTES:
                    raise EvidenceVerifyError("ZIP member byte budget exceeded")
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise EvidenceVerifyError("ZIP total byte budget exceeded")
                if info.file_size > max(info.compress_size, 1) * MAX_COMPRESSION_RATIO:
                    raise EvidenceVerifyError("ZIP compression ratio budget exceeded")
                if name not in _ROOT_FILES and not re.fullmatch(r"objects/[0-9a-f]{64}", name):
                    raise EvidenceVerifyError("Unexpected or nested ZIP member")
            if not _ROOT_FILES.issubset(names):
                raise EvidenceVerifyError("Required package file missing")
            result = {}
            actual_total = 0
            for info in infos:
                blocks, size = [], 0
                with archive.open(info) as source:
                    while block := source.read(1024 * 1024):
                        size += len(block)
                        actual_total += len(block)
                        if size > MAX_MEMBER_BYTES or actual_total > MAX_TOTAL_BYTES:
                            raise EvidenceVerifyError("Actual decompressed byte budget exceeded")
                        blocks.append(block)
                if size != info.file_size:
                    raise EvidenceVerifyError("ZIP member size mismatch")
                result[info.filename] = b"".join(blocks)
            return result
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError) as error:
        raise EvidenceVerifyError(f"Invalid ZIP: {type(error).__name__}") from error


def _checksums(files: dict[str, bytes]) -> None:
    expected = {}
    try:
        lines = files["SHA256SUMS"].decode("ascii").splitlines()
    except UnicodeError as error:
        raise EvidenceVerifyError("Invalid checksum encoding") from error
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise EvidenceVerifyError("Invalid SHA256SUMS record")
        digest, path = _digest(line[:64]), safe_relative(line[66:])
        if path in expected or path == "SHA256SUMS":
            raise EvidenceVerifyError("Duplicate or self-referential checksum")
        expected[path] = digest
    if set(expected) != set(files) - {"SHA256SUMS"}:
        raise EvidenceVerifyError("Checksum file/member set differs")
    for path, digest in expected.items():
        if sha256(files[path]).hexdigest() != digest:
            raise EvidenceVerifyError(f"Checksum mismatch: {path}")


def read_junit(data: bytes) -> dict:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise EvidenceVerifyError("JUnit XML declarations/entities refused")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise EvidenceVerifyError("Invalid JUnit XML") from error
    if root.tag not in {"testsuites", "testsuite"}:
        raise EvidenceVerifyError("Unexpected JUnit root")
    results = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "tests": []}
    for suite in root.iter("testsuite"):
        cases = list(suite.iter("testcase"))
        counts = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                  "errors": sum(c.find("error") is not None for c in cases),
                  "skipped": sum(c.find("skipped") is not None for c in cases)}
        for field, count in counts.items():
            if field in suite.attrib:
                try:
                    matches = int(suite.attrib[field]) == count
                except ValueError:
                    matches = False
                if not matches:
                    raise EvidenceVerifyError("JUnit declared counts differ from cases")
    for case in root.iter("testcase"):
        failed, errored, skipped = (bool(case.findall(t)) for t in ("failure", "error", "skipped"))
        if sum((failed, errored, skipped)) > 1:
            raise EvidenceVerifyError("Conflicting JUnit testcase outcomes")
        try:
            duration = float(case.get("time", "0"))
        except ValueError as error:
            raise EvidenceVerifyError("Invalid JUnit duration") from error
        if not math.isfinite(duration) or duration < 0:
            raise EvidenceVerifyError("Invalid JUnit duration")
        outcome, field = ("FAIL", "failed") if failed else ("ERROR", "errors") if errored else (
            "SKIPPED", "skipped") if skipped else ("PASS", "passed")
        nodeid = f"{case.get('classname', '')}::{case.get('name', '')}"
        if not case.get("name"):
            raise EvidenceVerifyError("JUnit testcase identity missing")
        results[field] += 1
        results["collected"] += 1
        results["tests"].append({"nodeid": nodeid, "outcome": outcome})
    if len({r["nodeid"] for r in results["tests"]}) != results["collected"]:
        raise EvidenceVerifyError("Duplicate JUnit test identity")
    return results


def _entries(files: dict[str, bytes], manifest: dict) -> dict[str, dict]:
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != "ORDERFLOW_AUDIT_LITE":
        raise EvidenceVerifyError("Unsupported manifest schema")
    if manifest.get("sensitivity") != "MAINTAINER_AUDIT":
        raise EvidenceVerifyError("Audit sensitivity missing")
    if not isinstance(manifest.get("created_at"), str) or not manifest["created_at"]:
        raise EvidenceVerifyError("Export timestamp missing")
    if _digest(manifest.get("verifier_source_sha256")) != sha256(files["verify_audit_bundle.py"]).hexdigest():
        raise EvidenceVerifyError("Bundled verifier source hash mismatch")
    rows = manifest.get("entries")
    if not isinstance(rows, list) or len(rows) > 10000:
        raise EvidenceVerifyError("Invalid manifest entries")
    entries, used_objects = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceVerifyError("Invalid manifest entry")
        source = safe_relative(row.get("source_path"))
        if source in entries:
            raise EvidenceVerifyError("Duplicate source manifest entry")
        source_sha, exported_sha = _digest(row.get("source_sha256")), _digest(row.get("exported_sha256"))
        forbidden = {"hidden_tests", "reference_patches", "private_manifests", "frozen_private_manifests", "private_labels"}
        if any(part in forbidden for part in PurePosixPath(source).parts):
            raise EvidenceVerifyError("Private answer source cannot be an included asset")
        obj = row.get("object")
        if obj != f"objects/{exported_sha}" or obj not in files:
            raise EvidenceVerifyError("CAS reference missing or invalid")
        data = files[obj]
        if sha256(data).hexdigest() != exported_sha or row.get("exported_bytes") != len(data):
            raise EvidenceVerifyError("CAS content or size mismatch")
        if type(row.get("source_bytes")) is not int or row["source_bytes"] < 0:
            raise EvidenceVerifyError("Invalid source byte count")
        if row.get("included") is not True or row.get("sensitivity") != "MAINTAINER_AUDIT":
            raise EvidenceVerifyError("Invalid inclusion or sensitivity")
        if row.get("transformation") not in {"NONE", "CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1"}:
            raise EvidenceVerifyError("Unknown evidence transformation")
        if row.get("transformation") == "NONE" and (source_sha != exported_sha or row["source_bytes"] != len(data)):
            raise EvidenceVerifyError("Untransformed source identity differs")
        provenance = row.get("line_provenance")
        if provenance is not None:
            lines = data.splitlines(keepends=True)
            if row.get("line_range") != [1, len(lines)] or row.get("slice_status") != "COMPLETE_FILE":
                raise EvidenceVerifyError("Incomplete or false line slice")
            if not isinstance(provenance, list) or len(provenance) != len(lines):
                raise EvidenceVerifyError("Line provenance count mismatch")
            for i, (item, raw) in enumerate(zip(provenance, lines), 1):
                if item.get("line") != i or _digest(item.get("exported_sha256")) != sha256(raw).hexdigest():
                    raise EvidenceVerifyError("Exported line SHA mismatch")
                _digest(item.get("source_sha256"))
                if row.get("transformation") == "NONE" and item["source_sha256"] != item["exported_sha256"]:
                    raise EvidenceVerifyError("Untransformed source line differs")
        entries[source] = row
        used_objects.add(obj)
    if used_objects != {name for name in files if name.startswith("objects/")}:
        raise EvidenceVerifyError("Orphan or missing CAS object")
    return entries


def _entry_json(files, entries, source):
    if source not in entries:
        raise EvidenceVerifyError("Required source missing")
    return load_json(files[entries[source]["object"]])


def _raw_references(value, entries, files, *, owner_run: str) -> int:
    """Validate every included normalized reference against its source line SHA."""
    count = 0
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            ref = item if all(k in item for k in ("path", "line", "sha256")) else None
            if ref is not None:
                path = ref["path"]
                if isinstance(path, str) and path.startswith("archive://"):
                    path = path[len("archive://"):]
                row = entries.get(path)
                if row is None or row.get("run_id") != owner_run:
                    raise EvidenceVerifyError("Raw event reference missing or cross-run")
                n = ref["line"]
                lines = row.get("line_provenance", [])
                if type(n) is not int or not 1 <= n <= len(lines) or ref["sha256"] != lines[n - 1]["source_sha256"]:
                    raise EvidenceVerifyError("Raw event source line hash mismatch")
                count += 1
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return count


def _native_identities(runtime, summary, entries, files, owner_run):
    """Bind claimed verified children to their first own official session_meta.

    Native scheduling/completion semantics remain in the raw records for audit;
    this check does not infer a child from natural-language role descriptions.
    """
    metadata, events_by_thread, file_threads = {}, {}, {}
    declared_verified = (summary.get("subagents") or {}).get("verified_count", 0)
    records = (runtime.get("native_rollouts") or {}).get("files", [])
    for record in records:
        path = record.get("path")
        if isinstance(path, str) and path.startswith("archive://"):
            path = path[len("archive://"):]
        if path not in entries or entries[path].get("run_id") != owner_run:
            raise EvidenceVerifyError("Native raw file missing or cross-run")
        if record.get("sha256") != entries[path]["source_sha256"]:
            raise EvidenceVerifyError("Native source-file hash differs")
        lines = files[entries[path]["object"]].splitlines()
        if not lines:
            if declared_verified:
                raise EvidenceVerifyError("Native session file empty")
            continue
        try:
            first = load_json(lines[0])
        except EvidenceVerifyError:
            if declared_verified:
                raise
            continue
        if first.get("type") != "session_meta" or not isinstance(first.get("payload"), dict):
            if declared_verified:
                raise EvidenceVerifyError("First own native session_meta missing")
            continue
        meta = first["payload"]
        identifier = meta.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in metadata:
            raise EvidenceVerifyError("Native own thread identity missing or duplicated")
        metadata[identifier] = meta
        events_by_thread[identifier] = []
        for n, line in enumerate(lines, 1):
            try:
                event = load_json(line)
            except EvidenceVerifyError:
                if declared_verified:
                    raise
                continue
            if isinstance(event, dict):
                events_by_thread[identifier].append((n, event))
        file_threads[path] = identifier
    lead = runtime.get("thread_id")
    own_rows, own_turns, pending = {}, {}, set(metadata)
    while pending:
        advanced = False
        for identifier in sorted(pending):
            parent = metadata[identifier].get("parent_thread_id")
            if parent and parent not in own_turns:
                continue
            accepted, turns, active = {}, set(), None
            for n, event in events_by_thread[identifier][1:]:
                payload = event.get("payload")
                if not isinstance(payload, dict) or event.get("type") == "session_meta":
                    continue
                if event.get("type") == "event_msg" and payload.get("type") == "task_started":
                    turn = payload.get("turn_id")
                    valid = isinstance(turn, str) and bool(turn)
                    if parent:
                        attribution = payload.get("turn_attribution")
                        valid = valid and isinstance(attribution, dict) and attribution.get("parent_turn_id") in own_turns[parent] and turn not in own_turns[parent]
                    active = turn if valid else None
                    if valid:
                        turns.add(turn)
                if active and payload.get("thread_id") in (None, identifier) and payload.get("turn_id") in (None, active):
                    accepted[n] = event
            own_rows[identifier], own_turns[identifier] = accepted, turns
            pending.remove(identifier)
            advanced = True
        if not advanced:
            if any(a.get("verified") is True for a in (summary.get("subagents") or {}).get("agents", [])):
                raise EvidenceVerifyError("Verified native parent chain cannot be resolved")
            break

    def referenced(ref, identifier):
        if not isinstance(ref, dict):
            raise EvidenceVerifyError("Verified native evidence reference absent")
        path = ref.get("path", "")
        if path.startswith("archive://"):
            path = path[len("archive://"):]
        if file_threads.get(path) != identifier or ref.get("line") not in own_rows.get(identifier, {}):
            raise EvidenceVerifyError("Native evidence is inherited history or belongs to another thread")
        return own_rows[identifier][ref["line"]]

    def text(content, *, strip=True):
        if not isinstance(content, list):
            return None
        values = [p.get("text") for p in content if isinstance(p, dict) and p.get("type") in {"text", "Text", "input_text", "output_text"}]
        value = "\n".join(v for v in values if isinstance(v, str))
        # Nonemptiness may ignore outer whitespace. Identity comparisons must
        # preserve every original character in final answers and receipts.
        return (value.strip() if strip else value) if value.strip() else None

    agents = (summary.get("subagents") or {}).get("agents", [])
    if not isinstance(agents, list):
        raise EvidenceVerifyError("Invalid native child list")
    ids = set()
    for agent in agents:
        identifier = agent.get("agent_id")
        if identifier in ids or not isinstance(identifier, str):
            raise EvidenceVerifyError("Duplicate native child identity")
        ids.add(identifier)
        if agent.get("verified") is True:
            if identifier not in metadata or not agent.get("execution_verified") or not agent.get("completed") or not agent.get("parent_receipt"):
                raise EvidenceVerifyError("Verified child lacks its own execution/completion/receipt evidence")
            meta = metadata[identifier]
            if meta.get("parent_thread_id") != agent.get("parent_thread_id") or meta.get("session_id") != runtime.get("session_id", lead):
                raise EvidenceVerifyError("Verified child native parent/session association differs")
            parent = agent["parent_thread_id"]
            parent_path = metadata.get(parent, {}).get("agent_path") or "/root"
            own_path = meta.get("agent_path")
            source_meta = meta.get("source")
            source = ((source_meta.get("subagent") or {}).get("thread_spawn")
                      if isinstance(source_meta, dict) else None)
            if not isinstance(source, dict) or source.get("parent_thread_id") != parent or source.get("agent_path") != own_path or agent.get("agent_path") != own_path:
                raise EvidenceVerifyError("Verified native spawn metadata differs")
            spawn = referenced((agent.get("spawn") or {}).get("raw_reference"), parent)
            item = (spawn.get("payload") or {}).get("item") or {}
            if spawn.get("type") != "event_msg" or item.get("type") != "SubAgentActivity" or item.get("kind") != "started" or item.get("agent_thread_id") != identifier:
                raise EvidenceVerifyError("Verified native spawn event absent")
            delivery = referenced((agent.get("task_delivery") or {}).get("raw_reference"), identifier)
            dp = delivery.get("payload") or {}
            if delivery.get("type") != "response_item" or dp.get("type") != "agent_message" or dp.get("author") != parent_path or dp.get("recipient") != own_path:
                raise EvidenceVerifyError("Verified native task delivery absent")
            delivery_comm = referenced((agent.get("task_delivery") or {}).get("communication_reference"), identifier)
            if delivery_comm.get("type") != "inter_agent_communication_metadata" or (delivery_comm.get("payload") or {}).get("trigger_turn") is not True:
                raise EvidenceVerifyError("Verified native task trigger absent")
            complete = referenced((agent.get("completion") or {}).get("raw_reference"), identifier)
            cp = complete.get("payload") or {}
            if complete.get("type") != "event_msg" or cp.get("type") != "task_complete" or cp.get("error") is not None or not isinstance(cp.get("last_agent_message"), str):
                raise EvidenceVerifyError("Verified native successful task_complete absent")
            final = referenced((agent.get("final_answer") or {}).get("raw_reference"), identifier)
            fp = final.get("payload") or {}
            final_item = fp.get("item") or {}
            final_text = text(final_item.get("content"), strip=False) if final.get("type") == "event_msg" and final_item.get("type") == "AgentMessage" else text(fp.get("content"), strip=False) if final.get("type") == "response_item" and fp.get("role") == "assistant" else None
            if final_text != cp["last_agent_message"]:
                raise EvidenceVerifyError("Verified native final answer and completion differ")
            executed = any(e.get("type") == "event_msg" and (e.get("payload") or {}).get("thread_id") == identifier and
                           ((e.get("payload") or {}).get("item") or {}).get("type") in {"CommandExecution", "FileChange"} and
                           ((e.get("payload") or {}).get("item") or {}).get("status") == "completed" for e in own_rows[identifier].values())
            if not executed:
                raise EvidenceVerifyError("Verified child has no own completed tool activity")
            receipt = referenced((agent.get("parent_receipt") or {}).get("raw_reference"), parent)
            rp = receipt.get("payload") or {}
            receipt_text = text(rp.get("content"), strip=False)
            receipt_comm = referenced((agent.get("parent_receipt") or {}).get("communication_reference"), parent)
            expected_receipt = f"Message Type: FINAL_ANSWER\nTask name: {parent_path}\nSender: {own_path}\nPayload:\n" + cp["last_agent_message"]
            if receipt.get("type") != "response_item" or rp.get("type") != "agent_message" or rp.get("author") != own_path or rp.get("recipient") != parent_path or not isinstance(receipt_text, str) or receipt_text != expected_receipt or receipt_comm.get("type") != "inter_agent_communication_metadata" or (receipt_comm.get("payload") or {}).get("trigger_turn") is not False:
                raise EvidenceVerifyError("Verified native parent completion receipt absent")
    subagents = summary.get("subagents") or {}
    if "verified_count" in subagents and subagents["verified_count"] != sum(v.get("verified") is True for v in agents):
        raise EvidenceVerifyError("Native verified child count differs")


def _verify_runs(files, entries, index) -> list[dict]:
    if not isinstance(index, dict) or index.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceVerifyError("Invalid Run index")
    rows = index.get("runs")
    if not isinstance(rows, list) or not rows:
        raise EvidenceVerifyError("Run index empty")
    seen, conclusions = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceVerifyError("Run index row is not an object")
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not _UUID.fullmatch(run_id) or run_id in seen:
            raise EvidenceVerifyError("Invalid or duplicate Run ID")
        seen.add(run_id)
        root = safe_relative(row.get("source_run_path"))
        if PurePosixPath(root).name != run_id:
            raise EvidenceVerifyError("Run ID and source directory differ")
        report_path = row.get("report")
        if report_path != root + "/evaluation_report.json":
            raise EvidenceVerifyError("Report cross-run reference")
        report = _entry_json(files, entries, report_path)
        if not isinstance(report, dict) or report.get("run_id") != run_id:
            raise EvidenceVerifyError("Report Run ID differs")
        for key in ("overall_status", "runtime_status", "evaluation_status", "submission_integrity_status",
                    "multi_agent_status", "integration_status", "episode_id", "scenario_version", "scenario_variant"):
            if row.get(key) != report.get(key):
                raise EvidenceVerifyError(f"Run index/report disagreement: {key}")
            if key.endswith("status") and row.get(key) is not None and row[key] not in _STATUSES:
                raise EvidenceVerifyError("Unknown Run status")
        if row.get("fingerprints") != report.get("fingerprints"):
            raise EvidenceVerifyError("Run fingerprint disagreement")
        # Manual/postmortem reports have no runtime. Never invent an Agent session.
        runtime_path = row.get("runtime_metadata")
        if runtime_path:
            if runtime_path != root + "/runtime_metadata.json":
                raise EvidenceVerifyError("Runtime metadata cross-run reference")
            runtime = _entry_json(files, entries, runtime_path)
            if runtime.get("run_id") != run_id:
                raise EvidenceVerifyError("Runtime metadata Run ID differs")
            if row.get("model") != runtime.get("model") or row.get("resource_policy") != runtime.get("resource_watchdog"):
                raise EvidenceVerifyError("Runtime model/resource disagreement")
            if row.get("provider") != runtime.get("provider", report.get("provider")):
                raise EvidenceVerifyError("Provider/effort metadata differs")
            if runtime.get("provider") and report.get("provider") and runtime["provider"] != report["provider"]:
                raise EvidenceVerifyError("Runtime/report Provider disagreement")
            if row.get("agent_mode") != runtime.get("agent_mode", report.get("agent_mode", "UNAVAILABLE")):
                raise EvidenceVerifyError("Agent-mode metadata differs")
            if row.get("completion_policy") != runtime.get("completion_policy", "bounded" if runtime.get("timeout_seconds") else "UNAVAILABLE"):
                raise EvidenceVerifyError("Completion policy metadata differs")
            if runtime.get("runtime_result") is not None and runtime["runtime_result"] != report.get("runtime_status"):
                raise EvidenceVerifyError("Runtime terminal result differs")
            summary_path = root + "/native_rollout_summary.json"
            if summary_path in entries:
                summary = _entry_json(files, entries, summary_path)
                if summary.get("run_id") != run_id or row.get("subagents") != summary.get("subagents"):
                    raise EvidenceVerifyError("Native collaboration summary differs or cross-run")
                if summary.get("thread_id") and runtime.get("thread_id") and summary["thread_id"] != runtime["thread_id"]:
                    raise EvidenceVerifyError("Native lead identity differs from Runtime")
                _native_identities(runtime, summary, entries, files, run_id)
                _raw_references(summary, entries, files, owner_run=run_id)
                if report.get("multi_agent_status") == "PASS" and (summary.get("subagents") or {}).get("verified_count", 0) < 2:
                    raise EvidenceVerifyError("Multi-Agent PASS lacks two verified native children")
                if row.get("agent_mode") == "single" and (summary.get("subagents") or {}).get("spawned_count", 0):
                    if report.get("runtime_status") == "PASS":
                        raise EvidenceVerifyError("Successful Single-Agent Runtime unexpectedly spawned children")
        else:
            runtime = None
        status = report.get("evaluation_status", report.get("overall_status"))
        if status is None:
            status = report.get("overall_status")
        results = report.get("test_results")
        expectation = row.get("suite_expectation", {})
        suite_completeness = "UNVERIFIED"
        if expectation.get("availability") == "AVAILABLE":
            identities = expectation.get("expected_test_identities")
            if not isinstance(identities, list) or not identities or any(not isinstance(v, str) or not v for v in identities) or len(set(identities)) != len(identities):
                raise EvidenceVerifyError("Invalid required test identities")
            if expectation.get("expected_test_count") != len(identities):
                raise EvidenceVerifyError("Required test count differs from identities")
            if expectation.get("private_manifest_sha256") != (report.get("fingerprints") or {}).get("private_manifest_sha256"):
                raise EvidenceVerifyError("Required-test source fingerprint differs")
            _digest(expectation.get("source_sha256"))
            safe_relative(expectation.get("source_path"))
            if expectation.get("identity_kind") not in {"nodeid", "test_name"}:
                raise EvidenceVerifyError("Invalid required-test identity convention")
        elif expectation.get("availability") != "UNVERIFIED":
            raise EvidenceVerifyError("Required-test availability missing")
        junit = row.get("junit")
        if junit:
            if junit != root + "/artifacts/junit.xml":
                raise EvidenceVerifyError("JUnit cross-run reference")
            parsed = read_junit(files[entries[junit]["object"]]) if junit in entries else None
            if parsed is None or not isinstance(results, dict):
                raise EvidenceVerifyError("JUnit or test results missing")
            for key in ("collected", "passed", "failed", "errors", "skipped"):
                if results.get(key) != parsed[key]:
                    raise EvidenceVerifyError("JUnit/report test counts differ")
            identities = [(v.get("nodeid"), v.get("outcome")) for v in results.get("tests", [])]
            actual = [(v["nodeid"], v["outcome"]) for v in parsed["tests"]]
            if Counter(identities) != Counter(actual):
                raise EvidenceVerifyError("JUnit/report test identities or outcomes differ")
            if status == "PASS" and (report.get("pytest_exit_code") != 0 or parsed["collected"] == 0 or
                                     parsed["failed"] or parsed["errors"] or parsed["skipped"]):
                raise EvidenceVerifyError("PASS contradicts pytest/JUnit")
            if row.get("test_counts") != {k: parsed[k] for k in ("collected", "passed", "failed", "errors", "skipped")}:
                raise EvidenceVerifyError("Run-index test counts differ")
            if expectation.get("availability") == "AVAILABLE":
                actual_required = [v["nodeid"] if expectation["identity_kind"] == "nodeid" else v["nodeid"].rsplit("::", 1)[-1] for v in parsed["tests"]]
                if status == "PASS" and Counter(actual_required) != Counter(expectation["expected_test_identities"]):
                    raise EvidenceVerifyError("Necessary required test set is incomplete or substituted")
                suite_completeness = "COMPLETE" if Counter(actual_required) == Counter(expectation["expected_test_identities"]) else "INCOMPLETE"
        elif status in {"PASS", "FAIL"}:
            raise EvidenceVerifyError("Scored Run lacks JUnit")
        elif results and row.get("test_counts") != {k: results.get(k) for k in ("collected", "passed", "failed", "errors", "skipped")}:
            raise EvidenceVerifyError("Unscored Run counts disagree")
        if row.get("submission"):
            submission = row["submission"]
            patch_path = submission.get("patch")
            if not patch_path.startswith(root + "/") or patch_path not in entries:
                raise EvidenceVerifyError("Submission missing or cross-run")
            integrity = report.get("submission_integrity") or {}
            if submission.get("patch_sha256") != integrity.get("patch_sha256"):
                raise EvidenceVerifyError("Submission identity differs from fidelity result")
            # Credential redaction may change exported bytes; source patch hash stays separate.
            if submission.get("patch_sha256") != entries[patch_path]["source_sha256"]:
                raise EvidenceVerifyError("Submission/source patch hash mismatch")
            for key in ("baseline_tree_sha256", "expected_tree_sha256", "applied_candidate_tree_sha256", "status"):
                if submission.get(key) != integrity.get(key):
                    raise EvidenceVerifyError("Submission tree/fidelity disagreement")
            if integrity.get("status") == "PASS" or report.get("submission_integrity_status") == "PASS":
                for key in ("patch_sha256", "baseline_tree_sha256", "expected_tree_sha256", "applied_candidate_tree_sha256"):
                    _digest(integrity.get(key))
                if integrity["expected_tree_sha256"] != integrity["applied_candidate_tree_sha256"]:
                    raise EvidenceVerifyError("Successful fidelity has different trees")
        elif report.get("submission_integrity_status") == "PASS":
            raise EvidenceVerifyError("Verified submission patch omitted")
        oracle_paths = row.get("oracles", [])
        oracle_rows = []
        for path in oracle_paths:
            if not path.startswith(root + "/artifacts/oracle-"):
                raise EvidenceVerifyError("Oracle cross-run reference")
            oracle = _entry_json(files, entries, path)
            if not isinstance(oracle, dict) or type(oracle.get("consistent")) is not bool:
                raise EvidenceVerifyError("Invalid Oracle record")
            oracle_rows.append(oracle)
            if status == "PASS" and not oracle["consistent"]:
                raise EvidenceVerifyError("PASS contradicts independent Oracle")
        embedded = report.get("database_oracle")
        if isinstance(embedded, list) and embedded:
            if Counter(json.dumps(v, sort_keys=True) for v in oracle_rows) != Counter(json.dumps(v, sort_keys=True) for v in embedded):
                raise EvidenceVerifyError("Report/independent Oracle records differ")
        if row.get("oracle_count") != len(oracle_rows):
            raise EvidenceVerifyError("Run-index Oracle count differs")
        if row.get("recovery_coverage") != report.get("recovery_coverage"):
            raise EvidenceVerifyError("Recovery coverage disagreement")
        raw_count = 0
        for path in row.get("traces", []):
            if not path.startswith(root + "/") or path not in entries:
                raise EvidenceVerifyError("Trace missing or cross-run")
            for line in files[entries[path]["object"]].splitlines():
                try:
                    event = load_json(line)
                except EvidenceVerifyError:
                    # Official malformed lines are kept; their provenance is still hashed.
                    continue
                if isinstance(event, dict) and event.get("run_id") not in (None, run_id):
                    raise EvidenceVerifyError("Trace event belongs to a different Run")
                raw_count += _raw_references(event, entries, files, owner_run=run_id)
        for entry in entries.values():
            if entry.get("run_id") == run_id and not entry["source_path"].startswith(root + "/"):
                raise EvidenceVerifyError("Manifest source outside declared Run")
        original = row.get("postmortem_of")
        if original and (original == run_id or original not in {v.get("run_id") for v in rows}):
            raise EvidenceVerifyError("Postmortem original Run missing or self-reference")
        conclusions.append({"run_id": run_id, "overall_status": report.get("overall_status"),
                            "runtime_status": report.get("runtime_status"), "evaluation_status": status,
                            "postmortem_of": original, "test_counts": row.get("test_counts"),
                            "oracle_count": len(oracle_rows), "validated_raw_references": raw_count,
                            "suite_completeness": suite_completeness})
    allowed = seen
    if any(v.get("run_id") is not None and v.get("run_id") not in allowed for v in entries.values()):
        raise EvidenceVerifyError("Manifest references unknown Run")
    return conclusions


def _not_included(files, entries):
    omitted = load_json(files["NOT_INCLUDED.json"])
    if not isinstance(omitted, dict) or omitted.get("verification") != "POINTERS_ONLY_ORIGINAL_BYTES_UNVERIFIED":
        raise EvidenceVerifyError("Omitted-byte qualification missing")
    seen = set()
    for row in omitted.get("entries", []):
        path = safe_relative(row.get("source_path"))
        if path in entries or path in seen or row.get("included") is not False or row.get("status") != "NOT_INCLUDED":
            raise EvidenceVerifyError("Omitted pointer conflicts with included entries")
        seen.add(path)
        _digest(row.get("source_sha256"))
    return len(seen)


def verify_bundle(path: Path | str) -> dict:
    """Verify included bytes and consistency; never claim source attestation."""
    path = Path(path)
    files = _read_package(path)
    _checksums(files)
    manifest = load_json(files["MANIFEST.json"])
    index = load_json(files["RUN_INDEX.json"])
    entries = _entries(files, manifest)
    conclusions = _verify_runs(files, entries, index)
    omitted = _not_included(files, entries)
    if (manifest.get("full_archive") or {}).get("indexed_file_count") != len(entries) + omitted:
        raise EvidenceVerifyError("Included/omitted index does not cover the source manifest")
    return {"status": "PASS", "schema_version": SCHEMA_VERSION,
            "bundle_sha256": sha256(path.read_bytes()).hexdigest(), "bundle_bytes": path.stat().st_size,
            "members": len(files), "included_source_files": len(entries), "unique_content_objects": len({v['object'] for v in entries.values()}),
            "not_included_pointers": omitted, "runs": conclusions,
            "verification_scope": "included bytes, checksums, Run/report/JUnit/Oracle/submission and raw-reference consistency",
            "original_bytes_not_included": "UNVERIFIED", "runtime_origin_attestation": "UNVERIFIED",
            "verifier_in_zip_executed": False, "network_used": False, "archive_extracted": False}


def inspect_bundle(path: Path | str) -> dict:
    """Inspection also verifies safety and consistency; it never upgrades a score."""
    result = verify_bundle(path)
    return {**result, "kind": "ORDERFLOW_AUDIT_LITE", "sensitivity": "MAINTAINER_AUDIT"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "inspect"))
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json", action="store_true", help="emit structured result (default)")
    args = parser.parse_args(argv)
    try:
        result = verify_bundle(args.bundle) if args.command == "verify" else inspect_bundle(args.bundle)
    except (EvidenceVerifyError, OSError, KeyError, TypeError, ValueError, RecursionError, AttributeError, IndexError) as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
