"""Actual FalkorDB CLI tests with explicitly synthetic pinned evidence."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

from test_feedback import repo, prepared, experience, query
from test_orderflow_outcome_bridge import RUN, write_json

spec = importlib.util.spec_from_file_location("aevora_test_ingest_cli",
    Path(__file__).resolve().parents[1] / "scripts/ingest_orderflow_outcome.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def arguments(evidence, output):
    files = json.loads(evidence.manifest.read_text())["ordinary_files_sha256"]
    prefix = evidence.run.relative_to(evidence.root).as_posix() + "/"
    seal = evidence.run / "run_evidence_manifest.json"
    write_json(seal, {"ordinary_files_sha256": {name[len(prefix):]: value
                                              for name, value in files.items() if name.startswith(prefix)}})
    return ["--run-dir", str(evidence.run), "--run-id", RUN,
        "--run-seal-sha256", sha256(seal.read_bytes()).hexdigest(),
        "--source-archive", str(evidence.root), "--source-manifest-sha256", evidence.anchor.manifest_sha256,
        "--source-snapshot-relative-path", "final_source_snapshot", "--output", str(output)]


def test_actual_cli_current_profile_ingests_and_repeats(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    query(repo)
    output = tmp_path / "receipt.json"
    assert cli.main(arguments(evidence, output)) == 0
    receipt = json.loads(output.read_text())
    assert receipt["status"] == "INGESTED" and receipt["idempotent"] is True
    assert receipt["after_graph"] == receipt["repeat_graph"] == receipt["final_graph"]
    assert receipt["ingestion"]["verdict"] == "PASS"
    assert receipt["ingestion"]["feedback_status"] == "outcome_observed_no_attribution"
    assert receipt["adoption"] == "UNVERIFIED" and receipt["attribution"] == "UNKNOWN"
    assert receipt["new_conflict_audit_ids"] == []


@pytest.mark.parametrize("flag", ["--run-seal-sha256", "--source-manifest-sha256"])
def test_wrong_trusted_pin_rejects_and_archives_without_outcome(repo, tmp_path, flag):
    evidence = prepared(tmp_path)
    output = tmp_path / "receipt.json"
    args = arguments(evidence, output)
    args[args.index(flag) + 1] = "0" * 64
    before = repo.state_fingerprint()
    assert cli.main(args) == 2
    assert json.loads(output.read_text())["status"] == "OUTCOME_VERIFICATION_REJECTED"
    assert repo.state_fingerprint() == before
    assert repo.get_node("VerifiedOutcome", "orderflow:" + RUN) is None


def test_conflict_retains_original_and_real_audit_receipt(repo, tmp_path):
    evidence = prepared(tmp_path)
    assert cli.main(arguments(evidence, tmp_path / "first.json")) == 0
    original = repo.get_node("VerifiedOutcome", "orderflow:" + RUN)
    evidence.report["evaluation_ended_at"] = "2026-10-11T00:00:01+00:00"
    evidence.commit()
    output = tmp_path / "conflict.json"
    assert cli.main(arguments(evidence, output)) == 3
    receipt = json.loads(output.read_text())
    assert receipt["status"] == "IMMUTABLE_CONFLICT" and receipt["exit_code"] == 3
    assert receipt["original_outcome_preserved"] is True
    assert receipt["new_conflict_audit_ids"]
    assert repo.get_node("VerifiedOutcome", "orderflow:" + RUN) == original


def test_missing_public_runtime_classified_without_ingestion(repo, tmp_path):
    evidence = prepared(tmp_path)
    evidence.report.pop("scenario_metadata")
    evidence.commit()
    output = tmp_path / "receipt.json"
    before = repo.state_fingerprint()
    assert cli.main(arguments(evidence, output)) == 2
    assert json.loads(output.read_text())["status"] == "TRUST_CONTRACT_REJECTED"
    assert repo.state_fingerprint() == before


def test_existing_receipt_not_overwritten_or_graph_mutated(repo, tmp_path):
    evidence = prepared(tmp_path)
    output = tmp_path / "receipt.json"
    output.write_text("preserve earlier receipt")
    before = repo.state_fingerprint()
    assert cli.main(arguments(evidence, output)) == 2
    assert output.read_text() == "preserve earlier receipt"
    assert repo.state_fingerprint() == before


def test_receipt_cannot_pollute_sealed_run(repo, tmp_path):
    evidence = prepared(tmp_path)
    output = evidence.run / "forbidden-receipt.json"
    before = repo.state_fingerprint()
    assert cli.main(arguments(evidence, output)) == 2
    assert not output.exists() and repo.state_fingerprint() == before


def test_receipt_parent_symlink_refused(repo, tmp_path):
    evidence = prepared(tmp_path)
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path, target_is_directory=True)
    before = repo.state_fingerprint()
    assert cli.main(arguments(evidence, linked / "receipt.json")) == 2
    assert not (tmp_path / "receipt.json").exists() and repo.state_fingerprint() == before


def test_caller_verdict_flag_is_not_supported(repo, tmp_path):
    evidence = prepared(tmp_path)
    output = tmp_path / "receipt.json"
    before = repo.state_fingerprint()
    with pytest.raises(SystemExit) as rejected:
        cli.main(arguments(evidence, output) + ["--verdict", "PASS"])
    assert rejected.value.code == 2
    assert not output.exists() and repo.state_fingerprint() == before


def test_source_traversal_and_run_identity_rejected_before_graph(repo, tmp_path):
    evidence = prepared(tmp_path)
    output = tmp_path / "receipt.json"
    args = arguments(evidence, output)
    args[args.index("--source-snapshot-relative-path") + 1] = "../final_source_snapshot"
    before = repo.state_fingerprint()
    assert cli.main(args) == 2 and repo.state_fingerprint() == before
    assert not output.exists()
