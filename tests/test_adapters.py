"""Contract checks for submission and disabled experience integration."""

from dataclasses import asdict
from hashlib import sha256
import json

import pytest

from integrations.agents import (
    AgentAdapter,
    Availability,
    CodexNativeAdapter,
    ExecutionContext,
    ExecutionStatus,
    ExecutionTrace,
    ManualSubmissionAdapter,
    SubmissionArtifact,
    SubmissionKind,
    TaskInput,
)
from integrations.experience import (
    DecisionKind,
    DisabledExperienceAdapter,
    ExperienceAdapter,
    ExperienceCandidate,
    ExperienceContext,
    ExperienceDecision,
    ExperienceEvidence,
    ExperienceOutcome,
    ExperienceQuery,
    ExperienceStatus,
    response_to_dict,
)


def agent_inputs(tmp_path):
    return (
        TaskInput("SMOKE-001", "1.0.0", "Restore stock exactly once on cancellation"),
        ExecutionContext("run-contract", str(tmp_path)),
    )


def test_manual_patch_is_received_without_applying_it(tmp_path):
    patch = tmp_path / "submission.diff"
    original = b"--- a/service.py\n+++ b/service.py\n@@ -1 +1 @@\n-bug\n+fix\n"
    patch.write_bytes(original)
    task, context = agent_inputs(tmp_path)
    adapter = ManualSubmissionAdapter(SubmissionArtifact(SubmissionKind.PATCH, str(patch)))

    result = adapter.execute(task, context)

    assert isinstance(adapter, AgentAdapter)
    assert result.status is ExecutionStatus.SUBMITTED
    assert result.submission.sha256 == sha256(original).hexdigest()
    assert patch.read_bytes() == original
    assert sorted(item.name for item in tmp_path.iterdir()) == ["submission.diff"]
    assert result.agent_data_availability is Availability.UNAVAILABLE
    assert result.agent_assignments is None
    assert result.agent_metrics is None
    assert result.trace[0].event_type == "submission.received"
    assert result.trace[0].source == "manual_submission"
    assert json.loads(json.dumps(result.to_dict()))["status"] == "SUBMITTED"


def test_manual_workspace_digest_is_repeatable_and_sensitive_to_contents(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "service.py"
    source.write_text("original", encoding="utf-8")
    task, context = agent_inputs(tmp_path)
    adapter = ManualSubmissionAdapter(SubmissionArtifact("workspace", str(workspace)))

    first = adapter.execute(task, context)
    second = adapter.execute(task, context)
    assert first.submission.sha256 == second.submission.sha256
    assert first.trace[0].event_id != second.trace[0].event_id

    source.write_text("changed", encoding="utf-8")
    changed = adapter.execute(task, context)
    assert first.submission.sha256 != changed.submission.sha256


def test_missing_submission_and_digest_mismatch_are_errors(tmp_path):
    task, context = agent_inputs(tmp_path)
    missing = ManualSubmissionAdapter(SubmissionArtifact("patch", str(tmp_path / "missing")))
    assert missing.execute(task, context).status is ExecutionStatus.ERROR
    patch = tmp_path / "submission.diff"
    patch.write_text("actual bytes", encoding="utf-8")
    wrong_digest = ManualSubmissionAdapter(SubmissionArtifact("patch", str(patch), "0" * 64))
    result = wrong_digest.execute(task, context)
    assert result.status is ExecutionStatus.ERROR
    assert result.submission is None
    assert result.errors


def test_manual_workspace_rejects_symlink_to_external_bytes(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    (workspace / "leak").symlink_to(outside)
    task, context = agent_inputs(tmp_path)
    result = ManualSubmissionAdapter(SubmissionArtifact("workspace", str(workspace))).execute(
        task, context
    )
    assert result.status is ExecutionStatus.ERROR
    assert "symbolic links" in result.errors[0]


def test_codex_native_execution_is_explicitly_unimplemented(tmp_path):
    adapter = CodexNativeAdapter()
    assert isinstance(adapter, AgentAdapter)
    with pytest.raises(NotImplementedError, match="NOT_IMPLEMENTED"):
        adapter.execute(*agent_inputs(tmp_path))


def test_trace_contract_has_required_observation_fields():
    trace = ExecutionTrace("run-contract", "runner", "workspace.prepared", {"files": 2})
    value = trace.to_dict()
    assert value["event_id"]
    assert value["timestamp"]
    assert value["run_id"] == "run-contract"
    assert value["source"] == "runner"
    assert value["event_type"] == "workspace.prepared"
    assert value["payload"] == {"files": 2}
    assert value["availability"] == "AVAILABLE"


def test_disabled_experience_contract_never_claims_activity():
    context = ExperienceContext("run-contract", "SMOKE-001", "1.0.0")
    query = ExperienceQuery(context, "What strategy matches the current topology?")
    candidate = ExperienceCandidate("candidate-contract", "Example strategy")
    decision = ExperienceDecision(context, candidate.experience_id, DecisionKind.ABSTAIN, "contract")
    outcome = ExperienceOutcome(context, "NOT_IMPLEMENTED")
    adapter = DisabledExperienceAdapter()
    assert isinstance(adapter, ExperienceAdapter)
    state_before = dict(vars(adapter))

    resolved = adapter.resolve_experience(query)
    evidence = adapter.build_evidence_bundle(context, (candidate,))
    recorded = adapter.record_decision(decision)
    submitted = adapter.submit_outcome(outcome)

    for response in (resolved, evidence, recorded, submitted):
        assert response.status is ExperienceStatus.DISABLED
        assert response.reason
        assert json.loads(json.dumps(response_to_dict(response)))["status"] == "DISABLED"
    assert resolved.candidates == ()
    assert evidence.bundle is None
    assert recorded.recorded is False
    assert recorded.decision_reference is None
    assert submitted.submitted is False
    assert submitted.outcome_reference is None
    assert vars(adapter) == state_before
    assert adapter.metadata()["hits"] is None
    assert adapter.metadata()["decisions"] is None
    assert adapter.metadata()["feedback"] is None


def test_verify_requires_actual_verification_steps():
    context = ExperienceContext("run-contract", "SMOKE-001", "1.0.0")
    with pytest.raises(ValueError, match="concrete verification steps"):
        ExperienceDecision(context, "candidate-contract", "VERIFY", "check applicability")
    decision = ExperienceDecision(
        context,
        "candidate-contract",
        "VERIFY",
        "Check the documented scope",
        verification_steps=("Run the independent multi-worker concurrency check",),
    )
    assert decision.decision is DecisionKind.VERIFY
    assert asdict(decision)["verification_steps"]


def test_verified_evidence_and_outcome_require_report_references():
    context = ExperienceContext("run-contract", "SMOKE-001", "1.0.0")
    with pytest.raises(ValueError, match="independent report reference"):
        ExperienceEvidence("source-run", verified=True)
    with pytest.raises(ValueError, match="independent report reference"):
        ExperienceOutcome(context, "PASS", independently_verified=True)
    with pytest.raises(ValueError, match="evaluation status"):
        ExperienceOutcome(context, "ASSUMED_SUCCESS")
