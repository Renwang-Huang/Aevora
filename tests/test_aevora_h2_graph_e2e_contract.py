"""Pure CLI/file/projection contracts; no mock graph or engineering verdicts."""
import argparse
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("h2_graph_e2e_contract_impl",
    Path(__file__).resolve().parents[1] / "scripts/aevora_h2_graph_e2e.py")
_implementation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_implementation)
EvidenceRejected = _implementation.EvidenceRejected
GRAPH_NAME = _implementation.GRAPH_NAME
RawCommands = _implementation.RawCommands
anchor_from_arguments = _implementation.anchor_from_arguments
comparison_rows = _implementation.comparison_rows
endpoint = _implementation.endpoint
ordinary_path = _implementation.ordinary_path
parser = _implementation.parser
raw_value = _implementation.raw_value
read_json = _implementation.read_json
write = _implementation.write


def valid_endpoint():
    return {"AEVORA_FALKORDB_PORT": "17679", "AEVORA_FALKORDB_GRAPH": GRAPH_NAME,
            "AEVORA_FALKORDB_HOST": "127.0.0.1"}


def test_dedicated_endpoint_accepts_only_exact_g3_authority():
    endpoint(valid_endpoint())


@pytest.mark.parametrize("field,value", [
    ("AEVORA_FALKORDB_PORT", "16379"), ("AEVORA_FALKORDB_PORT", "17680"),
    ("AEVORA_FALKORDB_PORT", ""), ("AEVORA_FALKORDB_GRAPH", "aevora_h2_g0"),
    ("AEVORA_FALKORDB_GRAPH", "aevora_h1_release1"), ("AEVORA_FALKORDB_GRAPH", ""),
    ("AEVORA_FALKORDB_HOST", "example.invalid"), ("AEVORA_FALKORDB_HOST", "0.0.0.0"),
])
def test_other_graphs_or_endpoints_cannot_be_selected(field, value):
    environment = valid_endpoint()
    environment[field] = value
    with pytest.raises(EvidenceRejected):
        endpoint(environment)


def test_new_evidence_write_is_owner_only_and_refuses_overwrite(tmp_path):
    target = tmp_path / "receipt.json"
    write(target, {"actual_field": 7})
    assert target.stat().st_mode & 0o777 == 0o600
    assert read_json(target) == {"actual_field": 7}
    with pytest.raises(FileExistsError):
        write(target, {"actual_field": 8})
    assert read_json(target) == {"actual_field": 7}


def test_archive_path_does_not_follow_symbolic_components(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(EvidenceRejected):
        ordinary_path(link / "receipt.json")


@pytest.mark.parametrize("data", [b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b'{"x":'])
def test_trusted_configuration_rejects_ambiguous_or_nonfinite_json(tmp_path, data):
    from aevora.checkpoint import CheckpointRejected
    path = tmp_path / "input.json"
    path.write_bytes(data)
    with pytest.raises(CheckpointRejected):
        read_json(path)


def test_raw_protocol_preserves_scalar_and_byte_types_without_narration():
    assert raw_value([None, True, 2, 1.5, "x", b"\x00\xff", {"k": (1, 2)}]) == [
        None, True, 2, 1.5, "x", {"redis_type": "bytes", "base64": "AP8="}, {"k": [1, 2]}]
    with pytest.raises(EvidenceRejected):
        raw_value(object())


def test_raw_journal_has_actual_byte_hashable_lines_and_exclusive_creation(tmp_path):
    journal = RawCommands(tmp_path)
    journal.append({"command": ["GRAPH.RO_QUERY", GRAPH_NAME, "RETURN 1"], "actual_response": [[1]]})
    journal.close()
    lines = journal.path.read_bytes().splitlines(keepends=True)
    assert len(lines) == 1 and lines[0].endswith(b"\n")
    assert journal.count == 1 and journal.bytes == len(lines[0])
    assert json.loads(lines[0])["actual_response"] == [[1]]
    assert journal.path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        RawCommands(tmp_path)


@pytest.mark.parametrize("decision", ["APPLY", "VERIFY", "ABSTAIN"])
def test_comparison_projects_supplied_returned_fields_without_deciding_a_strategy(decision):
    # Explicit synthetic pure-projection data, not a graph, hidden answer or
    # fabricated natural Agent run. Actual graph integration is separate.
    raw = {"id": "experience:unfamiliar", "public_summary": "Unfamiliar public text"}
    value = {"status": "AVAILABLE", "candidates": [{"experience_id": raw["id"],
        "decision": decision, "principle_decision": "APPLY", "reason": "ACTUAL_RETURNED_REASON",
        "current_operation_coverage": "UNVERIFIED", "evidence_bundle": {"experience": raw}}]}
    row, = comparison_rows(value)
    assert row["when_decision"] == decision and row["reason"] == "ACTUAL_RETURNED_REASON"
    assert row["raw_public_experience"] == raw
    assert row["whole_operation_coverage"] == "UNVERIFIED"
    assert row["attribution"] == "UNKNOWN" and row["causal_benefit"] == "UNVERIFIED"


@pytest.mark.parametrize("value", [{}, {"status": "UNAVAILABLE", "candidates": []},
    {"status": "AVAILABLE", "candidates": [{"decision": "PASS"}]},
    {"status": "AVAILABLE", "candidates": [{"decision": "APPLY", "experience_id": "x",
                                               "evidence_bundle": {"experience": {"id": "y"}}}]}])
def test_incomplete_comparison_never_falls_back_to_fixed_apply(value):
    with pytest.raises(EvidenceRejected):
        comparison_rows(value)


def test_ingestion_anchor_requires_real_trusted_pin_arguments():
    args = argparse.Namespace(archive_root=None, manifest_sha256=None,
                             source_archive_root=None, source_manifest_sha256=None, run_id=None)
    with pytest.raises(EvidenceRejected):
        anchor_from_arguments(args)


def test_cli_quiescence_is_explicit_and_no_verdict_or_cypher_input_is_available():
    cli = parser()
    with pytest.raises(SystemExit) as error:
        cli.parse_args(["compare", "/tmp/new-evidence"])
    assert error.value.code == 2
    args = cli.parse_args(["compare", "/tmp/new-evidence", "--writers-quiesced"])
    assert args.operation == "compare" and args.writers_quiesced is True
    assert not any(action.dest in {"verdict", "outcome", "cypher", "graph_name", "password"}
                   for action in cli._actions)
