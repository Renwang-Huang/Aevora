"""Versioned G21 entry: existing pytest/owned DB collector, no Agent orchestration."""

import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.validation.regression import main as regression


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--owned-port", required=True, type=int)
    a = p.parse_args()
    os.environ["AEVORA_G21_ARTIFACT_ROOT"] = str(a.output / "SDK_RAW")
    return regression(
        [
            "--output",
            str(a.output),
            "--owned-port",
            str(a.owned_port),
            "--",
            "-q",
            "aevora_core/tests/gen2",
            "-p",
            "no:cacheprovider",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
