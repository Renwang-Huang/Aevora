"""Pure synthetic archive contracts; not evidence of model/DB/test execution.

Every export uses the unchanged exporter/verifier, without mocked runtime calls.
"""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from benchmark import evidence_export as legacy
from benchmark import evidence_verify

_spec = importlib.util.spec_from_file_location("h2_export_contract_impl",
    Path(__file__).resolve().parents[1] / "scripts/aevora_h2_export.py")
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)
RUN = "11111111-1111-4111-8111-111111111111"
READBACK = "22222222-2222-4222-8222-222222222222"
UNSELECTED = "33333333-3333-4333-8333-333333333333"
TIME = "2026-10-11T00:00:00+00:00"


def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return path


def freeze(root, *, special=None):
    files = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
             for p in root.rglob("*") if p.is_file() and p.name != "EVIDENCE_MANIFEST.json"}
    if special:
        files.update(special)
    put(root, "EVIDENCE_MANIFEST.json", {"ordinary_files_sha256": files,
        "total_bytes": sum((root / p).stat().st_size for p in files), "classification": "SYNTHETIC_CONTRACT_ONLY"})


@pytest.fixture
def full(tmp_path):
    root = tmp_path / "full"
    root.mkdir()
    challenge = "g3/live/runs/" + RUN
    report = {"run_id": RUN, "episode_id": "D-V02", "scenario_version": "synthetic-only",
        "scenario_variant": "v02", "overall_status": "ERROR", "runtime_status": "ERROR",
        "evaluation_status": "NOT_RUN", "submission_integrity_status": "NOT_RUN",
        "multi_agent_status": "UNVERIFIED", "integration_status": "PARTIAL", "test_results": None,
        "database_oracle": [], "fingerprints": {}, "pytest_exit_code": None,
        "qualification": "SYNTHETIC_ARCHIVE_CONTRACT; NO_MODEL_EXECUTION"}
    put(root, challenge + "/evaluation_report.json", report)
    put(root, challenge + "/runtime_metadata.json", {"run_id": RUN, "runtime_result": "ERROR",
        "model": "synthetic-only", "provider": "synthetic-only", "agent_mode": "multi"})
    put(root, challenge + "/run_evidence_manifest.json", {"run_id": RUN, "files": {}})
    raw = b'{"type":"thread.started","thread_id":"synthetic-only"}\n'
    (root / challenge / "codex_events.jsonl").write_bytes(raw)
    put(root, challenge + "/aevora_mcp_events.jsonl", {"source": "SYNTHETIC_CONTRACT_ONLY", "method": "resolve_experience"})
    put(root, challenge + "/artifacts/native_rollouts/child.jsonl", {"source": "SYNTHETIC_CONTRACT_ONLY", "type": "session_meta"})
    put(root, challenge + "/artifacts/topology-huge.json", {"classification": "FULL_TOPOLOGY_POINTER_ONLY"})
    observation = "g3/observation_session/runs/" + READBACK
    put(root, observation + "/observation_report.json", {"kind": "NEW_SESSION_READ_ONLY_EVIDENCE_OBSERVATION",
        "run_id": READBACK, "evaluation_result": "NOT_EXECUTED", "adapter_runtime_result": "ERROR",
        "adapter_failure_kind": "NO_PATCH", "source_unchanged": True, "classification": "SYNTHETIC_CONTRACT_ONLY"})
    put(root, observation + "/runtime_metadata.json", {"run_id": READBACK, "runtime_result": "ERROR",
        "failure_kind": "NO_PATCH", "qualification": "SYNTHETIC_CONTRACT_ONLY"})
    put(root, observation + "/codex_events.jsonl", {"source": "SYNTHETIC_CONTRACT_ONLY", "type": "thread.completed"})
    put(root, observation + "/aevora_mcp_events.jsonl", {"source": "SYNTHETIC_CONTRACT_ONLY", "method": "build_evidence_bundle"})
    put(root, observation + "/run_evidence_manifest.json", {"run_id": READBACK, "files": {}})
    put(root, "g2/repeat/ATTEMPTS.jsonl", {"classification": "SYNTHETIC_CONTRACT_ONLY", "actual": "FAIL"})
    put(root, "g2/repeat/SOURCE_EPOCH.json", {"files": {"app/source.py": "1" * 64}})
    put(root, "g2/runs/" + UNSELECTED + "/evaluation_report.json", {"run_id": UNSELECTED, "overall_status": "ERROR"})
    put(root, "G0_GATE.json", {"status": "PARTIAL", "classification": "SYNTHETIC_CONTRACT_ONLY"})
    put(root, "security/SECURITY_GATE.json", {"status": "FAIL", "classification": "SYNTHETIC_CONTRACT_ONLY"})
    put(root, "recovery/RECOVERY_GATE.json", {"status": "PARTIAL", "classification": "SYNTHETIC_CONTRACT_ONLY"})
    put(root, "g3/check/command.json", {"argv": ["synthetic-contract-command"], "exit_code": 2})
    put(root, "release/command-2.json", {"argv": ["synthetic-contract-command"], "exit_code": 1})
    put(root, "g3/QUERY_SNAPSHOT_REFS.json", {"classification": "SYNTHETIC_CONTRACT_ONLY", "query_id": "synthetic"})
    put(root, "AUDIT_KEY_CYPHER.json", {"classification": "SYNTHETIC_CONTRACT_ONLY", "query": "RETURN 1"})
    put(root, "AUDIT_CHANGE_MANIFEST.json", {"classification": "SYNTHETIC_CONTRACT_ONLY", "files": {}})
    put(root, "g3/trusted_graph_commands.jsonl", {"classification": "FULL_RAW_CYPHER_POINTER_ONLY"})
    put(root, "g3/GRAPH_AFTER.json", {"classification": "FULL_RAW_GRAPH_POINTER_ONLY"})
    core = root / "g3/frozen_source_snapshot/aevora_core/src/aevora/models.py"
    core.parent.mkdir(parents=True); core.write_text('"""Synthetic core source export contract."""\n')
    doc = root / "g3/frozen_source_snapshot/aevora_core/docs/GRAPH_SCHEMA.md"
    doc.parent.mkdir(parents=True); doc.write_text("# Synthetic schema contract\n")
    put(root, "reports/AEVORA_H2_REPORT.json", {"classification": "SYNTHETIC_CONTRACT_ONLY", "status": "PARTIAL"})
    hidden = root / "g3/frozen_source_snapshot/evaluator/hidden_tests/test_hidden.py"
    hidden.parent.mkdir(parents=True); hidden.write_text("# must never export\n")
    builder = root / "g3/frozen_source_snapshot/benchmark/episodes/episode_d_v02.py"
    builder.parent.mkdir(parents=True); builder.write_text("# private repair factory must never export\n")
    (root / "contracts.junit.xml").write_text('<testsuite tests="0" errors="0" failures="0" skipped="0"/>')
    freeze(root)
    return root


