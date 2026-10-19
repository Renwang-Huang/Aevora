"""Trusted local evidence seals, with explicit limits on immutability claims."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import shutil
import stat
from integrations.agents import utc_timestamp
from integrations.codex_trace import redact_jsonl


def archive_native_rollouts(state: Path, archive: Path, *, secret_values=()) -> dict:
    """Collect only this fresh run's official session files after writers stop.

    This is a local redacted record, not independent runtime attestation. Never
    follow participant-created links or read the maintainer's CODEX_HOME.
    """
    import os
    root = state / "sessions"
    if not root.exists():
        return {"availability": "UNAVAILABLE", "reason": "no official session files", "files": []}
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Native session root must be a regular directory")
    records = []
    total = 0
    entries = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        entries += len(dirs) + len(names)
        if entries > 10000 or len(Path(directory).relative_to(root).parts) > 50:
            raise ValueError("Native rollout entry/depth budget exceeded")
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Native session directory link refused")
        for name in sorted(names):
            source = Path(directory) / name
            if source.suffix != ".jsonl":
                continue
            mode = source.lstat()
            if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                raise ValueError("Native rollout link or special file refused")
            total += mode.st_size
            if len(records) >= 1000 or mode.st_size > 64 * 1024**2 or total > 128 * 1024**2:
                raise ValueError("Native rollout archive budget exceeded")
            relative = source.relative_to(root)
            target = archive / "artifacts" / "native_rollouts" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # Reserve destination exclusively; redaction never overwrites a
            # previous run's evidence, including in retry/error paths.
            with target.open("xb"):
                pass
            try:
                record = redact_jsonl(source, target, secret_values=secret_values)
            except RecursionError as error:
                raise ValueError("Native rollout JSON nesting budget exceeded") from error
            session_metadata = []
            event_types = {}
            for line in target.read_bytes().splitlines():
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                kind = event.get("type") if isinstance(event, dict) else None
                if isinstance(kind, str):
                    event_types[kind] = event_types.get(kind, 0) + 1
                if kind == "session_meta":
                    session_metadata.append(event.get("payload"))
            records.append({**record, "relative_path": str(relative),
                            "session_metadata": session_metadata, "event_types": event_types})
    return {"availability": "AVAILABLE" if records else "UNAVAILABLE", "files": records,
            "source": "official per-run CODEX_HOME sessions JSONL",
            "policy": "post-process cleanup, bounded regular files, credential redaction"}


def seal_inputs(workspace: Path, archive: Path, prompt: bytes) -> dict:
    destination = archive / "sealed_public_inputs"
    destination.mkdir(mode=0o700)
    hashes = {}
    for source in sorted(workspace.rglob("*")):
        mode = source.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode) or source.stat().st_nlink != 1:
            raise ValueError("Initial public inputs must be regular single-link files")
        relative = str(source.relative_to(workspace))
        data = source.read_bytes()
        if len(data) > 5_000_000:
            raise ValueError("Public input exceeds sealing limit")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(data)
        hashes[relative] = sha256(data).hexdigest()
    with (archive / "exact_stdin.txt").open("xb") as output:
        output.write(prompt)
    record = {"sealed_at": utc_timestamp(), "run_id": archive.name,
              "files": hashes, "exact_stdin_sha256": sha256(prompt).hexdigest(),
              "policy": "trusted pre-execution snapshot; local hashes, not third-party immutable storage"}
    with (archive / "input_seal.json").open("x") as output:
        json.dump(record, output, indent=2, sort_keys=True)
        output.write("\n")
    return record


def seal_run(archive: Path) -> dict:
    files = {}
    refused = []
    total_bytes = 0
    for path in sorted(archive.rglob("*")):
        relative = str(path.relative_to(archive))
        if any(part in ("codex-state", "__pycache__") for part in path.relative_to(archive).parts):
            continue
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode) or path.stat().st_nlink != 1:
            refused.append({"path": relative, "reason": "link_or_special_entry_not_followed"})
            continue
        total_bytes += path.stat().st_size
        if len(files) >= 10000 or total_bytes > 1_000_000_000:
            raise ValueError("Run archive exceeds its finite evidence-sealing budget")
        digest = sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1_048_576), b""):
                digest.update(block)
        files[relative] = digest.hexdigest()
    payload = {"run_id": archive.name, "sealed_at": utc_timestamp(), "files": files,
               "previous_seal_sha256": sha256((archive / "input_seal.json").read_bytes()).hexdigest() if (archive / "input_seal.json").exists() else "UNAVAILABLE",
               "refused_entries": refused,
               "immutability": "host protected local hash chain; no third-party attestation"}
    with (archive / "run_evidence_manifest.json").open("x") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")
    return payload
