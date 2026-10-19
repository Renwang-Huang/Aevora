"""Manual application-directory compatibility through trusted fidelity checks."""
import os
import shutil

import pytest

from benchmark.manifest import ROOT
from benchmark.runner import BenchmarkRunner
from benchmark.submission import (SubmissionIntegrityError, snapshot_source_tree,
                                  source_tree_sha256)
from evaluator.suites import get_suite


def _source(destination):
    destination.mkdir(parents=True)
    for original in (ROOT / "app").rglob("*.py"):
        relative = original.relative_to(ROOT / "app")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    return destination


@pytest.mark.parametrize("layout", ["workspace", "app", "custom_name", "deep/custom_name"])
def test_manual_application_directory_contract_survives_fidelity_checks(tmp_path, layout):
    if layout == "workspace":
        submission = tmp_path / "workspace"
        application = _source(submission / "app")
    else:
        submission = application = _source(tmp_path / layout)
    expected = snapshot_source_tree(application, app_directory=True)
    report = BenchmarkRunner(tmp_path / "runs").evaluate("SMOKE-001", submission)
    assert report["overall_status"] == "PASS"
    assert report["submission_integrity_status"] == "PASS"
    assert report["submission_integrity"]["expected_tree_sha256"] == source_tree_sha256(expected)
    assert report["submission_integrity"]["applied_candidate_tree_sha256"] == source_tree_sha256(expected)
    assert report["test_results"]["collected"] == len(get_suite("smoke").expected_tests)
    assert report["test_results"]["passed"] == report["test_results"]["collected"]
    assert report["test_results"]["failed"] == report["test_results"]["errors"] == report["test_results"]["skipped"] == 0
    assert "EVALUATE" in report["lifecycle"] and report["environment_reset"] is True


def test_direct_app_snapshot_uses_actual_directory_not_sibling_app(tmp_path):
    source = _source(tmp_path / "custom_name")
    unrelated = _source(tmp_path / "app")
    (unrelated / "service.py").write_text("THIS_SIBLING_MUST_NOT_BE_READ\n")
    expected = {"app/" + p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*.py")}
    assert snapshot_source_tree(source, app_directory=True) == expected


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_direct_app_flag_does_not_bypass_single_link_regular_source_checks(tmp_path, kind):
    source = _source(tmp_path / "custom_name")
    extra = source / "extra.py"
    if kind == "fifo":
        os.mkfifo(extra)
    else:
        external = tmp_path / "outside.py"
        external.write_text("EXTERNAL_CANARY\n")
        if kind == "symlink":
            extra.symlink_to(external)
        else:
            os.link(external, extra)
    with pytest.raises(SubmissionIntegrityError):
        snapshot_source_tree(source, app_directory=True)
