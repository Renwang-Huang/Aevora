"""Synthetic native-rollout schema contracts; these are not live agent evidence."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from integrations.native_rollout_trace import analyze_native_rollouts


def row(kind, payload, second=0):
    return {"timestamp": f"2026-10-10T00:00:{second:02d}.000Z", "type": kind, "payload": payload}


def meta(identifier, parent=None):
    result = {"id": identifier, "session_id": "lead", "parent_thread_id": parent,
              "agent_path": "/root" if not parent else f"/root/{identifier}", "cli_version": "0.162.1"}
    if parent:
        result["source"] = {"subagent": {"thread_spawn": {
            "parent_thread_id": parent, "agent_path": result["agent_path"], "depth": 1}}}
    return row("session_meta", result)


def start(turn, parent_turn=None):
    return row("event_msg", {"type": "task_started", "turn_id": turn,
        "turn_attribution": {"turn_id": turn, "parent_turn_id": parent_turn, "root_turn_id": "lead-turn"}})


def item(thread, turn, payload, second=1):
    return row("event_msg", {"type": "item_completed", "thread_id": thread, "turn_id": turn,
                             "item": payload}, second)


def communication(author, recipient, turn, text, trigger=True, encrypted=False, second=2):
    content = [{"type": "input_text", "text": text}]
    if encrypted:
        content.append({"type": "encrypted_content", "encrypted_content": "opaque-synthetic-ciphertext"})
    return [row("inter_agent_communication_metadata", {"trigger_turn": trigger}, second),
        row("response_item", {"type": "agent_message", "id": f"amsg-{author}-{recipient}",
            "author": author, "recipient": recipient, "content": content,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn}}, second)]


def fixture():
    lead = [meta("lead"), start("lead-turn")]
    files = {"lead": lead}
    for number in range(1, 3):
        name = f"child-{number}"; turn = f"{name}-turn"; path = f"/root/{name}"
        lead.append(item("lead", "lead-turn", {"type": "SubAgentActivity", "kind": "started",
            "id": f"spawn-{number}", "agent_thread_id": name, "agent_path": path}))
        # Real fork shape: first own meta, then copied parent meta/context/events.
        child = [meta(name, "lead"), meta("lead"), start("lead-turn"),
            item("lead", "lead-turn", {"type": "CommandExecution", "id": "inherited-command",
                "status": "completed"}),
            row("response_item", {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "inherited parent issue"}]}), start(turn, "lead-turn")]
        child += communication("/root", path, turn,
            f"Message Type: NEW_TASK\nTask name: {path}\nSender: /root\nPayload:\n", encrypted=True)
        child += [item(name, turn, {"type": "CommandExecution", "id": "actual-command",
            "status": "completed", "command": ["true"], "exit_code": 0}, 3),
            row("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "call-1"}, 3),
            row("token_usage_record", {"thread_id": name, "turn_id": turn, "response_id": f"resp-{name}",
                "usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
                "thread_token_usage": {"input_tokens": 700, "output_tokens": 300}}, 4),
            row("response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
                "content": [{"type": "output_text", "text": f"Actual findings for {name}"}]}, 5),
            row("event_msg", {"type": "task_complete", "turn_id": turn, "error": None,
                "last_agent_message": f"Actual findings for {name}"}, 6)]
        files[name] = child
        lead += communication(path, "/root", "lead-turn",
            f"Message Type: FINAL_ANSWER\nTask name: /root\nSender: {path}\nPayload:\nActual findings for {name}",
            trigger=False, second=7)
    return files


def analyze(tmp_path, files=None, *, mutate_records=None, run_id="run-contract"):
    archive = tmp_path / "run-contract"
    root = archive / "artifacts/native_rollouts"
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for identifier, values in (files or fixture()).items():
        path = root / f"{identifier}.jsonl"
        content = "".join(json.dumps(value) + "\n" for value in values).encode()
        path.write_bytes(content)
        records.append({"path": str(path), "sha256": sha256(content).hexdigest()})
    if mutate_records:
        mutate_records(records, root)
    return analyze_native_rollouts(run_id, archive, {"files": records}, expected_parent_thread_id="lead")


def test_two_typed_children_complete_return_and_references_are_exact(tmp_path):
    result = analyze(tmp_path)
    s = result["summary"]
    assert s["integrity"] == {"status": "COMPLETE", "errors": []}
    assert s["subagents"]["verified_count"] == s["subagents"]["spawned_count"] == 2
    assert s["subagents"]["completed_count"] == s["subagents"]["parent_receipt_count"] == 2
    assert s["subagents"]["task_plaintext_count"] == 0
    assert s["usage"]["totals"]["input_tokens"] == 14
    assert s["usage"]["totals"]["total_tokens"] == 20  # never sum cumulative 700/300
    for child in s["subagents"]["agents"]:
        assert child["tools"] == {"CommandExecution": 1, "custom_tool_call": 1}
        assert child["task"] == "UNAVAILABLE" and child["task_delivery"] != "UNAVAILABLE"
    for e in result["events"]:
        ref = e["payload"]["raw_reference"]
        from pathlib import Path
        raw = Path(ref["path"]).read_bytes().splitlines(keepends=True)[ref["line"] - 1]
        assert sha256(raw).hexdigest() == ref["sha256"]
        assert e["timestamp"] == json.loads(raw)["timestamp"]
        assert e["run_id"] == "run-contract"


@pytest.mark.parametrize("remove", ["spawn", "meta", "delivery", "completion", "final", "receipt", "tools"])
def test_each_required_link_is_required(tmp_path, remove):
    files = fixture()
    if remove == "spawn":
        files["lead"] = [r for r in files["lead"] if r["payload"].get("item", {}).get("agent_thread_id") != "child-1"]
    elif remove == "meta":
        files["child-1"][0]["payload"]["source"] = {}
    elif remove == "delivery":
        files["child-1"] = [r for r in files["child-1"] if r["type"] != "inter_agent_communication_metadata"]
    elif remove == "completion":
        files["child-1"] = [r for r in files["child-1"] if r["payload"].get("type") != "task_complete"]
    elif remove == "final":
        files["child-1"] = [r for r in files["child-1"] if r["payload"].get("role") != "assistant"]
    elif remove == "receipt":
        files["lead"] = [r for r in files["lead"] if r["payload"].get("author") != "/root/child-1"]
    elif remove == "tools":
        files["child-1"] = [r for r in files["child-1"] if r["payload"].get("item", {}).get("id") != "actual-command"]
    result = analyze(tmp_path, files)["summary"]["subagents"]
    assert result["verified_count"] == 1


@pytest.mark.parametrize("field,value", [("parent_thread_id", "different-parent"),
    ("session_id", "another-run"), ("agent_path", "/root/unrelated")])
def test_child_cannot_join_wrong_parent_session_or_path(tmp_path, field, value):
    files = fixture(); files["child-1"][0]["payload"][field] = value
    result = analyze(tmp_path, files)["summary"]
    assert result["subagents"]["agents"][0]["verified"] is False


def test_error_and_commentary_never_count_as_successful_return(tmp_path):
    files = fixture()
    for r in files["child-1"]:
        if r["payload"].get("type") == "task_complete":
            r["payload"]["error"] = {"message": "429 Too Many Requests"}
    for r in files["child-2"]:
        if r["payload"].get("role") == "assistant":
            r["payload"]["phase"] = "commentary"
    result = analyze(tmp_path, files)["summary"]["subagents"]
    assert result["completed_count"] == result["verified_count"] == 0
    assert result["agents"][0]["errors"] == [{"message": "429 Too Many Requests"}]


def test_inherited_parent_success_tools_and_usage_never_count(tmp_path):
    files = fixture()
    files["child-1"] = files["child-1"][:5]  # no new own turn at all
    result = analyze(tmp_path, files)["summary"]["subagents"]
    child = result["agents"][0]
    assert child["tools"] == {} and child["usage"] == []
    assert child["task_delivery"] == child["completion"] == "UNAVAILABLE"
    assert child["execution_verified"] is False and child["verified"] is False


def test_interacted_and_natural_language_claims_do_not_make_spawns(tmp_path):
    files = fixture()
    for r in files["lead"]:
        if r["payload"].get("item", {}).get("type") == "SubAgentActivity":
            r["payload"]["item"]["kind"] = "interacted"
    files["lead"].append(row("response_item", {"type": "message", "role": "assistant",
        "phase": "final_answer", "content": [{"type": "output_text", "text": "Two experts ran and passed."}]}))
    result = analyze(tmp_path, files)["summary"]["subagents"]
    assert result["spawned_count"] == result["verified_count"] == 0
    assert result["availability"] == "UNAVAILABLE"


def test_empty_cipher_without_task_content_is_not_a_delivery(tmp_path):
    files = fixture()
    for r in files["child-1"]:
        if r["payload"].get("type") == "agent_message":
            r["payload"]["content"] = [{"type": "encrypted_content", "encrypted_content": ""}]
    result = analyze(tmp_path, files)["summary"]["subagents"]["agents"][0]
    assert result["task_delivery"] == "UNAVAILABLE" and not result["verified"]


@pytest.mark.parametrize("tamper", ["hash", "outside", "symlink", "hardlink", "malformed", "duplicate", "run"])
def test_archive_integrity_errors_close_all_verification(tmp_path, tamper):
    def mutate(records, root):
        path = root / "child-1.jsonl"
        if tamper == "hash":
            records[1]["sha256"] = "0" * 64
        elif tamper == "outside":
            records[1]["path"] = str(tmp_path / "elsewhere.jsonl")
        elif tamper == "symlink":
            target = root / "target"; path.rename(target); path.symlink_to(target)
        elif tamper == "hardlink":
            import os
            os.link(path, root / "hardlink")
        elif tamper == "malformed":
            with path.open("ab") as f:
                f.write(b"not-json\n")
            records[1]["sha256"] = sha256(path.read_bytes()).hexdigest()
        elif tamper == "duplicate":
            records.append(deepcopy(records[1]))
    result = analyze(tmp_path, mutate_records=mutate,
        run_id="wrong-run" if tamper == "run" else "run-contract")["summary"]
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert result["subagents"]["verified_count"] == 0


def test_missing_archives_stay_unavailable(tmp_path):
    result = analyze_native_rollouts("run", tmp_path / "run", {"files": []})["summary"]
    assert result["usage"]["availability"] == result["subagents"]["availability"] == "UNAVAILABLE"
    assert result["subagents"]["verified_count"] == 0


def test_duplicate_usage_is_not_double_counted_or_verified(tmp_path):
    files = fixture()
    usage = next(r for r in files["child-1"] if r["type"] == "token_usage_record")
    files["child-1"].append(deepcopy(usage))
    result = analyze(tmp_path, files)["summary"]
    assert result["usage"]["totals"]["total_tokens"] == 20
    assert result["subagents"]["verified_count"] == 0
    assert {"code": "DUPLICATE_USAGE_RESPONSE", "thread_id": "child-1"} in result["integrity"]["errors"]


def test_plaintext_tasks_are_actual_messages_and_legacy_final_matches_completion(tmp_path):
    files = fixture()
    for r in files["child-1"]:
        p = r["payload"]
        if p.get("type") == "agent_message":
            p["content"] = [{"type": "input_text", "text": "Investigate public transaction boundaries"}]
        if p.get("role") == "assistant":
            p.pop("phase")
    result = analyze(tmp_path, files)["summary"]["subagents"]
    assert result["verified_count"] == 2 and result["task_plaintext_count"] == 1
    assert result["agents"][0]["task"] == "Investigate public transaction boundaries"


@pytest.mark.parametrize("where,value", [("source", {"subagent": []}),
    ("content", None), ("message_metadata", []), ("turn_id", ["invalid"]),
    ("parent_id", []), ("timestamp", None)])
def test_malformed_nested_fields_are_unavailable_or_incomplete_not_crashes(tmp_path, where, value):
    files = fixture()
    if where == "source":
        files["child-1"][0]["payload"]["source"] = value
    elif where == "parent_id":
        files["child-1"][0]["payload"]["parent_thread_id"] = value
    elif where == "timestamp":
        files["child-1"][0]["timestamp"] = value
    elif where == "turn_id":
        next(r for r in files["child-1"] if r["payload"].get("turn_id") == "child-1-turn")["payload"]["turn_id"] = value
    else:
        message = next(r for r in files["child-1"] if r["payload"].get("type") == "agent_message")
        message["payload"]["content" if where == "content" else "internal_chat_message_metadata_passthrough"] = value
    result = analyze(tmp_path, files)["summary"]
    if where != "message_metadata":
        assert not result["subagents"]["agents"][0]["verified"]


def test_deep_json_record_closes_verification(tmp_path):
    def mutate(records, root):
        path = root / "child-1.jsonl"
        with path.open("ab") as f:
            f.write(b"[" * 3000 + b"0" + b"]" * 3000 + b"\n")
        records[1]["sha256"] = sha256(path.read_bytes()).hexdigest()
    result = analyze(tmp_path, mutate_records=mutate)["summary"]
    assert result["integrity"]["status"] == "INCOMPLETE"
    assert result["subagents"]["verified_count"] == 0


def test_encrypted_message_without_new_task_envelope_is_not_delivery(tmp_path):
    files = fixture()
    message = next(r for r in files["child-1"] if r["payload"].get("type") == "agent_message")
    message["payload"]["content"][0]["text"] = "I delegated work to an expert"
    assert analyze(tmp_path, files)["summary"]["subagents"]["agents"][0]["task_delivery"] == "UNAVAILABLE"


def test_error_child_has_real_notification_but_no_successful_completion(tmp_path):
    files = fixture()
    complete = next(r for r in files["child-1"] if r["payload"].get("type") == "task_complete")
    complete["payload"].update(error={"message": "429"}, last_agent_message=None)
    result = analyze(tmp_path, files)["summary"]["subagents"]
    assert result["spawned_count"] == result["parent_receipt_count"] == 2
    assert result["completed_count"] == result["verified_count"] == 1


def test_official_optional_error_omission_is_none_not_runtime_error(tmp_path):
    files = fixture()
    for rows in files.values():
        for r in rows:
            if r["payload"].get("type") == "task_complete":
                r["payload"].pop("error")
    assert analyze(tmp_path, files)["summary"]["subagents"]["verified_count"] == 2
