"""Record-only demo checks; every fabricated closure is explicitly synthetic.

No DB, Docker, subprocess, candidate or model is executed by these tests.
Positive fixture checks do not constitute real H1 Gate or native evidence.
"""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import aevora_demo as demo
from aevora_core.tests.test_orderflow_outcome_bridge import Evidence, RUN, write_json
from aevora.orderflow_outcome_bridge import M1_SEED_RUNS

OBSERVATION = "6bbae0aa-d651-4a63-a170-783f92381c19"


@pytest.fixture(autouse=True)
def synthetic_launcher_environment(monkeypatch):
    # Record-only contracts must not inherit real maintainer mount markers
    # from whichever trusted launcher runs the developer test suite.
    for name in ("AEVORA_FALKORDB_PASSWORD_FILE", "ORDERFLOW_GATEWAY_SECRET_PATH", "ORDERFLOW_CODEX_BINARY"):
        monkeypatch.delenv(name, raising=False)


def sealed(run):
    files = {path.relative_to(run).as_posix(): sha256(path.read_bytes()).hexdigest()
             for path in run.rglob("*") if path.is_file() and path.name != "run_evidence_manifest.json"}
    path = run / "run_evidence_manifest.json"
    write_json(path, {"run_id": run.name, "sealed_at": "2026-10-11T08:00:00+00:00", "files": files,
                      "previous_seal_sha256": files["input_seal.json"], "refused_entries": []})
    return sha256(path.read_bytes()).hexdigest()


