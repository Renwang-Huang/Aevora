"""Synthetic package contracts; never evidence of a real model execution."""
from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import pytest

from benchmark.evidence_export import EvidenceExportError, export_archive, inspect_bundle, verify_bundle
from benchmark.evidence_verify import EvidenceVerifyError, safe_relative


RUN = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
FIXED_TIME = "2026-10-10T00:00:00+00:00"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n")


def freeze(root):
    entries = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
               for p in root.rglob("*") if p.is_file() and p.name != "EVIDENCE_MANIFEST.json"}
    write_json(root / "EVIDENCE_MANIFEST.json", {"ordinary_files_sha256": entries,
                                               "total_bytes": sum((root / p).stat().st_size for p in entries)})


def add_run(root, run_id=RUN, *, outcome="PASS", runtime="PASS", original=None, private_text=""):
    prefix = f"runs/{run_id}"
    run = root / prefix
    run.mkdir(parents=True)
    patch = b"diff --git a/app/service.py b/app/service.py\n--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-old\n+new\n"
    raw = (json.dumps({"type": "thread.started", "thread_id": "synthetic-thread"}) + "\n").encode()
    (run / "codex_events.jsonl").write_bytes(raw)
    reference = {"path": str(run / "codex_events.jsonl"), "line": 1, "sha256": sha256(raw).hexdigest()}
    (run / "agent_trace.jsonl").write_text(json.dumps({"run_id": run_id, "payload": {"raw_reference": reference}, "source": "SYNTHETIC_TEST"}) + "\n")
    report = {"run_id": run_id, "episode_id": "D", "scenario_version": "test-only", "scenario_variant": "v01",
              "overall_status": outcome, "runtime_status": runtime, "evaluation_status": outcome if outcome != "TIMEOUT" else "NOT_RUN",
              "submission_integrity_status": "PASS" if outcome in {"PASS", "FAIL"} else "NOT_RUN",
              "multi_agent_status": "NOT_APPLICABLE", "integration_status": "PASS" if runtime == "PASS" else "PARTIAL",
              "fingerprints": {"test_suite": {"version": "synthetic", "sha256": "1" * 64}}, "database_oracle": [],
              "recovery_coverage": {"status": "COMPLETE"}, "private_diagnostic": private_text}
    if outcome in {"PASS", "FAIL"}:
        (run / "artifacts").mkdir()
        (run / "submission.diff").write_bytes(patch)
        report["submission_integrity"] = {"status": "PASS", "patch_sha256": sha256(patch).hexdigest(),
                                          "baseline_tree_sha256": "2" * 64, "expected_tree_sha256": "3" * 64,
                                          "applied_candidate_tree_sha256": "3" * 64}
        failed = outcome == "FAIL"
        report["pytest_exit_code"] = 1 if failed else 0
        report["test_results"] = {"collected": 1, "passed": 0 if failed else 1, "failed": 1 if failed else 0,
                                  "errors": 0, "skipped": 0, "tests": [{"nodeid": "test_d::test_case", "outcome": outcome}]}
        failure = '<failure message="synthetic failure">actual assertion failed</failure>' if failed else ""
        (run / "artifacts/junit.xml").write_text(f'<testsuites><testsuite tests="1" failures="{int(failed)}" errors="0" skipped="0"><testcase classname="test_d" name="test_case" time="0.01">{failure}</testcase></testsuite></testsuites>')
        oracle = {"consistent": not failed, "inventory": [], "ledger": [], "orders": [], "violations": [] if not failed else ["synthetic mismatch"]}
        write_json(run / "artifacts/oracle-test_case-final.json", oracle)
        report["database_oracle"] = [oracle]
    else:
        report["pytest_exit_code"] = None
        report["test_results"] = None
        report["submission_integrity"] = None
    write_json(run / "evaluation_report.json", report)
    write_json(run / "runtime_metadata.json", {"run_id": run_id, "model": "synthetic-model", "resource_watchdog": {"wall_seconds": 1200},
                                                "timeout_seconds": 1200, "provider": "synthetic-fixture", "agent_mode": "single"})
    write_json(run / "native_rollout_summary.json", {"run_id": run_id, "subagents": {"verified_count": 0}})
    write_json(root / f"commands/{run_id}/command.json", {"argv": ["synthetic-test-command"], "exit_code": 0 if outcome == "PASS" else 1,
                                                         "run_id": run_id, "status": outcome})
    suite = {"id": "D", "implemented": True, "expected_test_count": 1,
             "expected_tests": ["test_d::test_case"]}
    write_json(root / "frozen/evaluator/private_manifests/D.json", suite)
    report["fingerprints"]["private_manifest_sha256"] = sha256((root / "frozen/evaluator/private_manifests/D.json").read_bytes()).hexdigest()
    write_json(run / "evaluation_report.json", report)
    if original:
        write_json(root / "POSTMORTEM_RESULTS.json", [{"original_run_id": original, "postmortem_run_id": run_id}])
    return run


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "full"
    root.mkdir()
    add_run(root)
    write_json(root / "omitted/workspace/source.json", {"purpose": "not audit input"})
    freeze(root)
    return root


