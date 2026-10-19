"""Synthetic schema regressions; these fixtures are not native runtime evidence."""
from copy import deepcopy

import pytest

from integrations.native_rollout_trace import _text
from test_native_rollout_trace import analyze, fixture, item


def with_final(text, *, channel="response", completion=None, receipt=None):
    files = fixture()
    child = files["child-1"]
    response = next(row for row in child if row["payload"].get("role") == "assistant")
    response["payload"]["content"] = [{"type": "output_text", "text": text}]
    if channel in ("item", "both"):
        child.insert(child.index(response), item("child-1", "child-1-turn", {
            "type": "AgentMessage", "id": "actual-final", "phase": "final_answer",
            "content": [{"type": "Text", "text": text}],
        }, 5))
    if channel == "item":
        child.remove(response)
    ended = next(row for row in child if row["payload"].get("type") == "task_complete")
    ended["payload"]["last_agent_message"] = text if completion is None else completion
    parent = next(row for row in files["lead"] if row["payload"].get("author") == "/root/child-1")
    parent["payload"]["content"] = [{"type": "input_text", "text": (
        "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/child-1\nPayload:\n"
        + (text if receipt is None else receipt)
    )}]
    return files


def first_child(result):
    return next(agent for agent in result["summary"]["subagents"]["agents"]
                if agent["agent_id"] == "child-1")


@pytest.mark.parametrize("channel", ["response", "item", "both"])
@pytest.mark.parametrize("text", ["report\n\n", "  report", "\n\treport \n", "report"])
def test_exact_final_and_completion_preserve_boundary_whitespace(tmp_path, channel, text):
    result = analyze(tmp_path, with_final(text, channel=channel))
    child = first_child(result)
    assert child["completed"] and child["verified"]
    assert result["summary"]["subagents"]["verified_count"] == 2
    final = next(event for event in result["events"]
                 if event["event_type"] == "native.final_answer"
                 and event["payload"]["thread_id"] == "child-1")
    assert final["payload"]["event"]["text"] == text
    receipt = next(event for event in result["events"]
                   if event["event_type"] == "native.parent_receipt"
                   and event["payload"]["event"]["author"] == "/root/child-1")
    assert receipt["payload"]["event"]["content"] == (
        "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/child-1\nPayload:\n" + text
    )


@pytest.mark.parametrize("channel", ["response", "item", "both"])
@pytest.mark.parametrize("text,completion", [
    ("report\n\n", "report"), ("report", "report\n\n"),
    (" report", "report"), ("report", " report"),
    ("right\n", "wrong\n"),
])
def test_real_content_or_boundary_whitespace_mismatch_does_not_complete(tmp_path, channel, text, completion):
    child = first_child(analyze(tmp_path, with_final(text, channel=channel, completion=completion)))
    assert child["completed"] is False
    assert child["verified"] is False


@pytest.mark.parametrize("text,receipt", [
    ("report\n\n", "report"), ("report", "report\n\n"),
    (" report", "report"), ("report", " report"),
    ("report", "different"), ("report", "report with extra content"),
    ("report", "prefix report suffix"),
])
def test_receipt_missing_exact_final_text_does_not_verify(tmp_path, text, receipt):
    child = first_child(analyze(tmp_path, with_final(text, receipt=receipt)))
    assert child["completed"] is True
    assert child["verified"] is False


@pytest.mark.parametrize("prefix", [
    " Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/child-1\nPayload:\n",
    "Message Type: FINAL_ANSWER\nTask name: /wrong\nSender: /root/child-1\nPayload:\n",
    "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /wrong\nPayload:\n",
    "Message Type: NEW_TASK\nTask name: /root\nSender: /root/child-1\nPayload:\n",
])
def test_typed_receipt_prefix_must_match_actual_parent_and_child(tmp_path, prefix):
    files = with_final("report\n\n")
    parent = next(row for row in files["lead"] if row["payload"].get("author") == "/root/child-1")
    parent["payload"]["content"] = [{"type": "input_text", "text": prefix + "report\n\n"}]
    child = first_child(analyze(tmp_path, files))
    assert child["completed"] is True and child["verified"] is False


@pytest.mark.parametrize("problem", ["missing", "error", "null", "integer", "list",
                                     "missing_text", "wrong_turn", "commentary"])
def test_completion_missing_error_or_malformed_still_fails_closed(tmp_path, problem):
    files = with_final(" report\n\n")
    child = files["child-1"]
    ended = next(row for row in child if row["payload"].get("type") == "task_complete")
    if problem == "missing":
        child.remove(ended)
    elif problem == "error":
        ended["payload"]["error"] = {"message": "Synthetic terminal error"}
    elif problem in ("null", "integer", "list"):
        ended["payload"]["last_agent_message"] = {"null": None, "integer": 3, "list": [" report\n\n"]}[problem]
    elif problem == "missing_text":
        ended["payload"].pop("last_agent_message")
    elif problem == "wrong_turn":
        ended["payload"]["turn_id"] = "unrelated-turn"
    elif problem == "commentary":
        next(row for row in child if row["payload"].get("role") == "assistant")["payload"]["phase"] = "commentary"
    result = first_child(analyze(tmp_path, files))
    assert result["completed"] is False
    assert result["verified"] is False


@pytest.mark.parametrize("content", [None, [], [{"type": "output_text", "text": None}],
                                     [{"type": "output_text", "text": 3}],
                                     [{"type": "encrypted_content", "encrypted_content": "synthetic"}]])
def test_malformed_final_content_is_not_a_completion(tmp_path, content):
    files = with_final("report\n\n")
    next(row for row in files["child-1"] if row["payload"].get("role") == "assistant")["payload"]["content"] = deepcopy(content)
    result = first_child(analyze(tmp_path, files))
    assert result["completed"] is False and result["verified"] is False


@pytest.mark.parametrize("text", ["", " ", "\n\t\n"])
def test_whitespace_only_final_is_not_substantive_completion(tmp_path, text):
    child = first_child(analyze(tmp_path, with_final(text)))
    assert child["completed"] is False and child["verified"] is False
    assert _text([{"type": "Text", "text": text}], preserve_whitespace=True) is None


def test_ordinary_text_extraction_behavior_is_preserved():
    content = [{"type": "input_text", "text": " \nreport\t\n"}]
    assert _text(content) == "report"
    assert _text(content, preserve_whitespace=True) == " \nreport\t\n"
