"""Real official MCP SDK, authenticated existing UDS Broker, real owned FalkorDB."""

from datetime import datetime, timezone, timedelta
import json, os, secrets, socket, tempfile
from pathlib import Path
import pytest
from aevora.contracts import *
from aevora.mcp_v2 import ReadGrant
from aevora.mcp_broker import MCPBroker, MAX_MESSAGE_BYTES, PROTOCOL
from aevora_core.tests.test_mcp_real_graph import connect, tool, rpc
from tools.validation.g21_fixture import seed, facts, update_state


def broker(v2, tmp_path, monkeypatch, session="session-one", generation="one"):
    artifact_root = os.environ.get("AEVORA_G21_ARTIFACT_ROOT")
    if artifact_root:
        tmp_path = Path(artifact_root) / tmp_path.name
        tmp_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", v2.binding.graph_name)
    grant = ReadGrant(
        v2.tenant,
        "run-g21",
        session,
        generation,
        (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        authz_epoch=v2.state()["authz_epoch"],
    )
    n = record(
        v2.tenant,
        "Session",
        [grant.run_id, grant.session_id, grant.generation],
        run_id=grant.run_id,
        session_id=grant.session_id,
        grant_generation=grant.generation,
        profile=PROFILE,
        state="ACTIVE",
        valid_until=grant.valid_until,
    )
    v2.put_node(n)
    fs = facts(v2.registry, task__shared_state_kind="sqlite_file")
    config = tmp_path / ("config-" + session + "-" + generation + ".json")
    config.write_text(
        canonical_json(
            dict(
                binding=v2.binding.__dict__,
                registry=v2.registry.__dict__,
                facts=fs,
                grant=grant.__dict__,
            )
        )
    )
    config.chmod(0o600)
    token = secrets.token_hex(32)
    folder = Path(tempfile.mkdtemp(prefix="g21-mcp-"))
    return MCPBroker(
        run_id=grant.run_id,
        public_context={},
        socket_path=folder / "m.sock",
        run_token=token,
        event_path=tmp_path / ("events-" + session + "-" + generation + ".jsonl"),
        server_environment={
            "AEVORA_V2_QUERY_AUDIT": str(tmp_path / "SDK_RAW_CYPHER.jsonl")
        },
        enable_proposals=True,
        protocol_profile=PROFILE,
        v2_config_path=str(config),
    ), token


def test_real_sdk_graph_read_decision_and_four_tools(v2, tmp_path, monkeypatch):
    seed(v2)
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            tools = rpc(c, r, 2, "tools/list")["tools"]
            assert {t["name"] for t in tools} == {
                "resolve_experience",
                "build_evidence_bundle",
                "record_decision",
                "propose_experience",
            }
            q = tool(c, r, 3, "resolve_experience", {"task_context": {}})
            assert not q["isError"], q
            q = q["structuredContent"]
            rec = q["recommendations"][0]
            assert rec["core_verdict"] == "APPLY"
            full = tool(
                c,
                r,
                4,
                "build_evidence_bundle",
                dict(
                    experience_id=rec["experience_id"],
                    query_id=q["query_id"],
                    view="recommendation",
                ),
            )
            assert not full["isError"], full
            d = dict(
                query_id=q["query_id"],
                experience_id=rec["experience_id"],
                recommendation_id=rec["recommendation_id"],
                idempotency_key="first",
                decision="VERIFY",
                reason="Independently verify actual code",
                verification_steps=["Run public engineering tests"],
            )
            first = tool(c, r, 5, "record_decision", {"decision": d})
            assert not first["isError"], first
            second = tool(c, r, 6, "record_decision", {"decision": d})
            assert first["structuredContent"] == second["structuredContent"]
            assert (
                v2.node(first["structuredContent"]["decision_id"])["state"]
                == "CLAIM_ONLY"
            )
            assert len(v2.transport.query("MATCH(n:VerifiedOutcome) RETURN n.id")) == 1
        finally:
            r.close()
            c.close()
    assert b.metadata["handler_cleanup_complete"]
    events = [json.loads(line) for line in b.event_path.read_text().splitlines()]
    assert any(e["category"] == "V2_RESPONSE_DELIVERED" for e in events)
    assert max(e.get("delivered_bytes", 0) for e in events) <= MAX_MESSAGE_BYTES


@pytest.mark.parametrize(
    "attack",
    [
        {"tenant_id": "other"},
        {"graph": "other"},
        {"Hostprincipal": "admin"},
        {"task_context": {"worker_count_known": 1}},
        {"task_context": {"Authority": "trusted"}},
        {"protocol_profile": "aevora.mcp/1.2"},
    ],
)
def test_real_sdk_caller_cannot_select_authority(v2, tmp_path, monkeypatch, attack):
    seed(v2)
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            out = tool(c, r, 2, "resolve_experience", {"task_context": {}, **attack})
            assert out["isError"]
            assert "structuredContent" not in out
        finally:
            r.close()
            c.close()


def test_real_sdk_lossless_pages_and_revoked_cached_cursor(v2, tmp_path, monkeypatch):
    data = seed(v2, outcomes=("PASS",) * 16 + ("FAIL",))
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            q = tool(c, r, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
            rec = q["recommendations"][0]
            args = dict(
                experience_id=rec["experience_id"],
                query_id=q["query_id"],
                view="recommendation",
            )
            first = tool(c, r, 3, "build_evidence_bundle", args)["structuredContent"]
            assert (
                first["truncated"] and first["next_cursor"] and first["document_sha256"]
            )
            cursor = first["next_cursor"]
            pages = [first]
            i = 4
            while pages[-1]["has_more"]:
                result = tool(
                    c,
                    r,
                    i,
                    "build_evidence_bundle",
                    {**args, "cursor": pages[-1]["next_cursor"]},
                )
                assert not result["isError"], result
                pages.append(result["structuredContent"])
                i += 1
            assert all(p["document_sha256"] == first["document_sha256"] for p in pages)
            assert sum(len(p["entries"]) for p in pages) == first["total_items"]
            # New connection cannot use old HMAC or query identity.
            c2, r2 = connect(b, t)
            try:
                assert tool(
                    c2, r2, 2, "build_evidence_bundle", {**args, "cursor": cursor}
                )["isError"]
            finally:
                r2.close()
                c2.close()
            # Graph authz revoke invalidates cached pages; guard closes connection rather than leaks old bytes.
            update_state(v2, authz_epoch=1)
            c.sendall(
                (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": i,
                            "method": "tools/call",
                            "params": {
                                "name": "build_evidence_bundle",
                                "arguments": {**args, "cursor": cursor},
                            },
                        }
                    )
                    + "\n"
                ).encode()
            )
            try:
                raw = r.readline()
                assert (
                    not raw or json.loads(raw).get("result", {}).get("isError") is True
                )
            except ConnectionResetError:
                pass
        finally:
            r.close()
            c.close()


