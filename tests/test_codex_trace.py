"""Synthetic wire-contract tests, not evidence of a real Codex agent execution."""

from hashlib import sha256
import json

import pytest

from integrations.codex_trace import (
    REDACTED,
    UNAVAILABLE,
    parse_trace,
    redact,
    redact_jsonl,
    redact_text,
)


def write_events(tmp_path, events):
    path = tmp_path / "codex_events.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    return path


def turn_start():
    return [{"type": "thread.started", "thread_id": "parent-contract"}, {"type": "turn.started"}]


def turn_end(**extra):
    usage = {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 4}
    usage.update(extra)
    return {"type": "turn.completed", "usage": usage}


def collab(item_id, tool, receivers, states, *, prompt=None, parent="parent-contract", status="completed"):
    return {
        "type": "item.completed",
        "item": {
            "id": item_id, "type": "collab_tool_call", "tool": tool,
            "sender_thread_id": parent, "receiver_thread_ids": receivers,
            "prompt": prompt, "agents_states": states, "status": status,
        },
    }


def parse(tmp_path, events, **kwargs):
    raw = write_events(tmp_path, events)
    trace = tmp_path / "agent_trace.jsonl"
    return parse_trace(raw, trace, "run-contract", **kwargs), raw, trace


def test_complete_turn_references_exact_archived_bytes(tmp_path):
    events = turn_start() + [turn_end(reasoning_output_tokens=2)]
    result, raw, trace = parse(tmp_path, events, collected_at="2026-10-10T00:00:00+00:00")
    assert result["integrity"]["status"] == "COMPLETE"
    assert result["thread_id"] == "parent-contract"
    assert result["session_id"] == UNAVAILABLE
    assert result["turn_status"] == "COMPLETED"
    assert result["event_count"] == 3
    assert result["raw_events_sha256"] == sha256(raw.read_bytes()).hexdigest()
    assert result["trace_sha256"] == sha256(trace.read_bytes()).hexdigest()
    assert result["usage"]["totals"] == {
        "input_tokens": 10, "cached_input_tokens": 3,
        "output_tokens": 4, "reasoning_output_tokens": 2,
    }
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    original_lines = raw.read_bytes().splitlines(keepends=True)
    for index, row in enumerate(rows):
        assert row["run_id"] == "run-contract"
        assert row["timestamp"] == "2026-10-10T00:00:00+00:00"
        assert row["payload"]["timestamp_source"] == "archive_collection_utc"
        assert row["payload"]["official_timestamp"] == UNAVAILABLE
        assert row["payload"]["raw_reference"] == {
            "path": str(raw), "line": index + 1,
            "sha256": sha256(original_lines[index]).hexdigest(),
        }


def test_only_structured_spawn_and_completed_states_verify_two_children(tmp_path):
    events = turn_start() + [
        collab("spawn-1", "spawn_agent", ["child-1"], {"child-1": {"status": "running", "message": None}}, prompt="Investigate inventory transactions"),
        collab("spawn-2", "spawn_agent", ["child-2"], {"child-2": {"status": "pending_init", "message": None}}, prompt="Reproduce concurrency and inspect tests"),
        collab("wait-1", "wait", ["child-1", "child-2"], {
            "child-1": {"status": "completed", "message": "Transaction investigation completed"},
            "child-2": {"status": "completed", "message": "Public concurrency reproduction completed"},
        }),
        turn_end(),
    ]
    result, raw, _ = parse(tmp_path, events)
    evidence = result["subagents"]
    assert evidence["availability"] == "AVAILABLE"
    assert evidence["spawned_count"] == evidence["completed_count"] == evidence["verified_count"] == 2
    assert {agent["thread_id"] for agent in evidence["agents"]} == {"child-1", "child-2"}
    for agent in evidence["agents"]:
        assert agent["parent_thread_id"] == "parent-contract"
        assert agent["task"] != UNAVAILABLE
        assert agent["completion_reference"]["line"] == 5
        assert agent["spawn_reference"]["path"] == str(raw)
    assert result["integrity"]["status"] == "COMPLETE"


def test_collab_tool_completion_is_not_child_task_completion(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        collab("spawn", "spawn_agent", ["child"], {"child": {"status": "running", "message": None}}, prompt="Investigate"),
        turn_end(),
    ])
    assert result["subagents"]["spawned_count"] == 1
    assert result["subagents"]["completed_count"] == 0
    assert result["subagents"]["verified_count"] == 0


