#!/usr/bin/env python3
"""Finite real-graph necessity controls, on an owned copy of reviewed history.

The reviewed graph is read-only. One real material support edge is removed
only from a nonce-named official Graph.copy. No synthetic Outcome, model call,
Core patch, cached current answer or claim of statistical causal benefit.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import select
import socket
import socketserver
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.aevora_h2_graph_e2e import (
    GRAPH_NAME, RawCommands, endpoint, now, ordinary_path, public_manifest,
    read_json, require, sha, source_epoch, write,
)
from scripts.aevora_h2_graph_maintenance import paused_auto_save
from scripts.aevora_h2_security import Evidence, RPCClient, broker_case

VERSION = "aevora.h2-finite-graph-controls/1.0"


@contextmanager
def graph_environment(name):
    previous = os.environ["AEVORA_FALKORDB_GRAPH"]
    os.environ["AEVORA_FALKORDB_GRAPH"] = name
    try:
        yield
    finally:
        os.environ["AEVORA_FALKORDB_GRAPH"] = previous


class OwnedRelay:
    """Owned TCP transport to the known H2 DB; payloads are never archived.

    Reuses socketserver's bounded owner lifecycle. AUTH passes only in memory
    to the existing trusted DB. Evidence contains counts and socket state,
    never Redis payload bytes or credential values. Stopping leaves its socket
    owned until the negative requests finish, avoiding unknown-service probes.
    """
    def __init__(self):
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.pairs, self.handlers = set(), set()
        self.accepted = self.forwarded = 0
        relay = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                upstream = None
                thread = threading.current_thread()
                try:
                    upstream = socket.create_connection(("127.0.0.1", 17679), timeout=3)
                    for connection in (self.request, upstream):
                        connection.settimeout(2)
                    pair = (self.request, upstream)
                    with relay.lock:
                        relay.accepted += 1
                        relay.pairs.add(pair)
                        relay.handlers.add(thread)
                    while not relay.stopped.is_set():
                        readable, _, _ = select.select(pair, [], [], .05)
                        for source in readable:
                            data = source.recv(16384)
                            if not data:
                                return
                            target = upstream if source is self.request else self.request
                            target.sendall(data)
                            with relay.lock:
                                relay.forwarded += len(data)
                except OSError:
                    # Transport refusal/close is the actual fault under test;
                    # payloads and SDK exception text must never be journaled.
                    pass
                finally:
                    if upstream is not None:
                        with relay.lock:
                            relay.pairs.discard((self.request, upstream))
                            relay.handlers.discard(thread)
                        upstream.close()

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            block_on_close = False
            request_queue_size = 8

        self.server = Server(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
            kwargs={"poll_interval": .05}, name="aevora-owned-db-relay", daemon=True)
        self.thread.start()
        self.socket_closed = False

    def metadata(self):
        with self.lock:
            return {"owned_loopback_port": self.port, "known_upstream_port": 17679,
                    "accepted_connections": self.accepted, "forwarded_byte_count": self.forwarded,
                    "payload_bytes_archived": False, "active_pairs": len(self.pairs),
                    "active_handlers": len(self.handlers), "server_thread_stopped": not self.thread.is_alive(),
                    "listener_owned_until_close": not self.socket_closed,
                    "stopped": self.stopped.is_set()}

    def stop(self):
        self.stopped.set()
        self.server.shutdown()
        self.thread.join(2)
        # Hold the original socket, but refuse new connections on it.
        try:
            self.server.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        with self.lock:
            pairs = list(self.pairs)
            handlers = list(self.handlers)
        for pair in pairs:
            for connection in pair:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
        for handler in handlers:
            handler.join(2)
        require(not self.thread.is_alive() and not self.pairs and not self.handlers,
                "Owned relay transport cleanup was not completed")

    def close(self):
        self.stop()
        self.server.server_close()
        self.socket_closed = True


def unavailable(answer):
    return (isinstance(answer, dict) and answer.get("result", {}).get("isError") is True
            and "structuredContent" not in answer["result"]
            and "AEVORA_GRAPH_UNAVAILABLE" in json.dumps(answer["result"]))


def disconnected_controls(evidence, context, clone, experience_id):
    """Official MCP SDK errors at owned endpoints; no fallback answer."""
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        with broker_case(evidence, "graph_no_service", context=context,
                server_environment={"AEVORA_FALKORDB_PORT": str(port), "AEVORA_FALKORDB_GRAPH": clone}) as (broker, token, directory):
            client = RPCClient(broker, token, directory / "client_events.jsonl")
            try:
                client.initialize()
                answer = client.tool("resolve_experience", {"task_context": {}})
                write(directory / "ACTUAL_UNAVAILABLE_RESPONSE.json", answer)
                require(evidence.check("owned_no_service_is_error_no_cached_answer", unavailable(answer),
                    {"owned_bound_non_listening_port": port, "actual_response": answer},
                    scope="Actual official MCP SDK and Redis connection refusal; no unknown endpoint"),
                    "Unavailable graph returned a cached or available answer")
            finally:
                client.close()
    relay = OwnedRelay()
    try:
        with broker_case(evidence, "graph_real_disconnect", context=context,
                server_environment={"AEVORA_FALKORDB_PORT": str(relay.port), "AEVORA_FALKORDB_GRAPH": clone}) as (broker, token, directory):
            client = RPCClient(broker, token, directory / "client_events.jsonl")
            try:
                client.initialize()
                answer = client.tool("resolve_experience", {"task_context": {}})
                require(not answer["result"].get("isError") and answer["result"]["structuredContent"]["status"] == "AVAILABLE",
                        "Owned relay did not establish an actual successful graph query")
                actual = answer["result"]["structuredContent"]
                require(experience_id in {row["experience_id"] for row in actual["candidates"]},
                        "Actual connected graph did not return the selected experience")
                bundle = client.tool("build_evidence_bundle", {"experience_id": experience_id, "query_id": actual["query_id"]})
                require(not bundle["result"].get("isError") and bundle["result"]["structuredContent"]["status"] == "AVAILABLE",
                        "Connected official MCP could not read its actual snapshot bundle")
                write(directory / "CONNECTED_ACTUAL_RESOLVER.json", answer)
                write(directory / "CONNECTED_ACTUAL_BUNDLE.json", bundle)
                write(directory / "RELAY_BEFORE_DISCONNECT.json", relay.metadata())
                relay.stop()
                for tool, arguments in (("resolve_experience", {"task_context": {}}),
                        ("build_evidence_bundle", {"experience_id": experience_id, "query_id": actual["query_id"]})):
                    failed = client.tool(tool, arguments)
                    write(directory / (tool + "_ACTUAL_DISCONNECTED_RESPONSE.json"), failed)
                    require(evidence.check(tool + "_after_actual_disconnect_no_cached_answer", unavailable(failed),
                        {"actual_response": failed, "transport": relay.metadata()},
                        scope="Same actual initialized MCP SDK process; previously successful owned graph connection terminated"),
                        "Disconnected graph returned a cached or available answer")
            finally:
                client.close()
    finally:
        relay.close()
        write(evidence.output / "OWNED_RELAY_CLEANUP.json", relay.metadata())


def sources():
    epoch = source_epoch()
    for name in ("scripts/aevora_h2_graph_controls.py", "scripts/aevora_h2_graph_maintenance.py",
                 "scripts/aevora_h2_security.py", "benchmark/scenarios/D-V02/public.json"):
        epoch["files_sha256"][name] = sha(ROOT / name)
    from falkordb.graph import Graph
    sdk_path = Path(inspect.getsourcefile(Graph))
    epoch["official_sdk_graph_source"] = {"path": str(sdk_path), "sha256": sha(sdk_path)}
    epoch["version"] = VERSION
    return epoch


def run(args):
    endpoint(os.environ)
    require(args.writers_quiesced is True, "Trusted reviewed-corpus writers must be quiesced")
    output = ordinary_path(args.output)
    evidence = Evidence(output)
    epoch = sources()
    write(output / "SOURCE_BEFORE.json", epoch)
    corpus = read_json(args.corpus_manifest)
    require(sha(args.corpus_manifest) == args.corpus_manifest_sha256
            and corpus.get("status") == "PASS" and corpus.get("deployment_source_type") == "maintainer_seed"
            and corpus.get("corpus_classification") == "HISTORICAL_CONTROLLED_REPLAY; NOT_NEW_AGENT_SESSION",
            "Approved corpus pin/classification is absent or changed")
    from aevora.checkpoint import capture_graph
    from aevora.experience_resolver import ExperienceResolver
    from aevora.graph_repository import GraphRepository
    from aevora.mcp_server import ExperienceService
    from integrations.aevora import public_runtime_context
    manifest = public_manifest(args.public_manifest)
    require(manifest["id"] == "D-V02", "Controls require the actual D-V02 public manifest")
    context = public_runtime_context(manifest)
    write(output / "INPUT_PROVENANCE.json", {"corpus_manifest_sha256": sha(args.corpus_manifest),
        "public_manifest_sha256": sha(args.public_manifest), "public_runtime_context": context,
        "model_calls": 0, "source_type": "MAINTAINER_CONTROL; NOT_NATURAL_AGENT"})
    main = clone_repo = None
    main_raw = clone_raw = None
    main_before = main_after = None
    clone = "aevora_h2_g3_control_" + uuid.uuid4().hex
    attempted_copy = False
    error = None
    result = {}

    @contextmanager
    def clone_cleanup_before_save():
        try:
            yield
        finally:
            # This exits before the outer maintenance context performs SAVE.
            # A failed experiment must not persist an abandoned clone either.
            if main is not None and attempted_copy and main._client.connection.exists(clone):
                require(clone.startswith("aevora_h2_g3_control_") and clone != GRAPH_NAME,
                        "Cleanup identity is not the owned nonce clone")
                if clone_repo is not None:
                    clone_repo._graph.delete()
                else:
                    actual = main._client.select_graph(clone).delete()
                    main_raw.append({"command": ["GRAPH.DELETE", clone], "graph_name": clone,
                                     "status": "RETURNED", "actual_response": actual})
                require(main._client.connection.exists(clone) == 0, "Failed control clone cleanup was incomplete")
                write(output / "FAILED_CONTROL_CLONE_CLEANUP.json", {"clone": clone,
                    "actual_deleted": True, "before_maintenance_explicit_save": True})
    try:
        (output / "main").mkdir()
        main_raw = RawCommands(output / "main")
        main = GraphRepository.from_environment()
        main_raw.attach(main)
        require(main_raw.exists(main), "Reviewed graph does not exist; no fallback is permitted")
        main_before = capture_graph(main)
        write(output / "MAIN_GRAPH_BEFORE.json", main_before)
        require(main_before == corpus["snapshot"], "Reviewed corpus changed before finite controls")
        main_resolution = ExperienceResolver(main).resolve(context, persist_snapshots=False)
        write(output / "MAIN_READ_ONLY_RESOLUTION.json", main_resolution)
        conflicts = [{"experience_id": row["experience_id"], "actual_strategy": row["strategy"],
            "decision": row["decision"], "reason": row["reason"],
            "required_conflicting_premises": [item for item in row["conflicting_premises"] if item["required"]],
            "attribution": "FINITE_CURRENT_WHEN_CONFLICT; NOT_AGENT_NEGATIVE_TRANSFER"}
            for row in main_resolution["candidates"]
            if any(item["required"] for item in row.get("conflicting_premises", []))]
        write(output / "FINITE_NEGATIVE_TRANSFER_OBSERVATION.json", {"actual_public_context": context,
            "rows": conflicts, "scope": "Recorded history with actually conflicting necessary runtime premises cannot justify blind APPLY"})
        require(evidence.check("actual_required_conflict_prevents_blind_apply",
            bool(conflicts) and all(row["decision"] != "APPLY" for row in conflicts), conflicts,
            scope="Actual reviewed-corpus WHEN/WHY facts; no strategy name or desired repair answer is hardcoded"),
            "Finite premise-conflict control did not refuse blind applicability")
        choices = [(row, path) for row in main_resolution["candidates"]
                   for path in row.get("principle_support_paths", [])]
        require(bool(choices), "No actual material support path exists for this public context")
        selected, path = choices[0]
        experience_id = selected["experience_id"]
        evidence_id = path["records"]["Evidence"]["id"]
        outcome_id = path["records"]["VerifiedOutcome"]["id"]
        with paused_auto_save(output), clone_cleanup_before_save():
            require(main._client.connection.exists(clone) == 0, "Fresh owned clone name already exists")
            attempted_copy = True
            copied = main._graph.copy(clone)
            require(copied.name == clone and main._client.connection.exists(clone) == 1,
                    "Actual official Graph.copy did not create its owned destination")
            write(output / "GRAPH_COPY_RECEIPT.json", {"actual_source": main.graph_name,
                "actual_destination": copied.name, "destination_absent_before": True,
                "policy": "ONE_ACTUAL_OFFICIAL_COPY; NO_RETRY_OR_REPLACEMENT_CORPUS"})
            with graph_environment(clone):
                clone_repo = GraphRepository.from_environment()
            (output / "clone").mkdir()
            clone_raw = RawCommands(output / "clone")
            clone_raw.attach(clone_repo)
            copied_state = capture_graph(clone_repo)
            write(output / "CLONE_BEFORE.json", copied_state)
            require({k:v for k,v in copied_state.items() if k != "graph_name"} ==
                    {k:v for k,v in main_before.items() if k != "graph_name"}, "Official copy differs from the reviewed graph")
            service = ExperienceService(run_id="h2-control-" + uuid.uuid4().hex, public_context=context, repository=clone_repo)
            before = service.resolve_experience({})
            bundle_before = service.build_evidence_bundle(experience_id, before["query_id"])
            write(output / "CONNECTED_BEFORE_RESOLUTION.json", before)
            write(output / "CONNECTED_BEFORE_BUNDLE.json", bundle_before)
            clone_before_delete = capture_graph(clone_repo)
            edges = clone_repo.query("MATCH (s:Evidence {id:$source})-[r:VERIFIES]->(t:VerifiedOutcome {id:$target}) "
                "RETURN r.id,r.payload_json,r.payload_sha256", {"source": evidence_id, "target": outcome_id})
            require(len(edges) == 1, "Selected actual material evidence has no unique VERIFIES edge")
            edge_id = edges[0][0]
            write(output / "SELECTED_ACTUAL_MATERIAL_EDGE.json", {"experience_id": experience_id,
                "actual_path": path, "source_id": evidence_id, "target_id": outcome_id,
                "relation": "VERIFIES", "edge_id": edge_id, "actual_edge_rows": edges,
                "selection": "FIRST_ACTUAL_PRINCIPLE_SUPPORT_PATH; NO_HARDCODED_REPAIR_LABEL"})
            clone_repo.query("MATCH (s:Evidence {id:$source})-[r:VERIFIES {id:$edge}]->(t:VerifiedOutcome {id:$target}) DELETE r",
                {"source": evidence_id, "target": outcome_id, "edge": edge_id}, read_only=False)
            after_delete = capture_graph(clone_repo)
            require(after_delete["nodes"] == clone_before_delete["nodes"]
                    and len(after_delete["edges"]) == len(clone_before_delete["edges"]) - 1
                    and [row for row in clone_before_delete["edges"] if row not in after_delete["edges"]] ==
                        [[evidence_id, "VERIFIES", edge_id, edges[0][2], outcome_id]],
                    "Ablation changed something other than the exact owned material edge")
            write(output / "CLONE_SINGLE_EDGE_ABLATION.json", {"before": clone_before_delete, "after": after_delete})
            after = service.resolve_experience({})
            bundle_after = service.build_evidence_bundle(experience_id, after["query_id"])
            write(output / "CONNECTED_AFTER_RESOLUTION.json", after)
            write(output / "CONNECTED_AFTER_BUNDLE.json", bundle_after)
            old_row = next(row for row in before["candidates"] if row["experience_id"] == experience_id)
            new_row = next(row for row in after["candidates"] if row["experience_id"] == experience_id)
            changed_why = (path in bundle_before["support_paths"] and path not in bundle_after["support_paths"]
                    and len(bundle_after["support_paths"]) == len(bundle_before["support_paths"]) - 1
                    and bundle_before["retrieval_snapshot_sha256"] != bundle_after["retrieval_snapshot_sha256"])
            require(changed_why,
                    "Actual current WHY still claims the removed complete support path")
            delta = {"before_decision": old_row["decision"], "after_decision": new_row["decision"],
                "before_reason": old_row["reason"], "after_reason": new_row["reason"],
                "before_principle_decision": old_row["principle_decision"], "after_principle_decision": new_row["principle_decision"],
                "support_path_counts": [len(bundle_before["support_paths"]), len(bundle_after["support_paths"])],
                "before_retrieval_snapshot_sha256": bundle_before["retrieval_snapshot_sha256"],
                "after_retrieval_snapshot_sha256": bundle_after["retrieval_snapshot_sha256"],
                "attribution": "FINITE_SINGLE_PATH_NECESSITY; NO_STATISTICAL_OR_AGENT_CAUSAL_CREDIT"}
            write(output / "ACTUAL_GRAPH_NECESSITY_DELTA.json", delta)
            require(evidence.check("material_path_ablation_changes_current_why", changed_why, delta,
                    scope="One actual reviewed-corpus support edge deleted only from the nonce clone; resolver and WHY actual SDK reads"),
                    "Necessity evidence check failed")
            # Immutable historical replay remains explicitly historical; it is
            # not an excuse for returning the old full bundle as current truth.
            replay = service.build_evidence_bundle(experience_id, before["query_id"])
            require(replay["snapshot_mode"] == "IMMUTABLE_QUERY_REPLAY"
                    and replay["retrieval_snapshot_sha256"] == bundle_before["retrieval_snapshot_sha256"],
                    "Historical immutable query replay was unexpectedly changed")
            write(output / "EXPLICIT_HISTORICAL_SNAPSHOT_REPLAY.json", replay)
            disconnected_controls(evidence, context, clone, experience_id)
            after_controls = capture_graph(clone_repo)
            outcome_nodes = lambda snapshot: [row for row in snapshot["nodes"] if row[0] == ["VerifiedOutcome"]]
            require(outcome_nodes(after_controls) == outcome_nodes(copied_state), "Controls created or changed a trusted Outcome")
            write(output / "CLONE_AFTER_CONTROLS.json", after_controls)
            clone_repo._graph.delete()
            require(main._client.connection.exists(clone) == 0, "Owned clone remains after actual Graph.delete")
            write(output / "CLONE_CLEANUP.json", {"clone": clone, "actual_deleted": True,
                "owned_nonce_destination": True, "trusted_outcomes_unchanged": True})
        result.update(delta=delta, clone=clone, trusted_outcomes_unchanged=True)
    except Exception as failure:
        error = {"status": "ERROR", "error_type": type(failure).__name__,
                 "message_policy": "TYPE_ONLY; NO_CONNECTION_OR_SECRET_CONTENT"}
        write(output / "CONTROL_ERROR.json", error)
    finally:
        # A failed copy/control must not leave an owned graph behind. Never
        # delete the reviewed graph, G0/G1 or any non-owned destination.
        try:
            if main is not None and attempted_copy and main._client.connection.exists(clone):
                require(clone.startswith("aevora_h2_g3_control_") and clone != GRAPH_NAME,
                        "Cleanup identity is not the owned nonce clone")
                if clone_repo is not None:
                    clone_repo._graph.delete()
                else:
                    main._client.select_graph(clone).delete()
                require(main._client.connection.exists(clone) == 0, "Failed control clone cleanup was incomplete")
                write(output / "FAILED_CONTROL_CLONE_CLEANUP.json", {"clone": clone, "actual_deleted": True})
            if main is not None and main_before is not None:
                main_after = capture_graph(main)
                write(output / "MAIN_GRAPH_AFTER.json", main_after)
                require(main_before == main_after, "Reviewed main graph changed during controls")
        except Exception as cleanup_failure:
            error = {"status": "ERROR", "error_type": type(cleanup_failure).__name__, "stage": "cleanup_or_main_fingerprint"}
            write(output / "CLEANUP_ERROR.json", error)
        finally:
            for raw in (clone_raw, main_raw):
                if raw is not None:
                    raw.close()
            for repo in (clone_repo, main):
                if repo is not None:
                    repo.close()
    final_epoch = sources()
    write(output / "SOURCE_AFTER.json", final_epoch)
    unchanged = epoch["files_sha256"] == final_epoch["files_sha256"] and epoch["official_sdk_graph_source"] == final_epoch["official_sdk_graph_source"]
    passed = error is None and main_before == main_after and unchanged and evidence.checks and all(row["status"] == "PASS" for row in evidence.checks)
    raw_refs = [{"path": str(path.relative_to(output)), "sha256": sha(path)} for path in sorted(output.rglob("*.jsonl"))]
    summary = {"version": VERSION, "status": "PASS" if passed else "FAIL", "error": error,
        "model_calls": 0, "new_trusted_outcomes": 0, "main_corpus_unchanged": main_before is not None and main_before == main_after,
        "source_unchanged": unchanged, "checks": evidence.checks, "raw_evidence": raw_refs, **result,
        "scope": "Finite real-copy path necessity and actual MCP disconnect controls; not a statistical ablation or Agent benefit experiment",
        "unverified": ["Causal governance benefit on Agent repair", "Statistical negative transfer", "Native Agent behavior under Graph failure", "Shared-kernel hostile-runtime attestation"],
        "started_source_epoch_sha256": sha(output / "SOURCE_BEFORE.json"), "ended_at": now()}
    write(output / "SUMMARY.json", summary)
    print(json.dumps({key: summary[key] for key in ("status", "model_calls", "new_trusted_outcomes", "main_corpus_unchanged", "source_unchanged")}))
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--writers-quiesced", required=True, action="store_true")
    parser.add_argument("--corpus-manifest", required=True, type=Path)
    parser.add_argument("--corpus-manifest-sha256", required=True)
    parser.add_argument("--public-manifest", type=Path, default=ROOT / "benchmark/scenarios/D-V02/public.json")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
