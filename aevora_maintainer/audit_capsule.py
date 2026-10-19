"""Read-only Aevora supplement for the existing OrderFlow Audit-Lite exporter.

The trusted collector embeds this capsule in a NEW Full Archive PROTOCOL.json.
This module neither writes that protocol nor changes Benchmark source/results.
Verification checks included bytes, not the origin or truth of an experiment.
"""
from __future__ import annotations

import base64
from collections import Counter
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping

from benchmark import evidence_export, evidence_verify
from integrations.codex_trace import redact_text


CAPSULE_VERSION = "aevora.audit_capsule/1.0"
REQUIRED_CATEGORIES = frozenset({
    "DESIGN", "GRAPH_SCHEMA", "QUERY_COOKBOOK", "GATE", "JUNIT",
    "MCP_TRACE", "OUTCOME", "SOURCE_CHANGE",
})
MAX_ENTRIES = 256
MAX_SOURCE_BYTES = 8 * 1024**2
MAX_TOTAL_BYTES = 48 * 1024**2
MAX_CAPSULE_BYTES = 80 * 1024**2
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".xml", ".log", ".sql", ".cypher", ".diff"}
_ALLOWED_SUFFIXES = _TEXT_SUFFIXES | {".py", ".toml", ".yaml", ".yml", ".sh"}
_FORBIDDEN_PARTS = {
    "hidden_tests", "reference_patches", "private_manifests", "frozen_private_manifests",
    "private_labels", "participant", "workspace", "candidate", "codex-state", ".git",
    ".codex", "secrets", "credentials", "__pycache__",
}
_FORBIDDEN_NAMES = {
    ".env", ".runtime.env", "auth.json", "credentials.json", "config.toml",
    "falkordb.conf", "falkordb.password", "gateway.key", "identity.json",
}


class AuditCapsuleError(ValueError):
    """Unsafe, missing, changing or inconsistent supplement; nothing is written."""


