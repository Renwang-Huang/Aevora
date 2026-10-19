#!/usr/bin/env python3
"""H2-G0 isolated RDB failure injection; all new commands and failures are retained.

The host controller uses Docker. Trusted Python operations use the established
Aevora launcher once. No Participant, model request or original volume write.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62"
IMAGE_DIGEST = IMAGE.split("@", 1)[1]
H1 = ROOT / "aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288"
RUN = "5089297e-39e7-4bd5-8b87-cbc7e21de022"
SOURCE_VOLUME = "aevora-h1_aevora-experience-data"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def trusted_operation(args):
    from aevora.graph_repository import GraphRepository
    from aevora.checkpoint import capture_graph
    from aevora.models import digest
    repository = GraphRepository.from_environment()
    try:
        if args.operation == "seed":
            from aevora.historical_import import import_verified_history
            repository.initialize()
            result = import_verified_history(repository, args.historical_archive)
            snapshot = capture_graph(repository)
            assert len(snapshot["public_paths"]) == 2
            assert all(len(paths["evidence"]) == 2 for paths in snapshot["public_paths"].values())
            result.update({"snapshot": snapshot, "kind": "CURRENT_REVERIFICATION_OF_HISTORICAL_CONTROLLED_CHAINS"})
        elif args.operation == "tail-feedback":
            from aevora.feedback import ingest_outcome
            from aevora.orderflow_outcome_bridge import TrustAnchor, verify_outcome
            run_dir = H1 / "release_admission_v2/live/runs" / RUN
            original_receipt = json.loads((H1 / "G4_TRUSTED_INGEST_RECEIPT.json").read_text())
            anchor = TrustAnchor(run_dir, original_receipt["run_seal_sha256"], {"evaluation_report.json": RUN},
                profile="current_live", manifest_relative_path="run_evidence_manifest.json",
                source_archive_root=H1 / "release_admission_v2",
                source_manifest_sha256=original_receipt["source_manifest_sha256"],
                source_manifest_relative_path="SOURCE_TRUST_MANIFEST.json",
                source_snapshot_relative_path="frozen_source_snapshot")
            verified = verify_outcome(anchor, "evaluation_report.json")
            raw_path = run_dir / "aevora_mcp_events.jsonl"
            pins = {}
            for line in raw_path.read_text().splitlines():
                event = json.loads(line)
                if event.get("category") != "JSONRPC":
                    continue
                payload = json.loads(event["raw_json"])
                result = payload.get("result", {}).get("structuredContent", {})
                if result.get("query_id") and result.get("query_record_sha256"):
                    pins[("Query", result["query_id"])] = result["query_record_sha256"]
                if result.get("decision_id") and result.get("payload_sha256"):
                    pins[("Decision", result["decision_id"])] = result["payload_sha256"]
            assert len(pins) == 4, "Actual sealed query/decision result set differs"
            previous = os.environ["AEVORA_FALKORDB_PORT"], os.environ["AEVORA_FALKORDB_GRAPH"]
            os.environ["AEVORA_FALKORDB_PORT"] = "16379"
            os.environ["AEVORA_FALKORDB_GRAPH"] = "aevora_h1_release1"
            try:
                origin = GraphRepository.from_environment()
            finally:
                os.environ["AEVORA_FALKORDB_PORT"], os.environ["AEVORA_FALKORDB_GRAPH"] = previous
            copied_nodes, copied_edges = [], []
            try:
                for (label, identifier), pin in sorted(pins.items()):
                    value = origin.get_node(label, identifier)
                    assert value is not None and value.get("run_id") == RUN and digest(value) == pin
                    repository.put_node(label, value)
                    copied_nodes.append({"label": label, "id": identifier, "payload_sha256": pin,
                                         "origin": "SEALED_OFFICIAL_MCP_RESULT_JOINED_TO_READ_ONLY_H1_GRAPH"})
                source_ids = [identifier for _, identifier in pins]
                rows = origin.query("MATCH (s)-[r]->(t) WHERE s.id IN $ids "
                    "AND type(r) IN $relations RETURN labels(s),s.id,type(r),r.payload_json,labels(t),t.id "
                    "ORDER BY s.id,type(r),t.id", {"ids": source_ids,
                    "relations": ["DERIVED_FROM", "CONSIDERED", "RESPONDS_TO", "DECIDED"]})
                for source_labels, source_id, relation, raw, target_labels, target_id in rows:
                    source_label, target_label = source_labels[0], target_labels[0]
                    if target_label == "Context":
                        value = origin.get_node(target_label, target_id)
                        repository.put_node(target_label, value)
                    elif target_label in {"Query", "Decision"}:
                        assert target_id in source_ids
                    elif target_label == "Experience":
                        assert repository.get_node(target_label, target_id) is not None
                    else:
                        raise AssertionError("Unexpected historical exposure endpoint")
                    receipt = repository.put_edge(relation, source_label, source_id, target_label, target_id,
                                                  json.loads(raw))
                    copied_edges.append({"relation": relation, "source": source_id, "target": target_id, **receipt})
            finally:
                origin.close()
            first = ingest_outcome(repository, anchor, "evaluation_report.json")
            state = repository.state_fingerprint()
            second = ingest_outcome(repository, anchor, "evaluation_report.json")
            assert first == second and state == repository.state_fingerprint()
            assert first["feedback_status"] == "outcome_observed_no_attribution"
            result = {"status": "TRUSTED_HISTORICAL_FEEDBACK_REPLAYED", "kind": "CONTROLLED_HISTORICAL_REPLAY; NOT_NEW_AGENT_RUN",
                "original_run_id": RUN, "sealed_mcp_sha256": sha(raw_path), "run_seal_sha256": anchor.manifest_sha256,
                "source_manifest_sha256": original_receipt["source_manifest_sha256"],
                "copied_actual_exposures": copied_nodes, "copied_actual_relations": copied_edges,
                "independent_outcome_verdict": verified["verdict"], "feedback": first,
                "idempotent": True, "snapshot": capture_graph(repository), "attribution": "UNKNOWN"}
        else:
            from aevora.experience_resolver import ExperienceResolver
            snapshot = capture_graph(repository)
            actual = ExperienceResolver(repository).resolve({"concurrency_scope": "independent_processes",
                "shared_state_kind": "sqlite_file", "synchronization_scope": "per_process",
                "transaction_guarantees": "sqlite_atomic_write_transactions"})
            assert capture_graph(repository) == snapshot
            result = {"status": "NEW_CLIENT_QUERY_EXECUTED", "scope": "NEW_SDK_CONNECTION; NOT_CODEX_SESSION",
                      "snapshot": snapshot, "actual_resolver_output": actual}
        write(args.output, result)
        print(json.dumps({"status": result["status"], "output_sha256": sha(args.output)}))
        return 0
    finally:
        repository.close()


def run_recovery(args):
    sys.path.insert(0, str(ROOT))
    from scripts.aevora_h1_audit import record
    archive = args.archive.absolute()
    assert args.trial_label and re.fullmatch(r"[A-Za-z0-9_-]+", args.trial_label)
    private = archive / args.trial_label
    private.mkdir(mode=0o700)
    records = private / "commands"
    records.mkdir(mode=0o700)
    backups = private / "backups"
    backups.mkdir(mode=0o700)
    restores = private / "restore_staging"
    restores.mkdir(mode=0o700)
    project = "aevora-h2-recovery-" + archive.name.split("-")[-1][:8] + "-" + uuid.uuid4().hex[:6]
    graph = "aevora_h2_recovery_" + project.rsplit("-", 1)[1]
    compose = private / "compose.json"
    services = {}
    for index, service in enumerate(("primary", "restore-one", "restore-two")):
        services[service] = {"image": IMAGE, "container_name": project + "-" + service,
            "entrypoint": ["redis-server"], "command": ["--loadmodule", "/var/lib/falkordb/bin/falkordb.so",
                "--include", "/run/secrets/redis.conf", "--appendonly", "no", "--save", "", "--dir", "/data"],
            "ports": [f"127.0.0.1:{17680+index}:6379"], "volumes": [service + ":/data"],
            "secrets": ["redis.conf", "db.password"], "restart": "no", "mem_limit": "1g", "cpus": 2, "pids_limit": 256,
            "healthcheck": {"test": ["CMD-SHELL", 'test "$$(REDISCLI_AUTH="$$(cat /run/secrets/db.password)" redis-cli -e ping)" = PONG'],
                            "interval": "2s", "timeout": "3s", "retries": 20}}
    config = {"name": project, "services": services, "volumes": {key: {} for key in services},
              "secrets": {"redis.conf": {"file": os.environ["AEVORA_REDIS_CONFIG_FILE"]},
                          "db.password": {"file": os.environ["AEVORA_FALKORDB_PASSWORD_FILE"]}}}
    write(compose, config)
    command = ["docker", "compose", "-p", project, "-f", str(compose)]
    results = []
    def execute(label, argv, expected=0):
        code = record(records, label, argv)
        results.append({"label": label, "exit_code": code, "expected_exit_code": expected,
                        "receipt": str((records / label / "command.json").relative_to(archive))})
        if code != expected:
            raise RuntimeError(label + " exited " + str(code) + ", expected " + str(expected))
        return records / label
    def trusted(label, operation, output, extra=(), port=17680, expected=0):
        argv = ["env", "AEVORA_FALKORDB_PORT=" + str(port), "AEVORA_FALKORDB_GRAPH=" + graph,
                str(ROOT / "scripts/aevora-python"), str(ROOT / "aevora_core/scripts/aevora_checkpoint.py"),
                operation, "--output", str(output), *map(str, extra)]
        return execute(label, argv, expected=expected)
    started = datetime.now(timezone.utc).isoformat()
    source_epoch = {p: sha(ROOT / p) for p in ("aevora_core/src/aevora/checkpoint.py",
        "aevora_core/scripts/aevora_checkpoint.py", "aevora_core/tests/test_checkpoint.py",
        "aevora_core/tests/test_checkpoint_fifo.py",
        "scripts/aevora_h2_recovery.py", "aevora_core/src/aevora/models.py",
        "aevora_core/src/aevora/graph_repository.py", "aevora_core/src/aevora/feedback.py",
        "aevora_core/src/aevora/orderflow_outcome_bridge.py")}
    write(private / "SOURCE_EPOCH.json", source_epoch)
    verdict = "NOT_COMPLETED"
    try:
        execute("00-image-inspect", ["docker", "image", "inspect", IMAGE, "--format", "{{json .RepoDigests}}"])
        execute("01-primary-up", command + ["up", "-d", "--wait", "primary"])
        execute("02-primary-mount-inspect", ["docker", "inspect", project + "-primary", "--format", "{{json .Mounts}}"])
        mounts = json.loads((records / "02-primary-mount-inspect/stdout.log").read_text())
        volume = next(mount["Name"] for mount in mounts if mount["Destination"] == "/data")
        assert volume == project + "_primary" and volume != SOURCE_VOLUME
        execute("03-real-seed", ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
            str(ROOT / "scripts/aevora-python"), str(Path(__file__).absolute()), "seed",
            "--historical-archive", str(args.historical_archive), "--output", str(private / "seed.json")])
        trusted("04-save-boundary", "save", private / "save_boundary.json", ["--writers-quiesced"])
        execute("05-rdb-copy", ["docker", "cp", project + "-primary:/data/dump.rdb", str(private / "exported.rdb")])
        trusted("06-checkpoint-publish", "publish", private / "checkpoint_receipt.json",
            ["--rdb-source", private / "exported.rdb", "--backup-root", backups,
             "--save-boundary", private / "save_boundary.json", "--save-boundary-sha256", sha(private / "save_boundary.json"),
             "--image-digest", IMAGE_DIGEST, "--writers-quiesced"])
        checkpoint_receipt = json.loads((private / "checkpoint_receipt.json").read_text())
        checkpoint, pin = Path(checkpoint_receipt["checkpoint_dir"]), checkpoint_receipt["manifest_sha256"]
        extra = ["--checkpoint", checkpoint, "--manifest-sha256", pin]
        trusted("07-backup-integrity", "verify", private / "backup_verified.json", extra)
        execute("08-normal-stop", command + ["stop", "primary"])
        execute("09-normal-restart", command + ["up", "-d", "--wait", "primary"])
        trusted("10-normal-restart-verify", "verify-restored", private / "normal_verified.json", extra)
        execute("11-checkpoint-contracts", ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
            str(ROOT / "scripts/aevora-python"), "-m", "pytest", "-q", "aevora_core/tests/test_checkpoint.py",
            "aevora_core/tests/test_checkpoint_fifo.py",
            "--junitxml=" + str(private / "checkpoint.junit.xml")])
        # Tests issue SAVE for their UUID graph; re-establish the original checkpoint
        # RDB before the tail injection so the saved baseline remains exact.
        trusted("12-reestablish-save", "save", private / "save_before_tail.json", ["--writers-quiesced"])
        tail_started = datetime.now(timezone.utc).isoformat()
        execute("13-unsaved-trusted-feedback", ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
            str(ROOT / "scripts/aevora-python"), str(Path(__file__).absolute()), "tail-feedback",
            "--output", str(private / "unsaved_feedback.json")])
        trusted("14-tail-diverges-negative", "verify-restored", private / "tail_mismatch.json", extra, expected=2)
    except BaseException as error:
        write(private / "failure.json", {"status": "FAILED", "error_type": type(error).__name__})
        execute("98-stop-after-precondition-failure", command + ["stop"])
        raise
    try:
        execute("15-primary-sigkill", command + ["kill", "-s", "SIGKILL", "primary"])
        execute("16-killed-state", ["docker", "inspect", project + "-primary", "--format", "{{json .State}}"])
        state = json.loads((records / "16-killed-state/stdout.log").read_text())
        assert state["Running"] is False and state["ExitCode"] == 137
        execute("17-crash-restart", command + ["up", "-d", "--wait", "primary"])
        trusted("18-crash-tail-verify", "verify-restored", private / "crash_verified.json", extra)
        execute("19-new-client-query", ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
            str(ROOT / "scripts/aevora-python"), str(Path(__file__).absolute()), "new-client",
            "--output", str(private / "new_client.json")])
        for index, service in enumerate(("restore-one", "restore-two"), 1):
            target = restores / service
            trusted(f"20-{index}-stage", "stage", private / (service + "_staged.json"),
                [*extra, "--destination", target, "--server-stopped"])
            execute(f"21-{index}-create-cold", command + ["create", service])
            execute(f"22-{index}-inspect-cold", ["docker", "inspect", project + "-" + service,
                "--format", '{"state":{{json .State}},"mounts":{{json .Mounts}}}'])
            cold = json.loads((records / f"22-{index}-inspect-cold/stdout.log").read_text())
            target_volume = next(mount["Name"] for mount in cold["mounts"] if mount["Destination"] == "/data")
            assert not cold["state"]["Running"] and target_volume == project + "_" + service and target_volume != SOURCE_VOLUME
            execute(f"23-{index}-install-cold-rdb", ["docker", "run", "--rm", "--network", "none", "--read-only",
                "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
                "--mount", "type=volume,source=" + target_volume + ",target=/data",
                "--mount", "type=bind,source=" + str(target) + ",target=/restore,readonly",
                "--entrypoint", "/bin/sh", IMAGE, "-c", "test ! -e /data/dump.rdb && cp /restore/dump.rdb /data/dump.rdb"])
            execute(f"24-{index}-restore-up", command + ["up", "-d", "--wait", service])
            trusted(f"25-{index}-restored-graph-verify", "verify-restored", private / (service + "_verified.json"),
                    extra, port=17680 + index)
        # Corrupt a new backup copy while keeping the approved original untouched.
        corrupted_root = private / "corrupted_backup"
        corrupted_root.mkdir(mode=0o700)
        corrupted = corrupted_root / checkpoint.name
        shutil.copytree(checkpoint, corrupted)
        payload = bytearray((corrupted / "dump.rdb").read_bytes())
        payload[len(payload) // 2] ^= 1
        (corrupted / "dump.rdb").write_bytes(payload)
        argv = ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
                str(ROOT / "scripts/aevora-python"), str(ROOT / "aevora_core/scripts/aevora_checkpoint.py"),
                "stage", "--output", str(private / "corrupted_rejected.json"), "--checkpoint", str(corrupted),
                "--manifest-sha256", pin, "--destination", str(restores / "must-not-exist"), "--server-stopped"]
        execute("26-corrupt-backup-rejection", argv, expected=2)
        assert not (restores / "must-not-exist").exists()
        trusted("27-original-backup-still-valid", "verify", private / "original_still_valid.json", extra)
        # The actual historical Outcome is missing after recovery, then re-ingestion
        # is retried twice identically and kept as new unsaved data on an isolated DB.
        execute("28-repeat-real-outcome-after-recovery", ["env", "AEVORA_FALKORDB_PORT=17680", "AEVORA_FALKORDB_GRAPH=" + graph,
            str(ROOT / "scripts/aevora-python"), str(Path(__file__).absolute()), "tail-feedback",
            "--output", str(private / "reingested_feedback.json")])
        verdict = "PASS_RDB_SCOPE"
        feedback = json.loads((private / "unsaved_feedback.json").read_text())
        recovered = json.loads((private / "new_client.json").read_text())
        tail_ids = [feedback["feedback"]["outcome_id"], feedback["feedback"]["completion_audit_id"],
                    *(row["feedback_id"] for row in feedback["feedback"]["receipts"])]
        recovered_ids = {row[1] for row in recovered["snapshot"]["nodes"]}
        assert all(identity not in recovered_ids for identity in tail_ids)
        assert all(sha(ROOT / p) == expected for p, expected in source_epoch.items()), "Recovery source changed during run"
        write(private / "RECOVERY_GATE.json", {"status": verdict, "started_at": started,
            "ended_at": datetime.now(timezone.utc).isoformat(), "project": project, "graph_name": graph,
            "ports": [17680, 17681, 17682], "isolated_volumes": [project + "_" + key for key in services],
            "h1_volume_written": False, "checkpoint": checkpoint_receipt, "commands": results,
            "source_epoch": source_epoch, "source_bytes_unchanged_during_run": True,
            "tests_junit_sha256": sha(private / "checkpoint.junit.xml"),
            "normal_save_restart": "PASS", "sigkill_exit": 137, "unsaved_feedback_tail_lost": tail_ids,
            "repeat_cold_restore": "2/2_ACTUAL_DB_LOAD_AND_GRAPH_PATH_CONSTRAINT_MATCH",
            "repeat_real_outcome": "IDEMPOTENT", "corruption_rejected": True,
            "new_connection": "NEW_SDK_CONNECTION; NOT_CODEX_SESSION",
            "rpo": {"checkpoint_saved_at": json.loads((private / "save_before_tail.json").read_text())["saved_at"],
                    "tail_injection_started_at": tail_started,
                    "last_preserved_boundary": "EXPLICIT_RDB_SAVE", "unsaved_tail_loss": "OBSERVED",
                    "guarantee": "NO_ZERO_LOSS; NO_POWER_LOSS_PROOF; OBSERVED_LOCAL_PROCESS_CRASH_ONLY"},
            "attribution": "UNKNOWN", "kind": "CONTROLLED_HISTORICAL_REPLAY; NOT_NEW_AGENT_CHALLENGE"})
        print(json.dumps({"status": verdict, "gate": str(private / "RECOVERY_GATE.json")}))
    finally:
        execute("99-stop-isolated-services", command + ["stop"])
    return 0


def run_aof(args):
    sys.path.insert(0, str(ROOT))
    from scripts.aevora_h1_audit import record
    target = args.archive.absolute() / "g0_aof_replay"
    target.mkdir(mode=0o700)
    name = "aevora-h2-aof-replay-" + args.archive.name.split("-")[-1][:10]
    hash_argv = ["docker", "run", "--rm", "--network", "none", "--read-only", "--memory", "256m",
                "--cpus", "1", "--pids-limit", "64", "--mount", "type=volume,source=" + SOURCE_VOLUME + ",target=/source,readonly",
                "--entrypoint", "/bin/sh", IMAGE, "-c", "sha256sum /source/appendonlydir/*"]
    record(target, "source-aof-before", hash_argv)
    argv = ["docker", "run", "--name", name, "--network", "none", "--read-only", "--memory", "1g", "--cpus", "2",
        "--pids-limit", "256", "--tmpfs", "/replay:rw,size=256m", "--mount",
        "type=volume,source=" + SOURCE_VOLUME + ",target=/source,readonly", "--entrypoint", "/bin/sh", IMAGE, "-c",
        'cp -a /source/appendonlydir /replay/ && timeout 30s redis-server --loadmodule /var/lib/falkordb/bin/falkordb.so '
        '--dir /replay --appendonly yes --appendfilename appendonly.aof --port 0 --unixsocket /replay/redis.sock --save ""']
    code = record(target, "retained-aof-isolated-replay", argv)
    record(target, "source-aof-after", hash_argv)
    before = (target / "source-aof-before/stdout.log").read_bytes()
    after = (target / "source-aof-after/stdout.log").read_bytes()
    log = (target / "retained-aof-isolated-replay/stdout.log").read_text(errors="replace")
    record(target, "aof-container-inspect", ["docker", "inspect", name, "--format", '{"state":{{json .State}},"mounts":{{json .Mounts}}}'])
    observations = {"SIGSEGV": re.search(r"crashed by signal:\s*11\b", log) is not None, "GRAPH_EFFECT": "GRAPH.EFFECT" in log,
                    "GraphContext_GetSchemaByID": "GraphContext_GetSchemaByID" in log}
    write(target / "AOF_REPLAY_RESULT.json", {"status": "CONFIRMED_AOF_REPLAY_FAILURE" if code == 139 and all(observations.values()) else "UNEXPECTED_REPLAY_RESULT",
        "kind": "NEW_H2_READ_ONLY_RETAINED_DATA_REPLAY", "image_digest": IMAGE_DIGEST, "exit_code": code,
        "source_volume": SOURCE_VOLUME, "source_mount": "READ_ONLY", "working_copy": "DISPOSABLE_TMPFS",
        "network": "NONE", "credential_mounts": False, "source_aof_bytes_unchanged": before == after,
        "source_aof_sha_receipt_sha256": sha(target / "source-aof-before/command.json"),
        "raw_log_sha256": sha(target / "retained-aof-isolated-replay/stdout.log"), "observations": observations,
        "root_cause_identity_with_upstream_issue_2201": "UNVERIFIED", "mitigation": "RDB_CHECKPOINT; AOF_REPAIR_NOT_BLOCKING_H2"})
    assert before == after and code == 139 and all(observations.values())
    print(json.dumps({"status": "CONFIRMED_AOF_REPLAY_FAILURE", "exit_code": code}))
    return 0


def review_aof(args):
    """Additive review of sealed command bytes; do not edit the first collector result."""
    target = args.archive.absolute() / "g0_aof_replay"
    before = target / "source-aof-before"
    after = target / "source-aof-after"
    replay = target / "retained-aof-isolated-replay"
    receipt = json.loads((replay / "command.json").read_text())
    for directory in (before, after, replay):
        record = json.loads((directory / "command.json").read_text())
        assert record["stdout_sha256"] == sha(directory / "stdout.log")
        assert record["stderr_sha256"] == sha(directory / "stderr.log")
    assert json.loads((before / "command.json").read_text())["exit_code"] == 0
    assert json.loads((after / "command.json").read_text())["exit_code"] == 0
    assert (before / "stdout.log").read_bytes() == (after / "stdout.log").read_bytes()
    argv = receipt["argv"]
    assert argv[argv.index("--network") + 1] == "none" and "--read-only" in argv
    assert "type=volume,source=" + SOURCE_VOLUME + ",target=/source,readonly" in argv
    assert not any("password" in argument or "key" in argument for argument in argv)
    log = (replay / "stdout.log").read_text(errors="replace")
    observations = {"SIGSEGV_11": re.search(r"crashed by signal:\s*11\b", log) is not None,
                    "GraphContext_GetSchemaByID": "GraphContext_GetSchemaByID" in log,
                    "GRAPH_EFFECT": "GRAPH.EFFECT" in log}
    assert receipt["exit_code"] == 139 and all(observations.values())
    result = {"status": "CONFIRMED_AOF_REPLAY_FAILURE", "evidence_kind": "ADDITIVE_REVIEW_OF_THIS_H2_DYNAMIC_REPLAY",
              "original_collector_exit": 1, "original_collector_issue": "Searched 'signal 11', but actual Redis reports 'signal: 11'",
              "original_collector_result_preserved": True, "engine_exit": 139,
              "replay_receipt_sha256": sha(replay / "command.json"), "raw_log_sha256": sha(replay / "stdout.log"),
              "observations": observations, "source_aof_bytes_unchanged": True,
              "source_volume_mount": "READ_ONLY", "credential_mounts": False,
              "image_digest": IMAGE_DIGEST, "upstream_exact_root_cause": "UNVERIFIED"}
    write(target / "AOF_REPLAY_REVIEW_V2.json", result)
    print(json.dumps(result))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["run", "aof", "aof-review", "seed", "tail-feedback", "new-client"])
    p.add_argument("--archive", type=Path)
    p.add_argument("--historical-archive", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--trial-label", default="g0_recovery")
    args = p.parse_args()
    if args.operation == "run":
        return run_recovery(args)
    if args.operation == "aof":
        return run_aof(args)
    if args.operation == "aof-review":
        return review_aof(args)
    return trusted_operation(args)


if __name__ == "__main__":
    raise SystemExit(main())
