"""New checkpoint security controls; actual DB coverage is in the original suite."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("operation", ["ordinary_read", "manifest_read"])
def test_fifo_is_rejected_by_bounded_real_subprocess(tmp_path, operation):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    fifo = private / "manifest.json"
    os.mkfifo(fifo, 0o600)
    if operation == "manifest_read":
        (private / "dump.rdb").write_bytes(b"REDIS0011synthetic-contract-fixture")
        (private / "dump.rdb").chmod(0o600)
    program = """import sys
from pathlib import Path
from aevora.checkpoint import _read, verify_checkpoint, CheckpointRejected
try:
    if sys.argv[1] == "ordinary_read":
        _read(Path(sys.argv[2]) / "manifest.json", 4096)
    else:
        verify_checkpoint(Path(sys.argv[2]), "a" * 64)
except CheckpointRejected:
    print("ACTUAL_FIFO_TYPE_REJECTED")
    raise SystemExit(2)
raise SystemExit(9)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, operation, str(private)],
        capture_output=True,
        text=True,
        timeout=2,
    )
    assert result.returncode == 2
    assert result.stdout.strip() == "ACTUAL_FIFO_TYPE_REJECTED"
    assert result.stderr == ""


@pytest.mark.parametrize("depth", [65, 2000])
def test_nested_manifest_is_classified_in_bounded_real_subprocess(tmp_path, depth):
    source = tmp_path / "deep.json"
    source.write_text('{"nested":' + "[" * depth + "0" + "]" * depth + "}")
    program = """import sys
from pathlib import Path
from aevora.checkpoint import _json, CheckpointRejected
try:
    _json(Path(sys.argv[1]).read_bytes())
except CheckpointRejected:
    print("ACTUAL_NESTED_MANIFEST_REJECTED")
    raise SystemExit(2)
raise SystemExit(9)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, str(source)],
        capture_output=True,
        text=True,
        timeout=2,
    )
    assert result.returncode == 2
    assert result.stdout.strip() == "ACTUAL_NESTED_MANIFEST_REJECTED"
    assert result.stderr == ""


def _schema_contract_rows():
    # Explicit schema-validation values, not a simulated graph/SDK verdict.
    from aevora.models import LABELS

    return [
        {
            "entitytype": "NODE",
            "label": label,
            "type": kind,
            "properties": properties,
            "status": "OPERATIONAL",
        }
        for label in sorted(LABELS)
        for kind, properties in (
            ("UNIQUE", ["id"]),
            ("MANDATORY", ["id", "payload_json", "payload_sha256"]),
        )
    ]


def test_constraint_contract_matches_current_schema_with_property_order_independence():
    from aevora.checkpoint import _validate_constraints

    rows = _schema_contract_rows()
    rows[1]["properties"].reverse()
    assert len(_validate_constraints(rows)) == len(rows)


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate_row",
        "wrong_property",
        "wrong_label",
        "wrong_type",
        "wrong_entity",
        "duplicate_property",
        "nonoperational",
        "missing_field",
        "malformed_properties",
    ],
)
def test_same_count_incorrect_constraint_set_is_rejected(defect):
    from aevora.checkpoint import _validate_constraints, CheckpointRejected

    rows = _schema_contract_rows()
    if defect == "duplicate_row":
        rows[1] = dict(rows[0])
    elif defect == "wrong_property":
        rows[0]["properties"] = ["payload_json"]
    elif defect == "wrong_label":
        rows[0]["label"] = "UnownedLabel"
    elif defect == "wrong_type":
        rows[0]["type"] = "MANDATORY"
    elif defect == "wrong_entity":
        rows[0]["entitytype"] = "RELATIONSHIP"
    elif defect == "duplicate_property":
        rows[1]["properties"] = ["id", "payload_json", "payload_json"]
    elif defect == "nonoperational":
        rows[0]["status"] = "PENDING"
    elif defect == "missing_field":
        del rows[0]["properties"]
    else:
        rows[0]["properties"] = {"id": True}
    with pytest.raises(CheckpointRejected):
        _validate_constraints(rows)
