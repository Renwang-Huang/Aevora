"""Offline integrity/evidence review contracts; no native or model run claims."""
import hashlib
import json
from pathlib import Path

import pytest

from benchmark.participant import extract_submission
from benchmark.runner import BenchmarkRunner
from benchmark.submission import snapshot_source_tree
from integrations.agents import ExecutionResult, ExecutionStatus, SubmissionArtifact
from integrations.codex_agent import CodexConfig
from integrations.runtime_evidence import seal_inputs, seal_run


@pytest.mark.parametrize("mismatch", ["artifact_patch", "sealed_patch", "sealed_expected", "sealed_baseline", "sealed_file", "missing_extraction"])
def test_codex_submission_mismatch_cannot_start_hidden_evaluation(tmp_path, monkeypatch, mismatch):
    from integrations.codex_agent import CodexAgentAdapter
    import evaluator.runner as evaluator
    calls = []

    def forbidden_hidden_evaluation(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Hidden evaluator must not start for an integrity mismatch")

    def offline_contract(_self, _task, context):
        workspace = Path(context.workspace)
        archive = Path(context.constraints["archive"])
        baseline = Path(context.constraints["baseline"])
        source = workspace / "app/service.py"
        source.write_bytes(source.read_bytes() + b"\n# Offline integrity contract modification\n")
        evidence = extract_submission(baseline, workspace, archive / "submission.diff")
        artifact_digest = evidence["sha256"]
        if mismatch == "artifact_patch":
            artifact_digest = "0" * 64
        elif mismatch == "sealed_patch":
            evidence["sha256"] = "0" * 64
        elif mismatch == "sealed_expected":
            evidence["expected_tree_sha256"] = "0" * 64
        elif mismatch == "sealed_baseline":
            evidence["baseline_tree_sha256"] = "0" * 64
        elif mismatch == "sealed_file":
            first = sorted(evidence["expected_files_sha256"])[0]
            evidence["expected_files_sha256"][first] = "0" * 64
        return ExecutionResult(
            ExecutionStatus.SUBMITTED,
            SubmissionArtifact("patch", evidence["patch_path"], artifact_digest),
            runtime_metadata={"runtime_result": "PASS", "multi_agent_result": "PARTIAL",
                              "submission": None if mismatch == "missing_extraction" else evidence, "subagents": {"verified_count": 0,
                              "availability": "UNAVAILABLE"},
                              "test_fixture": "OFFLINE_INTEGRITY_CONTRACT_NOT_NATIVE_EVIDENCE"},
        )

    monkeypatch.setattr(CodexAgentAdapter, "execute", offline_contract)
    monkeypatch.setattr(evaluator, "evaluate", forbidden_hidden_evaluation)
    report = BenchmarkRunner(tmp_path / "runs").run_agent(
        "A", config=CodexConfig(tmp_path / "not-started", tmp_path / "unused-auth"))
    assert calls == []
    assert report["overall_status"] == "ERROR"
    assert report["submission_integrity_status"] == "ERROR"
    assert report["evaluation_result"] == "NOT_RUN"
    assert any("SUBMISSION_INTEGRITY_ERROR" in error for error in report["execution_errors"])


def test_rejected_manual_partial_patch_keeps_baseline_and_skips_hidden_evaluation(tmp_path, monkeypatch):
    import evaluator.runner as evaluator
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("A")
    archive = tmp_path / "runs" / prepared["run_id"]
    initial = snapshot_source_tree(archive / "workspace")
    patch = tmp_path / "partial.diff"
    patch.write_text("--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-INVALID\n+CHANGED\n")
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Hidden evaluation may not follow rejected patch")
    monkeypatch.setattr(evaluator, "evaluate", forbidden)
    report = runner.evaluate("A", patch, run_id=prepared["run_id"])
    assert calls == []
    assert report["overall_status"] == "ERROR"
    assert "EVALUATE" not in report["lifecycle"]
    assert snapshot_source_tree(archive / "workspace") == initial
    assert snapshot_source_tree(archive / "candidate") == initial


def test_exact_stdin_and_initial_files_are_sealed_before_public_tree_changes(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "app").mkdir(parents=True)
    source = workspace / "app/service.py"
    source.write_bytes(b"PUBLIC_BASELINE = 1\n")
    (workspace / "ISSUE.md").write_text("Public incident")
    archive = tmp_path / "archive"
    archive.mkdir()
    prompt = b"Exact public input\n\nDelegate independent tasks.\n"
    record = seal_inputs(workspace, archive, prompt)
    source.write_bytes(b"PUBLIC_REPAIR = 2\n")
    assert (archive / "exact_stdin.txt").read_bytes() == prompt
    assert record["exact_stdin_sha256"] == hashlib.sha256(prompt).hexdigest()
    assert (archive / "sealed_public_inputs/app/service.py").read_bytes() == b"PUBLIC_BASELINE = 1\n"
    assert record["files"]["app/service.py"] == hashlib.sha256(b"PUBLIC_BASELINE = 1\n").hexdigest()
    assert json.loads((archive / "input_seal.json").read_text()) == record
    assert "not third-party immutable" in record["policy"]
    with pytest.raises(FileExistsError):
        seal_inputs(workspace, archive, b"Replacement input")
    assert (archive / "exact_stdin.txt").read_bytes() == prompt


@pytest.mark.parametrize("kind", ["symbolic", "hard"])
def test_initial_input_sealing_rejects_links(tmp_path, kind):
    import os
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "ordinary-public-file"
    source.write_text("Public marker")
    target = workspace / "ISSUE.md"
    if kind == "symbolic":
        target.symlink_to(source)
    else:
        os.link(source, target)
    archive = tmp_path / "archive"
    archive.mkdir()
    with pytest.raises(ValueError):
        seal_inputs(workspace, archive, b"Public input")
    assert not (archive / "input_seal.json").exists()


def test_run_seal_is_append_only_and_binds_original_input_seal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "ISSUE.md").write_text("Public incident")
    archive = tmp_path / "archive"
    archive.mkdir()
    seal_inputs(workspace, archive, b"Exact input")
    (archive / "evaluation_report.json").write_text('{"test_fixture":"NOT_AN_EVALUATION"}\n')
    record = seal_run(archive)
    assert record["previous_seal_sha256"] == hashlib.sha256((archive / "input_seal.json").read_bytes()).hexdigest()
    assert record["files"]["evaluation_report.json"] == hashlib.sha256((archive / "evaluation_report.json").read_bytes()).hexdigest()
    assert "no third-party attestation" in record["immutability"]
    before = (archive / "run_evidence_manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        seal_run(archive)
    assert (archive / "run_evidence_manifest.json").read_bytes() == before