def _json(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise AuditCapsuleError("Capsule must contain finite JSON data") from None


def _path(value: object) -> str:
    try:
        evidence_verify.safe_relative(value)
    except (TypeError, ValueError):
        raise AuditCapsuleError("Asset path must be a safe relative path") from None
    parts = PurePosixPath(value).parts
    lowered = {part.casefold() for part in parts}
    name = parts[-1].casefold()
    if (lowered & _FORBIDDEN_PARTS or name in _FORBIDDEN_NAMES
            or name.endswith((".key", ".pem", ".p12", ".pfx", ".password", ".sqlite", ".db"))
            or name.startswith(".env.") or PurePosixPath(name).suffix not in _ALLOWED_SUFFIXES):
        raise AuditCapsuleError("Private, credential, executable-state or unsupported asset path refused")
    return value


def _secrets(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise AuditCapsuleError("secret_values must be an iterable of distinct strings")
    try:
        result = tuple(islice(iter(values), 33))
    except TypeError:
        raise AuditCapsuleError("secret_values must be iterable") from None
    if len(result) > 32 or any(not isinstance(v, str) or not v or len(v) > 16384 for v in result):
        raise AuditCapsuleError("Invalid bounded secret scan configuration")
    return tuple(sorted(set(result), key=len, reverse=True))


def _line_map(source: bytes, exported: bytes) -> list[dict]:
    old, new = source.splitlines(keepends=True), exported.splitlines(keepends=True)
    if len(old) != len(new):
        raise AuditCapsuleError("Portable transformation changed JSONL line count")
    return [{"line": n, "source_sha256": sha256(before).hexdigest(),
             "exported_sha256": sha256(after).hexdigest()}
            for n, (before, after) in enumerate(zip(old, new), 1)]


def _scan_export(data: bytes, secrets: tuple[str, ...]) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise AuditCapsuleError("Audit assets must be UTF-8 text") from None
    # Known arbitrary secret values complement the existing credential patterns;
    # they are never returned, hashed, or read from identity files by this module.
    if redact_text(text, secret_values=secrets) != text:
        raise AuditCapsuleError("Exported asset still contains a sensitive credential pattern")


def build_capsule(archive: Path | str, public_assets: Mapping[str, str | Mapping[str, str]],
                  *, secret_values: Iterable[str] = ()) -> dict:
    """Read an explicit finite path/category map from one NEW trusted archive.

    Values are a category name or {category, representation: utf8|base64}.
    Every required category must be present. Only archived copies are accepted;
    this API cannot reach repository files via absolute paths or traversal.
    Base64 encodes the *exported* bytes, retaining byte identity through the
    outer JSON exporter. Original source digests remain separate pointers.
    """
    root = Path(archive).absolute()
    if root.is_symlink() or not root.is_dir():
        raise AuditCapsuleError("Archive must be an ordinary directory")
    root = root.resolve(strict=True)
    if not isinstance(public_assets, Mapping) or not 1 <= len(public_assets) <= MAX_ENTRIES:
        raise AuditCapsuleError("Asset selection must be a nonempty bounded mapping")
    secrets, entries, total = _secrets(secret_values), [], 0
    if any(not isinstance(path, str) for path in public_assets):
        raise AuditCapsuleError("Asset paths must be strings")
    for relative, specification in sorted(public_assets.items()):
        relative = _path(relative)
        if isinstance(specification, str):
            category = specification
            representation = "utf8" if PurePosixPath(relative).suffix in _TEXT_SUFFIXES else "base64"
        elif isinstance(specification, Mapping) and set(specification) == {"category", "representation"}:
            category, representation = specification["category"], specification["representation"]
        else:
            raise AuditCapsuleError("Asset descriptor must contain only category and representation")
        if (not isinstance(category, str) or category not in REQUIRED_CATEGORIES
                or not isinstance(representation, str) or representation not in {"utf8", "base64"}):
            raise AuditCapsuleError("Unknown category or representation")
        try:
            source = evidence_export._read_regular(root, relative, max_bytes=MAX_SOURCE_BYTES)
        except (OSError, ValueError):
            raise AuditCapsuleError("Selected asset missing, linked, special, oversized or changing") from None
        total += len(source)
        if not source or total > MAX_TOTAL_BYTES:
            raise AuditCapsuleError("Asset must be nonempty and total byte budget must hold")
        try:
            exported, details = evidence_export._transform(source, relative, root)
            text = redact_text(exported.decode("utf-8"), secret_values=secrets)
            exported = text.encode("utf-8")
        except (ValueError, UnicodeError):
            raise AuditCapsuleError("Selected asset cannot be safely transformed") from None
        if len(exported) > MAX_SOURCE_BYTES:
            raise AuditCapsuleError("Exported asset exceeds byte budget")
        _scan_export(exported, secrets)
        entry = {"source_path": relative, "category": category, "representation": representation,
                 "source_sha256": sha256(source).hexdigest(), "source_bytes": len(source),
                 "exported_sha256": sha256(exported).hexdigest(), "exported_bytes": len(exported),
                 "transformation": "NONE" if source == exported else "CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1",
                 "source_bytes_verification": "INCLUDED_IDENTICAL_BYTES" if source == exported else "FULL_ARCHIVE_ONLY_UNVERIFIED"}
        if relative.endswith(".jsonl"):
            entry.update(line_map=_line_map(source, exported), slice_status="COMPLETE_FILE")
        if representation == "utf8":
            entry["utf8_text"] = exported.decode("utf-8")
        else:
            entry["data_base64"] = base64.b64encode(exported).decode("ascii")
        entries.append(entry)
    capsule = {"schema_version": CAPSULE_VERSION, "kind": "AEVORA_AUDIT_CAPSULE",
               "sensitivity": "MAINTAINER_AUDIT", "source_archive_id": root.name,
               "required_categories": sorted(REQUIRED_CATEGORIES), "entries": entries,
               "assurance": "Included exported bytes and source hash pointers; runtime origin and semantic claims UNVERIFIED"}
    capsule["capsule_sha256"] = sha256(_json(capsule)).hexdigest()
    verify_capsule(capsule, secret_values=secrets)
    return capsule


def verify_capsule(capsule: dict, *, secret_values: Iterable[str] = ()) -> dict:
    """Check explicit category coverage, included bytes and complete line maps.

    No package code is imported/executed, source pointer followed, ZIP extracted,
    model invoked, or network/graph service contacted. A PASS here is byte and
    metadata consistency; Gate assertions remain claims for human review.
    """
    secrets = _secrets(secret_values)
    if (not isinstance(capsule, dict) or capsule.get("schema_version") != CAPSULE_VERSION
            or capsule.get("kind") != "AEVORA_AUDIT_CAPSULE" or capsule.get("sensitivity") != "MAINTAINER_AUDIT"
            or capsule.get("required_categories") != sorted(REQUIRED_CATEGORIES)):
        raise AuditCapsuleError("Unsupported capsule schema or required-category policy")
    raw = _json(capsule)
    if len(raw) > MAX_CAPSULE_BYTES:
        raise AuditCapsuleError("Capsule exceeds serialized byte budget")
    recorded = capsule.get("capsule_sha256")
    if not isinstance(recorded, str) or not _HEX.fullmatch(recorded):
        raise AuditCapsuleError("Invalid capsule SHA256")
    body = {k: v for k, v in capsule.items() if k != "capsule_sha256"}
    if sha256(_json(body)).hexdigest() != recorded:
        raise AuditCapsuleError("Capsule content digest differs")
    entries = capsule.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise AuditCapsuleError("Invalid bounded capsule entries")
    seen, counts, total, junit, mcp = set(), Counter(), 0, [], []
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuditCapsuleError("Asset entry must be an object")
        path = _path(entry.get("source_path"))
        if path in seen:
            raise AuditCapsuleError("Duplicate capsule source path")
        seen.add(path)
        category = entry.get("category")
        if not isinstance(category, str) or category not in REQUIRED_CATEGORIES:
            raise AuditCapsuleError("Unknown capsule category")
        counts[category] += 1
        representation = entry.get("representation")
        try:
            if representation == "utf8" and "data_base64" not in entry and isinstance(entry.get("utf8_text"), str):
                data = entry["utf8_text"].encode("utf-8")
            elif representation == "base64" and "utf8_text" not in entry and isinstance(entry.get("data_base64"), str):
                data = base64.b64decode(entry["data_base64"], validate=True)
                if base64.b64encode(data).decode("ascii") != entry["data_base64"]:
                    raise ValueError("noncanonical base64")
            else:
                raise ValueError("invalid representation")
        except (ValueError, UnicodeError):
            raise AuditCapsuleError("Invalid included asset encoding") from None
        _scan_export(data, secrets)
        total += len(data)
        if not data or len(data) > MAX_SOURCE_BYTES or total > MAX_TOTAL_BYTES:
            raise AuditCapsuleError("Invalid included byte budget")
        for field in ("source_sha256", "exported_sha256"):
            if not isinstance(entry.get(field), str) or not _HEX.fullmatch(entry[field]):
                raise AuditCapsuleError("Invalid source or export SHA256")
        if (type(entry.get("source_bytes")) is not int or not 1 <= entry["source_bytes"] <= MAX_SOURCE_BYTES
                or type(entry.get("exported_bytes")) is not int or entry["exported_bytes"] != len(data)
                or sha256(data).hexdigest() != entry["exported_sha256"]):
            raise AuditCapsuleError("Included byte length or export digest differs")
        identical = entry.get("transformation") == "NONE"
        if entry.get("transformation") not in {"NONE", "CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1"}:
            raise AuditCapsuleError("Unknown transformation")
        if identical and (entry["source_sha256"] != entry["exported_sha256"] or entry["source_bytes"] != len(data)):
            raise AuditCapsuleError("Identical-source declaration contradicts bytes")
        expected_assurance = "INCLUDED_IDENTICAL_BYTES" if identical else "FULL_ARCHIVE_ONLY_UNVERIFIED"
        if entry.get("source_bytes_verification") != expected_assurance:
            raise AuditCapsuleError("Original-source assurance differs from transformation")
        if path.endswith(".jsonl"):
            lines, mapping = data.splitlines(keepends=True), entry.get("line_map")
            if entry.get("slice_status") != "COMPLETE_FILE" or not isinstance(mapping, list) or len(mapping) != len(lines):
                raise AuditCapsuleError("Complete JSONL source line map required")
            for number, (line, row) in enumerate(zip(lines, mapping), 1):
                if (not isinstance(row, dict) or set(row) != {"line", "source_sha256", "exported_sha256"}
                        or type(row.get("line")) is not int or row["line"] != number
                        or not isinstance(row.get("source_sha256"), str) or not _HEX.fullmatch(row["source_sha256"])
                        or row.get("exported_sha256") != sha256(line).hexdigest()
                        or identical and row["source_sha256"] != row["exported_sha256"]):
                    raise AuditCapsuleError("JSONL line identity or byte hash differs")
        elif "line_map" in entry or "slice_status" in entry:
            raise AuditCapsuleError("Line maps are only valid for complete JSONL files")
        try:
            if category == "JUNIT":
                parsed = evidence_verify.read_junit(data)
                if not parsed["collected"]:
                    raise ValueError("empty JUnit")
                junit.append({"source_path": path, **{k: v for k, v in parsed.items() if k != "tests"}})
            elif category == "MCP_TRACE":
                if not path.endswith(".jsonl"):
                    raise ValueError("MCP trace must be JSONL")
                valid, malformed = 0, 0
                for line in data.splitlines():
                    try:
                        value = evidence_verify.load_json(line)
                        valid += isinstance(value, dict)
                        malformed += not isinstance(value, dict)
                    except evidence_verify.EvidenceVerifyError:
                        malformed += 1
                if not valid:
                    raise ValueError("MCP trace has no valid object lines")
                mcp.append({"source_path": path, "valid_object_lines": valid, "malformed_lines": malformed,
                            "native_agent_call_origin": "UNVERIFIED"})
            elif category in {"GATE", "OUTCOME", "SOURCE_CHANGE"} and path.endswith(".json"):
                if not isinstance(evidence_verify.load_json(data), (dict, list)):
                    raise ValueError("structured audit evidence required")
        except ValueError:
            raise AuditCapsuleError("Required category has invalid structured evidence") from None
    if set(counts) != REQUIRED_CATEGORIES:
        raise AuditCapsuleError("Required design, schema, query, Gate, JUnit, MCP, Outcome or source-change bytes missing")
    return {"status": "PASS", "schema_version": CAPSULE_VERSION, "capsule_sha256": recorded,
            "entries": len(entries), "included_exported_bytes": total, "categories": dict(sorted(counts.items())),
            "junit": junit, "mcp_trace": mcp, "verification_scope": "included bytes, category coverage, JUnit structure and complete JSONL line maps",
            "runtime_origin_attestation": "UNVERIFIED", "semantic_gate_claims": "UNVERIFIED",
            "transformed_original_bytes": "UNVERIFIED", "bundled_code_executed": False, "network_used": False}


def verify_exported_capsule(package: Path | str, *, secret_values: Iterable[str] = ()) -> dict:
    """Verify the existing ZIP and its PROTOCOL Aevora supplement read-only.

    Obtain this verifier and the Benchmark verifier from an independent trusted
    source. Never execute a verifier received inside the package being checked.
    Every capsule source SHA must agree with the outer Full Archive index.
    """
    try:
        benchmark_result = evidence_verify.verify_bundle(package)
        files = evidence_verify._read_package(Path(package))
        manifest = evidence_verify.load_json(files["MANIFEST.json"])
        candidates = [e for e in manifest["entries"] if e["source_path"] == "PROTOCOL.json"]
        if len(candidates) != 1:
            raise AuditCapsuleError("Exactly one exported PROTOCOL.json required")
        protocol = evidence_verify.load_json(files[candidates[0]["object"]])
        capsule = protocol.get("aevora_capsule")
        result = verify_capsule(capsule, secret_values=secret_values)
        pointers = {e["source_path"]: e["source_sha256"] for e in manifest["entries"]}
        omitted = evidence_verify.load_json(files["NOT_INCLUDED.json"])["entries"]
        pointers.update({e["source_path"]: e["source_sha256"] for e in omitted})
        for entry in capsule["entries"]:
            if pointers.get(entry["source_path"]) != entry["source_sha256"]:
                raise AuditCapsuleError("Capsule source differs from Full Archive source index")
        return {**result, "bundle_sha256": benchmark_result["bundle_sha256"],
                "benchmark_verification": benchmark_result,
                "source_index_crosscheck": "PASS", "zip_extracted": False}
    except AuditCapsuleError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise AuditCapsuleError("Audit-Lite ZIP or capsule verification failed") from None