def export(root, tmp_path, name="audit.zip"):
    return export_archive(root, tmp_path / name, created_at=FIXED_TIME)


def mutate_package(path, output, callback, *, rehash=True):
    with zipfile.ZipFile(path) as source:
        files = {p.filename: source.read(p) for p in source.infolist()}
    callback(files)
    if rehash:
        files["SHA256SUMS"] = "".join(f"{sha256(v).hexdigest()}  {p}\n" for p, v in sorted(files.items()) if p != "SHA256SUMS").encode()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for p, v in sorted(files.items()):
            archive.writestr(p, v)
    return output


def modify_json(files, name, fn):
    value = json.loads(files[name]); fn(value); files[name] = (json.dumps(value, sort_keys=True) + "\n").encode()


def modify_object(files, source_suffix, fn):
    manifest = json.loads(files["MANIFEST.json"])
    row = next(x for x in manifest["entries"] if x["source_path"].endswith(source_suffix))
    value = json.loads(files[row["object"]]); fn(value)
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    old = row["object"]; new_sha = sha256(raw).hexdigest(); new = "objects/" + new_sha
    del files[old]; files[new] = raw
    row.update(object=new, exported_sha256=new_sha, exported_bytes=len(raw), transformation="CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1")
    files["MANIFEST.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode()


def test_normal_export_verify_and_inspect_preserve_source(archive, tmp_path):
    before = {p.relative_to(archive).as_posix(): sha256(p.read_bytes()).hexdigest() for p in archive.rglob("*") if p.is_file()}
    receipt = export(archive, tmp_path)
    assert receipt["status"] == "PASS" and receipt["source_writes"] is False
    assert verify_bundle(tmp_path / "audit.zip")["runs"][0]["evaluation_status"] == "PASS"
    assert inspect_bundle(tmp_path / "audit.zip")["sensitivity"] == "MAINTAINER_AUDIT"
    assert receipt["verification"]["not_included_pointers"] == 2  # omitted source + private suite metadata
    after = {p.relative_to(archive).as_posix(): sha256(p.read_bytes()).hexdigest() for p in archive.rglob("*") if p.is_file()}
    assert before == after


def test_standalone_offline_verifier_in_empty_directory(archive, tmp_path):
    export(archive, tmp_path)
    isolated = tmp_path / "isolated"; isolated.mkdir()
    script = isolated / "verify_audit_bundle.py"
    with zipfile.ZipFile(tmp_path / "audit.zip") as package:
        script.write_bytes(package.read("verify_audit_bundle.py"))
    result = subprocess.run([sys.executable, "-I", str(script), "verify", str(tmp_path / "audit.zip"), "--json"], cwd=isolated,
                            capture_output=True, text=True, timeout=20, env={})
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "PASS" and parsed["network_used"] is False and parsed["archive_extracted"] is False


def test_fixed_timestamp_is_byte_deterministic(archive, tmp_path):
    first = export(archive, tmp_path, "first.zip"); second = export(archive, tmp_path, "second.zip")
    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()


def test_cas_deduplicates_equal_exported_content(archive, tmp_path):
    raw = (archive / f"runs/{RUN}/codex_stderr.log")
    raw.write_text("identical\n")
    (archive / f"runs/{RUN}/artifacts/pytest.stderr.log").write_text("identical\n")
    freeze(archive)
    receipt = export(archive, tmp_path)
    assert receipt["verification"]["unique_content_objects"] < receipt["verification"]["included_source_files"]


def test_timeout_and_postmortem_scores_remain_distinct(tmp_path):
    root = tmp_path / "full"; root.mkdir()
    add_run(root, outcome="TIMEOUT", runtime="TIMEOUT")
    add_run(root, SECOND, original=RUN)
    freeze(root)
    receipt = export(root, tmp_path)
    rows = {x["run_id"]: x for x in receipt["verification"]["runs"]}
    assert rows[RUN]["runtime_status"] == "TIMEOUT" and rows[RUN]["evaluation_status"] == "NOT_RUN"
    assert rows[SECOND]["evaluation_status"] == "PASS" and rows[SECOND]["postmortem_of"] == RUN


@pytest.mark.parametrize("status", ["FAIL", "ERROR", "TIMEOUT", "CANCELLED"])
def test_abnormal_outcomes_are_preserved(tmp_path, status):
    root = tmp_path / "full"; root.mkdir(); add_run(root, outcome=status, runtime=status); freeze(root)
    receipt = export(root, tmp_path)
    assert receipt["verification"]["runs"][0]["overall_status"] == status


def test_credentials_and_personal_paths_are_redacted(tmp_path):
    root = tmp_path / "full"; root.mkdir()
    fake_key = "sk-syntheticcredentialABCDEFGHIJ12345"
    run = add_run(root, private_text=f"Authorization: Bearer synthetic-secret-123 /home/test-person/private {fake_key}")
    (run / "codex_stderr.log").write_text('api_key="' + fake_key + '"\n')
    freeze(root); export(root, tmp_path)
    with zipfile.ZipFile(tmp_path / "audit.zip") as package:
        all_data = b"\n".join(package.read(p) for p in package.namelist())
        manifest = json.loads(package.read("MANIFEST.json"))
    assert fake_key.encode() not in all_data and b"synthetic-secret-123" not in all_data
    assert b"/home/test-person" not in all_data
    assert any(x["source_sha256"] != x["exported_sha256"] for x in manifest["entries"])


def test_single_byte_tamper_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    tampered = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda files: files.__setitem__("README_AUDIT.md", files["README_AUDIT.md"] + b"x"), rehash=False)
    with pytest.raises(EvidenceExportError, match="Checksum mismatch"):
        verify_bundle(tampered)


