"""Validated, append-only graph values and deliberately narrow public projections."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

LEGACY_SCHEMA_VERSION = "aevora.graph/1.0"
LEGACY_QUERY_VERSION = "aevora.multihop/1.0"
SCHEMA_VERSION = "aevora.graph/1.1"
QUERY_VERSION = "aevora.multihop/1.1"
RULE_VERSION = "aevora.when/1.1"
LEGACY_LABELS = frozenset({"Experience", "ExperienceRevision", "Rule", "Premise", "Evidence",
                    "VerifiedOutcome", "Context", "Task", "Agent", "Query", "Decision",
                    "ObservedAction", "Feedback", "AuditEvent", "Schema"})
LEGACY_RELATIONSHIPS = frozenset({"HAS_REVISION", "USES_RULE", "REQUIRES", "SUPPORTED_BY",
                           "COUNTEREXAMPLE", "OBSERVED_OUTCOME", "VERIFIES", "IN_CONTEXT",
                           "FOR_TASK", "QUERIED", "CONSIDERED", "DECIDED", "CLAIMS_ADOPTION",
                           "OBSERVED_ACTION", "HAS_FEEDBACK", "FROM_OUTCOME", "REVISES",
                           "RESPONDS_TO", "DERIVED_FROM"})
LABELS = LEGACY_LABELS | {"GovernanceEvent", "QuerySnapshot"}
RELATIONSHIPS = LEGACY_RELATIONSHIPS | {"SUPERSEDES", "GOVERNS", "AT_SNAPSHOT"}
LIFECYCLE_SCHEMA_VERSION = "aevora.graph/1.2"
LIFECYCLE_LABELS = LABELS | {"Candidate", "LifecycleHead", "CandidateEvent", "SourceVerification", "ExternalObservation"}
LIFECYCLE_RELATIONSHIPS = RELATIONSHIPS | {"HAS_LIFECYCLE", "HAS_CANDIDATE_EVENT", "PREVIOUS_EVENT", "HAS_SOURCE_VERIFICATION", "PUBLISHED_FROM"}
PUBLIC_CONTEXT_FACTS = frozenset({"concurrency_scope", "worker_count", "worker_count_known",
    "shared_state_kind", "synchronization_scope", "transaction_guarantees", "observed_failure_mode",
    "shared_object_scope", "sqlite_journal_mode", "operation_semantics", "authority_model",
    "clock_domain", "failure_domain", "contract_version", "lease_expiry_semantics",
    "authority_validation", "supported_operation_set"})
SOURCE_TYPES = frozenset({"natural_agent_run", "maintainer_seed", "synthetic_or_test_fixture"})
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$")


class GraphError(RuntimeError):
    """Aevora's graph operation failed."""


class GraphUnavailable(GraphError):
    """Database/SDK connection is unavailable; callers must not use a fallback corpus."""


class ImmutableConflict(GraphError):
    """The same stable identifier was presented with different bytes."""


