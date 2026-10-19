"""Real filesystem integrity contracts plus real FalkorDB snapshot validation.

The tiny REDIS-header bytes in filesystem cases are synthetic file fixtures,
never loaded as a database and never reported as successful graph recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

import pytest

from aevora.checkpoint import (CHECKPOINT_VERSION, CheckpointRejected, capture_graph,
                              publish_checkpoint, save_boundary, stage_restore,
                              verify_checkpoint, verify_restored)
from aevora.graph_repository import GraphRepository
from aevora.models import SCHEMA_VERSION, QUERY_VERSION, digest

IMAGE = "sha256:" + "a" * 64


def filesystem_fixture(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    source = root / "exported.rdb"
    source.write_bytes(b"REDIS0011synthetic-filesystem-fixture-not-a-loaded-database")
    snapshot = {"graph_name": "synthetic_filesystem_fixture", "schema_version": SCHEMA_VERSION,
                "query_version": QUERY_VERSION, "nodes": [], "edges": [],
                "graph_sha256": digest({"nodes": [], "edges": []})}
    boundary = {"version": CHECKPOINT_VERSION, "writers_quiesced": True, "save_result": True,
                "graph_snapshot": snapshot, "source_type": "synthetic_or_test_fixture"}
    published = publish_checkpoint(source, root, boundary, snapshot, image_digest=IMAGE,
                                   writers_quiesced=True)
    return root, source, boundary, Path(published["checkpoint_dir"]), published


def rewrite_manifest(path, update):
    manifest = json.loads((path / "manifest.json").read_text())
    update(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest))
    return hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest()


def test_publish_and_stage_are_private_and_do_not_claim_database_recovery(tmp_path):
    root, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    assert checkpoint.stat().st_mode & 0o777 == 0o700
    assert {p.name for p in checkpoint.iterdir()} == {"manifest.json", "dump.rdb"}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in checkpoint.iterdir())
    manifest = verify_checkpoint(checkpoint, receipt["manifest_sha256"])
    assert "may be lost" in manifest["rpo"]
    staged = stage_restore(checkpoint, receipt["manifest_sha256"], root / "cold", server_stopped=True)
    assert staged["status"] == "RESTORE_STAGED" and "STILL_REQUIRED" in staged["scope"]
    assert (root / "cold/dump.rdb").read_bytes() == (checkpoint / "dump.rdb").read_bytes()


@pytest.mark.parametrize("pin", [None, "", "A" * 64, "f" * 63, "../manifest.json", "f" * 64])
def test_missing_invalid_or_unapproved_manifest_pin_is_rejected(tmp_path, pin):
    _, _, _, checkpoint, _ = filesystem_fixture(tmp_path)
    with pytest.raises(CheckpointRejected):
        verify_checkpoint(checkpoint, pin)


@pytest.mark.parametrize("filename", ["dump.rdb", "manifest.json"])
def test_corrupt_file_cannot_stage_restore(tmp_path, filename):
    root, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    path = checkpoint / filename
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    with pytest.raises(CheckpointRejected):
        stage_restore(checkpoint, receipt["manifest_sha256"], root / "cold", server_stopped=True)
    assert not (root / "cold").exists()


@pytest.mark.parametrize("filename", ["dump.rdb", "manifest.json"])
@pytest.mark.parametrize("link_kind", ["symbolic", "hard"])
def test_linked_checkpoint_files_are_rejected(tmp_path, filename, link_kind):
    root, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    path = checkpoint / filename
    moved = root / ("moved-" + filename)
    path.rename(moved)
    if link_kind == "symbolic":
        path.symlink_to(moved)
    else:
        os.link(moved, path)
    with pytest.raises(CheckpointRejected):
        verify_checkpoint(checkpoint, receipt["manifest_sha256"])


def test_extra_file_or_public_permissions_are_rejected(tmp_path):
    _, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    (checkpoint / "unapproved").write_text("no")
    with pytest.raises(CheckpointRejected, match="file set"):
        verify_checkpoint(checkpoint, receipt["manifest_sha256"])
    (checkpoint / "unapproved").unlink()
    checkpoint.chmod(0o755)
    with pytest.raises(CheckpointRejected, match="0700"):
        verify_checkpoint(checkpoint, receipt["manifest_sha256"])


@pytest.mark.parametrize("filename", ["dump.rdb", "manifest.json"])
def test_public_checkpoint_file_permissions_are_rejected(tmp_path, filename):
    _, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    (checkpoint / filename).chmod(0o644)
    with pytest.raises(CheckpointRejected, match="0600"):
        verify_checkpoint(checkpoint, receipt["manifest_sha256"])


@pytest.mark.parametrize("field,value", [("version", "aevora.rdb_checkpoint/999"),
                                       ("checkpoint_id", "another-id"), ("rdb_filename", "../dump.rdb")])
def test_pinned_but_incompatible_manifest_is_rejected(tmp_path, field, value):
    _, _, _, checkpoint, _ = filesystem_fixture(tmp_path)
    pin = rewrite_manifest(checkpoint, lambda m: m.update({field: value}))
    with pytest.raises(CheckpointRejected):
        verify_checkpoint(checkpoint, pin)


def test_graph_inventory_hash_and_schema_are_checked(tmp_path):
    _, _, _, checkpoint, _ = filesystem_fixture(tmp_path)
    pin = rewrite_manifest(checkpoint, lambda m: m["save_boundary"]["graph_snapshot"].update({"graph_sha256": "0" * 64}))
    with pytest.raises(CheckpointRejected, match="inventory"):
        verify_checkpoint(checkpoint, pin)
    pin = rewrite_manifest(checkpoint, lambda m: m["save_boundary"]["graph_snapshot"].update({"schema_version": "incompatible"}))
    with pytest.raises(CheckpointRejected, match="Incompatible"):
        verify_checkpoint(checkpoint, pin)


def test_duplicate_json_key_cannot_be_approved(tmp_path):
    _, _, _, checkpoint, _ = filesystem_fixture(tmp_path)
    path = checkpoint / "manifest.json"
    path.write_text('{"version":"first", "version":"second"}')
    with pytest.raises(CheckpointRejected, match="Duplicate"):
        verify_checkpoint(checkpoint, hashlib.sha256(path.read_bytes()).hexdigest())


def test_restore_never_overwrites_existing_directory_or_live_target(tmp_path):
    root, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    target = root / "cold"
    target.mkdir(mode=0o700)
    (target / "untouched").write_text("original")
    with pytest.raises(CheckpointRejected, match="new directory"):
        stage_restore(checkpoint, receipt["manifest_sha256"], target, server_stopped=True)
    with pytest.raises(CheckpointRejected, match="stopped"):
        stage_restore(checkpoint, receipt["manifest_sha256"], root / "other", server_stopped=False)
    assert (target / "untouched").read_text() == "original" and not (root / "other").exists()


def test_publication_rejects_changed_graph_unquiesced_writers_and_bad_rdb(tmp_path):
    root, source, boundary, _, _ = filesystem_fixture(tmp_path)
    before = set(root.iterdir())
    for snapshot, quiesced in [({"different": True}, True), (boundary["graph_snapshot"], False)]:
        with pytest.raises(CheckpointRejected):
            publish_checkpoint(source, root, boundary, snapshot, image_digest=IMAGE, writers_quiesced=quiesced)
    source.write_bytes(b"not an rdb")
    with pytest.raises(CheckpointRejected, match="RDB header"):
        publish_checkpoint(source, root, boundary, boundary["graph_snapshot"], image_digest=IMAGE, writers_quiesced=True)
    assert set(root.iterdir()) == before


def test_symlink_parent_is_rejected(tmp_path):
    root, _, _, checkpoint, receipt = filesystem_fixture(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(CheckpointRejected, match="Symlink"):
        verify_checkpoint(alias / checkpoint.name, receipt["manifest_sha256"])


@pytest.fixture
def real_repo():
    previous = os.environ.get("AEVORA_FALKORDB_GRAPH")
    os.environ["AEVORA_FALKORDB_GRAPH"] = "aevora_checkpoint_test_" + uuid.uuid4().hex
    try:
        repository = GraphRepository.from_environment()
        repository.initialize()
    finally:
        if previous is None:
            os.environ.pop("AEVORA_FALKORDB_GRAPH", None)
        else:
            os.environ["AEVORA_FALKORDB_GRAPH"] = previous
    try:
        yield repository
    finally:
        repository._graph.delete()  # Only the UUID-named test graph.
        repository.close()


def test_real_graph_capture_checks_bytes_and_actual_save_boundary(real_repo):
    real_repo.put_node("Task", {"id": "task:real-checkpoint", "public_title": "Real snapshot fixture"})
    snapshot = capture_graph(real_repo)
    assert snapshot["node_count"] == 2 and snapshot["edge_count"] == 0
    assert any(row[1] == "task:real-checkpoint" for row in snapshot["nodes"])
    boundary = save_boundary(real_repo, writers_quiesced=True)
    assert boundary["graph_snapshot"] == snapshot and boundary["save_result"] is True
    assert boundary["redis_version"]
    with pytest.raises(CheckpointRejected, match="quiesced"):
        save_boundary(real_repo, writers_quiesced=False)


def test_real_graph_payload_corruption_is_independently_detected(real_repo):
    real_repo.query("CREATE (:Task {id:$id,payload_json:$payload,payload_sha256:$sha})",
                    {"id": "task:bad", "payload": '{"id":"task:bad"}', "sha": "f" * 64}, read_only=False)
    with pytest.raises(CheckpointRejected, match="stored identity/digest"):
        capture_graph(real_repo)


def test_current_source_version_cannot_replace_missing_actual_schema_marker(real_repo):
    real_repo.query("MATCH (s:Schema {id:$id}) DELETE s", {"id": SCHEMA_VERSION}, read_only=False)
    with pytest.raises(CheckpointRejected, match="schema marker"):
        capture_graph(real_repo)


def test_restore_must_match_actual_graph_not_just_manifest_json(tmp_path, real_repo):
    root, _, boundary, checkpoint, _ = filesystem_fixture(tmp_path)
    actual = capture_graph(real_repo)
    pin = rewrite_manifest(checkpoint, lambda m: m["save_boundary"].update({"graph_snapshot": actual}))
    verified = verify_restored(real_repo, checkpoint, pin)
    assert verified["status"] == "RESTORED_GRAPH_VERIFIED"
    assert verified["client_identity"] == "NEW_SDK_CONNECTION; NOT_A_CODEX_SESSION"
    real_repo.put_node("Task", {"id": "task:after-checkpoint", "public_title": "Tail change"})
    with pytest.raises(CheckpointRejected, match="differ"):
        verify_restored(real_repo, checkpoint, pin)
