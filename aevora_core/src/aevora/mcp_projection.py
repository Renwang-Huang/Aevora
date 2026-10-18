"""Bound public wire projections; preserve the resolver's complete snapshots.

The SDK intentionally emits both text and structured content. Budgets below
measure that actual encoding, including its escaping, rather than counting
characters. Continuations are opaque, connection-local capabilities; every
read rechecks the existing graph authorization. No applicability rule lives here.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
import hashlib
import hmac
import json
import secrets
import threading
import time

import pydantic_core
from mcp.types import JSONRPCResponse

from .mcp_broker import MAX_MESSAGE_BYTES, _message
from .models import digest

WIRE_BUDGET = 196_608  # Keep the existing 262144-byte broker limit unchanged.
PAGE_BUDGET = 24_576
TTL_SECONDS = 900
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_DOCUMENTS = 32
VERSION = "aevora.public-projection/1.0"


class ProjectionCapacityError(ValueError):
    """A finite public projection resource limit, never a successful result."""


def wire_bytes(value: dict) -> bytes:
    """mcp1.26 dict conversion plus a worst-case legal 128-character RPC ID."""
    text = pydantic_core.to_json(value, indent=2).decode()
    message = JSONRPCResponse(jsonrpc="2.0", id="\0" * 128, result={
        "content": [{"type": "text", "text": text}],
        "structuredContent": value, "isError": False})
    return message.model_dump_json(by_alias=True, exclude_none=True).encode() + b"\n"


def fits(value: dict) -> bool:
    raw = wire_bytes(value)
    if len(raw) > WIRE_BUDGET:
        return False
    try:
        _message(raw)  # Retain the broker's independent depth/node limits too.
    except (ValueError, RecursionError):
        return False
    return True


def _preview(value, *, depth=0):
    """A disclosed preview; the full object remains separately retrievable."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return raw[:512].decode("utf-8", errors="ignore")
    if isinstance(value, (list, dict)) and depth >= 4:
        return {"preview_omitted": True, "count": len(value), "sha256": digest(value)}
    if isinstance(value, list):
        return [_preview(v, depth=depth + 1) for v in value[:8]]
    if isinstance(value, dict):
        return {k: _preview(v, depth=depth + 1) for k, v in sorted(value.items())[:16]}
    return value


def candidate_summary(candidate: dict, query_id: str) -> dict:
    stable = ("experience_id", "decision", "reason", "principle_decision",
              "current_operation_coverage", "query_snapshot_id", "query_snapshot_sha256",
              "retrieval_snapshot_sha256", "governance_evidence_sha256", "attribution")
    result = {k: candidate[k] for k in stable if k in candidate}
    for key in ("strategy", "matched_premises", "conflicting_premises", "unknown_premises",
                "missing_material_premises", "verification_steps", "rule_ids", "rule_versions",
                "governance_projection", "graph_integrity_issues", "recommendation_scope"):
        if key in candidate:
            result[key] = _preview(candidate[key])
            if len(pydantic_core.to_json(result[key])) > 2048:
                result[key] = {"preview_omitted": True, "sha256": digest(candidate[key])}
    experience = candidate.get("evidence_bundle", {}).get("experience", {})
    result["experience_preview"] = {k: _preview(experience[k]) for k in
        ("id", "title", "public_summary", "source_type", "limitations") if k in experience}
    result["evidence_index"] = {
        key: {"count": len(value), "sha256": digest(value)}
        for key, value in sorted(candidate.items()) if isinstance(value, list)}
    result.update(truncated=True, projection="CANDIDATE_SUMMARY_PREVIEW",
                  full_candidate_sha256=digest(candidate),
                  detail_reference={"tool": "build_evidence_bundle", "experience_id": candidate["experience_id"],
                                    "query_id": query_id, "view": "candidate"},
                  disclosure="Previews may omit text/rows, including counterexamples. Retrieve details before deciding.")
    return result


