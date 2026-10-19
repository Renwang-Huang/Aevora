#!/usr/bin/env python3
"""Aevora H1 command receipts and immutable baseline (no credential reads)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    with Path(path).open("x") as output:
        json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def capture():
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4())
    archive = ROOT / "aevora_validation" / name
    archive.mkdir(parents=True, exist_ok=False)
    baseline = archive / "g0"
    baseline.mkdir()
    files = {}
    for directory in ("app", "benchmark", "evaluator", "integrations", "scripts", "tests", "docs", "benchmark_roadmap"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts:
                if path.suffix in {".py", ".json", ".md", ".diff", ".toml", ".yaml", ".sh"} or path.name in {"python312", "orderflow"}:
                    files[path.relative_to(ROOT).as_posix()] = digest(path)
    for path in ROOT.glob("*"):
        if path.is_file() and not path.is_symlink() and (path.suffix in {".md", ".toml"} or path.name == ".gitignore"):
            files[path.name] = digest(path)
    for relative in files:
        dest = baseline / "source_snapshot" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, dest)
    write(baseline / "BASELINE_SOURCES.json", files)
    # All existing archives/reports remain byte-for-byte protected, not just a selected Run.
    history, metadata_only = {}, []
    for name in ("runs", "evidence_review", "phase3_5_validation", "m1_validation", "m1_1_validation"):
        start = ROOT / name
        if not start.exists():
            continue
        for directory, dirs, names in os.walk(start, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not (Path(directory) / d).is_symlink())
            for filename in sorted(names):
                path = Path(directory) / filename
                relative = path.relative_to(ROOT).as_posix()
                if path.is_symlink():
                    metadata_only.append({"path": relative, "symlink_target": os.readlink(path), "content": "NOT_READ"})
                elif path.is_file():
                    history[relative] = digest(path)
    for relative, sha in files.items():
        if relative.endswith(".md") and ("VALIDATION_REPORT" in relative or relative.startswith(("M1_", "PHASE", "PROJECT_REALITY"))):
            history[relative] = sha
    write(baseline / "PROTECTED_HISTORY.json", history)
    write(baseline / "HISTORICAL_LINK_METADATA.json", metadata_only)
    naming = subprocess.run(["rg", "-n", "-i", "graphswarm|aevora", "README.md", "AGENTS.md", "pyproject.toml", "app", "benchmark", "integrations", "evaluator", "docs", "benchmark_roadmap"], cwd=ROOT, capture_output=True, text=True)
    (baseline / "BRAND_INVENTORY.txt").write_text(naming.stdout)
    status = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, capture_output=True, text=True)
    (baseline / "GIT_STATUS.txt").write_text(status.stdout)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write(baseline / "BASELINE.json", {"recorded_at": now(), "git_head": head,
        "source_files": len(files), "protected_history_files": len(history),
        "naming_command_exit": naming.returncode, "trust_scope": "Maintainer local file authority; no independent external signature",
        "historical_optional_materials": {"GraphSwarm_Agent_Interface_Architecture(1).md": "NOT_FOUND_IN_READABLE_WORKSPACE",
            "GraphSwarm_H0_Preflight_and_Hackathon_Build_Codex_Task_v1.0.md": "NOT_FOUND_IN_READABLE_WORKSPACE",
            "early_graph_prototype": "NOT_FOUND_IN_READABLE_WORKSPACE"}})
    (ROOT / "aevora_validation" / "CURRENT").write_text(str(archive) + "\n")
    print(json.dumps({"archive": str(archive), "source_files": len(files), "protected_history_files": len(history)}))


def record(archive, label, argv):
    if not label or "/" in label or label in {".", ".."} or not argv:
        raise ValueError("New receipt label and argument vector required")
    # Credentials must be delivered via trusted credential files, never arguments.
    if any("sk-" in value or "Bearer " in value or "password=" in value for value in argv):
        raise ValueError("Credential-like command arguments forbidden")
    directory = archive / label
    directory.mkdir(exist_ok=False)
    started, clock = now(), time.monotonic()
    with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        code = process.wait()
    receipt = {"argv": argv, "cwd": str(ROOT), "exit_code": code, "started_at": started, "ended_at": now(),
        "elapsed_seconds": time.monotonic() - clock,
        "stdout_sha256": digest(directory / "stdout.log"), "stderr_sha256": digest(directory / "stderr.log")}
    write(directory / "command.json", receipt)
    print(json.dumps(receipt))
    return code


def integrity(archive, junit, output):
    baseline = json.loads((archive / "g0/BASELINE_SOURCES.json").read_text())
    history = json.loads((archive / "g0/PROTECTED_HISTORY.json").read_text())
    truth = json.loads((ROOT / "m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/FROZEN_TASK_TRUTH.json").read_text())["files"]
    groups = {"inherited_test_source_bytes": {p:s for p,s in baseline.items() if p.startswith("tests/")},
              "independent_task_truth": truth, "protected_history": history}
    checks = {}
    for name, files in groups.items():
        mismatches = [p for p,s in files.items() if (ROOT/p).is_symlink() or not (ROOT/p).is_file() or digest(ROOT/p)!=s]
        checks[name] = {"status":"FAIL" if mismatches else "PASS", "file_count":len(files), "mismatches":mismatches}
    identities = lambda path: [f"{c.get('classname','')}::{c.get('name','')}" for c in ET.parse(path).getroot().iter("testcase")]
    original = identities(archive / "g0/BASELINE_JUNIT.xml")
    current = identities(junit)
    cases = list(ET.parse(junit).getroot().iter("testcase"))
    bad = [c.get("name") for c in cases if any(c.find(n) is not None for n in ("failure","error","skipped"))]
    missing = sorted(set(original)-set(current))
    checks["inherited_test_identities"] = {"status":"PASS" if not bad and not missing and len(current)==len(set(current)) else "FAIL",
        "required":len(original),"retained":len(set(original)&set(current)),"current":len(current),"missing":missing,"bad":bad,"junit_sha256":digest(junit)}
    changes = [{"path":p,"before":s,"after":digest(ROOT/p) if (ROOT/p).is_file() else None}
               for p,s in baseline.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=s]
    result = {"status":"PASS" if all(c["status"]=="PASS" for c in checks.values()) else "FAIL","checks":checks,
        "changed_existing_sources":changes,"recorded_at":now(),"assurance":"Current byte verification of complete captured historical file set; local trust"}
    write(output,result)
    print(json.dumps({"status":result["status"],"checks":checks,"changed_existing_source_count":len(changes)}))
    return 0 if result["status"]=="PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("capture")
    command = sub.add_parser("record")
    command.add_argument("archive", type=Path)
    command.add_argument("label")
    command.add_argument("argv", nargs=argparse.REMAINDER)
    audit = sub.add_parser("integrity")
    audit.add_argument("archive", type=Path)
    audit.add_argument("junit", type=Path)
    audit.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.operation == "capture":
        capture()
        return 0
    if args.operation == "integrity":
        return integrity(args.archive.resolve(),args.junit.resolve(),args.output.resolve())
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    return record(args.archive.resolve(), args.label, argv)


if __name__ == "__main__":
    raise SystemExit(main())
