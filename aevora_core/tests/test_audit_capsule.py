"""Synthetic Audit-Lite contracts, never evidence of a live Agent experiment."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from aevora import audit_capsule
from aevora.audit_capsule import AuditCapsuleError, build_capsule, verify_capsule, verify_exported_capsule
from benchmark.evidence_export import export_archive


RUN = "11111111-1111-4111-8111-111111111111"
STAMP = "2026-10-11T00:00:00+00:00"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def rehash(value):
    value["capsule_sha256"] = sha256(encode({k: v for k, v in value.items() if k != "capsule_sha256"})).hexdigest()
    return value


@pytest.fixture
def assets(tmp_path):
    root = tmp_path / "full"
    root.mkdir()
    sources = {
        "public/design.md": ("DESIGN", b"# Synthetic design\nBoundary contract.\n"),
        "public/schema.md": ("GRAPH_SCHEMA", b"# Synthetic schema\nExperience -> Evidence.\n"),
        "public/query.cypher": ("QUERY_COOKBOOK", b"MATCH (e:Experience {id:$id}) RETURN e.id;\n"),
        "gates/G1_GATE.json": ("GATE", b'{"status":"FAIL","synthetic":true}\n'),
        "tests/junit.xml": ("JUNIT", b'<testsuite tests="1" failures="1"><testcase name="synthetic"><failure>retained</failure></testcase></testsuite>'),
        "runs/aevora_mcp_events.jsonl": ("MCP_TRACE", b'{"category":"JSONRPC","source":"SYNTHETIC_TEST"}\r\nmalformed official line\n'),
        "outcomes/verified.json": ("OUTCOME", b'{"verdict":"FAIL","source":"SYNTHETIC_TEST"}\n'),
        "sources/models.py": ("SOURCE_CHANGE", b'"""Synthetic public source."""\nVALUE = 1\n'),
    }
    for path, (_, data) in sources.items():
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    return root, {path: category for path, (category, _) in sources.items()}


def source_hashes(root):
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_complete_capsule_is_read_only_and_byte_exact(assets):
    root, selected = assets
    before = source_hashes(root)
    capsule = build_capsule(root, selected)
    result = verify_capsule(capsule)
    assert source_hashes(root) == before
    assert result["status"] == "PASS" and result["network_used"] is False
    assert result["junit"][0]["failed"] == 1
    assert result["mcp_trace"][0]["malformed_lines"] == 1
    assert result["mcp_trace"][0]["native_agent_call_origin"] == "UNVERIFIED"
    for entry in capsule["entries"]:
        raw = (root / entry["source_path"]).read_bytes()
        exported = entry.get("utf8_text", "").encode() if entry["representation"] == "utf8" else base64.b64decode(entry["data_base64"])
        assert raw == exported
        assert entry["source_sha256"] == entry["exported_sha256"] == sha256(raw).hexdigest()
    assert next(e for e in capsule["entries"] if e["source_path"].endswith(".py"))["representation"] == "base64"


def test_portable_and_arbitrary_secret_transformation_has_separate_hashes(assets):
    root, selected = assets
    token = "unshaped-project-test-token"
    source = (json.dumps({"source": "SYNTHETIC_TEST", "path": str(root / "somewhere"),
                          "value": token, "Authorization": "Bearer SYNTHETIC_SECRET_12345"}) + "\r\n").encode()
    file = root / "runs/aevora_mcp_events.jsonl"
    file.write_bytes(source)
    capsule = build_capsule(root, selected, secret_values=[token])
    entry = next(e for e in capsule["entries"] if e["category"] == "MCP_TRACE")
    assert token not in entry["utf8_text"] and "SYNTHETIC_SECRET_12345" not in entry["utf8_text"]
    assert "archive://somewhere" in entry["utf8_text"]
    assert entry["source_sha256"] == sha256(source).hexdigest() != entry["exported_sha256"]
    assert entry["source_bytes_verification"] == "FULL_ARCHIVE_ONLY_UNVERIFIED"
    assert entry["line_map"][0]["source_sha256"] == sha256(source).hexdigest()
    assert entry["line_map"][0]["exported_sha256"] == sha256(entry["utf8_text"].encode()).hexdigest()
    assert file.read_bytes() == source
    assert verify_capsule(capsule, secret_values=[token])["status"] == "PASS"


def test_capsule_is_deterministic_for_identical_inputs(assets):
    root, selected = assets
    assert build_capsule(root, selected) == build_capsule(root, dict(reversed(list(selected.items()))))


@pytest.mark.parametrize("missing", sorted(audit_capsule.REQUIRED_CATEGORIES))
def test_every_required_category_is_mandatory(assets, missing):
    root, selected = assets
    selected = {p: c for p, c in selected.items() if c != missing}
    with pytest.raises(AuditCapsuleError, match="missing"):
        build_capsule(root, selected)


@pytest.mark.parametrize("path", ["../outside.md", "/outside.md", "private_manifests/D.json",
    "evaluator/hidden_tests/test.py", "evaluator/reference_patches/D.diff", "frozen_private_manifests/A.json",
    "private_labels/answer.json", "auth.json", "keys/key.pem", "credentials/file.json", "falkordb.password",
    "secret/gateway.key", "participant/app/service.py", "candidate/app/service.py", "state/codex-state/log.jsonl",
    ".runtime.env", "data/business.db", "state/config.toml", "file.exe"])
def test_forbidden_source_paths_are_rejected(assets, path):
    root, selected = assets
    with pytest.raises(AuditCapsuleError):
        build_capsule(root, {**selected, path: "SOURCE_CHANGE"})


@pytest.mark.parametrize("kind", ["symlink_file", "symlink_directory", "hardlink", "fifo", "missing"])
def test_linked_special_or_missing_file_refused(assets, kind):
    root, selected = assets
    file = root / "public/design.md"
    original = file.read_bytes()
    file.unlink()
    if kind == "symlink_file":
        outside = root.parent / "outside.md"; outside.write_bytes(original); file.symlink_to(outside)
    elif kind == "symlink_directory":
        directory = root / "public"; directory.rename(root / "original-public"); directory.symlink_to(root / "original-public")
    elif kind == "hardlink":
        outside = root.parent / "outside.md"; outside.write_bytes(original); os.link(outside, file)
    elif kind == "fifo":
        os.mkfifo(file)
    with pytest.raises(AuditCapsuleError):
        build_capsule(root, selected)


@pytest.mark.parametrize("mutation", ["payload", "export_sha", "source_sha", "line_hash", "line_number",
    "line_removed", "duplicate", "source_assurance", "category_policy", "base64", "junit", "empty_trace"])
def test_rehashed_inconsistent_capsule_refused(assets, mutation):
    root, selected = assets
    value = deepcopy(build_capsule(root, selected))
    trace = next(e for e in value["entries"] if e["category"] == "MCP_TRACE")
    entry = value["entries"][0]
    if mutation == "payload": entry["utf8_text"] += "tampered"
    elif mutation == "export_sha": entry["exported_sha256"] = "f" * 64
    elif mutation == "source_sha": entry["source_sha256"] = "f" * 64
    elif mutation == "line_hash": trace["line_map"][0]["exported_sha256"] = "f" * 64
    elif mutation == "line_number": trace["line_map"][0]["line"] = 2
    elif mutation == "line_removed": trace["line_map"].pop()
    elif mutation == "duplicate": value["entries"].append(deepcopy(entry))
    elif mutation == "source_assurance": entry["source_bytes_verification"] = "UNVERIFIED"
    elif mutation == "category_policy": value["required_categories"].remove("DESIGN")
    elif mutation == "base64":
        entry = next(e for e in value["entries"] if e["representation"] == "base64")
        entry["data_base64"] = "%%%"
    elif mutation in {"junit", "empty_trace"}:
        entry = next(e for e in value["entries"] if e["category"] == ("JUNIT" if mutation == "junit" else "MCP_TRACE"))
        entry["utf8_text"] = '<testsuite tests="0"></testsuite>' if mutation == "junit" else "malformed only\n"
        raw = entry["utf8_text"].encode()
        entry.update(source_sha256=sha256(raw).hexdigest(), exported_sha256=sha256(raw).hexdigest(),
                     source_bytes=len(raw), exported_bytes=len(raw))
        if mutation == "empty_trace": entry["line_map"] = audit_capsule._line_map(raw, raw)
    with pytest.raises(AuditCapsuleError):
        verify_capsule(rehash(value))


def test_sensitive_value_inside_base64_is_rejected(assets):
    root, selected = assets
    value = build_capsule(root, selected)
    entry = next(e for e in value["entries"] if e["representation"] == "base64")
    data = b'KEY = "sk-syntheticcredentialABCDEFGHIJ12345"\n'
    entry.update(data_base64=base64.b64encode(data).decode(), source_bytes=len(data), exported_bytes=len(data),
                 source_sha256=sha256(data).hexdigest(), exported_sha256=sha256(data).hexdigest())
    with pytest.raises(AuditCapsuleError, match="sensitive"):
        verify_capsule(rehash(value))


@pytest.mark.parametrize("limit,value", [("MAX_ENTRIES", 1), ("MAX_SOURCE_BYTES", 1), ("MAX_TOTAL_BYTES", 1), ("MAX_CAPSULE_BYTES", 1)])
def test_all_byte_and_entry_budgets_enforced(assets, monkeypatch, limit, value):
    root, selected = assets
    monkeypatch.setattr(audit_capsule, limit, value)
    with pytest.raises(AuditCapsuleError):
        build_capsule(root, selected)


@pytest.mark.parametrize("secrets", ["secret", [""], [123], ["x"] * 33, iter(range(1000000000))])
def test_secret_configuration_bounded_without_disclosure(assets, secrets):
    root, selected = assets
    with pytest.raises(AuditCapsuleError):
        build_capsule(root, selected, secret_values=secrets)


def make_export(assets, tmp_path, *, wrong_pointer=False):
    root, selected = assets
    capsule = build_capsule(root, selected)
    if wrong_pointer:
        entry = capsule["entries"][0]
        entry.update(source_sha256="f" * 64, transformation="CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1",
                     source_bytes_verification="FULL_ARCHIVE_ONLY_UNVERIFIED")
        rehash(capsule)
    (root / "PROTOCOL.json").write_bytes(encode({"aevora_capsule": capsule, "suite_expectations": []}))
    run = root / "runs" / RUN; run.mkdir()
    report = {"run_id": RUN, "episode_id": "D", "overall_status": "TIMEOUT", "runtime_status": "TIMEOUT",
              "evaluation_status": "NOT_RUN", "integration_status": "PARTIAL", "test_results": None,
              "pytest_exit_code": None, "fingerprints": {}, "multi_agent_status": "NOT_APPLICABLE"}
    (run / "evaluation_report.json").write_bytes(encode(report))
    indexed = source_hashes(root)
    (root / "EVIDENCE_MANIFEST.json").write_bytes(encode({"ordinary_files_sha256": indexed,
        "total_bytes": sum((root / p).stat().st_size for p in indexed)}))
    output = tmp_path / "audit.zip"
    export_archive(root, output, run_ids=[RUN], created_at=STAMP)
    return output


def test_unchanged_orderflow_exporter_preserves_capsule_and_crosschecks_pointers(assets, tmp_path):
    package = make_export(assets, tmp_path)
    result = verify_exported_capsule(package)
    assert result["status"] == "PASS" and result["source_index_crosscheck"] == "PASS"
    assert result["zip_extracted"] is False and result["bundled_code_executed"] is False
    assert result["benchmark_verification"]["runs"][0]["overall_status"] == "TIMEOUT"
    assert result["semantic_gate_claims"] == "UNVERIFIED"


def test_outer_frozen_source_pointer_cannot_be_reinterpreted(assets, tmp_path):
    package = make_export(assets, tmp_path, wrong_pointer=True)
    with pytest.raises(AuditCapsuleError, match="source differs"):
        verify_exported_capsule(package)