def test_missing_required_file_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda files: files.pop("RUN_INDEX.json"))
    with pytest.raises(EvidenceExportError, match="Required"):
        verify_bundle(bad)


def test_forged_junit_report_disagreement_is_rejected_even_with_new_checksums(archive, tmp_path):
    export(archive, tmp_path)
    def corrupt(files):
        modify_object(files, "/evaluation_report.json", lambda d: d["test_results"].update(passed=0, failed=1))
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", corrupt)
    with pytest.raises(EvidenceExportError, match="JUnit/report test counts"):
        verify_bundle(bad)


def test_forged_test_identity_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda f: modify_object(f, "/evaluation_report.json", lambda d: d["test_results"]["tests"][0].update(nodeid="other::fake")))
    with pytest.raises(EvidenceExportError, match="identities"):
        verify_bundle(bad)


def test_correlated_junit_and_report_deletion_still_rejects_missing_required_identity(archive, tmp_path):
    # Two independent expected identities prevent a malicious package from
    # reducing both JUnit and the report to a mutually consistent one-test PASS.
    run = archive / f"runs/{RUN}"
    report = json.loads((run / "evaluation_report.json").read_text())
    report["test_results"].update(collected=2, passed=2)
    report["test_results"]["tests"].append({"nodeid": "test_d::test_second", "outcome": "PASS"})
    junit = '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"><testcase classname="test_d" name="test_case"/><testcase classname="test_d" name="test_second"/></testsuite></testsuites>'
    (run / "artifacts/junit.xml").write_text(junit)
    suite = {"id": "D", "implemented": True, "expected_test_count": 2,
             "expected_tests": ["test_d::test_case", "test_d::test_second"]}
    write_json(archive / "frozen/evaluator/private_manifests/D.json", suite)
    report["fingerprints"]["private_manifest_sha256"] = sha256((archive / "frozen/evaluator/private_manifests/D.json").read_bytes()).hexdigest()
    write_json(run / "evaluation_report.json", report); freeze(archive); export(archive, tmp_path)
    def corrupt(files):
        manifest = json.loads(files["MANIFEST.json"])
        row = next(x for x in manifest["entries"] if x["source_path"].endswith("/artifacts/junit.xml"))
        raw = '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="test_d" name="test_case"/></testsuite></testsuites>'.encode()
        old = row["object"]; new_sha = sha256(raw).hexdigest(); new = "objects/" + new_sha
        del files[old]; files[new] = raw; row.update(object=new, exported_sha256=new_sha, exported_bytes=len(raw), transformation="CREDENTIAL_REDACTION_AND_PORTABLE_PATHS_V1")
        files["MANIFEST.json"] = json.dumps(manifest, sort_keys=True).encode()
        def reduce_report(d):
            d["test_results"].update(collected=1, passed=1)
            d["test_results"]["tests"] = d["test_results"]["tests"][:1]
        modify_object(files, "/evaluation_report.json", reduce_report)
        modify_json(files, "RUN_INDEX.json", lambda d: d["runs"][0]["test_counts"].update(collected=1, passed=1))
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", corrupt)
    with pytest.raises(EvidenceExportError, match="required test"):
        verify_bundle(bad)


