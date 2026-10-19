#!/usr/bin/env python3
"""Repository wrapper; the exported verifier itself needs only Python stdlib."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "benchmark/evidence_verify.py"), run_name="__main__")