def fixture_index(tmp_path, *, failed=False):
    """Pinned small synthetic archives exercising real bounded verifier code."""
    evidence = Evidence(tmp_path / "source", episode="D", fail=failed)
    write_json(evidence.run / "input_seal.json", {"fixture_type": "synthetic_record_only"})
    write_json(evidence.run / "runtime_metadata.json", {"run_id": RUN, "thread_id": "synthetic-challenge-thread",
                                                      "session_id": "synthetic-challenge-session"})
    evidence.commit()
    challenge_seal = sealed(evidence.run)
    observation = tmp_path / "observation/runs" / OBSERVATION
    observation.mkdir(parents=True)
    write_json(observation / "input_seal.json", {"fixture_type": "synthetic_record_only"})
    write_json(observation / "runtime_metadata.json", {"run_id": OBSERVATION, "thread_id": "synthetic-observation-thread",
        "session_id": "synthetic-observation-session"})
    write_json(observation / "observation_report.json", {"run_id": OBSERVATION, "evaluation_result": "NOT_EXECUTED",
        "submission": None, "source_unchanged": True, "source_before_sha256": "1" * 64,
        "source_after_sha256": "1" * 64, "session_observation_status": "COMPLETE"})
    raw = b'{"fixture_type":"synthetic_record_only","not_actual_native_event":true}\n'
    for name in ("aevora_mcp_events.jsonl", "codex_events.jsonl"):
        (observation / name).write_bytes(raw)
    observation_seal = sealed(observation)
    outcome_id = "orderflow:" + RUN
    observed_path = {"relation": "OBSERVED_OUTCOME", "records": {"VerifiedOutcome": {"id": outcome_id}}}
    graph_state = {"graph_name": "synthetic_record_only_namespace", "node_count": 60,
                   "edge_count": 101, "graph_sha256": "2" * 64}
    # These are synthetic structured copies of the required historical IDs,
    # never an assertion that this unit fixture imported the real graph.
    public_paths = {"fixture_type": "synthetic_record_only", "observed": [observed_path],
        "historical": [{"id": "orderflow:" + run, "verdict": "FAIL" if label == "rlock_d" else "PASS"}
                       for label, run in M1_SEED_RUNS.items()]}
    audit = {"run_id": OBSERVATION, "source_seal": {"seal_sha256": observation_seal},
        "native_integrity": {"status": "COMPLETE"}, "native_session_id": "synthetic-observation-session",
        "new_session_outcome_observation": {"status": "OBSERVED_IN_HOST_AND_TYPED_NATIVE_OUTPUT",
            "trusted_outcome_id": outcome_id, "matches": [{"actual_path": observed_path,
                "path_sha256": sha256(json.dumps(observed_path, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
                "host_reference": {"path": str(observation / "aevora_mcp_events.jsonl"), "line": 1, "sha256": sha256(raw).hexdigest()},
                "native_reference": {"path": str(observation / "codex_events.jsonl"), "line": 1, "sha256": sha256(raw).hexdigest()}}]}}
    write_json(tmp_path / "observation_audit.json", audit)
    feedback = {"status": "INGESTED", "exit_code": 0, "idempotent": True, "run_id": RUN,
        "run_seal_sha256": challenge_seal, "source_manifest_sha256": evidence.anchor.manifest_sha256,
        "attribution": "UNKNOWN", "adoption": "UNVERIFIED", "final_graph": graph_state,
        "ingestion": {"outcome_id": outcome_id, "run_id": RUN,
            "verdict": "FAIL" if failed else "PASS", "feedback_status": "outcome_observed_no_attribution",
            "receipts": [{"id": "synthetic-observed-feedback"}]}}
    write_json(tmp_path / "feedback.json", feedback)
    persistence_paths = {"save_command": "g4-rdb-explicit-save/command.json",
                         "restart_command": "g4-container-rdb-restart/command.json",
                         "before_snapshot": "G4_BEFORE_RESTART.json", "after_snapshot": "G4_AFTER_RESTART.json"}
    for label, argv in (("save_command", ["docker", "exec", "synthetic", "redis-cli", "SAVE"]),
                        ("restart_command", ["docker", "compose", "restart", "synthetic"])):
        write_json(tmp_path / persistence_paths[label], {"fixture_type": "synthetic_record_only", "argv": argv, "exit_code": 0})
    for label in ("before_snapshot", "after_snapshot"):
        write_json(tmp_path / persistence_paths[label], {"fixture_type": "synthetic_record_only",
                    "graph_state": graph_state, "public_paths": public_paths})
    gates = {}
    for number in range(6):
        name = f"G{number}.json"
        write_json(tmp_path / name, {"status": "PASS", "fixture_type": "synthetic_record_only",
                                    "state": {"graph_name": "synthetic_record_only_namespace"}})
        gates[f"G{number}"] = {"path": name, "sha256": sha256((tmp_path / name).read_bytes()).hexdigest()}
    files = {name: sha256((tmp_path / name).read_bytes()).hexdigest() for name in
        ["source/EVIDENCE_MANIFEST.json", "feedback.json", "observation_audit.json"] + [f"G{i}.json" for i in range(6)] + list(persistence_paths.values())}
    index = {"schema_version": demo.SCHEMA, "synthetic_record_only_fixture": True, "files": files,
        "source_anchor": {"archive_path": "source", "manifest_relative_path": "EVIDENCE_MANIFEST.json",
                          "sha256": evidence.anchor.manifest_sha256, "snapshot_relative_path": "final_source_snapshot"},
        "gates": gates, "runs": {"challenge": {"run_id": RUN, "path": evidence.run.relative_to(tmp_path).as_posix(), "seal_sha256": challenge_seal},
            "observation": {"run_id": OBSERVATION, "path": observation.relative_to(tmp_path).as_posix(), "seal_sha256": observation_seal}},
        "feedback": {"path": "feedback.json", "sha256": files["feedback.json"], "outcome_id": outcome_id},
        "persistence": {label: {"path": name, "sha256": files[name]} for label, name in persistence_paths.items()},
        "observation_trace_audit": {"path": "observation_audit.json", "sha256": files["observation_audit.json"], "trusted_outcome_id": outcome_id}}
    return evidence, index


def verify(tmp_path, index):
    path = tmp_path / "CLOSURE_INDEX.json"
    write_json(path, index)
    return demo.verify_existing(tmp_path, path.name, sha256(path.read_bytes()).hexdigest())


def repin(tmp_path, index, name):
    value = sha256((tmp_path / name).read_bytes()).hexdigest()
    index["files"][name] = value
    for record in [*index["gates"].values(), *index["persistence"].values(), index["feedback"], index["observation_trace_audit"]]:
        if record["path"] == name:
            record["sha256"] = value


def test_plan_only_generates_existing_argv_and_deferred_parameters(tmp_path, monkeypatch):
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("No subprocess permitted in plan"))
    result = demo.plan(tmp_path / "new-full", tmp_path / "history", None, "regression/command.json")
    assert result["status"] == "PLAN_ONLY" and result["executed"] is False
    stages = {row["stage"]: row for row in result["stages"]}
    assert "aevora_live.py" in stages["native_D"]["argv"][-5]
    assert stages["trusted_ingest"]["required_parameters"] == ["challenge_run_id", "approved_run_seal_sha256", "approved_pre_live_source_sha256"]
    assert stages["rdb_save"]["manual_only"] is True and stages["rdb_restart"]["manual_only"] is True
    assert stages["fresh_read_only_observation"]["argv"][-2].endswith("aevora_new_session_probe.py")
    assert not (tmp_path / "new-full").exists()


def test_synthetic_closure_consistency_is_never_real_h1_pass(tmp_path):
    _, index = fixture_index(tmp_path)
    result = verify(tmp_path, index)
    assert result["consistency"] == "PASS" and result["closure_result"] == "SYNTHETIC_CONSISTENCY_ONLY"
    assert result["model_called"] is False and result["graph_contacted"] is False
    assert result["candidate_executed"] is False and result["source_modified"] is False
    assert result["session_ids_distinct"] is True


def test_valid_business_fail_remains_fail(tmp_path):
    _, index = fixture_index(tmp_path, failed=True)
    result = verify(tmp_path, index)
    assert result["consistency"] == "PASS" and result["episode_d_task_outcome"] == "FAIL"
    assert result["closure_result"] == "SYNTHETIC_CONSISTENCY_ONLY"


def unavailable_session_fixture(tmp_path):
    """Synthetic fallback authority; official events remain record-only."""
    _, index = fixture_index(tmp_path)
    run = tmp_path / index["runs"]["observation"]["path"]
    metadata = json.loads((run / "runtime_metadata.json").read_text())
    metadata["session_id"] = "UNAVAILABLE"
    write_json(run / "runtime_metadata.json", metadata)
    report = json.loads((run / "observation_report.json").read_text())
    report.update({"session_id": "UNAVAILABLE", "thread_id": metadata["thread_id"]})
    write_json(run / "observation_report.json", report)
    raw = (run / "codex_events.jsonl").read_bytes()
    event = json.dumps({"type": "thread.started", "thread_id": metadata["thread_id"],
                        "fixture_type": "synthetic_record_only", "not_actual_native_event": True}).encode() + b"\n"
    (run / "codex_events.jsonl").write_bytes(event + raw)
    audit = json.loads((tmp_path / "observation_audit.json").read_text())
    audit["native_session_id"] = metadata["thread_id"]
    audit["new_session_outcome_observation"]["matches"][0]["native_reference"]["line"] = 2
    refresh_observation(tmp_path, index, audit)
    return index, run, audit


def refresh_observation(tmp_path, index, audit):
    run = tmp_path / index["runs"]["observation"]["path"]
    seal_sha = sealed(run)
    index["runs"]["observation"]["seal_sha256"] = seal_sha
    audit["source_seal"]["seal_sha256"] = seal_sha
    write_json(tmp_path / "observation_audit.json", audit)
    repin(tmp_path, index, "observation_audit.json")


def test_unavailable_session_accepts_only_sealed_official_thread_identity_without_backfill(tmp_path):
    index, run, _ = unavailable_session_fixture(tmp_path)
    before = {p: sha256(p.read_bytes()).hexdigest() for p in run.rglob("*") if p.is_file()}
    result = verify(tmp_path, index)
    assert result["consistency"] == "PASS" and result["closure_result"] == "SYNTHETIC_CONSISTENCY_ONLY"
    assert result["observation_session_id"] == "UNAVAILABLE"
    assert result["observation_identity_source"] == "sealed_official_thread.started"
    assert before == {p: sha256(p.read_bytes()).hexdigest() for p in run.rglob("*") if p.is_file()}
    assert json.loads((run / "runtime_metadata.json").read_text())["session_id"] == "UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["audit_incomplete", "native_mismatch", "report_thread_mismatch", "metadata_thread_mismatch", "official_missing", "official_multiple", "official_thread_mismatch", "missing_session_field"])
def test_unavailable_session_fallback_rejects_unproved_or_ambiguous_identity(tmp_path, mutation):
    index, run, audit = unavailable_session_fixture(tmp_path)
    if mutation == "audit_incomplete":
        audit["native_integrity"]["status"] = "INCOMPLETE"
    elif mutation == "native_mismatch":
        audit["native_session_id"] = "wrong-thread"
    elif mutation in {"report_thread_mismatch", "metadata_thread_mismatch", "missing_session_field"}:
        name = "observation_report.json" if mutation == "report_thread_mismatch" else "runtime_metadata.json"
        record = json.loads((run / name).read_text())
        if mutation == "missing_session_field":
            del record["session_id"]
        else:
            record["thread_id"] = "wrong-thread"
        write_json(run / name, record)
    else:
        path = run / "codex_events.jsonl"
        lines = path.read_bytes().splitlines(keepends=True)
        if mutation == "official_missing":
            lines.pop(0)
            audit["new_session_outcome_observation"]["matches"][0]["native_reference"]["line"] = 1
        elif mutation == "official_multiple":
            # The existing observed raw line remains line two; duplicate
            # official identity is rejected even if both IDs are identical.
            lines.append(lines[0])
        else:
            event = json.loads(lines[0])
            event["thread_id"] = "wrong-thread"
            lines[0] = json.dumps(event).encode() + b"\n"
        path.write_bytes(b"".join(lines))
    refresh_observation(tmp_path, index, audit)
    with pytest.raises(demo.DemoError):
        verify(tmp_path, index)


def test_failed_gate_reported_separately_from_consistent_files(tmp_path):
    _, index = fixture_index(tmp_path)
    write_json(tmp_path / "G2.json", {"status": "FAIL", "fixture_type": "synthetic_record_only"})
    repin(tmp_path, index, "G2.json")
    result = verify(tmp_path, index)
    assert result["consistency"] == "PASS" and result["gate_verdicts"]["G2"] == "FAIL"
    assert result["all_declared_gates_pass"] is False


@pytest.mark.parametrize("mutation", ["save_exit", "restart_argv", "changed_state", "changed_paths", "missing_history", "missing_observed", "feedback_state"])
def test_resealed_persistence_failures_rejected(tmp_path, mutation):
    _, index = fixture_index(tmp_path)
    if mutation == "save_exit":
        filename = index["persistence"]["save_command"]["path"]
        value = json.loads((tmp_path / filename).read_text())
        value["exit_code"] = 1
    elif mutation == "restart_argv":
        filename = index["persistence"]["restart_command"]["path"]
        value = json.loads((tmp_path / filename).read_text())
        value["argv"] = ["docker", "compose", "status"]
    elif mutation == "feedback_state":
        filename = "feedback.json"
        value = json.loads((tmp_path / filename).read_text())
        value["final_graph"]["node_count"] += 1
    else:
        filename = index["persistence"]["after_snapshot"]["path"]
        value = json.loads((tmp_path / filename).read_text())
        if mutation == "changed_state":
            value["graph_state"]["node_count"] += 1
        elif mutation == "changed_paths":
            value["public_paths"]["observed"][0]["unapproved_change"] = True
        else:
            if mutation == "missing_history":
                value["public_paths"]["historical"].pop()
            else:
                value["public_paths"]["observed"] = []
            # Pin both before and after consistently to prove the structural
            # requirements independently reject erased evidence.
            before_name = index["persistence"]["before_snapshot"]["path"]
            write_json(tmp_path / before_name, value)
            repin(tmp_path, index, before_name)
    write_json(tmp_path / filename, value)
    repin(tmp_path, index, filename)
    with pytest.raises(demo.DemoError):
        verify(tmp_path, index)


def sdk_persistence_fixture(tmp_path):
    """Explicitly synthetic SDK-save/stop-up receipts; never run a probe."""
    _, index = fixture_index(tmp_path)
    probe_name = "g4_persistence_probe.py"
    (tmp_path / probe_name).write_text('"""synthetic_record_only; never executed"""\n')
    index["files"][probe_name] = sha256((tmp_path / probe_name).read_bytes()).hexdigest()
    index["persistence"]["save_probe"] = {"path": probe_name, "sha256": index["files"][probe_name]}
    stop_name = "g4-graceful-container-stop/command.json"
    index["persistence"]["stop_command"] = {"path": stop_name, "sha256": "0" * 64}
    for label, operation in (("before_snapshot", "save"), ("after_snapshot", "snapshot")):
        name = index["persistence"][label]["path"]
        snapshot = json.loads((tmp_path / name).read_text())
        snapshot.update({"operation": operation, "save_result": True if operation == "save" else None,
                         "persistence": {"aof_enabled": 0, "loading": 0, "rdb_last_bgsave_status": "ok"}})
        write_json(tmp_path / name, snapshot)
        repin(tmp_path, index, name)
    before_name = index["persistence"]["before_snapshot"]["path"]
    before = json.loads((tmp_path / before_name).read_text())
    output = json.dumps({"operation": "save", "graph_state": before["graph_state"],
                         "output_sha256": index["persistence"]["before_snapshot"]["sha256"]}).encode() + b"\n"
    commands = [
        ("save_command", ["scripts/aevora-python", str(tmp_path / probe_name), "save", str(tmp_path / before_name)],
         output, b"", 0),
        ("stop_command", ["docker", "compose", "-f", "aevora_core/compose.yaml", "stop", "experience-graph"],
         b"", b"Container synthetic Stopped\n", 2),
        ("restart_command", ["docker", "compose", "-f", "aevora_core/compose.yaml", "up", "-d", "--wait", "experience-graph"],
         b"", b"Container synthetic Started\nContainer synthetic Healthy\n", 4)]
    for label, argv, stdout, stderr, second in commands:
        name = index["persistence"][label]["path"]
        parent = Path(name).parent
        hashes = {}
        for channel, data in (("stdout", stdout), ("stderr", stderr)):
            log_name = (parent / (channel + ".log")).as_posix()
            target = tmp_path / log_name; target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(data)
            hashes[channel + "_sha256"] = sha256(data).hexdigest()
            index["files"][log_name] = sha256(data).hexdigest()
        write_json(tmp_path / name, {"fixture_type": "synthetic_record_only", "argv": argv, "exit_code": 0,
                    "cwd": str(demo.ROOT), "started_at": f"2026-10-11T08:00:{second:02d}+00:00",
                    "ended_at": f"2026-10-11T08:00:{second+1:02d}+00:00", **hashes})
        repin(tmp_path, index, name)
    return index


def test_pinned_sdk_save_and_same_service_stop_up_consistency_without_execution(tmp_path, monkeypatch):
    index = sdk_persistence_fixture(tmp_path)
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("No synthetic SDK or Docker execution"))
    result = verify(tmp_path, index)
    assert result["consistency"] == "PASS" and result["closure_result"] == "SYNTHETIC_CONSISTENCY_ONLY"
    assert result["persistence_method"] == "PINNED_SDK_SAVE_AND_SAME_SERVICE_STOP_UP"
    assert result["model_called"] is False and result["graph_contacted"] is False