def export(full, tmp_path, name="h2.zip", **kwargs):
    return adapter.export_h2(full, tmp_path / name, run_ids=[RUN], observation_run_ids=[READBACK],
        created_at=TIME, **kwargs)


def bundle_parts(path):
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        entries = {r["source_path"]: r for r in manifest["entries"]}
        omitted = json.loads(z.read("NOT_INCLUDED.json"))["entries"]
        index = json.loads(z.read("RUN_INDEX.json"))
    return entries, omitted, index


def test_actual_adapter_preserves_full_bytes_and_keeps_observation_unscored(full, tmp_path):
    before = {p.relative_to(full).as_posix(): sha256(p.read_bytes()).hexdigest() for p in full.rglob("*") if p.is_file()}
    original = legacy._selection
    receipt = export(full, tmp_path)
    assert receipt["status"] == "PASS" and receipt["source_writes"] is False
    assert receipt["worker_exit_code"] == 0 and receipt["selected_observation_session_ids"] == [READBACK]
    assert legacy._selection is original
    entries, _, index = bundle_parts(tmp_path / "h2.zip")
    assert [r["run_id"] for r in index["runs"]] == [RUN]
    assert index["runs"][0]["evaluation_status"] == "NOT_RUN"
    observation = "g3/observation_session/runs/" + READBACK
    assert entries[observation + "/observation_report.json"]["run_id"] is None
    assert not any(p.endswith(READBACK + "/evaluation_report.json") for p in entries)
    after = {p.relative_to(full).as_posix(): sha256(p.read_bytes()).hexdigest() for p in full.rglob("*") if p.is_file()}
    assert before == after


