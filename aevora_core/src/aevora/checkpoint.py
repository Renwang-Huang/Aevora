"""Maintainer-only RDB checkpoints with explicit quiescence and cold restore.

Redis produces the actual RDB; this module never serializes graph JSON into a
pretend database. Hash pins are local integrity authority, not attestation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any
import uuid

from .models import LABELS, RELATIONSHIPS, SCHEMA_VERSION, QUERY_VERSION, digest, schema_catalog, InvalidRecord

CHECKPOINT_VERSION = "aevora.rdb_checkpoint/1.0"
MAX_RDB_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class CheckpointRejected(ValueError):
    """No backup/restore publication is authorized by the supplied evidence."""


def _check(ok: bool, message: str) -> None:
    if not ok:
        raise CheckpointRejected(message)


def _sha_pin(value: str) -> str:
    _check(isinstance(value, str) and _SHA.fullmatch(value) is not None,
           "An approved lowercase manifest SHA256 is required")
    return value


def _parents(path: Path) -> None:
    for parent in (path, *path.parents):
        _check(not parent.is_symlink(), "Symlink path components are forbidden")


def _read(path: Path, maximum: int) -> bytes:
    _parents(path)
    # Reject FIFO/devices using fstat without first blocking at open(FIFO).
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _check(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
               and before.st_uid == os.getuid(), "Owned single-link ordinary files required")
        _check(0 < before.st_size <= maximum, "File size is outside the checkpoint bound")
        chunks = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        data = b"".join(chunks)
        _check(len(data) == before.st_size and before.st_size == after.st_size
               and before.st_mtime_ns == after.st_mtime_ns
               and before.st_ctime_ns == after.st_ctime_ns,
               "Checkpoint input changed while being read")
        return data
    finally:
        os.close(fd)


def _json(data: bytes) -> dict:
    def pairs(values):
        result = {}
        for key, value in values:
            _check(key not in result, "Duplicate manifest keys are forbidden")
            result[key] = value
        return result
    try:
        result = json.loads(data, object_pairs_hook=pairs,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                CheckpointRejected("Nonfinite manifest value")))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise CheckpointRejected("Checkpoint manifest is not valid JSON") from None
    _check(isinstance(result, dict), "Checkpoint manifest must be an object")
    stack = [(result, 0)]
    visited = 0
    while stack:
        value, depth = stack.pop()
        visited += 1
        _check(depth <= 64 and visited <= 500000, "Checkpoint JSON structure exceeds bounds")
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    return result


def _write(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private_directory(path: Path) -> None:
    _parents(path)
    info = path.stat()
    _check(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
           and stat.S_IMODE(info.st_mode) == 0o700,
           "Checkpoint directories must be owned mode-0700 directories")


def _catalog(version):
    try:
        return schema_catalog(version)
    except InvalidRecord:
        raise CheckpointRejected("Incompatible graph schema/query version") from None


def _validate_constraints(constraints: Any, schema_version: str = SCHEMA_VERSION) -> list[dict]:
    """Validate actual SDK rows against this source epoch's complete schema.

    Property order has no semantic significance; duplicate properties or rows
    do. Counting OPERATIONAL rows alone cannot establish the active schema.
    """
    labels = _catalog(schema_version)["labels"]
    expected = {(label, "UNIQUE", ("id",)) for label in labels}
    expected.update((label, "MANDATORY", ("id", "payload_json", "payload_sha256"))
                    for label in labels)
    _check(isinstance(constraints, list) and len(constraints) == len(expected),
           "Actual schema constraint cardinality differs from the required schema")
    seen = set()
    for row in constraints:
        _check(isinstance(row, dict) and row.get("entitytype") == "NODE"
               and row.get("status") == "OPERATIONAL", "Invalid or non-operational node constraint")
        label, kind, properties = row.get("label"), row.get("type"), row.get("properties")
        _check(isinstance(label, str) and isinstance(kind, str)
               and isinstance(properties, list) and all(isinstance(value, str) for value in properties),
               "Malformed actual schema constraint")
        _check(len(properties) == len(set(properties)), "Duplicate constraint properties")
        identity = label, kind, tuple(sorted(properties))
        _check(identity in expected and identity not in seen,
               "Unexpected or duplicate actual schema constraint")
        seen.add(identity)
    _check(seen == expected, "Actual schema constraints do not match the required schema")
    return sorted(constraints, key=lambda row: json.dumps(row, sort_keys=True))


def capture_graph(repo, *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    """Check payload bytes, all identities/relations and actual public paths.

    Queries are separate statements. The caller must stop trusted writers; an
    equal state comparison is an additional check, not an ABA-proof fence.
    """
    catalog = _catalog(schema_version)
    nodes = repo.query("MATCH (n) RETURN labels(n),n.id,n.payload_json,n.payload_sha256 ORDER BY n.id")
    edges = repo.query("MATCH (s)-[r]->(t) RETURN s.id,type(r),r.id,r.payload_json,r.payload_sha256,t.id "
                       "ORDER BY s.id,type(r),r.id,t.id")
    node_rows, edge_rows, identities = [], [], set()
    schema_present = False
    for labels, identity, raw, fingerprint in nodes:
        _check(len(labels) == 1 and labels[0] in catalog["labels"], "Unknown or ambiguous node label")
        payload = _json(raw.encode("utf-8"))
        _check(payload.get("id") == identity and digest(payload) == fingerprint,
               "Node payload does not match its stored identity/digest")
        _check(identity not in identities, "Duplicate node identity")
        identities.add(identity)
        if labels == ["Schema"] and identity == schema_version:
            schema_present = payload.get("version") == schema_version
        node_rows.append([labels, identity, fingerprint])
    _check(schema_present, "Actual active graph schema marker is absent")
    edge_ids = set()
    for source, relation, identity, raw, fingerprint, target in edges:
        _check(relation in catalog["relationships"] and source in identities and target in identities,
               "Unknown relation or absent endpoint")
        payload = _json(raw.encode("utf-8"))
        _check(payload.get("id") == identity and digest(payload) == fingerprint,
               "Edge payload does not match its stored identity/digest")
        _check(identity not in edge_ids, "Duplicate relation identity")
        edge_ids.add(identity)
        edge_rows.append([source, relation, identity, fingerprint, target])
    constraints = _validate_constraints(repo._graph.list_constraints(), schema_version)
    return {"graph_name": repo.graph_name, "schema_version": schema_version,
            "query_version": catalog["query_version"], "node_count": len(nodes), "edge_count": len(edges),
            "nodes": node_rows, "edges": edge_rows,
            "graph_sha256": digest({"nodes": node_rows, "edges": edge_rows}),
            "constraints": constraints,
            "public_paths": {key: {"premises": repo.premise_paths(key),
                                   "evidence": repo.snapshot_public_paths(key)}
                             for key in repo.experience_ids()}}


def save_boundary(repo, *, writers_quiesced: bool, schema_version: str = SCHEMA_VERSION) -> dict:
    _check(writers_quiesced is True, "Trusted writers must be explicitly quiesced")
    before = capture_graph(repo, schema_version=schema_version)
    try:
        saved = repo._client.connection.save()
        persistence = repo._client.connection.info("persistence")
        server = repo._client.connection.info("server")
    except Exception as error:
        raise CheckpointRejected("RDB SAVE failed: " + type(error).__name__) from None
    after = capture_graph(repo, schema_version=schema_version)
    _check(saved is True and persistence.get("loading") == 0
           and persistence.get("aof_enabled") == 0
           and persistence.get("rdb_last_bgsave_status") == "ok", "RDB persistence boundary failed")
    _check(before == after, "Graph changed across SAVE")
    return {"version": CHECKPOINT_VERSION, "saved_at": datetime.now(timezone.utc).isoformat(),
            "save_result": True, "writers_quiesced": True, "graph_snapshot": after,
            "redis_version": server["redis_version"],
            "rdb_last_save_time": persistence["rdb_last_save_time"],
            "consistency_scope": "TRUSTED_WRITERS_QUIESCED; TWO_STATE_CHECK; NO_HOSTILE_ADMIN_FENCE"}


def publish_checkpoint(rdb_source: Path, backup_root: Path, boundary: dict,
                       live_snapshot: dict, *, image_digest: str,
                       writers_quiesced: bool) -> dict:
    """Publish Redis-produced RDB after a trusted SAVE/copy/graph-check pipeline."""
    _check(writers_quiesced is True and boundary.get("writers_quiesced") is True,
           "Trusted writers must remain explicitly quiesced")
    _check(boundary.get("version") == CHECKPOINT_VERSION and boundary.get("save_result") is True,
           "A successful actual SAVE boundary is required")
    _check(live_snapshot == boundary.get("graph_snapshot"), "Graph changed after SAVE/export")
    _check(re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is not None,
           "The actually inspected image digest is required")
    catalog = _catalog(live_snapshot.get("schema_version"))
    _check(live_snapshot.get("query_version") == catalog["query_version"], "Graph version mismatch")
    rdb = _read(Path(rdb_source), MAX_RDB_BYTES)
    _check(len(rdb) >= 9 and re.fullmatch(rb"REDIS[0-9]{4}", rdb[:9]) is not None,
           "Input is not a Redis-produced RDB header")
    backup_root = Path(backup_root).absolute()
    _private_directory(backup_root)
    checkpoint_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4())
    manifest = {"version": CHECKPOINT_VERSION, "checkpoint_id": checkpoint_id,
                "created_at": datetime.now(timezone.utc).isoformat(), "image_digest": image_digest,
                "save_boundary": boundary, "rdb_filename": "dump.rdb", "rdb_bytes": len(rdb),
                "rdb_sha256": hashlib.sha256(rdb).hexdigest(),
                "rpo": "All writes after this completed SAVE may be lost; no zero-loss/power-loss guarantee"}
    data = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()
    _check(len(data) <= MAX_MANIFEST_BYTES, "Checkpoint manifest exceeds size bound")
    temporary = Path(tempfile.mkdtemp(prefix=".checkpoint-", dir=backup_root))
    final = backup_root / checkpoint_id
    try:
        _write(temporary / "dump.rdb", rdb)
        _write(temporary / "manifest.json", data)
        _sync_directory(temporary)
        _check(not final.exists(), "Checkpoint already exists")
        os.rename(temporary, final)
        _sync_directory(backup_root)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {"checkpoint_dir": str(final), "checkpoint_id": checkpoint_id,
            "manifest_sha256": hashlib.sha256(data).hexdigest(), "rdb_sha256": manifest["rdb_sha256"],
            "graph_sha256": live_snapshot["graph_sha256"], "status": "CHECKPOINT_PUBLISHED"}


def verify_checkpoint(checkpoint: Path, expected_manifest_sha256: str) -> dict:
    expected = _sha_pin(expected_manifest_sha256)
    checkpoint = Path(checkpoint).absolute()
    _private_directory(checkpoint)
    _check({path.name for path in checkpoint.iterdir()} == {"manifest.json", "dump.rdb"},
           "Checkpoint has an unexpected file set")
    _check(all(stat.S_IMODE((checkpoint / name).lstat().st_mode) == 0o600
               for name in ("manifest.json", "dump.rdb")), "Checkpoint files must be mode 0600")
    raw = _read(checkpoint / "manifest.json", MAX_MANIFEST_BYTES)
    _check(hashlib.sha256(raw).hexdigest() == expected, "Approved manifest pin mismatch")
    manifest = _json(raw)
    _check(manifest.get("version") == CHECKPOINT_VERSION and manifest.get("rdb_filename") == "dump.rdb",
           "Checkpoint format/version mismatch")
    _check(isinstance(manifest.get("image_digest"), str)
           and re.fullmatch(r"sha256:[0-9a-f]{64}", manifest["image_digest"]) is not None,
           "Checkpoint image digest is invalid")
    _check(manifest.get("checkpoint_id") == checkpoint.name, "Checkpoint directory identity mismatch")
    boundary = manifest.get("save_boundary")
    _check(isinstance(boundary, dict) and boundary.get("save_result") is True
           and boundary.get("writers_quiesced") is True, "Invalid SAVE boundary")
    snapshot = boundary.get("graph_snapshot")
    _check(isinstance(snapshot, dict), "Incompatible graph schema/query version")
    catalog = _catalog(snapshot.get("schema_version"))
    _check(snapshot.get("query_version") == catalog["query_version"], "Incompatible graph schema/query version")
    if "constraints" in snapshot:
        _validate_constraints(snapshot["constraints"], snapshot["schema_version"])
    _check(snapshot.get("graph_sha256") == digest({"nodes": snapshot.get("nodes"),
                                                   "edges": snapshot.get("edges")}),
           "Checkpoint graph inventory digest mismatch")
    rdb = _read(checkpoint / "dump.rdb", MAX_RDB_BYTES)
    _check(len(rdb) == manifest.get("rdb_bytes") and hashlib.sha256(rdb).hexdigest() == manifest.get("rdb_sha256"),
           "RDB content is corrupt or differs from the approved checkpoint")
    _check(re.fullmatch(rb"REDIS[0-9]{4}", rdb[:9]) is not None, "RDB header mismatch")
    return manifest


def stage_restore(checkpoint: Path, expected_manifest_sha256: str, destination: Path,
                  *, server_stopped: bool) -> dict:
    """Only a new private staging directory is allowed; never overwrite a live DB.

    The deployment controller must independently inspect its stopped, isolated
    target container before installation. This routine has no Docker/DB authority.
    """
    _check(server_stopped is True, "Restore requires an explicitly stopped target")
    manifest = verify_checkpoint(checkpoint, expected_manifest_sha256)
    destination = Path(destination).absolute()
    _parents(destination)
    _private_directory(destination.parent)
    _check(not destination.exists(), "Restore destination must be a new directory")
    temporary = Path(tempfile.mkdtemp(prefix=".restore-", dir=destination.parent))
    try:
        data = _read(Path(checkpoint) / "dump.rdb", MAX_RDB_BYTES)
        _check(len(data) == manifest["rdb_bytes"]
               and hashlib.sha256(data).hexdigest() == manifest["rdb_sha256"],
               "RDB changed between verification and restore publication")
        _write(temporary / "dump.rdb", data)
        _sync_directory(temporary)
        _check(not destination.exists(), "Restore destination already exists")
        os.rename(temporary, destination)
        _sync_directory(destination.parent)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {"status": "RESTORE_STAGED", "checkpoint_id": manifest["checkpoint_id"],
            "destination": str(destination), "rdb_sha256": manifest["rdb_sha256"],
            "scope": "COLD_NEW_TARGET_ONLY; SERVER_LOAD_AND_GRAPH_VERIFY_STILL_REQUIRED"}


def verify_restored(repo, checkpoint: Path, expected_manifest_sha256: str) -> dict:
    manifest = verify_checkpoint(checkpoint, expected_manifest_sha256)
    version = manifest["save_boundary"]["graph_snapshot"]["schema_version"]
    current = capture_graph(repo, schema_version=version)
    _check(current == manifest["save_boundary"]["graph_snapshot"],
           "Restored actual graph/relations/constraints/public paths differ from the checkpoint")
    return {"status": "RESTORED_GRAPH_VERIFIED", "checkpoint_id": manifest["checkpoint_id"],
            "graph_sha256": current["graph_sha256"], "node_count": current["node_count"],
            "edge_count": current["edge_count"], "experience_paths": len(current["public_paths"]),
            "client_identity": "NEW_SDK_CONNECTION; NOT_A_CODEX_SESSION",
            "schema_version": version, "migration_status": "NOT_AUTOMATIC; VERIFY_OLD_THEN_EXPLICITLY_MIGRATE",
            "scope": "ACTUAL_GRAPH_EQUALITY; DB_LOAD_ORIGIN_REQUIRES_DEPLOYMENT_CONTROLLER_EVIDENCE"}