@pytest.mark.parametrize("mutation", ["missing_stop", "missing_probe", "probe_pin", "probe_argv", "save_operation", "save_result", "aof_enabled", "save_status", "loading", "after_aof", "log_hash", "unindexed_log", "save_output", "stop_exit", "service_mismatch", "compose_mismatch", "cwd_mismatch", "save_after_stop", "stop_after_up", "naive_time", "up_not_healthy"])
def test_sdk_save_stop_up_requires_exact_trust_and_actual_ordered_receipts(tmp_path, mutation):
    index = sdk_persistence_fixture(tmp_path)
    if mutation in {"missing_stop", "missing_probe"}:
        del index["persistence"]["stop_command" if mutation == "missing_stop" else "save_probe"]
    elif mutation == "probe_pin":
        index["persistence"]["save_probe"]["sha256"] = "0" * 64
    elif mutation == "unindexed_log":
        del index["files"]["g4-graceful-container-stop/stderr.log"]
    else:
        if mutation in {"save_operation", "save_result", "aof_enabled", "save_status", "loading", "after_aof"}:
            label = "after_snapshot" if mutation == "after_aof" else "before_snapshot"
        elif mutation in {"stop_exit", "service_mismatch", "compose_mismatch", "cwd_mismatch", "stop_after_up", "naive_time"}:
            label = "stop_command"
        elif mutation == "up_not_healthy":
            label = "restart_command"
        else:
            label = "save_command"
        name = index["persistence"][label]["path"]
        value = json.loads((tmp_path / name).read_text())
        if mutation == "probe_argv":
            value["argv"][1] = str(tmp_path / "unapproved_probe.py")
        elif mutation == "save_operation":
            value["operation"] = "snapshot"
        elif mutation == "save_result":
            value["save_result"] = False
        elif mutation in {"aof_enabled", "after_aof"}:
            value["persistence"]["aof_enabled"] = 1
        elif mutation == "save_status":
            value["persistence"]["rdb_last_bgsave_status"] = "err"
        elif mutation == "loading":
            value["persistence"]["loading"] = 1
        elif mutation == "log_hash":
            value["stdout_sha256"] = "0" * 64
        elif mutation in {"save_output", "up_not_healthy"}:
            channel = "stdout" if mutation == "save_output" else "stderr"
            log_name = (Path(name).parent / (channel + ".log")).as_posix()
            data = b'{"operation":"save","output_sha256":"incorrect"}\n' if mutation == "save_output" else b"Container synthetic Started\n"
            (tmp_path / log_name).write_bytes(data)
            index["files"][log_name] = sha256(data).hexdigest()
            value[channel + "_sha256"] = sha256(data).hexdigest()
        elif mutation == "stop_exit":
            value["exit_code"] = 1
        elif mutation == "service_mismatch":
            value["argv"][-1] = "unrelated-service"
        elif mutation == "compose_mismatch":
            value["argv"][3] = "unrelated-compose.yaml"
        elif mutation == "cwd_mismatch":
            value["cwd"] = str(tmp_path)
        elif mutation == "save_after_stop":
            value["ended_at"] = "2026-10-11T08:00:03+00:00"
        elif mutation == "stop_after_up":
            value["ended_at"] = "2026-10-11T08:00:05+00:00"
        else:
            value["started_at"] = "2026-10-11T08:00:02"
        write_json(tmp_path / name, value)
        repin(tmp_path, index, name)
    with pytest.raises(demo.DemoError):
        verify(tmp_path, index)