def test_h2_gate_core_schema_attempts_and_command_receipts_are_selected(full, tmp_path):
    export(full, tmp_path)
    entries, omitted, _ = bundle_parts(tmp_path / "h2.zip")
    required = {"G0_GATE.json", "security/SECURITY_GATE.json", "recovery/RECOVERY_GATE.json",
        "g2/repeat/ATTEMPTS.jsonl", "g2/repeat/SOURCE_EPOCH.json", "g3/check/command.json",
        "release/command-2.json", "g3/QUERY_SNAPSHOT_REFS.json", "AUDIT_KEY_CYPHER.json",
        "AUDIT_CHANGE_MANIFEST.json", "reports/AEVORA_H2_REPORT.json", "contracts.junit.xml",
        "g3/frozen_source_snapshot/aevora_core/src/aevora/models.py",
        "g3/frozen_source_snapshot/aevora_core/docs/GRAPH_SCHEMA.md"}
    assert required <= set(entries)
    assert entries["g3/check/command.json"]["role"] == "COMMAND_RECEIPT"
    assert entries["g2/repeat/ATTEMPTS.jsonl"]["slice_status"] == "COMPLETE_FILE"
    omitted_paths = {v["source_path"] for v in omitted}
    assert {"g3/trusted_graph_commands.jsonl", "g3/GRAPH_AFTER.json",
        "g3/frozen_source_snapshot/evaluator/hidden_tests/test_hidden.py",
        "g3/frozen_source_snapshot/benchmark/episodes/episode_d_v02.py",
        "g2/runs/" + UNSELECTED + "/evaluation_report.json",
        "g3/live/runs/" + RUN + "/artifacts/topology-huge.json"} <= omitted_paths
    assert all(v["status"] == "NOT_INCLUDED" and len(v["source_sha256"]) == 64 for v in omitted)


def test_native_child_and_both_sessions_mcp_are_complete_files(full, tmp_path):
    export(full, tmp_path)
    entries, _, _ = bundle_parts(tmp_path / "h2.zip")
    required = ["g3/live/runs/" + RUN + "/codex_events.jsonl",
        "g3/live/runs/" + RUN + "/artifacts/native_rollouts/child.jsonl",
        "g3/live/runs/" + RUN + "/aevora_mcp_events.jsonl",
        "g3/observation_session/runs/" + READBACK + "/codex_events.jsonl",
        "g3/observation_session/runs/" + READBACK + "/aevora_mcp_events.jsonl"]
    for p in required:
        assert entries[p]["slice_status"] == "COMPLETE_FILE" and entries[p]["line_range"] == [1, 1]
        assert entries[p]["line_provenance"][0]["source_sha256"] == sha256((full / p).read_bytes()).hexdigest()


def test_manual_repeat_junit_and_recovery_matrix_are_support_without_fake_scored_rows(full, tmp_path):
    prefix = "g2/runs/" + UNSELECTED + "/artifacts/"
    path = full / (prefix + "junit.xml")
    path.parent.mkdir(parents=True)
    path.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    put(full, prefix + "recovery-request-method-phase-matrix.json",
        {"classification": "SYNTHETIC_CONTRACT_ONLY", "status": "INCOMPLETE"})
    put(full, prefix + "topology-large.json", {"classification": "FULL_ONLY"})
    freeze(full); export(full, tmp_path)
    entries, omitted, index = bundle_parts(tmp_path / "h2.zip")
    assert {prefix + "junit.xml", prefix + "recovery-request-method-phase-matrix.json"} <= set(entries)
    assert entries[prefix + "junit.xml"]["run_id"] is None
    assert entries[prefix + "recovery-request-method-phase-matrix.json"]["run_id"] is None
    assert {r["run_id"] for r in index["runs"]} == {RUN}
    assert prefix + "topology-large.json" in {r["source_path"] for r in omitted}
    assert "g2/runs/" + UNSELECTED + "/evaluation_report.json" not in entries


def test_explicit_fixed_timestamp_preserves_zip_determinism(full, tmp_path):
    a = export(full, tmp_path, "first.zip")
    b = export(full, tmp_path, "second.zip")
    assert a["bundle_sha256"] == b["bundle_sha256"]
    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()


