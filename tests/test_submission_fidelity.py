"""Submission integrity regressions: exact trees, isolation and atomic failure."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

from benchmark.participant import _diff
import benchmark.submission as submission
from benchmark.submission import (
    SubmissionIntegrityError, apply_verified_patch, expected_tree_from_patch,
    snapshot_source_tree, source_tree_sha256,
)


def write_tree(root, tree):
    (root / "app").mkdir(parents=True, exist_ok=True)
    for name, content in tree.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def patch_file(root, before, after):
    patch, _ = _diff({name.removeprefix("app/"): data for name, data in before.items()},
                     {name.removeprefix("app/"): data for name, data in after.items()}, "app")
    path = root / "submission.diff"
    path.write_text(patch, encoding="utf-8")
    return path


@pytest.fixture(params=["maintainer_root", "nested", "other_parent", "independent_non_git"])
def layout(request, tmp_path):
    if request.param == "independent_non_git":
        independent = Path("/tmp/phase3_5_validation")
        independent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="submission-", dir=independent) as temporary:
            root = Path(temporary)
            result = subprocess.run([submission._git_executable(), "rev-parse", "--show-toplevel"],
                                    cwd=root, env={"PATH": "/usr/bin:/bin", "HOME": str(root)},
                                    capture_output=True)
            assert result.returncode != 0
            yield root
    elif request.param == "other_parent":
        git = submission._git_executable()
        parent = tmp_path / "other-repository"
        parent.mkdir()
        empty_template = tmp_path / "empty-template"
        empty_template.mkdir()
        result = subprocess.run([git, "init", "--quiet", "--template=" + str(empty_template)],
                                cwd=parent, capture_output=True,
                                env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                     "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        assert result.returncode == 0, result.stderr
        root = parent / "deep" / "run"
        root.mkdir(parents=True)
        yield root
    else:
        root = tmp_path if request.param == "maintainer_root" else tmp_path / "deep" / "run"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.mark.parametrize("operation", ["empty_create", "empty_delete", "create", "delete", "modify", "mixed"])
def test_exact_tree_across_git_layouts(layout, operation, tmp_path):
    before = {"app/service.py": b"VALUE = 1\n", "app/delete.py": b"OLD = 3\n", "app/empty.py": b""}
    after = dict(before)
    if operation == "empty_create":
        after["app/new_empty.py"] = b""
    elif operation == "empty_delete":
        del after["app/empty.py"]
    elif operation == "create":
        after["app/nested/new.py"] = b"NEW = 2\n"
    elif operation == "delete":
        del after["app/delete.py"]
    elif operation == "modify":
        after["app/service.py"] = b"VALUE = 9\n"
    else:
        after["app/nested/new.py"] = b"NO_NEWLINE = 4"
        after["app/new_empty.py"] = b""
        after["app/service.py"] = b"VALUE = 9\n"
        del after["app/delete.py"]
        del after["app/empty.py"]
    candidate = layout / "candidate"
    write_tree(candidate, before)
    (candidate / "PUBLIC.txt").write_text("unchanged public material")
    patch = patch_file(layout, before, after)
    metadata = apply_verified_patch(candidate, patch, expected_tree=after)
    (tmp_path / "integrity_metadata.json").write_text(json.dumps({
        "layout": str(layout), "operation": operation, "integrity": metadata,
        "original_submission_files_sha256": {name: hashlib.sha256(value).hexdigest() for name, value in sorted(after.items())},
    }, indent=2, sort_keys=True) + "\n")
    assert snapshot_source_tree(candidate) == after
    assert (candidate / "PUBLIC.txt").read_text() == "unchanged public material"
    assert metadata["baseline_tree_sha256"] == source_tree_sha256(before)
    assert metadata["patch_sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert metadata["expected_tree_sha256"] == metadata["applied_candidate_tree_sha256"] == source_tree_sha256(after)
    assert {row["path"] for row in metadata["changed_files"]} == {
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    assert not list(layout.glob(".orderflow-submission-*"))


@pytest.mark.parametrize("before,after", [
    (b"OLD", b"NEW"), (b"OLD\n", b"NEW"), (b"OLD", b"NEW\n"),
    (b"a\r\nb\r\n", b"a\r\nc\r\n"),
    (b"a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n", b"Z\nb\nc\nd\ne\nf\ng\nh\ni\nK\n"),
])
def test_missing_final_newline_crlf_and_multiple_hunks(tmp_path, before, after):
    initial = {"app/service.py": before}
    final = {"app/service.py": after}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    apply_verified_patch(candidate, patch_file(tmp_path, initial, final))
    assert snapshot_source_tree(candidate) == final


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_standard_git_empty_file_headers_without_text_headers(tmp_path, operation):
    empty_sha = hashlib.sha1(b"blob 0\0").hexdigest()
    before = {"app/service.py": b"pass\n"}
    after = dict(before)
    if operation == "create":
        after["app/empty.py"] = b""
        mode = "new file mode 100644"
        index = f"index {'0' * 40}..{empty_sha}"
    else:
        before["app/empty.py"] = b""
        mode = "deleted file mode 100644"
        index = f"index {empty_sha}..{'0' * 40}"
    candidate = tmp_path / "candidate"
    write_tree(candidate, before)
    patch = tmp_path / "submission.diff"
    patch.write_text(f"diff --git a/app/empty.py b/app/empty.py\n{mode}\n{index}\n")
    apply_verified_patch(candidate, patch, expected_tree=after)
    assert snapshot_source_tree(candidate) == after


@pytest.mark.parametrize("bad_path", [
    "app/../../private.py", "app/a/../service.py", "app//service.py", "app/./service.py",
    "/app/service.py", "other/service.py", "app/.git/service.py", "app/service.txt",
    "app\\service.py", "app/white space.py",
])
def test_rejects_unsafe_patch_paths_without_baseline_changes(tmp_path, bad_path):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = tmp_path / "submission.diff"
    patch.write_text(f"--- a/{bad_path}\n+++ b/{bad_path}\n@@ -1 +1 @@\n-pass\n+CHANGED\n")
    with pytest.raises(SubmissionIntegrityError):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


@pytest.mark.parametrize("body", [
    "GIT binary patch\nliteral 3\nabc\n", "Binary files a/app/service.py and b/app/service.py differ\n",
    "rename from app/service.py\nrename to app/renamed.py\n",
    "copy from app/service.py\ncopy to app/copied.py\n",
    "new file mode 120000\n", "new file mode 100755\n", "old mode 100644\nnew mode 100755\n",
    "index 1234567..9876543 100644\n", "unexpected header\n",
])
def test_rejects_unsupported_git_operations(tmp_path, body):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = tmp_path / "submission.diff"
    patch.write_text("diff --git a/app/service.py b/app/service.py\n" + body +
                     "--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-pass\n+CHANGED\n")
    with pytest.raises(SubmissionIntegrityError):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


@pytest.mark.parametrize("content", [
    "", "--- a/app/service.py\n", "--- a/app/service.py\n+++ b/app/service.py\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -1,2 +1,2 @@\n-pass\n+CHANGED\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-WRONG\n+CHANGED\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +2 @@\n-pass\n+CHANGED\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-pass\n+CHANGED",
    "--- a/app/service.py\n+++ b/app/renamed.py\n@@ -1 +1 @@\n-pass\n+CHANGED\n",
    "--- /dev/null\n+++ /dev/null\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n pass\n",
    "--- a/app/service.py\n+++ b/app/service.py\n@@ -9 +9 @@\n-pass\n+CHANGED\n",
])
def test_rejects_invalid_truncated_or_noop_hunks(tmp_path, content):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = tmp_path / "submission.diff"
    patch.write_text(content)
    with pytest.raises(SubmissionIntegrityError):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


def test_rejects_partial_patch_and_duplicate_path_atomically(tmp_path):
    initial = {"app/service.py": b"pass\n", "app/other.py": b"old\n"}
    final = {"app/service.py": b"CHANGED\n", "app/other.py": b"new\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, final)
    good = patch.read_bytes()
    for bad in (good.replace(b"-old\n", b"-INVALID\n"), good + good):
        patch.write_bytes(bad)
        with pytest.raises(SubmissionIntegrityError):
            apply_verified_patch(candidate, patch)
        assert snapshot_source_tree(candidate) == initial


@pytest.mark.parametrize("target,kind", [
    ("app/service.py", "symlink"), ("app/service.py", "hardlink"),
    ("app/cache.bin", "symlink"), ("app/cache.bin", "hardlink"),
    ("app/pipe.py", "fifo"), ("app/nested", "symlink_dir"),
])
def test_rejects_source_links_and_special_entries(tmp_path, target, kind):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    external = tmp_path / "external"
    external.write_bytes(b"PRIVATE\n")
    path = candidate / target
    if path.exists():
        path.unlink()
    if kind == "hardlink":
        os.link(external, path)
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "symlink_dir":
        path.symlink_to(tmp_path, target_is_directory=True)
    else:
        path.symlink_to(external)
    patch = patch_file(tmp_path, initial, {"app/service.py": b"CHANGED\n"})
    with pytest.raises(SubmissionIntegrityError):
        apply_verified_patch(candidate, patch)
    assert external.read_bytes() == b"PRIVATE\n"


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_rejects_linked_patch_files(tmp_path, kind):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, {"app/service.py": b"CHANGED\n"})
    linked = tmp_path / "linked.diff"
    if kind == "symlink":
        linked.symlink_to(patch)
    else:
        os.link(patch, linked)
    with pytest.raises(SubmissionIntegrityError):
        apply_verified_patch(candidate, linked)
    assert snapshot_source_tree(candidate) == initial


def test_rejects_source_path_conflict_before_publication(tmp_path):
    initial = {"app/service.py": b"pass\n", "app/conflict.py": b"OLD\n"}
    final = {**initial, "app/conflict.py/new.py": b"NEW\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, final)
    with pytest.raises(SubmissionIntegrityError, match="conflicts"):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


def test_independent_expected_tree_is_enforced(tmp_path):
    initial = {"app/service.py": b"pass\n"}
    final = {"app/service.py": b"CHANGED\n"}
    candidate = tmp_path / "candidate"
    participant = tmp_path / "participant"
    write_tree(candidate, initial)
    write_tree(participant, final)
    cache = participant / "app/__pycache__"
    cache.mkdir()
    (cache / "service.pyc").write_bytes(b"ordinary unsubmitted cache")
    patch = patch_file(tmp_path, initial, final)
    with pytest.raises(SubmissionIntegrityError, match="independently collected"):
        apply_verified_patch(candidate, patch, expected_tree=initial)
    assert snapshot_source_tree(candidate) == initial
    result = apply_verified_patch(candidate, patch, expected_tree=participant)
    assert result["expected_tree_sha256"] == source_tree_sha256(final)


def test_clean_git_ignores_parent_environment_config_attributes_and_hooks(tmp_path, monkeypatch):
    initial = {"app/service.py": b"pass\n"}
    final = {"app/service.py": b"CHANGED\n", "app/empty.py": b""}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, final)
    marker = tmp_path / "HOOK_RAN"
    hookdir = tmp_path / "hooks"
    hookdir.mkdir()
    (hookdir / "post-applypatch").write_text(f"#!/bin/sh\ntouch {marker}\n")
    (hookdir / "post-applypatch").chmod(0o755)
    attributes = tmp_path / "attributes"
    attributes.write_text("*.py text eol=crlf\n")
    config = tmp_path / "host-config"
    config.write_text(f"[core]\n\tautocrlf = true\n\thooksPath = {hookdir}\n\tattributesFile = {attributes}\n")
    for key, value in {
        "GIT_DIR": str(tmp_path / "unrelated.git"), "GIT_WORK_TREE": str(tmp_path / "wrong-tree"),
        "GIT_INDEX_FILE": str(tmp_path / "wrong-index"), "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_SYSTEM": str(config), "GIT_TEMPLATE_DIR": str(hookdir),
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.autocrlf", "GIT_CONFIG_VALUE_0": "true",
        "HOME": str(tmp_path), "PATH": "/malicious/nonexistent",
    }.items():
        monkeypatch.setenv(key, value)
    result = apply_verified_patch(candidate, patch)
    assert result["status"] == "PASS"
    assert snapshot_source_tree(candidate) == final
    assert not marker.exists()
    assert not (tmp_path / "wrong-index").exists()


def test_git_success_without_actual_changes_is_rejected(tmp_path, monkeypatch):
    initial = {"app/service.py": b"pass\n"}
    final = {**initial, "app/empty.py": b""}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, final)
    original = submission._git_run
    def silent_skip(git, worktree, git_dir, home, args):
        if args[0] == "apply":
            return ""
        return original(git, worktree, git_dir, home, args)
    monkeypatch.setattr(submission, "_git_run", silent_skip)
    with pytest.raises(SubmissionIntegrityError, match="actual candidate tree"):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


def test_no_unverified_fallback_when_atomic_publication_unavailable(tmp_path, monkeypatch):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, {"app/service.py": b"CHANGED\n"})
    def unavailable(*_args):
        raise SubmissionIntegrityError("atomic publication unavailable")
    monkeypatch.setattr(submission, "_exchange", unavailable)
    with pytest.raises(SubmissionIntegrityError, match="unavailable"):
        apply_verified_patch(candidate, patch)
    assert snapshot_source_tree(candidate) == initial


def test_failed_publication_verification_rolls_back_original_app(tmp_path, monkeypatch):
    initial = {"app/service.py": b"pass\n"}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, {"app/service.py": b"CHANGED\n"})
    original = submission._exchange
    calls = 0
    def changed_during_publish(left, right):
        nonlocal calls
        calls += 1
        original(left, right)
        if calls == 1:
            (left / "service.py").write_bytes(b"interference\n")
    monkeypatch.setattr(submission, "_exchange", changed_during_publish)
    with pytest.raises(SubmissionIntegrityError, match="Published candidate"):
        apply_verified_patch(candidate, patch)
    assert calls == 2
    assert snapshot_source_tree(candidate) == initial


def test_tree_digest_covers_paths_and_empty_files():
    assert source_tree_sha256({}) != source_tree_sha256({"app/empty.py": b""})
    assert source_tree_sha256({"app/a.py": b"x"}) != source_tree_sha256({"app/b.py": b"x"})
    assert source_tree_sha256({"app/a.py": b"x"}) != source_tree_sha256({"app/a.py": b"x\n"})


def test_parser_limits_and_binary_payloads():
    initial = {"app/service.py": b"pass\n"}
    for patch in (b"\0", b"\xff\n", b"x" * 1_000_001):
        with pytest.raises(SubmissionIntegrityError):
            expected_tree_from_patch(initial, patch)


def test_hunk_payload_that_looks_like_headers_is_not_treated_as_a_path(tmp_path):
    from benchmark.runner import apply_patch
    initial = {"app/service.py": b'TEXT = """\n-- public text\n++ old text\n"""\n'}
    final = {"app/service.py": b'TEXT = """\n++ new text\n"""\n'}
    candidate = tmp_path / "candidate"
    write_tree(candidate, initial)
    patch = patch_file(tmp_path, initial, final)
    assert b"--- public text\n" in patch.read_bytes()
    assert b"+++ new text\n" in patch.read_bytes()
    apply_patch(candidate, patch, expected_tree=final)
    assert snapshot_source_tree(candidate) == final