@pytest.mark.parametrize("prompt,message", [(None, "Completed"), ("Task", None), ("", "")])
def test_unavailable_task_or_response_does_not_verify_independent_work(tmp_path, prompt, message):
    result, _, _ = parse(tmp_path, turn_start() + [
        collab("spawn", "spawn_agent", ["child"], {"child": {"status": "completed", "message": message}}, prompt=prompt),
        turn_end(),
    ])
    assert result["subagents"]["spawned_count"] == result["subagents"]["completed_count"] == 1
    assert result["subagents"]["verified_count"] == 0


def test_agent_prose_cannot_create_collaboration_events(tmp_path):
    text = 'I used spawn_agent {"agent_id":"fake"} and three experts completed the task.'
    result, _, trace = parse(tmp_path, turn_start() + [
        {"type": "item.completed", "item": {"id": "message", "type": "agent_message", "text": text}},
        turn_end(),
    ])
    assert result["subagents"]["availability"] == UNAVAILABLE
    assert result["subagents"]["agents"] == []
    assert text in json.loads(trace.read_text().splitlines()[2])["payload"]["event"]["item"]["text"]


def test_appserver_wire_type_is_not_accepted_as_exec_collaboration(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        {"type": "item.completed", "item": {
            "id": "appserver", "type": "collabAgentToolCall", "tool": "spawnAgent",
            "senderThreadId": "parent-contract", "receiverThreadIds": ["child"],
            "agentsStates": {"child": {"status": "completed", "message": "done"}},
        }}, turn_end(),
    ])
    assert result["subagents"]["availability"] == UNAVAILABLE
    assert result["integrity"]["unknown_item_types"] == {"collabAgentToolCall": 1}


def test_wrong_parent_is_rejected_without_fabricating_relationship(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        collab("spawn", "spawn_agent", ["child"], {"child": {"status": "completed", "message": "done"}}, prompt="Task", parent="other-session"),
        turn_end(),
    ])
    assert result["subagents"]["spawned_count"] == 0
    assert "COLLAB_PARENT_MISMATCH" in {error["code"] for error in result["integrity"]["errors"]}


@pytest.mark.parametrize("field,value", [("tool", {}), ("status", []), ("receiver_thread_ids", [[]]), ("agents_states", {"child": {"status": {}}})])
def test_malformed_collaboration_fields_are_reported_without_parser_crash(tmp_path, field, value):
    event = collab("spawn", "spawn_agent", ["child"], {}, prompt="Task")
    event["item"][field] = value
    result, _, _ = parse(tmp_path, turn_start() + [event, turn_end()])
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert result["subagents"]["spawned_count"] == 0
    assert "INVALID_COLLAB_ITEM" in {error["code"] for error in result["integrity"]["errors"]}


def test_completion_for_unobserved_child_does_not_prove_a_spawn(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        collab("wait", "wait", ["unseen"], {"unseen": {"status": "completed", "message": "done"}}), turn_end(),
    ])
    assert result["subagents"]["availability"] == "AVAILABLE"
    assert result["subagents"]["spawned_count"] == result["subagents"]["verified_count"] == 0


def test_unknown_event_is_preserved_without_reinterpreting_payload(tmp_path):
    unknown = {"type": "future.event", "value": {"tool": "spawn_agent", "thread_id": "invented"}}
    result, _, trace = parse(tmp_path, turn_start() + [unknown, turn_end()])
    assert result["integrity"]["unknown_events"] == {"future.event": 1}
    assert json.loads(trace.read_text().splitlines()[2])["payload"]["event"] == unknown
    assert result["subagents"]["spawned_count"] == 0


def test_turn_failure_is_complete_evidence_of_runtime_failure(tmp_path):
    failure = {"type": "turn.failed", "error": {"message": "Model service unavailable"}}
    result, _, _ = parse(tmp_path, turn_start() + [failure])
    assert result["integrity"]["status"] == "COMPLETE"
    assert result["turn_status"] == "FAILED"
    assert result["runtime_errors"][0]["error"] == failure["error"]
    assert result["usage"]["availability"] == result["usage"]["totals"] == UNAVAILABLE


def startup_warning():
    # Wire shape/message observed in actual Run
    # 666f334a-5335-419d-bcd4-45797d819c8d, codex_events.jsonl line 2.
    # Replaying this contract fixture is not proof of a model call or subagent.
    return {"type": "item.completed", "item": {
        "id": "item_0", "type": "error",
        "message": "Model metadata for `gpt-6.1-sol` not found. Defaulting to fallback metadata; this can degrade performance and cause issues.",
    }}