def test_standalone_trusted_verifier_works_offline_outside_repository(full, tmp_path):
    export(full, tmp_path)
    isolated = tmp_path / "independent"; isolated.mkdir()
    trusted = isolated / "trusted_verify.py"
    trusted.write_bytes(Path(evidence_verify.__file__).read_bytes())
    process = subprocess.run([sys.executable, "-I", "-B", str(trusted), "verify", str(tmp_path / "h2.zip"), "--json"],
        cwd=isolated, capture_output=True, timeout=20, env={})
    result = json.loads(process.stdout)
    assert process.returncode == 0 and result["status"] == "PASS"
    assert result["network_used"] is False and result["archive_extracted"] is False


def test_byte_tamper_is_rejected_by_the_unchanged_independent_verifier(full, tmp_path):
    export(full, tmp_path)
    with zipfile.ZipFile(tmp_path / "h2.zip") as original:
        parts = {n: original.read(n) for n in original.namelist()}
    parts["README_AUDIT.md"] += b"single-byte-tamper"
    with zipfile.ZipFile(tmp_path / "tampered.zip", "w", compression=zipfile.ZIP_DEFLATED) as out:
        for n, data in parts.items(): out.writestr(n, data)
    with pytest.raises(evidence_verify.EvidenceVerifyError, match="Checksum mismatch"):
        evidence_verify.verify_bundle(tmp_path / "tampered.zip")


def test_reuses_redaction_without_reading_actual_credentials(full, tmp_path):
    fake = "sk-syntheticH2contractONLYABCDEFGHIJ1234567890"
    raw = full / ("g3/live/runs/" + RUN + "/aevora_mcp_events.jsonl")
    raw.write_text(json.dumps({"synthetic_only": True, "api_key": fake, "path": "/home/synthetic-user/private"}) + "\n")
    freeze(full); original = raw.read_bytes()
    export(full, tmp_path)
    with zipfile.ZipFile(tmp_path / "h2.zip") as z:
        data = b"\n".join(z.read(p) for p in z.namelist())
    assert fake.encode() not in data and b"/home/synthetic-user" not in data
    assert raw.read_bytes() == original


def test_existing_full_and_output_are_not_overwritten(full, tmp_path):
    export(full, tmp_path)
    prior = (tmp_path / "h2.zip").read_bytes()
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)
    assert (tmp_path / "h2.zip").read_bytes() == prior


def test_output_inside_full_is_rejected(full):
    with pytest.raises(adapter.H2ExportError):
        adapter.export_h2(full, full / "bad.zip", run_ids=[RUN], created_at=TIME)
    assert not (full / "bad.zip").exists()


def test_final_full_seal_is_required(full, tmp_path):
    (full / "EVIDENCE_MANIFEST.json").unlink()
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)
    assert not (tmp_path / "h2.zip").exists()


def test_changed_source_bytes_cannot_be_exported_under_old_sha(full, tmp_path):
    (full / "G0_GATE.json").write_text('{"status":"changed-after-seal"}\n')
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)
    assert not (tmp_path / "h2.zip").exists()


@pytest.mark.parametrize("ids", [[], [RUN, RUN], ["not-a-run"], ["AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"]])
def test_invalid_or_duplicate_primary_ids_are_rejected(full, tmp_path, ids):
    with pytest.raises(adapter.H2ExportError):
        adapter.export_h2(full, tmp_path / "bad.zip", run_ids=ids, created_at=TIME)


def test_primary_and_readback_roles_cannot_collide(full, tmp_path):
    with pytest.raises(adapter.H2ExportError):
        adapter.export_h2(full, tmp_path / "bad.zip", run_ids=[RUN], observation_run_ids=[RUN], created_at=TIME)


def test_readback_is_not_selected_as_an_engineering_run(full, tmp_path):
    with pytest.raises(adapter.H2ExportError):
        adapter.export_h2(full, tmp_path / "bad.zip", run_ids=[READBACK], created_at=TIME)


def test_observation_cannot_claim_scored_pass(full, tmp_path):
    put(full, "g3/observation_session/runs/" + READBACK + "/observation_report.json",
        {"kind": "NEW_SESSION_READ_ONLY_EVIDENCE_OBSERVATION", "run_id": READBACK, "evaluation_result": "PASS"})
    freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


def test_observation_needs_a_stopped_matching_seal(full, tmp_path):
    put(full, "g3/observation_session/runs/" + READBACK + "/run_evidence_manifest.json",
        {"run_id": RUN, "files": {}})
    freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


