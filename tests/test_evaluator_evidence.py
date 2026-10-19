"""Evidence from previous invocations and incomplete XML cannot imply success."""
import pytest

from benchmark.templates import create_template
from evaluator.runner import evaluate, read_junit


def test_timeout_does_not_reuse_previous_concurrency_or_database_evidence(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    artifacts = tmp_path / "output"
    artifacts.mkdir()
    for name in ("concurrency-previous.json", "oracle-previous.json"):
        (artifacts / name).write_text('{"previous":true}')
    (artifacts / "worker-previous.stderr.log").write_text("previous worker")
    (workspace / "app/service.py").write_text("while True:\n    pass\n")
    result = evaluate(workspace, artifacts, timeout_seconds=1)
    assert result["status"] == "TIMEOUT"
    assert result["concurrency_evidence"] == []
    assert result["database_oracle"] == []
    assert not (artifacts / "worker-previous.stderr.log").exists()


@pytest.mark.parametrize("xml", [
    '<testsuite tests="2"><testcase name="one"/></testsuite>',
    '<testsuite tests="1" failures="0"><testcase name="one"><failure/></testcase></testsuite>',
    '<testsuite tests="1"><testcase name="one"><failure/><skipped/></testcase></testsuite>',
    '<testsuite tests="1"><testcase name="one" time="nan"/></testsuite>',
])
def test_invalid_junit_counts_and_outcomes_are_rejected(tmp_path, xml):
    report = tmp_path / "junit.xml"
    report.write_text(xml)
    with pytest.raises(ValueError):
        read_junit(report)
