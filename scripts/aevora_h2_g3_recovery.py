#!/usr/bin/env python3
"""Trusted H2-G3 RDB SAVE/publication/cold restore after a real sealed Outcome.

No model requests, fabricated Outcomes, restore into source volumes, H1 access
or password argv. Plan/help are declarative and do not contact Docker or a DB.
Only a new scoped target may be retained for a later separately audited session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62"
IMAGE_DIGEST = IMAGE.split("@", 1)[1]
GRAPH = "aevora_h2_g3_reviewed"
SOURCE_PORT, RESTORE_PORT = 17679, 17683
VERSION = "aevora.h2-g3-rdb-recovery/1.0"
HEX = re.compile(r"[0-9a-f]{64}\Z")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
ARCHIVE = re.compile(r"H2-[0-9]{8}T[0-9]{6}Z-[0-9a-f-]{36}\Z")


class RecoveryRejected(ValueError):
    """Input, actual deployment or graph verification failed."""


def require(condition, message):
    if not condition:
        raise RecoveryRejected(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def ordinary(path):
    path = Path(path).absolute()
    require(not any(part.is_symlink() for part in (path, *path.parents)), "Linked path components refused")
    return path


def digest(path):
    value = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
    require(len(data) <= 32 * 1024**2, "New evidence exceeds its archive byte bound")
    fd = os.open(ordinary(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def read_json(path):
    from aevora.checkpoint import _read, _json, MAX_MANIFEST_BYTES
    return _json(_read(ordinary(path), MAX_MANIFEST_BYTES))


def public_source_identity(value):
    """Accept only actual H2 source metadata, never Config.Env/auth values."""
    require(isinstance(value, dict), "Actual source inspection is absent")
    ports = value.get("ports")
    bindings = ports.get("6379/tcp") if isinstance(ports, dict) else None
    require(isinstance(value.get("state"), dict) and value["state"].get("Running") is True
            and value.get("configured_image") == IMAGE
            and isinstance(bindings, list) and bindings == [{"HostIp": "127.0.0.1", "HostPort": str(SOURCE_PORT)}],
            "Source must be the running pinned H2 loopback17679 deployment")
    require(isinstance(value.get("mounts"), list) and all(isinstance(row, dict) for row in value["mounts"]),
            "Actual Docker mount metadata is malformed")
    data = [row for row in value["mounts"] if row.get("Destination") == "/data"]
    require(len(data) == 1 and data[0].get("Type") == "volume"
            and isinstance(data[0].get("Name"), str) and data[0]["Name"].startswith("aevora-h2-")
            and "h1" not in data[0]["Name"], "Source data volume must be isolated H2, never H1")
    return data[0]["Name"]


def compose_config(project, config_file, password_file):
    require(re.fullmatch(r"aevora-h2-g3-recovery-[0-9a-f]{8}-[0-9a-f]{8}", project) is not None,
            "Only this controller's new random project namespace is allowed")
    service = {"image": IMAGE, "container_name": project + "-restored",
        "entrypoint": ["redis-server"], "command": ["--loadmodule", "/var/lib/falkordb/bin/falkordb.so",
            "--include", "/run/secrets/redis.conf", "--appendonly", "no", "--save", "", "--dir", "/data"],
        "ports": ["127.0.0.1:17683:6379"], "volumes": ["restored-data:/data"],
        "secrets": ["redis.conf", "db.password"], "restart": "no",
        "mem_limit": "1g", "cpus": 2, "pids_limit": 256,
        "healthcheck": {"test": ["CMD-SHELL",
            'test "$$(redis-cli ping)" = "NOAUTH Authentication required." && test "$$(REDISCLI_AUTH="$$(cat /run/secrets/db.password)" redis-cli -e ping)" = PONG'],
            "interval": "2s", "timeout": "3s", "retries": 20}}
    return {"name": project, "services": {"restored": service}, "volumes": {"restored-data": {}},
        "secrets": {"redis.conf": {"file": str(config_file)}, "db.password": {"file": str(password_file)}}}


def checked_secret_metadata(path, archive):
    """Stat-only credential gate; never read/hash/copy secret contents."""
    path = ordinary(path)
    require(path.parent.name == archive.name and str(path.parent).startswith("/home/"),
            "Only the current H2 project-specific host credential directory is accepted")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600, "Credential must be owner-only ordinary single-link file")
    return path


def validate_controller(args):
    archive = ordinary(args.archive)
    require(archive.is_dir() and ARCHIVE.fullmatch(archive.name)
            and archive.parent == ROOT / "aevora_validation", "Only the current independent H2 Full Archive is accepted")
    require(not (archive / "EVIDENCE_MANIFEST.json").exists(), "No new evidence is appended to a finally sealed Full")
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,80}", args.label) is not None, "Simple new evidence label required")
    require(isinstance(args.source_container, str) and args.source_container.startswith("aevora-h2-")
            and re.fullmatch(r"[A-Za-z0-9_.-]+", args.source_container) is not None
            and "h1" not in args.source_container, "Source container must be explicitly H2, never H1")
    require(type(args.command_timeout) is int and 10 <= args.command_timeout <= 300, "Finite offline command timeout required")
    runtime = ordinary(args.runtime)
    require(runtime.is_relative_to(ROOT / "aevora_validation/h2_runtime" / archive.name),
            "Explicit independently verified current H2 runtime required")
    return archive, runtime


def source_epoch():
    names = ["scripts/aevora_h2_g3_recovery.py", "scripts/aevora_h2_graph_maintenance.py",
        "scripts/aevora_h2_graph_e2e.py", "scripts/aevora-h2-python", "aevora_core/scripts/aevora_checkpoint.py"]
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "aevora_core/src/aevora").glob("*.py"))]
    return {name: digest(ROOT / name) for name in names}


def load_admitted_outcome(args):
    require(args.trusted_outcome is not None and args.ingest_receipt is not None
            and HEX.fullmatch(args.trusted_outcome_sha256 or "")
            and HEX.fullmatch(args.ingest_receipt_sha256 or ""),
            "Actual trusted current-live Outcome and ingest receipt pins are required")
    outcome_path, receipt_path = ordinary(args.trusted_outcome), ordinary(args.ingest_receipt)
    require(outcome_path.name == "VERIFIED_ENGINEERING_OUTCOME.json"
            and receipt_path.name == "TRUSTED_INGEST_RECEIPT.json" and outcome_path.parent == receipt_path.parent,
            "Use the actual completed trusted-ingest artifacts")
    outcome, receipt = read_json(outcome_path), read_json(receipt_path)
    require(digest(outcome_path) == args.trusted_outcome_sha256 and digest(receipt_path) == args.ingest_receipt_sha256,
            "Trusted actual Outcome/ingest receipt differs from its approved pin")
    require(outcome.get("source_type") == "current_live" and outcome.get("verification_profile") == "current_live"
            and outcome.get("episode_id") == "D-V02" and UUID.fullmatch(outcome.get("run_id", ""))
            and outcome.get("id") == "orderflow:" + outcome["run_id"] and HEX.fullmatch(outcome.get("immutable_digest", "")),
            "Only the actual new D-V02 current-live Outcome is admitted")
    require(receipt.get("status") == "INGESTED" and receipt.get("outcome_id") == outcome["id"]
            and receipt.get("run_id") == outcome["run_id"] and receipt.get("verdict") == outcome.get("verdict")
            and receipt.get("feedback_status") == "outcome_observed_no_attribution"
            and isinstance(receipt.get("receipts"), list) and receipt["receipts"],
            "Actual completed trusted observed feedback is required, regardless of solving verdict")
    return outcome, receipt


def trusted_endpoint(port):
    require(os.environ.get("AEVORA_FALKORDB_HOST", "127.0.0.1") == "127.0.0.1"
            and os.environ.get("AEVORA_FALKORDB_PORT") == str(port)
            and os.environ.get("AEVORA_FALKORDB_GRAPH") == GRAPH, "Wrong trusted recovery endpoint")


def target_worker(args):
    from aevora.graph_repository import GraphRepository
    from aevora.checkpoint import capture_graph
    from aevora.models import digest as payload_digest
    trusted_endpoint(args.port)
    require(args.port in (SOURCE_PORT, RESTORE_PORT), "Only dedicated H2 source/new-target ports allowed")
    outcome, receipt = load_admitted_outcome(args)
    repository = GraphRepository.from_environment()
    sys.path.insert(0, str(ROOT))
    from scripts.aevora_h2_graph_e2e import RawCommands
    raw_directory = args.output.parent / (args.output.stem + "-raw")
    raw_directory.mkdir(mode=0o700, exist_ok=False)
    journal = RawCommands(raw_directory)
    journal.attach(repository)
    try:
        before = capture_graph(repository)
        stored = repository.get_node("VerifiedOutcome", outcome["id"])
        completion = repository.get_node("AuditEvent", receipt["completion_audit_id"])
        require(stored == outcome and completion is not None and completion.get("outcome_id") == outcome["id"]
                and completion.get("outcome_digest") == outcome["immutable_digest"]
                and completion.get("run_id") == outcome["run_id"], "Actual target Outcome/ingestion completion is absent or changed")
        observed = []
        for row in receipt["receipts"]:
            require(row.get("outcome_id") == outcome["id"] and row.get("relation") == "OBSERVED_OUTCOME",
                    "Trusted receipt contains unrelated feedback")
            repository.require_edge("OBSERVED_OUTCOME", "ExperienceRevision", row["revision_id"], "Evidence", row["evidence_id"])
            repository.require_edge("VERIFIES", "Evidence", row["evidence_id"], "VerifiedOutcome", outcome["id"])
            require(any(path.get("records", {}).get("VerifiedOutcome", {}).get("id") == outcome["id"]
                        and path.get("relation") == "OBSERVED_OUTCOME"
                        for path in repository.snapshot_public_paths(row["experience_id"])),
                    "Actual newly observed public evidence path is unavailable")
            observed.append({k: row[k] for k in ("experience_id", "revision_id", "evidence_id", "feedback_id", "outcome_id", "relation")})
        after = capture_graph(repository)
        require(before == after, "Writers changed the graph during target verification")
        result = {"status": "ACTUAL_TRUSTED_TARGET_PATHS_VERIFIED", "port": args.port, "graph_name": GRAPH,
            "target_outcome_id": outcome["id"], "target_verdict": outcome["verdict"],
            "target_payload_sha256": payload_digest(stored), "immutable_digest": outcome["immutable_digest"],
            "completion_audit_id": completion["id"], "actual_observed_paths": observed, "snapshot": after,
            "client_identity": "NEW_TRUSTED_SDK_CONNECTION; NOT_CODEX_SESSION", "attribution": "UNKNOWN"}
    finally:
        try:
            journal.close()
        finally:
            repository.close()
    result.update(raw_graph_commands=str(journal.path), raw_command_count=journal.count,
                  raw_graph_commands_sha256=digest(journal.path), disclosure="TRUSTED_HOST_ONLY")
    write(args.output, result)
    return 0


def save_worker(args):
    trusted_endpoint(SOURCE_PORT)
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt("Offline maintenance cancellation")
    previous = signal.signal(signal.SIGTERM, interrupted)
    sys.path.insert(0, str(ROOT))
    from scripts.aevora_h2_graph_maintenance import paused_auto_save
    spec = importlib.util.spec_from_file_location("trusted_existing_checkpoint_cli", ROOT / "aevora_core/scripts/aevora_checkpoint.py")
    checkpoint_cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(checkpoint_cli)
    try:
        with paused_auto_save(args.output.parent):
            require(checkpoint_cli.main(["save", "--output", str(args.output), "--writers-quiesced"]) == 0,
                    "Actual existing SAVE CLI did not complete")
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0


def run_controller(args):
    archive, runtime = validate_controller(args)
    config_file = checked_secret_metadata(args.redis_config_file, archive)
    password_file = checked_secret_metadata(args.password_file, archive)
    output = archive / "g3" / args.label
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    commands = output / "commands"; commands.mkdir(mode=0o700)
    backups = output / "backups"; backups.mkdir(mode=0o700)
    staging = output / "restore_staging"; staging.mkdir(mode=0o700)
    project = "aevora-h2-g3-recovery-" + uuid.uuid4().hex[:8] + "-" + uuid.uuid4().hex[:8]
    container, volume = project + "-restored", project + "_restored-data"
    compose_file = output / "compose.json"
    write(compose_file, compose_config(project, config_file, password_file))
    compose = ["docker", "compose", "-p", project, "-f", str(compose_file)]
    epoch = source_epoch(); write(output / "SOURCE_EPOCH.json", epoch)
    started, receipts, created, retained, error, result = now(), [], False, False, None, None
    sys.path.insert(0, str(ROOT))
    from scripts.aevora_h1_audit import record
    def execute(label, argv):
        code = record(commands, label, ["timeout", "--signal=TERM", "--kill-after=15s", str(args.command_timeout) + "s", *map(str, argv)])
        receipts.append({"label": label, "actual_exit_code": code, "command_receipt": str((commands / label / "command.json").relative_to(archive))})
        require(code == 0, "COMMAND_TIMEOUT" if code == 124 else "Actual step failed: " + label)
        return commands / label
    def trusted(label, script, parameters, port=SOURCE_PORT):
        return execute(label, ["env", "AEVORA_H2_RUNTIME=" + str(runtime), "AEVORA_FALKORDB_PORT=" + str(port),
            "AEVORA_FALKORDB_GRAPH=" + GRAPH, "AEVORA_FALKORDB_PASSWORD_FILE=" + str(password_file),
            str(ROOT / "scripts/aevora-h2-python"), "-I", "-B", script, *parameters])
    target_args = ["--trusted-outcome", str(args.trusted_outcome), "--trusted-outcome-sha256", args.trusted_outcome_sha256,
        "--ingest-receipt", str(args.ingest_receipt), "--ingest-receipt-sha256", args.ingest_receipt_sha256]
    try:
        require(all(isinstance(p, str) for p in target_args), "Actual Outcome/ingest pin arguments are required")
        image = execute("00-pinned-image", ["docker", "image", "inspect", IMAGE, "--format", "{{json .RepoDigests}}"])
        require(any(value.endswith("@" + IMAGE_DIGEST) for value in json.loads((image / "stdout.log").read_text())),
                "Actual official image digest differs")
        inspected = execute("01-source-inspect", ["docker", "inspect", args.source_container, "--format",
            '{"state":{{json .State}},"configured_image":{{json .Config.Image}},"image_id":{{json .Image}},"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}}}'])
        actual_source = json.loads((inspected / "stdout.log").read_text())
        source_volume = public_source_identity(actual_source)
        trusted("02-target-source", str(Path(__file__).resolve()),
            ["_target", "--port", str(SOURCE_PORT), "--output", str(output / "source_target.json"), *target_args])
        trusted("03-save-boundary", str(Path(__file__).resolve()),
            ["_save", "--output", str(output / "save_boundary.json")])
        execute("04-copy-source-rdb", ["docker", "cp", args.source_container + ":/data/dump.rdb", str(output / "exported.rdb")])
        (output / "exported.rdb").chmod(0o600)
        cli = str(ROOT / "aevora_core/scripts/aevora_checkpoint.py")
        trusted("05-publish-checkpoint", cli, ["publish", "--output", str(output / "checkpoint_receipt.json"),
            "--rdb-source", str(output / "exported.rdb"), "--backup-root", str(backups),
            "--save-boundary", str(output / "save_boundary.json"), "--save-boundary-sha256", digest(output / "save_boundary.json"),
            "--image-digest", IMAGE_DIGEST, "--writers-quiesced"])
        checkpoint = json.loads((output / "checkpoint_receipt.json").read_text())
        restore_args = ["--checkpoint", checkpoint["checkpoint_dir"], "--manifest-sha256", checkpoint["manifest_sha256"]]
        trusted("06-checkpoint-integrity", cli, ["verify", "--output", str(output / "checkpoint_verified.json"), *restore_args])
        destination = staging / "cold-restored"
        trusted("07-cold-stage", cli, ["stage", "--output", str(output / "restore_staged.json"), *restore_args,
            "--destination", str(destination), "--server-stopped"])
        created = True
        execute("08-new-target-create", compose + ["create", "restored"])
        inspected = execute("09-new-target-inspect-cold", ["docker", "inspect", container, "--format",
            '{"state":{{json .State}},"configured_image":{{json .Config.Image}},"image_id":{{json .Image}},"mounts":{{json .Mounts}}}'])
        cold = json.loads((inspected / "stdout.log").read_text())
        target_mounts = [row for row in cold["mounts"] if row.get("Destination") == "/data"]
        require(cold["state"]["Running"] is False and cold["configured_image"] == IMAGE
                and cold["image_id"] == actual_source["image_id"] and len(target_mounts) == 1
                and target_mounts[0].get("Type") == "volume" and target_mounts[0].get("Name") == volume
                and volume != source_volume and "h1" not in volume,
                "Only the new stopped target volume may receive RDB bytes")
        execute("10-install-new-volume-rdb", ["docker", "run", "--rm", "--network", "none", "--read-only",
            "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
            "--mount", "type=volume,source=" + volume + ",target=/data",
            "--mount", "type=bind,source=" + str(destination) + ",target=/restore,readonly",
            "--entrypoint", "/bin/sh", IMAGE, "-c",
            "test ! -e /data/dump.rdb && cp /restore/dump.rdb /data/dump.rdb"])
        execute("11-restored-up", compose + ["up", "-d", "--wait", "--wait-timeout", "60", "restored"])
        trusted("12-restored-graph-verify", cli, ["verify-restored", "--output", str(output / "restored_verified.json"), *restore_args], RESTORE_PORT)
        trusted("13-restored-target-paths", str(Path(__file__).resolve()),
            ["_target", "--port", str(RESTORE_PORT), "--output", str(output / "restored_target.json"), *target_args], RESTORE_PORT)
        trusted("14-source-still-identical", str(Path(__file__).resolve()),
            ["_target", "--port", str(SOURCE_PORT), "--output", str(output / "source_after.json"), *target_args])
        prior = json.loads((output / "source_target.json").read_text())
        restored = json.loads((output / "restored_target.json").read_text())
        after = json.loads((output / "source_after.json").read_text())
        boundary = json.loads((output / "save_boundary.json").read_text())
        require(prior["snapshot"] == restored["snapshot"] == after["snapshot"] == boundary["graph_snapshot"]
                and prior["actual_observed_paths"] == restored["actual_observed_paths"],
                "Restored/new-source actual Outcome graph differs")
        require(source_epoch() == epoch, "Trusted recovery source changed during execution")
        retained = args.retain_restored_for_readback is True
        result = {"status": "PASS", "scope": "ACTUAL_RDB_SAVE_PUBLISH_COLD_NEW_VOLUME_RESTORE; NO_CODEX_READBACK_YET",
            "target_outcome_id": prior["target_outcome_id"], "target_verdict": prior["target_verdict"],
            "target_immutable_digest": prior["immutable_digest"], "graph_sha256": prior["snapshot"]["graph_sha256"],
            "node_count": prior["snapshot"]["node_count"], "edge_count": prior["snapshot"]["edge_count"],
            "actual_observed_paths": restored["actual_observed_paths"], "checkpoint": checkpoint,
            "source_volume": source_volume, "restored_volume": volume, "restore_container": container,
            "restored_port": RESTORE_PORT, "restored_graph": GRAPH, "restored_container_retained": retained,
            "persistence_scope": "REAL_INSTANCE_LEVEL_RDB; REVIEWED_GRAPH_ONLY_VERIFIED; NO_AOF_OR_ZERO_LOSS_CLAIM",
            "rpo": "Writes after this completed SAVE can be lost", "model_session_readback": "UNVERIFIED",
            "attribution": "UNKNOWN"}
    except BaseException as caught:
        error = {"status": "ERROR", "error_type": type(caught).__name__,
            "classification": "ACTUAL_RECOVERY_ABORT; NO_FALLBACK_OR_SOURCE_RESTORE"}
        write(output / "RECOVERY_ERROR.json", error)
    finally:
        cleanup_error = None
        if created and not retained:
            try:
                execute("98-stop-new-target-only", compose + ["stop", "restored"])
            except BaseException as caught:
                cleanup_error = {"status": "ERROR", "error_type": type(caught).__name__}
                write(output / "CLEANUP_ERROR.json", cleanup_error)
        if result is None or error is not None or cleanup_error is not None:
            result = {"status": "ERROR", "scope": "ACTUAL_STEP_FAILURE_RETAINED; NO_RESTORE_PASS", "error": error, "cleanup_error": cleanup_error}
        result.update(version=VERSION, started_at=started, finished_at=now(), commands=receipts,
            source_epoch_sha256=digest(output / "SOURCE_EPOCH.json"), compose_sha256=digest(compose_file),
            cleanup_policy="Only the new scoped restore service is stopped; its new evidence volume is retained",
            source_container_never_stopped=True, h1_access="NONE",
            restore_down_command=compose + ["down"], no_secret_contents_or_standalone_hash_archived=True)
        write(output / "RECOVERY_GATE.json", result)
    print(json.dumps({"status": result["status"], "gate": str(output / "RECOVERY_GATE.json"),
        "gate_sha256": digest(output / "RECOVERY_GATE.json"), "restore_port": RESTORE_PORT}))
    return 0 if result["status"] == "PASS" else 2


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="operation", required=True)
    for operation in ("plan", "run"):
        command = commands.add_parser(operation)
        command.add_argument("archive", type=Path)
        command.add_argument("--label", required=True)
        command.add_argument("--source-container", required=True)
        command.add_argument("--runtime", type=Path, required=True)
        command.add_argument("--redis-config-file", type=Path, required=True)
        command.add_argument("--password-file", type=Path, required=True)
        command.add_argument("--trusted-outcome", type=Path)
        command.add_argument("--trusted-outcome-sha256")
        command.add_argument("--ingest-receipt", type=Path)
        command.add_argument("--ingest-receipt-sha256")
        command.add_argument("--writers-quiesced", action="store_true", required=True)
        command.add_argument("--command-timeout", type=int, default=90)
        command.add_argument("--retain-restored-for-readback", action="store_true")
    save = commands.add_parser("_save"); save.add_argument("--output", type=Path, required=True)
    target = commands.add_parser("_target"); target.add_argument("--output", type=Path, required=True)
    target.add_argument("--port", type=int, required=True)
    for field in ("trusted-outcome", "ingest-receipt"):
        target.add_argument("--" + field, type=Path, required=True)
        target.add_argument("--" + field + "-sha256", required=True)
    args = cli.parse_args(argv)
    os.umask(0o077)
    try:
        if args.operation == "_save":
            return save_worker(args)
        if args.operation == "_target":
            return target_worker(args)
        if args.operation == "run":
            return run_controller(args)
        archive, runtime = validate_controller(args)
        config_file, password_file = ordinary(args.redis_config_file), ordinary(args.password_file)
        output = archive / "g3" / args.label
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        write(output / "DECLARATIVE_PLAN.json", {"status": "NOT_EXECUTED",
            "scope": "STATIC_PLAN_ONLY; NO_DOCKER_DB_SECRET_READ_OR_RESTORE",
            "source_container": args.source_container, "source_port": SOURCE_PORT, "restore_port": RESTORE_PORT,
            "graph_key": GRAPH, "image": IMAGE, "runtime": str(runtime),
            "secrets": "EXTERNAL_HOST_FILE_PATHS_ONLY; CONTENT_AND_HASH_NOT_READ",
            "required_actual_runtime_pins": ["VERIFIED_ENGINEERING_OUTCOME.json/SHA", "TRUSTED_INGEST_RECEIPT.json/SHA"],
            "steps": ["source image/port/volume inspection", "real observed Outcome/path check",
                "controlled mature SAVE boundary", "source RDB copy", "atomic pinned publication",
                "cold stage/new dedicated project-volume", "same-image load at17683",
                "full exact graph/path/constraint equality", "new-source unchanged check"],
            "retain_for_future_readback": args.retain_restored_for_readback, "new_codex_session": "NOT_STARTED",
            "source_epoch": source_epoch()})
        print(json.dumps({"status": "NOT_EXECUTED", "plan": str(output / "DECLARATIVE_PLAN.json")}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError) as error:
        print(json.dumps({"status": "ERROR", "error_type": type(error).__name__, "scope": "NO_FALSE_RECOVERY_PASS"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
