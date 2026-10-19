#!/usr/bin/env python3
"""Safe staged Aevora H1 demo and offline closure consistency review.

plan/stages print existing commands without running them. verify-existing is
read-only and performs no model, graph or candidate execution. run starts only
the existing native D collector, after explicit live authorization and approved
gate pins. RDB SAVE/restart and the final observation are deliberate maintainer
stages, never automatic side effects of planning or verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.evidence_export import _read_regular
from benchmark.evidence_verify import load_json, safe_relative

SCHEMA = "aevora-h1-closure-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


class DemoError(ValueError):
    """Missing, unsafe or inconsistent local authority/evidence."""


def require(condition, message):
    if not condition:
        raise DemoError(message)


def checked_sha(value):
    require(isinstance(value, str) and HEX.fullmatch(value), "Invalid approved SHA256")
    return value


def read(root, relative, expected=None, *, maximum=64 * 1024**2):
    safe_relative(relative)
    root = Path(root).absolute()
    require(root.resolve() == root, "Archive root must have no linked components")
    try:
        data = _read_regular(root, relative, max_bytes=maximum)
    except OSError as error:
        raise DemoError("Evidence is unavailable or unsafe: " + relative) from error
    if expected is not None:
        require(sha256(data).hexdigest() == checked_sha(expected), "Pinned file SHA256 differs: " + relative)
    return data


def pinned_json(root, record, files):
    require(isinstance(record, dict), "Explicit pinned record required")
    name = safe_relative(record.get("path"))
    expected = checked_sha(record.get("sha256"))
    require(files.get(name) == expected, "Critical reference differs from closure file map")
    return load_json(read(root, name, expected))


def command_logs(root, record, reference, files):
    """Check actual archived output against both command and closure pins."""
    parent = PurePosixPath(safe_relative(reference.get("path"))).parent
    result = {}
    for channel in ("stdout", "stderr"):
        name = (parent / (channel + ".log")).as_posix()
        expected = checked_sha(record.get(channel + "_sha256"))
        require(files.get(name) == expected, "Command log is not pinned by the closure")
        result[channel] = read(root, name, expected, maximum=8 * 1024**2)
    return result


def command_interval(record):
    values = []
    for key in ("started_at", "ended_at"):
        raw = record.get(key)
        require(isinstance(raw, str) and len(raw) <= 128, "Actual command timestamp required")
        value = datetime.fromisoformat(raw)
        require(value.tzinfo is not None and value.utcoffset() is not None, "Command timestamp must include timezone")
        values.append(value)
    require(values[0] <= values[1], "Command timestamps are reversed")
    return values


def _inside(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise DemoError("Reference escapes authorized archive") from error
    safe_relative(relative)
    return relative


def gate_checks(authority_root, gate_root, gate, *, current_sources=False):
    require(gate.get("status") == "PASS" and gate.get("gate") == "G3_NATIVE_ADMISSION", "Native admission is not PASS")
    required = {"provider": "gateway", "model": "gpt-5.6-terra", "reasoning_effort": "max",
                "experience": "aevora", "completion_policy": "completion-aware", "agent_timeout": None,
                "request_budget": None, "parallel_trials": 1}
    require(all(gate.get(key) == value for key, value in required.items()), "Native profile differs from approved H1 profile")
    require(type(gate.get("maximum_model_concurrency")) is int and 1 <= gate["maximum_model_concurrency"] <= 4,
            "Model concurrency must be bounded to 1..4")
    checks = gate.get("checks")
    require(isinstance(checks, dict) and 5 <= len(checks) <= 64, "Complete admission evidence required")
    graph_names = set()
    for relative, expected in checks.items():
        require(isinstance(relative, str) and "\\" not in relative, "Invalid admission reference")
        # Existing gates intentionally use ../Gx.json inside one Full archive.
        # Normalize lexically, then enforce the explicit authority root and
        # descriptor-based no-link file reads; never use arbitrary host paths.
        path = Path(os.path.abspath(gate_root / relative))
        normalized = _inside(authority_root, path)
        value = load_json(read(authority_root, normalized, expected))
        verdict = value.get("status", value.get("mandatory_boundary_result"))
        require(verdict == "PASS" or ("exit_code" in value and value["exit_code"] == 0),
                "Admission evidence is not a passed gate/command")
        for field in ("state", "release_graph", "main_state"):
            state = value.get(field)
            if isinstance(state, dict) and isinstance(state.get("graph_name"), str):
                graph_names.add(state["graph_name"])
    read(gate_root, "SOURCE_TRUST_MANIFEST.json", gate.get("source_manifest_sha256"), maximum=32 * 1024**2)
    require(isinstance(gate.get("frozen_source_sha256"), dict) and bool(gate["frozen_source_sha256"]), "No frozen sources")
    if current_sources:
        from scripts.m11_calibration import verify_freeze
        for name in gate["frozen_source_sha256"]:
            safe_relative(name)
        verify_freeze(gate)
    require(len(graph_names) == 1, "Admission must pin one actual G1/G2 graph namespace")
    graph_name = next(iter(graph_names))
    require(re.fullmatch(r"[A-Za-z0-9_]{1,200}", graph_name), "Unsafe graph namespace")
    return graph_name


def closure_example():
    """Strict shape; placeholders are parameters, never invented evidence."""
    return {"schema_version": SCHEMA,
        "files": {**{f"G{i}_GATE.json": "<sha256>" for i in range(6)}, "release/SOURCE_TRUST_MANIFEST.json": "<sha256>",
                  "G4_FEEDBACK_RECEIPT.json": "<sha256>", "observation_audit/trace_audit.json": "<sha256>",
                  "g4-rdb-explicit-save/command.json": "<sha256>", "g4-container-rdb-restart/command.json": "<sha256>",
                  "G4_BEFORE_RESTART.json": "<sha256>", "G4_AFTER_RESTART.json": "<sha256>"},
        "source_anchor": {"archive_path": "release", "manifest_relative_path": "SOURCE_TRUST_MANIFEST.json",
                          "sha256": "<pre-live-approved-sha256>", "snapshot_relative_path": "frozen_source_snapshot"},
        "gates": {f"G{i}": {"path": f"G{i}_GATE.json", "sha256": "<sha256>", "verdict_field": "status"} for i in range(6)},
        "runs": {"challenge": {"run_id": "<D-run-uuid>", "path": "release/live/runs/<D-run-uuid>", "seal_sha256": "<sha256>"},
                 "observation": {"run_id": "<new-observation-uuid>", "path": "release/observation_session/runs/<new-observation-uuid>", "seal_sha256": "<sha256>"}},
        "feedback": {"path": "G4_FEEDBACK_RECEIPT.json", "sha256": "<sha256>", "outcome_id": "orderflow:<D-run-uuid>"},
        "persistence": {"save_command": {"path": "g4-rdb-explicit-save/command.json", "sha256": "<sha256>"},
                        "restart_command": {"path": "g4-container-rdb-restart/command.json", "sha256": "<sha256>"},
                        "before_snapshot": {"path": "G4_BEFORE_RESTART.json", "sha256": "<sha256>"},
                        "after_snapshot": {"path": "G4_AFTER_RESTART.json", "sha256": "<sha256>"}},
        "observation_trace_audit": {"path": "observation_audit/trace_audit.json", "sha256": "<sha256>",
                                    "trusted_outcome_id": "orderflow:<D-run-uuid>"},
        "qualification": "Local maintainer pins; not external attestation or causal improvement proof"}


def plan(archive, historical_archive, gate_files, regression):
    archive, history = Path(archive).absolute(), Path(historical_archive).absolute()
    gates = gate_files or ["G0_GATE.json", "G1_RELEASE_GATE.json", "G2_GATE.json", "G3_PRELIVE_GATE.json", "G3_FINAL_INTEGRITY.json"]
    require(all(safe_relative(name) for name in gates), "Gate paths must be archive-relative")
    safe_relative(regression)
    graph_name = "aevora_demo_" + sha256(str(archive).encode()).hexdigest()[:20]
    launch = ["env", "AEVORA_FALKORDB_GRAPH=" + graph_name, str(ROOT / "scripts/aevora-python")]
    stages = [
        {"stage": "historical_import", "argv": launch + [str(ROOT / "scripts/aevora_graph_gate.py"), "import", str(archive / "G1_IMPORT.json"), "--historical-archive", str(history)],
         "precondition": "Dedicated authenticated RDB-mode graph; G0 and historical pins approved; graph credentials stay host-only. Generate fresh G1/G2/G3 evidence for this namespace and have the maintainer publish the reviewed named Gates; do not reuse another namespace's PASS."},
        {"stage": "when_why", "argv": launch + [str(ROOT / "scripts/aevora_decision_gate.py"), str(archive / "G2_GATE.json")],
         "precondition": "Actual G1 paths/import pass; ablations use copies; do not run on an active challenge"},
        {"stage": "isolation", "argv": launch + [str(ROOT / "scripts/aevora_isolation_gate.py"), str(archive / "G3_ISOLATION_GATE.json")],
         "precondition": "Dedicated test environment; no active challenge; original regression independently recorded"},
        {"stage": "freeze", "argv": [str(ROOT / "scripts/python312"), str(ROOT / "scripts/aevora_live.py"), "freeze", str(archive)] +
            [word for name in gates for word in ("--gate-file", name)] + ["--regression", regression],
         "precondition": "All declared gate files really PASS and regression command exit 0; fresh snapshot/output paths"},
        {"stage": "native_D", "argv": ["env", "ORDERFLOW_ENABLE_CODEX=1", "AEVORA_FALKORDB_GRAPH=" + graph_name, str(ROOT / "scripts/aevora-python")] +
            [str(ROOT / "scripts/aevora_live.py"), "run", str(archive), "--trial", "native_challenge"],
         "precondition": "Approve LIVE_GATE and SOURCE_TRUST_MANIFEST SHA before model call; serial trial, completion-aware/max; manual cancel remains available"},
        {"stage": "independent_evaluation", "argv": None,
         "instruction": "The existing native collector runs the existing independent D Evaluator automatically. Preserve its real PASS/FAIL/ERROR/TIMEOUT and 28-case identity check; do not replace the Agent patch."},
        {"stage": "trusted_ingest", "argv_template": launch + [str(ROOT / "aevora_core/scripts/ingest_orderflow_outcome.py"),
            "--run-dir", str(archive / "live/runs/{challenge_run_id}"), "--run-id", "{challenge_run_id}",
            "--run-seal-sha256", "{approved_run_seal_sha256}", "--source-archive", str(archive),
            "--source-manifest-relative-path", "SOURCE_TRUST_MANIFEST.json", "--source-manifest-sha256", "{approved_pre_live_source_sha256}",
            "--output", str(archive / "G4_FEEDBACK_RECEIPT.json")],
         "required_parameters": ["challenge_run_id", "approved_run_seal_sha256", "approved_pre_live_source_sha256"],
         "precondition": "Stop Run writers, approve actual Run seal; complete independent engineering PASS or FAIL, actual same-Run Query exposure for experience feedback"},
        {"stage": "rdb_before_snapshot", "argv": launch + [str(ROOT / "scripts/aevora_graph_gate.py"), "snapshot", str(archive / "G4_RDB_BEFORE.json")],
         "precondition": "All Participant/graph writers stopped; exclusive maintenance window; no automatic restart"},
        {"stage": "rdb_save", "manual_only": True, "argv": ["docker", "compose", "-f", str(ROOT / "aevora_core/compose.yaml"), "exec", "-T", "experience-graph", "sh", "-c",
            'REDISCLI_AUTH="$(cat /run/secrets/aevora_db_password)" redis-cli -e SAVE'],
         "precondition": "Record real command exit; do not log password or change to unvalidated AOF mode"},
        {"stage": "rdb_restart", "manual_only": True, "argv": ["docker", "compose", "-f", str(ROOT / "aevora_core/compose.yaml"), "restart", "experience-graph"],
         "precondition": "Exclusive explicit operator approval after successful SAVE; service health must recover"},
        {"stage": "rdb_after_snapshot", "argv": launch + [str(ROOT / "scripts/aevora_graph_gate.py"), "snapshot", str(archive / "G4_RDB_AFTER.json")],
         "precondition": "Compare exact state and actual multi-hop paths with before; publish actual command/gate receipts"},
        {"stage": "fresh_read_only_observation", "argv": ["env", "ORDERFLOW_ENABLE_CODEX=1", "AEVORA_FALKORDB_GRAPH=" + graph_name, str(ROOT / "scripts/aevora-python"), str(ROOT / "scripts/aevora_new_session_probe.py"), str(archive)],
         "precondition": "Actual ingestion + RDB restart verification passed; new Session, unchanged source; retain expected NO_PATCH, no benchmark score"},
        {"stage": "trace_audit", "argv_template": launch + [str(ROOT / "scripts/aevora_trace_audit.py"), str(archive / "observation_session/runs/{observation_run_id}"),
            str(archive / "observation_audit"), "--expected-seal-sha256", "{approved_observation_seal_sha256}", "--trusted-outcome-id", "orderflow:{challenge_run_id}"],
         "required_parameters": ["observation_run_id", "approved_observation_seal_sha256", "challenge_run_id"]},
    ]
    return {"schema_version": "aevora.staged_demo/1.0", "status": "PLAN_ONLY", "executed": False,
            "archive": str(archive), "dedicated_graph_namespace": graph_name, "stages": stages, "closure_index_example": closure_example(),
            "limits": "Reuse existing native scheduling/evaluation. No automatic graph restart, credential provisioning, scientific cohort or causal-benefit claim."}


def verify_existing(root, index_reference, index_sha256):
    root = Path(root).absolute()
    value = load_json(read(root, index_reference, index_sha256, maximum=8 * 1024**2))
    require(isinstance(value, dict) and value.get("schema_version") == SCHEMA, "Unsupported closure index schema")
    files = value.get("files")
    require(isinstance(files, dict) and 1 <= len(files) <= 10000, "Bounded explicit closure file map required")
    for name, expected in files.items():
        read(root, name, expected)
    gates = value.get("gates")
    require(isinstance(gates, dict) and set(gates) == {f"G{i}" for i in range(6)}, "Complete explicit G0–G5 records required")
    verdicts = {}
    for label, record in gates.items():
        gate = pinned_json(root, record, files)
        field = record.get("verdict_field", "status")
        require(field in {"status", "mandatory_boundary_result"}, "Unsupported explicit gate verdict field")
        verdicts[label] = gate.get(field, "UNAVAILABLE")
    source = value.get("source_anchor")
    require(isinstance(source, dict), "Frozen source anchor required")
    source_archive_path = source.get("archive_path")
    require(isinstance(source_archive_path, str), "Explicit source archive path required")
    source_root = root if source_archive_path == "." else root / safe_relative(source_archive_path)
    source_manifest = safe_relative(source.get("manifest_relative_path"))
    source_ref = source_manifest if source_archive_path == "." else (PurePosixPath(source_archive_path) / source_manifest).as_posix()
    require(files.get(source_ref) == source.get("sha256"), "Source anchor differs from closure map")
    source_map = load_json(read(source_root, source_manifest, source["sha256"], maximum=32 * 1024**2))
    source_files = source_map.get("files", source_map.get("ordinary_files_sha256"))
    require(isinstance(source_files, dict) and 1 <= len(source_files) <= 10000, "Frozen source files absent")
    for name, expected in source_files.items():
        read(source_root, name, expected)
    runs = value.get("runs")
    require(isinstance(runs, dict) and set(runs) == {"challenge", "observation"}, "Two explicit Run identities required")
    from scripts.aevora_trace_audit import verify_run_seal
    seals, metadata = {}, {}
    for label, record in runs.items():
        run_id = record.get("run_id")
        require(isinstance(run_id, str) and UUID.fullmatch(run_id), "Invalid exact Run UUID")
        run_ref = safe_relative(record.get("path"))
        require(PurePosixPath(run_ref).name == run_id, "Run path/identity differ")
        seals[label] = verify_run_seal(root / run_ref, checked_sha(record.get("seal_sha256")))
        metadata[label] = load_json(read(root / run_ref, "runtime_metadata.json", seals[label]["files"].get("runtime_metadata.json")))
    challenge, observation = runs["challenge"], runs["observation"]
    require(challenge["run_id"] != observation["run_id"], "Observation must be a different Run")
    from aevora.orderflow_outcome_bridge import TrustAnchor, verify_outcome
    anchor = TrustAnchor(root / challenge["path"], challenge["seal_sha256"], {"evaluation_report.json": challenge["run_id"]},
        profile="current_live", manifest_relative_path="run_evidence_manifest.json", source_archive_root=source_root,
        source_manifest_sha256=source["sha256"], source_manifest_relative_path=source_manifest,
        source_snapshot_relative_path=source.get("snapshot_relative_path", "frozen_source_snapshot"))
    outcome = verify_outcome(anchor, "evaluation_report.json")
    synthetic = value.get("synthetic_record_only_fixture") is True
    require(outcome.get("episode_id") == "D" and (synthetic or outcome.get("test_count") == 28),
            "H1 demo requires independent D-v01's complete 28-case evaluation")
    feedback_record = value.get("feedback")
    feedback = pinned_json(root, feedback_record, files)
    ingested = feedback.get("ingestion", {})
    require(feedback_record.get("outcome_id") == outcome["id"] == ingested.get("outcome_id"), "Feedback Outcome differs from challenge")
    require(feedback.get("status") == "INGESTED" and feedback.get("exit_code") == 0 and feedback.get("idempotent") is True,
            "Feedback is not a completed identical ingestion")
    require(feedback.get("run_id") == outcome["run_id"] == ingested.get("run_id")
            and ingested.get("verdict") == outcome["verdict"], "Feedback verdict/Run differs from independently verified evidence")
    require(feedback.get("run_seal_sha256") == challenge["seal_sha256"]
            and feedback.get("source_manifest_sha256") == source["sha256"], "Feedback trust pins differ")
    require(ingested.get("feedback_status") == "outcome_observed_no_attribution" and bool(ingested.get("receipts"))
            and feedback.get("attribution") == "UNKNOWN" and feedback.get("adoption") == "UNVERIFIED", "No real observed feedback chain")
    persistence = value.get("persistence")
    required_persistence = {"save_command", "restart_command", "before_snapshot", "after_snapshot"}
    require(isinstance(persistence, dict) and set(persistence) in
            (required_persistence, required_persistence | {"save_probe", "stop_command"}),
            "Exact archived SAVE/restart and snapshot references required")
    save = pinned_json(root, persistence["save_command"], files)
    restart = pinned_json(root, persistence["restart_command"], files)
    require(type(save.get("exit_code")) is int and save["exit_code"] == 0
            and type(restart.get("exit_code")) is int and restart["exit_code"] == 0,
            "Archived SAVE/restart command did not succeed")
    before = pinned_json(root, persistence["before_snapshot"], files)
    after = pinned_json(root, persistence["after_snapshot"], files)
    if "save_probe" in persistence:
        probe = persistence["save_probe"]
        require(isinstance(probe, dict), "Explicit approved SAVE probe required")
        probe_ref, probe_sha = safe_relative(probe.get("path")), checked_sha(probe.get("sha256"))
        require(probe_ref.endswith(".py") and files.get(probe_ref) == probe_sha, "SAVE probe differs from approved closure pin")
        read(root, probe_ref, probe_sha, maximum=1024**2)
        # This is a locally approved maintainer probe, never candidate code.
        # The source pin, exact invocation, output hash and real RDB result
        # must agree; arbitrary lowercase 'save' arguments are not accepted.
        launchers = {"scripts/aevora-python", str(ROOT / "scripts/aevora-python")}
        require(isinstance(save.get("argv"), list) and len(save["argv"]) == 4 and save["argv"][0] in launchers
                and save["argv"][1:] == [str(root / probe_ref), "save", str(root / persistence["before_snapshot"]["path"])],
                "SDK SAVE must invoke exactly the approved probe and snapshot")
        for snapshot, operation in ((before, "save"), (after, "snapshot")):
            state = snapshot.get("persistence", {})
            require(snapshot.get("operation") == operation and isinstance(state, dict)
                    and type(state.get("aof_enabled")) is int and state["aof_enabled"] == 0
                    and type(state.get("loading")) is int and state["loading"] == 0
                    and state.get("rdb_last_bgsave_status") == "ok", "SDK persistence is not a completed RDB-mode operation")
        require(before.get("save_result") is True, "SDK SAVE did not report an actual successful save")
        stop = pinned_json(root, persistence["stop_command"], files)
        require(type(stop.get("exit_code")) is int and stop["exit_code"] == 0, "Container stop did not succeed")
        stop_argv, up_argv = stop.get("argv"), restart.get("argv")
        compose = {"aevora_core/compose.yaml", str(ROOT / "aevora_core/compose.yaml")}
        require(isinstance(stop_argv, list) and isinstance(up_argv, list) and len(stop_argv) == 6 and len(up_argv) == 8
                and stop_argv[:3] == ["docker", "compose", "-f"] and stop_argv[3] in compose
                and stop_argv[4:] == ["stop", "experience-graph"]
                and up_argv[:4] == stop_argv[:4] and up_argv[4:] == ["up", "-d", "--wait", "experience-graph"],
                "Restart must be exact same-service Compose stop followed by healthy up")
        require(save.get("cwd") == stop.get("cwd") == restart.get("cwd") == str(ROOT), "Persistence commands have different trusted working directories")
        save_start, save_end = command_interval(save)
        stop_start, stop_end = command_interval(stop)
        up_start, up_end = command_interval(restart)
        require(save_end <= stop_start and stop_end <= up_start, "Persistence command ordering is not SAVE then stop then up")
        save_logs = command_logs(root, save, persistence["save_command"], files)
        stop_logs = command_logs(root, stop, persistence["stop_command"], files)
        up_logs = command_logs(root, restart, persistence["restart_command"], files)
        saved_output = load_json(save_logs["stdout"])
        require(isinstance(saved_output, dict) and saved_output.get("operation") == "save"
                and saved_output.get("graph_state") == before.get("graph_state")
                and saved_output.get("output_sha256") == persistence["before_snapshot"]["sha256"],
                "SAVE command output differs from the actual pinned snapshot")
        require(re.search(rb"\bStopped\b", stop_logs["stderr"]) is not None
                and re.search(rb"\bStarted\b", up_logs["stderr"]) is not None
                and re.search(rb"\bHealthy\b", up_logs["stderr"]) is not None,
                "Container output does not confirm stop/start/health")
        persistence_method = "PINNED_SDK_SAVE_AND_SAME_SERVICE_STOP_UP"
    else:
        require(isinstance(save.get("argv"), list) and any("SAVE" in str(word) for word in save["argv"])
                and isinstance(restart.get("argv"), list) and "restart" in restart["argv"],
                "Persistence receipts do not record SAVE and restart commands")
        persistence_method = "ARCHIVED_DIRECT_SAVE_AND_RESTART"
    require(isinstance(before.get("graph_state"), dict) and before["graph_state"] == after.get("graph_state")
            and before["graph_state"] == feedback.get("final_graph"),
            "Persistence graph state differs from the final ingested state")
    require(isinstance(before.get("public_paths"), (dict, list)) and bool(before["public_paths"])
            and before["public_paths"] == after.get("public_paths"), "Restart did not preserve exact public evidence paths")
    pending = [before["public_paths"]]
    historical_ids, observed_paths = set(), []
    visited = 0
    while pending:
        item = pending.pop()
        visited += 1
        require(visited <= 100000, "Persistence public path shape exceeds budget")
        if isinstance(item, dict):
            if isinstance(item.get("id"), str) and item["id"].startswith("orderflow:") and item.get("verdict") in {"PASS", "FAIL"}:
                historical_ids.add(item["id"])
            if item.get("relation") == "OBSERVED_OUTCOME" and item.get("records", {}).get("VerifiedOutcome", {}).get("id") == outcome["id"]:
                observed_paths.append(item)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    from aevora.orderflow_outcome_bridge import M1_SEED_RUNS
    require({"orderflow:" + run for run in M1_SEED_RUNS.values()} <= historical_ids,
            "Historical support/counterexample Outcome evidence missing after persistence")
    require(bool(observed_paths), "Persisted graph has no exact new observed Outcome path")
    audit_record = value.get("observation_trace_audit")
    audit = pinned_json(root, audit_record, files)
    seen = audit.get("new_session_outcome_observation", {})
    require(audit.get("run_id") == observation["run_id"] and audit.get("source_seal", {}).get("seal_sha256") == observation["seal_sha256"],
            "Observation audit belongs to another Run/seal")
    require(audit_record.get("trusted_outcome_id") == outcome["id"] == seen.get("trusted_outcome_id"), "Observation points to another Outcome")
    require(seen.get("status") == "OBSERVED_IN_HOST_AND_TYPED_NATIVE_OUTPUT" and bool(seen.get("matches")),
            "Updated feedback not established in typed native output")
    require(isinstance(seen["matches"], list) and len(seen["matches"]) <= 1000, "Bounded observation joins required")
    raw_lines = {}
    for match in seen["matches"]:
        actual = match.get("actual_path", {})
        require(actual.get("relation") == "OBSERVED_OUTCOME"
                and actual.get("records", {}).get("VerifiedOutcome", {}).get("id") == outcome["id"], "Observed path is unrelated")
        canonical = json.dumps(actual, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        require(match.get("path_sha256") == sha256(canonical).hexdigest(), "Observed path identity differs")
        for channel in ("host_reference", "native_reference"):
            reference = match.get(channel)
            require(isinstance(reference, dict), "Actual host/native raw reference required")
            path = Path(reference.get("path", ""))
            run_root = root / observation["path"]
            relative = _inside(run_root, path if path.is_absolute() else run_root / path)
            require(relative in seals["observation"]["files"], "Observation reference is not in the sealed Run")
            if relative not in raw_lines:
                require(len(raw_lines) < 64, "Observation raw-file budget exceeded")
                raw_lines[relative] = read(run_root, relative, seals["observation"]["files"][relative]).splitlines(keepends=True)
            number = reference.get("line")
            require(type(number) is int and 1 <= number <= len(raw_lines[relative]), "Invalid raw line reference")
            require(sha256(raw_lines[relative][number - 1]).hexdigest() == reference.get("sha256"),
                    "Observation raw line hash differs")
    require(audit.get("native_integrity", {}).get("status") == "COMPLETE", "Native observation evidence incomplete")
    observation_report = load_json(read(root / observation["path"], "observation_report.json",
        seals["observation"]["files"].get("observation_report.json")))
    require(observation_report.get("run_id") == observation["run_id"]
            and observation_report.get("evaluation_result") == "NOT_EXECUTED"
            and observation_report.get("submission") is None
            and observation_report.get("source_unchanged") is True
            and observation_report.get("source_before_sha256") == observation_report.get("source_after_sha256")
            and HEX.fullmatch(str(observation_report.get("source_after_sha256", "")))
            and observation_report.get("session_observation_status") == "COMPLETE", "Read-only observation contract is not complete")
    session_id = metadata["observation"].get("session_id")
    native_id = audit.get("native_session_id")
    if session_id == "UNAVAILABLE":
        # NO_PATCH is an expected result for this read-only observer, so the
        # repair Adapter may not supply a Session ID. Retain that unavailable
        # field; accept a thread identity only from the separately sealed
        # official event stream and complete native archive review.
        require(isinstance(native_id, str) and native_id not in {"", "UNAVAILABLE", "UNKNOWN"}
                and native_id == metadata["observation"].get("thread_id") == observation_report.get("thread_id"),
                "Unavailable Session requires exact audited Runtime/report thread identity")
        official = read(root / observation["path"], "codex_events.jsonl", seals["observation"]["files"].get("codex_events.jsonl"))
        lines = official.splitlines()
        require(len(lines) <= 100000, "Official event identity budget exceeded")
        threads = []
        for line in lines:
            if not line.strip():
                continue
            event = load_json(line)
            require(isinstance(event, dict), "Official event must be a JSON object")
            if event.get("type") == "thread.started":
                threads.append(event.get("thread_id"))
        require(threads == [native_id], "Unique sealed official thread.started identity required")
        identity_source = "sealed_official_thread.started"
    else:
        require(isinstance(session_id, str) and session_id not in {"", "UNKNOWN"} and native_id == session_id,
                "Observation native session differs from Runtime identity")
        identity_source = "runtime_session_id_and_complete_native_audit"
    ids = [metadata[key].get("thread_id") for key in ("challenge", "observation")]
    fresh = all(isinstance(identifier, str) and identifier not in {"", "UNAVAILABLE", "UNKNOWN"} for identifier in ids) and ids[0] != ids[1]
    gate_pass = all(verdict == "PASS" for verdict in verdicts.values())
    return {"schema_version": "aevora.demo_review/1.0", "consistency": "PASS", "gate_verdicts": verdicts,
            "closure_result": "SYNTHETIC_CONSISTENCY_ONLY" if synthetic else "TASK_FAILED" if outcome["verdict"] == "FAIL" else "PASS" if gate_pass and fresh else "UNVERIFIED_OR_FAILED_GATE",
            "all_declared_gates_pass": gate_pass,
            "episode_d_task_outcome": outcome["verdict"], "challenge_run_id": challenge["run_id"], "observation_run_id": observation["run_id"],
            "session_ids_distinct": fresh, "trusted_outcome_id": outcome["id"], "checked_index_files": len(files),
            "observation_session_id": session_id, "observation_identity_source": identity_source,
            "checked_source_files": len(source_files), "run_seals": {key:{k:v for k,v in seal.items() if k != "files"} for key,seal in seals.items()},
            "persistence": "ARCHIVED_SAVE_RESTART_EXACT_STATE_AND_PUBLIC_PATH_MATCH",
            "persistence_method": persistence_method,
            "model_called": False, "graph_contacted": False, "candidate_executed": False, "source_modified": False,
            "attribution": "UNKNOWN", "external_origin_attestation": "UNVERIFIED"}


def run_challenge(archive, authority_root, gate_sha256, trial, authorize_live):
    require(authorize_live, "Explicit --authorize-live is required; plan never grants authorization")
    archive, authority_root = Path(archive).absolute(), Path(authority_root).absolute()
    gate = load_json(read(archive, "LIVE_GATE.json", gate_sha256))
    graph_name = gate_checks(authority_root, archive, gate, current_sources=True)
    require(isinstance(trial, str) and trial.isidentifier() and len(trial) <= 64, "Bounded unique trial label required")
    require(not (archive / "live" / trial).exists(), "Trial output already exists; no session reuse")
    # The trusted wrapper clears the caller's environment, then exposes only
    # fixed maintainer credential/tool mounts. In particular the outer
    # ORDERFLOW_ENABLE_CODEX flag is not retained. An inside marker with
    # missing tools must fail closed; nesting its /bin/sh launcher is invalid.
    mounts = {"AEVORA_FALKORDB_PASSWORD_FILE": "/maintainer/aevora-db.password",
              "ORDERFLOW_GATEWAY_SECRET_PATH": "/maintainer/gateway.key",
              "ORDERFLOW_CODEX_BINARY": "/tools/codex"}
    inside = any(os.environ.get(key) == path for key, path in mounts.items())
    options = {"cwd": ROOT, "check": False}
    if inside:
        require(sys.version_info[:2] == (3, 12), "Trusted collector requires Python 3.12")
        require(all(os.environ.get(key) == path for key, path in mounts.items()),
                "Trusted launcher lacks model/database capability mounts; use ORDERFLOW_ENABLE_CODEX=1 on the host")
        require(all(regular_capability(path) for path in ("/maintainer/aevora-db.password", "/maintainer/gateway.key"))
                and all(regular_capability(path, executable=True) for path in ("/tools/codex", "/tools/codex-code-mode-host")),
                "Trusted launcher model/database files or executable Codex helpers are unavailable")
        command = [sys.executable, str(ROOT / "scripts/aevora_live.py"), "run", str(archive), "--trial", trial]
        options["env"] = {**os.environ, "AEVORA_FALKORDB_GRAPH": graph_name}
    else:
        command = ["env", "ORDERFLOW_ENABLE_CODEX=1", "AEVORA_FALKORDB_GRAPH=" + graph_name, str(ROOT / "scripts/aevora-python"),
                   str(ROOT / "scripts/aevora_live.py"), "run", str(archive), "--trial", trial]
    # The existing collector owns exit receipts, cancellation and completeness.
    # No new wall timeout or native Agent orchestration is added here.
    return subprocess.run(command, **options).returncode


def regular_capability(path, *, executable=False):
    """Inspect mount metadata/access only; never read or archive credentials."""
    try:
        info = Path(path).lstat()
    except OSError:
        return False
    access = os.R_OK | (os.X_OK if executable else 0)
    return stat.S_ISREG(info.st_mode) and info.st_size > 0 and os.access(path, access)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("plan", "stages"):
        p = sub.add_parser(name, help="Print exact existing argv and deferred trust-pin parameters; execute nothing")
        p.add_argument("--archive", type=Path, required=True)
        p.add_argument("--historical-archive", type=Path, required=True)
        p.add_argument("--gate-file", action="append")
        p.add_argument("--regression", default="regression/command.json")
    p = sub.add_parser("verify-existing", help="Read-only full seals, source pins and cross-Run closure check")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--index-reference", default="CLOSURE_INDEX.json")
    p.add_argument("--index-sha256", required=True)
    p = sub.add_parser("run", help="Explicitly authorized existing D collector only; never restart the graph")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--authority-root", type=Path, required=True)
    p.add_argument("--gate-sha256", required=True)
    p.add_argument("--trial", required=True)
    p.add_argument("--authorize-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation in {"plan", "stages"}:
            result = plan(args.archive, args.historical_archive, args.gate_file, args.regression)
        elif args.operation == "verify-existing":
            result = verify_existing(args.archive, args.index_reference, args.index_sha256)
        else:
            return run_challenge(args.archive, args.authority_root, args.gate_sha256, args.trial, args.authorize_live)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        print(json.dumps({"consistency": "FAIL", "error_type": type(error).__name__, "error": str(error),
                          "model_called": False, "source_modified": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
