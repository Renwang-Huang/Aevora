"""Experience accountability data contracts and an explicitly disabled adapter.

No lookup, decision storage, outcome feedback, MCP, or graph service is
implemented. Replacing the adapter must not grant access to private evaluators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class ExperienceStatus(StrEnum):
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class DecisionKind(StrEnum):
    APPLY = "APPLY"
    VERIFY = "VERIFY"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ExperienceContext:
    run_id: str
    episode_id: str
    scenario_version: str
    topology: str | None = None
    concurrency: str | None = None
    shared_state: str | None = None
    public_facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperienceQuery:
    context: ExperienceContext
    question: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperienceEvidence:
    source_run_id: str
    report_reference: str | None = None
    verified: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if self.verified and not self.report_reference:
            raise ValueError("Verified evidence requires an independent report reference")


@dataclass(frozen=True)
class ExperienceCandidate:
    experience_id: str
    strategy: str
    context: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[ExperienceEvidence, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceBundle:
    context: ExperienceContext
    candidates: tuple[ExperienceCandidate, ...]
    evidence: tuple[ExperienceEvidence, ...] = ()
    applicability_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperienceDecision:
    context: ExperienceContext
    experience_id: str
    decision: DecisionKind
    reason: str
    evidence_references: tuple[str, ...] = ()
    verification_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", DecisionKind(self.decision))
        if not self.reason.strip():
            raise ValueError("Experience decisions require a reason")
        if self.decision is DecisionKind.VERIFY and not self.verification_steps:
            raise ValueError("VERIFY requires concrete verification steps")


@dataclass(frozen=True)
class ExperienceOutcome:
    context: ExperienceContext
    overall_status: str
    report_reference: str | None = None
    decision_reference: str | None = None
    independently_verified: bool = False

    def __post_init__(self) -> None:
        if self.overall_status not in {"PASS", "FAIL", "ERROR", "TIMEOUT", "NOT_IMPLEMENTED"}:
            raise ValueError("Outcome must use an evaluation status")
        if self.independently_verified and not self.report_reference:
            raise ValueError("Verified outcomes require an independent report reference")


@dataclass(frozen=True)
class ResolveResponse:
    status: ExperienceStatus
    candidates: tuple[ExperienceCandidate, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class EvidenceResponse:
    status: ExperienceStatus
    bundle: EvidenceBundle | None = None
    reason: str = ""


@dataclass(frozen=True)
class RecordDecisionResponse:
    status: ExperienceStatus
    decision_reference: str | None = None
    recorded: bool = False
    reason: str = ""


@dataclass(frozen=True)
class SubmitOutcomeResponse:
    status: ExperienceStatus
    outcome_reference: str | None = None
    submitted: bool = False
    reason: str = ""


@runtime_checkable
class ExperienceAdapter(Protocol):
    def resolve_experience(self, query: ExperienceQuery) -> ResolveResponse:
        ...

    def build_evidence_bundle(
        self, context: ExperienceContext, candidates: tuple[ExperienceCandidate, ...]
    ) -> EvidenceResponse:
        ...

    def record_decision(self, decision: ExperienceDecision) -> RecordDecisionResponse:
        ...

    def submit_outcome(self, outcome: ExperienceOutcome) -> SubmitOutcomeResponse:
        ...


class DisabledExperienceAdapter:
    """Stateless null adapter: every call reports DISABLED and stores nothing."""

    status = ExperienceStatus.DISABLED
    reason = "Experience integration is disabled in Phase 1"

    def resolve_experience(self, query: ExperienceQuery) -> ResolveResponse:
        return ResolveResponse(status=self.status, reason=self.reason)

    def build_evidence_bundle(
        self, context: ExperienceContext, candidates: tuple[ExperienceCandidate, ...]
    ) -> EvidenceResponse:
        return EvidenceResponse(status=self.status, reason=self.reason)

    def record_decision(self, decision: ExperienceDecision) -> RecordDecisionResponse:
        return RecordDecisionResponse(status=self.status, reason=self.reason)

    def submit_outcome(self, outcome: ExperienceOutcome) -> SubmitOutcomeResponse:
        return SubmitOutcomeResponse(status=self.status, reason=self.reason)

    def metadata(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "adapter": type(self).__name__,
            "hits": None,
            "decisions": None,
            "feedback": None,
            "reason": self.reason,
        }


def response_to_dict(
    response: ResolveResponse | EvidenceResponse | RecordDecisionResponse | SubmitOutcomeResponse,
) -> dict[str, Any]:
    return asdict(response)