@pytest.mark.parametrize("mutation", ["feedback_run", "feedback_verdict", "feedback_outcome", "observation_outcome", "raw_line_hash", "observed_path_hash", "native_session"])
def test_resealed_cross_run_or_semantic_conflicts_rejected(tmp_path, mutation):
    _, index = fixture_index(tmp_path)
    filename = "feedback.json" if mutation.startswith("feedback_") else "observation_audit.json"
    value = json.loads((tmp_path / filename).read_text())
    if mutation == "feedback_run":
        value["ingestion"]["run_id"] = OBSERVATION
    elif mutation == "feedback_verdict":
        value["ingestion"]["verdict"] = "FAIL"
    elif mutation == "feedback_outcome":
        value["ingestion"]["outcome_id"] = "orderflow:" + OBSERVATION
    elif mutation == "observation_outcome":
        value["new_session_outcome_observation"]["trusted_outcome_id"] = "orderflow:" + OBSERVATION
    elif mutation == "raw_line_hash":
        value["new_session_outcome_observation"]["matches"][0]["native_reference"]["sha256"] = "0" * 64
    elif mutation == "observed_path_hash":
        value["new_session_outcome_observation"]["matches"][0]["path_sha256"] = "0" * 64
    else:
        value["native_session_id"] = "wrong-session"
    write_json(tmp_path / filename, value)
    repin(tmp_path, index, filename)
    with pytest.raises(demo.DemoError):
        verify(tmp_path, index)