def test_observed_cli_startup_warning_is_complete_and_preserved(tmp_path):
    warning = startup_warning()
    result, raw, trace = parse(tmp_path, [turn_start()[0], warning, turn_start()[1], turn_end()])
    assert result["integrity"]["status"] == "COMPLETE"
    assert result["turn_status"] == "COMPLETED"
    assert result["completed_items"] == {"error": 1}
    assert result["startup_warnings"] == [{
        "item_id": "item_0", "message": warning["item"]["message"],
        "raw_reference": {"path": str(raw), "line": 2,
            "sha256": sha256(raw.read_bytes().splitlines(keepends=True)[1]).hexdigest()},
    }]
    observation = json.loads(trace.read_text().splitlines()[1])
    assert observation["payload"]["event"] == warning
    assert observation["payload"]["classification"] == "startup_warning"
    assert result["subagents"]["verified_count"] == 0


def test_observed_warning_does_not_hide_a_subsequent_failed_turn(tmp_path):
    result, _, _ = parse(tmp_path, [turn_start()[0], startup_warning(), turn_start()[1],
        {"type": "error", "message": "UPSTREAM_CONNECTION_ERROR"},
        {"type": "turn.failed", "error": {"message": "UPSTREAM_CONNECTION_ERROR"}},
    ])
    assert result["integrity"]["status"] == "COMPLETE"
    assert result["turn_status"] == "FAILED"
    assert len(result["runtime_errors"]) == 2
    assert len(result["startup_warnings"]) == 1


@pytest.mark.parametrize("case", ["no_thread", "duplicate", "pending", "not_completed", "no_message", "after_turn"])
def test_warning_exception_requires_valid_fresh_startup_lifecycle(tmp_path, case):
    warning = startup_warning()
    events = [turn_start()[0]]
    if case == "no_thread":
        events = []
    elif case == "duplicate":
        events.append(startup_warning())
    elif case == "pending":
        events.append({"type": "item.started", "item": {"id": "pending", "type": "command_execution"}})
    elif case == "not_completed":
        warning["type"] = "item.started"
    elif case == "no_message":
        warning["item"]["message"] = None
    elif case == "after_turn":
        events += [turn_start()[1], turn_end()]
    events.append(warning)
    events += [turn_start()[1], turn_end()]
    result, _, _ = parse(tmp_path, events)
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert "ITEM_OUTSIDE_TURN" in {error["code"] for error in result["integrity"]["errors"]}


@pytest.mark.parametrize("item_type", ["command_execution", "file_change", "collab_tool_call", "agent_message"])
def test_nonwarning_items_still_require_an_active_turn(tmp_path, item_type):
    item = {"id": "outside", "type": item_type}
    if item_type == "collab_tool_call":
        item = collab("outside", "spawn_agent", ["child"], {}, prompt="task")["item"]
    result, _, _ = parse(tmp_path, [turn_start()[0], {"type": "item.completed", "item": item}, turn_start()[1], turn_end()])
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert "ITEM_OUTSIDE_TURN" in {error["code"] for error in result["integrity"]["errors"]}
    assert result["startup_warnings"] == []


def test_multiple_turns_sum_observed_usage_without_inventing_optional_fields(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [turn_end(), {"type": "turn.started"}, turn_end(cache_write_input_tokens=5)])
    assert result["turns_started"] == result["turns_finished"] == 2
    assert result["usage"]["totals"] == {"input_tokens": 20, "cached_input_tokens": 6, "output_tokens": 8, "cache_write_input_tokens": 5}
    assert "reasoning_output_tokens" not in result["usage"]["totals"]


@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": True, "cached_input_tokens": 0, "output_tokens": 2}, {"input_tokens": -1, "cached_input_tokens": 0, "output_tokens": 2}])
def test_invalid_usage_is_unavailable_and_trace_incomplete(tmp_path, usage):
    result, _, _ = parse(tmp_path, turn_start() + [{"type": "turn.completed", "usage": usage}])
    assert result["usage"]["availability"] == UNAVAILABLE
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert "INVALID_USAGE" in {error["code"] for error in result["integrity"]["errors"]}


def test_truncated_turn_and_item_are_explicit(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        {"type": "item.started", "item": {"id": "cmd", "type": "command_execution", "status": "in_progress", "command": "pytest", "aggregated_output": "", "exit_code": None}},
    ])
    codes = {error["code"] for error in result["integrity"]["errors"]}
    assert {"UNFINISHED_TURN", "UNFINISHED_ITEMS"} <= codes
    assert result["turn_status"] == UNAVAILABLE
    assert result["timestamp_source"] == "trace_parse_utc"


