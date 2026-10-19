#!/usr/bin/env python3
"""Replay the unchanged inherited cancellation assertion; no model requests."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import pytest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--repeats", type=int, default=50)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    module = importlib.import_module("test_completion_runtime")
    rows = []
    for i in range(args.repeats):
        work = args.output / str(i)
        work.mkdir()
        error = None
        with pytest.MonkeyPatch.context() as patch:
            try:
                module.test_real_adapter_cancel_stops_running_process_and_keeps_original_result(work, patch)
            except Exception:
                error = traceback.format_exc()
        paths = list(work.rglob("runtime_metadata.json"))
        rows.append({"iteration": i, "unchanged_assertion": "FAIL" if error else "PASS", "error": error,
            "runtime_metadata": [str(path.relative_to(args.output)) for path in paths],
            "observations": [json.loads(path.read_text()) for path in paths]})
        if error:
            print(json.dumps({"iteration": i, "error": error, "runtime_metadata": rows[-1]["observations"]}), flush=True)
    result = {"status": "PASS" if all(r["unchanged_assertion"] == "PASS" for r in rows) else "FAIL", "repeats": len(rows),
        "source_sha256": hashlib.sha256((ROOT / "tests/test_completion_runtime.py").read_bytes()).hexdigest(),
        "kind": "dynamic repeated inherited contract assertion, synthetic CLI, no model calls", "iterations": rows}
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "repeats": len(rows), "failures": sum(bool(r["error"]) for r in rows)}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
