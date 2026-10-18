"""Aevora's three public tools, served by the official MCP Python SDK.

The trusted broker supplies immutable run authority before MCP initialization.
This module and the graph password file are never mounted in Participant.
Participant decisions are claims; this service cannot create trusted outcomes.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError, WithJsonSchema

from .graph_repository import GraphRepository
from .proposal_contract import CandidateProposal
from .models import GraphError, GraphUnavailable, canonical_json, digest, normalize_context, utc_now, validate_id, PUBLIC_CONTEXT_FACTS


VERSION = "aevora.mcp/1.2"
_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
_FACT_KEYS = PUBLIC_CONTEXT_FACTS


class PublicContextClaims(BaseModel):
    """Eight documented MCP facts, never a source of trusted applicability.

    Omit uncertain claims or use null. Text examples describe public vocabulary,
    not a closed enum or a particular Run's private/pinned values. The Host's
    existing extended fact vocabulary remains an internal compatibility contract.
    The serialized UTF-8 claims object is limited to 8192 bytes before graph
    access; errors never echo the supplied values.
    """

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    concurrency_scope: StrictStr | None = Field(default=None,
        description="Public topology label, e.g. single_process_threads or independent_processes. Omit/null if unknown.")
    worker_count_known: StrictBool | None = Field(default=None,
        description="Whether the public worker count is known: boolean, NOT a count or [2,4] array. Omit/null if unknown.")
    shared_state_kind: StrictStr | None = Field(default=None,
        description="Public shared-state kind, e.g. sqlite_file. Text label, not a narrative object.")
    synchronization_scope: StrictStr | None = Field(default=None,
        description="Public synchronization scope label, e.g. shared_process_object or per_process.")
    transaction_guarantees: StrictStr | None = Field(default=None,
        description="Declared public transaction capability label, e.g. sqlite_atomic_write_transactions; not proof of a repair.")
    observed_failure_mode: StrictStr | None = Field(default=None,
        description="Public failure/symptom label. Missing facts remain unknown; claims cannot establish premises.")
    shared_object_scope: StrictStr | None = Field(default=None,
        description="Public shared-object scope label, when independently known. Omit/null otherwise.")
    sqlite_journal_mode: StrictStr | None = Field(default=None,
        description="Observed public SQLite journal-mode label, when known. Omit/null otherwise; no closed enum is imposed.")


# Official SDK still transports an object. Its disclosed schema and our pre-tool
# validation both come from this model. Validation stays here so errors never
# echo argument values through SDK-generated Pydantic exception formatting.
PublicContextArgument = Annotated[dict[str, Any], WithJsonSchema(PublicContextClaims.model_json_schema())]


class ContextClaimsConflict(ValueError):
    """A claim cannot override a known authorized public environment fact."""


def validate_public_context_claims(value):
    try:
        claims = PublicContextClaims.model_validate(value).model_dump(exclude_unset=True)
        if len(json.dumps(claims, ensure_ascii=False).encode("utf-8")) > 8192:
            raise ValueError("AEVORA_CONTEXT_SIZE_INVALID")
        return claims
    except UnicodeError:
        raise ValueError("AEVORA_CONTEXT_ENCODING_INVALID") from None
    except ValidationError as error:
        issues = []
        for detail in error.errors(include_input=False, include_context=False, include_url=False):
            field = detail["loc"][0] if detail["loc"] else "task_context"
            if field not in PublicContextClaims.model_fields:
                field = "unsupported_field"
            issues.append(str(field) + ":" + detail["type"])
        raise ValueError("AEVORA_CONTEXT_SCHEMA_INVALID: " + ", ".join(sorted(set(issues)))) from None


class LazyGraphRepository:
    """Keep MCP initialization observable when the real database is offline.

    This defers the official repository connection, without substituting any
    data or backend. Failed construction is retried only on a new tool call.
    """

    def __init__(self):
        self._repository = None

    def __getattr__(self, name):
        if self._repository is None:
            try:
                self._repository = GraphRepository.from_environment()
            except (GraphError, OSError, ValueError):
                raise GraphUnavailable("Trusted graph connection unavailable") from None
        return getattr(self._repository, name)


class ExperienceService:
    """Graph-backed public service; run authority never comes from tool input."""

    def __init__(self, *, run_id: str, public_context: dict, repository,
                 resolver_factory=None, bundle_builder=None, enable_proposals: bool = False):
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid pinned run authority")
        self.run_id = run_id
        self.public_context = normalize_context(public_context)
        if set(self.public_context) - _FACT_KEYS:
            raise ValueError("Only public applicability facts may be authorized")
        self.repository = repository
        if type(enable_proposals) is not bool:
            raise ValueError('Explicit proposal capability required')
        self.enable_proposals = enable_proposals
        if resolver_factory is None:
            from .experience_resolver import ExperienceResolver
            resolver_factory = ExperienceResolver
        if bundle_builder is None:
            from .evidence_bundle import build_evidence_bundle
            bundle_builder = build_evidence_bundle
        self.resolver = resolver_factory(repository)
        self.bundle_builder = bundle_builder

    def propose_experience(self, proposal: dict) -> dict:
        if not self.enable_proposals:
            raise ValueError('Proposal capability is disabled for this Session')
        from .candidate import CandidateLifecycle
        return CandidateLifecycle(self.repository).propose(self.run_id, proposal)

    def resolve_experience(self, task_context: dict) -> dict:
        from .experience_resolver import is_unknown
        claims = normalize_context(task_context)
        if set(claims) - _FACT_KEYS:
            raise ValueError("Undocumented context or authority field")
        facts = dict(self.public_context)
        for key, value in claims.items():
            if key in facts and not is_unknown(facts[key]):
                if type(value) is not type(facts[key]) or value != facts[key]:
                    raise ContextClaimsConflict("Claim conflicts with pinned public environment")
        # Claims are useful trace data, never a source of verified runtime
        # premises. Unknown or absent pinned facts must remain unknown until
        # the trusted caller supplies independently established public facts.
        result = self.resolver.resolve(facts)
        if not isinstance(result, dict) or result.get("status") != "AVAILABLE" or not isinstance(result.get("candidates"), list):
            raise GraphUnavailable("Graph resolver did not supply available evidence")
        if len(result["candidates"]) > 256:
            raise GraphError("Candidate collection bound exceeded")
        candidate_ids = []
        for candidate in result["candidates"]:
            if not isinstance(candidate, dict):
                raise GraphError("Malformed graph candidate")
            candidate_ids.append(validate_id(candidate.get("experience_id")))
        query_id = "query:" + self.run_id + ":" + str(uuid.uuid4())
        # A separate namespace preserves immutable pre-hardening probe Context
        # records whose provenance included caller claims.
        context_id = "context:query:trusted-public:v1:" + digest(facts)
        self.repository.put_node("Context", {"id": context_id, "facts": facts,
                                             "source_type": "trusted_public_environment"})
        query = {"id": query_id, "run_id": self.run_id, "created_at": utc_now(),
                 "task_context": facts, "pinned_public_context": self.public_context, "participant_claims": claims,
                 "candidate_experience_ids": candidate_ids,
                 "query_version": result.get("query_version", "UNAVAILABLE"),
                 "graph_snapshot_sha256": result.get("graph_snapshot_sha256", "UNAVAILABLE"),
                 "response_sha256": digest(result), "authority": "scoped_broker_run",
                 "context_authority": "TRUSTED_PINNED_PUBLIC_FACTS_ONLY",
                 "participant_claims_status": "UNVERIFIED_NOT_USED_FOR_APPLICABILITY",
                 "agent_thread_id": "UNAVAILABLE"}
        snapshots = result.get("query_snapshot_ids")
        if snapshots is not None:
            if not isinstance(snapshots, dict) or set(snapshots) != set(candidate_ids):
                raise GraphError("Query snapshot candidate declaration mismatch")
            for experience_id, snapshot_id in snapshots.items():
                content = self.repository.load_query_snapshot(validate_id(snapshot_id))
                if content.get("context") != facts or content.get("candidate", {}).get("experience_id") != experience_id:
                    raise GraphError("Query snapshot does not match actual facts/candidate")
            query.update(query_snapshot_ids=snapshots,
                         governance_evidence_sha256=result.get("governance_evidence_sha256", "UNAVAILABLE"),
                         decision_engine_version=result.get("decision_engine_version", "UNAVAILABLE"))
        self.repository.put_node("Query", query)
        self.repository.put_edge("DERIVED_FROM", "Query", query_id, "Context", context_id)
        for experience_id in candidate_ids:
            self.repository.put_edge("CONSIDERED", "Query", query_id, "Experience", experience_id)
        for snapshot_id in (snapshots or {}).values():
            self.repository.put_edge("AT_SNAPSHOT", "Query", query_id, "QuerySnapshot", snapshot_id)
        return {**result, "query_id": query_id, "run_id": self.run_id,
                "query_record_sha256": digest(query), "mcp_version": VERSION,
                "context_authority": "TRUSTED_PINNED_PUBLIC_FACTS_ONLY",
                "pinned_public_context": self.public_context,
                "participant_claims": claims,
                "participant_claims_status": "UNVERIFIED_NOT_USED_FOR_APPLICABILITY"}

    def build_evidence_bundle(self, experience_id: str, query_id: str | None = None) -> dict:
        validate_id(experience_id)
        if not self.repository.experience_was_resolved(self.run_id, experience_id):
            raise ValueError("Experience was not returned to this authorized run")
        if query_id is not None:
            query = self.repository.get_node("Query", validate_id(query_id))
            if not query or query.get("run_id") != self.run_id or experience_id not in query.get("candidate_experience_ids", []):
                raise ValueError("Snapshot query must belong to this authorized Run")
            snapshot_id = query.get("query_snapshot_ids", {}).get(experience_id)
            if not snapshot_id:
                raise ValueError("Legacy Query has no replayable snapshot")
            self.repository.require_edge("CONSIDERED","Query",query_id,"Experience",experience_id)
            self.repository.require_query_snapshot_edge(query_id, snapshot_id)
            content = self.repository.load_query_snapshot(snapshot_id)
            if content.get("candidate", {}).get("experience_id") != experience_id or content.get("context") != query.get("task_context"):
                raise GraphError("Stored snapshot association mismatch")
            return {**content["candidate"]["evidence_bundle"], "query_snapshot_id": snapshot_id,
                    "snapshot_mode": "IMMUTABLE_QUERY_REPLAY", "as_of": content["as_of"]}
        return self.bundle_builder(self.repository, experience_id)

    def record_decision(self, decision: dict) -> dict:
        allowed = {"decision_id", "query_id", "experience_id", "decision", "reason", "verification_steps"}
        if not isinstance(decision, dict) or set(decision) - allowed:
            raise ValueError("Decision contains unsupported authority or outcome fields")
        query_id, experience_id = validate_id(decision.get("query_id")), validate_id(decision.get("experience_id"))
        query = self.repository.get_node("Query", query_id)
        if not query or query.get("run_id") != self.run_id or experience_id not in query.get("candidate_experience_ids", []):
            raise ValueError("Decision must reference an actual query and candidate in this run")
        kind = decision.get("decision")
        reason = decision.get("reason")
        steps = decision.get("verification_steps", [])
        if kind not in {"APPLY", "VERIFY", "ABSTAIN"} or not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
            raise ValueError("Decision kind and bounded reason are required")
        if not isinstance(steps, list) or len(steps) > 32 or any(not isinstance(s, str) or not s.strip() or len(s) > 1000 for s in steps):
            raise ValueError("Verification steps must be bounded nonempty text")
        if kind == "VERIFY" and not steps:
            raise ValueError("VERIFY requires observable verification steps")
        identifier = decision.get("decision_id") or "decision:" + self.run_id + ":" + str(uuid.uuid4())
        validate_id(identifier)
        if not identifier.startswith("decision:" + self.run_id + ":"):
            raise ValueError("Decision identity must belong to current run")
        existing = self.repository.get_node("Decision", identifier)
        payload = {"id": identifier, "run_id": self.run_id, "query_id": query_id,
                   "experience_id": experience_id, "decision": kind, "reason": reason,
                   "verification_steps": steps, "authority": "UNTRUSTED_PARTICIPANT_CLAIM",
                   "adoption": "CLAIM_ONLY", "attribution": "UNKNOWN", "agent_thread_id": "UNAVAILABLE",
                   "created_at": existing.get("created_at") if existing else utc_now()}
        if query.get("query_snapshot_ids"):
            self.repository.require_edge("CONSIDERED","Query",query_id,"Experience",experience_id)
            payload["query_snapshot_id"] = query["query_snapshot_ids"][experience_id]
            self.repository.require_query_snapshot_edge(query_id, payload["query_snapshot_id"])
            content = self.repository.load_query_snapshot(payload["query_snapshot_id"])
            if content.get("candidate", {}).get("experience_id") != experience_id or content.get("context") != query.get("task_context"):
                raise GraphError("Decision snapshot association mismatch")
            payload["decision_engine_version"] = query.get("decision_engine_version", "UNAVAILABLE")
        receipt = self.repository.put_node("Decision", payload)
        self.repository.put_edge("RESPONDS_TO", "Decision", identifier, "Query", query_id)
        self.repository.put_edge("DECIDED", "Decision", identifier, "Experience", experience_id)
        return {"status": "RECORDED_UNTRUSTED", "decision_id": identifier, "run_id": self.run_id,
                "query_id": query_id, "experience_id": experience_id,
                "payload_sha256": receipt["payload_sha256"], "attribution": "UNKNOWN",
                "trusted_outcome": "NOT_SUBMITTED", "mcp_version": VERSION}


def create_server(service: ExperienceService):
    """Use the official SDK transport/initialization/schema machinery."""
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    from .mcp_projection import PublicProjection, ProjectionCapacityError

    projection = PublicProjection(service)

    class PublicContractServer(FastMCP):
        async def list_tools(self):
            tools = await super().list_tools()
            for tool in tools:
                if tool.name == "resolve_experience":
                    tool.inputSchema = {**tool.inputSchema, "additionalProperties": False}
            return tools

        async def call_tool(self, name, arguments):
            if name == "resolve_experience":
                if (not isinstance(arguments, dict) or "task_context" not in arguments
                        or set(arguments) - {"task_context", "cursor"}):
                    raise ValueError("AEVORA_CONTEXT_ARGUMENTS_INVALID: provide task_context and optional cursor")
                # Validate before official SDK pre_parse_json can coerce strings.
                arguments = {**arguments, "task_context": validate_public_context_claims(arguments["task_context"])}
            if name in {"resolve_experience", "build_evidence_bundle"}:
                if not isinstance(arguments, dict):
                    raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT")
                cursor = arguments.get("cursor")
                if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 256):
                    raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT")
            if name == "build_evidence_bundle":
                if (set(arguments) - {"experience_id", "query_id", "cursor", "view"}
                        or not isinstance(arguments.get("experience_id"), str)
                        or len(arguments["experience_id"]) > 240
                        or arguments.get("query_id") is not None and (
                            not isinstance(arguments["query_id"], str) or len(arguments["query_id"]) > 240)
                        or not isinstance(arguments.get("view", "bundle"), str)
                        or arguments.get("view", "bundle") not in {"bundle", "candidate"}):
                    raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT")
            return await super().call_tool(name, arguments)

    server = PublicContractServer("Aevora", instructions=(
        "Aevora supplies contextual experience evidence. Query before choosing a strategy. "
        "A query is not proof of adoption and a decision is an untrusted claim. "
        "Only the independent benchmark evaluator and trusted host can record verified outcomes."))

    def invoke(method, value):
        try:
            return method(value)
        except ProjectionCapacityError:
            raise RuntimeError("AEVORA_RESPONSE_CAPACITY_EXCEEDED") from None
        except (GraphUnavailable, OSError):
            raise RuntimeError("AEVORA_GRAPH_UNAVAILABLE") from None
        except GraphError:
            raise RuntimeError("AEVORA_GRAPH_RECORD_ERROR") from None
        except ContextClaimsConflict:
            raise ValueError("AEVORA_CONTEXT_CONFLICT: claims cannot override the authorized environment; query with task_context={} when uncertain") from None
        except (ValueError, TypeError):
            raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT") from None

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
    def resolve_experience(task_context: PublicContextArgument, cursor: str | None = None) -> dict[str, Any]:
        """Resolve public applicability facts against actual graph evidence.

        task_context may contain concurrency_scope, worker_count_known,
        shared_state_kind, synchronization_scope, transaction_guarantees,
        observed_failure_mode, shared_object_scope, sqlite_journal_mode.
        worker_count_known is boolean, not a worker count or array. All other
        fields are text labels or null. Arrays, nested objects and extra fields
        are invalid. Examples in schema are public vocabulary, not pinned values.
        Use task_context={} to query without claims. Omit or use null for unknown
        claims; missing trusted facts remain unknown. Preserve returned query_id.
        Caller claims are archived but cannot establish applicability premises.
        Responses contain bounded candidate previews with explicit evidence counts.
        Follow next_cursor (same task_context and connection) until has_more=false.
        Retrieve build_evidence_bundle using the candidate's detail_reference for
        full WHEN/WHY and counterexamples; previews disclose all omitted detail.
        Cursors expire after 900 seconds and cannot cross SDK connections/runs.
        """
        return invoke(lambda _: projection.resolve(task_context, cursor), None)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False), structured_output=True)
    def build_evidence_bundle(experience_id: str, query_id: str | None = None,
                              cursor: str | None = None, view: str = "bundle") -> dict[str, Any]:
        """Show public support, counterexamples and versions for a queried experience.

        Only IDs actually returned by a query in this run are authorized.
        Hidden tests, reference patches and private report paths are excluded.
        view=candidate with query_id retrieves the complete immutable resolver
        decision and bundle. Small responses retain the original shape. Large
        documents use lossless RFC6901 entries with document_sha256; follow ALL
        next_cursor pages with the same IDs/view/connection before concluding.
        Cursors expire after 900 seconds; restart this tool without a cursor if
        expired/evicted. No outcome or applicability is changed by pagination.
        """
        try:
            return projection.bundle(experience_id, query_id, cursor, view)
        except ProjectionCapacityError:
            raise RuntimeError("AEVORA_RESPONSE_CAPACITY_EXCEEDED") from None
        except (GraphUnavailable, OSError):
            raise RuntimeError("AEVORA_GRAPH_UNAVAILABLE") from None
        except GraphError:
            raise RuntimeError("AEVORA_GRAPH_RECORD_ERROR") from None
        except (ValueError, TypeError):
            raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT") from None

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
    def record_decision(decision: dict[str, Any]) -> dict[str, Any]:
        """Append an untrusted decision claim bound to this run's actual query.

        Required keys: query_id, experience_id, decision (APPLY/VERIFY/ABSTAIN),
        reason. VERIFY also requires verification_steps (list of concrete steps).
        Optional decision_id must start with decision:<current run_id>:.
        No caller verdict, verified flag, feedback or outcome is accepted.
        """
        return invoke(service.record_decision, decision)

    if getattr(service, "enable_proposals", False):
        @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
        def propose_experience(proposal: CandidateProposal) -> dict[str, Any]:
            """Propose UNTRUSTED conditional experience, never publish or verify it.

            Required exact fields: candidate_key (short local ID), title,
            strategy, public_summary; necessary_conditions, inapplicable_conditions
            and scope (public fact keys mapped to lists of scalar values);
            unknown_fields (public fact NAMES only), limitations (free-text lists); source_references (list of
            {kind: Query|Decision|ObservedAction, id: actual current-run ID}).
            Use unknown_fields for unproved premises. No paths, credentials,
            run_id, source_type, verified, outcome or publication authority.
            The trusted host independently establishes origin and admission.
            """
            return invoke(service.propose_experience, proposal.model_dump())
    return server


def main() -> int:
    # This trusted bootstrap precedes the official MCP newline transport. It is
    # never forwarded to Participant and contains no token or DB secret value.
    raw = sys.stdin.buffer.readline(16_385)
    if len(raw) > 16_384 or not raw.endswith(b"\n"):
        raise RuntimeError("Bounded trusted authority header required")
    authority = json.loads(raw)
    if isinstance(authority, dict) and authority.get("protocol_profile") == "aevora.mcp/2.0.0-rc2":
        from .mcp_v2 import load_configuration, V2Service, create_server as create_v2_server
        if set(authority) != {"protocol", "run_id", "public_context", "connection_id", "protocol_profile", "v2_config_path", "enable_proposals"} or authority["protocol"] != "aevora-mcp-uds-v1":
            raise RuntimeError("Invalid explicit v2 bootstrap")
        repo, grant, facts = load_configuration(authority["v2_config_path"])
        if grant.run_id != authority["run_id"]:
            raise RuntimeError("Invalid explicit v2 authority")
        create_v2_server(V2Service(repo, grant, facts, authority["connection_id"])).run(transport="stdio")
        return 0
    if not isinstance(authority, dict) or set(authority) not in (
        {"protocol", "run_id", "public_context", "connection_id"},
        {"protocol", "run_id", "public_context", "connection_id", "enable_proposals"}) or authority["protocol"] != "aevora-mcp-uds-v1":
        raise RuntimeError("Trusted MCP authority unavailable")
    service = ExperienceService(run_id=authority["run_id"], public_context=authority["public_context"],
                                repository=LazyGraphRepository(), enable_proposals=authority.get('enable_proposals', False))
    create_server(service).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
