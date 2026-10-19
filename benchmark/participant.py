"""Build public participant workspaces and extract actual source submissions.

This module runs trusted file operations and Git only. It never imports or
executes candidate business code, and it does not select a repair strategy.
The caller keeps the baseline and generated evidence outside the participant
execution environment.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from typing import Any


MAX_SOURCE_FILES = 100
MAX_SOURCE_BYTES = 2_000_000
MAX_TREE_ENTRIES = 1_000
MAX_PUBLIC_DOCUMENT_BYTES = 100_000
MAX_PATCH_BYTES = 1_000_000
SAFE_PYTHON_PATH = re.compile(r"[A-Za-z0-9_/.-]+\.py\Z")


class NoPatchError(ValueError):
    """No business source change was produced; public test evidence is retained."""


def _safe_parents(path: Path) -> Path:
    path = path.absolute()
    for parent in reversed((path, *path.parents)):
        try:
            mode = parent.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symbolic links are forbidden in participant paths: {parent}")
    return path


def _directory(path: Path) -> Path:
    path = _safe_parents(path)
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError(f"Expected an ordinary directory: {path}")
    return path


def _read_regular(path: Path, byte_limit: int) -> bytes:
    _safe_parents(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"Expected a single-link ordinary file: {path}")
    if before.st_size > byte_limit:
        raise ValueError(f"Public/source file exceeds its byte limit: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError(f"Expected a single-link ordinary file: {path}")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError(f"File changed during source collection: {path}")
        content = source.read(byte_limit + 1)
        after = os.fstat(source.fileno())
    if len(content) > byte_limit:
        raise ValueError(f"Public/source file exceeds its byte limit: {path}")
    if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed during source collection: {path}")
    if b"\0" in content:
        raise ValueError(f"Only UTF-8 text source files are accepted: {path}")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Only UTF-8 text source files are accepted: {path}") from error
    return content


def _python_tree(path: Path, *, missing_ok: bool = False) -> dict[str, bytes]:
    _safe_parents(path)
    if not path.exists():
        if missing_ok:
            return {}
        raise ValueError(f"Missing public/source directory: {path}")
    _directory(path)
    contents: dict[str, bytes] = {}
    total = 0
    for entry_count, item in enumerate(path.rglob("*"), start=1):
        if entry_count > MAX_TREE_ENTRIES:
            raise ValueError("Participant source tree exceeds its entry limit")
        mode = item.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f"Non-ordinary entry is forbidden: {item}")
        if stat.S_ISDIR(mode):
            continue
        # Reject links even when the file extension is outside the allowlist.
        if item.lstat().st_nlink != 1:
            raise ValueError(f"Hard links are forbidden: {item}")
        if item.suffix != ".py":
            continue
        relative = item.relative_to(path).as_posix()
        if not SAFE_PYTHON_PATH.fullmatch(relative) or any(part in {".", ".."} for part in Path(relative).parts):
            raise ValueError(f"Unsafe Python submission path: {relative}")
        content = _read_regular(item, MAX_SOURCE_BYTES)
        total += len(content)
        contents[relative] = content
        if total > MAX_SOURCE_BYTES or len(contents) > MAX_SOURCE_FILES:
            raise ValueError("Participant source exceeds the 100-file / 2 MB limit")
    return contents


def _write_tree(directory: Path, contents: dict[str, bytes]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for relative, content in contents.items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _public_issue(manifest: dict[str, Any]) -> str:
    task = manifest.get("public_task")
    if not isinstance(task, dict) or not isinstance(task.get("description"), str):
        raise ValueError("Public manifest must contain a public task description")
    constraints = task.get("constraints", [])
    if not isinstance(constraints, list) or any(not isinstance(item, str) for item in constraints):
        raise ValueError("Public task constraints must be strings")
    sections = [
        f"# OrderFlow Incident — {manifest.get('id', 'UNAVAILABLE')}",
        "", task["description"], "", "## Public constraints", "",
        *(f"- {constraint}" for constraint in constraints),
        "", "## Public runtime requirements", "",
        "```json", json.dumps(manifest.get("runtime", {}), indent=2, ensure_ascii=False), "```",
        "", "## Public initial state", "",
        "```json", json.dumps(manifest.get("initial_state", {}), indent=2, ensure_ascii=False), "```",
        "", "Investigate the reported issue, implement your own repair, and add useful public regression tests.",
        "The initial public tests are in tests/public/. Only business Python source changes under app/ are submitted for independent evaluation.",
        "",
    ]
    return "\n".join(sections)


ROLES = {
    "investigator": (
        "Investigate the reported incident using public code and return evidence to the lead.",
        "Independently inspect the public business code and reported symptoms. Explain your hypotheses with file and line evidence. Do not edit shared source unless the lead explicitly delegates ownership. Do not spawn or delegate to subagents; return your findings and uncertainty directly to the lead. Do not claim tests you did not execute.",
    ),
    "test_engineer": (
        "Independently reproduce the public incident and propose regression coverage.",
        "Use only the public issue, public source and public tests. Independently attempt to reproduce the reported behavior and identify useful regression tests. Do not spawn or delegate to subagents; report actual commands and results directly to the lead. Coordinate ownership before modifying shared files; do not change task requirements or fabricate outcomes.",
    ),
    "reviewer": (
        "Review the proposed changes for correctness and regressions independently.",
        "Independently review the proposed patch against the public issue and API constraints. Check business invariants and potential regressions, and report concrete findings directly to the lead. Do not spawn or delegate to subagents. Do not edit shared files without an explicit delegation. Treat unexecuted checks as unavailable.",
    ),
}

PARTICIPANT_INSTRUCTIONS = """# Participant working instructions