def test_missing_suite_source_is_explicitly_unverified(archive, tmp_path):
    (archive / "frozen/evaluator/private_manifests/D.json").unlink(); freeze(archive)
    receipt = export(archive, tmp_path)
    assert receipt["verification"]["runs"][0]["suite_completeness"] == "UNVERIFIED"


def test_fidelity_tree_mismatch_rejects_correlated_report_index_tamper(archive, tmp_path):
    report_path = archive / f"runs/{RUN}/evaluation_report.json"
    report = json.loads(report_path.read_text()); report["submission_integrity"].pop("status"); write_json(report_path, report)
    freeze(archive); export(archive, tmp_path)
    def corrupt(files):
        modify_object(files, "/evaluation_report.json", lambda d: d["submission_integrity"].update(applied_candidate_tree_sha256="9" * 64))
        modify_json(files, "RUN_INDEX.json", lambda d: d["runs"][0]["submission"].update(applied_candidate_tree_sha256="9" * 64))
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", corrupt)
    with pytest.raises(EvidenceExportError, match="different trees"):
        verify_bundle(bad)


def test_pilot_list_schema_supported(archive, tmp_path):
    write_json(archive / "PILOT_RESULTS.json", [{"run_id": RUN, "status": "PASS"}]); freeze(archive)
    assert export(archive, tmp_path)["run_ids"] == [RUN]


def test_runtime_liveness_and_provider_raw_events_included(archive, tmp_path):
    run = archive / f"runs/{RUN}"
    (run / "runtime_activity.jsonl").write_text(json.dumps({"run_id": RUN, "state": "ACTIVE_MODEL_REQUEST"}) + "\n")
    (run / "gateway_requests.jsonl").write_text(json.dumps({"run_id": RUN, "status": "SSE_STREAMING"}) + "\n")
    write_json(run / "runtime_status.json", {"run_id": RUN, "status": "PASS"})
    freeze(archive); export(archive, tmp_path)
    with zipfile.ZipFile(tmp_path / "audit.zip") as package:
        names = {x["source_path"] for x in json.loads(package.read("MANIFEST.json"))["entries"]}
    assert {f"runs/{RUN}/{p}" for p in ("runtime_activity.jsonl", "gateway_requests.jsonl", "runtime_status.json")} <= names


