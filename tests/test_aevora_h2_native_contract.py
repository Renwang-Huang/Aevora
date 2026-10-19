"""Pure admission-format contracts, not native/model execution evidence."""
import importlib.util
import json
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts/aevora_h2_native.py"
_spec = importlib.util.spec_from_file_location("h2_native_contract", _path)
native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(native)


def gates():
    return [
        {"gate": "H2-G0", "verdict": "PASS_REQUIRED_FUNCTIONAL_EVIDENCE"},
        {"gate": "H2-G1", "status": "PASS"},
        {"gate": "H2-G2", "status": "PASS"},
        {"version": "aevora.h2-dv02-security/1.0", "status": "PASS", "mandatory_boundary_result": "PASS"},
    ]


def test_admission_requires_all_four_receipt_types():
    native.validate_gate_receipts(gates())


@pytest.mark.parametrize("missing", range(4))
def test_missing_mandatory_gate_fails_closed(missing):
    values = gates()
    values.pop(missing)
    with pytest.raises(ValueError):
        native.validate_gate_receipts(values)


@pytest.mark.parametrize("index,field", [(0, "verdict"), (1, "status"), (2, "status"),
                                        (3, "status"), (3, "mandatory_boundary_result")])
def test_partial_or_failed_gate_fails_closed(index, field):
    values = gates()
    values[index][field] = "PARTIAL"
    with pytest.raises(ValueError):
        native.validate_gate_receipts(values)


def test_unrelated_pass_is_not_an_admission():
    with pytest.raises(ValueError):
        native.validate_gate_receipts(gates() + [{"status": "PASS"}])


def release_files(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    rows = {"app/service.py": {"sha256": "a" * 64, "mode": 0o644}}
    common = {"commit": "1" * 40, "git_tree": "2" * 40, "source_tree_sha256": "3" * 64}
    (release / "SOURCE_MANIFEST.json").write_text(json.dumps({**common, "source_files": rows}))
    (release / "COMMIT_RECEIPT.json").write_text(json.dumps({**common, "command_results": [{"exit_code": 0}]}))
    return rows


def test_release_requires_exact_commit_and_source_epoch(tmp_path):
    rows = release_files(tmp_path)
    assert native.validate_release(tmp_path, "release/COMMIT_RECEIPT.json", "1" * 40, rows) == "release/SOURCE_MANIFEST.json"


@pytest.mark.parametrize("kind", ["short-commit", "wrong-commit", "changed-source", "failed-git"])
def test_release_binding_rejects_inconsistent_receipts(tmp_path, kind):
    rows = release_files(tmp_path)
    commit = "1" * 40
    if kind == "short-commit":
        commit = "1111111"
    elif kind == "wrong-commit":
        commit = "4" * 40
    elif kind == "changed-source":
        rows["app/service.py"]["sha256"] = "b" * 64
    else:
        path = tmp_path / "release/COMMIT_RECEIPT.json"
        value = json.loads(path.read_text())
        value["command_results"][0]["exit_code"] = 1
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        native.validate_release(tmp_path, "release/COMMIT_RECEIPT.json", commit, rows)


def test_admission_receipt_refuses_parent_traversal(tmp_path):
    with pytest.raises(ValueError):
        native.receipt(tmp_path, "../private.json")


def test_admission_receipt_refuses_link(tmp_path):
    (tmp_path / "actual.json").write_text("{}")
    (tmp_path / "linked.json").symlink_to("actual.json")
    with pytest.raises(OSError):
        native.receipt(tmp_path, "linked.json")