def test_live_observation_state_is_refused(full, tmp_path):
    (full / ("g3/observation_session/runs/" + READBACK + "/codex-state")).mkdir()
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


@pytest.mark.parametrize("relative", ["../escape.json", "/absolute.json", "g3/frozen_source_snapshot/evaluator/hidden_tests/test_hidden.py",
    "g3/frozen_source_snapshot/benchmark/episodes/episode_d_v02.py", "g3/trusted_graph_commands.jsonl"])
def test_explicit_selection_cannot_bypass_private_and_heavy_boundaries(full, tmp_path, relative):
    with pytest.raises((adapter.H2ExportError, evidence_verify.EvidenceVerifyError)):
        export(full, tmp_path, support_paths=[relative])


def test_large_supporting_file_is_full_pointer_and_explicit_inclusion_fails(full, tmp_path):
    large = full / "reports/LARGE_REPORT.md"
    large.write_bytes(b"SYNTHETIC_SUPPORT_ONLY\n" + b"x" * adapter.MAX_SUPPORT_BYTES)
    freeze(full); export(full, tmp_path)
    entries, omitted, _ = bundle_parts(tmp_path / "h2.zip")
    assert "reports/LARGE_REPORT.md" not in entries
    row = next(r for r in omitted if r["source_path"] == "reports/LARGE_REPORT.md")
    assert row["source_sha256"] == sha256(large.read_bytes()).hexdigest()
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path, "explicit.zip", support_paths=["reports/LARGE_REPORT.md"])


def test_selected_supporting_hardlink_is_error_not_silent_omission(full, tmp_path):
    os.link(full / "G0_GATE.json", full / "SECOND_GATE.json")
    freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


def test_supporting_fifo_inspection_is_nonblocking_and_rejected(full, tmp_path):
    fifo = full / "FIFO_GATE.json"; os.mkfifo(fifo)
    freeze(full, special={"FIFO_GATE.json": "0" * 64})
    command = [sys.executable, "-I", "-B", str(Path(adapter.__file__)), "_worker", str(full), str(tmp_path / "fifo.zip"),
        "--run-id", RUN, "--created-at", TIME]
    process = subprocess.run(command, capture_output=True, timeout=3, env={})
    assert process.returncode == 2 and json.loads(process.stdout)["status"] == "ERROR"
    assert not (tmp_path / "fifo.zip").exists()


def test_symlink_ancestor_is_refused(full, tmp_path):
    alias = tmp_path / "linked"; alias.symlink_to(full, target_is_directory=True)
    with pytest.raises(adapter.H2ExportError):
        adapter.export_h2(alias, tmp_path / "bad.zip", run_ids=[RUN], created_at=TIME)


@pytest.mark.parametrize("timeout", [0, -1, 1801, True])
def test_offline_resource_timeout_is_explicitly_bounded(full, tmp_path, timeout):
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path, timeout_seconds=timeout)


def test_original_capacity_limits_and_verifier_source_remain_authoritative():
    assert legacy.MAX_SOURCE_BYTES == 128 * 1024**2 and legacy.MAX_SELECTED_BYTES == 512 * 1024**2
    assert evidence_verify.MAX_MEMBER_BYTES == 128 * 1024**2
    assert evidence_verify.MAX_TOTAL_BYTES == 512 * 1024**2 and evidence_verify.MAX_ZIP_BYTES == 256 * 1024**2


def prepared_readback_fixture(full):
    """Faithful Runner.prepare shape; still explicitly synthetic, no model credit."""
    prefix = "g3/observation_session/runs/" + READBACK
    report = {"run_id": READBACK, "overall_status": "PREPARED", "lifecycle": ["LOAD", "PREPARE"],
              "test_results": None, "submission": None, "ended_at": None, "execution_errors": []}
    path = put(full, prefix + "/evaluation_report.json", report)
    observation = json.loads((full / prefix / "observation_report.json").read_text())
    observation.update(source_unchanged=True, public_inputs_unchanged=True, native_turn_complete=True)
    put(full, prefix + "/observation_report.json", observation)
    put(full, prefix + "/runtime_metadata.json", {"run_id": READBACK, "runtime_result": "ERROR",
        "failure_kind": "NO_PATCH", "exit_code": 0, "fresh_session": True,
        "qualification": "SYNTHETIC_ARCHIVE_CONTRACT; NO_MODEL_EXECUTION"})
    put(full, prefix + "/run_evidence_manifest.json", {"run_id": READBACK,
        "files": {"evaluation_report.json": sha256(path.read_bytes()).hexdigest()}})
    freeze(full)
    return prefix


