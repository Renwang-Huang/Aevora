"""Trusted, byte-exact application of bounded business source submissions.

The strict parser computes an expected tree without executing candidate code.
Git applies the same bytes of each parsed file section in a new repository with
an empty template, a clean environment and explicit configuration. Only an
identical result is published. Per-file application also accepts the existing
extractor's mixture of empty Git sections and ordinary unified sections, which
Git otherwise ambiguously treats as a single extended-header section.
Publication requires Linux renameat2(RENAME_EXCHANGE); there is no non-atomic or
unverified fallback. The caller must stop participant writers before collection.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from typing import Any

MAX_PATCH_BYTES = 1_000_000
MAX_SOURCE_BYTES = 2_000_000
MAX_SOURCE_FILES = 100
MAX_TREE_ENTRIES = 1_000
_PATH = re.compile(r"app/[A-Za-z0-9_/.-]+\.py\Z")
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: [^\n]*)?\n\Z")
_INDEX = re.compile(r"index ([0-9a-f]{7,40})\.\.([0-9a-f]{7,40})(?: (100644))?\n\Z")


class SubmissionIntegrityError(ValueError):
    """An untrusted submission did not produce its exact authorized tree."""

    code = "SUBMISSION_INTEGRITY_ERROR"


def _fail(message: str) -> None:
    raise SubmissionIntegrityError(f"SUBMISSION_INTEGRITY_ERROR: {message}")


def _safe_path(name: str) -> str:
    if (not _PATH.fullmatch(name)
            or any(part in {"", ".", "..", ".git"} for part in name.split("/"))):
        _fail("Patches may modify only Python files under app/ using ordinary paths")
    return name


def _ordinary_parents(path: Path) -> Path:
    path = path.absolute()
    # absolute() preserves '..'; reject it before filesystem resolution.
    if ".." in path.parts:
        _fail("Path traversal is forbidden")
    for parent in reversed((path, *path.parents)):
        try:
            mode = parent.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            _fail(f"Symbolic links are forbidden: {parent}")
    return path


def _read_regular(path: Path, limit: int) -> bytes:
    path = _ordinary_parents(path)
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            _fail(f"Expected a single-link regular file: {path}")
        if before.st_size > limit:
            _fail(f"File exceeds byte limit: {path}")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                _fail(f"File changed or became linked during collection: {path}")
            value = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if len(value) > limit or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            _fail(f"File changed or exceeded byte limit during collection: {path}")
        _text(value, str(path))
        return value
    except OSError as error:
        _fail(f"Unable to safely read {path}: {type(error).__name__}")


def _text(value: bytes, label: str) -> str:
    if b"\0" in value:
        _fail(f"Binary/NUL content is forbidden: {label}")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        _fail(f"Only UTF-8 text is accepted: {label}")


def read_submission_patch(path: Path) -> bytes:
    """Bounded no-follow, single-link UTF-8 patch read for trusted ingestion."""
    return _read_regular(Path(path), MAX_PATCH_BYTES)


def _validate_tree(tree: Mapping[str, bytes]) -> dict[str, bytes]:
    if not isinstance(tree, Mapping):
        _fail("Expected tree must be a mapping of app/... paths to bytes")
    result: dict[str, bytes] = {}
    total = 0
    for name, value in tree.items():
        if not isinstance(name, str) or not isinstance(value, bytes):
            _fail("Expected tree must map app/... Python paths to bytes")
        _safe_path(name)
        _text(value, name)
        for parent in Path(name).parents:
            if parent.as_posix() in tree:
                _fail(f"Source path conflicts with a file: {name}")
        total += len(value)
        result[name] = value
    if total > MAX_SOURCE_BYTES or len(result) > MAX_SOURCE_FILES:
        _fail("Source tree exceeds the 100-file / 2 MB limit")
    return result


def snapshot_source_tree(workspace: Path, *, require_only_python: bool = False,
                         app_directory: bool = False) -> dict[str, bytes]:
    """Read regular UTF-8 app/**/*.py; reject links and special app entries.

    Keys include the app/ prefix. Non-app workspace material is neither read nor
    copied into the isolated application repository. app_directory explicitly
    treats workspace as a direct application directory and normalizes keys to app/.
    Ordinary non-Python files
    (e.g. participant-generated bytecode) are ignored unless require_only_python
    is requested for a trusted candidate/staging directory.
    """
    workspace = _ordinary_parents(Path(workspace))
    app = workspace if app_directory else workspace / "app"
    if not workspace.is_dir() or not app.is_dir():
        _fail("Candidate must contain an ordinary app directory; patches may modify only Python files under app/")
    _ordinary_parents(app)
    tree: dict[str, bytes] = {}
    for count, item in enumerate(sorted(app.rglob("*")), start=1):
        if count > MAX_TREE_ENTRIES:
            _fail("Source tree exceeds its entry limit")
        mode = item.lstat().st_mode
        if stat.S_ISDIR(mode):
            _ordinary_parents(item)
            continue
        if not stat.S_ISREG(mode) or item.lstat().st_nlink != 1:
            _fail(f"Links and special source entries are forbidden: {item}")
        if item.suffix != ".py":
            if require_only_python:
                _fail(f"Candidate app contains a non-Python file: {item}")
            continue
        name = _safe_path("app/" + item.relative_to(app).as_posix())
        tree[name] = _read_regular(item, MAX_SOURCE_BYTES)
    return _validate_tree(tree)


def source_tree_sha256(tree: Mapping[str, bytes]) -> str:
    """Version 1 tree digest: ordered length-prefixed relative names and bytes."""
    tree = _validate_tree(tree)
    digest = hashlib.sha256()
    for name, value in sorted(tree.items()):
        relative = name.encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _header_path(line: str, marker: str) -> str | None:
    if not line.startswith(marker) or not line.endswith("\n"):
        _fail("Missing or truncated unified diff header")
    path = line[len(marker):-1].split("\t", 1)[0]
    if path == "/dev/null":
        return None
    prefix = "a/" if marker == "--- " else "b/"
    if not path.startswith(prefix):
        _fail("Patches may modify only Python files under app/")
    return _safe_path(path[2:])


def _source_lines(value: bytes) -> list[bytes]:
    # Unified diff and Git use LF delimiters, not Python's Unicode splitlines.
    pieces = value.split(b"\n")
    return [part + b"\n" for part in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])


def _blob_sha1(value: bytes) -> str:
    return hashlib.sha1(f"blob {len(value)}\0".encode() + value).hexdigest()


def _index_matches(declared: str, content: bytes | None) -> bool:
    return (set(declared) == {"0"}) if content is None else _blob_sha1(content).startswith(declared)


def expected_tree_from_patch(baseline: Mapping[str, bytes], patch_bytes: bytes,
                             *, _sections: list[bytes] | None = None) -> dict[str, bytes]:
    """Interpret a strict subset of Git/unified text diff without fuzzy matching.

    Each path occurs once, offsets/counts/context are exact, rename/copy/mode
    changes/binaries/preambles are rejected. Empty Git additions/deletions may
    contain mode/index headers with or without ---/+++ headers.
    """
    before = _validate_tree(baseline)
    result = dict(before)
    if not patch_bytes or len(patch_bytes) > MAX_PATCH_BYTES:
        _fail("Patch is empty or exceeds the 1 MB limit")
    text = _text(patch_bytes, "submission patch")
    if not text.endswith("\n"):
        _fail("Patch is truncated (missing final LF)")
    lines = [line + "\n" for line in text[:-1].split("\n")]
    cursor = 0
    seen: set[str] = set()
    while cursor < len(lines):
        section_start = cursor
        git_name = None
        mode = None
        index = None
        if lines[cursor].startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/(\S+) b/(\S+)\n", lines[cursor])
            if not match or match[1] != match[2]:
                _fail("Renames/copies or malformed Git paths are forbidden")
            git_name = _safe_path(match[1])
            cursor += 1
            while cursor < len(lines) and not lines[cursor].startswith(("--- ", "diff --git ")):
                line = lines[cursor]
                if line in {"new file mode 100644\n", "deleted file mode 100644\n"}:
                    if mode is not None or index is not None:
                        _fail("Duplicate or misplaced file mode header")
                    mode = "create" if line.startswith("new") else "delete"
                elif _INDEX.fullmatch(line):
                    if index is not None:
                        _fail("Duplicate index header")
                    index = _INDEX.fullmatch(line).groups()[:2]
                else:
                    _fail("Only ordinary unified text patches are accepted; unsupported Git header")
                cursor += 1
        if cursor < len(lines) and lines[cursor].startswith("--- "):
            old = _header_path(lines[cursor], "--- ")
            cursor += 1
            if cursor >= len(lines):
                _fail("Truncated unified diff headers")
            new = _header_path(lines[cursor], "+++ ")
            cursor += 1
            if old is None and new is None:
                _fail("Both diff paths cannot be /dev/null")
            if old is not None and new is not None and old != new:
                _fail("Renames/copies are forbidden")
            name = old or new
            operation = "create" if old is None else "delete" if new is None else "modify"
            if git_name is not None and git_name != name:
                _fail("Git and unified diff paths disagree")
            if mode is not None and mode != operation:
                _fail("Git file mode and unified diff operation disagree")
        elif git_name is not None and mode is not None and index is not None:
            name, operation = git_name, mode
        else:
            _fail("Submission must be a unified text patch")
        if name in seen:
            _fail(f"Duplicate patch path: {name}")
        seen.add(name)
        prior = before.get(name)
        if operation == "create" and prior is not None:
            _fail(f"Creation path already exists: {name}")
        if operation != "create" and prior is None:
            _fail(f"Patch target does not exist: {name}")
        original = _source_lines(prior or b"")
        output: list[bytes] = []
        position = 0
        hunk_count = 0
        while cursor < len(lines) and lines[cursor].startswith("@@ "):
            hunk = _HUNK.fullmatch(lines[cursor])
            if not hunk:
                _fail(f"Malformed hunk: {name}")
            old_start, old_count, new_start, new_count = (
                int(hunk[1]), int(hunk[2] or 1), int(hunk[3]), int(hunk[4] or 1))
            if (old_count and not old_start) or (new_count and not new_start):
                _fail(f"Invalid zero hunk offset: {name}")
            old_offset = old_start - 1 if old_count else old_start
            new_offset = new_start - 1 if new_count else new_start
            if old_offset < position or old_offset > len(original):
                _fail(f"Overlapping or out-of-range hunk: {name}")
            output.extend(original[position:old_offset])
            if new_offset != len(output):
                _fail(f"Inconsistent new hunk offset: {name}")
            cursor += 1
            rows: list[tuple[str, bytes]] = []
            consumed_old = consumed_new = 0
            while consumed_old < old_count or consumed_new < new_count:
                if cursor >= len(lines) or lines[cursor][:1] not in {" ", "-", "+"}:
                    _fail(f"Truncated or invalid hunk: {name}")
                kind, body = lines[cursor][0], lines[cursor][1:].encode("utf-8")
                consumed_old += kind != "+"
                consumed_new += kind != "-"
                if consumed_old > old_count or consumed_new > new_count:
                    _fail(f"Hunk count exceeded: {name}")
                cursor += 1
                if cursor < len(lines) and lines[cursor] == "\\ No newline at end of file\n":
                    body = body[:-1]
                    cursor += 1
                rows.append((kind, body))
            removed = [body for kind, body in rows if kind != "+"]
            if original[old_offset:old_offset + old_count] != removed:
                _fail(f"Hunk context/content mismatch: {name}")
            output.extend(body for kind, body in rows if kind != "-")
            position = old_offset + old_count
            hunk_count += 1
        output.extend(original[position:])
        final = b"".join(output)
        if operation == "delete":
            if final:
                _fail(f"Deletion did not remove all source content: {name}")
            del result[name]
            after = None
        else:
            if not hunk_count and operation != "create":
                _fail(f"Modification requires a content hunk: {name}")
            if operation == "modify" and prior == final:
                _fail(f"No source change in patch section: {name}")
            result[name] = final
            after = final
        if not hunk_count and operation in {"create", "delete"} and git_name is None:
            _fail("Empty file changes require explicit Git mode headers")
        if index and (not _index_matches(index[0], prior) or not _index_matches(index[1], after)):
            _fail(f"Git index blob hash does not match source: {name}")
        if _sections is not None:
            _sections.append("".join(lines[section_start:cursor]).encode("utf-8"))
    if before == result:
        _fail("Patch did not change any business source")
    return _validate_tree(result)


def _git_executable() -> str:
    # Fixed trusted locations; never consult a participant-controlled PATH.
    for name in ("/tools/git", "/usr/bin/git", "/bin/git"):
        if Path(name).is_file() and os.access(name, os.X_OK):
            return name
    _fail("Trusted Git executable is unavailable")


def _git_run(git: str, worktree: Path, git_dir: Path, home: Path, arguments: list[str]) -> str:
    environment = {
        "PATH": "/usr/bin:/bin", "HOME": str(home), "XDG_CONFIG_HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull, "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "LANG": "C",
    }
    command = [git, "--git-dir=" + str(git_dir), "--work-tree=" + str(worktree),
               "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null",
               "-c", "core.autocrlf=false", "-c", "core.eol=lf",
               "-c", "core.fsmonitor=false", "-c", "apply.ignoreWhitespace=no", *arguments]
    try:
        completed = subprocess.run(command, cwd=worktree, env=environment,
                                   capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        _fail(f"Isolated Git failed: {type(error).__name__}")
    if completed.returncode:
        # Bounded diagnostics contain only public patch paths/content, no env.
        detail = completed.stderr.decode("utf-8", errors="replace")[-2_000:].strip()
        _fail(f"Isolated git {' '.join(arguments[:2])} failed ({completed.returncode}): {detail}")
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _exchange(left: Path, right: Path) -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renameat2
    except (AttributeError, OSError):
        _fail("Atomic renameat2 publication is unavailable; no unsafe fallback")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        code = ctypes.get_errno()
        _fail(f"Atomic publication failed: {errno.errorcode.get(code, code)}")


def apply_verified_patch(candidate: Path, patch: Path, *, expected_tree=None) -> dict[str, Any]:
    """Verify, cross-check with clean Git, then atomically publish app source.

    expected_tree may be an independently collected workspace Path or a mapping
    returned by snapshot_source_tree(). On every pre-publication rejection the
    original candidate is untouched. Evidence is returned; caller archives it.
    """
    candidate = _ordinary_parents(Path(candidate))
    patch = _ordinary_parents(Path(patch))
    patch_bytes = read_submission_patch(patch)
    baseline = snapshot_source_tree(candidate, require_only_python=True)
    sections: list[bytes] = []
    expected = expected_tree_from_patch(baseline, patch_bytes, _sections=sections)
    if expected_tree is not None:
        external = snapshot_source_tree(Path(expected_tree)) if isinstance(expected_tree, (str, Path)) else _validate_tree(expected_tree)
        if expected != external:
            _fail("Patch-derived expected tree differs from the independently collected submission")
    metadata = {
        "status": "PASS", "tree_digest_algorithm": "sha256-length-prefixed-source-tree-v1",
        "baseline_tree_sha256": source_tree_sha256(baseline),
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
        "expected_tree_sha256": source_tree_sha256(expected),
        "changed_files": [
            {"path": name, "action": "create" if name not in baseline else "delete" if name not in expected else "modify",
             "before_sha256": hashlib.sha256(baseline[name]).hexdigest() if name in baseline else None,
             "after_sha256": hashlib.sha256(expected[name]).hexdigest() if name in expected else None}
            for name in sorted(baseline.keys() | expected.keys()) if baseline.get(name) != expected.get(name)],
        "verification": "strict diff interpreter + original per-file sections in clean Git + byte-exact tree comparison",
        "patch_sections_sha256": [hashlib.sha256(section).hexdigest() for section in sections],
        "atomic_publication": "Linux renameat2(RENAME_EXCHANGE)",
    }
    with tempfile.TemporaryDirectory(prefix=".orderflow-submission-", dir=candidate.parent) as temporary:
        staging = Path(temporary)
        worktree = staging / "tree"
        git_dir = staging / "git"
        home = staging / "home"
        template = staging / "empty-template"
        for path in (worktree / "app", home, template):
            path.mkdir(parents=True)
        for name, content in baseline.items():
            target = worktree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o644)
        git = _git_executable()
        _git_run(git, worktree, git_dir, home, ["init", "--quiet", "--template=" + str(template)])
        metadata["git_version"] = _git_run(git, worktree, git_dir, home, ["--version"])
        isolated_patches = []
        for number, section in enumerate(sections):
            isolated_patch = staging / f"section-{number:03d}.diff"
            isolated_patch.write_bytes(section)
            isolated_patches.append(isolated_patch)
        for flags in (["--check"], []):
            for isolated_patch in isolated_patches:
                _git_run(git, worktree, git_dir, home,
                         ["apply", "--whitespace=nowarn", *flags, "--", str(isolated_patch)])
        applied = snapshot_source_tree(worktree, require_only_python=True)
        if applied != expected:
            _fail("Git returned success but actual candidate tree differs from expected tree")
        metadata["applied_candidate_tree_sha256"] = source_tree_sha256(applied)
        if snapshot_source_tree(candidate, require_only_python=True) != baseline:
            _fail("Candidate baseline changed before publication")
        _exchange(candidate / "app", worktree / "app")
        try:
            if snapshot_source_tree(candidate, require_only_python=True) != expected:
                _fail("Published candidate differs from the verified staging tree")
        except Exception:
            _exchange(candidate / "app", worktree / "app")
            raise
    return metadata