Read ISSUE.md, public.json, TASK.md, app/ and tests/public/ as the task inputs.
Use Codex native subagent tools for independent work. Delegate distinct tasks to
at least two real subagents, wait for their results, and incorporate their actual
findings before producing the final submission. Investigator, test engineer and
reviewer role instructions are provided in .codex/agents/. A textual claim about
delegation is not evidence of native subagent execution.

For this controlled runtime, use exactly two child tasks and deliver each task
explicitly: call `spawn_agent` with `fork_turns="none"`, then `send_message` to
the returned child path with the same task text. Never use `fork_turns="all"`.
Wait for both child terminal results before implementing the repair.

Only the lead agent may delegate. A spawned investigator, test engineer or
reviewer must not spawn another agent; each child returns its result directly
to the lead. This prevents recursive child trees and keeps the pre-registered
role count fixed.

The lead coordinates shared-file ownership. Independent investigation may run
in parallel, while each source file has one writer at a time. The lead may
implement the repair after investigation and request independent review.

Preserve the public business APIs and requirements. Develop your own solution,
retain concurrent business capacity, and add useful public regression tests.
Run public tests with `python3 -m unittest discover -s tests/public -v`.
Do not fabricate test records or disable requirements to report success.
State executed commands, limitations and remaining issues in the final result.
Only actual app/**/*.py changes will be submitted to independent evaluation;
public test modifications are retained separately as execution evidence.
"""

SINGLE_PARTICIPANT_INSTRUCTIONS = """# Participant working instructions

Read ISSUE.md, public.json, TASK.md, app/ and tests/public/ as the task inputs.
Investigate, implement, test and submit this incident in this single-agent
session. Native subagent tools are disabled by the runtime configuration.

Preserve the public business APIs and requirements. Develop your own solution,
retain concurrent business capacity, and add useful public regression tests.
Run public tests with `python3 -m unittest discover -s tests/public -v`.
Do not fabricate test records or disable requirements to report success.
State executed commands, limitations and remaining issues in the final result.
Only actual app/**/*.py changes will be submitted to independent evaluation;
public test modifications are retained separately as execution evidence.
"""

ONE_CHILD_PARTICIPANT_INSTRUCTIONS = """# Participant working instructions

