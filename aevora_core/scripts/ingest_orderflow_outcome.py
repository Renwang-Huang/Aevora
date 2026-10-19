#!/usr/bin/env python3
"""Maintainer-only current-live OrderFlow ingestion with an immutable receipt.

No caller verdict, already-minted Outcome or Participant tool input is accepted.
The two SHA256 pins must be approved by the trusted Runner/maintainer outside
the Participant. This command does not infer adoption from a passing outcome.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from aevora.feedback import ingest_outcome
from aevora.graph_repository import GraphRepository
from aevora.models import GraphError, GraphUnavailable, ImmutableConflict, InvalidRecord, digest
from aevora.orderflow_outcome_bridge import TrustAnchor, OutcomeVerificationError, _Archive, canonical_bytes


def _sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("Expected an approved lowercase SHA256")
    return value


def _uuid(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value):
        raise argparse.ArgumentTypeError("Expected the exact authorized Run UUID")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--run-dir", type=Path, required=True)
    result.add_argument("--run-id", type=_uuid, required=True)
    result.add_argument("--run-seal-sha256", type=_sha, required=True)
    result.add_argument("--report-reference", choices=["evaluation_report.json"], default="evaluation_report.json")
    result.add_argument("--source-archive", type=Path, required=True)
    result.add_argument("--source-manifest-sha256", type=_sha, required=True)
    result.add_argument("--source-snapshot-relative-path", default="frozen_source_snapshot")
    result.add_argument("--source-manifest-relative-path", default="EVIDENCE_MANIFEST.json")
    result.add_argument("--experience-id", action="append", default=None,
                        help="Optional authorized selection; each ID requires an actual same-Run Query edge")
    result.add_argument("--output", type=Path, required=True,
                        help="New receipt file in an existing trusted directory, outside the sealed Run/source snapshot")
    return result


def _open_receipt(args) -> int:
    output = args.output.absolute()
    run = args.run_dir.absolute()
    snapshot = args.source_archive.absolute() / args.source_snapshot_relative_path
    for protected in (run, snapshot):
        if output == protected or protected in output.parents:
            raise InvalidRecord("Receipt must be outside sealed Run and frozen source snapshot")
    if output.name in {"", ".", ".."}:
        raise InvalidRecord("Receipt must be a new ordinary file")
    # Descriptor-based parent traversal refuses any symlink; O_EXCL prevents
    # overwriting earlier results. No writable DB credential enters this file.
    directory = _Archive(output.parent)
    try:
        return os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       0o600, dir_fd=directory.fd)
    finally:
        directory.close()


def _conflicts(repo) -> list[str]:
    return [row[0] for row in repo.query("MATCH (a:AuditEvent) WHERE a.id STARTS WITH 'conflict:' "
                                        "RETURN a.id ORDER BY a.id LIMIT 1000")]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        anchor = TrustAnchor(args.run_dir, args.run_seal_sha256,
            {args.report_reference: args.run_id}, profile="current_live",
            manifest_relative_path="run_evidence_manifest.json",
            source_archive_root=args.source_archive,
            source_manifest_sha256=args.source_manifest_sha256,
            source_manifest_relative_path=args.source_manifest_relative_path,
            source_snapshot_relative_path=args.source_snapshot_relative_path)
        if anchor.archive_root.name != args.run_id:
            raise InvalidRecord("Run directory identity differs from authorized Run")
        receipt_fd = _open_receipt(args)
    except (OutcomeVerificationError, InvalidRecord, OSError) as error:
        print(json.dumps({"status": "PRECONDITION_REJECTED", "error_type": type(error).__name__}))
        return 2

    started = datetime.now(timezone.utc).isoformat()
    receipt = {"schema_version": "aevora.trusted_ingestion_receipt/1.0", "run_id": args.run_id,
        "started_at": started, "profile": "current_live", "run_seal_sha256": args.run_seal_sha256,
        "source_manifest_sha256": args.source_manifest_sha256, "report_reference": args.report_reference,
        "authority": "TRUSTED_HOST_PINNED_ARCHIVES", "attribution": "UNKNOWN",
        "adoption": "UNVERIFIED", "causal_claim": "NONE", "status": "NOT_COMPLETED"}
    repo = None
    existing_digest = None
    before_conflicts: list[str] = []
    code = 0
    try:
        repo = GraphRepository.from_environment()
        repo.initialize()
        receipt["before_graph"] = repo.state_fingerprint()
        original = repo.get_node("VerifiedOutcome", "orderflow:" + args.run_id)
        existing_digest = digest(original) if original is not None else None
        before_conflicts = _conflicts(repo)
        first = ingest_outcome(repo, anchor, args.report_reference, experience_ids=args.experience_id)
        after_first = repo.state_fingerprint()
        repeated = ingest_outcome(repo, anchor, args.report_reference, experience_ids=args.experience_id)
        after_repeat = repo.state_fingerprint()
        identical = first == repeated and after_first == after_repeat
        receipt.update({"status": "INGESTED" if identical else "IDEMPOTENCE_FAILED",
            "ingestion": first, "after_graph": after_first, "repeat_graph": after_repeat,
            "identical_repeat_receipt": first == repeated, "idempotent": identical})
        code = 0 if identical else 5
    except ImmutableConflict as error:
        receipt.update(status="IMMUTABLE_CONFLICT", error_type=type(error).__name__)
        code = 3
    except OutcomeVerificationError as error:
        receipt.update(status="OUTCOME_VERIFICATION_REJECTED", error_type=type(error).__name__)
        code = 2
    except InvalidRecord as error:
        receipt.update(status="TRUST_CONTRACT_REJECTED", error_type=type(error).__name__)
        code = 2
    except GraphUnavailable as error:
        receipt.update(status="DATABASE_UNAVAILABLE", error_type=type(error).__name__)
        code = 4
    except GraphError as error:
        receipt.update(status="DATABASE_ERROR", error_type=type(error).__name__)
        code = 4
    except Exception as error:
        receipt.update(status="INTERNAL_ERROR", error_type=type(error).__name__)
        code = 5
    finally:
        if repo is not None:
            try:
                receipt["final_graph"] = repo.state_fingerprint()
                final = repo.get_node("VerifiedOutcome", "orderflow:" + args.run_id)
                final_digest = digest(final) if final is not None else None
                receipt["original_outcome_preserved"] = (final_digest == existing_digest) if existing_digest else "NOT_APPLICABLE"
                receipt["new_conflict_audit_ids"] = sorted(set(_conflicts(repo)) - set(before_conflicts))
            except GraphError as error:
                receipt["final_graph_observation"] = "UNAVAILABLE"
                receipt["final_graph_error_type"] = type(error).__name__
            repo.close()
        receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
        receipt["exit_code"] = code
        data = canonical_bytes(receipt) + b"\n"
        try:
            with os.fdopen(receipt_fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            print(json.dumps({"status": "RECEIPT_WRITE_FAILED", "error_type": type(error).__name__}))
            return 5
    print(json.dumps({"status": receipt["status"], "run_id": args.run_id, "exit_code": code,
                      "receipt": str(args.output.absolute()), "receipt_sha256": __import__("hashlib").sha256(data).hexdigest()}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