def test_file_change_completed_only_is_valid_official_event(tmp_path):
    result, _, _ = parse(tmp_path, turn_start() + [
        {"type": "item.completed", "item": {"id": "patch", "type": "file_change", "changes": [{"path": "app/inventory.py", "kind": "update"}], "status": "completed"}},
        turn_end(),
    ])
    assert result["integrity"]["status"] == "COMPLETE"
    assert result["completed_items"] == {"file_change": 1}


def test_duplicate_item_completion_is_not_counted_twice(tmp_path):
    item = {"type": "item.completed", "item": {"id": "message", "type": "agent_message", "text": "done"}}
    result, _, _ = parse(tmp_path, turn_start() + [item, item, turn_end()])
    assert result["completed_items"]["agent_message"] == 1
    assert result["integrity"]["status"] == "INCOMPLETE"


def test_invalid_lines_and_empty_stream_are_archived_as_incomplete(tmp_path):
    raw = tmp_path / "codex_events.jsonl"
    raw.write_bytes(b'not-json\n[1,2]\n{}\n\xff\n')
    trace = tmp_path / "agent_trace.jsonl"
    result = parse_trace(raw, trace, "run-contract")
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert result["thread_id"] == UNAVAILABLE
    assert result["event_count"] == 4
    assert len(trace.read_text().splitlines()) == 4
    raw.write_bytes(b"")
    empty = parse_trace(raw, trace, "run-contract")
    assert empty["integrity"]["status"] == "INCOMPLETE"
    assert empty["event_count"] == 0


def test_redactor_protects_nested_credentials_without_changing_usage():
    original = {
        "Authorization": "Bearer sample-auth", "access_token": "sample-access",
        "nested": [{"refreshToken": "sample-refresh", "api-key": "sample-key", "usage": {"input_tokens": 20}}],
        "text": "Authorization: Bearer sample-auth OPENAI_API_KEY=sample-key refresh_token='sample-refresh'",
    }
    cleaned = redact(original)
    serialized = json.dumps(cleaned)
    for secret in ("sample-auth", "sample-access", "sample-refresh", "sample-key"):
        assert secret not in serialized
    assert cleaned["nested"][0]["usage"]["input_tokens"] == 20
    assert original["access_token"] == "sample-access"


def test_explicit_secret_values_and_common_key_shapes_are_removed():
    text = "custom-opaque-value sk-proj-0123456789abcdef and Bearer abc.def.ghi"
    cleaned = redact_text(text, secret_values=("custom-opaque-value",))
    assert "custom-opaque-value" not in cleaned
    assert "0123456789abcdef" not in cleaned
    assert "abc.def.ghi" not in cleaned
    assert REDACTED in cleaned


def test_redacted_jsonl_keeps_original_nonsensitive_bytes_and_malformed_diagnosis(tmp_path):
    raw = tmp_path / "capture.tmp"
    raw.write_bytes(b'{ "type": "thread.started", "thread_id": "parent-contract" }\r\n{"api_key":"contract-secret"}\ninvalid access_token=opaque-value\n')
    archived = tmp_path / "codex_events.jsonl"
    result = redact_jsonl(raw, archived)
    contents = archived.read_bytes()
    assert contents.splitlines(keepends=True)[0] == raw.read_bytes().splitlines(keepends=True)[0]
    assert b"contract-secret" not in contents and b"opaque-value" not in contents
    assert contents.splitlines()[2].startswith(b"invalid ")
    assert result["redacted_lines"] == 2
    assert result["malformed_lines"] == 1
    assert result["sha256"] == sha256(contents).hexdigest()


def test_trace_payload_is_redacted_even_if_caller_supplied_unsafe_capture(tmp_path):
    result, _, trace = parse(tmp_path, turn_start() + [{"type": "error", "message": "Bearer opaque-token", "access_token": "contract-secret"}, {"type": "turn.failed", "error": {"message": "failed"}}])
    assert "opaque-token" not in trace.read_text()
    assert "contract-secret" not in trace.read_text()
    assert "opaque-token" not in json.dumps(result)


def test_same_path_cannot_destroy_raw_event_archive(tmp_path):
    raw = write_events(tmp_path, turn_start() + [turn_end()])
    original = raw.read_bytes()
    with pytest.raises(ValueError, match="must differ"):
        parse_trace(raw, raw, "run-contract")
    assert raw.read_bytes() == original
