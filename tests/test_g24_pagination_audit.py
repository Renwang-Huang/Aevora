import copy

import pytest

from aevora.mcp_projection import TTL_SECONDS, PublicProjection
from tools.experiments.g24.pagination_audit import (
    PaginationAuditError,
    digest,
    reconstruct,
    verify_pages,
)


def _page(value, *, offset=0, more=False, cursor=None):
    entries = [{"pointer": "", "container": "object", "length": len(value)}]
    entries.extend({"pointer": "/" + key, "value": value[key]} for key in sorted(value))
    return {
        "status": "AVAILABLE",
        "offset": offset,
        "total_items": len(entries),
        "has_more": more,
        "next_cursor": cursor,
        "entries": entries,
        "document_sha256": digest(value),
        "source_sha256": digest(value),
        "read_scope": {"semantic_epoch": 1, "authz_epoch": 0},
    }


def test_full_lossless_page_reconstructs_and_hashes():
    value = {"a": "hello", "b": ["x", "y"]}
    page = _page(value)
    assert reconstruct([page]) == value
    assert verify_pages([page], value)["status"] == "PASS"


def test_error_page_is_never_pass():
    page = _page({"a": 1})
    page["isError"] = True
    with pytest.raises(PaginationAuditError):
        verify_pages([page])


def test_duplicate_and_reordered_pages_fail():
    value = {"a": 1}
    page = _page(value)
    with pytest.raises(PaginationAuditError):
        verify_pages([page, copy.deepcopy(page)])
    reordered = copy.deepcopy(page)
    reordered["offset"] = 1
    with pytest.raises(PaginationAuditError):
        verify_pages([reordered])


def test_tampered_value_fails_hash():
    page = _page({"a": 1})
    page["entries"][1]["value"] = 2
    with pytest.raises(PaginationAuditError):
        verify_pages([page])


def test_string_continuation_is_lossless():
    page = {
        "status": "AVAILABLE", "offset": 0, "total_items": 3,
        "has_more": False, "next_cursor": None,
        "read_scope": {"semantic_epoch": 1},
        "entries": [
            {"pointer": "/text", "string_offset": 0, "string_length": 6, "value": "abc"},
            {"pointer": "/text", "string_offset": 3, "string_length": 6, "value": "def"},
            {"pointer": "/text", "string_offset": 6, "string_length": 6, "value": ""},
        ],
    }
    page["document_sha256"] = digest({"text": "abcdef"})
    page["source_sha256"] = page["document_sha256"]
    assert reconstruct([page]) == {"text": "abcdef"}
    assert verify_pages([page], {"text": "abcdef"})["status"] == "PASS"


def test_cursor_expiry_and_tampering_are_rejected():
    class Clock:
        value = 0.0
        def __call__(self):
            return self.value

    clock = Clock()
    projection = PublicProjection(None, clock=clock)
    identifier = projection._remember(
        "bundle", "binding", {}, [{"pointer": "/x", "value": 1}],
        lambda _page: None, "source",
    )
    cursor = projection._cursor(identifier, 0)
    with pytest.raises(ValueError):
        projection.continuation(cursor[:-1] + ("A" if cursor[-1] != "A" else "B"),
                                "bundle", "binding")
    clock.value = TTL_SECONDS + 1
    with pytest.raises(ValueError):
        projection.continuation(cursor, "bundle", "binding")


def test_revoked_authorization_fails_before_page_delivery():
    class Clock:
        value = 0.0
        def __call__(self):
            return self.value

    def revoked(_page):
        raise PermissionError("REVOKED")

    projection = PublicProjection(None, clock=Clock())
    identifier = projection._remember(
        "bundle", "binding", {"status": "AVAILABLE"},
        [{"pointer": "/x", "value": 1}], revoked, "source",
    )
    with pytest.raises(PermissionError):
        projection._page(identifier, 0)