def test_index_pin_required_and_actual_artifacts_not_changed(tmp_path):
    _, index = fixture_index(tmp_path)
    write_json(tmp_path / "CLOSURE_INDEX.json", index)
    before = {p: sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(demo.DemoError):
        demo.verify_existing(tmp_path, "CLOSURE_INDEX.json", "0" * 64)
    assert before == {p: sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()}


def test_full_run_raw_tampering_rejected(tmp_path):
    _, index = fixture_index(tmp_path)
    (tmp_path / index["runs"]["observation"]["path"] / "codex_events.jsonl").write_text("tampered\n")
    with pytest.raises(ValueError):
        verify(tmp_path, index)


def test_index_duplicate_json_and_source_traversal_rejected(tmp_path):
    path = tmp_path / "CLOSURE_INDEX.json"
    path.write_text('{"schema_version":"one","schema_version":"two"}')
    with pytest.raises(ValueError):
        demo.verify_existing(tmp_path, path.name, sha256(path.read_bytes()).hexdigest())
    path.unlink()
    _, index = fixture_index(tmp_path)
    index["source_anchor"]["archive_path"] = "../outside"
    with pytest.raises(ValueError):
        verify(tmp_path, index)


def test_file_link_and_cross_archive_paths_refused(tmp_path):
    _, index = fixture_index(tmp_path)
    original = tmp_path / "G0.json"
    preserved = tmp_path / "preserved.json"
    original.rename(preserved)
    original.symlink_to(preserved)
    with pytest.raises(ValueError):
        verify(tmp_path, index)


def test_run_without_explicit_authorization_never_reads_gate_or_starts_process(tmp_path, monkeypatch):
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("No actual live subprocess allowed"))
    with pytest.raises(demo.DemoError, match="authorize-live"):
        demo.run_challenge(tmp_path, tmp_path, "0" * 64, "synthetic", False)


