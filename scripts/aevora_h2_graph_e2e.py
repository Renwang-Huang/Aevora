#!/usr/bin/env python3
"""Trusted H2-G3 historical corpus, read-only governance review and live feedback.

No Codex/model invocation, fallback graph, fabricated Outcome or public admin
API. Raw graph commands/results are maintainer-only evidence. The graph key and
endpoint are pinned so these operations cannot mutate the G0/G1 corpus or H1.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
GRAPH_NAME = "aevora_h2_g3_reviewed"
PORT = "17679"
VERSION = "aevora.h2-g3-graph-evidence/1.0"
MAX_JSON_BYTES = 32 * 1024**2
MAX_RAW_BYTES = 128 * 1024**2


class EvidenceRejected(ValueError):
    """No database or archive action is authorized by this input."""


def require(condition, message):
    if not condition:
        raise EvidenceRejected(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ordinary_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink path components refused")
    return path


def read_json(path):
    # Reuse the checkpoint reader's bounded FIFO/link/owner/change checks and
    # duplicate/depth handling. These are trusted configuration/evidence files.
    from aevora.checkpoint import _read, _json
    return _json(_read(ordinary_path(path), MAX_JSON_BYTES))


def write(path, value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    require(len(encoded) <= MAX_JSON_BYTES, "Evidence JSON exceeds its archive bound")
    path = ordinary_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def endpoint(environment):
    require(environment.get("AEVORA_FALKORDB_HOST", "127.0.0.1") == "127.0.0.1",
            "G3 review requires the isolated loopback endpoint")
    require(environment.get("AEVORA_FALKORDB_PORT") == PORT, "G3 review requires isolated H2 port17679")
    require(environment.get("AEVORA_FALKORDB_GRAPH") == GRAPH_NAME,
            "G3 review requires its dedicated graph key; G0/G1/H1 keys are forbidden")


def raw_value(value):
    """Preserve official Redis scalar/array response types without stringifying."""
    if isinstance(value, bytes):
        return {"redis_type": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, (list, tuple)):
        return [raw_value(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: raw_value(item) for key, item in value.items()}
    raise EvidenceRejected("Unrecognized official Redis response type")


class RawCommands:
    """Observe this one SDK Graph object's actual execute_command responses.

    Instance scope includes SDK CALL db.constraints()/schema queries. The
    connection's AUTH/discovery methods are not intercepted or archived.
    """
    def __init__(self, output):
        self.path = output / "trusted_graph_commands.jsonl"
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.stream = os.fdopen(descriptor, "wb")
        self.count, self.bytes = 0, 0
        self.graph, self.original = None, None

    def append(self, event):
        event = {"sequence": self.count + 1, "source": "ACTUAL_OFFICIAL_FALKORDB_SDK_RESPONSE", **event}
        raw = json.dumps(raw_value(event), ensure_ascii=False, sort_keys=True, allow_nan=False).encode() + b"\n"
        require(self.bytes + len(raw) <= MAX_RAW_BYTES, "Raw graph evidence byte budget exhausted")
        self.stream.write(raw)
        self.stream.flush()
        self.count += 1
        self.bytes += len(raw)

    def attach(self, repository):
        self.graph = repository._graph
        self.original = self.graph.execute_command

        def observed(*args, **kwargs):
            require(args and isinstance(args[0], str) and args[0].upper().startswith("GRAPH."),
                    "Only this graph's SDK command may enter the raw journal")
            started, start_ns = now(), time.monotonic_ns()
            event = {"graph_name": self.graph.name, "command": list(args), "options": kwargs,
                     "started_at": started, "start_monotonic_ns": start_ns,
                     "disclosure": "TRUSTED_HOST_ONLY; NOT_PARTICIPANT_OR_PUBLIC_EXPORT"}
            try:
                result = self.original(*args, **kwargs)
                event.update(status="RETURNED", actual_response=result)
                return result
            except Exception as error:
                # SDK exception messages may contain query payloads or
                # connection data; only their actual class is recorded.
                event.update(status="ERROR", error_type=type(error).__name__)
                raise
            finally:
                event.update(ended_at=now(), end_monotonic_ns=time.monotonic_ns())
                self.append(event)

        self.graph.execute_command = observed

    def exists(self, repository):
        result = repository._client.connection.exists(GRAPH_NAME)
        require(type(result) is int and result in (0, 1), "Unexpected dedicated key existence result")
        self.append({"command": ["EXISTS", GRAPH_NAME], "status": "RETURNED", "actual_response": result,
                     "graph_name": GRAPH_NAME, "observed_at": now()})
        return result == 1

    def close(self):
        if self.graph is not None:
            self.graph.execute_command = self.original
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


def public_manifest(path):
    from benchmark.manifest import ScenarioManifest
    from dataclasses import asdict
    value = read_json(path)
    return asdict(ScenarioManifest.from_dict(value))


def comparison_rows(resolved):
    """Explain actual returned rows; this function does not decide applicability."""
    require(isinstance(resolved, dict) and resolved.get("status") == "AVAILABLE"
            and isinstance(resolved.get("candidates"), list), "Resolver evidence is unavailable")
    rows = []
    for candidate in resolved["candidates"]:
        require(isinstance(candidate, dict) and candidate.get("decision") in {"APPLY", "VERIFY", "ABSTAIN"},
                "Unexpected real resolver classification")
        bundle = candidate.get("evidence_bundle", {})
        experience = bundle.get("experience")
        require(isinstance(experience, dict) and experience.get("id") == candidate.get("experience_id"),
                "Comparison row lacks its actual graph text origin")
        rows.append({"experience_id": candidate["experience_id"], "raw_public_experience": experience,
            "when_decision": candidate["decision"], "reason": candidate.get("reason"),
            "principle_decision": candidate.get("principle_decision", "UNAVAILABLE"),
            "whole_operation_coverage": candidate.get("current_operation_coverage", "UNAVAILABLE"),
            "matched_premises": candidate.get("matched_premises", []),
            "conflicting_premises": candidate.get("conflicting_premises", []),
            "missing_material_premises": candidate.get("missing_material_premises", []),
            "support_paths": bundle.get("support_paths", []),
            "counterexample_paths": bundle.get("counterexample_paths", []),
            "observed_outcome_paths": bundle.get("observed_outcome_paths", []),
            "retrieval_snapshot_sha256": candidate.get("retrieval_snapshot_sha256", "UNAVAILABLE"),
            "governance_evidence_sha256": candidate.get("governance_evidence_sha256", "UNAVAILABLE"),
            "attribution": "UNKNOWN", "causal_benefit": "UNVERIFIED",
            "text_only_comparator": "SAME_ACTUAL_PUBLIC_EXPERIENCE_TEXT; NO_FABRICATED_POLICY_OR_AGENT_RUN"})
    return rows


def source_epoch():
    files = {str(path.relative_to(ROOT)): sha(path)
             for path in sorted((ROOT / "aevora_core/src/aevora").glob("*.py"))}
    for name in ("scripts/aevora_h2_graph_e2e.py", "integrations/aevora.py"):
        files[name] = sha(ROOT / name)
    process = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
    require(process.returncode == 0, "Actual source commit could not be read")
    return {"version": VERSION, "git_head": process.stdout.strip(), "files_sha256": files,
        "environment_versions": {"python": sys.version, "sqlite": __import__("sqlite3").sqlite_version,
            **{package: importlib.metadata.version(package) for package in ("aevora-core", "falkordb", "redis", "mcp")}},
        "classification": "CURRENT_H2_SOURCE; NOT_H1_LIVE_CODE", "recorded_at": now()}


def anchor_from_arguments(args):
    from aevora.orderflow_outcome_bridge import TrustAnchor
    required = ("archive_root", "manifest_sha256", "source_archive_root", "source_manifest_sha256", "run_id")
    require(all(getattr(args, field, None) is not None for field in required),
            "Actual sealed Run and frozen source pins are required for ingestion")
    return TrustAnchor(ordinary_path(args.archive_root), args.manifest_sha256,
        {args.report_reference: args.run_id}, profile="current_live",
        manifest_relative_path=args.manifest_relative_path,
        source_archive_root=ordinary_path(args.source_archive_root),
        source_manifest_sha256=args.source_manifest_sha256,
        source_manifest_relative_path=args.source_manifest_relative_path,
        source_snapshot_relative_path=args.source_snapshot_relative_path)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("operation", choices=("seed", "compare", "fingerprint", "ingest"))
    result.add_argument("output", type=Path, help="New owner-only evidence directory; never reused")
    result.add_argument("--writers-quiesced", action="store_true", required=True,
                        help="Trusted caller owns the graph writer lifecycle; no competing live session")
    result.add_argument("--historical-archive", type=Path)
    result.add_argument("--corpus-manifest", type=Path)
    result.add_argument("--corpus-manifest-sha256")
    result.add_argument("--public-manifest", type=Path, default=ROOT / "benchmark/scenarios/D-V02/public.json")
    result.add_argument("--archive-root", type=Path)
    result.add_argument("--manifest-sha256")
    result.add_argument("--manifest-relative-path", default="run_evidence_manifest.json")
    result.add_argument("--source-archive-root", type=Path)
    result.add_argument("--source-manifest-sha256")
    result.add_argument("--source-manifest-relative-path", default="SOURCE_TRUST_MANIFEST.json")
    result.add_argument("--source-snapshot-relative-path", default="frozen_source_snapshot")
    result.add_argument("--report-reference", default="evaluation_report.json")
    result.add_argument("--run-id")
    result.add_argument("--verify-idempotence", action="store_true")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    endpoint(os.environ)
    output = ordinary_path(args.output)
    protected = [ordinary_path(path) for path in
                 (args.historical_archive, args.archive_root, args.source_archive_root) if path is not None]
    require(all(not output.is_relative_to(path) and not path.is_relative_to(output) for path in protected),
            "New evidence must be separate from protected source and Run archives")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    require(stat.S_IMODE(output.stat().st_mode) == 0o700, "Evidence directory must be private")
    epoch = source_epoch()
    write(output / "SOURCE_EPOCH.json", epoch)
    journal = RawCommands(output)
    repository = None
    code, failure, pending_gate = 2, None, None
    try:
        from aevora.graph_repository import GraphRepository
        from aevora.checkpoint import capture_graph
        repository = GraphRepository.from_environment()
        journal.attach(repository)
        exists = journal.exists(repository)
        if args.operation == "seed":
            require(args.historical_archive is not None, "Seed requires the exact authorized historical archive")
            require(not exists, "Seed requires a new graph key; existing state is never overwritten or deleted")
            from aevora.historical_import import import_verified_history, ATOMIC_ID, LOCK_ID
            from aevora.orderflow_outcome_bridge import verify_historical_seeds, public_outcome_summary
            verified = verify_historical_seeds(args.historical_archive)
            write(output / "HISTORICAL_VERIFICATION.json", verified)
            repository.initialize()
            imported = import_verified_history(repository, args.historical_archive)
            snapshot = capture_graph(repository)
            require(repository.experience_ids() == sorted((ATOMIC_ID, LOCK_ID)), "Imported corpus identity differs")
            actual_outcomes = repository.query("MATCH (o:VerifiedOutcome) RETURN o.id ORDER BY o.id")
            require([row[0] for row in actual_outcomes] == sorted(row["id"] for row in verified["outcomes"].values()),
                    "Corpus has outcomes outside the four sealed historical strategy replays")
            manifest = {"status": "PASS", "scope": "ACTUAL_VERIFIED_HISTORICAL_SEED; NOT_NATIVE_OR_QUERY_GATE",
                "deployment_source_type": "maintainer_seed",
                "corpus_classification": "HISTORICAL_CONTROLLED_REPLAY; NOT_NEW_AGENT_SESSION",
                "source_archive_manifest_sha256": next(iter(verified["outcomes"].values()))["source_manifest_sha256"],
                "source_archive": str(ordinary_path(args.historical_archive)),
                "historical_outcomes": {key: public_outcome_summary(value) for key, value in verified["outcomes"].items()},
                "origin_policy": "PRESERVE_TRUE_NATURAL_ORIGIN; EACH_REPLAY_IS_EXPLICITLY_HISTORICAL",
                "new_task_gold_or_reference": "NOT_IMPORTED", "g1_synthetic_fixtures": "NOT_IMPORTED",
                "participant_projection": "EXISTING_CORE_PUBLIC_ALLOWLIST; RAW_PAYLOADS_REMAIN_HOST_ONLY",
                "import_receipt": imported, "snapshot": snapshot,
                "causal_benefit": "UNVERIFIED", "attribution": "UNKNOWN"}
            pending_gate = (output / "CORPUS_MANIFEST.json", manifest)
        else:
            require(exists, "Dedicated corpus graph is absent; no fallback graph is allowed")
            before = capture_graph(repository)
            write(output / "GRAPH_BEFORE.json", before)
            if args.operation == "compare":
                from aevora.experience_resolver import ExperienceResolver
                from integrations.aevora import public_runtime_context
                require(args.corpus_manifest is not None and isinstance(args.corpus_manifest_sha256, str)
                        and re.fullmatch(r"[0-9a-f]{64}", args.corpus_manifest_sha256) is not None,
                        "Read-only review requires the approved historical corpus manifest pin")
                corpus = read_json(args.corpus_manifest)
                require(sha(args.corpus_manifest) == args.corpus_manifest_sha256
                        and corpus.get("status") == "PASS"
                        and corpus.get("deployment_source_type") == "maintainer_seed"
                        and corpus.get("corpus_classification") == "HISTORICAL_CONTROLLED_REPLAY; NOT_NEW_AGENT_SESSION",
                        "Historical corpus receipt differs from its approved pin")
                initial = corpus.get("snapshot", {})
                require(initial.get("graph_name") == GRAPH_NAME
                        and all(row in before["nodes"] for row in initial.get("nodes", []))
                        and all(row in before["edges"] for row in initial.get("edges", []))
                        and bool(initial.get("nodes")) and bool(initial.get("edges")),
                        "Initial historical corpus identities changed or disappeared")
                manifest = public_manifest(args.public_manifest)
                context = public_runtime_context(manifest)
                actual = ExperienceResolver(repository).resolve(context, persist_snapshots=False)
                write(output / "ACTUAL_RESOLVER_OUTPUT.json", actual)
                write(output / "FINITE_TEXT_GOVERNANCE_COMPARISON.json", {
                    "classification": "READ_ONLY_REAL_GRAPH_FINITE_REVIEW; NOT_STATISTICAL_ABLATION",
                    "public_manifest_sha256": sha(args.public_manifest), "public_context": context,
                    "rows": comparison_rows(actual), "graph_ablation": "NOT_PERFORMED_IN_REVIEWED_LIVE_CORPUS",
                    "new_agent_session": "NOT_RUN_BY_THIS_SCRIPT", "governance_causal_increment": "UNVERIFIED"})
            elif args.operation == "ingest":
                from aevora.orderflow_outcome_bridge import verify_outcome, public_outcome_summary
                from aevora.feedback import ingest_outcome
                anchor = anchor_from_arguments(args)
                verified = verify_outcome(anchor, args.report_reference)
                require(verified["source_type"] == "current_live", "Only sealed actual current-live evidence is ingested")
                write(output / "VERIFIED_ENGINEERING_OUTCOME.json", verified)
                first = ingest_outcome(repository, anchor, args.report_reference)
                write(output / "TRUSTED_INGEST_RECEIPT.json", first)
                if args.verify_idempotence:
                    prior = capture_graph(repository)
                    second = ingest_outcome(repository, anchor, args.report_reference)
                    after_repeat = capture_graph(repository)
                    require(first == second and prior == after_repeat, "Identical trusted feedback replay changed graph facts")
                    write(output / "IDEMPOTENT_INGEST_RECEIPT.json", {"actual_second_receipt": second,
                        "snapshot_before": prior, "snapshot_after": after_repeat, "unchanged": True})
                write(output / "PUBLIC_OUTCOME_SUMMARY.json", public_outcome_summary(verified))
            after = capture_graph(repository)
            write(output / "GRAPH_AFTER.json", after)
            if args.operation in {"compare", "fingerprint"}:
                require(before == after, "Read-only governance review changed the graph or had concurrent writers")
            if args.operation == "compare":
                pending_gate = (output / "CORPUS_REVIEW_GATE.json", {"status": "PASS",
                    "scope": "ACTUAL_HISTORICAL_SEED_PLUS_READ_ONLY_CURRENT_ENGINE_REVIEW; NO_MODEL",
                    "corpus_manifest_sha256": args.corpus_manifest_sha256,
                    "public_manifest_sha256": sha(args.public_manifest), "graph_sha256": after["graph_sha256"],
                    "resolver_output_sha256": sha(output / "ACTUAL_RESOLVER_OUTPUT.json"),
                    "comparison_sha256": sha(output / "FINITE_TEXT_GOVERNANCE_COMPARISON.json"),
                    "read_only_state_unchanged": True, "current_operation_context": context,
                    "native_challenge": "NOT_RUN_BY_THIS_SCRIPT", "causal_benefit": "UNVERIFIED"})
            write(output / "GRAPH_CHANGE.json", {"operation": args.operation,
                "before_sha256": before["graph_sha256"], "after_sha256": after["graph_sha256"],
                "unchanged": before == after, "new_nodes": after["node_count"] - before["node_count"],
                "new_edges": after["edge_count"] - before["edge_count"],
                "consistency_scope": "TRUSTED_WRITERS_QUIESCED; MULTIQUERY_STATE_CHECK; NOT_ADMIN_ABA_FENCE"})
        require(source_epoch()["files_sha256"] == epoch["files_sha256"], "Source changed during graph operation")
        code = 0
    except Exception as error:
        failure = {"status": "ERROR", "error_type": type(error).__name__,
                   "message_policy": "TYPE_ONLY; NO_SDK_CONNECTION_OR_CREDENTIAL_CONTENT"}
        write(output / "OPERATION_ERROR.json", failure)
    finally:
        cleanup_errors = []
        try:
            journal.close()
        except Exception as error:
            cleanup_errors.append(type(error).__name__)
        try:
            if repository is not None:
                repository.close()
        except Exception as error:
            cleanup_errors.append(type(error).__name__)
        if cleanup_errors:
            code = 2
            write(output / "CLEANUP_ERROR.json", {"status": "ERROR", "error_types": cleanup_errors})
        if code == 0 and pending_gate is not None:
            try:
                write(*pending_gate)
            except Exception as error:
                code = 2
                write(output / "GATE_PUBLICATION_ERROR.json", {"status": "ERROR", "error_type": type(error).__name__})
        write(output / "OPERATION_RECEIPT.json", {"version": VERSION, "operation": args.operation,
            "graph_name": GRAPH_NAME, "port": int(PORT), "exit_code": code, "error": failure,
            "finished_at": now(), "raw_command_count": journal.count, "raw_bytes": journal.bytes,
            "raw_sha256": sha(journal.path), "source_epoch_sha256": sha(output / "SOURCE_EPOCH.json"),
            "disclosure": "TRUSTED_HOST_FULL_EVIDENCE; NOT_PARTICIPANT_DATA",
            "scope": "ACTUAL_DATABASE_OPERATION; NO_MODEL_OR_CODEX_SESSION_STARTED"})
    print(json.dumps({"operation": args.operation, "exit_code": code,
                      "receipt_sha256": sha(output / "OPERATION_RECEIPT.json")}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