def _entries(value, pointer=""):
    """Lossless JSON Pointer (RFC6901) pages, including empty containers.

    Whole values fit in a single entry where possible. Large containers are
    declared before their children; long strings use explicit character offsets.
    No entry can hide the existence of another entry or an unfavorable path.
    """
    if len(pydantic_core.to_json(value)) <= 4096:
        yield {"pointer": pointer, "value": value}
    elif isinstance(value, dict):
        yield {"pointer": pointer, "container": "object", "length": len(value)}
        for key, part in sorted(value.items()):
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from _entries(part, pointer + "/" + escaped)
    elif isinstance(value, list):
        yield {"pointer": pointer, "container": "array", "length": len(value)}
        for index, part in enumerate(value):
            yield from _entries(part, pointer + "/" + str(index))
    elif isinstance(value, str):
        for offset in range(0, len(value), 512):
            yield {"pointer": pointer, "string_offset": offset, "string_length": len(value),
                   "value": value[offset:offset + 512]}
    else:
        raise ProjectionCapacityError("Unsupported oversized JSON value")


class PublicProjection:
    """Finite per-SDK-connection snapshot cache, never a graph truth store."""

    def __init__(self, service, *, clock=time.monotonic):
        self.service, self.clock = service, clock
        self._key = secrets.token_bytes(32)
        self._documents = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()

    def _remember(self, kind, binding, metadata, rows, authorize, source_sha256):
        size = len(pydantic_core.to_json(rows)) + len(pydantic_core.to_json(metadata))
        if size > MAX_CACHE_BYTES:
            raise ProjectionCapacityError("Public evidence exceeds finite snapshot capacity")
        with self._lock:
            for key, doc in list(self._documents.items()):
                if self.clock() >= doc["expires"]:
                    self._bytes -= self._documents.pop(key)["bytes"]
            while self._documents and (len(self._documents) >= MAX_DOCUMENTS or self._bytes + size > MAX_CACHE_BYTES):
                self._bytes -= self._documents.popitem(last=False)[1]["bytes"]
            identifier = secrets.token_hex(16)
            self._documents[identifier] = dict(kind=kind, binding=binding, metadata=metadata, rows=rows,
                authorize=authorize, sha256=source_sha256, expires=self.clock() + TTL_SECONDS, bytes=size)
            self._bytes += size
        return identifier

    def _cursor(self, identifier, offset):
        body = identifier + ":" + str(offset)
        mac = hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode((body + ":" + mac).encode()).decode().rstrip("=")

    def continuation(self, token, kind, binding):
        if not isinstance(token, str) or not 1 <= len(token) <= 256:
            raise ValueError("Invalid continuation")
        try:
            raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True).decode("ascii")
            identifier, offset, mac = raw.split(":")
            body = identifier + ":" + offset
            if not hmac.compare_digest(mac, hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()):
                raise ValueError
            index = int(offset)
        except (ValueError, UnicodeError):
            raise ValueError("Invalid continuation") from None
        with self._lock:
            doc = self._documents.get(identifier)
            if not doc or doc["kind"] != kind or doc["binding"] != binding or self.clock() >= doc["expires"]:
                raise ValueError("Continuation expired or outside this authorized connection")
        if not 0 <= index < len(doc["rows"]):
            raise ValueError("Invalid continuation offset")
        return self._page(identifier, index)

    def _page(self, identifier, offset):
        with self._lock:
            return self._page_locked(identifier, offset)

    def _page_locked(self, identifier, offset):
        doc = self._documents[identifier]
        result = {**doc["metadata"], "projection_version": VERSION, "truncated": True,
                  "source_sha256": doc["sha256"], "offset": offset, "total_items": len(doc["rows"]),
                  "cursor_scope": "SDK_CONNECTION_AND_RUN_AND_IMMUTABLE_DOCUMENT",
                  "cursor_ttl_seconds": TTL_SECONDS, "has_more": False, "next_cursor": None,
                  "items": []}
        field = "candidates" if doc["kind"] == "resolve" else "entries"
        result[field] = result.pop("items")
        for row in doc["rows"][offset:]:
            proposal = {**result, field: result[field] + [row], "has_more": True,
                        "next_cursor": self._cursor(identifier, offset + len(result[field]) + 1)}
            if (len(pydantic_core.to_json(proposal)) > PAGE_BUDGET or not fits(proposal)):
                break
            result = proposal
        if not result[field]:
            raise ProjectionCapacityError("One public evidence item exceeds the wire budget")
        end = offset + len(result[field])
        result.update(has_more=end < len(doc["rows"]), next_cursor=self._cursor(identifier, end) if end < len(doc["rows"]) else None)
        doc["authorize"](result[field])  # A cached page never bypasses current graph/owner checks.
        if not fits(result):
            raise ProjectionCapacityError("Encoded public response exceeds the wire budget")
        return result

    def resolve(self, claims, cursor=None):
        binding = digest(claims)
        if cursor is not None:
            return self.continuation(cursor, "resolve", binding)
        full = self.service.resolve_experience(claims)
        if full.get("status") != "AVAILABLE":  # Explicit synthetic transport contracts stay labeled synthetic.
            if not fits(full):
                raise ProjectionCapacityError("Encoded response exceeds the wire budget")
            return full
        rows = [candidate_summary(row, full["query_id"]) for row in sorted(full["candidates"], key=lambda x: x["experience_id"])]
        metadata = {k: v for k, v in full.items() if k not in {"candidates", "query_snapshot_ids"}}
        metadata.update(projection="CANDIDATE_SUMMARY_INDEX", candidate_count=len(rows),
                        detail_tool="build_evidence_bundle", snapshot_index="Included in each candidate summary")
        if not rows:
            result = {**metadata, "candidates": [], "has_more": False, "truncated": False, "next_cursor": None,
                      "projection_version": VERSION}
            if not fits(result):
                raise ProjectionCapacityError("Empty index metadata exceeds the wire budget")
            return result
        query_id = full["query_id"]
        def authorize(page):
            for row in page:
                self.service.build_evidence_bundle(row["experience_id"], query_id)
        identifier = self._remember("resolve", binding, metadata, rows, authorize, digest(full))
        return self._page(identifier, 0)

    def bundle(self, experience_id, query_id=None, cursor=None, view="bundle"):
        if view not in {"bundle", "candidate"}:
            raise ValueError("Invalid evidence view")
        binding = digest([experience_id, query_id, view])
        if cursor is not None:
            return self.continuation(cursor, "bundle", binding)
        bundle = self.service.build_evidence_bundle(experience_id, query_id)
        if view == "candidate":
            if query_id is None:
                raise ValueError("Candidate view requires the immutable query ID")
            query = self.service.repository.get_node("Query", query_id)
            snapshot_id = query["query_snapshot_ids"][experience_id]
            content = self.service.repository.load_query_snapshot(snapshot_id)
            bundle = {**content["candidate"], "query_snapshot_id": snapshot_id,
                      "query_snapshot_sha256": snapshot_id.removeprefix("snapshot:")}
        complete = {**bundle, "truncated": False, "has_more": False, "next_cursor": None,
                    "projection_version": VERSION}
        if fits(complete):
            return complete
        if len(pydantic_core.to_json(bundle)) > MAX_DOCUMENT_BYTES:
            raise ProjectionCapacityError("Public evidence exceeds finite document capacity")
        rows = list(_entries(bundle))
        metadata = {"status": "AVAILABLE", "experience_id": experience_id, "query_id": query_id, "view": view,
                    "projection": "LOSSLESS_JSON_POINTER_ENTRIES", "document_sha256": digest(bundle),
                    "snapshot_mode": bundle.get("snapshot_mode", "IMMUTABLE_CONNECTION_DOCUMENT"),
                    "query_snapshot_id": bundle.get("query_snapshot_id"),
                    "retrieval_snapshot_sha256": bundle.get("retrieval_snapshot_sha256"),
                    "reconstruction": "RFC6901 pointers; containers precede children; string_offset is Unicode character offset. Retrieve ALL pages and verify document_sha256."}
        def authorize(_):
            self.service.build_evidence_bundle(experience_id, query_id)
        identifier = self._remember("bundle", binding, metadata, rows, authorize, digest(bundle))
        return self._page(identifier, 0)