def test_run_bad_gate_pin_never_starts_process(tmp_path, monkeypatch):
    write_json(tmp_path / "LIVE_GATE.json", {"status": "PASS", "fixture_type": "synthetic_record_only"})
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("No actual live subprocess allowed"))
    with pytest.raises(demo.DemoError, match="SHA256"):
        demo.run_challenge(tmp_path, tmp_path, "0" * 64, "synthetic", True)


def admission_fixture(tmp_path):
    """Synthetic local authorization for record-only handoff tests."""
    checks = {}
    for number in range(5):
        name = f"synthetic-gate-{number}.json"
        write_json(tmp_path / name, {"status": "PASS", "fixture_type": "synthetic_record_only",
                                    "state": {"graph_name": "synthetic_record_only_namespace"}})
        checks[name] = sha256((tmp_path / name).read_bytes()).hexdigest()
    write_json(tmp_path / "SOURCE_TRUST_MANIFEST.json", {"fixture_type": "synthetic_record_only", "files": {}})
    relative = "scripts/aevora_live.py"
    gate = {"status": "PASS", "gate": "G3_NATIVE_ADMISSION", "checks": checks,
        "source_manifest_sha256": sha256((tmp_path / "SOURCE_TRUST_MANIFEST.json").read_bytes()).hexdigest(),
        "frozen_source_sha256": {relative: sha256((demo.ROOT / relative).read_bytes()).hexdigest()},
        "provider": "gateway", "model": "gpt-5.6-terra", "reasoning_effort": "max", "experience": "aevora",
        "completion_policy": "completion-aware", "agent_timeout": None, "request_budget": None,
        "parallel_trials": 1, "maximum_model_concurrency": 4}
    write_json(tmp_path / "LIVE_GATE.json", gate)
    return gate


