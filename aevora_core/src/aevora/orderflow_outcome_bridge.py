"""Verify locally authorized OrderFlow evidence without executing candidate code.

This module has no Participant API, graph credentials or verdict argument. Its
trust root is supplied by the maintainer, outside the Participant environment.
Local pinned hashes establish byte provenance, not external attestation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping
import ast
from .source_evidence import (EvidenceFiles, OutcomeVerificationError, _require,
    _relative, _digest, _json, read_junit)

VERIFIER_IDENTITY = "AevoraOrderFlowOutcomeBridge/0.3.0"
_MAX_MANIFEST = 32 * 1024**2
# Actual sealed M1 D reports embed all 201 topology observations (25-28 MB).
# Keep a finite budget that admits those existing, unmodified raw reports.
_MAX_REPORT = 64 * 1024**2
_MAX_SOURCE = 2 * 1024**2
_MAX_XML = 8 * 1024**2


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class TrustAnchor:
    """Maintainer configuration; never construct this from Participant fields.

    historical_full uses a pinned Full manifest with its frozen source snapshot.
    current_live uses the pinned Run seal and a separately pinned source archive.
    allowed_reports maps exact archive-relative report paths to authorized Run IDs.
    """

    archive_root: Path
    manifest_sha256: str
    allowed_reports: Mapping[str, str]
    profile: str = "historical_full"
    manifest_relative_path: str = "EVIDENCE_MANIFEST.json"
    source_snapshot_relative_path: str = "final_source_snapshot"
    source_archive_root: Path | None = None
    source_manifest_sha256: str | None = None
    source_manifest_relative_path: str = "EVIDENCE_MANIFEST.json"

    def __post_init__(self) -> None:
        _require(self.profile in {"historical_full", "current_live"}, "Unknown trust profile")
        _digest(self.manifest_sha256)
        object.__setattr__(self, "archive_root", Path(self.archive_root).absolute())
        _relative(self.manifest_relative_path)
        _relative(self.source_snapshot_relative_path)
        _require(isinstance(self.allowed_reports, Mapping) and 0 < len(self.allowed_reports) <= 1000,
                 "An explicit report allowlist is required")
        reports = {_relative(name): run for name, run in self.allowed_reports.items()}
        _require(all(isinstance(run, str) and 0 < len(run) <= 200 and "/" not in run for run in reports.values()),
                 "Invalid authorized Run identity")
        object.__setattr__(self, "allowed_reports", MappingProxyType(reports))
        if self.source_archive_root is not None:
            object.__setattr__(self, "source_archive_root", Path(self.source_archive_root).absolute())
            _digest(self.source_manifest_sha256)
            _relative(self.source_manifest_relative_path)
        else:
            _require(self.source_manifest_sha256 is None, "Separate source pin needs a source root")


class _Archive(EvidenceFiles):
    """OrderFlow adds its candidate-tree protocol to the common bounded reader."""

    def tree(self, relative: str, manifest: Mapping[str, str]) -> dict[str, bytes]:
        relative = _relative(relative)
        parent, name = self._parent(relative)
        try:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        finally:
            os.close(parent)
        names: list[str] = []
        entries = 0

        def visit(directory: int, prefix: str, depth: int) -> None:
            nonlocal entries
            _require(depth <= 20, "Candidate directory depth exceeded")
            for item in sorted(os.listdir(directory)):
                entries += 1
                _require(entries <= 1000, "Candidate entry budget exceeded")
                info = os.stat(item, dir_fd=directory, follow_symlinks=False)
                rel = prefix + "/" + item
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(item, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                    try:
                        visit(child, rel, depth + 1)
                    finally:
                        os.close(child)
                else:
                    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and item.endswith(".py"),
                             "Candidate links, special files and non-Python entries are forbidden")
                    names.append(rel)
        try:
            visit(fd, relative, 0)
        finally:
            os.close(fd)
        _require(0 < len(names) <= 100, "Candidate file count is invalid")
        sealed = {name for name in manifest if name.startswith(relative + "/")}
        _require(set(names) == sealed, "Candidate file identities differ from pinned archive")
        tree = {"app/" + name[len(relative) + 1:]: self.read(name, _MAX_SOURCE, manifest[name]) for name in names}
        _require(sum(map(len, tree.values())) <= _MAX_SOURCE, "Candidate source byte budget exceeded")
        return tree


def _manifest(archive: _Archive, relative: str, pin: str) -> dict[str, str]:
    value = _json(archive.read(relative, _MAX_MANIFEST, pin))
    _require(isinstance(value, dict), "Manifest must be an object")
    files = value.get("ordinary_files_sha256", value.get("files"))
    _require(isinstance(files, dict) and 0 < len(files) <= 100000, "Invalid trusted file manifest")
    return {_relative(name): _digest(digest) for name, digest in files.items()}


def _sealed(archive: _Archive, manifest: Mapping[str, str], relative: str, limit: int) -> bytes:
    _require(relative in manifest, "Required evidence is absent from trusted manifest")
    return archive.read(relative, limit, manifest[relative])


def _source_digest(files: Mapping[str, str]) -> str:
    value = sha256()
    for name, digest in sorted(files.items()):
        value.update(name.encode() + b"\0" + digest.encode() + b"\n")
    return value.hexdigest()


def _tree_digest(tree: Mapping[str, bytes]) -> str:
    value = sha256()
    for name, data in sorted(tree.items()):
        encoded = name.encode()
        value.update(len(encoded).to_bytes(8, "big") + encoded + len(data).to_bytes(8, "big") + data)
    return value.hexdigest()


def _junit(data: bytes, required: list[str]) -> dict:
    return read_junit(data, required)


def _verify(anchor: TrustAnchor, archive: _Archive, source: _Archive,
            files: Mapping[str, str], source_files: Mapping[str, str], reference: str) -> dict:
    relative = archive.reference(reference)
    _require(relative in anchor.allowed_reports, "Report is not on the authorized allowlist")
    report_bytes = _sealed(archive, files, relative, _MAX_REPORT)
    report = _json(report_bytes)
    _require(isinstance(report, dict), "Report must be an object")
    run_id = anchor.allowed_reports[relative]
    parent = PurePosixPath(relative).parent
    path_run_id = archive.root.name if parent.as_posix() == "." else parent.name
    _require(report.get("run_id") == run_id and path_run_id == run_id,
             "Report Run identity differs from authorized path")
    episode = report.get("episode_id")
    _require(episode in {"A", "D", "D-V02"}, "Only complete implemented A/D/D-V02 outcomes are admitted")
    verdict = report.get("evaluation_status")
    _require(verdict in {"PASS", "FAIL"} and report.get("overall_status") == verdict
             and report.get("evaluator_status") == verdict, "Incomplete or inconsistent engineering verdict")
    _require(report.get("submission_integrity_status") == "PASS" and not report.get("execution_errors")
             and "fingerprints_after_evaluation" not in report, "Submission/evaluator integrity is not verified")
    fingerprint = report.get("fingerprints")
    _require(isinstance(fingerprint, dict), "Missing evaluator fingerprints")
    prefix = anchor.source_snapshot_relative_path
    pm_name = prefix + "/evaluator/private_manifests/" + episode + ".json"
    pm_bytes = _sealed(source, source_files, pm_name, _MAX_SOURCE)
    _require(sha256(pm_bytes).hexdigest() == fingerprint.get("private_manifest_sha256"),
             "Private manifest identity differs from frozen evaluator")
    config = _json(pm_bytes)
    required = config.get("expected_tests")
    _require(isinstance(required, list) and 0 < len(required) <= 1000
             and all(isinstance(name, str) and name for name in required)
             and len(set(required)) == len(required), "Invalid frozen required test set")
    _require(type(config.get("expected_test_count")) is int and config["expected_test_count"] == len(required),
             "Private manifest test count is inconsistent")
    for key in ("evaluator", "test_suite"):
        group = fingerprint.get(key)
        _require(isinstance(group, dict) and isinstance(group.get("files"), dict)
                 and 0 < len(group["files"]) <= 1000 and isinstance(group.get("version"), str),
                 "Invalid evaluator/suite fingerprint group")
        hashes = {_relative(name): _digest(digest) for name, digest in group["files"].items()}
        snapshot_names = {name[len(prefix) + 1:] for name in source_files if name.startswith(prefix + "/")}
        evaluator_names = {name for name in snapshot_names if name.startswith("evaluator/")
                           and name.endswith(".py") and "__pycache__" not in PurePosixPath(name).parts}
        evaluator_names.add("benchmark/sandbox.py")
        suite_directory = "episode_d_v02" if episode == "D-V02" else "episode_" + episode.lower()
        suite_names = {name for name in snapshot_names
                       if name.startswith("evaluator/hidden_tests/" + suite_directory + "/")
                       and name.endswith(".py") and "__pycache__" not in PurePosixPath(name).parts}
        suite_names.update({"evaluator/hidden_tests/conftest.py", "evaluator/oracle.py"})
        _require(set(hashes) == (evaluator_names if key == "evaluator" else suite_names),
                 "Fingerprint file identities differ from complete frozen source set")
        _require(_source_digest(hashes) == group.get("sha256"), "Composite source fingerprint is inconsistent")
        for name, digest in hashes.items():
            data = _sealed(source, source_files, prefix + "/" + name, _MAX_SOURCE)
            _require(sha256(data).hexdigest() == digest, "Evaluator source differs from frozen fingerprint")
    suite = fingerprint["test_suite"]
    _require(suite.get("id") == config.get("suite") and suite.get("version") == config.get("suite_version"),
             "Private manifest suite identity is inconsistent")
    version_source = _sealed(source, source_files, prefix + "/evaluator/fingerprints.py", _MAX_SOURCE)
    definitions = ast.parse(version_source.decode("utf-8"))
    versions = [node.value.value for node in definitions.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "EVALUATOR_VERSION" for target in node.targets)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    _require(versions == [fingerprint["evaluator"].get("version")], "Evaluator version differs from frozen source")
    started, ended = (datetime.fromisoformat(report[key]) for key in ("evaluation_started_at", "evaluation_ended_at"))
    _require(started.tzinfo is not None and ended.tzinfo is not None and started <= ended,
             "Evaluation timestamps are invalid")
    artifacts = report.get("artifacts")
    _require(isinstance(artifacts, dict), "Missing independent evaluation artifacts")
    junit_name = archive.reference(artifacts.get("junit_xml"))
    run_prefix = "" if parent.as_posix() == "." else parent.as_posix() + "/"
    _require(junit_name == run_prefix + "artifacts/junit.xml", "JUnit belongs to a different Run")
    junit_bytes = _sealed(archive, files, junit_name, _MAX_XML)
    tests = _junit(junit_bytes, required)
    recorded = report.get("test_results")
    _require(isinstance(recorded, dict) and isinstance(recorded.get("tests"), list), "Missing reported test identities")
    _require(all(type(recorded.get(key)) is int and recorded[key] == tests[key]
                 for key in ("collected", "passed", "failed", "errors", "skipped")),
             "Report counts differ from independent JUnit")
    expected_rows = [{key: row.get(key) for key in ("name", "nodeid", "outcome")} for row in recorded["tests"]]
    _require(sorted(expected_rows, key=lambda row: row["name"]) == sorted(tests["tests"], key=lambda row: row["name"]),
             "Report testcase outcomes differ from independent JUnit")
    _require(tests["errors"] == 0 and tests["skipped"] == 0, "Incomplete or errored hidden suite cannot be verified")
    expected_exit = 0 if verdict == "PASS" else 1
    _require(type(report.get("pytest_exit_code")) is int and report["pytest_exit_code"] == expected_exit
             and (tests["failed"] == 0 if verdict == "PASS" else tests["failed"] > 0),
             "Pytest exit and engineering verdict are inconsistent")
    tree = archive.tree(run_prefix + "candidate/app", files)
    candidate_digest = _tree_digest(tree)
    integrity = report.get("submission_integrity")
    submission = report.get("submission")
    _require(isinstance(integrity, dict) and isinstance(submission, dict), "Missing submission provenance")
    _require(candidate_digest == submission.get("evaluated_sha256") == integrity.get("expected_tree_sha256")
             == integrity.get("applied_candidate_tree_sha256"), "Evaluated candidate tree differs from submission")
    patch_digest = None
    if submission.get("kind") == "patch":
        patch_name = archive.reference(artifacts.get("patch"))
        _require(patch_name == run_prefix + "patch.diff", "Patch belongs to a different Run")
        patch_bytes = _sealed(archive, files, patch_name, _MAX_SOURCE)
        patch_digest = sha256(patch_bytes).hexdigest()
        _require(patch_digest == submission.get("sha256") == integrity.get("patch_sha256"),
                 "Submitted patch digest is inconsistent")
        baseline = archive.tree(run_prefix + "sealed_public_inputs/app", files)
        _require(_tree_digest(baseline) == integrity.get("baseline_tree_sha256"),
                 "Patch baseline differs from sealed public inputs")
        # Reuse OrderFlow's mature, non-executing bounded strict interpreter.
        # Import only in the trusted host, and only its pinned source version.
        parser_source = _sealed(source, source_files, prefix + "/benchmark/submission.py", _MAX_SOURCE)
        import benchmark.submission as strict_submission
        parser_path = Path(strict_submission.__file__).absolute()
        parser_archive = _Archive(parser_path.parent)
        try:
            actual_parser = parser_archive.read(parser_path.name, _MAX_SOURCE)
        finally:
            parser_archive.close()
        _require(actual_parser == parser_source, "Trusted diff interpreter version differs from source pin")
        derived = strict_submission.expected_tree_from_patch(baseline, patch_bytes)
        _require(derived == tree, "Patch-derived source does not equal evaluated candidate")
        if report.get("agent", {}).get("adapter") == "codex_exec":
            extracted = report["agent"].get("extracted_submission")
            _require(isinstance(extracted, dict) and extracted.get("sha256") == patch_digest
                     and extracted.get("baseline_tree_sha256") == integrity["baseline_tree_sha256"]
                     and extracted.get("expected_tree_sha256") == candidate_digest
                     and report["agent"].get("submission_sha256") == patch_digest,
                     "Native submission extraction differs from verified source")
            _require(extracted.get("expected_files_sha256") == {name: sha256(data).hexdigest() for name, data in tree.items()},
                     "Native per-file extraction differs from evaluated source")
    else:
        _require(submission.get("kind") == "workspace" and integrity.get("patch_sha256") == "NOT_APPLICABLE",
                 "Unrecognized submission provenance")
    observations = {}
    for key, recorded_key in (("oracle_records", "database_oracle"), ("topology_records", "worker_topology_evidence"),
                              ("recovery_records", "recovery_evidence")):
        refs = artifacts.get(key, [])
        recorded_values = report.get(recorded_key, [])
        _require(isinstance(refs, list) and isinstance(recorded_values, list) and len(refs) == len(recorded_values)
                 and len(refs) <= 1000, "Independent artifact count differs from report")
        normalized_refs = [archive.reference(name) for name in refs]
        _require(len(set(normalized_refs)) == len(normalized_refs), "Independent artifact identities are duplicated")
        loaded = []
        for name in refs:
            rel = archive.reference(name)
            _require(rel.startswith(run_prefix + "artifacts/"), "Oracle artifact belongs to a different Run")
            loaded.append(_json(_sealed(archive, files, rel, _MAX_REPORT)))
        _require(loaded == recorded_values, "Independent observation differs from report")
        observations[recorded_key] = loaded
    oracles = observations["database_oracle"]
    _require(bool(oracles) and all(isinstance(row, dict) and type(row.get("consistent")) is bool
                                  and isinstance(row.get("violations"), list) for row in oracles),
             "Missing valid independent database Oracle")
    _require(all(row["consistent"] == (len(row["violations"]) == 0) for row in oracles),
             "Oracle consistency and violations disagree")
    if verdict == "PASS":
        _require(all(row["consistent"] for row in oracles), "PASS has inconsistent independent database Oracle")
    topology = observations["worker_topology_evidence"]
    recovery = observations["recovery_evidence"]
    coverage = report.get("recovery_coverage")
    _require(isinstance(coverage, dict), "Missing recovery coverage")
    if episode in {"D", "D-V02"}:
        _require(bool(topology) and fingerprint.get("execution_strategy") == "shared-db-workers",
                 "D has no independent Worker topology")
        points = {}
        for point in ("before_commit", "transaction_committed", "before_response"):
            rows = [row for row in recovery if isinstance(row, dict) and row.get("label") == point]
            reached = [row for row in rows
                       if row.get("availability") == "AVAILABLE" and isinstance(row.get("kill"), dict)
                       and row["kill"].get("signal") == "SIGKILL" and row["kill"].get("worker_pidfd_exited") is True]
            points[point] = len(reached)
            stated = coverage.get("points", {}).get(point, {})
            _require(stated.get("verified_interruptions") == len(reached)
                     and stated.get("availability") == ("AVAILABLE" if reached else "UNVERIFIED"),
                     "Recovery coverage differs from independent interruption records")
            if "recorded_attempts" in stated:
                _require(stated["recorded_attempts"] == len(rows), "Recovery attempt count is inconsistent")
            if "host_pids" in stated:
                _require(stated["host_pids"] == [row["kill"]["identity"]["host_pid"] for row in reached],
                         "Recovery Worker identity is inconsistent")
        _require(coverage.get("status") == ("COMPLETE" if all(points.values()) else "PARTIAL"),
                 "Recovery summary status is inconsistent")
        if verdict == "PASS":
            _require(points["transaction_committed"] > 0 and points["before_response"] > 0,
                     "Required recovery evidence is unverified")
        if episode == "D-V02":
            matrix_name = archive.reference(artifacts.get("request_recovery_matrix"))
            _require(matrix_name == run_prefix + "artifacts/recovery-request-method-phase-matrix.json",
                     "Request recovery matrix belongs to a different Run")
            recorded_matrix = _json(_sealed(archive, files, matrix_name, _MAX_XML))
            import evaluator.dv02_admission as admission
            admission_source = _sealed(source, source_files, prefix + "/evaluator/dv02_admission.py", _MAX_SOURCE)
            admission_archive = _Archive(Path(admission.__file__).absolute().parent)
            try:
                _require(admission_archive.read(Path(admission.__file__).name, _MAX_SOURCE) == admission_source,
                         "Request recovery verifier differs from source pin")
            finally:
                admission_archive.close()
            matrix = admission.recovery_matrix(report, config)
            _require(matrix == recorded_matrix and matrix["status"] == "COMPLETE",
                     "Incomplete or inconsistent request method/phase recovery matrix")
    else:
        _require(fingerprint.get("execution_strategy") == "single-worker" and coverage.get("status") == "NOT_APPLICABLE",
                 "A evaluation topology is inconsistent")
    verifier_path = Path(__file__).absolute()
    verifier_archive = _Archive(verifier_path.parent)
    try:
        verifier_source_sha256 = sha256(verifier_archive.read(verifier_path.name, _MAX_SOURCE)).hexdigest()
        evidence_reader_sha256 = sha256(verifier_archive.read('source_evidence.py', _MAX_SOURCE)).hexdigest()
    finally:
        verifier_archive.close()
    outcome = {
        "id": "orderflow:" + run_id, "schema_version": "1.0.0", "run_id": run_id, "episode_id": episode,
        "verdict": verdict, "submission_digest": candidate_digest, "candidate_tree_sha256": candidate_digest,
        "patch_sha256": patch_digest, "evaluator_fingerprint": fingerprint["evaluator"]["sha256"],
        "evaluator_version": fingerprint["evaluator"]["version"], "test_suite_version": suite["version"],
        "test_suite_fingerprint": suite["sha256"], "verifier_identity": VERIFIER_IDENTITY,
        "verifier_source_sha256": verifier_source_sha256,
        "verifier_dependencies_sha256": {"source_evidence.py": evidence_reader_sha256},
        "source_report_sha256": sha256(report_bytes).hexdigest(), "source_manifest_sha256": anchor.manifest_sha256,
        "junit_sha256": sha256(junit_bytes).hexdigest(), "source_reference": str(archive.root / relative),
        "source_type": "historical_replay" if anchor.profile == "historical_full" else "current_live",
        "verification_profile": anchor.profile, "attribution": "UNKNOWN", "test_count": tests["collected"],
        "test_counts": {key: tests[key] for key in ("passed", "failed", "errors", "skipped")},
        "evaluated_at": report.get("evaluation_ended_at"),
        "private_verification": {"private_manifest_sha256": fingerprint["private_manifest_sha256"],
            "source_snapshot": str(source.root / prefix), "checked_archive_files": dict(archive.files_read),
            "checked_source_files": dict(source.files_read), "oracle_count": len(oracles),
            "inconsistent_oracle_count": sum(not row["consistent"] for row in oracles),
            "topology_record_count": len(topology), "recovery_status": coverage["status"]},
        "assurance": "Maintainer-authorized local byte provenance; no third-party attestation or causal attribution",
    }
    outcome["immutable_digest"] = sha256(canonical_bytes(outcome)).hexdigest()
    return outcome


def verify_outcome(anchor: TrustAnchor, report_reference: str | Path) -> dict:
    """Mint a verified Outcome solely from authorized real archived evidence.

    The returned dictionary is a transport copy of immutable canonical facts.
    Its digest is an identity/conflict check, not authentication. Only trusted
    host code may call the graph's Outcome ingestion API.
    """
    _require(isinstance(anchor, TrustAnchor), "A maintainer TrustAnchor is required")
    archive = source = None
    try:
        archive = _Archive(anchor.archive_root)
        files = _manifest(archive, anchor.manifest_relative_path, anchor.manifest_sha256)
        if anchor.source_archive_root is None:
            source, source_files = archive, files
        else:
            source = _Archive(anchor.source_archive_root)
            source_files = _manifest(source, anchor.source_manifest_relative_path, anchor.source_manifest_sha256)
        return _verify(anchor, archive, source, files, source_files, str(report_reference))
    except OutcomeVerificationError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, SyntaxError, RecursionError, OverflowError) as error:
        raise OutcomeVerificationError("Unable to verify authorized OrderFlow evidence: " + type(error).__name__) from error
    finally:
        if source is not None and source is not archive:
            source.close()
        if archive is not None:
            archive.close()


def public_outcome_summary(outcome: Mapping[str, Any]) -> dict:
    """Allowlisted summary only; never release private paths, tests or source maps."""
    allowed = ("id", "run_id", "episode_id", "verdict", "submission_digest", "evaluator_fingerprint",
               "test_suite_fingerprint", "source_report_sha256", "source_type", "verifier_identity",
               "test_count", "attribution", "immutable_digest", "assurance", "verifier_source_sha256")
    return {key: outcome[key] for key in allowed if key in outcome}


M1_MANIFEST_SHA256 = "a914e4fbacd1c96bc382686e6c38981a5041a7345d16eb9679f62ece29ca94ce"
M1_SEED_RUNS = {
    "rlock_a": "6a312f02-3e28-406a-81f7-86b2636e836f",
    "rlock_d": "c39773d4-33fe-408b-81af-2b3dcd19fa84",
    "atomic_a": "4943e873-6e9d-4905-a281-dfb621b56748",
    "atomic_d": "cf083714-0a91-4392-81ed-1070f2cdef71",
}


def verify_historical_seeds(archive_root: Path) -> dict:
    """Check the four H1-authorized M1 reports against their original seal.

    The seed source mapping is maintainer configuration, not Agent input. The
    natural strategy's original Phase 3 Session is an explicitly separate
    origin reference; these four engineering outcomes are maintainer replays.
    """
    reports = {f"offline-final/runs/{run}/evaluation_report.json": run for run in M1_SEED_RUNS.values()}
    anchor = TrustAnchor(archive_root, M1_MANIFEST_SHA256, reports)
    outcomes = {label: verify_outcome(anchor, f"offline-final/runs/{run}/evaluation_report.json")
                for label, run in M1_SEED_RUNS.items()}
    archive = None
    try:
        archive = _Archive(anchor.archive_root)
        files = _manifest(archive, anchor.manifest_relative_path, anchor.manifest_sha256)
        transfer_bytes = _sealed(archive, files, "offline-final/exact-strategy-transfer.json", _MAX_SOURCE)
        transfers = _json(transfer_bytes)
        producer = _sealed(archive, files, "final_source_snapshot/scripts/m1_offline_regression.py", _MAX_SOURCE)
        for source_key, target_key, transfer_key in (
            ("rlock_a", "rlock_d", "a-local-lock"),
            ("atomic_a", "atomic_d", "a-original-natural-replay"),
        ):
            left, right, stated = outcomes[source_key], outcomes[target_key], transfers[transfer_key]
            _require(left["submission_digest"] == right["submission_digest"] == stated["source_sha256"]
                     == stated["target_sha256"] and stated["source_run_id"] == left["run_id"]
                     and stated["target_run_id"] == right["run_id"]
                     and stated["source_status"] == left["verdict"] and stated["target_status"] == right["verdict"],
                     "Exact historical strategy transfer disagrees with independently checked runs")
        return {"schema_version": "1.0.0", "verification_result": "PASS", "outcomes": outcomes,
            "provenance_observations": {
                "rlock": {"experience_source_type": "maintainer_seed",
                    "source_runs": [M1_SEED_RUNS["rlock_a"], M1_SEED_RUNS["rlock_d"]],
                    "claim": "Exact same source tree: single-process A support and multi-process D counterexample"},
                "atomic": {"experience_source_type": "natural_agent_run",
                    "origin_run_id": "339f7d73-29df-4242-8920-9e566bce8a9c",
                    "origin_patch_sha256": "0525c9650546d438589bd26e7bafd46cd0b1e51b6e469fd67bcb8458138d9f0f",
                    "source_runs": [M1_SEED_RUNS["atomic_a"], M1_SEED_RUNS["atomic_d"]],
                    "claim": "Frozen producer applies the historical Agent patch; A/D support are distinct maintainer replays",
                    "origin_runtime_scope": "Origin reference only here; original native Session proof is a separate historical audit"},
                "producer_sha256": sha256(producer).hexdigest(),
                "transfer_sha256": sha256(transfer_bytes).hexdigest(),
                "assurance": "Current byte cross-check of historically executed tests, not newly executed hidden suites"}}
    finally:
        if archive is not None:
            archive.close()


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Verify authorized Aevora historical OrderFlow seeds, offline")
    parser.add_argument("--historical-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    _require(not args.output.absolute().is_relative_to(args.historical_archive.absolute()),
             "New observations cannot be written into protected historical evidence")
    result = verify_historical_seeds(args.historical_archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as target:
        target.write(canonical_bytes(result) + b"\n")
    print(json.dumps({"result": result["verification_result"], "verified_runs": len(result["outcomes"]),
        "output_sha256": sha256(args.output.read_bytes()).hexdigest(),
        "verdicts": {label: value["verdict"] for label, value in result["outcomes"].items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