def test_cross_session_reference_and_nonexistent_reference_have_same_error(
    v2, tmp_path, monkeypatch
):
    seed(v2)
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            q = tool(c, r, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
        finally:
            r.close()
            c.close()
    other, token = broker(v2, tmp_path, monkeypatch, session="session-two")
    with other:
        c, r = connect(other, token)
        try:
            reference = q["recommendations"][0]["experience_id"]
            existing = tool(
                c,
                r,
                2,
                "build_evidence_bundle",
                dict(
                    experience_id=reference,
                    query_id=q["query_id"],
                    view="recommendation",
                ),
            )
            absent = tool(
                c,
                r,
                3,
                "build_evidence_bundle",
                dict(
                    experience_id=reference,
                    query_id="Query:absent",
                    view="recommendation",
                ),
            )
            assert existing["isError"] and absent["isError"]
            assert existing["content"] == absent["content"]
        finally:
            r.close()
            c.close()


def test_cached_page_rechecks_actual_negative_evidence_even_without_epoch(
    v2, tmp_path, monkeypatch
):
    data = seed(v2, outcomes=("PASS",) * 16 + ("FAIL",))
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            q = tool(c, r, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
            args = dict(
                experience_id=q["recommendations"][0]["experience_id"],
                query_id=q["query_id"],
                view="recommendation",
            )
            page = tool(c, r, 3, "build_evidence_bundle", args)["structuredContent"]
            assert page["has_more"]
            negative = next(e for e in data["edges"] if e["kind"] == "COUNTEREXAMPLE")
            v2.transport.query(
                "MATCH()-[r {id:$id}]->() DELETE r",
                dict(id=negative["id"]),
                read_only=False,
            )
            result = tool(
                c,
                r,
                4,
                "build_evidence_bundle",
                {**args, "cursor": page["next_cursor"]},
            )
            assert result["isError"] and "structuredContent" not in result
        finally:
            r.close()
            c.close()


def test_v2_delivery_scope_is_archived_without_blanket_secret_redaction(
    v2, tmp_path, monkeypatch
):
    seed(v2)
    b, t = broker(v2, tmp_path, monkeypatch)
    with b:
        c, r = connect(b, t)
        try:
            q = tool(c, r, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
            assert q["read_scope"]["protocol_profile"] == PROFILE
            proposal = dict(
                candidate_key="source-bound",
                title="An untrusted conditional observation",
                strategy="Verify the complete durable operation",
                public_summary="Not a Host publication",
                necessary_conditions={"task.shared_state_kind": ["sqlite_file"]},
                inapplicable_conditions={},
                scope={"task.shared_state_kind": ["sqlite_file"]},
                unknown_fields=[],
                limitations=["Synthetic read-side acceptance only"],
                source_references=[{"kind": "Query", "id": q["query_id"]}],
            )
            made = tool(c, r, 3, "propose_experience", {"proposal": proposal})
            assert not made["isError"], made
            assert made["structuredContent"]["publication"] == "NOT_PUBLISHED"
            absent = {
                **proposal,
                "candidate_key": "absent",
                "source_references": [{"kind": "Query", "id": "Query:absent"}],
            }
            denied = tool(c, r, 4, "propose_experience", {"proposal": absent})
            assert denied["isError"]
        finally:
            r.close()
            c.close()
    events = [json.loads(l) for l in b.event_path.read_text().splitlines()]
    delivered = {
        e["delivered_sha256"]
        for e in events
        if e["category"] == "V2_RESPONSE_DELIVERED"
    }
    assert all(
        isinstance(e["read_scope"], dict)
        for e in events
        if e["category"] == "V2_RESPONSE_DELIVERED"
    )
    replies = [
        e
        for e in events
        if e["category"] == "JSONRPC"
        and e.get("direction") == "OFFICIAL_SDK_TO_PARTICIPANT"
    ]
    assert replies and all(
        e["redaction"] == "NONE" and e["archived_message_sha256"] in delivered
        for e in replies
    )


def test_committed_future_withdrawal_invalidates_cached_result_on_time_boundary(
    v2, tmp_path, monkeypatch
):
    from tools.validation.g21_fixture import seal_closure
    import aevora.mcp_v2 as m

    data = seed(v2)
    effective = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    g = record(
        v2.tenant,
        "GovernanceEvent",
        "future-withdraw",
        event_type="withdraw",
        effective_at=effective,
        scope=data["revision"]["scope"],
        target_id=data["revision"]["id"],
        target_label="ExperienceRevision",
    )
    seal_closure(
        v2,
        "future-withdraw-manifest",
        data["experience"],
        data["nodes"] + [g],
        data["edges"] + [edge(v2.tenant, "GOVERNS", g, data["revision"])],
    )
    b, t = broker(v2, tmp_path, monkeypatch)
    repo, grant, fs = m.load_configuration(b.v2_config_path)
    service = m.V2Service(repo, grant, fs, "controlled-clock-probe")
    query = service.resolve({})
    assert query["recommendations"][0]["core_verdict"] == "APPLY"
    # Real DB; only policy as-of clock moves. No fake result/backend/Outcome.
    monkeypatch.setattr(m, "utc_now", lambda: later)
    with pytest.raises(V2Error, match="STALE_SNAPSHOT"):
        service.bundle(query["recommendations"][0]["experience_id"], query["query_id"])
    repo.transport.close()


def test_two_real_tenant_brokers_keep_independent_host_graph_bindings(
    v2, tmp_path, monkeypatch
):
    from aevora.graph_repository import GraphRepository
    import uuid

    seed(v2, "same-local-key")
    a, ta = broker(v2, tmp_path, monkeypatch, session="tenant-a-session")
    settings = v2.transport._client.connection.connection_pool.connection_kwargs
    name = "aevora_v2_g21_peer_" + uuid.uuid4().hex
    transport = GraphRepository(
        host="127.0.0.1",
        port=settings["port"],
        password=settings["password"],
        graph_name=name,
    )
    peer = transport.v2(TenantBinding("tenant-peer", name), TrustRegistry())
    peer.initialize()
    peer_data = seed(peer, "same-local-key")
    b, tb = broker(peer, tmp_path, monkeypatch, session="tenant-b-session")
    # Global host environment now points B; A must keep its immutable captured binding.
    with a, b:
        ca, ra = connect(a, ta)
        cb, rb = connect(b, tb)
        try:
            qa = tool(ca, ra, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
            qb = tool(cb, rb, 2, "resolve_experience", {"task_context": {}})[
                "structuredContent"
            ]
            assert (
                qa["read_scope"]["tenant_id"] == v2.tenant
                and qb["read_scope"]["tenant_id"] == peer.tenant
            )
            assert (
                qa["recommendations"][0]["experience_id"]
                != qb["recommendations"][0]["experience_id"]
            )
            rejected = tool(
                cb,
                rb,
                3,
                "build_evidence_bundle",
                dict(
                    experience_id=qa["recommendations"][0]["experience_id"],
                    query_id=qa["query_id"],
                    view="recommendation",
                ),
            )
            assert rejected["isError"] and "structuredContent" not in rejected
        finally:
            ra.close()
            ca.close()
            rb.close()
            cb.close()
    transport.close()


def test_real_broker_closes_parent_graph_client(v2, tmp_path, monkeypatch):
    seed(v2)
    b, t = broker(v2, tmp_path, monkeypatch)
    closed = []
    with b:
        c, r = connect(b, t)
        try:
            assert not tool(c, r, 2, "resolve_experience", {"task_context": {}})[
                "isError"
            ]
            original = b._v2_guard.repo.transport.close

            def close_actual():
                closed.append(True)
                return original()

            monkeypatch.setattr(b._v2_guard.repo.transport, "close", close_actual)
        finally:
            r.close()
            c.close()
    assert closed == [True]
    assert b.metadata["v2_repository_closed"] is True