def test_authorized_run_handoff_is_only_existing_collector_recorded(tmp_path, monkeypatch):
    admission_fixture(tmp_path)
    recorded = []

    def record_only(argv, **kwargs):
        recorded.append((argv, kwargs))
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(demo.subprocess, "run", record_only)
    assert demo.run_challenge(tmp_path, tmp_path, sha256((tmp_path / "LIVE_GATE.json").read_bytes()).hexdigest(), "synthetic_record_only", True) == 7
    assert len(recorded) == 1
    argv, options = recorded[0]
    assert argv == ["env", "ORDERFLOW_ENABLE_CODEX=1", "AEVORA_FALKORDB_GRAPH=synthetic_record_only_namespace", str(demo.ROOT / "scripts/aevora-python"),
        str(demo.ROOT / "scripts/aevora_live.py"), "run", str(tmp_path), "--trial", "synthetic_record_only"]
    assert "timeout" not in options and options["check"] is False
    assert not (tmp_path / "live").exists()


def inside_capabilities(monkeypatch):
    values = {"AEVORA_FALKORDB_PASSWORD_FILE": "/maintainer/aevora-db.password",
              "ORDERFLOW_GATEWAY_SECRET_PATH": "/maintainer/gateway.key", "ORDERFLOW_CODEX_BINARY": "/tools/codex"}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    # The actual trusted launcher intentionally does not preserve the outer
    # ORDERFLOW_ENABLE_CODEX flag after --clearenv.
    monkeypatch.delenv("ORDERFLOW_ENABLE_CODEX", raising=False)
    monkeypatch.setattr(demo.sys, "version_info", (3, 12, 0))
    monkeypatch.setattr(demo.sys, "executable", "/synthetic/python312")
    monkeypatch.setattr(demo, "regular_capability", lambda path, **kwargs: True)


def test_inside_ready_handoff_calls_existing_collector_directly_without_nested_wrapper(tmp_path, monkeypatch):
    admission_fixture(tmp_path)
    inside_capabilities(monkeypatch)
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", "unapproved_old_graph")
    inherited = dict(demo.os.environ)
    recorded = []
    monkeypatch.setattr(demo.subprocess, "run", lambda argv, **kwargs: recorded.append((argv, kwargs)) or SimpleNamespace(returncode=9))
    assert demo.run_challenge(tmp_path, tmp_path, sha256((tmp_path / "LIVE_GATE.json").read_bytes()).hexdigest(), "direct_record_only", True) == 9
    argv, options = recorded[0]
    assert argv == ["/synthetic/python312", str(demo.ROOT / "scripts/aevora_live.py"), "run", str(tmp_path), "--trial", "direct_record_only"]
    assert options["env"] == {**inherited, "AEVORA_FALKORDB_GRAPH": "synthetic_record_only_namespace"}
    assert options["cwd"] == demo.ROOT and options["check"] is False and "timeout" not in options
    assert str(demo.ROOT / "scripts/aevora-python") not in argv
    assert not (tmp_path / "live").exists()


