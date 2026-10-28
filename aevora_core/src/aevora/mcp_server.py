"""Aevora's public tools, served by the official MCP Python SDK.

The trusted broker supplies immutable run authority before MCP initialization.
This module and the graph password file are never mounted in Participant.
Participant decisions are claims; this service cannot create trusted outcomes.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from typing import Any

from .graph_repository import GraphRepository
from .proposal_contract import CandidateProposal
from .observation_contract import ObservationUseReport
from .models import GraphError, GraphUnavailable, canonical_json, digest, normalize_context, utc_now, validate_id, PUBLIC_CONTEXT_FACTS


AGENT_INSTRUCTIONS = (
    "When Aevora is enabled, proactively call resolve_experience once before choosing an approach "
    "for nontrivial coding, debugging, or design tasks; do not wait for the user to mention Aevora. "
    "Skip trivial requests and respect explicit opt-outs. Pass a short public task description as query; "
    "use task_context={} when facts are unknown. Query text affects relevance only, never trusted facts. "
    "Native task recall defaults to bounded summaries; use build_evidence_bundle with query_id for complete evidence. "
    "Caller claims do not establish applicability. If no experience is returned, optionally search_observations "
    "with concrete task keywords and mode=ranked on native SQLite for UNTRUSTED investigative leads, then continue normal work. "
    "Observation search never establishes APPLY, verified facts or outcomes; check actual state and evidence. "
    "After investigating an observation, record its actual use or rejection with record_observation_use when supported; "
    "the report is an untrusted claim, not proof of exposure, adoption or outcome. "
    "For returned experience IDs, inspect evidence and record the actual APPLY/VERIFY/ABSTAIN choice; "
    "do not invent IDs or decisions when the result is empty. After meaningful work, propose reusable "
    "public observations with limitations, if proposal tools are enabled. Empty necessary_conditions "
    "and scope are allowed for unscoped UNTRUSTED drafts; never invent facts to fill them. "
    "Such drafts cannot be admitted or published; once bounds are established, submit a new bounded "
    "proposal with a new candidate_key, retaining the original draft history. "
    "Report tool failures briefly and continue independent work when possible. No credentials, private "
    "paths or hidden test material in proposals. Decisions and self-tests do not prove adoption, "
    "verified outcomes or causal benefit. Querying or proposing does not authorize publication."
)

VERSION = "aevora.mcp/1.1"
_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
_FACT_KEYS = PUBLIC_CONTEXT_FACTS


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

    def search_observations(self, args:dict)->dict:
        from .observations import search
        return search(self.repository,args['query'],args.get('limit',10))

    def resolve_experience(self, task_context: dict, query: str | None = None,
                           limit: int = 5, detail: str = 'summary') -> dict:
        if query is not None:
            raise ValueError('Task-text recall requires the native SQLite runtime; Python reference supports condition diagnostics only')
        from .experience_resolver import is_unknown
        claims = normalize_context(task_context)
        if set(claims) - _FACT_KEYS:
            raise ValueError("Undocumented context or authority field")
        facts = dict(self.public_context)
        for key, value in claims.items():
            if key in facts and not is_unknown(facts[key]):
                if type(value) is not type(facts[key]) or value != facts[key]:
                    raise ValueError("Claim conflicts with pinned public environment")
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

    server = FastMCP("Aevora", instructions=AGENT_INSTRUCTIONS)

    def invoke(method, value):
        try:
            return method(value)
        except (GraphUnavailable, OSError):
            raise RuntimeError("AEVORA_GRAPH_UNAVAILABLE") from None
        except GraphError:
            raise RuntimeError("AEVORA_GRAPH_RECORD_ERROR") from None
        except (ValueError, TypeError):
            raise ValueError("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT") from None

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
    def resolve_experience(task_context: dict[str, Any], query: str | None = None,
                           limit: int = 5, detail: str = 'summary') -> dict[str, Any]:
        """Recall task-relevant experience, then check pinned facts against graph evidence.

        Native SQLite: query is a short public task description (max 1000 characters;
        no credentials/private paths). Missing query returns TASK_QUERY_REQUIRED and
        no recommendations. limit is 1..20 (default 5); detail is summary or full.
        Summaries contain bounded excerpts; fetch complete evidence with query_id.
        Native uses BM25, Chinese fragments and disclosed aliases; a protected
        optional local embedding adapter adds cosine/RRF hybrid retrieval.
        Provider failure is an explicit lexical fallback. Relevance is never
        verified applicability or task utility; actual semantic quality depends
        on the configured model and needs separate evaluation.
        task_context claims cannot establish or override trusted Host/target_* facts.
        Preserve query_id. Python reference supports legacy condition diagnostics
        without query; explicit task-text recall requires the native runtime.
        """
        if query is not None:
            return invoke(service.resolve_experience, task_context, query, limit, detail)
        return invoke(service.resolve_experience, task_context)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False), structured_output=True)
    def search_observations(query:str,limit:int=10,mode:str='literal')->dict[str,Any]:
        """Search public untrusted observations across this project using concrete literal keywords.

        Native SQLite additionally accepts mode=ranked: FTS5/BM25, Chinese fragments
        and a disclosed engineering alias list; bounded public excerpts. Default
        literal preserves old substring behavior; Python reference is literal only.
        Ranked native results include up to two ID-ordered untrusted usage claims;
        they do not change rank or establish exposure, adoption or outcomes.
        Native auto-diagnostic groups can show an unverified source project hint,
        source IDs and a count of captured records, not a count of proven failures.
        Returns at most 20 matches. These are investigative leads only,
        never verified experience or APPLY. Original Run and current lifecycle
        remain visible; rejected/withdrawn records are history, not advice.
        """
        if mode != 'literal':
            raise ValueError('Ranked observation recall requires the native SQLite runtime')
        return invoke(service.search_observations,{'query':query,'limit':limit})

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False), structured_output=True)
    def read_observation_sources(candidate_id: str, after: str = '', limit: int = 10) -> dict[str, Any]:
        """Read bounded public sources for a candidate in the pinned target project.

        Native SQLite only. limit 1..20; use next_cursor for another page.
        Source observations are untrusted and never prove outcomes or APPLY.
        Refresh from the start to include later sources with lower IDs.
        Unknown target project or a different project is refused.
        """
        raise ValueError('Observation source reads require the native SQLite runtime')

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False), structured_output=True)
    def build_evidence_bundle(experience_id: str, query_id: str | None = None) -> dict[str, Any]:
        """Show public support, counterexamples and versions for a queried experience.

        Only IDs actually returned by a query in this run are authorized.
        Hidden tests, reference patches and private report paths are excluded.
        """
        try:
            return service.build_evidence_bundle(experience_id, query_id)
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

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
    def record_observation_use(report: ObservationUseReport) -> dict[str, Any]:
        """Record an untrusted report about an existing observation on native SQLite.

        Supply candidate_id, a stable report_key, purpose (DEBUGGING, PLANNING,
        IMPLEMENTATION, VALIDATION or OTHER), disposition (INVESTIGATED, REUSED,
        REJECTED, NOT_RELEVANT or INCONCLUSIVE), and a short public reason.
        Optional elapsed_seconds is a reported integer from 0 to 86400. Reusing a
        key with changed content fails. A candidate is checked to exist, but the
        report does not prove exposure, adoption, a verified outcome or benefit.
        Native SQLite only; the Python graph reference explicitly refuses it.
        Never include private paths, credentials or hidden test material.
        """
        raise ValueError('Observation usage reports require the native SQLite runtime')

    if getattr(service, "enable_proposals", False):
        @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False), structured_output=True)
        def propose_experience(proposal: CandidateProposal) -> dict[str, Any]:
            """Propose UNTRUSTED conditional experience, never publish or verify it.

            Required exact fields: candidate_key (short local ID), title,
            strategy, public_summary; necessary_conditions, inapplicable_conditions
            and scope (public fact keys mapped to lists of scalar values);
            unknown_fields (public fact NAMES only), limitations (free-text lists); source_references (list of
            {kind: Query|Decision|ObservedAction, id: actual current-run ID}).
            Empty necessary_conditions and scope are accepted as unscoped drafts, never admitted or published.
            Never fabricate facts to fill these fields. Use unknown_fields for unproved public premises. No paths, credentials,
            run_id, source_type, verified, outcome or publication authority.
            The trusted host independently establishes origin and admission.
            """
            return invoke(service.propose_experience, proposal.model_dump(exclude_none=True))
    return server


def main() -> int:
    # This trusted bootstrap precedes the official MCP newline transport. It is
    # never forwarded to Participant and contains no token or DB secret value.
    raw = sys.stdin.buffer.readline(16_385)
    if len(raw) > 16_384 or not raw.endswith(b"\n"):
        raise RuntimeError("Bounded trusted authority header required")
    authority = json.loads(raw)
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