def test_unsubstantiated_verified_child_claim_is_rejected(archive, tmp_path):
    run = archive / f"runs/{RUN}"
    summary = {"run_id": RUN, "subagents": {"verified_count": 1, "agents": [
        {"agent_id": "invented-child", "verified": True, "execution_verified": True, "completed": True, "parent_receipt": {"claimed": True}}
    ]}}
    write_json(run / "native_rollout_summary.json", summary); freeze(archive)
    with pytest.raises(EvidenceExportError, match="own execution"):
        export(archive, tmp_path)


def test_unknown_status_enum_is_rejected(archive, tmp_path):
    p = archive / f"runs/{RUN}/evaluation_report.json"
    report = json.loads(p.read_text()); report["runtime_status"] = "HYPOTHETICAL_PASS"; write_json(p, report); freeze(archive)
    with pytest.raises(EvidenceExportError, match="Unknown Run status"):
        export(archive, tmp_path)


@pytest.mark.parametrize("source", ["source/evaluator/hidden_tests/answer.py", "hidden_tests/answer.py",
                                    "reference_patches/answer.diff", "private_manifests/D.json",
                                    "source/private_labels/decision.json"])
def test_private_answer_source_cannot_be_inserted_as_cas_asset(archive, tmp_path, source):
    export(archive, tmp_path)
    def corrupt(files):
        modify_json(files, "MANIFEST.json", lambda d: d["entries"][0].update(source_path=source))
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", corrupt)
    with pytest.raises(EvidenceExportError, match="Private answer"):
        verify_bundle(bad)


def test_wrong_run_reference_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda f: modify_json(f, "RUN_INDEX.json", lambda d: d["runs"][0].update(run_id=SECOND)))
    with pytest.raises(EvidenceExportError, match="Run ID"):
        verify_bundle(bad)


def test_false_pass_oracle_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda f: modify_object(f, "/oracle-test_case-final.json", lambda d: d.update(consistent=False)))
    with pytest.raises(EvidenceExportError, match="Oracle"):
        verify_bundle(bad)


def test_raw_line_hash_tamper_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    def corrupt(files):
        modify_json(files, "MANIFEST.json", lambda d: next(x for x in d["entries"] if x["source_path"].endswith("codex_events.jsonl"))["line_provenance"][0].update(source_sha256="9" * 64))
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", corrupt)
    with pytest.raises(EvidenceExportError, match="source line"):
        verify_bundle(bad)


@pytest.mark.parametrize("member", ["../escape", "/absolute", "C:/bad", "folder\\bad", "folder/../bad", "folder//bad", "CON"])
def test_nonportable_and_traversal_member_is_rejected(archive, tmp_path, member):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda f: f.__setitem__(member, b"bad"))
    with pytest.raises(EvidenceExportError):
        verify_bundle(bad)


def test_duplicate_zip_member_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = tmp_path / "bad.zip"; bad.write_bytes((tmp_path / "audit.zip").read_bytes())
    with zipfile.ZipFile(bad, "a") as package:
        with pytest.warns(UserWarning):
            package.writestr("README_AUDIT.md", "duplicate")
    with pytest.raises(EvidenceExportError, match="Duplicate ZIP"):
        verify_bundle(bad)


def test_symlink_zip_member_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = tmp_path / "bad.zip"; bad.write_bytes((tmp_path / "audit.zip").read_bytes())
    with zipfile.ZipFile(bad, "a") as package:
        info = zipfile.ZipInfo("objects/" + "9" * 64); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
        package.writestr(info, "/etc/passwd")
    with pytest.raises(EvidenceExportError, match="links"):
        verify_bundle(bad)


def test_nested_archive_reference_is_rejected(archive, tmp_path):
    export(archive, tmp_path)
    bad = mutate_package(tmp_path / "audit.zip", tmp_path / "bad.zip", lambda f: f.__setitem__("nested.zip", b"not followed"))
    with pytest.raises(EvidenceExportError, match="Unexpected"):
        verify_bundle(bad)