@pytest.mark.parametrize("mutation", ["missing_codex", "missing_helper", "missing_gateway", "missing_database", "wrong_python", "wrong_binary_marker"])
def test_inside_missing_capabilities_rejects_without_nested_or_direct_process(tmp_path, monkeypatch, mutation):
    admission_fixture(tmp_path)
    inside_capabilities(monkeypatch)
    if mutation == "wrong_python":
        monkeypatch.setattr(demo.sys, "version_info", (3, 11, 0))
    elif mutation == "wrong_binary_marker":
        monkeypatch.setenv("ORDERFLOW_CODEX_BINARY", "/unapproved/codex")
    else:
        missing = {"missing_codex": "/tools/codex", "missing_helper": "/tools/codex-code-mode-host",
                   "missing_gateway": "/maintainer/gateway.key", "missing_database": "/maintainer/aevora-db.password"}[mutation]
        monkeypatch.setattr(demo, "regular_capability", lambda path, **kwargs: path != missing)
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("Missing capabilities must not start any process"))
    with pytest.raises(demo.DemoError):
        demo.run_challenge(tmp_path, tmp_path, sha256((tmp_path / "LIVE_GATE.json").read_bytes()).hexdigest(), "direct_record_only", True)


@pytest.mark.parametrize("mutation", ["no_authorization", "wrong_pin", "changed_freeze", "existing_trial"])
def test_inside_capabilities_cannot_bypass_existing_authorization_pin_freeze_or_unique_trial(tmp_path, monkeypatch, mutation):
    gate = admission_fixture(tmp_path)
    inside_capabilities(monkeypatch)
    if mutation == "changed_freeze":
        gate["frozen_source_sha256"]["scripts/aevora_live.py"] = "0" * 64
        write_json(tmp_path / "LIVE_GATE.json", gate)
    elif mutation == "existing_trial":
        (tmp_path / "live/direct_record_only").mkdir(parents=True)
    expected = "0" * 64 if mutation == "wrong_pin" else sha256((tmp_path / "LIVE_GATE.json").read_bytes()).hexdigest()
    monkeypatch.setattr(demo, "regular_capability", lambda *a, **k: pytest.fail("Earlier guards must reject before capability dispatch"))
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("Earlier guards must not start a process"))
    with pytest.raises(ValueError):
        demo.run_challenge(tmp_path, tmp_path, expected, "direct_record_only", mutation != "no_authorization")


def test_capability_metadata_requires_nonempty_regular_readable_executable_files_and_refuses_links(tmp_path):
    path = tmp_path / "synthetic_tool"
    path.write_text("synthetic_record_only")
    path.chmod(0o600)
    assert demo.regular_capability(path) is True
    assert demo.regular_capability(path, executable=True) is False
    path.chmod(0o700)
    assert demo.regular_capability(path, executable=True) is True
    link = tmp_path / "synthetic_link"; link.symlink_to(path)
    assert demo.regular_capability(link, executable=True) is False
    path.write_bytes(b"")
    assert demo.regular_capability(path) is False
    assert demo.regular_capability(tmp_path) is False
    assert demo.regular_capability(tmp_path / "missing") is False


@pytest.mark.parametrize("mutation", ["gate_failure", "silent_model_downgrade", "excess_concurrency", "source_changed"])
def test_authorized_flag_cannot_bypass_gate_or_source_check(tmp_path, monkeypatch, mutation):
    gate = admission_fixture(tmp_path)
    if mutation == "gate_failure":
        gate["status"] = "FAIL"
    elif mutation == "silent_model_downgrade":
        gate["reasoning_effort"] = "high"
    elif mutation == "excess_concurrency":
        gate["maximum_model_concurrency"] = 5
    else:
        gate["frozen_source_sha256"]["scripts/aevora_live.py"] = "0" * 64
    write_json(tmp_path / "LIVE_GATE.json", gate)
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: pytest.fail("Only record-only subprocess tests allowed"))
    with pytest.raises(ValueError):
        demo.run_challenge(tmp_path, tmp_path, sha256((tmp_path / "LIVE_GATE.json").read_bytes()).hexdigest(), "synthetic", True)


def test_cli_plan_and_stages_exit_zero_without_execution(tmp_path, capsys):
    for operation in ("plan", "stages"):
        assert demo.main([operation, "--archive", str(tmp_path / "new"), "--historical-archive", str(tmp_path / "history")]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["executed"] is False and result["closure_index_example"]["schema_version"] == "aevora-h1-closure-v1"
