"""Strict verification of lossless public JSON-pointer pages."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


class PaginationAuditError(ValueError):
    pass


def _fail(message: str):
    raise PaginationAuditError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _parts(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        _fail("JSON pointer must be empty or absolute")
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer[1:].split("/")
    ]


def _ensure_parent(root: Any, parts: list[str]):
    current = root
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if isinstance(current, list):
            if not part.isdecimal():
                _fail("JSON pointer list index is not numeric")
            position = int(part)
            while len(current) <= position:
                current.append(None)
            if current[position] is None:
                current[position] = [] if next_part.isdecimal() else {}
            current = current[position]
        elif isinstance(current, dict):
            if part not in current:
                current[part] = [] if next_part.isdecimal() else {}
            current = current[part]
        else:
            _fail("JSON pointer traverses a scalar")
    return current, parts[-1]


def _set(root: Any, pointer: str, value: Any, *, string_offset=None, string_length=None):
    parts = _parts(pointer)
    if not parts:
        if not isinstance(value, (dict, list)):
            _fail("Root replacement must be an object or array")
        if isinstance(root, dict):
            root.clear(); root.update(value)
        elif isinstance(root, list):
            root.clear(); root.extend(value)
        else:
            _fail("Root replacement type mismatch")
        return
    parent, key = _ensure_parent(root, parts)
    if isinstance(parent, list):
        if not key.isdecimal():
            _fail("JSON pointer list index is not numeric")
        index = int(key)
        while len(parent) <= index:
            parent.append(None)
        if string_offset is not None:
            old = parent[index]
            if old is None:
                old = ""
            if not isinstance(old, str) or len(old) != string_offset:
                _fail("String continuation offset mismatch")
            if not isinstance(value, str) or len(value) > string_length:
                _fail("String continuation length mismatch")
            parent[index] = old + value
        else:
            if parent[index] is not None:
                _fail("Duplicate JSON pointer value")
            parent[index] = value
    else:
        if string_offset is not None:
            old = parent.get(key, "")
            if not isinstance(old, str) or len(old) != string_offset:
                _fail("String continuation offset mismatch")
            if not isinstance(value, str) or len(value) > string_length:
                _fail("String continuation length mismatch")
            parent[key] = old + value
        else:
            if key in parent:
                _fail("Duplicate JSON pointer value")
            parent[key] = value


def reconstruct(pages: list[dict]) -> dict:
    if not pages:
        _fail("No pages")
    root: dict = {}
    seen = set()
    for page_number, page in enumerate(pages):
        entries = page.get("entries")
        if not isinstance(entries, list):
            _fail(f"Page {page_number} has no entries")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("pointer"), str):
                _fail("Malformed JSON pointer entry")
            pointer = entry["pointer"]
            marker = (pointer, entry.get("string_offset"))
            if marker in seen:
                _fail(f"Duplicate page entry {marker}")
            seen.add(marker)
            if "container" in entry:
                if entry["container"] not in {"object", "array"}:
                    _fail("Unknown container type")
                target = {} if entry["container"] == "object" else []
                target_parts = _parts(pointer)
                if not target_parts:
                    root = target
                else:
                    _set(root, pointer, target)
            elif "value" in entry:
                _set(
                    root,
                    pointer,
                    entry["value"],
                    string_offset=entry.get("string_offset"),
                    string_length=entry.get("string_length"),
                )
            else:
                _fail("Entry has neither container nor value")
    return root


def _cursor_offset(token: str) -> int | None:
    if not isinstance(token, str):
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("ascii")
        _, offset, _ = raw.split(":")
        return int(offset)
    except (ValueError, UnicodeError):
        return None


def _without_fields(value: Any, fields: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_fields(part, fields)
            for key, part in value.items()
            if key not in fields
        }
    if isinstance(value, list):
        return [_without_fields(part, fields) for part in value]
    return value


def verify_pages(pages: list[dict], reference: dict | None = None,
                 ignore_fields: tuple[str, ...] = ()) -> dict:
    if not pages:
        _fail("No pages to verify")
    read_scope = None
    total_items = None
    expected_offset = 0
    for index, page in enumerate(pages):
        if page.get("isError") is True:
            _fail(f"Page {index} is an MCP error")
        if page.get("status") != "AVAILABLE":
            _fail(f"Page {index} status is not AVAILABLE")
        if page.get("offset") != expected_offset:
            _fail(f"Page {index} offset is not contiguous")
        entries = page.get("entries")
        if not isinstance(entries, list) or not entries:
            _fail(f"Page {index} has no entries")
        if total_items is None:
            total_items = page.get("total_items")
        elif total_items != page.get("total_items"):
            _fail("total_items changed between pages")
        if read_scope is None:
            read_scope = page.get("read_scope")
        elif read_scope != page.get("read_scope"):
            _fail("read_scope changed between pages")
        expected_offset += len(entries)
        if index < len(pages) - 1:
            if page.get("has_more") is not True:
                _fail(f"Page {index} is not marked has_more")
            if _cursor_offset(page.get("next_cursor")) != expected_offset:
                _fail(f"Page {index} cursor offset mismatch")
        else:
            if page.get("has_more") is not False or page.get("next_cursor") is not None:
                _fail("Final page is not terminal")
    if total_items != expected_offset:
        _fail("Page entries do not cover total_items")
    reconstructed = reconstruct(pages)
    source_hash = pages[0].get("source_sha256")
    document_hash = pages[0].get("document_sha256")
    actual_hash = digest(reconstructed)
    if source_hash and source_hash != actual_hash:
        _fail("Reconstructed source SHA differs from page source_sha256")
    if document_hash and document_hash != actual_hash:
        _fail("Reconstructed document SHA differs from page document_sha256")
    if reference is not None and canonical(_without_fields(reconstructed, ignore_fields)) != canonical(
            _without_fields(reference, ignore_fields)):
        _fail("Reconstructed full document differs from reference response")
    return {
        "status": "PASS",
        "page_count": len(pages),
        "entry_count": expected_offset,
        "reconstructed_sha256": actual_hash,
        "page_document_sha256": document_hash,
    }
