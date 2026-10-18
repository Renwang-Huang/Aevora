"""Explicit v2 canonical contracts. Host registration, not JSON shape, conveys trust."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from functools import lru_cache
import hashlib
import json
import re
from .models import (
    canonical_json,
    digest,
    validate_id,
    LIFECYCLE_LABELS,
    LIFECYCLE_RELATIONSHIPS,
)

GRAPH_VERSION = "aevora.graph/2.0.0-rc2"
PROFILE = "aevora.mcp/2.0.0-rc2"
POLICY = "aevora.whenwhy/2.0.0-rc2"
LABELS = LIFECYCLE_LABELS | {
    "TenantState",
    "Authority",
    "PublicationManifest",
    "Run",
    "Session",
    "ToolEvent",
    "DeliveryReceipt",
    "Recommendation",
    "SnapshotChunk",
}
RELATIONS = LIFECYCLE_RELATIONSHIPS | {
    "ATTESTED_BY",
    "PUBLISHED_BY",
    "COMMITS",
    "HAS_AGENT",
    "SPAWNED",
    "HAS_SESSION",
    "IN_SESSION",
    "BY_AGENT",
    "HAS_CHUNK",
    "PRODUCED",
    "DELIVERED",
    "OF_RECOMMENDATION",
    "CITES",
    "CORRELATED_ACTION",
}
COMMON = {
    "id",
    "tenant_id",
    "record_version",
    "kind",
    "created_at",
    "source_type",
    "authority_ref",
    "visibility",
}
INDEXED = COMMON | {
    "candidate_id",
    "event_id",
    "sequence",
    "source_id",
    "source_kind",
    "target_id",
    "target_kind",
    "scope_token",
    "experience_id",
    "revision_id",
    "run_id",
    "session_id",
    "epoch",
    "authz_epoch",
    "state",
    "generation",
    "policy_version",
    "verdict",
    "valid_from",
    "valid_until",
    "chunk_index",
    "grant_generation",
    "profile",
}
MAX_RECORD = 262144
MAX_CHUNK = 65536
MAX_CHUNKS = 128
MAX_DOCUMENT = MAX_CHUNK * MAX_CHUNKS


class V2Error(ValueError):
    def __init__(self, code="GRAPH_INTEGRITY_ERROR"):
        self.code = code
        super().__init__(code)


def require(condition, code="GRAPH_INTEGRITY_ERROR"):
    if not condition:
        raise V2Error(code)


def timestamp(value):
    require(
        isinstance(value, str)
        and bool(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
            )
        )
    )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise V2Error() from None


def identity(tenant, kind, key):
    validate_id(tenant)
    require(kind in LABELS or kind in RELATIONS)
    return kind + ":" + digest([tenant, "aevora.graph/2", key])


def no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result)
        result[k] = v
    return result


def decode_json(raw):
    try:
        return json.loads(
            raw,
            object_pairs_hook=no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(V2Error()),
        )
    except (TypeError, ValueError, RecursionError):
        raise V2Error() from None


@lru_cache(maxsize=32)
def schema(name):
    return json.loads(
        files("aevora.schemas_v2").joinpath(name + ".schema.json").read_text()
    )


@lru_cache(maxsize=32)
def validator(name):
    from jsonschema import Draft202012Validator

    return Draft202012Validator(schema(name))


def validate_schema(name, value):
    require(next(validator(name).iter_errors(value), None) is None, "INVALID_INPUT")
    return value


def fact(value):
    # Cache only a positive proof keyed by immutable complete bytes; return the
    # caller's current value, never a shared mutable cached record. Authority
    # registry membership and current permissions are checked on every read.
    _fact_proof(canonical_json(value))
    return value


@lru_cache(maxsize=2048)
def _fact_proof(raw):
    value = decode_json(raw)
    validate_schema("fact", value)
    require(value["key"].split(".")[0] == value["phase"])
    if value["availability"] == "KNOWN":
        if value["key"] == "task.worker_count":
            require(type(value["value"]) is int)
        elif value["key"] == "task.worker_count_known":
            require(type(value["value"]) is bool)
        else:
            require(type(value["value"]) is str)
        timestamp(value["observed_at"])
        require(bool(value["source_refs"]) and bool(value["authority_ref"]))
    return None


def scope(value):
    _scope_proof(canonical_json(value))
    return value


@lru_cache(maxsize=2048)
def _scope_proof(raw):
    value = decode_json(raw)
    require(isinstance(value, dict) and len(value) <= 32)
    properties = schema("propose_experience.arguments")["properties"]["proposal"][
        "properties"
    ]["scope"]["properties"]
    from jsonschema import Draft202012Validator

    for k, values in value.items():
        if k == "task.worker_count":
            require(all(type(v) is int for v in values))
        require(
            k in properties
            and not list(Draft202012Validator(properties[k]).iter_errors(values))
        )
    return None


def native(payload):
    return {
        **{k: v for k, v in payload.items() if k in INDEXED and v is not None},
        "payload_json": canonical_json(payload),
        "payload_sha256": digest(payload),
    }


def record(
    tenant,
    kind,
    key,
    *,
    authority="trusted-host",
    created=None,
    source="trusted_host",
    visibility="PUBLIC",
    **body,
):
    result = dict(
        id=identity(tenant, kind, key),
        tenant_id=tenant,
        record_version=GRAPH_VERSION,
        kind=kind,
        created_at=created
        if created is not None
        else datetime.now(timezone.utc).isoformat(),
        source_type=source,
        authority_ref=authority,
        visibility=visibility,
        identity_key=key,
        **body,
    )
    validate_record(result, tenant)
    return result


def validate_record(value, tenant):
    require(
        isinstance(value, dict)
        and COMMON <= set(value)
        and value["tenant_id"] == tenant
    )
    require(
        value["kind"] in LABELS | RELATIONS and value["record_version"] == GRAPH_VERSION
    )
    required = {
        "Experience": {"scope_token", "title", "strategy"},
        "ExperienceRevision": {
            "experience_id",
            "declared_rule_id",
            "supersedes_ids",
            "scope",
            "valid_from",
            "revision_kind",
        },
        "Rule": {"scope", "scope_token", "premise_ids", "strategy_sha256"},
        "Premise": {"fact_key", "phase", "mode", "allowed_values"},
        "Authority": {
            "authority_class",
            "independence",
            "state",
            "verifier_version",
            "source_sha256",
        },
        "VerifiedOutcome": {
            "task_id",
            "verdict",
            "result_sha256",
            "artifact_sha256",
            "failure_class",
        },
        "Evidence": {"revision_id", "outcome_id", "artifact_sha256", "strategy_sha256"},
        "Context": {"task_id", "facts"},
        "Task": {"facts"},
        "GovernanceEvent": {
            "event_type",
            "effective_at",
            "scope",
            "target_id",
            "target_label",
        },
        "TenantState": {"epoch", "authz_epoch", "generation", "policy_version"},
        "Session": {
            "run_id",
            "session_id",
            "grant_generation",
            "profile",
            "state",
            "valid_until",
        },
        "PublicationManifest": {"experience_id", "epoch", "document"},
        "QuerySnapshot": {"document"},
    }
    require(required.get(value["kind"], set()) <= set(value))
    validate_id(value["id"])
    require(value["id"] == identity(tenant, value["kind"], value.get("identity_key")))
    validate_id(value["authority_ref"])
    timestamp(value["created_at"])
    require(value["visibility"] in {"PUBLIC", "HOST_ONLY"})
    require(len(canonical_json(value).encode()) <= MAX_RECORD, "CAPACITY_EXCEEDED")
    for k in ("epoch", "authz_epoch", "chunk_index"):
        if k in value:
            require(type(value[k]) is int and value[k] >= 0)
    if value["kind"] == "Premise":
        scope({value["fact_key"]: value["allowed_values"]})
        require(
            value["phase"] in {"task", "artifact_before"}
            and value["fact_key"].split(".")[0] == value["phase"]
        )
        require(value["mode"] in {"necessary", "exclusion"})
    if value["kind"] in {"Context", "Task"}:
        for k, v in value.get("facts", {}).items():
            require(k == v["key"])
            fact(v)
    if value["kind"] == "SnapshotChunk":
        require(
            isinstance(value.get("text"), str)
            and len(value["text"].encode()) <= MAX_CHUNK,
            "CAPACITY_EXCEEDED",
        )
        require(
            hashlib.sha256(value["text"].encode()).hexdigest() == value["chunk_sha256"]
        )
    return value


def decode(properties, tenant):
    require(isinstance(properties, dict))
    value = decode_json(properties.get("payload_json"))
    validate_record(value, tenant)
    require(properties == native(value))
    return value


def edge(tenant, kind, source, target, **body):
    require(kind in RELATIONS and source["tenant_id"] == target["tenant_id"] == tenant)
    return record(
        tenant,
        kind,
        [source["kind"], source["id"], target["kind"], target["id"]],
        source_id=source["id"],
        source_kind=source["kind"],
        target_id=target["id"],
        target_kind=target["kind"],
        **body,
    )


@dataclass(frozen=True)
class TenantBinding:
    tenant_id: str
    graph_name: str

    def __post_init__(self):
        validate_id(self.tenant_id)
        validate_id(self.graph_name)
        require(self.graph_name.startswith("aevora_v2_"), "UNAUTHORIZED")


@dataclass
class TrustRegistry:
    # Constructed only on trusted host. No public method registers an authority.
    authorities: dict = field(default_factory=dict)
    outcomes: dict = field(default_factory=dict)
    fact_sources: dict = field(default_factory=dict)
    publications: dict = field(default_factory=dict)

    def verify_fact(self, value):
        fact(value)
        if value["availability"] == "KNOWN":
            require(
                value["authority_class"]
                in {"HOST_DECLARED_TASK", "HOST_OBSERVED", "INDEPENDENT_ORACLE"}
            )
            require(self.fact_sources.get(digest(value)) == value["authority_ref"])

    def verify_outcome(self, outcome, authority):
        require(
            authority["authority_class"]
            in {"INDEPENDENT_ORACLE", "ENGINEERING_VERIFIER"}
        )
        require(
            authority.get("independence") == "INDEPENDENT"
            and authority.get("state") == "ACTIVE"
        )
        require(self.authorities.get(authority["id"]) == digest(authority))
        if 'valid_from' in authority or 'valid_until' in authority:
            # Verifier registration permits issuance during this interval.
            # Historical certificates remain checkable after credential expiry;
            # current mutation permission is checked again by the Host fence.
            require('valid_from' in authority and 'valid_until' in authority)
            require(timestamp(authority['valid_from']) <= timestamp(outcome['created_at'])
                    < timestamp(authority['valid_until']))
        require(outcome["authority_ref"] == authority["id"])
        require(self.outcomes.get(outcome["id"]) == digest(outcome))
        require(bool(re.fullmatch("[0-9a-f]{64}", outcome.get("result_sha256", ""))))