def test_actual_runner_prepared_readback_stays_original_unscored_pointer(full, tmp_path):
    prefix = prepared_readback_fixture(full)
    original = (full / prefix / "evaluation_report.json").read_bytes()
    receipt = export(full, tmp_path)
    entries, omitted, index = bundle_parts(tmp_path / "h2.zip")
    assert receipt["adapter_version"] == "aevora.h2-audit-lite/1.0.1"
    assert prefix + "/evaluation_report.json" not in entries
    assert prefix + "/evaluation_report.json" in {v["source_path"] for v in omitted}
    assert [r["run_id"] for r in index["runs"]] == [RUN]
    assert (full / prefix / "evaluation_report.json").read_bytes() == original


@pytest.mark.parametrize("status", ["PASS", "FAIL", "ERROR", "TIMEOUT", "NOT_IMPLEMENTED", "NOT_RUN"])
def test_prepared_observation_cannot_disguise_any_nonprepared_grade(full, tmp_path, status):
    prefix = prepared_readback_fixture(full)
    report = json.loads((full / prefix / "evaluation_report.json").read_text()); report["overall_status"] = status
    path = put(full, prefix + "/evaluation_report.json", report)
    put(full, prefix + "/run_evidence_manifest.json", {"run_id": READBACK,
        "files": {"evaluation_report.json": sha256(path.read_bytes()).hexdigest()}})
    freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


@pytest.mark.parametrize("field,value", [("test_results", {}), ("pytest_exit_code", 0),
    ("submission", {}), ("runtime_result", "PASS"), ("evaluation_result", "PASS"),
    ("evaluation_started_at", TIME), ("evaluation_ended_at", TIME), ("ended_at", TIME),
    ("database_oracle", [{"pass": True}]), ("execution_errors", ["actual"]),
    ("lifecycle", ["LOAD", "PREPARE", "EVALUATE"]), ("run_id", RUN)])
def test_prepared_label_cannot_hide_execution_or_score_fields(full, tmp_path, field, value):
    prefix = prepared_readback_fixture(full)
    report = json.loads((full / prefix / "evaluation_report.json").read_text()); report[field] = value
    path = put(full, prefix + "/evaluation_report.json", report)
    put(full, prefix + "/run_evidence_manifest.json", {"run_id": READBACK,
        "files": {"evaluation_report.json": sha256(path.read_bytes()).hexdigest()}})
    freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


@pytest.mark.parametrize("field,value", [("failure_kind", "TIMEOUT"), ("runtime_result", "PASS"),
    ("exit_code", 1), ("exit_code", False), ("fresh_session", False), ("run_id", RUN)])
def test_prepared_observation_needs_matching_no_patch_runtime(full, tmp_path, field, value):
    prefix = prepared_readback_fixture(full)
    runtime = json.loads((full / prefix / "runtime_metadata.json").read_text()); runtime[field] = value
    put(full, prefix + "/runtime_metadata.json", runtime); freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


@pytest.mark.parametrize("field", ["source_unchanged", "public_inputs_unchanged", "native_turn_complete"])
def test_prepared_observation_needs_unchanged_complete_public_session(full, tmp_path, field):
    prefix = prepared_readback_fixture(full)
    report = json.loads((full / prefix / "observation_report.json").read_text()); report[field] = False
    put(full, prefix + "/observation_report.json", report); freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)


def test_prepared_readback_cannot_be_explicitly_selected_as_report(full, tmp_path):
    prefix = prepared_readback_fixture(full)
    with pytest.raises(adapter.H2ExportError):
        export(full, tmp_path, support_paths=[prefix + "/evaluation_report.json"])


def test_prepared_readback_requires_its_original_run_seal_hash(full, tmp_path):
    prefix = prepared_readback_fixture(full)
    put(full, prefix + "/run_evidence_manifest.json", {"run_id": READBACK, "files": {}}); freeze(full)
    with pytest.raises(adapter.H2ExportError): export(full, tmp_path)
