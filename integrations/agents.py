"""Submission and trace contracts for manual and future native Codex execution.

This module describes observations, not an agent scheduler. A manually supplied
workspace or patch is an artifact; receiving it is not evidence of agent work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class SubmissionKind(StrEnum):
    WORKSPACE = "workspace"
    PATCH = "patch"


class ExecutionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass(frozen=True)
class TaskInput:
    episode_id: str
    scenario_version: str
    public_task: str
    public_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    workspace: str
    started_at: str = field(default_factory=utc_timestamp)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmissionArtifact:
    kind: SubmissionKind
    reference: str
    sha256: str | None = None
    received_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", SubmissionKind(self.kind))
        if not self.reference:
            raise ValueError("A submission must reference a real workspace or patch")
        if self.sha256 is not None and (
            len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("sha256 must be a lowercase SHA256 hex digest")


@dataclass(frozen=True)
class ExecutionTrace:
    run_id: str
    source: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    availability: Availability = Availability.AVAILABLE
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    submission: SubmissionArtifact | None
    trace: tuple[ExecutionTrace, ...] = ()
    errors: tuple[str, ...] = ()
    agent_data_availability: Availability = Availability.UNAVAILABLE
    agent_assignments: tuple[dict[str, Any], ...] | None = None
    agent_metrics: dict[str, Any] | None = None
    runtime_metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class AgentAdapter(Protocol):
    def execute(self, task: TaskInput, context: ExecutionContext) -> ExecutionResult:
        """Return actual artifacts and observations for a task execution."""
        ...


def _artifact_digest(path: Path, kind: SubmissionKind) -> str:
    """Hash supplied bytes; do not follow links into files outside a submission."""
    if path.is_symlink():
        raise ValueError("Submission references must not be symbolic links")
    if kind is SubmissionKind.PATCH:
        if not path.is_file():
            raise ValueError("A patch submission must be a file")
        return sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise ValueError("A workspace submission must be a directory")
    digest = sha256()
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("Workspace submissions must not contain symbolic links")
        if item.is_file():
            relative_path = item.relative_to(path).as_posix().encode("utf-8")
            content = item.read_bytes()
            digest.update(len(relative_path).to_bytes(8, "big"))
            digest.update(relative_path)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return digest.hexdigest()


class ManualSubmissionAdapter:
    """Receive an existing artifact without applying patches or running agents."""

    def __init__(self, submission: SubmissionArtifact) -> None:
        self.submission = submission

    def execute(self, task: TaskInput, context: ExecutionContext) -> ExecutionResult:
        path = Path(self.submission.reference).absolute()
        try:
            actual_digest = _artifact_digest(path, self.submission.kind)
            if self.submission.sha256 is not None and self.submission.sha256 != actual_digest:
                raise ValueError("Submission digest does not match the supplied artifact")
        except (OSError, ValueError) as error:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                submission=None,
                errors=(str(error),),
                trace=(ExecutionTrace(
                    run_id=context.run_id,
                    source="manual_submission",
                    event_type="submission.rejected",
                    payload={"episode_id": task.episode_id, "error": str(error)},
                ),),
            )
        artifact = replace(
            self.submission,
            reference=str(path),
            sha256=actual_digest,
            received_at=utc_timestamp(),
        )
        return ExecutionResult(
            status=ExecutionStatus.SUBMITTED,
            submission=artifact,
            trace=(ExecutionTrace(
                run_id=context.run_id,
                source="manual_submission",
                event_type="submission.received",
                payload={
                    "episode_id": task.episode_id,
                    "scenario_version": task.scenario_version,
                    "submission": asdict(artifact),
                },
            ),),
        )


class CodexNativeAdapter:
    """Legacy, unconfigured Phase1 entry. Use configured CodexAgentAdapter.

    Retained for the original contract; this class never starts an unisolated
    process or invents execution. The real implementation is codex_agent.py.
    """

    def execute(self, task: TaskInput, context: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError(
            "Legacy unconfigured execution is NOT_IMPLEMENTED; use CodexAgentAdapter with isolated runtime configuration"
        )
