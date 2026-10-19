#!/usr/bin/env python3
"""Compare M1 truth/history and original tests against the captured R0 baseline."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("junit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Integrity receipt must be a new file")
    source = json.loads((args.baseline / "M1_BASELINE_SOURCES.json").read_text())
    original_tests = {p: sha for p, sha in source.items() if p.startswith("tests/")}
    truth = json.loads((args.baseline / "FROZEN_TASK_TRUTH.json").read_text())["files"]
    history = json.loads((args.baseline / "PROTECTED_HISTORY.json").read_text())
    checks = {}
    for name, files in (("original_test_bytes", original_tests), ("task_truth", truth), ("protected_history", history)):
        mismatch = []
        for relative, expected in files.items():
            path = ROOT / relative
            if path.is_symlink() or not path.is_file() or digest(path) != expected:
                mismatch.append(relative)
        checks[name] = {"status": "PASS" if not mismatch else "FAIL", "checked_files": len(files),
            "mismatches": mismatch}
    root = ET.parse(args.junit).getroot()
    cases = list(root.iter("testcase"))
    identities = [f"{c.get('classname', '')}::{c.get('name', '')}" for c in cases]
    original = json.loads((args.baseline / "BASELINE_TEST_IDENTITIES.json").read_text())
    missing = sorted(set(original) - set(identities))
    counts = {"collected": len(cases), "failed": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases), "skipped": sum(c.find("skipped") is not None for c in cases)}
    checks["test_identities"] = {"status": "PASS" if not missing and len(identities) == len(set(identities)) and
        not any(counts[k] for k in ("failed", "errors", "skipped")) else "FAIL",
        "original_required_count": len(original), "retained": len(set(original) & set(identities)),
        "missing": missing, "counts": counts, "junit_sha256": digest(args.junit)}
    changes = [{"path": p, "before_sha256": old, "current_sha256": digest(ROOT / p) if (ROOT / p).is_file() else None}
        for p, old in source.items() if not (ROOT / p).is_file() or digest(ROOT / p) != old]
    result = {"status": "PASS" if all(v["status"] == "PASS" for v in checks.values()) else "FAIL",
        "recorded_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "intentional_baseline_source_changes": changes,
        "qualification": "Local current bytes and executed JUnit identities; not independent execution attestation"}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checks": checks}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
