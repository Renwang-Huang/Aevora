#!/usr/bin/env python3
"""Offline Aevora trace joins derived from a fully verified, stopped Run.

This postprocessor does not call a model, graph, evaluator or candidate code.
It reuses OrderFlow's native parser to exclude inherited parent history. Local
hashes prove archive consistency, not independent execution attestation or an
Agent's mental use of a recommendation.

Official contracts (installed Codex 0.162.1):
https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/protocol/src/items.rs
https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/protocol/src/protocol.rs
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.evidence_export import _read_regular
from benchmark.evidence_verify import load_json, safe_relative
from integrations.codex_trace import parse_trace, redact
from integrations.native_rollout_trace import analyze_native_rollouts

VERSION = "aevora.trace-audit/1.1"
UNKNOWN = "UNKNOWN"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TOOLS = {"resolve_experience", "build_evidence_bundle", "record_decision"}
_MAX_FILE = 128 * 1024**2
_MAX_TOTAL = 1_000_000_000


class TraceAuditError(ValueError):
    """An unsafe, live or inconsistent archive cannot receive a final audit."""


def _require(condition, message):
    if not condition:
        raise TraceAuditError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _reference(path, line=None, raw=None, **fields):
    value = {"path": str(path), **fields}
    if line is not None:
        value.update(line=line, sha256=sha256(raw).hexdigest())
    return value


def _rows(path, data):
    result = []
    for line, raw in enumerate(data.splitlines(keepends=True), 1):
        if not raw.strip():
            continue
        _require(len(raw) <= 4 * 1024**2, "JSONL line exceeds audit budget")
        value = load_json(raw)
        _require(isinstance(value, dict), "JSONL objects required")
        result.append({"value": value, "reference": _reference(path, line, raw)})
    return result


def verify_run_seal(run_dir, expected_seal_sha256=None):
    """Verify all bytes covered by the full Run seal and its input seal chain."""
    run = Path(run_dir).absolute()
    _require(run.is_dir() and run.resolve() == run, "Run path must have no linked components")
    _require(not (run / "codex-state").exists() and not (run / "codex-state").is_symlink(),
             "Participant state still exists; stopped Run required")
    seal_bytes = _read_regular(run, "run_evidence_manifest.json", max_bytes=32 * 1024**2)
    seal_sha = sha256(seal_bytes).hexdigest()
    if expected_seal_sha256 is not None:
        _require(isinstance(expected_seal_sha256, str) and _HEX.fullmatch(expected_seal_sha256)
                 and expected_seal_sha256 == seal_sha, "Run seal differs from the supplied trusted pin")
    seal = load_json(seal_bytes)
    _require(isinstance(seal, dict) and seal.get("run_id") == run.name and _time(seal.get("sealed_at")),
             "Invalid full Run seal identity or timestamp")
    files = seal.get("files")
    _require(isinstance(files, dict) and 0 < len(files) <= 10000, "Invalid full Run file index")
    _require(seal.get("refused_entries") == [], "Full Run seal contains refused unsafe entries")
    actual_names = set()
    for directory, directories, names in os.walk(run, followlinks=False):
        for name in directories:
            _require(not (Path(directory) / name).is_symlink(), "Archive directory links refused")
        directories[:] = [name for name in directories if name not in {"codex-state", "__pycache__"}]
        for name in names:
            relative = (Path(directory) / name).relative_to(run).as_posix()
            if name == "run_evidence_manifest.json" and relative == name:
                continue
            _require(not name.endswith(".pending"), "Pending runtime material cannot receive final audit")
            actual_names.add(relative)
    _require(actual_names == set(files), "Full Run file identities differ from the seal")
    total = 0
    for relative, expected in files.items():
        safe_relative(relative)
        _require(isinstance(expected, str) and _HEX.fullmatch(expected), "Invalid file SHA256")
        data = _read_regular(run, relative, max_bytes=_MAX_FILE)
        total += len(data)
        _require(total <= _MAX_TOTAL, "Full Run exceeds audit byte budget")
        _require(sha256(data).hexdigest() == expected, "Full Run source SHA256 mismatch: " + relative)
    _require("input_seal.json" in files and seal.get("previous_seal_sha256") == files["input_seal.json"],
             "Input seal chain is missing or inconsistent")
    return {"status": "VERIFIED", "run_id": run.name, "seal_sha256": seal_sha,
            "sealed_at": seal["sealed_at"], "checked_files": len(files), "checked_bytes": total,
            "trusted_pin_supplied": expected_seal_sha256 is not None,
            "origin_attestation": "UNVERIFIED; local consistency only", "files": files}


def _sealed_bytes(run, seal, relative):
    _require(relative in seal["files"], "Required trace evidence is not sealed: " + relative)
    data = _read_regular(run, relative, max_bytes=_MAX_FILE)
    _require(sha256(data).hexdigest() == seal["files"][relative], "Evidence changed after full seal verification")
    return data


def _relative(run, value):
    _require(isinstance(value, str), "Trace path must be a string")
    path = Path(value)
    relative = path.relative_to(run).as_posix() if path.is_absolute() else path.as_posix()
    safe_relative(relative)
    return relative


def _project_native_metadata(run, seal, metadata):
    """Validate exact sealed paths, then project only their in-memory spelling.

    The collector may serialize a cwd-relative repository path when its Run
    was supplied relatively. That spelling must resolve from this explicitly
    identified repository root into this precise sealed Run. No basename,
    suffix, current working directory, identity or content inference is used.
    Existing absolute and run-relative paths receive the same strict checks.
    """
    native = metadata.get("native_rollouts", {})
    _require(isinstance(native, dict), "Native metadata must be an object")
    records = native.get("files", [])
    _require(isinstance(records, list) and len(records) <= 1000,
             "Native metadata file budget or schema invalid")
    repository = ROOT.absolute()
    _require(repository.resolve() == repository, "Repository path base must not contain links")
    archive_root = run / "artifacts" / "native_rollouts"
    projected_records, mappings, seen = [], [], set()
    original_canonical_sha = sha256(_canonical(metadata)).hexdigest()
    for record in records:
        _require(isinstance(record, dict) and isinstance(record.get("path"), str),
                 "Invalid native file record")
        before = record["path"]
        path = Path(before)
        if path.is_absolute():
            _require(str(path) == before, "Non-canonical absolute native path")
            safe_relative(before[1:])
            candidate, scope = path, "ABSOLUTE_SEALED_RUN_PATH"
        else:
            safe_relative(before)
            if before.startswith("artifacts/native_rollouts/"):
                candidate, scope = run / before, "RUN_RELATIVE_SEALED_PATH"
            else:
                candidate, scope = repository / before, "REPOSITORY_RELATIVE_SEALED_PATH"
        _require(candidate.is_relative_to(archive_root) and candidate != archive_root,
                 "Native path is outside this sealed Run's native archive")
        _require(candidate.resolve() == candidate, "Native path links refused")
        relative = candidate.relative_to(run).as_posix()
        safe_relative(relative)
        _require(relative not in seen, "Duplicate native file identity")
        seen.add(relative)
        data = _sealed_bytes(run, seal, relative)
        actual_sha = sha256(data).hexdigest()
        _require(record.get("sha256") == actual_sha == seal["files"][relative],
                 "Native record hash differs from the sealed file")
        after = str(candidate)
        projected_records.append({**record, "path": after})
        mappings.append({"before": before, "after": after, "source_scope": scope,
                         "changed": before != after, "sealed_relative_path": relative,
                         "sealed_file_sha256": actual_sha, "identity_and_content_modified": False})
    projected = {**metadata, "native_rollouts": {**native, "files": projected_records}}
    _require(sha256(_canonical(metadata)).hexdigest() == original_canonical_sha,
             "Original metadata mutated during path projection")
    parser_source = Path(analyze_native_rollouts.__code__.co_filename).absolute()
    _require(parser_source.resolve() == parser_source and parser_source.is_file(),
             "Native parser source must be an ordinary trusted file")
    evidence = {"status": "PROJECTED" if any(row["changed"] for row in mappings) else "NOT_NEEDED",
                "scope": "POST_RUNTIME_DERIVATION_ONLY; ORIGINAL_METADATA_AND_RUN_UNMODIFIED",
                "repository_path_base": str(repository),
                "original_metadata_sha256": seal["files"]["runtime_metadata.json"],
                "original_metadata_canonical_sha256": original_canonical_sha,
                "native_parser_source_path": str(parser_source),
                "native_parser_source_sha256": sha256(parser_source.read_bytes()).hexdigest(),
                "postprocessor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "mappings": mappings, "identities_modified": False, "content_modified": False}
    return projected, evidence


def _objects(value):
    """Inspect typed tool outputs, including JSON text inside MCP content.

    Free-form assistant/user prose is never supplied to this function. JSON
    text after a code-mode Output marker remains a typed tool output channel;
    this does not turn a printed claim into trusted causal evidence.
    """
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        _require(count <= 100000 and depth <= 24, "Typed tool output exceeds shape budget")
        if isinstance(item, dict):
            yield item
            pending.extend((part, depth + 1) for part in item.values())
        elif isinstance(item, list):
            pending.extend((part, depth + 1) for part in item)
        elif isinstance(item, str):
            candidates = [item.strip()]
            if "\nOutput:\n" in item:
                candidates.append(item.split("\nOutput:\n", 1)[1].strip())
            for text in candidates:
                if not text.startswith(("{", "[")):
                    continue
                try:
                    decoded = load_json(text.encode())
                except ValueError:
                    continue
                pending.append((decoded, depth + 1))
                break


def _structured(result):
    if not isinstance(result, dict):
        return {}
    direct = result.get("structuredContent")
    if isinstance(direct, dict):
        return direct
    return next((value for value in _objects(result.get("content", []))
                 if value.get("status") in {"AVAILABLE", "RECORDED_UNTRUSTED"}), {})


def _host_calls(run, seal):
    name = "aevora_mcp_events.jsonl"
    if name not in seal["files"]:
        return [], []
    calls, pending, rows = [], {}, _rows(run / name, _sealed_bytes(run, seal, name))
    sequences = []
    for row in rows:
        event = row["value"]
        _require(event.get("run_id") == run.name, "MCP event belongs to another Run")
        sequence = event.get("sequence")
        _require(type(sequence) is int and sequence > 0, "MCP event sequence unavailable")
        sequences.append(sequence)
        if event.get("category") != "JSONRPC":
            continue
        raw = event.get("raw_json")
        _require(isinstance(raw, str) and raw.endswith("\n"), "Archived MCP frame unavailable")
        _require(event.get("archived_message_sha256") == sha256(raw.encode()).hexdigest(),
                 "Archived MCP message SHA256 mismatch")
        rpc = load_json(raw.encode())
        _require(isinstance(rpc, dict) and rpc.get("jsonrpc") == "2.0", "Malformed archived JSONRPC")
        identifier = rpc.get("id")
        key = (event.get("connection_id"), type(identifier).__name__, identifier)
        if event.get("direction") == "PARTICIPANT_TO_OFFICIAL_SDK" and rpc.get("method") == "tools/call":
            params = rpc.get("params", {})
            _require(params.get("name") in _TOOLS and key not in pending, "Invalid or duplicate host tool request")
            call = {"tool": params["name"], "connection_id": event.get("connection_id", UNKNOWN),
                    "jsonrpc_request_id": identifier, "request_timestamp": event.get("timestamp", UNKNOWN),
                    "request_reference": row["reference"], "argument_sha256": sha256(_canonical(params.get("arguments", {}))).hexdigest(),
                    "response_timestamp": UNKNOWN, "response_reference": UNKNOWN,
                    "response_status": "NOT_RETURNED", "query_id": UNKNOWN, "decision_id": UNKNOWN,
                    "native_agent_id": UNKNOWN, "mental_causality": "UNVERIFIED"}
            pending[key] = call
            calls.append(call)
        elif event.get("direction") == "OFFICIAL_SDK_TO_PARTICIPANT" and key in pending:
            call = pending.pop(key)
            result = rpc.get("result", {})
            output = _structured(result)
            call.update(response_timestamp=event.get("timestamp", UNKNOWN), response_reference=row["reference"],
                        response_status="ERROR" if "error" in rpc or result.get("isError") is True else "RETURNED" if output else "NO_STRUCTURED_RESULT",
                        query_id=output.get("query_id", UNKNOWN), decision_id=output.get("decision_id", UNKNOWN),
                        experience_id=output.get("experience_id", UNKNOWN),
                        result_sha256=sha256(_canonical(output)).hexdigest(), _output=output)
            if call["query_id"] != UNKNOWN:
                _require(isinstance(call["query_id"], str) and call["query_id"].startswith("query:" + run.name + ":"),
                         "Returned Query belongs to another Run")
            if call["decision_id"] != UNKNOWN:
                _require(isinstance(call["decision_id"], str) and call["decision_id"].startswith("decision:" + run.name + ":"),
                         "Returned Decision belongs to another Run")
    _require(sequences == list(range(1, len(sequences) + 1)), "MCP event sequence incomplete or duplicated")
    return calls, rows


def _native_rows(run, seal, metadata):
    native = metadata.get("native_rollouts", {})
    analysis = analyze_native_rollouts(run.name, run, native,
                                      expected_parent_thread_id=metadata.get("thread_id"))
    if analysis["summary"]["integrity"]["status"] != "COMPLETE":
        return [], analysis
    anchors = {}
    threads = {}
    for event in analysis["events"]:
        payload = event["payload"]
        ref = payload["raw_reference"]
        relative = _relative(run, ref["path"])
        if event["event_type"] == "native.session_meta":
            threads[relative] = payload["thread_id"]
        else:
            anchors.setdefault(relative, set()).add(ref["line"])
    own = []
    for record in native.get("files", []):
        relative = _relative(run, record["path"])
        _require(relative.startswith("artifacts/native_rollouts/"), "Native trace escaped its archive")
        rows = _rows(run / relative, _sealed_bytes(run, seal, relative))
        active = None
        ranges = []
        for row in rows:
            event = row["value"]; payload = event.get("payload", {})
            if event.get("type") == "event_msg" and payload.get("type") == "task_started":
                if active:
                    ranges.append(active)
                active = {"start": row["reference"]["line"], "end": len(rows) + 1,
                          "turn_id": payload.get("turn_id"), "anchored": False}
            if active:
                if row["reference"]["line"] in anchors.get(relative, set()):
                    active["anchored"] = True
                active["end"] = row["reference"]["line"]
                if event.get("type") == "event_msg" and payload.get("type") == "task_complete":
                    ranges.append(active); active = None
        if active:
            ranges.append(active)
        for span in ranges:
            if not span["anchored"]:
                continue
            for row in rows:
                line = row["reference"]["line"]
                payload = row["value"].get("payload", {})
                if span["start"] <= line <= span["end"] and payload.get("thread_id") in (None, threads.get(relative)) and payload.get("turn_id") in (None, span["turn_id"]):
                    own.append({**row, "thread_id": threads.get(relative, UNKNOWN), "turn_id": span["turn_id"]})
    return own, analysis


def _native_outputs(rows):
    calls = {}
    outputs = []
    for row in rows:
        event = row["value"]; payload = event.get("payload", {})
        path = row["reference"]["path"]
        if event.get("type") == "response_item" and payload.get("type") in {"function_call", "custom_tool_call"}:
            identifier = payload.get("call_id")
            if isinstance(identifier, str):
                _require((path, identifier) not in calls, "Duplicate own native call ID")
                calls[(path, identifier)] = row
        elif event.get("type") == "response_item" and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
            call = calls.get((path, payload.get("call_id")))
            if call and call["turn_id"] == row["turn_id"]:
                outputs.append({"source": "codex.native.typed_tool_output", "channel": "TYPED_FUNCTION_OR_CODEMODE_OUTPUT",
                    "thread_id": row["thread_id"], "turn_id": row["turn_id"], "call_id": payload["call_id"],
                    "native_tool_name": call["value"]["payload"].get("name", UNKNOWN), "server": UNKNOWN, "tool": UNKNOWN,
                    "timestamp": event.get("timestamp", UNKNOWN), "reference": row["reference"],
                    "call_reference": call["reference"], "_value": payload.get("output")})
        elif event.get("type") == "event_msg" and payload.get("type") in {"mcp_tool_call_end", "item_completed"}:
            item = payload.get("item", {})
            if payload.get("type") == "mcp_tool_call_end":
                invocation = payload.get("invocation", {})
                result = payload.get("result", {})
                result = result.get("Ok", result) if isinstance(result, dict) else result
                identifier = payload.get("call_id")
            elif isinstance(item, dict) and item.get("type") == "McpToolCall":
                invocation, result, identifier = item, item.get("result"), item.get("id")
            else:
                continue
            if invocation.get("server") == "aevora" and invocation.get("tool") in _TOOLS:
                outputs.append({"source": "codex.native.typed_mcp_output", "channel": "OFFICIAL_MCP_INVOCATION_FIELDS",
                    "thread_id": row["thread_id"], "turn_id": row["turn_id"], "call_id": identifier or UNKNOWN,
                    "server": invocation["server"], "tool": invocation["tool"],
                    "timestamp": event.get("timestamp", UNKNOWN), "reference": row["reference"], "_value": result})
    return outputs


def _exec_outputs(run, seal, destination, metadata):
    if "codex_events.jsonl" not in seal["files"]:
        return [], {"status": "UNAVAILABLE"}
    _sealed_bytes(run, seal, "codex_events.jsonl")
    summary = parse_trace(run / "codex_events.jsonl", destination / "exec_trace_derived.jsonl", run.name,
                          collected_at=metadata.get("ended_at"))
    outputs = []
    if summary.get("integrity", {}).get("status") != "COMPLETE":
        return outputs, summary
    if metadata.get("thread_id") not in (None, UNKNOWN, "UNAVAILABLE"):
        _require(summary.get("thread_id") == metadata["thread_id"], "Exec thread differs from current native Run")
    for row in _rows(run / "codex_events.jsonl", _sealed_bytes(run, seal, "codex_events.jsonl")):
        event = row["value"]; item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call" and item.get("server") == "aevora" and item.get("tool") in _TOOLS:
            outputs.append({"source": "codex.exec.typed_mcp_output", "channel": "OFFICIAL_EXEC_MCP_FIELDS",
                "thread_id": summary.get("thread_id", UNKNOWN), "call_id": item.get("id", UNKNOWN),
                "server": item["server"], "tool": item["tool"], "timestamp": UNKNOWN,
                "timestamp_source": "UNAVAILABLE_IN_EXEC_STREAM", "reference": row["reference"], "_value": item.get("result")})
    return outputs, summary


def _business_paths(changes):
    names = changes.keys() if isinstance(changes, dict) else [item.get("path") for item in changes if isinstance(item, dict)] if isinstance(changes, list) else []
    return sorted(name for name in names if isinstance(name, str) and re.search(r"(?:^|/)app/[^\n]+\.py$", name))


def _patch_evidence(run, seal, metadata, rows):
    host = []
    if "runtime_activity.jsonl" in seal["files"]:
        for row in _rows(run / "runtime_activity.jsonl", _sealed_bytes(run, seal, "runtime_activity.jsonl")):
            event = row["value"]
            if event.get("event_type") == "PATCH_TREE_CHANGE_FIRST_OBSERVED":
                host.append({"timestamp": event.get("detail", {}).get("observed_at", event.get("timestamp", UNKNOWN)),
                             "reference": row["reference"], "source": "trusted_runtime_observer",
                             "scope": "NONATOMIC_SOURCE_TREE_CHANGE_OBSERVATION"})
    patches, commands, begins = [], [], {}
    for row in rows:
        event = row["value"]; payload = event.get("payload", {})
        if event.get("type") != "event_msg":
            continue
        subtype = payload.get("type"); item = payload.get("item", {})
        if subtype == "patch_apply_begin":
            begins[(row["reference"]["path"], payload.get("call_id"))] = row
        elif subtype == "patch_apply_end" and payload.get("success") is True:
            paths = _business_paths(payload.get("changes", {}))
            if paths:
                begin = begins.get((row["reference"]["path"], payload.get("call_id")))
                patches.append({"timestamp": event.get("timestamp", UNKNOWN), "reference": row["reference"],
                    "thread_id": row["thread_id"], "paths": paths, "source": "official_successful_patch_event",
                    "request_timestamp": begin["value"].get("timestamp", UNKNOWN) if begin else UNKNOWN,
                    "request_reference": begin["reference"] if begin else UNKNOWN})
        elif subtype == "item_completed" and isinstance(item, dict):
            if item.get("type") == "FileChange" and item.get("status") == "completed":
                paths = _business_paths(item.get("changes", {}))
                if paths:
                    patches.append({"timestamp": event.get("timestamp", UNKNOWN), "reference": row["reference"],
                        "thread_id": row["thread_id"], "paths": paths, "source": "official_completed_file_change",
                        "request_timestamp": UNKNOWN, "request_reference": UNKNOWN})
            elif item.get("type") == "CommandExecution":
                commands.append({"timestamp": event.get("timestamp", UNKNOWN), "reference": row["reference"],
                    "thread_id": row["thread_id"], "status": item.get("status", UNKNOWN),
                    "exit_code": item.get("exit_code", UNKNOWN), "command_sha256": sha256(_canonical(item.get("command"))).hexdigest(),
                    "actual_source_write": "UNVERIFIED; arbitrary commands are not assumed to edit files"})
    def first(values):
        known = [value for value in values if _time(value["timestamp"])]
        return min(known, key=lambda value: _time(value["timestamp"])) if known else UNKNOWN
    return {"first_host_patch_observation": first(host), "first_successful_typed_business_patch": first(patches),
            "typed_business_patches": patches, "typed_commands": commands,
            "first_major_patch": UNKNOWN, "major_patch_reason": "Semantic importance cannot be established from event types alone",
            "ordering_assurance": "Observation timestamps; host polling is not exact first-write time and command writes may be unobserved"}


def _submission(run, seal):
    if "submission.diff" not in seal["files"]:
        return {"status": "NOT_PRODUCED", "timestamp": UNKNOWN}
    patch_sha = seal["files"]["submission.diff"]
    receipt = UNKNOWN
    if "execution_trace.jsonl" in seal["files"]:
        for row in _rows(run / "execution_trace.jsonl", _sealed_bytes(run, seal, "execution_trace.jsonl")):
            event = row["value"]
            submission = event.get("payload", {}).get("submission", {})
            if event.get("event_type") == "submission.received" and submission.get("sha256") == patch_sha:
                receipt = {"timestamp": submission.get("received_at", event.get("timestamp", UNKNOWN)),
                           "reference": row["reference"], "source": "trusted_runner_submission_receipt"}
                break
    return {"status": "SEALED_ARTIFACT", "patch_sha256": patch_sha,
            "artifact_reference": _reference(run / "submission.diff", sha256=patch_sha),
            "timestamp": receipt["timestamp"] if isinstance(receipt, dict) else UNKNOWN,
            "receipt": receipt, "actual_extraction_time": UNKNOWN}


def _before(left, right):
    a, b = _time(left), _time(right)
    return a < b if a and b else UNKNOWN


def _matching_native(call, native):
    matches = []
    for output in native:
        returned_at, requested_at = _time(output.get("timestamp")), _time(call.get("request_timestamp"))
        if returned_at and requested_at and returned_at < requested_at:
            continue
        objects = list(_objects(output["_value"]))
        identifiers = [(key, call.get(key)) for key in ("query_id", "decision_id") if call.get(key) != UNKNOWN]
        exact = [(key, identifier) for key, identifier in identifiers if any(value.get(key) == identifier for value in objects)]
        full_result = any(sha256(_canonical(value)).hexdigest() == call.get("result_sha256") for value in objects)
        if not exact and not full_result:
            continue
        if output.get("server") != UNKNOWN and output.get("tool") != call["tool"]:
            continue
        matches.append({key: value for key, value in output.items() if key != "_value"} | {
            "exact_identifier_fields": dict(exact), "exact_structured_result": full_result,
            "join_basis": "EXACT_QUERY_OR_DECISION_ID" if exact else "EXACT_RESULT_STRUCTURE; RPC_ID_LINK_UNAVAILABLE",
            "join_scope": "ACTUAL_TYPED_OUTPUT_VISIBILITY; NO_MENTAL_CAUSALITY_ASSERTION"})
    return matches


def _observed_paths(value, expected_id):
    paths = []
    for obj in _objects(value):
        entries = obj.get("observed_outcome_paths", [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("relation") == "OBSERVED_OUTCOME" and entry.get("records", {}).get("VerifiedOutcome", {}).get("id") == expected_id:
                paths.append(entry)
    return {sha256(_canonical(path)).hexdigest(): path for path in paths}


def audit_run(run_dir, output_dir, *, expected_seal_sha256=None, trusted_outcome_id=None):
    """Write a new derived audit outside the stopped Run; originals stay intact."""
    run, destination = Path(run_dir).absolute(), Path(output_dir).absolute()
    _require(destination != run and not destination.is_relative_to(run), "Derived output must be outside sealed Run")
    _require(not destination.exists() and not destination.is_symlink(), "Derived audit output must be new")
    seal = verify_run_seal(run, expected_seal_sha256)
    metadata = load_json(_sealed_bytes(run, seal, "runtime_metadata.json"))
    _require(metadata.get("run_id", run.name) == run.name, "Runtime metadata belongs to another Run")
    projected_metadata, projection = _project_native_metadata(run, seal, metadata)
    # Check existing ancestors before creating anything; mkdir through a link
    # could otherwise pollute a sealed Run before the later path check fails.
    ancestor = destination.parent
    while not ancestor.exists() and not ancestor.is_symlink():
        ancestor = ancestor.parent
    _require(ancestor.resolve() == ancestor and not ancestor.is_relative_to(run),
             "Derived output ancestors must not link into sealed Run")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _require(destination.parent.resolve() == destination.parent and not destination.parent.is_relative_to(run),
             "Derived output ancestors must not link into sealed Run")
    destination.mkdir(mode=0o700)
    calls, _ = _host_calls(run, seal)
    rows, native_analysis = _native_rows(run, seal, projected_metadata)
    native = _native_outputs(rows)
    exec_native, exec_analysis = _exec_outputs(run, seal, destination, metadata)
    native.extend(exec_native)
    patch = _patch_evidence(run, seal, metadata, rows)
    submission = _submission(run, seal)
    first_host = patch["first_host_patch_observation"]
    first_typed = patch["first_successful_typed_business_patch"]
    timeline = []
    for call in calls:
        call["native_matches"] = _matching_native(call, native) if call.get("response_status") == "RETURNED" else []
        actual_threads = sorted({match["thread_id"] for match in call["native_matches"] if match.get("thread_id") not in {UNKNOWN, "UNAVAILABLE", None}})
        call["native_agent_id"] = actual_threads[0] if len(actual_threads) == 1 else UNKNOWN
        call["native_identity_scope"] = "OFFICIAL_NATIVE_THREAD_METADATA; NEVER_HOST_PID_OR_CONNECTION"
        call["before_first_host_patch_observation"] = _before(call["response_timestamp"], first_host["timestamp"] if isinstance(first_host, dict) else UNKNOWN)
        call["before_first_typed_business_patch_completion"] = _before(call["response_timestamp"], first_typed["timestamp"] if isinstance(first_typed, dict) else UNKNOWN)
        call["before_first_successful_patch_request"] = _before(call["response_timestamp"], first_typed.get("request_timestamp", UNKNOWN) if isinstance(first_typed, dict) else UNKNOWN)
        call["before_final_submission_receipt"] = _before(call["response_timestamp"], submission["timestamp"])
        for stage in ("request", "response"):
            timeline.append({"timestamp": call[stage + "_timestamp"], "event_type": "aevora.tool_" + stage,
                             "tool": call["tool"], "reference": call[stage + "_reference"],
                             "query_id": call["query_id"], "decision_id": call["decision_id"]})
    observation = {"status": "NOT_REQUESTED", "mental_influence": "UNVERIFIED"}
    if trusted_outcome_id is not None:
        _require(isinstance(trusted_outcome_id, str) and 0 < len(trusted_outcome_id) <= 240,
                 "Bounded exact trusted outcome ID required")
        visible = []
        for call in calls:
            if call["response_status"] != "RETURNED":
                continue
            host_paths = _observed_paths(call.get("_output", {}), trusted_outcome_id)
            for output in native:
                actual_paths = _observed_paths(output["_value"], trusted_outcome_id)
                for path_hash in sorted(set(host_paths) & set(actual_paths)):
                    visible.append({"host_tool": call["tool"], "host_reference": call["response_reference"],
                                    "native_reference": output["reference"], "thread_id": output["thread_id"],
                                    "path_sha256": path_hash, "actual_path": host_paths[path_hash]})
        observation = {"status": "OBSERVED_IN_HOST_AND_TYPED_NATIVE_OUTPUT" if visible else "UNVERIFIED",
                       "trusted_outcome_id": trusted_outcome_id, "matches": visible,
                       "trust_scope": "EXACT_EXPECTED_ID_AND_ACTUAL_OBSERVED_OUTCOME_PATH; OUTCOME_AUTHORITY_VERIFIED_ELSEWHERE",
                       "mental_influence": "UNVERIFIED"}
    for row in (first_host, first_typed, submission.get("receipt", UNKNOWN)):
        if isinstance(row, dict):
            timeline.append({"event_type": row.get("source", "patch_observation"), **row})
    timeline.sort(key=lambda value: str(value.get("timestamp", UNKNOWN)))
    final_seal = verify_run_seal(run, seal["seal_sha256"])
    _require(final_seal["files"] == seal["files"], "Original Run changed during postprocessing")
    _require(sha256(Path(projection["native_parser_source_path"]).read_bytes()).hexdigest()
             == projection["native_parser_source_sha256"], "Native parser source changed during audit")
    _require(sha256(Path(__file__).read_bytes()).hexdigest() == projection["postprocessor_source_sha256"],
             "Postprocessor source changed during audit")
    report = {"schema_version": VERSION, "run_id": run.name, "postprocessing_only": True,
              "network_used": False, "model_called": False, "candidate_executed": False,
              "source_seal": {key: value for key, value in seal.items() if key != "files"},
              "native_metadata_path_projection": projection,
              "native_integrity": native_analysis["summary"]["integrity"],
              "native_subagents": native_analysis["summary"]["subagents"],
              "native_session_id": native_analysis["summary"]["session_id"],
              "exec_integrity": exec_analysis.get("integrity", {"status": "UNAVAILABLE"}),
              "host_tool_count": len(calls), "host_tools_with_typed_native_join": sum(bool(call["native_matches"]) for call in calls),
              "tool_calls": [{key: value for key, value in call.items() if key != "_output"} for call in calls],
              "patch_evidence": patch, "final_submission": submission,
              "new_session_outcome_observation": observation,
              "mental_causality": "UNVERIFIED", "automatic_strategy_attribution": "UNKNOWN",
              "limitations": ["Archive hashes are local consistency evidence, not external origin attestation.",
                              "Code-mode printed tool output proves typed-channel visibility, not untrusted claim truth.",
                              "Host patch polling is an upper bound on first observed source change; command writes may be unobserved.",
                              "Major-patch importance and internal causal influence are not inferred."]}
    with (destination / "trace_audit.json").open("xb") as output:
        output.write(json.dumps(redact(report), indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n")
    with (destination / "timeline.jsonl").open("xb") as output:
        for row in timeline:
            output.write(_canonical(redact(row)) + b"\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--expected-seal-sha256")
    parser.add_argument("--trusted-outcome-id")
    args = parser.parse_args(argv)
    try:
        result = audit_run(args.run_dir, args.output_dir, expected_seal_sha256=args.expected_seal_sha256,
                           trusted_outcome_id=args.trusted_outcome_id)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(json.dumps({"status": "ERROR", "error_type": type(error).__name__, "source_modified": False}))
        return 2
    print(json.dumps({"status": "AUDIT_WRITTEN", "run_id": result["run_id"],
                      "host_tool_count": result["host_tool_count"],
                      "typed_native_join_count": result["host_tools_with_typed_native_join"],
                      "outcome_observation": result["new_session_outcome_observation"]["status"],
                      "output_sha256": sha256((args.output_dir / "trace_audit.json").read_bytes()).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
