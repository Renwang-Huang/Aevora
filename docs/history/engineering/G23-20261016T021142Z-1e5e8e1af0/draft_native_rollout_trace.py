"""Observe archived official native rollouts, never infer agents from prose.

Contract: openai/codex rust-v0.162.1 protocol/{protocol,items,models}.rs.
Input files are this run's *already redacted* host archive. Local hashes verify
archive consistency; they are not independent attestation of runtime origin.
Child files contain inherited parent history. Only their first own session_meta
and new turns with attribution to their actual parent are counted. Encrypted
task content is kept UNAVAILABLE; no encrypted model arguments are decoded.
Raw line hashes include the original newline, as in codex_trace.parse_trace.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import stat
from typing import Any

from integrations.codex_trace import UNAVAILABLE, redact

CONTRACT_VERSION = "codex-rust-v0.162.1-native-rollout-2"
CONTRACT_SOURCE = "https://github.com/openai/codex/tree/rust-v0.162.1/codex-rs/protocol/src"
_USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                 "output_tokens", "reasoning_output_tokens", "total_tokens")


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _text(content: Any, *, preserve_whitespace: bool = False) -> str | None:
    if not isinstance(content, list) or any(
        isinstance(part, dict) and part.get("type") == "encrypted_content" for part in content
    ):
        return None
    values = [part.get("text") for part in content if isinstance(part, dict)
              and part.get("type") in ("text", "Text", "input_text", "output_text")]
    text = "\n".join(value for value in values if isinstance(value, str))
    if not text.strip():
        return None
    # Typed final/completion/receipt correlation is an exact-text contract.
    # Stripping a genuine final while preserving task_complete's text creates
    # false negatives; normalizing both would hide real content differences.
    return text if preserve_whitespace else text.strip()


def _usage(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {key: value[key] for key in _USAGE_FIELDS if key in value}
    return result if result and all(type(v) is int and v >= 0 for v in result.values()) else None


def analyze_native_rollouts(
    run_id: str, archive: Path | str, native_rollouts: dict, *,
    expected_parent_thread_id: str | None = None,
) -> dict:
    """Return ``{summary, events}``; this function does not mutate the archive.

    ``verified_count`` requires matched native spawn/session metadata, a real
    parent task delivery, child execution, successful task_complete with a
    separately recorded final answer, and a structured parent completion receipt.
    Encrypted delivered tasks can prove delivery but cannot prove their text or
    distinct semantics; ``task_content`` remains UNAVAILABLE in that case.
    All integrity failures close verification, while partial facts remain visible.
    """
    archive = Path(archive).absolute()
    errors: list[dict] = []
    events: list[dict] = []
    threads: dict[str, dict] = {}
    records = native_rollouts.get("files", []) if isinstance(native_rollouts, dict) else []
    if archive.name != run_id:
        errors.append({"code": "RUN_ID_MISMATCH"})
    if not isinstance(records, list) or len(records) > 1000:
        records = []
        errors.append({"code": "FILE_BUDGET_OR_SCHEMA"})
    root = archive / "artifacts" / "native_rollouts"
    total = 0

    def observe(thread: str, kind: str, row: dict, payload: dict) -> dict:
        try:
            safe_payload = redact(payload)
        except RecursionError:
            errors.append({"code": "NESTING_BUDGET", "raw_reference": row["reference"]})
            safe_payload = {"availability": UNAVAILABLE, "reason": "JSON nesting budget exceeded"}
        result = {"run_id": run_id, "source": "codex.native.rollout",
                  "event_type": kind, "timestamp": row["event"].get("timestamp", UNAVAILABLE),
                  "payload": {"thread_id": thread, "event": safe_payload,
                              "raw_reference": row["reference"],
                              "timestamp_source": "official_rollout_envelope"}}
        events.append(result)
        return {"raw_reference": row["reference"], "timestamp": result["timestamp"]}

    for record in records:
        try:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise ValueError("Invalid file record")
            path = Path(record["path"])
            if not path.is_absolute():
                path = archive / path
            relative = path.relative_to(root)
            if ".." in relative.parts:
                raise ValueError("Parent traversal")
            for parent in [root, *[root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts))]]:
                if parent.is_symlink() or not parent.is_dir():
                    raise ValueError("Directory link or missing archive root")
            mode = path.lstat()
            if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                raise ValueError("Not a regular single-link file")
            total += mode.st_size
            if mode.st_size > 64 * 1024**2 or total > 128 * 1024**2:
                raise ValueError("File byte budget")
            data = path.read_bytes()
            digest = sha256(data).hexdigest()
            if record.get("sha256") != digest:
                raise ValueError("Archived SHA256 mismatch or unavailable")
            rows = []
            for line, raw in enumerate(data.splitlines(keepends=True), 1):
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw)
                    if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
                        raise ValueError("Invalid event shape")
                    if not isinstance(event.get("timestamp"), str) or not event["timestamp"]:
                        raise ValueError("Official timestamp unavailable")
                    for key in ("thread_id", "turn_id"):
                        value = event["payload"].get(key)
                        if value is not None and not isinstance(value, str):
                            raise ValueError("Invalid thread/turn identifier")
                except (ValueError, UnicodeDecodeError, RecursionError):
                    errors.append({"code": "INVALID_EVENT", "path": str(path), "line": line})
                    continue
                rows.append({"event": event, "reference": {"path": str(path), "line": line,
                             "sha256": sha256(raw).hexdigest()}})
            if not rows or rows[0]["event"].get("type") != "session_meta":
                raise ValueError("First own session_meta unavailable")
            meta = rows[0]["event"]["payload"]
            identifier = meta.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in threads:
                raise ValueError("Missing or duplicated own thread identity")
            for key in ("parent_thread_id", "session_id", "agent_path"):
                if meta.get(key) is not None and not isinstance(meta[key], str):
                    raise ValueError("Invalid own metadata identifier")
            threads[identifier] = {"meta": meta, "meta_row": rows[0], "rows": rows,
                                   "sha256": digest, "path": str(path)}
        except (OSError, ValueError, RuntimeError) as error:
            errors.append({"code": "INVALID_ARCHIVED_FILE", "message": str(error),
                           "path": record.get("path", UNAVAILABLE) if isinstance(record, dict) else UNAVAILABLE})

    roots = [key for key, value in threads.items() if not value["meta"].get("parent_thread_id")]
    lead = expected_parent_thread_id if expected_parent_thread_id not in (None, UNAVAILABLE) else (
        roots[0] if len(roots) == 1 else None)
    if lead not in roots:
        errors.append({"code": "ROOT_THREAD_UNAVAILABLE_OR_AMBIGUOUS"})
        lead = None
    if lead:
        for identifier, thread in threads.items():
            if thread["meta"].get("session_id") != lead:
                errors.append({"code": "SESSION_ID_MISMATCH", "thread_id": identifier})

    # First strip copied history. A child turn must point at an actual new turn
    # of the matched parent, not at the inherited lead task_started record.
    own_rows: dict[str, list] = {}
    own_turns: dict[str, set] = {}
    pending = set(threads)
    while pending:
        advanced = False
        for identifier in sorted(pending):
            thread = threads[identifier]
            parent = thread["meta"].get("parent_thread_id")
            if parent and parent not in own_turns:
                continue
            turns: set[str] = set()
            accepted = []
            active = None
            for row in thread["rows"][1:]:
                e = row["event"]; p = e["payload"]
                if e.get("type") == "session_meta":
                    continue
                if e.get("type") == "event_msg" and p.get("type") == "task_started":
                    turn = p.get("turn_id")
                    attribution = p.get("turn_attribution", {})
                    valid = isinstance(turn, str) and bool(turn)
                    if parent:
                        valid = valid and isinstance(attribution, dict) and (
                            attribution.get("parent_turn_id") in own_turns[parent]
                            and turn not in own_turns[parent])
                    active = turn if valid else None
                    if valid:
                        turns.add(turn)
                if active is None:
                    continue
                if p.get("thread_id") not in (None, identifier) or p.get("turn_id") not in (None, active):
                    continue
                row = {**row, "own_turn_id": active}
                accepted.append(row)
            own_rows[identifier] = accepted
            own_turns[identifier] = turns
            pending.remove(identifier)
            advanced = True
        if not advanced:
            for identifier in sorted(pending):
                errors.append({"code": "PARENT_CHAIN_UNRESOLVED", "thread_id": identifier})
            break

    starts: dict[str, dict] = {}
    collab_deliveries: dict[str, list] = {}
    facts: dict[str, dict] = {}
    for identifier, rows in own_rows.items():
        thread = threads[identifier]; meta = thread["meta"]
        meta_ref = observe(identifier, "native.session_meta", thread["meta_row"], {
            key: meta.get(key, UNAVAILABLE) for key in (
                "id", "parent_thread_id", "session_id", "agent_path", "source", "cli_version")})
        fact = {"task_deliveries": [], "finals": [], "completions": [], "receipts": [],
                "tools": Counter(), "executed_tools": 0, "usage": [], "meta_reference": meta_ref}
        facts[identifier] = fact
        communication = None
        for row in rows:
            e = row["event"]; p = e["payload"]; kind = e.get("type")
            subtype = p.get("type")
            if kind == "inter_agent_communication_metadata":
                communication = (p, row)
                continue
            if kind == "response_item" and subtype == "agent_message":
                message_turn = _dict(p.get("internal_chat_message_metadata_passthrough")).get("turn_id")
                if message_turn is not None and message_turn != row["own_turn_id"]:
                    communication = None
                    continue
                author, recipient = p.get("author"), p.get("recipient")
                parent = meta.get("parent_thread_id")
                parent_path = threads.get(parent, {}).get("meta", {}).get("agent_path") or "/root"
                own_path = meta.get("agent_path") or "/root"
                content_parts = p.get("content") if isinstance(p.get("content"), list) else []
                encrypted = any(isinstance(part, dict) and part.get("type") == "encrypted_content"
                    and isinstance(part.get("encrypted_content"), str) and part["encrypted_content"]
                    for part in content_parts)
                envelope = "".join(part.get("text", "") for part in content_parts if isinstance(part, dict)
                    and part.get("type") == "input_text" and isinstance(part.get("text"), str))
                plaintext = _text(p.get("content"))
                if communication and communication[0].get("trigger_turn") is True and parent and (
                    author == parent_path and recipient == own_path
                ) and (plaintext or (encrypted and envelope.startswith(
                    f"Message Type: NEW_TASK\nTask name: {recipient}\nSender: {author}\nPayload:\n"))):
                    content = plaintext
                    ref = observe(identifier, "native.task_delivery", row, {
                        "author": author, "recipient": recipient, "message_id": p.get("id"),
                        "turn_id": row["own_turn_id"], "task_content": content or UNAVAILABLE,
                        "task_content_reason": "plaintext" if content else "encrypted_or_unavailable"})
                    fact["task_deliveries"].append({**ref, "turn_id": row["own_turn_id"],
                        "task_content": content or UNAVAILABLE,
                        "communication_reference": communication[1]["reference"]})
                elif communication and communication[0].get("trigger_turn") is False:
                    # This is official typed AgentMessage delivery. Completion
                    # semantics are checked against the exact runtime envelope,
                    # not guessed from a natural-language report about agents.
                    content = _text(p.get("content"), preserve_whitespace=True)
                    prefix = f"Message Type: FINAL_ANSWER\nTask name: {recipient}\nSender: {author}\nPayload:\n"
                    if isinstance(content, str) and content.startswith(prefix):
                        ref = observe(identifier, "native.parent_receipt", row, {
                            "author": author, "recipient": recipient, "message_id": p.get("id"),
                            "content": content, "turn_id": row["own_turn_id"]})
                        fact["receipts"].append({**ref, "author": author, "recipient": recipient,
                            "content": content, "communication_reference": communication[1]["reference"]})
                communication = None
            elif kind == "response_item" and subtype == "message" and p.get("role") == "user" and meta.get("parent_thread_id"):
                parent = meta["parent_thread_id"]
                text = _text(p.get("content"), preserve_whitespace=True)
                turn = _dict(p.get("internal_chat_message_metadata_passthrough")).get("turn_id")
                # Legacy official collaboration delivers a user message in the
                # child's new attributed turn. Exact plaintext must match the
                # parent's typed spawn/send_input prompt, never nearby prose.
                candidates = collab_deliveries.get(identifier, [])
                match = next((d for d in candidates if d["parent"] == parent and d["prompt"] == text), None)
                if match and turn == row["own_turn_id"]:
                    ref = observe(identifier, "native.legacy_task_delivery", row,
                                  dict(parent_thread_id=parent, turn_id=turn, content=text))
                    fact["task_deliveries"].append({**ref, "turn_id":turn,
                        "task_content":text, "communication_reference":match["reference"]})
            elif kind == "event_msg" and subtype == "item_completed" and p.get("thread_id") == identifier:
                item = p.get("item", {})
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "SubAgentActivity":
                    ref = observe(identifier, "native.subagent_activity", row, item)
                    child = item.get("agent_thread_id")
                    if item.get("kind") == "started" and isinstance(child, str):
                        if child in starts:
                            errors.append({"code": "DUPLICATE_SPAWN", "thread_id": child})
                        starts[child] = {**ref, "parent_thread_id": identifier, "item": item}
                elif item_type == "CollabAgentToolCall":
                    ref = observe(identifier, "native.CollabAgentToolCall", row, item)
                    if item.get("sender_thread_id") != identifier or item.get("status") != "completed":
                        continue
                    receivers = item.get("receiver_thread_ids", [])
                    prompt = item.get("prompt")
                    if item.get("tool") == "spawn_agent":
                        if len(receivers) != 1 or not isinstance(receivers[0], str):
                            errors.append({"code":"INVALID_TYPED_COLLAB_SPAWN", "thread_id":identifier})
                            continue
                        child = receivers[0]
                        if child in starts:
                            errors.append({"code":"DUPLICATE_SPAWN", "thread_id":child})
                        starts[child] = {**ref, "parent_thread_id":identifier, "item":item,
                                         "protocol_variant":"CollabAgentToolCall"}
                    if item.get("tool") in {"spawn_agent", "send_input"} and isinstance(prompt, str):
                        for child in receivers:
                            collab_deliveries.setdefault(child, []).append(
                                dict(parent=identifier, prompt=prompt, reference=row["reference"]))
                    states = item.get("agents_states", {})
                    if item.get("tool") in {"wait", "close_agent"} and isinstance(states, dict):
                        for child, state in states.items():
                            if isinstance(state, dict) and isinstance(state.get("completed"), str):
                                fact["receipts"].append({**ref, "actor_thread_id":child,
                                    "content":state["completed"], "native_completed_state":True})
                elif item_type in ("CommandExecution", "FileChange"):
                    fact["tools"][item_type] += 1
                    if item.get("status") == "completed":
                        fact["executed_tools"] += 1
                    observe(identifier, "native." + item_type, row, item)
                elif item_type == "McpToolCall":
                    fact["tools"][item_type] += 1
                    if item.get("status") == "completed" and item.get("error") is None:
                        fact["executed_tools"] += 1
                    observe(identifier, "native.McpToolCall", row,
                            {**item, "own_turn_id": row["own_turn_id"]})
                elif item_type == "AgentMessage":
                    content = _text(item.get("content"), preserve_whitespace=True)
                    if content:
                        fact["finals"].append({"text": content, "phase": item.get("phase"),
                            "turn_id": row["own_turn_id"], "row": row})
            elif kind == "response_item" and subtype in ("function_call", "custom_tool_call"):
                fact["tools"][subtype] += 1
                observe(identifier, "native.response_tool_call", row, {
                    key: p.get(key, UNAVAILABLE) for key in ("type", "name", "call_id", "status")})
            elif kind == "response_item" and subtype == "message" and p.get("role") == "assistant":
                content = _text(p.get("content"), preserve_whitespace=True)
                if content:
                    fact["finals"].append({"text": content, "phase": p.get("phase"),
                        "turn_id": row["own_turn_id"], "row": row})
            elif kind == "event_msg" and subtype == "task_complete":
                ref = observe(identifier, "native.task_complete", row, p)
                fact["completions"].append({**ref, "payload": p})
            elif kind == "token_usage_record" and p.get("thread_id") == identifier:
                usage = _usage(p.get("usage"))
                if usage and isinstance(p.get("response_id"), str):
                    ref = observe(identifier, "native.token_usage_record", row, p)
                    fact["usage"].append({**ref, "response_id": p["response_id"], "usage": usage,
                        "thread_token_usage": _usage(p.get("thread_token_usage")) or UNAVAILABLE})

    agents = []
    for child, spawn in sorted(starts.items()):
        thread = threads.get(child); fact = facts.get(child)
        parent = spawn["parent_thread_id"]
        meta = thread["meta"] if thread else {}
        source = _dict(_dict(_dict(meta.get("source")).get("subagent")).get("thread_spawn"))
        matched = bool(thread and fact and meta.get("parent_thread_id") == parent
            and isinstance(source, dict) and source.get("parent_thread_id") == parent
            and source.get("agent_path") == meta.get("agent_path") == spawn["item"].get("agent_path"))
        completion = final = receipt = None
        if matched:
            for candidate in fact["completions"]:
                p = candidate["payload"]
                # Official TurnCompleteEvent.error is Option with
                # skip_serializing_if=None: omission and null both mean None.
                if p.get("error") is not None or not isinstance(p.get("last_agent_message"), str):
                    continue
                for message in fact["finals"]:
                    if message["turn_id"] == p.get("turn_id") and message["text"] == p["last_agent_message"] and (
                        message["phase"] in (None, "final_answer")
                    ):
                        completion = candidate
                        final = observe(child, "native.final_answer", message["row"], {
                            "text": message["text"], "phase": message["phase"], "turn_id": message["turn_id"]})
                        break
            if completion and spawn.get("protocol_variant") == "CollabAgentToolCall":
                receipt = next((candidate for candidate in facts[parent]["receipts"]
                    if candidate.get("actor_thread_id") == child
                    and candidate.get("native_completed_state") is True
                    and candidate["content"] == completion["payload"]["last_agent_message"]), None)
            elif completion:
                recipient = threads[parent]["meta"].get("agent_path") or "/root"
                expected_receipt = (
                    f"Message Type: FINAL_ANSWER\nTask name: {recipient}\n"
                    f"Sender: {meta.get('agent_path')}\nPayload:\n"
                    + completion["payload"]["last_agent_message"]
                )
                for candidate in facts[parent]["receipts"]:
                    if (candidate.get("author") == meta.get("agent_path")
                        and candidate.get("recipient") == recipient
                        and candidate["content"] == expected_receipt):
                        receipt = candidate
                        break
            else:
                receipt = next((candidate for candidate in facts[parent]["receipts"]
                    if candidate.get("author") == meta.get("agent_path") and candidate.get("recipient") == (
                        threads[parent]["meta"].get("agent_path") or "/root")), None)
        delivery = next((item for item in fact["task_deliveries"]
            if not completion or item["turn_id"] == completion["payload"].get("turn_id")), None) if matched else None
        executed = bool(matched and fact["executed_tools"])
        verified = bool(matched and delivery and executed and completion and final and receipt and not errors)
        agents.append({"agent_id": child, "parent_thread_id": parent,
            "agent_path": spawn["item"].get("agent_path", UNAVAILABLE), "spawn": spawn,
            "session_matched": matched, "task_delivery": delivery or UNAVAILABLE,
            "task": delivery["task_content"] if delivery else UNAVAILABLE,
            "execution_verified": executed,
            "completed": bool(completion), "parent_receipt": receipt or UNAVAILABLE,
            "completion": completion or UNAVAILABLE, "final_answer": final or UNAVAILABLE,
            "verified": verified, "tools": dict(fact["tools"]) if fact else {},
            "usage": fact["usage"] if fact else UNAVAILABLE,
            "errors": [p["payload"]["error"] for p in fact["completions"]
                       if p["payload"].get("error") is not None] if fact else []})
    usage = []
    seen = set()
    for identifier, fact in facts.items():
        for record in fact["usage"]:
            key = (identifier, record["response_id"])
            if key in seen:
                errors.append({"code": "DUPLICATE_USAGE_RESPONSE", "thread_id": identifier})
                continue
            seen.add(key)
            usage.append({"thread_id": identifier, **record})
    if errors:
        for agent in agents:
            agent["verified"] = False
    totals = dict(Counter({key: sum(record["usage"].get(key, 0) for record in usage)
                          for key in _USAGE_FIELDS})) if usage else UNAVAILABLE
    summary = {"run_id": run_id, "source": "codex.native.rollout", "schema_version": CONTRACT_VERSION,
        "contract_source": CONTRACT_SOURCE, "thread_id": lead or UNAVAILABLE,
        "session_id": lead or UNAVAILABLE, "event_count": len(events),
        "subagents": {"availability": "AVAILABLE" if starts else UNAVAILABLE,
            "spawned_count": len(agents), "completed_count": sum(a["completed"] for a in agents),
            "parent_receipt_count": sum(a["parent_receipt"] != UNAVAILABLE for a in agents),
            "verified_count": sum(a["verified"] for a in agents), "agents": agents,
            "task_plaintext_count": sum(a["task"] != UNAVAILABLE for a in agents),
            "policy": "matched_native_spawn_session_task_execution_completion_final_and_parent_receipt"},
        "usage": {"availability": "AVAILABLE" if usage else UNAVAILABLE, "totals": totals,
                  "records": usage, "scope": "deduplicated_per_response_usage_not_cumulative_counters"},
        "integrity": {"status": "INCOMPLETE" if errors else "COMPLETE", "errors": errors},
        "origin_attestation": "UNAVAILABLE; host-collected local archive, not external attestation"}
    events.sort(key=lambda value: (str(value["timestamp"]), value["payload"]["raw_reference"]["path"],
                                   value["payload"]["raw_reference"]["line"]))
    return {"summary": summary, "events": events}
