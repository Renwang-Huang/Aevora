"""Reconcile native exec output with the official session rollout evidence.

`codex exec --json` in the pinned 0.163.0 binary does not project a completed
`spawn_agent` call into `collab_tool_call`. The session rollout remains the
authoritative local record for the typed function call, child session
parentage, child terminal state, and parent receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from audit import E, write


PROBES = (
    "native_probe_v2",
    "native_probe_v2_agents_enabled",
    "native_probe_v1_agents_enabled",
    "native_probe_v2_deliver_message",
    "native_probe_v2_fork_all",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def meta(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("type") == "session_meta":
            return event.get("payload", {})
    return {}


def session_files(probe: Path) -> list[Path]:
    return sorted((probe / "codex_home" / "sessions").rglob("*.jsonl"))


def text_parts(content: Any) -> dict[str, Any]:
    result = {"input_text": [], "encrypted_content": [], "other": []}
    if not isinstance(content, list):
        return result
    for part in content:
        if not isinstance(part, dict):
            continue
        if "input_text" in part:
            result["input_text"].append(part.get("input_text"))
        elif "encrypted_content" in part:
            result["encrypted_content"].append(part.get("encrypted_content"))
        elif "text" in part:
            result["other"].append(part.get("text"))
        elif "output_text" in part:
            result["other"].append(part.get("output_text"))
    return result


def analyze_probe(probe: Path) -> dict[str, Any]:
    raw_result = probe / "RESULT.json"
    stdout_path = probe / "stdout.jsonl"
    stderr_path = probe / "stderr.log"
    stdout_events = read_jsonl(stdout_path) if stdout_path.is_file() else []
    root_id = next(
        (
            event.get("thread_id")
            for event in stdout_events
            if event.get("type") == "thread.started"
        ),
        None,
    )
    sessions = []
    for path in session_files(probe):
        events = read_jsonl(path)
        session_meta = meta(events)
        sessions.append({
            "path": str(path),
            "sha256": sha(path),
            "meta": session_meta,
            "events": events,
        })
    root = next((item for item in sessions if item["meta"].get("id") == root_id), None)
    direct_children = [
        item for item in sessions
        if root_id and item["meta"].get("parent_thread_id") == root_id
    ]
    descendants = [
        item for item in sessions
        if root_id and item["meta"].get("parent_thread_id") != root_id
        and item is not root
    ]
    spawn_calls = []
    wait_calls = []
    send_calls = []
    if root:
        for event in root["events"]:
            payload = event.get("payload", {})
            if event.get("type") != "response_item" or payload.get("type") != "function_call":
                continue
            record = {
                "name": payload.get("name"),
                "call_id": payload.get("call_id"),
                "arguments": payload.get("arguments"),
                "ordinal": event.get("ordinal"),
            }
            if record["name"] == "spawn_agent":
                spawn_calls.append(record)
            elif record["name"] in {"wait", "wait_agent"}:
                wait_calls.append(record)
            elif record["name"] == "send_message":
                send_calls.append(record)
    exec_collab = [
        event.get("item", {})
        for event in stdout_events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "collab_tool_call"
    ]
    child_records = []
    for child in direct_children:
        task_messages = []
        final_messages = []
        response_ids = []
        terminal = []
        for event in child["events"]:
            payload = event.get("payload", {})
            if event.get("type") == "response_item" and payload.get("type") == "agent_message":
                if payload.get("author") == "/root":
                    task_messages.append(text_parts(payload.get("content")))
            if event.get("type") == "response_item" and payload.get("type") == "message":
                parts = text_parts(payload.get("content"))
                if payload.get("role") == "assistant":
                    final_messages.append(parts)
            if event.get("type") == "event_msg" and payload.get("type") == "task_complete":
                terminal.append({
                    "last_agent_message": payload.get("last_agent_message"),
                    "turn_id": payload.get("turn_id"),
                    "completed_at": payload.get("completed_at"),
                })
            if event.get("type") == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item", {})
                if item.get("type") == "TokenUsageRecord" or "response_id" in item:
                    response_ids.append(item.get("response_id"))
            if payload.get("type") == "token_usage_record":
                response_ids.append(payload.get("response_id"))
        visible_task = any(
            any((part or "").strip() for part in item["input_text"][1:])
            for item in task_messages
        )
        final_text = "\n".join(
            part
            for item in final_messages
            for part in item["other"]
            if part
        )
        terminal_text = "\n".join(
            item.get("last_agent_message") or ""
            for item in terminal
        )
        task_output_marker = "CHILD_OK" in (final_text + "\n" + terminal_text)
        task_delivery = (
            "PASS_ENCRYPTED_MESSAGE_TO_CHILD"
            if task_output_marker
            else "VISIBLE_TASK"
            if visible_task
            else "TASK_PAYLOAD_NOT_VISIBLE"
        )
        child_records.append({
            "thread_id": child["meta"].get("id"),
            "parent_thread_id": child["meta"].get("parent_thread_id"),
            "thread_source": child["meta"].get("thread_source"),
            "source": child["meta"].get("source"),
            "agent_path": child["meta"].get("agent_path"),
            "session_sha256": child["sha256"],
            "task_messages": task_messages,
            "task_payload_visible": visible_task,
            "task_output_marker": task_output_marker,
            "task_delivery": task_delivery,
            "final_text": final_text,
            "terminal_events": terminal,
            "provider_response_ids": sorted(set(item for item in response_ids if item)),
        })
    parent_receipts = []
    if root:
        for event in root["events"]:
            payload = event.get("payload", {})
            if event.get("type") != "response_item" or payload.get("type") != "agent_message":
                continue
            if payload.get("recipient") == "/root" and payload.get("author") != "/root":
                parent_receipts.append({
                    "author": payload.get("author"),
                    "content": text_parts(payload.get("content")),
                })
    identity = "NOT_VERIFIED"
    if spawn_calls and child_records:
        identity = "PASS"
    if identity == "PASS" and not any(item["terminal_events"] for item in child_records):
        identity = "CHILD_SESSION_NO_TERMINAL"
    if identity == "PASS" and not parent_receipts:
        identity = "CHILD_NO_PARENT_RECEIPT"
    task_delivery = "UNKNOWN"
    if child_records:
        if all(item["task_payload_visible"] for item in child_records):
            task_delivery = "PASS"
        elif any(item["task_payload_visible"] for item in child_records):
            task_delivery = "PARTIAL"
        else:
            task_delivery = "TASK_PAYLOAD_NOT_VISIBLE"
    recursive = len(descendants) > 0
    return {
        "probe": probe.name,
        "raw_stdout_status": (
            json.loads(raw_result.read_text()).get("status")
            if raw_result.is_file() else "MISSING"
        ),
        "protocol": (
            json.loads(raw_result.read_text()).get("protocol")
            if raw_result.is_file() else None
        ),
        "root_thread_id": root_id,
        "root_session_found": root is not None,
        "root_session_sha256": root["sha256"] if root else None,
        "spawn_calls_in_session": spawn_calls,
        "send_message_calls_in_session": send_calls,
        "wait_calls_in_session": wait_calls,
        "exec_json_collab_tools": sorted(
            item.get("tool") for item in exec_collab if item.get("tool")
        ),
        "exec_json_spawn_collab_count": sum(
            item.get("tool") == "spawn_agent" for item in exec_collab
        ),
        "direct_child_count": len(child_records),
        "descendant_session_count": len(descendants),
        "recursive_children_observed": recursive,
        "direct_children": child_records,
        "parent_receipt_count": len(parent_receipts),
        "parent_receipts": parent_receipts,
        "native_identity": identity,
        "task_delivery": (
            "PASS_ENCRYPTED_MESSAGE_TO_CHILD"
            if any(item["task_delivery"] == "PASS_ENCRYPTED_MESSAGE_TO_CHILD"
                   for item in child_records)
            else "TASK_PAYLOAD_NOT_VISIBLE"
        ),
        "task_output_marker_observed": any(
            item["task_output_marker"] for item in child_records
        ),
        "exec_json_projection_gap": bool(spawn_calls) and not any(
            item.get("tool") == "spawn_agent" for item in exec_collab
        ),
        "stderr_has_mcp_9000": (
            "127.0.0.1:9000" in stderr_path.read_text(errors="replace")
            if stderr_path.is_file() else False
        ),
        "stderr_has_provider_error": (
            "ERROR" in stderr_path.read_text(errors="replace").upper()
            if stderr_path.is_file() else False
        ),
        "config_sha256": (
            sha(probe / "codex_home/config.toml")
            if (probe / "codex_home/config.toml").is_file() else None
        ),
        "stdout_sha256": sha(stdout_path) if stdout_path.is_file() else None,
        "stderr_sha256": sha(stderr_path) if stderr_path.is_file() else None,
    }


def main() -> int:
    records = []
    for name in PROBES:
        probe = E / "09_evidence" / name
        if not probe.is_dir():
            records.append({"probe": name, "native_identity": "MISSING"})
            continue
        result = analyze_probe(probe)
        write(probe / "NATIVE_IDENTITY_AUDIT.json", result)
        records.append(result)
    task_verified = any(
        item.get("native_identity") == "PASS"
        and item.get("task_delivery") == "PASS_ENCRYPTED_MESSAGE_TO_CHILD"
        and item.get("parent_receipt_count", 0) > 0
        for item in records
    )
    summary = {
        "schema": "aevora.g24.native_identity_audit/1.0",
        "status": "PASS" if task_verified else "NOT_VERIFIED",
        "records": records,
        "native_identity": any(
            item.get("native_identity") == "PASS" for item in records
        ),
        "native_identity_session_graph": (
            "PASS"
            if any(item.get("native_identity") == "PASS" for item in records)
            else "NOT_VERIFIED"
        ),
        "native_parent_child": (
            "PASS" if task_verified else "NOT_VERIFIED_TASK_PAYLOAD_NOT_VISIBLE"
        ),
        "task_delivery": (
            "PASS_WITH_EXPLICIT_SEND_MESSAGE" if task_verified
            else "TASK_PAYLOAD_NOT_VISIBLE"
        ),
        "task_output_marker_observed": any(
            item.get("task_output_marker_observed") for item in records
        ),
        "exec_json_projection_gap": any(
            item.get("exec_json_projection_gap") for item in records
        ),
    }
    write(E / "09_evidence/NATIVE_IDENTITY_AUDIT.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
