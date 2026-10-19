"""Collector contracts with real local processes, never live Agent evidence."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
from uuid import uuid4

import pytest

from scripts import m11_calibration as collector


@pytest.mark.parametrize("url", ["http://example.invalid", "https://user:credential@example.invalid", "file:///tmp/gateway"])
def test_tls_admission_rejects_unsafe_endpoints_without_connection(url):
    with pytest.raises(ValueError, match="HTTPS"):
        collector.tls_probe(url)


def test_freeze_checks_current_bytes_and_rejects_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "ROOT", tmp_path)
    source = tmp_path / "source.py"
    source.write_bytes(b"original bytes")
    gate = {"frozen_source_sha256": {"source.py": hashlib.sha256(source.read_bytes()).hexdigest()}}
    collector.verify_freeze(gate)
    source.write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="changed"):
        collector.verify_freeze(gate)
    target = tmp_path / "target"
    source.rename(target)
    source.symlink_to(target)
    with pytest.raises(ValueError, match="Unsafe"):
        collector.verify_freeze(gate)


def test_collector_waits_for_real_work_completion_without_total_deadline(tmp_path, monkeypatch):
    run_id = str(uuid4())
    runs = tmp_path / "runs"
    release = tmp_path / "release"
    observations = []
    def status(archive):
        observations.append(archive.name)
        if len(observations) == 8:
            release.write_text("trusted fixture permits work to finish")
        return {"run_id": archive.name, "status": "RUNNING", "evidence_status": "PARTIAL_SNAPSHOT",
                "source": "SYNTHETIC_COLLECTOR_CONTRACT_NOT_CODEX"}
    monkeypatch.setattr("integrations.runtime_control.status_run", status)
    code = f"""import pathlib,json,time,hashlib
run=pathlib.Path({str(runs / run_id)!r}); run.mkdir(parents=True)
release=pathlib.Path({str(release)!r})
work=hashlib.sha256(b'actual local computation').hexdigest()
while not release.exists():
 work=hashlib.sha256(work.encode()).hexdigest()
 time.sleep(.005)
(run/'local-work.json').write_text(json.dumps({{'sha256':work,'source':'NOT_CODEX'}}))
(run/'evaluation_report.json').write_text(json.dumps({{'run_id':{run_id!r},'overall_status':'ERROR','evaluation_status':'NOT_RUN','source':'SYNTHETIC_COLLECTOR_CONTRACT_NOT_CODEX'}}))
"""
    receipt, report = collector.collect_trial(tmp_path / "command", [sys.executable, "-c", code], runs, snapshot_interval=.01)
    assert receipt["exit_code"] == 0
    assert receipt["collector_timeout"] is False
    assert receipt["collector_total_deadline_seconds"] is None
    assert receipt["elapsed_seconds"] > 1
    assert len(observations) >= 8
    assert receipt["run_id"] == report["run_id"] == run_id
    assert report["evaluation_status"] == "NOT_RUN"
    assert (runs / run_id / "local-work.json").is_file()


def test_collector_interrupt_propagates_and_preserves_original_attempt(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    run_id = str(uuid4())
    run = runs / run_id
    monkeypatch.setattr("integrations.runtime_control.status_run", lambda archive: {"run_id": archive.name, "status": "RUNNING"})
    code = f"""import pathlib,json,signal,time
run=pathlib.Path({str(run)!r});run.mkdir(parents=True)
def cancel(signum,frame):
 (run/'evaluation_report.json').write_text(json.dumps({{'run_id':{run_id!r},'overall_status':'CANCELLED','failure_kind':'COLLECTOR_INTERRUPTED','evaluation_status':'NOT_RUN','source':'SYNTHETIC_COLLECTOR_CONTRACT_NOT_CODEX'}}))
 raise SystemExit(5)
signal.signal(signal.SIGTERM,cancel)
(run/'ready').write_text('signal handler active')
while True:time.sleep(.01)
"""
    def interrupt():
        deadline = time.monotonic() + 10
        while not (run / "ready").exists() and time.monotonic() < deadline:
            time.sleep(.01)
        if (run / "ready").exists():
            os.kill(os.getpid(), signal.SIGTERM)
    thread = threading.Thread(target=interrupt)
    previous = signal.getsignal(signal.SIGTERM)
    thread.start()
    receipt, report = collector.collect_trial(tmp_path / "command", [sys.executable, "-c", code], runs, snapshot_interval=.01)
    thread.join(10)
    assert receipt["exit_code"] == 5
    assert receipt["collector_timeout"] is False
    assert receipt["collector_interruption"]["signal"] == signal.SIGTERM
    assert report["overall_status"] == "CANCELLED"
    assert report["failure_kind"] == "COLLECTOR_INTERRUPTED"
    assert report["evaluation_status"] == "NOT_RUN"
    assert signal.getsignal(signal.SIGTERM) == previous


def test_collector_abnormal_exit_is_not_success(tmp_path):
    receipt, report = collector.collect_trial(tmp_path / "command", [sys.executable, "-c", "raise SystemExit(17)"], tmp_path / "runs")
    assert receipt["exit_code"] == 17
    assert receipt["run_id"] is None
    assert receipt["status"] == "ERROR"
    assert report == {}
    assert receipt["collector_timeout"] is False
