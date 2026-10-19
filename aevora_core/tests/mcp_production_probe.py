"""Archive an explicit maintainer transport probe, never a model challenge."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import uuid

from aevora.graph_repository import GraphRepository
from aevora.historical_import import ATOMIC_ID, LOCK_ID, public_context
from aevora.mcp_broker import MCPBroker, PROTOCOL
from aevora.models import utc_now


def main() -> int:
    archive = Path(sys.argv[1])
    archive.mkdir(parents=True, exist_ok=False)
    run_id = "maintainer-probe-" + str(uuid.uuid4())
    token = secrets.token_hex(32)
    responses = []
    repository = GraphRepository.from_environment()
    before = repository.state_fingerprint()

    def request(channel, reader, identifier, method, params=None):
        value = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            value["params"] = params
        channel.sendall(json.dumps(value).encode() + b"\n")
        answer = json.loads(reader.readline())
        assert answer.get("id") == identifier
        responses.append({"request": value, "response": answer})
        assert "error" not in answer
        return answer["result"]

    def connect(broker):
        channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        channel.settimeout(20)
        channel.connect(str(broker.socket_path))
        reader = channel.makefile("rb")
        channel.sendall(json.dumps({"protocol": PROTOCOL, "run_id": run_id,
                                    "token": token, "nonce": secrets.token_hex(32)}).encode() + b"\n")
        assert json.loads(reader.readline())["aevora_transport"] == "READY"
        init = request(channel, reader, 1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                                         "clientInfo": {"name": "Aevora maintainer production transport probe", "version": "1"}})
        assert init["serverInfo"]["name"] == "Aevora"
        channel.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        return channel, reader

    def call(channel, reader, identifier, name, arguments):
        result = request(channel, reader, identifier, "tools/call", {"name": name, "arguments": arguments})
        assert result.get("isError") is False
        return result["structuredContent"]

    started = utc_now()
    with tempfile.TemporaryDirectory(prefix="aevora-mcp-") as channel_dir:
        broker = MCPBroker(run_id=run_id, public_context=public_context("multi_process_shared_sqlite"),
                           socket_path=Path(channel_dir) / "mcp.sock", run_token=token,
                           event_path=archive / "mcp_events.jsonl")
        with broker:
            first, reader = connect(broker)
            second = second_reader = None
            try:
                catalog = request(first, reader, 2, "tools/list")
                assert {tool["name"] for tool in catalog["tools"]} == {"resolve_experience", "build_evidence_bundle", "record_decision"}
                query = call(first, reader, 3, "resolve_experience", {"task_context": {}})
                kinds = {row["experience_id"]: row["decision"] for row in query["candidates"]}
                assert kinds[ATOMIC_ID] == "APPLY" and kinds[LOCK_ID] == "ABSTAIN"
                bundle = call(first, reader, 4, "build_evidence_bundle", {"experience_id": ATOMIC_ID})
                assert bundle["support_paths"]
                for private_field in ("private_verification", "source_reference", "hidden_tests/", "reference_patches/", "private_manifests/"):
                    assert private_field not in json.dumps(bundle)
                decision = call(first, reader, 5, "record_decision", {"decision": {
                    "query_id": query["query_id"], "experience_id": ATOMIC_ID, "decision": "VERIFY",
                    "reason": "Maintainer production transport probe, not Agent adoption or benchmark grade.",
                    "verification_steps": ["Verify SDK response and persisted scoped claim only"]}})
                second, second_reader = connect(broker)
                second_bundle = call(second, second_reader, 2, "build_evidence_bundle", {"experience_id": ATOMIC_ID})
                assert second_bundle["retrieval_snapshot_sha256"] == bundle["retrieval_snapshot_sha256"]
                assert repository.get_node("Query", query["query_id"])["run_id"] == run_id
                assert repository.get_node("Decision", decision["decision_id"])["authority"] == "UNTRUSTED_PARTICIPANT_CLAIM"
            finally:
                reader.close(); first.close()
                if second is not None:
                    second_reader.close(); second.close()
        assert broker.metadata["handler_cleanup_complete"] and broker.metadata["token_revoked"] and broker.metadata["socket_unlinked"]
        assert token not in (archive / "mcp_events.jsonl").read_text()
    after = repository.state_fingerprint()
    repository.close()
    result = {"status": "PASS", "evidence_kind": "CURRENT_MAINTAINER_PRODUCTION_TRANSPORT_PROBE",
              "model_invocation": False, "native_session_status": "NOT_EXECUTED",
              "benchmark_evaluation_status": "NOT_EXECUTED", "run_id": run_id,
              "started_at": started, "ended_at": utc_now(), "query_id": query["query_id"],
              "decision_id": decision["decision_id"], "graph_before": before, "graph_after": after,
              "candidate_decisions": kinds, "broker": broker.metadata,
              "raw_event_sha256": hashlib.sha256((archive / "mcp_events.jsonl").read_bytes()).hexdigest()}
    (archive / "sdk_requests_responses.json").write_text(json.dumps(responses, ensure_ascii=False, indent=2) + "\n")
    (archive / "probe_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
