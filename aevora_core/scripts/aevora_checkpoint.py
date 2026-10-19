#!/usr/bin/env python3
"""Trusted checkpoint CLI; it never accepts a Participant verdict or password argv."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from aevora.checkpoint import (CheckpointRejected, capture_graph, save_boundary,
                              publish_checkpoint, verify_checkpoint, stage_restore,
                              verify_restored)
from aevora.graph_repository import GraphRepository
from aevora.models import GraphError, digest


def write(path: Path, value: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["save", "snapshot", "publish", "verify", "stage", "verify-restored"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--writers-quiesced", action="store_true")
    parser.add_argument("--server-stopped", action="store_true")
    parser.add_argument("--rdb-source", type=Path)
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--save-boundary", type=Path)
    parser.add_argument("--save-boundary-sha256")
    parser.add_argument("--image-digest")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    repo = None
    try:
        if args.operation in {"save", "snapshot", "publish", "verify-restored"}:
            repo = GraphRepository.from_environment()
        if args.operation == "save":
            result = save_boundary(repo, writers_quiesced=args.writers_quiesced)
        elif args.operation == "snapshot":
            result = {"status": "ACTUAL_GRAPH_SNAPSHOT", "snapshot": capture_graph(repo)}
        elif args.operation == "publish":
            from aevora.checkpoint import _read, _json, MAX_MANIFEST_BYTES, _sha_pin
            raw = _read(args.save_boundary, MAX_MANIFEST_BYTES)
            if hashlib.sha256(raw).hexdigest() != _sha_pin(args.save_boundary_sha256):
                raise CheckpointRejected("SAVE boundary pin mismatch")
            result = publish_checkpoint(args.rdb_source, args.backup_root, _json(raw), capture_graph(repo),
                image_digest=args.image_digest, writers_quiesced=args.writers_quiesced)
        elif args.operation == "verify":
            manifest = verify_checkpoint(args.checkpoint, args.manifest_sha256)
            result = {"status": "CHECKPOINT_INTEGRITY_VERIFIED", "checkpoint_id": manifest["checkpoint_id"],
                      "rdb_sha256": manifest["rdb_sha256"]}
        elif args.operation == "stage":
            result = stage_restore(args.checkpoint, args.manifest_sha256, args.destination,
                                   server_stopped=args.server_stopped)
        else:
            result = verify_restored(repo, args.checkpoint, args.manifest_sha256)
        write(args.output, result)
        print(json.dumps({"operation": args.operation, "status": result.get("status", "SAVE_COMPLETE"),
                          "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
        return 0
    except (CheckpointRejected, GraphError, OSError, ValueError, TypeError) as error:
        result = {"operation": args.operation, "status": "REJECTED", "error_type": type(error).__name__,
                  "error": str(error) if isinstance(error, CheckpointRejected) else "Operation unavailable"}
        if not args.output.exists():
            write(args.output, result)
        print(json.dumps(result))
        return 2
    finally:
        if repo is not None:
            repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
