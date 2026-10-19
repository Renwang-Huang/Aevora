"""Incremental offline-verifier boundary controls; synthetic native records.

These records exercise verification semantics and are never model-run evidence.
Original evidence-export tests remain byte-for-byte untouched.
"""
from hashlib import sha256
import json

import pytest

from benchmark.evidence_verify import EvidenceVerifyError, _native_identities


LEAD = "synthetic-lead-thread"
CHILD = "synthetic-child-thread"
PARENT_TURN = "synthetic-parent-turn"
CHILD_TURN = "synthetic-child-turn"
RUN = "11111111-1111-4111-8111-111111111111"
LEAD_PATH = f"runs/{RUN}/artifacts/native_rollouts/lead.jsonl"
CHILD_PATH = f"runs/{RUN}/artifacts/native_rollouts/child.jsonl"


def native_fixture(final_text="completed", completion_text=None, *, complete_error=None, receipt_body=None):
    completion_text = final_text if completion_text is None else completion_text
    receipt_body = completion_text if receipt_body is None else receipt_body
    receipt_text = f"Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/coder\nPayload:\n{receipt_body}"
    lead = [
        {"type": "session_meta", "payload": {"id": LEAD, "agent_path": "/root", "session_id": LEAD}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": PARENT_TURN}},
        {"type": "event_msg", "payload": {"thread_id": LEAD, "turn_id": PARENT_TURN, "item": {
            "type": "SubAgentActivity", "kind": "started", "agent_thread_id": CHILD}}},
        {"type": "response_item", "payload": {"type": "agent_message", "author": "/root/coder", "recipient": "/root",
                                               "content": [{"type": "text", "text": receipt_text}]}},
        {"type": "inter_agent_communication_metadata", "payload": {"trigger_turn": False}},
    ]
    child = [
        {"type": "session_meta", "payload": {"id": CHILD, "parent_thread_id": LEAD, "agent_path": "/root/coder",
                                               "session_id": LEAD, "source": {"subagent": {"thread_spawn": {
                                                   "parent_thread_id": LEAD, "agent_path": "/root/coder"}}}}},
        # Inherited parent task data must not provide the child's own activity.
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": PARENT_TURN}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": CHILD_TURN,
                                           "turn_attribution": {"parent_turn_id": PARENT_TURN}}},
        {"type": "response_item", "payload": {"type": "agent_message", "author": "/root", "recipient": "/root/coder",
                                               "content": [{"type": "text", "text": "Investigate this synthetic task."}]}},
        {"type": "inter_agent_communication_metadata", "payload": {"trigger_turn": True}},
        {"type": "event_msg", "payload": {"thread_id": CHILD, "turn_id": CHILD_TURN,
                                           "item": {"type": "CommandExecution", "status": "completed"}}},
        {"type": "event_msg", "payload": {"thread_id": CHILD, "turn_id": CHILD_TURN,
                                           "item": {"type": "AgentMessage", "content": [{"type": "Text", "text": final_text}]}}},
        {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": CHILD_TURN,
                                           "error": complete_error, "last_agent_message": completion_text}},
    ]
    def encode(events):
        return b"".join((json.dumps(event, separators=(",", ":"))+"\n").encode() for event in events)
    files = {"objects/lead": encode(lead), "objects/child": encode(child)}
    entries = {path: {"object": obj, "run_id": RUN, "source_sha256": sha256(files[obj]).hexdigest()}
               for path, obj in ((LEAD_PATH, "objects/lead"), (CHILD_PATH, "objects/child"))}
    def ref(path, line):
        return {"path": path, "line": line}
    summary = {"subagents": {"spawned_count": 1, "verified_count": 1, "agents": [{
        "agent_id": CHILD, "parent_thread_id": LEAD, "agent_path": "/root/coder", "verified": True,
        "execution_verified": True, "completed": True,
        "spawn": {"raw_reference": ref(LEAD_PATH, 3)},
        "task_delivery": {"raw_reference": ref(CHILD_PATH, 4), "communication_reference": ref(CHILD_PATH, 5)},
        "final_answer": {"raw_reference": ref(CHILD_PATH, 7)},
        "completion": {"raw_reference": ref(CHILD_PATH, 8)},
        "parent_receipt": {"raw_reference": ref(LEAD_PATH, 4), "communication_reference": ref(LEAD_PATH, 5)},
    }]}}
    runtime = {"thread_id": LEAD, "session_id": LEAD,
               "native_rollouts": {"files": [{"path": p, "sha256": e["source_sha256"]} for p, e in entries.items()]}}
    return runtime, summary, entries, files


@pytest.mark.parametrize("text", ["completed", "completed\n", "\ncompleted", "\ncompleted\n", " completed ", "first\nsecond\n"])
def test_exact_nonempty_completion_preserves_outer_whitespace(text):
    runtime, summary, entries, files = native_fixture(text)
    _native_identities(runtime, summary, entries, files, RUN)


@pytest.mark.parametrize(("final", "completion"), [("completed", "different"), ("completed", "completed\n"),
                                                  ("\ncompleted", "completed"), (" completed ", "completed")])
def test_real_body_or_whitespace_difference_is_not_normalized_equal(final, completion):
    runtime, summary, entries, files = native_fixture(final, completion)
    with pytest.raises(EvidenceVerifyError, match="final answer and completion differ"):
        _native_identities(runtime, summary, entries, files, RUN)


def test_error_completion_cannot_be_verified():
    runtime, summary, entries, files = native_fixture(complete_error={"code": "SYNTHETIC_FAILURE"})
    with pytest.raises(EvidenceVerifyError, match="successful task_complete"):
        _native_identities(runtime, summary, entries, files, RUN)


def test_missing_final_answer_cannot_be_verified():
    runtime, summary, entries, files = native_fixture()
    summary["subagents"]["agents"][0]["final_answer"] = {}
    with pytest.raises(EvidenceVerifyError, match="evidence reference absent"):
        _native_identities(runtime, summary, entries, files, RUN)


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_empty_or_whitespace_only_final_answer_cannot_be_verified(text):
    runtime, summary, entries, files = native_fixture(text)
    with pytest.raises(EvidenceVerifyError, match="final answer and completion differ"):
        _native_identities(runtime, summary, entries, files, RUN)


@pytest.mark.parametrize(("final", "receipt"), [
    ("report", "report\n\n"), ("report", "report\nextra"), ("report", "prefixreport"),
    ("report", "reportextra"), ("report", " report"), ("report", "report "),
    ("report", "\nreport"), ("report", "report\n"), ("report\n", "report"),
    ("\nreport", "report"), ("report\n\n", "report\n"),
    ("first\nsecond", "first\nsecond\n"),
])
def test_parent_receipt_requires_exact_complete_final_body(final, receipt):
    runtime, summary, entries, files = native_fixture(final, receipt_body=receipt)
    with pytest.raises(EvidenceVerifyError, match="parent completion receipt absent"):
        _native_identities(runtime, summary, entries, files, RUN)