class InvalidRecord(ValueError):
    """A record does not satisfy the public graph contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidRecord("Record must contain finite JSON values") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_id(value: Any) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise InvalidRecord("Stable id must be 1..240 allowlisted ASCII characters")
    return value


def schema_catalog(version: str) -> dict:
    """Exact source-supported schemas; old checkpoints keep their own contract."""
    if version == LEGACY_SCHEMA_VERSION:
        return {"schema_version": version, "query_version": LEGACY_QUERY_VERSION,
                "labels": LEGACY_LABELS, "relationships": LEGACY_RELATIONSHIPS}
    if version == SCHEMA_VERSION:
        return {"schema_version": version, "query_version": QUERY_VERSION,
                "labels": LABELS, "relationships": RELATIONSHIPS}
    if version == LIFECYCLE_SCHEMA_VERSION:
        return {"schema_version": version, "query_version": QUERY_VERSION,
                "labels": LIFECYCLE_LABELS, "relationships": LIFECYCLE_RELATIONSHIPS}
    raise InvalidRecord("Unsupported graph schema version")


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise InvalidRecord("Timezone-aware timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidRecord("Invalid timestamp") from None
    if result.tzinfo is None:
        raise InvalidRecord("Timezone-aware timestamp required")
    return result.astimezone(timezone.utc)


def validate_scope(value: Any) -> dict:
    if not isinstance(value, dict) or len(value) > 32 or set(value) - PUBLIC_CONTEXT_FACTS:
        raise InvalidRecord("Scope requires allowlisted public semantic facts")
    for values in value.values():
        if not isinstance(values, list) or not 1 <= len(values) <= 32:
            raise InvalidRecord("Scope values must be a bounded nonempty list")
        if any(v is None or isinstance(v, (dict, list)) for v in values):
            raise InvalidRecord("Scope values must be known scalars")
    return json.loads(canonical_json(value))


def validate_record(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    if label not in LIFECYCLE_LABELS:
        raise InvalidRecord("Unknown graph label")
    if not isinstance(payload, dict):
        raise InvalidRecord("Record payload must be an object")
    validate_id(payload.get("id"))
    encoded = canonical_json(payload)
    if len(encoded.encode("utf-8")) > 256 * 1024:
        raise InvalidRecord("Record exceeds 256 KiB")
    if label == "Experience":
        if payload.get("source_type") not in SOURCE_TYPES:
            raise InvalidRecord("Experience requires explicit source_type")
        for field in ("strategy", "title", "public_summary"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise InvalidRecord(f"Experience requires nonempty {field}")
    if label == "Evidence":
        if payload.get("source_type") not in SOURCE_TYPES:
            raise InvalidRecord("Evidence requires explicit source_type")
        if not isinstance(payload.get("public_summary"), str):
            raise InvalidRecord("Evidence requires public_summary")
    if label == "VerifiedOutcome":
        for field in ("run_id", "submission_digest", "evaluator_fingerprint",
                      "test_suite_fingerprint", "verifier_identity"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise InvalidRecord(f"VerifiedOutcome requires {field}")
        if payload.get("verdict") not in {"PASS", "FAIL", "ERROR", "TIMEOUT", "NOT_IMPLEMENTED"}:
            raise InvalidRecord("VerifiedOutcome requires a real verdict")
        if "verified" in payload:
            raise InvalidRecord("Boolean verified is not an authority credential")
    if label == "Premise":
        validate_id(payload.get("fact_key"))
        values = payload.get("allowed_values")
        if not isinstance(values, list) or not values or len(values) > 32:
            raise InvalidRecord("Premise requires nonempty bounded allowed_values")
        if any(v is None or isinstance(v, (dict, list)) for v in values):
            raise InvalidRecord("Premise values must be known JSON scalars")
        if not isinstance(payload.get("required", True), bool):
            raise InvalidRecord("Premise required must be boolean")
    if label == "ExperienceRevision" and payload.get("revision_kind") == "rule_publication":
        validate_id(payload.get("experience_id")); validate_id(payload.get("declared_rule_id"))
        reason = payload.get("revision_reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
            raise InvalidRecord("Rule publication requires a bounded public reason")
        validate_id(payload.get("publication_audit_id"))
        validate_scope(payload.get("scope", {}))
        if payload.get("source_type") not in SOURCE_TYPES:
            raise InvalidRecord("Rule publication requires explicit source_type")
        predecessors = payload.get("supersedes_ids")
        if not isinstance(predecessors, list) or len(predecessors) > 32 or len(set(predecessors)) != len(predecessors):
            raise InvalidRecord("Invalid revision predecessor declaration")
        for predecessor in predecessors:
            validate_id(predecessor)
        parse_timestamp(payload.get("valid_from"))
        if payload.get("valid_until") is not None and parse_timestamp(payload["valid_until"]) <= parse_timestamp(payload["valid_from"]):
            raise InvalidRecord("Invalid revision validity interval")
    if label == "GovernanceEvent":
        allowed = {"id", "target_id", "target_label", "event_type", "source_type", "public_reason",
                   "scope", "effective_at", "created_at", "material_fact_keys", "completion_audit_id",
                   "authority", "source_reference_sha256"}
        if set(payload) - allowed or payload.get("authority") != "TRUSTED_HOST_GOVERNANCE":
            raise InvalidRecord("Unsupported governance authority or fields")
        if payload.get("target_label") not in {"Evidence", "ExperienceRevision"}:
            raise InvalidRecord("Invalid governance target")
        validate_id(payload.get("target_id")); validate_id(payload.get("completion_audit_id"))
        if payload.get("event_type") not in {"withdraw", "expire", "restrict_scope"}:
            raise InvalidRecord("Invalid governance event type")
        if payload.get("source_type") not in SOURCE_TYPES:
            raise InvalidRecord("Governance requires explicit source_type")
        if not isinstance(payload.get("public_reason"), str) or not 1 <= len(payload["public_reason"]) <= 4000:
            raise InvalidRecord("Bounded governance reason required")
        validate_scope(payload.get("scope", {}))
        keys = payload.get("material_fact_keys", [])
        if not isinstance(keys, list) or len(keys) > 32 or len(set(keys)) != len(keys) or set(keys) - PUBLIC_CONTEXT_FACTS:
            raise InvalidRecord("Invalid material scope keys")
        parse_timestamp(payload.get("effective_at")); parse_timestamp(payload.get("created_at"))
    if label == "QuerySnapshot":
        content = payload.get("content")
        if not isinstance(content, dict) or payload.get("content_sha256") != digest(content):
            raise InvalidRecord("Snapshot content digest mismatch")
        if payload["id"] != "snapshot:" + digest(content):
            raise InvalidRecord("Snapshot identity does not match actual content")
    if label in LIFECYCLE_LABELS - LABELS:
        from .candidate import validate_lifecycle_record
        validate_lifecycle_record(label, payload)
    return json.loads(encoded)


def normalize_context(context: dict[str, Any]) -> dict[str, Any]:
    """Unknown facts remain unknown. Nested claims and episode labels do not decide rules."""
    if not isinstance(context, dict) or len(context) > 64:
        raise InvalidRecord("Context must be a bounded object")
    for key, value in context.items():
        validate_id(key)
        if isinstance(value, (dict, list)):
            raise InvalidRecord("Context facts must be scalar")
    return json.loads(canonical_json(context))


_PUBLIC_FIELDS = {
    "Experience": ("id", "strategy", "title", "source_type", "created_at", "public_summary", "limitations",
                   "origin_run_id", "origin_patch_sha256", "publication_candidate_id"),
    "ExperienceRevision": ("id", "experience_id", "created_at", "revision_reason", "attribution",
        "revision_kind", "declared_rule_id", "scope", "valid_from", "valid_until", "source_type",
        "supersedes_ids", "publication_audit_id", "query_snapshot_ids", "base_revision_ids"),
    "Rule": ("id", "version", "public_description", "premise_ids", "premise_count"),
    "Premise": ("id", "fact_key", "allowed_values", "required", "public_description"),
    "Evidence": ("id", "source_type", "public_summary", "created_at", "source_run_id", "attribution"),
    "VerifiedOutcome": ("id", "run_id", "verdict", "submission_digest", "evaluator_fingerprint",
                        "test_suite_fingerprint", "test_count", "source_type", "attribution"),
    "Context": ("id", "facts", "source_type"),
    "Task": ("id", "public_title", "scenario_version"),
    "GovernanceEvent": ("id", "target_id", "target_label", "event_type", "source_type", "public_reason",
        "scope", "effective_at", "created_at", "material_fact_keys", "completion_audit_id", "authority"),
}


def public_record(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Allowlist projection, never recursively guessing which private fields are safe."""
    result = {key: payload[key] for key in _PUBLIC_FIELDS.get(label, ("id",)) if key in payload}
    if label == "Context" and "facts" in result:
        # Context nodes originate from the trusted bridge; only documented public facts leave it.
        result["facts"] = {key: value for key, value in result["facts"].items() if key in PUBLIC_CONTEXT_FACTS}
    return result
