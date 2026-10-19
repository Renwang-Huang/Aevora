from evaluator.recovery_coverage import recovery_coverage, missing_required_recovery


def test_unreached_window_is_unverified_not_verified_recovery():
    report = recovery_coverage([{"label": "commit", "availability": "UNAVAILABLE"}], required_points=("commit",))
    assert report["status"] == "PARTIAL"
    assert report["points"]["commit"]["availability"] == "UNVERIFIED"


def test_event_without_verified_death_is_not_an_interruption():
    report = recovery_coverage([{"label": "commit", "availability": "AVAILABLE",
                               "kill": {"signal": "SIGKILL", "worker_pidfd_exited": False}}], required_points=("commit",))
    assert report["status"] == "PARTIAL"


def test_complete_and_nonapplicable_coverage():
    rows = [{"label": label, "availability": "AVAILABLE", "kill": {
        "signal": "SIGKILL", "worker_pidfd_exited": True, "identity": {"host_pid": index + 100}}}
        for index, label in enumerate(("commit", "response"))]
    assert recovery_coverage(rows, required_points=("commit", "response"))["status"] == "COMPLETE"
    assert recovery_coverage([])["status"] == "NOT_APPLICABLE"


def test_unsupported_commit_path_cannot_silently_qualify_for_pass():
    coverage = recovery_coverage([], required_points=("transaction_committed", "before_response"))
    assert missing_required_recovery(coverage) == ["transaction_committed", "before_response"]
    assert missing_required_recovery(recovery_coverage([])) == []


def test_real_unbound_native_commit_is_evaluator_error_not_false_business_failure(tmp_path):
    from benchmark.episodes.episode_d import build_episode_d_fixture
    from benchmark.runner import BenchmarkRunner
    workspace = build_episode_d_fixture(tmp_path / "native-api", strategy="reference")
    path = workspace / "app/persistence.py"
    path.write_text(path.read_text().replace("connection.commit()", "sqlite3.Connection.commit(connection)")
                    .replace("connection.close()", "sqlite3.Connection.close(connection)"))
    report = BenchmarkRunner(tmp_path / "runs").evaluate("D", submission=workspace)
    assert report["test_results"]["collected"] == 28
    assert report["test_results"]["passed"] == 28
    assert report["test_results"]["errors"] == report["test_results"]["failed"] == 0
    assert all(row["consistent"] for row in report["database_oracle"])
    assert report["recovery_coverage"]["points"]["transaction_committed"]["availability"] == "UNVERIFIED"
    assert report["overall_status"] == "ERROR"
    assert any("RECOVERY_EVIDENCE_UNVERIFIED" in error for error in report["execution_errors"])
