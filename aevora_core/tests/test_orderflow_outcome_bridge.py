"""Synthetic contract fixtures; these tests are not OrderFlow engineering runs."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from aevora.orderflow_outcome_bridge import (
    OutcomeVerificationError, TrustAnchor, canonical_bytes, public_outcome_summary,
    verify_outcome,
)

RUN = "b663edbb-cbd8-42a3-b4cb-dbdd112ab789"
REPORT = f"offline/runs/{RUN}/evaluation_report.json"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def composite(files):
    value = sha256()
    for name, digest in sorted(files.items()):
        value.update(name.encode() + b"\0" + digest.encode() + b"\n")
    return value.hexdigest()


def tree_digest(files):
    value = sha256()
    for name, data in sorted(files.items()):
        name = name.encode()
        value.update(len(name).to_bytes(8, "big") + name + len(data).to_bytes(8, "big") + data)
    return value.hexdigest()


class Evidence:
    def __init__(self, root, *, fail=False, episode="A"):
        self.root = root
        self.run = root / "offline/runs" / RUN
        self.report_path = self.run / "evaluation_report.json"
        self.snapshot = root / "final_source_snapshot"
        source = {"evaluator/runner.py": b"# trusted synthetic fixture, never executed\n",
                  "evaluator/fingerprints.py": b'EVALUATOR_VERSION = "fixture-1"\n',
                  "evaluator/oracle.py": b"# synthetic Oracle source, not executed\n",
                  "evaluator/hidden_tests/conftest.py": b"# synthetic trusted fixture\n",
                  f"evaluator/hidden_tests/episode_{episode.lower()}/test_fixture.py": b"# synthetic suite source\n",
                  "benchmark/sandbox.py": b"# synthetic Sandbox source\n",
                  "benchmark/submission.py": (Path(__file__).resolve().parents[2] / "benchmark/submission.py").read_bytes()}
        for name, data in source.items():
            path = self.snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        hashes = {name: sha256(data).hexdigest() for name, data in source.items() if name != "benchmark/submission.py"}
        suite_hashes = {name: digest for name, digest in hashes.items() if name.startswith("evaluator/hidden_tests/")
                        or name == "evaluator/oracle.py"}
        self.private = {"suite": "episode_" + episode.lower(), "suite_version": "fixture-1",
                        "expected_test_count": 2, "expected_tests": ["test_one", "test_two"]}
        self.pm_path = self.snapshot / f"evaluator/private_manifests/{episode}.json"
        write_json(self.pm_path, self.private)
        candidate = {"app/__init__.py": b"", "app/service.py": b"class OrderFlow: pass\n"}
        for name, data in candidate.items():
            path = self.run / "candidate" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        digest = tree_digest(candidate)
        self.junit = self.run / "artifacts/junit.xml"
        self.junit.parent.mkdir(parents=True)
        self.junit.write_text('<testsuites><testsuite tests="2" failures="' + str(int(fail)) +
            '" errors="0" skipped="0"><testcase classname="test_fixture" name="test_one" time="0.1"/>' +
            '<testcase classname="test_fixture" name="test_two" time="0.2">' +
            ('<failure message="fixture failure"/>' if fail else '') + '</testcase></testsuite></testsuites>')
        self.oracle = {"consistent": not fail, "violations": ["synthetic counterexample"] if fail else [],
                       "oracle_version": "synthetic-test-fixture"}
        self.oracle_path = self.run / "artifacts/oracle-fixture.json"
        write_json(self.oracle_path, self.oracle)
        suite = {"version": "fixture-1", "files": suite_hashes, "sha256": composite(suite_hashes),
                 "id": self.private["suite"]}
        self.report = {"run_id": RUN, "episode_id": episode, "evaluation_status": "FAIL" if fail else "PASS",
            "overall_status": "FAIL" if fail else "PASS", "evaluator_status": "FAIL" if fail else "PASS",
            "submission_integrity_status": "PASS", "execution_errors": [],
            "fingerprints": {"private_manifest_sha256": sha256(self.pm_path.read_bytes()).hexdigest(),
                "evaluator": {"version": "fixture-1", "files": hashes, "sha256": composite(hashes)},
                "test_suite": suite, "execution_strategy": "single-worker" if episode == "A" else "shared-db-workers"},
            "artifacts": {"junit_xml": str(self.junit), "oracle_records": [str(self.oracle_path)]},
            "test_results": {"collected": 2, "passed": 2 - int(fail), "failed": int(fail), "errors": 0,
                "skipped": 0, "tests": [{"name": "test_one", "nodeid": "test_fixture::test_one", "outcome": "PASS"},
                {"name": "test_two", "nodeid": "test_fixture::test_two", "outcome": "FAIL" if fail else "PASS"}]},
            "pytest_exit_code": int(fail), "submission": {"kind": "workspace", "evaluated_sha256": digest},
            "submission_integrity": {"expected_tree_sha256": digest, "applied_candidate_tree_sha256": digest,
                                      "patch_sha256": "NOT_APPLICABLE"},
            "database_oracle": [self.oracle], "recovery_coverage": {"status": "NOT_APPLICABLE"},
            "evaluation_ended_at": "2026-10-11T00:00:00+00:00"}
        self.report["evaluation_started_at"] = "2026-10-10T23:59:59+00:00"
        if episode == "D":
            self.add_workers()
        self.commit()

    def add_workers(self):
        topology = {"fixture_type": "synthetic_test_fixture", "workers": [1, 2]}
        top = self.run / "artifacts/topology-fixture.json"
        write_json(top, topology)
        self.report["artifacts"]["topology_records"] = [str(top)]
        self.report["worker_topology_evidence"] = [topology]
        recovery = [{"label": point, "availability": "AVAILABLE", "kill": {
            "signal": "SIGKILL", "worker_pidfd_exited": True, "identity": {"host_pid": 123}}}
            for point in ("before_commit", "transaction_committed", "before_response")]
        paths = []
        for number, row in enumerate(recovery):
            path = self.run / f"artifacts/recovery-{number}.json"
            write_json(path, row)
            paths.append(str(path))
        self.report["artifacts"]["recovery_records"] = paths
        self.report["recovery_evidence"] = recovery
        self.report["recovery_coverage"] = {"status": "COMPLETE", "points": {
            row["label"]: {"availability": "AVAILABLE", "verified_interruptions": 1} for row in recovery}}

    def commit(self):
        write_json(self.report_path, self.report)
        files = {path.relative_to(self.root).as_posix(): sha256(path.read_bytes()).hexdigest()
                 for path in self.root.rglob("*") if path.is_file() and path.name != "EVIDENCE_MANIFEST.json"}
        self.manifest = self.root / "EVIDENCE_MANIFEST.json"
        write_json(self.manifest, {"ordinary_files_sha256": files})
        self.anchor = TrustAnchor(self.root, sha256(self.manifest.read_bytes()).hexdigest(), {REPORT: RUN})

    def verify(self):
        return verify_outcome(self.anchor, REPORT)


@pytest.fixture
def evidence(tmp_path):
    return Evidence(tmp_path / "archive")


def test_pass_is_derived_and_repeatable(evidence):
    first = evidence.verify()
    assert first == evidence.verify()
    assert first["id"] == "orderflow:" + RUN
    assert first["verdict"] == "PASS" and first["attribution"] == "UNKNOWN"
    body = {key: value for key, value in first.items() if key != "immutable_digest"}
    assert first["immutable_digest"] == sha256(canonical_bytes(body)).hexdigest()
    assert "private_manifest_sha256" in first["private_verification"]


def test_complete_fail_is_verified_not_dropped(tmp_path):
    outcome = Evidence(tmp_path / "archive", fail=True).verify()
    assert outcome["verdict"] == "FAIL"
    assert outcome["test_counts"]["failed"] == 1
    assert outcome["private_verification"]["inconsistent_oracle_count"] == 1


def test_public_projection_never_leaks_private_evidence(evidence):
    public = public_outcome_summary(evidence.verify())
    assert "source_reference" not in public and "private_verification" not in public
    assert str(evidence.root) not in json.dumps(public)
    assert "test_one" not in json.dumps(public)


def test_pin_cannot_be_taken_from_report(evidence):
    bad = replace(evidence.anchor, manifest_sha256="0" * 64)
    with pytest.raises(OutcomeVerificationError, match="trusted pin"):
        verify_outcome(bad, REPORT)


@pytest.mark.parametrize("reference", ["../evaluation_report.json", "/etc/passwd", "x/../y", "x\\y", "./x"])
def test_outside_traversal_and_noncanonical_paths_refused(evidence, reference):
    with pytest.raises(OutcomeVerificationError):
        verify_outcome(evidence.anchor, reference)


def test_unlisted_report_refused(evidence):
    with pytest.raises(OutcomeVerificationError, match="allowlist"):
        verify_outcome(evidence.anchor, "unlisted/evaluation_report.json")


def test_root_and_parent_symlinks_refused(evidence, tmp_path):
    link = tmp_path / "alias"
    link.symlink_to(evidence.root, target_is_directory=True)
    with pytest.raises(OutcomeVerificationError):
        verify_outcome(replace(evidence.anchor, archive_root=link), REPORT)


@pytest.mark.parametrize("kind", ["report", "manifest", "junit", "candidate", "source"])
def test_symlink_files_refused(evidence, tmp_path, kind):
    paths = {"report": evidence.report_path, "manifest": evidence.manifest,
             "junit": evidence.junit, "candidate": evidence.run / "candidate/app/service.py",
             "source": evidence.snapshot / "evaluator/runner.py"}
    path = paths[kind]
    other = tmp_path / ("external-" + kind)
    other.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(other)
    with pytest.raises(OutcomeVerificationError):
        evidence.verify()


def test_hardlinked_report_refused(evidence, tmp_path):
    os.link(evidence.report_path, tmp_path / "duplicate")
    with pytest.raises(OutcomeVerificationError, match="single-link"):
        evidence.verify()


def test_unsealed_byte_change_refused(evidence):
    evidence.report_path.write_text(evidence.report_path.read_text() + " ")
    with pytest.raises(OutcomeVerificationError, match="trusted pin"):
        evidence.verify()


def test_duplicate_report_json_keys_refused(evidence):
    data = evidence.report_path.read_text()
    evidence.report_path.write_text('{"run_id":"fake",' + data[1:])
    hashes = json.loads(evidence.manifest.read_text())
    hashes["ordinary_files_sha256"][REPORT] = sha256(evidence.report_path.read_bytes()).hexdigest()
    write_json(evidence.manifest, hashes)
    evidence.anchor = replace(evidence.anchor, manifest_sha256=sha256(evidence.manifest.read_bytes()).hexdigest())
    with pytest.raises(OutcomeVerificationError, match="Duplicate"):
        evidence.verify()


@pytest.mark.parametrize("field,value", [("run_id", "another-run"), ("overall_status", "FAIL"),
    ("pytest_exit_code", 1), ("pytest_exit_code", False), ("evaluation_status", "TIMEOUT"),
    ("submission_integrity_status", "ERROR"), ("execution_errors", ["changed evaluator"]),
    ("evaluation_started_at", "2026-10-11T00:00:01+00:00"), ("evaluation_ended_at", "2026-10-11T00:00:00")])
def test_forged_report_fields_refused_even_if_locally_sealed(evidence, field, value):
    evidence.report[field] = value
    evidence.commit()
    with pytest.raises(OutcomeVerificationError):
        evidence.verify()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "skip", "declared", "doctype", "entity", "nan", "outcome"])
def test_malformed_or_incomplete_junit_refused(evidence, mutation):
    text = evidence.junit.read_text()
    if mutation == "missing":
        text = text.replace('<testcase classname="test_fixture" name="test_one" time="0.1"/>', '')
    elif mutation == "duplicate":
        text = text.replace('name="test_two"', 'name="test_one"')
    elif mutation == "skip":
        text = text.replace('<testcase classname="test_fixture" name="test_two" time="0.2">',
                            '<testcase classname="test_fixture" name="test_two" time="0.2"><skipped/>')
    elif mutation == "declared":
        text = text.replace('tests="2"', 'tests="3"')
    elif mutation == "doctype":
        text = '<!DOCTYPE testsuites [<!ENTITY x "hello">]>' + text
    elif mutation == "entity":
        text = '<!ENTITY x "hello">' + text
    elif mutation == "nan":
        text = text.replace('time="0.1"', 'time="NaN"')
    else:
        text = text.replace('time="0.2">', 'time="0.2"><failure/>')
    evidence.junit.write_text(text)
    evidence.commit()
    with pytest.raises(OutcomeVerificationError):
        evidence.verify()


@pytest.mark.parametrize("mutation", ["suite_hash", "evaluator_hash", "source", "private_count", "private_names", "after", "omitted_source"])
def test_frozen_fingerprint_mismatch_refused(evidence, mutation):
    if mutation == "suite_hash":
        evidence.report["fingerprints"]["test_suite"]["sha256"] = "0" * 64
    elif mutation == "evaluator_hash":
        evidence.report["fingerprints"]["evaluator"]["files"]["evaluator/runner.py"] = "0" * 64
    elif mutation == "source":
        (evidence.snapshot / "evaluator/runner.py").write_text("# substituted evaluator\n")
    elif mutation.startswith("private"):
        evidence.private["expected_test_count" if mutation == "private_count" else "expected_tests"] = (
            1 if mutation == "private_count" else ["test_one", "test_one"])
        write_json(evidence.pm_path, evidence.private)
        evidence.report["fingerprints"]["private_manifest_sha256"] = sha256(evidence.pm_path.read_bytes()).hexdigest()
    elif mutation == "omitted_source":
        group = evidence.report["fingerprints"]["evaluator"]
        group["files"].pop("evaluator/runner.py")
        group["sha256"] = composite(group["files"])
    else:
        evidence.report["fingerprints_after_evaluation"] = evidence.report["fingerprints"]
    evidence.commit()
    with pytest.raises(OutcomeVerificationError):
        evidence.verify()


@pytest.mark.parametrize("mutation", ["tree", "extra", "digest", "oracle", "oracle_missing", "oracle_crossrun"])
def test_candidate_and_oracle_mismatch_refused(evidence, mutation):
    if mutation == "tree":
        (evidence.run / "candidate/app/service.py").write_text("# edited after evaluation\n")
    elif mutation == "extra":
        (evidence.run / "candidate/app/secret.txt").write_text("not source")
    elif mutation == "digest":
        evidence.report["submission_integrity"]["applied_candidate_tree_sha256"] = "0" * 64
    elif mutation == "oracle":
        write_json(evidence.oracle_path, {"consistent": False, "violations": ["real counterexample"]})
    elif mutation == "oracle_missing":
        evidence.report["database_oracle"] = []
        evidence.report["artifacts"]["oracle_records"] = []
    else:
        another = evidence.root / "another-run/artifacts/oracle-fixture.json"
        write_json(another, evidence.oracle)
        evidence.report["artifacts"]["oracle_records"] = [str(another)]
    evidence.commit()
    with pytest.raises(OutcomeVerificationError):
        evidence.verify()


def test_unsealed_added_candidate_refused(evidence):
    (evidence.run / "candidate/app/new.py").write_text("# unexpected source\n")
    with pytest.raises(OutcomeVerificationError, match="identities"):
        evidence.verify()


def test_claimed_evaluator_version_must_match_frozen_source(evidence):
    evidence.report["fingerprints"]["evaluator"]["version"] = "invented-version"
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="Evaluator version"):
        evidence.verify()


def test_oracle_identity_cannot_be_counted_twice(evidence):
    evidence.report["database_oracle"].append(evidence.oracle)
    evidence.report["artifacts"]["oracle_records"].append(str(evidence.oracle_path))
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="duplicated"):
        evidence.verify()


def test_d_recovery_requires_independent_kill_records(tmp_path):
    evidence = Evidence(tmp_path / "archive", episode="D")
    assert evidence.verify()["verdict"] == "PASS"
    row = evidence.report["recovery_evidence"][1]
    row["kill"]["worker_pidfd_exited"] = False
    write_json(Path(evidence.report["artifacts"]["recovery_records"][1]), row)
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="Recovery coverage"):
        evidence.verify()


def test_d_missing_topology_refused(tmp_path):
    evidence = Evidence(tmp_path / "archive", episode="D")
    evidence.report["worker_topology_evidence"] = []
    evidence.report["artifacts"]["topology_records"] = []
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="topology"):
        evidence.verify()


def test_d_forged_recovery_summary_refused(tmp_path):
    evidence = Evidence(tmp_path / "archive", episode="D")
    evidence.report["recovery_coverage"]["status"] = "NOT_APPLICABLE"
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="Recovery summary"):
        evidence.verify()


def test_patch_identity_is_checked(evidence):
    patch = evidence.run / "patch.diff"
    patch.write_text("--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-class Before: pass\n+class OrderFlow: pass\n")
    baseline = {"app/__init__.py": b"", "app/service.py": b"class Before: pass\n"}
    for name, data in baseline.items():
        path = evidence.run / "sealed_public_inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    digest = sha256(patch.read_bytes()).hexdigest()
    evidence.report["submission"].update(kind="patch", sha256=digest)
    evidence.report["submission_integrity"]["patch_sha256"] = digest
    evidence.report["submission_integrity"]["baseline_tree_sha256"] = tree_digest(baseline)
    evidence.report["artifacts"]["patch"] = str(patch)
    evidence.commit()
    assert evidence.verify()["patch_sha256"] == digest
    evidence.report["submission_integrity"]["patch_sha256"] = "0" * 64
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="patch digest"):
        evidence.verify()


def test_patch_content_cannot_be_passed_by_consistent_forged_hashes(evidence):
    patch = evidence.run / "patch.diff"
    patch.write_text("--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-class Before: pass\n+class Different: pass\n")
    baseline = {"app/__init__.py": b"", "app/service.py": b"class Before: pass\n"}
    for name, data in baseline.items():
        path = evidence.run / "sealed_public_inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    digest = sha256(patch.read_bytes()).hexdigest()
    evidence.report["submission"].update(kind="patch", sha256=digest)
    evidence.report["submission_integrity"].update(patch_sha256=digest, baseline_tree_sha256=tree_digest(baseline))
    evidence.report["artifacts"]["patch"] = str(patch)
    evidence.commit()
    with pytest.raises(OutcomeVerificationError, match="Patch-derived"):
        evidence.verify()


def test_large_raw_report_is_bounded_before_hashing(evidence):
    with evidence.report_path.open("wb") as file:
        file.truncate(64 * 1024**2 + 1)
    with pytest.raises(OutcomeVerificationError, match="byte budget"):
        evidence.verify()


def test_current_live_uses_separately_pinned_snapshot(evidence):
    anchor = TrustAnchor(evidence.run, "0" * 64, {"evaluation_report.json": RUN}, profile="current_live",
        manifest_relative_path="run_evidence_manifest.json", source_archive_root=evidence.root,
        source_manifest_sha256=evidence.anchor.manifest_sha256)
    files = {path.relative_to(evidence.run).as_posix(): sha256(path.read_bytes()).hexdigest()
             for path in evidence.run.rglob("*") if path.is_file()}
    manifest = evidence.run / "run_evidence_manifest.json"
    write_json(manifest, {"files": files})
    anchor = replace(anchor, manifest_sha256=sha256(manifest.read_bytes()).hexdigest())
    outcome = verify_outcome(anchor, "evaluation_report.json")
    assert outcome["source_type"] == "current_live" and outcome["run_id"] == RUN
