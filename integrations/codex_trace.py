"""Observe ``codex exec --json`` without inferring collaboration from prose.

The wire contract is the official Codex ``rust-v0.162.1`` exec_events.rs, not
the app-server protocol. In particular, exec emits ``collab_tool_call`` with
snake_case fields. This module does not start, schedule, or impersonate agents.

Callers keep the raw, redacted JSONL archive on the trusted host. References
identify its exact bytes, including each line's terminator. Unknown events stay
in the normalized archive. Tests using fabricated events are contract tests;
they are never evidence that an actual Codex session ran.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable

from integrations.agents import ExecutionTrace, utc_timestamp


TRACE_VERSION = "1.0.0"
UNAVAILABLE = "UNAVAILABLE"
EXEC_CONTRACT_SOURCE = (
    "https://raw.githubusercontent.com/openai/codex/rust-v0.162.1/"
    "codex-rs/exec/src/exec_events.rs"
)
REDACTED = "[REDACTED]"
_SECRET_KEYS = frozenset({
    "authorization", "proxyauthorization", "accesstoken", "refreshtoken",
    "idtoken", "apikey", "openaiapikey", "codexapikey",
    "password", "passwd", "secret", "clientsecret", "privatekey",
    "credential", "credentials", "cookie", "setcookie", "sessiontoken",
})
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:authorization|proxy_authorization|access_token|refresh_token|"
    r"id_token|api_key|openai_api_key|codex_api_key|password|client_secret|"
    r"private_key|session_token)\b\s*[:=]\s*)"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;}]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_API_KEY = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_EVENT_TYPES = frozenset({
    "thread.started", "turn.started", "turn.completed", "turn.failed",
    "item.started", "item.updated", "item.completed", "error",
})
_ITEM_TYPES = frozenset({
    "agent_message", "reasoning", "command_execution", "file_change",
    "mcp_tool_call", "collab_tool_call", "web_search", "todo_list", "error",
})
_COLLAB_TOOLS = frozenset({"spawn_agent", "send_input", "wait", "close_agent"})
_AGENT_STATUSES = frozenset({
    "pending_init", "running", "interrupted", "completed", "errored",
    "shutdown", "not_found",
})
_USAGE_FIELDS = (
    "input_tokens", "cached_input_tokens", "output_tokens",
    "cache_write_input_tokens", "reasoning_output_tokens",
)


def redact_text(text: str, *, secret_values: Iterable[str] = ()) -> str:
    """Remove known credential shapes; callers may also supply actual secrets.

    Pattern redaction cannot identify every arbitrary secret. The execution
    boundary must keep credentials out of participant tools in the first place.
    This helper neither reads identity files nor discovers host credentials.
    """
    result = text
    for secret in sorted(set(secret_values), key=len, reverse=True):
        if isinstance(secret, str) and secret:
            result = result.replace(secret, REDACTED)
    result = _BEARER.sub("Bearer " + REDACTED, result)
    result = _SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + REDACTED, result)
    result = _API_KEY.sub(REDACTED, result)
    return _JWT.sub(REDACTED, result)


def redact(value: Any, *, secret_values: Iterable[str] = ()) -> Any:
    """Return a recursively redacted copy of a JSON-compatible value."""
    secrets = tuple(secret_values)
    if isinstance(value, dict):
        return {
            key: REDACTED if re.sub(r"[^a-z0-9]", "", str(key).lower()) in _SECRET_KEYS
            else redact(item, secret_values=secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, secret_values=secrets) for item in value]
    if isinstance(value, str):
        return redact_text(value, secret_values=secrets)
    return value


def redact_jsonl(
    raw_path: Path | str,
    archive_path: Path | str,
    *,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Archive stdout after redaction, preserving malformed lines for diagnosis.

    The caller owns any temporary unredacted capture and its secure deletion.
    A malformed line stays malformed rather than becoming a fabricated event.
    Source and destination may coincide; bytes are read before any write.
    """
    raw_path, archive_path = Path(raw_path), Path(archive_path)
    original = raw_path.read_bytes()
    secrets = tuple(secret_values)
    lines = original.splitlines(keepends=True)
    archived: list[bytes] = []
    changed = 0
    malformed = 0
    for line in lines:
        terminator = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
        body = line[:-len(terminator)] if terminator else line
        try:
            value = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            malformed += 1
            cleaned = redact_text(body.decode("utf-8", errors="replace"), secret_values=secrets)
        else:
            cleaned_value = redact(value, secret_values=secrets)
            # Keep exact bytes when no sensitive value required redaction.
            if cleaned_value == value:
                archived.append(line)
                continue
            cleaned = json.dumps(cleaned_value, ensure_ascii=False, separators=(",", ":"))
        cleaned_line = cleaned.encode("utf-8") + terminator
        changed += cleaned_line != line
        archived.append(cleaned_line)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    content = b"".join(archived)
    archive_path.write_bytes(content)
    return {
        "path": str(archive_path), "sha256": sha256(content).hexdigest(),
        "original_sha256": sha256(original).hexdigest(),
        "original_bytes": len(original),
        "byte_identity": "EXACT" if original == content else "CREDENTIAL_REDACTED",
        "line_count": len(lines), "redacted_lines": changed,
        "malformed_lines": malformed, "policy": "credential_keys_and_patterns_v1",
    }


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_trace(
    raw_path: Path | str,
    trace_path: Path | str,
    run_id: str,
    *,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Normalize an archived exec stream and report only observed facts.

    ``collected_at`` is an optional caller-recorded archive collection timestamp,
    never an official event timestamp. Without it, timestamps describe parsing.
    The returned integrity status concerns evidence completeness; ``turn_status``
    separately describes whether the observed official turn completed or failed.
    Process exit, elapsed time, patch identity, and evaluation belong to callers.
    """
    if not _identifier(run_id):
        raise ValueError("run_id must be a non-empty string")
    raw_path, trace_path = Path(raw_path), Path(trace_path)
    if raw_path.absolute() == trace_path.absolute():
        raise ValueError("Trace destination must differ from raw event archive")
    content = raw_path.read_bytes()
    raw_lines = content.splitlines(keepends=True)
    errors: list[dict[str, Any]] = []
    runtime_errors: list[dict[str, Any]] = []
    startup_warnings: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    thread_id: str | None = None
    active_turn = False
    turns_started = 0
    turns_finished = 0
    turn_status = UNAVAILABLE
    pending_items: dict[str, str] = {}
    completed_item_ids: set[str] = set()
    item_counts: Counter[str] = Counter()
    unknown_events: Counter[str] = Counter()
    unknown_items: Counter[str] = Counter()
    usage_records: list[dict[str, Any]] = []
    agents: dict[str, dict[str, Any]] = {}
    structured_collab_count = 0
    timestamp_source = "archive_collection_utc" if collected_at else "trace_parse_utc"
    parse_timestamp = collected_at or utc_timestamp()

    def problem(code: str, line: int | None, message: str) -> None:
        errors.append({"code": code, "line": line, "message": message})

    for line_number, line in enumerate(raw_lines, 1):
        if not line.strip():
            continue
        reference = {
            "path": str(raw_path), "line": line_number,
            "sha256": sha256(line).hexdigest(),
        }
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            problem("INVALID_JSON", line_number, "Raw line is not a valid JSON event")
            event = {"type": "trace.invalid_line", "text": line.decode("utf-8", errors="replace")}
        if not isinstance(event, dict):
            problem("INVALID_EVENT", line_number, "Event must be a JSON object")
            event = {"type": "trace.invalid_event", "value": event}
        event_type = event.get("type")
        if not _identifier(event_type):
            problem("MISSING_EVENT_TYPE", line_number, "Event type is missing or invalid")
            event_type = "trace.invalid_event"
        elif event_type not in _EVENT_TYPES and not event_type.startswith("trace."):
            unknown_events[event_type] += 1

        observation = ExecutionTrace(
            run_id=run_id,
            source="codex.exec.jsonl",
            event_type=event_type,
            payload={
                "event": redact(event), "raw_reference": reference,
                "timestamp_source": timestamp_source,
                "official_timestamp": UNAVAILABLE,
                "thread_id": thread_id or UNAVAILABLE,
            },
            timestamp=parse_timestamp,
        ).to_dict()
        normalized.append(observation)

        if event_type == "thread.started":
            if thread_id is not None:
                problem("MULTIPLE_THREADS", line_number, "An exec invocation must start one fresh thread")
            elif not _identifier(event.get("thread_id")):
                problem("INVALID_THREAD_ID", line_number, "thread.started lacks a thread_id")
            else:
                thread_id = event["thread_id"]
                observation["payload"]["thread_id"] = thread_id
        elif event_type == "turn.started":
            if thread_id is None:
                problem("TURN_BEFORE_THREAD", line_number, "Turn started before a thread identifier was observed")
            if active_turn:
                problem("OVERLAPPING_TURNS", line_number, "Turn started before the previous turn ended")
            active_turn = True
            turns_started += 1
        elif event_type in {"turn.completed", "turn.failed"}:
            if not active_turn:
                problem("TURN_WITHOUT_START", line_number, "Terminal turn event lacks a turn.started")
            if pending_items:
                problem("TURN_ENDED_WITH_PENDING_ITEMS", line_number, "Turn ended before started items completed")
            active_turn = False
            turns_finished += 1
            turn_status = "COMPLETED" if event_type == "turn.completed" else "FAILED"
            if event_type == "turn.failed":
                runtime_errors.append({"error": redact(event.get("error")), "raw_reference": reference})
            else:
                usage = event.get("usage")
                required = _USAGE_FIELDS[:3]
                valid = isinstance(usage, dict) and all(
                    key in usage and type(usage[key]) is int and usage[key] >= 0
                    for key in required
                )
                if valid:
                    valid = all(
                        key not in usage or (type(usage[key]) is int and usage[key] >= 0)
                        for key in _USAGE_FIELDS
                    )
                if not valid:
                    problem("INVALID_USAGE", line_number, "turn.completed lacks valid official token usage")
                else:
                    usage_records.append({"usage": {key: usage[key] for key in _USAGE_FIELDS if key in usage}, "raw_reference": reference})
        elif event_type == "error":
            runtime_errors.append({"error": redact(event.get("message")), "raw_reference": reference})
        elif event_type.startswith("item."):
            item = event.get("item")
            if not isinstance(item, dict) or not _identifier(item.get("id")) or not _identifier(item.get("type")):
                problem("INVALID_ITEM", line_number, "Item event lacks a typed item and identifier")
                continue
            item_id, item_type = item["id"], item["type"]
            # The real 0.162.1 CLI can emit a non-fatal ErrorItem immediately
            # after thread.started, before turn.started (e.g. model metadata
            # fallback). This does not permit tools or duplicate item lifecycles
            # outside a turn, and the warning remains an observed raw event.
            startup_warning = (
                not active_turn and thread_id is not None and turns_started == 0
                and event_type == "item.completed" and item_type == "error"
                and _identifier(item.get("message")) and not pending_items
                and item_id not in completed_item_ids
            )
            if not active_turn:
                if startup_warning:
                    observation["payload"]["classification"] = "startup_warning"
                    startup_warnings.append({
                        "item_id": item_id, "message": redact(item["message"]),
                        "raw_reference": reference,
                    })
                else:
                    problem("ITEM_OUTSIDE_TURN", line_number, "Item event occurred outside an active turn")
            if item_type not in _ITEM_TYPES:
                unknown_items[item_type] += 1
            if event_type == "item.started":
                if item_id in pending_items or item_id in completed_item_ids:
                    problem("DUPLICATE_ITEM_START", line_number, "Item started more than once")
                pending_items[item_id] = item_type
            elif event_type == "item.completed":
                if item_id in completed_item_ids:
                    problem("DUPLICATE_ITEM_COMPLETION", line_number, "Item completed more than once")
                    continue
                if item_id in pending_items and pending_items[item_id] != item_type:
                    problem("ITEM_TYPE_CHANGED", line_number, "An item's type changed before completion")
                pending_items.pop(item_id, None)
                completed_item_ids.add(item_id)
                item_counts[item_type] += 1
            if item_type != "collab_tool_call":
                continue
            # Camel-case app-server items are unknown above, never reinterpreted.
            receivers = item.get("receiver_thread_ids")
            states = item.get("agents_states")
            sender = item.get("sender_thread_id")
            prompt = item.get("prompt")
            valid = (
                _identifier(item.get("tool"))
                and item["tool"] in _COLLAB_TOOLS
                and _identifier(item.get("status"))
                and item["status"] in {"in_progress", "completed", "failed"}
                and _identifier(sender)
                and isinstance(receivers, list)
                and all(_identifier(receiver) and receiver != sender for receiver in receivers)
                and len(receivers) == len(set(receivers))
                and isinstance(states, dict)
                and (prompt is None or isinstance(prompt, str))
            )
            if valid:
                valid = all(
                    _identifier(receiver) and isinstance(state, dict)
                    and _identifier(state.get("status"))
                    and state["status"] in _AGENT_STATUSES
                    and (state.get("message") is None or isinstance(state.get("message"), str))
                    for receiver, state in states.items()
                )
            if not valid:
                problem("INVALID_COLLAB_ITEM", line_number, "Malformed exec collab_tool_call fields")
                continue
            if sender != thread_id:
                problem("COLLAB_PARENT_MISMATCH", line_number, "Collaboration sender does not match the observed exec thread")
                continue
            structured_collab_count += 1
            if event_type != "item.completed" or item["status"] != "completed":
                continue
            if item["tool"] == "spawn_agent":
                if not receivers:
                    problem("SPAWN_WITHOUT_RECEIVER", line_number, "Completed spawn has no child identifier")
                for receiver in receivers:
                    if receiver in agents:
                        problem("DUPLICATE_AGENT_SPAWN", line_number, "Child identifier was spawned more than once")
                        continue
                    agents[receiver] = {
                        "thread_id": receiver, "parent_thread_id": sender,
                        "task": prompt if prompt and prompt.strip() else UNAVAILABLE,
                        "status": "SPAWNED", "spawn_reference": reference,
                        "completion_reference": UNAVAILABLE,
                        "completion_message": UNAVAILABLE,
                        "observations": [],
                    }
            for receiver in receivers:
                if receiver not in agents or receiver not in states:
                    continue
                state = states[receiver]
                agent = agents[receiver]
                agent["observations"].append({"tool": item["tool"], "state": redact(state), "raw_reference": reference})
                agent["status"] = state["status"].upper()
                if state["status"] == "completed":
                    agent["completion_reference"] = reference
                    agent["completion_message"] = redact(state.get("message")) if state.get("message") else UNAVAILABLE

    if thread_id is None:
        problem("MISSING_THREAD", None, "No thread.started identifier was observed")
    if turns_started == 0:
        problem("MISSING_TURN", None, "No turn.started event was observed")
    if active_turn or turns_started != turns_finished:
        problem("UNFINISHED_TURN", None, "Started and terminal turn events are incomplete")
    if pending_items:
        problem("UNFINISHED_ITEMS", None, "Items still lack completion: " + ", ".join(sorted(pending_items)))
    totals = {
        key: sum(record["usage"].get(key, 0) for record in usage_records)
        for key in _USAGE_FIELDS if any(key in record["usage"] for record in usage_records)
    }
    agent_list = list(agents.values())
    completed = [agent for agent in agent_list if agent["completion_reference"] != UNAVAILABLE]
    verified = [agent for agent in completed if agent["task"] != UNAVAILABLE and agent["completion_message"] != UNAVAILABLE]
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_content = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in normalized).encode("utf-8")
    trace_path.write_bytes(trace_content)
    return {
        "schema_version": TRACE_VERSION, "run_id": run_id,
        "source": "codex.exec.jsonl", "contract_source": EXEC_CONTRACT_SOURCE,
        "thread_id": thread_id or UNAVAILABLE, "session_id": UNAVAILABLE,
        "event_count": len(normalized), "raw_line_count": len(raw_lines),
        "raw_events_path": str(raw_path), "raw_events_sha256": sha256(content).hexdigest(),
        "trace_path": str(trace_path), "trace_sha256": sha256(trace_content).hexdigest(),
        "timestamp_source": timestamp_source,
        "turn_status": turn_status,
        "turns_started": turns_started, "turns_finished": turns_finished,
        "usage": {
            "availability": "AVAILABLE" if usage_records else UNAVAILABLE,
            "totals": totals if usage_records else UNAVAILABLE,
            "records": usage_records, "scope": "official_turn_completed_events",
        },
        "subagents": {
            "availability": "AVAILABLE" if structured_collab_count else UNAVAILABLE,
            "spawned_count": len(agent_list), "completed_count": len(completed),
            "verified_count": len(verified), "agents": agent_list,
            "evidence_policy": "structured_exec_spawn_and_completed_agent_state_with_task_and_message",
        },
        "completed_items": dict(item_counts), "runtime_errors": runtime_errors,
        "startup_warnings": startup_warnings,
        "integrity": {
            "status": "INCOMPLETE" if errors else "COMPLETE", "errors": errors,
            "unknown_events": dict(unknown_events), "unknown_item_types": dict(unknown_items),
        },
    }