def test_zip_size_budget_is_enforced(archive, tmp_path, monkeypatch):
    from benchmark import evidence_verify
    export(archive, tmp_path)
    monkeypatch.setattr(evidence_verify, "MAX_MEMBER_BYTES", 100)
    with pytest.raises(EvidenceExportError, match="byte budget"):
        verify_bundle(tmp_path / "audit.zip")


def test_compression_ratio_budget_is_enforced(archive, tmp_path, monkeypatch):
    from benchmark import evidence_verify
    export(archive, tmp_path)
    monkeypatch.setattr(evidence_verify, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(EvidenceExportError, match="ratio"):
        verify_bundle(tmp_path / "audit.zip")


def test_output_inside_source_is_refused(archive):
    with pytest.raises(EvidenceExportError, match="inside Full Archive"):
        export_archive(archive, archive / "audit.zip", created_at=FIXED_TIME)
    assert not (archive / "audit.zip").exists()


def test_output_overwrite_is_refused(archive, tmp_path):
    export(archive, tmp_path)
    original = (tmp_path / "audit.zip").read_bytes()
    with pytest.raises(EvidenceExportError, match="overwrite"):
        export(archive, tmp_path)
    assert (tmp_path / "audit.zip").read_bytes() == original


def test_source_hash_mismatch_is_refused(archive, tmp_path):
    (archive / f"runs/{RUN}/evaluation_report.json").write_text("{}")
    with pytest.raises(EvidenceExportError, match="frozen index"):
        export(archive, tmp_path)
    assert not (tmp_path / "audit.zip").exists()


def test_source_link_is_refused(archive, tmp_path):
    source = archive / f"runs/{RUN}/codex_stderr.log"
    source.symlink_to(tmp_path / "private-secret")
    value = json.loads((archive / "EVIDENCE_MANIFEST.json").read_text())
    value["ordinary_files_sha256"][source.relative_to(archive).as_posix()] = "f" * 64
    write_json(archive / "EVIDENCE_MANIFEST.json", value)
    with pytest.raises(EvidenceExportError):
        export(archive, tmp_path)


def test_invalid_or_duplicate_selection_is_refused(archive, tmp_path):
    for ids in ([RUN, RUN], [SECOND], ["../bad"]):
        with pytest.raises(EvidenceExportError):
            export_archive(archive, tmp_path / "audit.zip", run_ids=ids, created_at=FIXED_TIME)


def test_date_must_be_explicit_timezone(archive, tmp_path):
    with pytest.raises(EvidenceExportError, match="timezone"):
        export_archive(archive, tmp_path / "audit.zip", created_at="2026-10-10T00:00:00")


def test_completed_run_seal_export_without_collection_final_manifest(archive, tmp_path):
    run = archive / f"runs/{RUN}"
    hashes = {p.relative_to(run).as_posix(): sha256(p.read_bytes()).hexdigest() for p in run.rglob("*") if p.is_file()}
    write_json(run / "run_evidence_manifest.json", {"run_id": RUN, "files": hashes})
    (archive / "EVIDENCE_MANIFEST.json").unlink()
    receipt = export_archive(archive, tmp_path / "audit.zip", run_ids=[RUN], created_at=FIXED_TIME)
    assert receipt["status"] == "PASS" and receipt["full_archive_indexed_bytes"] is None


def test_active_state_run_is_not_exported(archive, tmp_path):
    run = archive / f"runs/{RUN}"; write_json(run / "run_evidence_manifest.json", {"run_id": RUN, "files": {}})
    (run / "codex-state").mkdir(); (archive / "EVIDENCE_MANIFEST.json").unlink()
    with pytest.raises(EvidenceExportError, match="stopped"):
        export_archive(archive, tmp_path / "audit.zip", run_ids=[RUN], created_at=FIXED_TIME)


def test_cross_platform_posix_relative_path():
    assert safe_relative("runs/" + RUN + "/artifacts/oracle-test[workers2].json")
    with pytest.raises(EvidenceVerifyError):
        safe_relative("runs\\" + RUN + "\\report.json")
