import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

from benchmark.participant import NoPatchError, build_participant, extract_submission
from benchmark.runner import BenchmarkRunner, apply_patch


@pytest.fixture
def public_workspace(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    report = runner.prepare("A")
    assert report["overall_status"] == "PREPARED"
    return tmp_path / "runs" / report["run_id"] / "workspace"


def test_builder_copies_actual_buggy_public_workspace_only(public_workspace, tmp_path):
    (public_workspace / "hidden_tests").mkdir()
    (public_workspace / "hidden_tests/answer.py").write_text("PRIVATE SECRET")
    (public_workspace / "private.json").write_text("PRIVATE SECRET")
    (public_workspace / "reference.diff").write_text("PRIVATE SECRET")
    (public_workspace / "business.sqlite").write_bytes(b"PRIVATE DATABASE")
    participant = build_participant(public_workspace, tmp_path / "participant")
    for source in (public_workspace / "app").rglob("*.py"):
        assert (participant / source.relative_to(public_workspace)).read_bytes() == source.read_bytes()
    assert "snapshot=snapshot" in (participant / "app/service.py").read_text()
    assert (participant / "tests/public/test_episode_a.py").exists()
    assert not (participant / "business.sqlite").exists()
    assert not (participant / "private.json").exists()
    assert not (participant / "hidden_tests").exists()
    assert not (participant / "reference.diff").exists()
    assert not (participant / "benchmark").exists()
    assert not (participant / "evaluator").exists()
    assert "PRIVATE SECRET" not in "".join(path.read_text() for path in participant.rglob("*")
                                           if path.is_file() and ".git" not in path.parts)
    head = subprocess.run([shutil.which("git"), "-c", "safe.directory=*", "log", "--format=%s", "-1"],
                          cwd=participant, text=True, capture_output=True)
    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == "Public incident baseline"


def test_issue_uses_only_public_manifest_without_repair_hint(public_workspace, tmp_path):
    path = public_workspace / "public.json"
    manifest = json.loads(path.read_text())
    manifest["public_task"] = {"description": "PUBLIC UNIQUE DESCRIPTION", "constraints": ["PUBLIC CONSTRAINT"]}
    manifest["runtime"] = {"public_runtime": "TOPOLOGY MARKER"}
    manifest["initial_state"] = {"public_stock": 123}
    path.write_text(json.dumps(manifest))
    participant = build_participant(public_workspace, tmp_path / "participant")
    issue = (participant / "ISSUE.md").read_text()
    assert "PUBLIC UNIQUE DESCRIPTION" in issue
    assert "PUBLIC CONSTRAINT" in issue
    assert "TOPOLOGY MARKER" in issue
    assert "123" in issue
    assert "snapshot" not in issue.lower()
    assert "BEGIN IMMEDIATE" not in issue
    assert "reference" not in issue.lower()
    assert "inventory.py" not in issue


def test_roles_are_parseable_and_require_real_independent_work(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    names = set()
    for role in (participant / ".codex/agents").glob("*.toml"):
        configuration = tomllib.loads(role.read_text())
        assert set(configuration) == {"name", "description", "developer_instructions"}
        assert "snapshot" not in role.read_text().lower()
        assert "BEGIN IMMEDIATE" not in role.read_text()
        names.add(configuration["name"])
    assert names == {"investigator", "test_engineer", "reviewer"}
    instructions = (participant / "AGENTS.md").read_text()
    assert "at least two real subagents" in instructions
    assert "wait for their results" in instructions


@pytest.mark.parametrize("relative", ["app/service.py", "tests/public/test_episode_a.py", "public.json", "TASK.md"])
@pytest.mark.parametrize("link_type", ["symbolic", "hard"])
def test_builder_rejects_links_in_public_inputs(public_workspace, tmp_path, relative, link_type):
    path = public_workspace / relative
    external = tmp_path / "external"
    external.write_bytes(path.read_bytes())
    path.unlink()
    if link_type == "symbolic":
        path.symlink_to(external)
    else:
        os.link(external, path)
    with pytest.raises(ValueError, match="[Ll]ink|single-link"):
        build_participant(public_workspace, tmp_path / "participant")


@pytest.mark.parametrize("relative", ["app", "tests/public"])
def test_builder_rejects_linked_directories(public_workspace, tmp_path, relative):
    path = public_workspace / relative
    moved = tmp_path / "moved"
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="links"):
        build_participant(public_workspace, tmp_path / "participant")


def test_builder_rejects_non_regular_public_entries(public_workspace, tmp_path):
    os.mkfifo(public_workspace / "app/pipe.py")
    with pytest.raises(ValueError, match="Non-ordinary"):
        build_participant(public_workspace, tmp_path / "participant")


@pytest.mark.parametrize("content", [b"\0", b"\xff", b"x" * 2_000_001], ids=["nul", "invalid-utf8", "oversized"])
def test_builder_rejects_binary_or_oversized_sources(public_workspace, tmp_path, content):
    (public_workspace / "app/new.py").write_bytes(content)
    with pytest.raises(ValueError, match="UTF-8|byte limit|2 MB"):
        build_participant(public_workspace, tmp_path / "participant")


def test_builder_enforces_file_limit_and_new_destination(public_workspace, tmp_path):
    destination = tmp_path / "participant"
    destination.mkdir()
    with pytest.raises(ValueError, match="must be new"):
        build_participant(public_workspace, destination)
    for number in range(101):
        (public_workspace / "app" / f"added_{number}.py").write_text("pass\n")
    with pytest.raises(ValueError, match="100-file"):
        build_participant(public_workspace, tmp_path / "other")


def test_actual_submission_diff_applies_and_excludes_test_changes(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    source = participant / "app/service.py"
    source.write_text(source.read_text() + "\n# Actual participant change\n")
    (participant / "app/new_module.py").write_text("VALUE = 9\n")
    (participant / "app/events.py").unlink()
    (participant / "tests/public/new_test.py").write_text("# Public test evidence\n")
    (participant / "pytest.ini").write_text("[pytest]\naddopts = --collect-only\n")
    patch = tmp_path / "archive/submission.diff"
    metadata = extract_submission(public_workspace, participant, patch)
    assert metadata["sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert set(metadata["changed_files"]) == {"app/service.py", "app/new_module.py", "app/events.py"}
    assert metadata["public_test_changes"]["changed_files"] == ["tests/public/new_test.py"]
    assert "Public test evidence" not in patch.read_text()
    assert "pytest.ini" not in patch.read_text()
    candidate = tmp_path / "candidate"
    shutil.copytree(public_workspace / "app", candidate / "app")
    apply_patch(candidate, patch)
    for path in (participant / "app").rglob("*.py"):
        assert (candidate / path.relative_to(participant)).read_bytes() == path.read_bytes()
    assert not (candidate / "app/events.py").exists()


def test_submission_preserves_missing_final_newline(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    (participant / "app/new.py").write_bytes(b"ANSWER = 42")
    metadata = extract_submission(public_workspace, participant, tmp_path / "archive/submission.diff")
    candidate = tmp_path / "candidate"
    shutil.copytree(public_workspace / "app", candidate / "app")
    apply_patch(candidate, Path(metadata["patch_path"]))
    assert (candidate / "app/new.py").read_bytes() == b"ANSWER = 42"


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_submission_preserves_empty_python_file_changes(public_workspace, tmp_path, operation):
    if operation == "delete":
        (public_workspace / "app/empty.py").touch()
    participant = build_participant(public_workspace, tmp_path / "participant")
    if operation == "create":
        (participant / "app/empty.py").touch()
    else:
        (participant / "app/empty.py").unlink()
    metadata = extract_submission(public_workspace, participant, tmp_path / "archive/submission.diff")
    candidate = tmp_path / "candidate"
    shutil.copytree(public_workspace / "app", candidate / "app")
    apply_patch(candidate, Path(metadata["patch_path"]))
    assert (candidate / "app/empty.py").exists() == (operation == "create")
    if operation == "create":
        assert (candidate / "app/empty.py").read_bytes() == b""


def test_no_source_patch_still_preserves_public_test_evidence(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    (participant / "tests/public/new_test.py").write_text("# Actual independent test\n")
    patch = tmp_path / "archive/submission.diff"
    with pytest.raises(NoPatchError, match="no app Python source changes"):
        extract_submission(public_workspace, participant, patch)
    assert not patch.exists()
    metadata = json.loads((patch.parent / "submission_metadata.json").read_text())
    assert metadata["sha256"] is None
    assert metadata["changed_files"] == []
    assert metadata["public_test_changes"]["changed_files"] == ["tests/public/new_test.py"]
    assert "Actual independent test" in (patch.parent / "public_test_changes.diff").read_text()


@pytest.mark.parametrize("link_type", ["symbolic", "hard"])
def test_submission_rejects_links(public_workspace, tmp_path, link_type):
    participant = build_participant(public_workspace, tmp_path / "participant")
    path = participant / "app/service.py"
    external = tmp_path / "external"
    external.write_bytes(path.read_bytes())
    path.unlink()
    if link_type == "symbolic":
        path.symlink_to(external)
    else:
        os.link(external, path)
    with pytest.raises(ValueError, match="[Ll]ink|single-link"):
        extract_submission(public_workspace, participant, tmp_path / "archive/submission.diff")


def test_evidence_must_be_outside_participant_and_baseline(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    for root in (public_workspace, participant):
        with pytest.raises(ValueError, match="outside"):
            extract_submission(public_workspace, participant, root / "submission.diff")


def test_existing_evidence_is_not_overwritten(public_workspace, tmp_path):
    participant = build_participant(public_workspace, tmp_path / "participant")
    (participant / "app/added.py").write_text("pass\n")
    destination = tmp_path / "archive"
    destination.mkdir()
    (destination / "submission.diff").write_text("PREVIOUS EVIDENCE")
    with pytest.raises(ValueError, match="must be new"):
        extract_submission(public_workspace, participant, destination / "submission.diff")
    assert (destination / "submission.diff").read_text() == "PREVIOUS EVIDENCE"
