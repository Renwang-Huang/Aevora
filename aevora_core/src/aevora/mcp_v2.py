"""Explicit Host-bound v2 profile for the existing four-tool MCP transport."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import os
from pathlib import Path
import stat
import uuid
from .contracts import *
from .models import utc_now
from .graph_repository import GraphRepository
from .mcp_projection import (
    MAX_DOCUMENT_BYTES,
    ProjectionCapacityError,
    PublicProjection,
    _entries,
    fits,
)


@dataclass(frozen=True)
class ReadGrant:
    tenant: str
    run_id: str
    session_id: str
    generation: str
    valid_until: str
    authz_epoch: int = 0
    profile: str = PROFILE

    def check(self):
        for value in [self.tenant, self.run_id, self.session_id, self.generation]:
            validate_id(value)
        require(
            self.profile == PROFILE
            and timestamp(self.valid_until) > datetime.now(timezone.utc),
            "UNAUTHORIZED",
        )

    def session_record_id(self, tenant):
        require(tenant == self.tenant, "UNAUTHORIZED")
        return identity(
            tenant, "Session", [self.run_id, self.session_id, self.generation]
        )


def load_configuration(path, environment=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid()
            and info.st_mode & 0o077 == 0
            and info.st_nlink == 1
            and info.st_size <= 1024 * 1024,
            "UNAUTHORIZED",
        )
        raw = os.read(fd, 1024 * 1024 + 1)
        require(len(raw) == info.st_size, "UNAUTHORIZED")
    finally:
        os.close(fd)
    config = decode_json(raw)
    require(set(config) == {"binding", "registry", "facts", "grant"}, "UNAUTHORIZED")
    grant = ReadGrant(**config["grant"])
    grant.check()
    binding = TenantBinding(**config["binding"])
    require(binding.tenant_id == grant.tenant, "UNAUTHORIZED")
    if set(config["registry"]) == {"pin_root"}:
        # This bootstrap file is private, owned, no-follow and mode0600.
        # No public tool accepts a path or registration operation.
        from .host_pins import read_registry
        registry = read_registry(config["registry"]["pin_root"])
    else:
        require(set(config["registry"]) ==
                {"authorities", "outcomes", "fact_sources", "publications"}, "UNAUTHORIZED")
        registry = TrustRegistry(**config["registry"])
    transport = GraphRepository.from_environment(environment)
    require(transport.graph_name == binding.graph_name, "UNAUTHORIZED")
    repo = transport.v2(binding, registry)
    for f in config["facts"].values():
        registry.verify_fact(f)
    repo.authorize(grant)
    return repo, grant, config["facts"]


class V2Service:
    def __init__(self, repo, grant, facts, connection_id):
        self.repository, self.grant, self.facts, self.connection_id = (
            repo,
            grant,
            facts,
            connection_id,
        )
        self.enable_proposals = True
        self.run_id = grant.run_id
        self._queries = {}
        self._claim_ids = set()

    def auth(self, state=None):
        state = self.repository.authorize(self.grant, state)
        return dict(
            protocol_profile=PROFILE,
            tenant_id=self.grant.tenant,
            run_id=self.grant.run_id,
            session_id=self.grant.session_id,
            connection_id=self.connection_id,
            grant_generation=self.grant.generation,
            semantic_epoch=state["epoch"],
            authz_epoch=state["authz_epoch"],
            generation=state["generation"],
        )

    def resolve(self, claims, request_key=None):
        from .experience_resolver import resolve_v2

        self.auth()
        for key, value in claims.items():
            trusted = self.facts.get("task." + key)
            if trusted and trusted["availability"] == "KNOWN":
                require(
                    type(value) is type(trusted["value"]) and value == trusted["value"],
                    "CONTEXT_CONFLICT",
                )
        key = request_key or uuid.uuid4().hex
        qid = identity(
            self.grant.tenant, "Query", [self.grant.run_id, self.grant.session_id, key]
        )
        if qid in self._queries:
            old = self._queries[qid]
            require(old["claims_sha256"] == digest(claims), "INVALID_INPUT")
            self.auth(old["state"])
            return old["response"]
        require(len(self._queries) < 32, "CAPACITY_EXCEEDED")
        state, rows = resolve_v2(self.repository, self.facts, qid, utc_now())
        response = dict(
            status="AVAILABLE" if rows else "EMPTY",
            query_id=qid,
            recommendations=[r for r, w in rows],
            candidate_count=len(rows),
            completeness="COMPLETE",
            read_scope=self.auth(state),
            participant_claims_status="UNVERIFIED_NOT_USED_FOR_APPLICABILITY",
        )
        snapshot = self.repository.put_document(
            "QuerySnapshot",
            qid,
            dict(response=response, witnesses={r["experience_id"]: w for r, w in rows}),
            run_id=self.run_id,
            session_id=self.grant.session_id,
        )
        query = record(
            self.grant.tenant,
            "Query",
            [self.grant.run_id, self.grant.session_id, key],
            run_id=self.run_id,
            session_id=self.grant.session_id,
            epoch=state["epoch"],
            authz_epoch=state["authz_epoch"],
            snapshot_id=snapshot["id"],
            claims_sha256=digest(claims),
            state_sha256=digest(state),
            grant_generation=self.grant.generation,
        )
        self.repository.put_node(query)
        for r, w in rows:
            n = record(
                self.grant.tenant,
                "Recommendation",
                [
                    r["query_id"],
                    r["experience_id"],
                    r["witness_sha256"],
                    r["context_sha256"],
                    r["policy_version"],
                ],
                run_id=self.run_id,
                session_id=self.grant.session_id,
                recommendation=r,
            )
            require(n["id"] == r["recommendation_id"])
            self.repository.put_node(n)
            self.repository.put_edge(edge(self.grant.tenant, "PRODUCED", query, n))
        self._queries[qid] = dict(
            state=state, response=response, claims_sha256=digest(claims)
        )
        self.auth(state)
        return response

    def bundle(self, experience_id, query_id, view="recommendation"):
        require(
            query_id in self._queries
            and any(
                r["experience_id"] == experience_id
                for r in self._queries[query_id]["response"]["recommendations"]
            ),
            "UNAUTHORIZED",
        )
        repo = self.repository
        state = repo.authorize(self.grant)
        query = repo.node(query_id)
        require(
            query["kind"] == "Query"
            and query["run_id"] == self.run_id
            and query["session_id"] == self.grant.session_id
            and query["grant_generation"] == self.grant.generation,
            "UNAUTHORIZED",
        )
        require(query["state_sha256"] == digest(state), "STALE_SNAPSHOT")
        document = repo.load_document(repo.node(query["snapshot_id"]))
        require(experience_id in document["witnesses"], "UNAUTHORIZED")
        old = document["witnesses"][experience_id]
        # Re-read actual published state even when epoch didn't change. No cached integrity bypass.
        # Revalidate authenticated recall catalogue too; an index/projection miss cannot hide a candidate.
        repo.discover(self.facts, state)
        current = repo.read_witness(experience_id, state)
        require(digest(current) == digest(old), "GRAPH_INTEGRITY_ERROR")
        recs = [
            r
            for r in document["response"]["recommendations"]
            if r["experience_id"] == experience_id
        ]
        require(len(recs) == 1)
        from .arbitration import arbitrate

        current_recommendation = arbitrate(current, self.facts, query_id, utc_now())
        require(current_recommendation == recs[0], "STALE_SNAPSHOT")
        self.auth(state)
        return dict(
            status="AVAILABLE",
            query_id=query_id,
            experience_id=experience_id,
            recommendation=recs[0],
            witness=current,
            document_sha256=digest(current),
            read_scope=self.auth(state),
            view=view,
        )

    def decision(self, body):
        full = self.bundle(body["experience_id"], body["query_id"])
        require(
            full["recommendation"]["recommendation_id"] == body["recommendation_id"],
            "UNAUTHORIZED",
        )
        key = [self.run_id, self.grant.session_id, body["idempotency_key"]]
        identifier = identity(self.grant.tenant, "Decision", key)
        self._untrusted("Decision", key, body)
        self._claim_ids.add(identifier)
        return dict(
            status="RECORDED_UNTRUSTED",
            decision_id=identifier,
            attribution="UNKNOWN",
            trusted_outcome="NOT_SUBMITTED",
            read_scope=full["read_scope"],
        )

    def _untrusted(self, kind, key, body):
        from .candidate import public_text

        for k in ["reason", "action_intent", "title", "strategy", "public_summary"]:
            if k in body:
                public_text(body[k])
        identifier = identity(self.grant.tenant, kind, key)
        rows = self.repository.execute("Q13", id=identifier)
        if rows:
            old = self.repository.node(identifier)
            require(old["body_sha256"] == digest(body), "INVALID_INPUT")
            return old
        value = record(
            self.grant.tenant,
            kind,
            key,
            source="UNTRUSTED_AGENT",
            run_id=self.run_id,
            session_id=self.grant.session_id,
            body=body,
            body_sha256=digest(body),
            state="PROPOSED_UNTRUSTED" if kind == "Candidate" else "CLAIM_ONLY",
            created=utc_now(),
        )
        self.repository.put_node(value)
        return value

    def propose(self, body):
        self.auth()
        for ref in body["source_references"]:
            permitted = (
                ref["kind"] == "Query"
                and ref["id"] in self._queries
                or ref["kind"] == "Recommendation"
                and any(
                    ref["id"] == r["recommendation_id"]
                    for q in self._queries.values()
                    for r in q["response"]["recommendations"]
                )
                or ref["kind"] == "Decision"
                and ref["id"] in self._claim_ids
            )
            require(permitted, "UNAUTHORIZED")
            n = self.repository.node(ref["id"])
            require(
                n["kind"] == ref["kind"]
                and n["run_id"] == self.run_id
                and n["session_id"] == self.grant.session_id,
                "UNAUTHORIZED",
            )
        n = self._untrusted(
            "Candidate",
            [self.run_id, self.grant.session_id, body["candidate_key"]],
            body,
        )
        return dict(
            status="PROPOSED_UNTRUSTED",
            candidate_id=n["id"],
            body_sha256=n["body_sha256"],
            publication="NOT_PUBLISHED",
            read_scope=self.auth(),
        )


class V2Projection(PublicProjection):
    def deliver(self, full, kind, binding, authorize):
        if fits(full):
            authorize([])
            return full
        require(
            len(canonical_json(full).encode()) <= MAX_DOCUMENT_BYTES,
            "CAPACITY_EXCEEDED",
        )
        rows = list(_entries(full))
        metadata = dict(
            status=full["status"],
            query_id=full["query_id"],
            read_scope=full["read_scope"],
            projection="LOSSLESS_JSON_POINTER_ENTRIES",
            document_sha256=digest(full),
        )
        identifier = self._remember(
            kind, binding, metadata, rows, authorize, digest(full)
        )
        return self._page(identifier, 0)

    def resolve_v2(self, claims, cursor=None, request_key=None):
        binding = digest(
            [
                self.service.grant.__dict__,
                self.service.connection_id,
                claims,
                request_key,
            ]
        )
        if cursor:
            return self.continuation(cursor, "resolve_v2", binding)
        full = self.service.resolve(claims, request_key)
        state = self.service.repository.state()
        query = full["query_id"]

        def authorize(_):
            self.service.auth(state)
            for r in full["recommendations"]:
                self.service.bundle(r["experience_id"], query)

        return self.deliver(full, "resolve_v2", binding, authorize)

    def bundle_v2(self, experience_id, query_id, cursor=None, view="recommendation"):
        binding = digest(
            [
                self.service.grant.__dict__,
                self.service.connection_id,
                experience_id,
                query_id,
                view,
            ]
        )
        if cursor:
            return self.continuation(cursor, "bundle_v2", binding)
        full = self.service.bundle(experience_id, query_id, view)

        def authorize(_):
            self.service.bundle(experience_id, query_id, view)

        return self.deliver(full, "bundle_v2", binding, authorize)


def create_server(service):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    projection = V2Projection(service)

    class Server(FastMCP):
        async def list_tools(self):
            tools = await super().list_tools()
            for t in tools:
                t.inputSchema = schema(t.name + ".arguments")
            return tools

        async def call_tool(self, name, arguments):
            try:
                require(
                    name
                    in {
                        "resolve_experience",
                        "build_evidence_bundle",
                        "record_decision",
                        "propose_experience",
                    },
                    "INVALID_INPUT",
                )
                validate_schema(name + ".arguments", arguments)
                require(
                    len(canonical_json(arguments).encode())
                    <= (
                        16384
                        if name == "propose_experience"
                        else 8192
                        if name == "resolve_experience"
                        else 32768
                    ),
                    "INVALID_INPUT",
                )
            except V2Error as e:
                raise ValueError(e.code) from None
            return await super().call_tool(name, arguments)

    server = Server(
        "Aevora",
        instructions="Explicit Graph v2 evidence arbitration. Recommendations are bounded, claims are untrusted. No Host publication authority is exposed.",
    )

    def invoke(fn):
        try:
            return fn()
        except V2Error as e:
            raise ValueError(e.code) from None
        except ProjectionCapacityError:
            raise ValueError("PAGE_CAPACITY_EXCEEDED") from None
        except Exception:
            raise RuntimeError("AEVORA_V2_OPERATION_FAILED") from None

    @server.tool(
        structured_output=True,
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, openWorldHint=False
        ),
    )
    def resolve_experience(
        task_context: dict, cursor: str | None = None, request_key: str | None = None
    ) -> dict[str, Any]:
        """Resolve Host-attested phase facts. Claims cannot establish premises; follow every lossless page."""
        return invoke(lambda: projection.resolve_v2(task_context, cursor, request_key))

    @server.tool(
        structured_output=True,
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, openWorldHint=False
        ),
    )
    def build_evidence_bundle(
        experience_id: str,
        query_id: str | None = None,
        cursor: str | None = None,
        view: str = "recommendation",
    ) -> dict[str, Any]:
        """Read complete typed witness under current permission and epoch. Follow all pages and verify SHA."""
        return invoke(
            lambda: projection.bundle_v2(experience_id, query_id, cursor, view)
        )

    @server.tool(
        structured_output=True,
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, openWorldHint=False
        ),
    )
    def record_decision(decision: dict) -> dict[str, Any]:
        """Record only an untrusted decision claim citing this Session's recommendation."""
        return invoke(lambda: service.decision(decision))

    @server.tool(
        structured_output=True,
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, openWorldHint=False
        ),
    )
    def propose_experience(proposal: dict) -> dict[str, Any]:
        """Store an untrusted Candidate; cannot publish, attest an outcome, or write graph facts."""
        return invoke(lambda: service.propose(proposal))

    return server


class OutputGuard:
    def __init__(self, path, environment=None):
        self.repo, self.grant, self.facts = load_configuration(path, environment)

    def check(self, value):
        current = self.repo.authorize(self.grant)
        result = value.get("result", {})
        if "structuredContent" in result and not result.get("isError"):
            auth = result["structuredContent"].get("read_scope", {})
            require(
                auth.get("run_id") == self.grant.run_id
                and auth.get("session_id") == self.grant.session_id
                and auth.get("protocol_profile") == PROFILE
                and auth.get("semantic_epoch") == current["epoch"]
                and auth.get("authz_epoch") == current["authz_epoch"]
                and auth.get("grant_generation") == self.grant.generation,
                "UNAUTHORIZED",
            )
        return dict(
            semantic_epoch=current["epoch"],
            authz_epoch=current["authz_epoch"],
            grant_generation=self.grant.generation,
            checked_at=utc_now(),
            linearization="LOCAL_BROKER_LOCK; EXTERNAL_DB_TO_SEND_RACE_REMAINS",
        )
