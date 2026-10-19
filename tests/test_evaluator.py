"""The independent oracle must detect defects and infrastructure failures."""

from benchmark.templates import create_template
from evaluator.runner import evaluate


def test_reference_implementation_passes(tmp_path):
    workspace = tmp_path / "reference"
    create_template(workspace, buggy=False)
    result = evaluate(workspace, tmp_path / "reference-evaluation")
    assert result["status"] == "PASS", result
    assert result["pytest_exit_code"] == 0
    assert result["test_results"]["collected"] == 8
    assert result["test_results"]["passed"] == 8
    assert result["test_results"]["failed"] == 0
    assert result["artifacts"]["junit_xml"]


def test_repeated_cancel_defect_fails_reproducibly(tmp_path):
    workspace = tmp_path / "buggy"
    create_template(workspace, buggy=True)
    first = evaluate(workspace, tmp_path / "first")
    second = evaluate(workspace, tmp_path / "second")
    for result in (first, second):
        assert result["status"] == "FAIL", result
        assert result["pytest_exit_code"] == 1
        assert result["test_results"]["failed"] > 0
        assert result["test_results"]["errors"] == 0
    assert first["test_results"]["failed"] == second["test_results"]["failed"]
    assert [(test["nodeid"], test["outcome"]) for test in first["test_results"]["tests"]] == [
        (test["nodeid"], test["outcome"]) for test in second["test_results"]["tests"]
    ]


def test_syntax_error_is_infrastructure_error_not_pass(tmp_path):
    workspace = tmp_path / "syntax-error"
    create_template(workspace, buggy=False)
    (workspace / "app" / "service.py").write_text("def broken(:\n", encoding="utf-8")
    result = evaluate(workspace, tmp_path / "syntax-evaluation")
    assert result["status"] == "ERROR", result
    assert result["pytest_exit_code"] != 0
    assert result["test_results"]["errors"] > 0


def test_hanging_worker_times_out_without_reusing_previous_report(tmp_path):
    workspace = tmp_path / "hanging"
    create_template(workspace, buggy=False)
    (workspace / "app" / "service.py").write_text("while True:\n    pass\n", encoding="utf-8")
    artifacts = tmp_path / "timeout-evaluation"
    artifacts.mkdir()
    (artifacts / "junit.xml").write_text('<testsuite tests="8"/>', encoding="utf-8")
    result = evaluate(workspace, artifacts, timeout_seconds=1)
    assert result["status"] == "TIMEOUT", result
    assert result["pytest_exit_code"] != 0
    assert result["artifacts"]["junit_xml"] is None
    assert result["test_results"]["passed"] == 0


def test_unexpected_hidden_test_count_cannot_pass(tmp_path):
    workspace = tmp_path / "reference"
    create_template(workspace, buggy=False)
    result = evaluate(workspace, tmp_path / "wrong-count", expected_test_count=9)
    assert result["status"] == "ERROR", result
    assert result["pytest_exit_code"] == 0
    assert "Expected 9 tests" in result["errors"][0]