Read ISSUE.md, public.json, TASK.md, app/ and tests/public/ as the task inputs.
This is a controlled single-child smoke. The lead is responsible for any
runtime-provided delegation. If you are the child, you must never call
`spawn_agent`, `send_message`, `followup_task`, `wait_agent`, or any other
collaboration tool; perform the read-only task in CHILD_TASK.md and return
directly to the lead. Do not delegate to any other agent. After the child
returns, investigate and implement the repair in the lead.

Preserve the public business APIs and requirements. Develop your own solution,
retain concurrent business capacity, and add useful public regression tests.
Run public tests with `python3 -m unittest discover -s tests/public -v`.
Do not fabricate test records or disable requirements to report success.
State executed commands, limitations and remaining issues in the final result.
Only actual app/**/*.py changes will be submitted to independent evaluation;
public test modifications are retained separately as execution evidence.
"""


def _initialize_public_git(destination: Path) -> None:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is required to initialize the participant baseline")
    # Do not consult maintainer global/system config, hooks, credentials or env.
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(destination),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "OrderFlow Participant Baseline",
        "GIT_AUTHOR_EMAIL": "participant@orderflow.invalid",
        "GIT_COMMITTER_NAME": "OrderFlow Participant Baseline",
        "GIT_COMMITTER_EMAIL": "participant@orderflow.invalid",
        "LC_ALL": "C.UTF-8",
    }
    commands = ([git, "-c", "init.defaultBranch=participant", "init", "-q"],
                [git, "-c", "core.hooksPath=/dev/null", "add", "--", "."],
                [git, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Public incident baseline"])
    for command in commands:
        result = subprocess.run(command, cwd=destination, env=environment, text=True,
                                capture_output=True, timeout=15)
        if result.returncode:
            raise RuntimeError(f"Participant Git initialization failed: {result.stderr.strip()}")


def build_participant(source_workspace: Path, destination: Path, *, agent_mode: str = "multi",
                      child_budget: int | None = None) -> Path:
    """Copy a fresh public-only workspace; never copy host private/root sources."""
    if agent_mode not in {"single", "multi"}:
        raise ValueError("Participant agent mode must be single or multi")
    if child_budget is not None and (type(child_budget) is not int or not 0 <= child_budget <= 8):
        raise ValueError("Participant child budget must be an integer in [0, 8]")
    source_workspace = _directory(Path(source_workspace))
    destination = _safe_parents(Path(destination))
    if destination.exists():
        raise ValueError("Participant destination must be new")
    app = _python_tree(source_workspace / "app")
    if "service.py" not in app:
        raise ValueError("Public workspace must contain app/service.py")
    tests = _python_tree(source_workspace / "tests/public")
    public_bytes = _read_regular(source_workspace / "public.json", MAX_PUBLIC_DOCUMENT_BYTES)
    task_bytes = _read_regular(source_workspace / "TASK.md", MAX_PUBLIC_DOCUMENT_BYTES)
    try:
        manifest = json.loads(public_bytes)
    except json.JSONDecodeError as error:
        raise ValueError("Public manifest must contain valid JSON") from error
    if not isinstance(manifest, dict):
        raise ValueError("Public manifest must be an object")
    issue = _public_issue(manifest)
    destination.mkdir(parents=True)
    _write_tree(destination / "app", app)
    _write_tree(destination / "tests/public", tests)
    (destination / "public.json").write_bytes(public_bytes)
    (destination / "TASK.md").write_bytes(task_bytes)
    (destination / "ISSUE.md").write_text(issue, encoding="utf-8")
    instructions = (
        ONE_CHILD_PARTICIPANT_INSTRUCTIONS
        if agent_mode == "multi" and child_budget == 1
        else PARTICIPANT_INSTRUCTIONS if agent_mode == "multi"
        else SINGLE_PARTICIPANT_INSTRUCTIONS
    )
    (destination / "AGENTS.md").write_text(instructions, encoding="utf-8")
    roles = destination / ".codex/agents"
    if agent_mode == "multi" and child_budget != 1:
        roles.mkdir(parents=True)
    for name, (description, instructions) in (
        ROLES.items() if agent_mode == "multi" and child_budget != 1 else ()
    ):
        # JSON string syntax is also valid TOML basic string syntax.
        (roles / f"{name}.toml").write_text(
            f"name = {json.dumps(name)}\n"
            f"description = {json.dumps(description)}\n"
            f"developer_instructions = {json.dumps(instructions)}\n", encoding="utf-8")
    _initialize_public_git(destination)
    return destination


def _diff(before: dict[str, bytes], after: dict[str, bytes], prefix: str) -> tuple[str, list[str]]:
    patches = []
    changed = []
    for relative in sorted(before.keys() | after.keys()):
        if before.get(relative) == after.get(relative):
            continue
        changed.append(f"{prefix}/{relative}")
        old = before.get(relative, b"").decode("utf-8").splitlines(keepends=True)
        new = after.get(relative, b"").decode("utf-8").splitlines(keepends=True)
        old_path = f"a/{prefix}/{relative}" if relative in before else "/dev/null"
        new_path = f"b/{prefix}/{relative}" if relative in after else "/dev/null"
        lines = list(difflib.unified_diff(old, new, fromfile=old_path, tofile=new_path))
        if not lines:
            # Empty-file creation/deletion has no text hunk. Ordinary Git mode
            # headers plus paths preserve the real change through git apply.
            empty_blob = hashlib.sha1(b"blob 0\0").hexdigest()
            mode = "new file mode 100644" if relative not in before else "deleted file mode 100644"
            index = f"index {'0' * 40}..{empty_blob}" if relative not in before else f"index {empty_blob}..{'0' * 40}"
            lines = [f"diff --git a/{prefix}/{relative} b/{prefix}/{relative}\n",
                     mode + "\n", index + "\n", f"--- {old_path}\n", f"+++ {new_path}\n"]
        for line in lines:
            patches.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return "".join(patches), changed


def extract_submission(baseline: Path, participant: Path, patch_path: Path) -> dict[str, Any]:
    """Extract the actual app diff and archive public tests separately.

    Returns sha256, changed_files, patch_path and public_test_changes. No app
    change raises NoPatchError after preserving test evidence and metadata.
    Caller must keep patch_path and baseline outside the participant mount.
    """
    baseline = _directory(Path(baseline))
    participant = _directory(Path(participant))
    patch_path = _safe_parents(Path(patch_path))
    for untrusted_root in (baseline, participant):
        if patch_path == untrusted_root or untrusted_root in patch_path.parents:
            raise ValueError("Submission evidence must be outside baseline and participant workspaces")
    before = _python_tree(baseline / "app")
    after = _python_tree(participant / "app", missing_ok=True)
    test_before = _python_tree(baseline / "tests/public", missing_ok=True)
    test_after = _python_tree(participant / "tests/public", missing_ok=True)
    patch, changed = _diff(before, after, "app")
    test_patch, test_changed = _diff(test_before, test_after, "tests/public")
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise ValueError("Extracted patch exceeds the 1 MB submission limit")
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    test_path = patch_path.parent / "public_test_changes.diff"
    metadata_path = patch_path.parent / "submission_metadata.json"
    for target in (patch_path, test_path, metadata_path):
        _safe_parents(target)
        if target.exists():
            raise ValueError("Submission evidence destination must be new")
    test_path.write_text(test_patch, encoding="utf-8")
    from benchmark.submission import source_tree_sha256
    metadata = {
        "baseline_tree_sha256": source_tree_sha256({"app/" + key: value for key, value in before.items()}),
        "expected_tree_sha256": source_tree_sha256({"app/" + key: value for key, value in after.items()}),
        "expected_files_sha256": {"app/" + key: hashlib.sha256(value).hexdigest() for key, value in after.items()},
        "patch_path": str(patch_path),
        "sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest() if changed else None,
        "changed_files": changed,
        "public_test_changes": {"path": str(test_path), "changed_files": test_changed,
                                "sha256": hashlib.sha256(test_patch.encode("utf-8")).hexdigest()},
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not changed:
        raise NoPatchError("Codex produced no app Python source changes; public test evidence was archived")
    patch_path.write_text(patch, encoding="utf-8")
    return metadata
