"""M1.1 real socket/process boundaries with synthetic upstreams, never live keys."""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import threading
import time
from uuid import uuid4

import pytest

from benchmark.resources import PARTICIPANT_LIMITS, ResourceLimits, ResourceWatchdog
from integrations.codex_agent import CodexAgentAdapter, CodexConfig, native_command
from integrations.runtime_control import RuntimeControl, cancel_run, status_run
from test_codex_agent import ContractBroker, fixture_config
from test_gateway_broker import _broker, _request, _payload, _response, _sse, _upstream, _wait_records


@contextmanager
def delayed_upstream(*, first_header_delay=0, stream_gaps=(), status_sequence=(), retry_after="1"):
    attempts = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            attempts.append(time.monotonic())
            status = status_sequence[min(len(attempts)-1, len(status_sequence)-1)] if status_sequence else 200
            time.sleep(first_header_delay)
            self.send_response(status)
            if status != 200:
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", retry_after)
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"synthetic fault"}}')
                return
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = [_sse({"type":"response.created", "response": _response(status="in_progress")})]
            frames += [_sse({"type":"response.output_text.delta", "delta":"observed fragment"})] * len(stream_gaps)
            frames += [_sse({"type":"response.completed", "response":_response()})]
            try:
                for index, frame in enumerate(frames):
                    if index and index <= len(stream_gaps):
                        time.sleep(stream_gaps[index-1])
                    self.wfile.write(frame)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(("127.0.0.1",0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval":0.02}, daemon=True)
    thread.start()
    try:
        yield {"url":f"http://127.0.0.1:{server.server_port}/v1", "attempts":attempts}
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def new_broker(upstream, **kwargs):
    return _broker(upstream, completion_policy="completion-aware", request_timeout=None,
                   token_ttl_seconds=None, request_budget=None, **kwargs)


def test_real_first_response_can_exceed_connect_timeout(tmp_path):
    with delayed_upstream(first_header_delay=0.15) as upstream, new_broker(upstream, connect_timeout_seconds=0.03, event_path=tmp_path/"events.jsonl") as broker:
        status, headers, body = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        assert status == 200 and b'response.completed' in body
        record = _wait_records(broker)["request_records"][0]
        assert record["http_first_response_seconds"] >= 0.1
        assert record["outcome"] == "COMPLETED"
    events = [json.loads(line) for line in (tmp_path/"events.jsonl").read_text().splitlines()]
    assert events[-1]["event_type"] == "REQUEST_FINISHED"
    assert broker.metadata["handler_cleanup_complete"]


def test_continuous_slow_sse_is_forwarded_and_gap_observed():
    with delayed_upstream(stream_gaps=(0.07,0.07,0.07)) as upstream, new_broker(upstream) as broker:
        status, _, body = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        record = _wait_records(broker)["request_records"][0]
        assert status == 200 and body.count(b'observed fragment') == 3
        assert record["max_body_gap_seconds"] >= 0.05
        assert record["observed_body_bytes"] == len(body)
        assert not broker.metadata["error_counts"]


def test_true_stream_idle_remains_active_then_explicit_cleanup_interrupts():
    with _upstream(stream=True, controlled=True) as upstream:
        with new_broker(upstream) as broker:
            outcome = []
            client = threading.Thread(target=lambda: outcome.append(_request(broker,method="POST",route="/v1/responses",body=_payload(stream=True))),daemon=True)
            client.start()
            assert upstream["first_sent"].wait(1)
            time.sleep(0.15)
            assert client.is_alive()
            active = broker.activity_snapshot()["active_requests"]
            assert active and active[0]["activity"] == "SSE_STREAMING"
        client.join(2)
        assert not client.is_alive() and broker.metadata["handler_cleanup_complete"]
        assert not broker.socket_path.exists()


@pytest.mark.parametrize("retry_after",["1","0"])
def test_real_429_retry_after_is_preserved_and_recovery_uses_new_request(retry_after):
    with delayed_upstream(status_sequence=(429,200),retry_after=retry_after) as upstream, new_broker(upstream) as broker:
        status, headers, _ = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        assert status == 429 and headers["Retry-After"] == retry_after
        time.sleep(int(headers["Retry-After"]))
        assert _request(broker,method="POST",route="/v1/responses",body=_payload(stream=True))[0] == 200
        assert broker.metadata["upstream_requests"] == 2
        assert broker.metadata["error_counts"]["UPSTREAM_RATE_LIMITED"] == 1


@pytest.mark.parametrize("code",[400,401,403,422])
def test_permanent_4xx_keeps_status_and_broker_never_retries(code):
    with delayed_upstream(status_sequence=(code,)) as upstream, new_broker(upstream) as broker:
        status, _, _ = _request(broker,method="POST",route="/v1/responses",body=_payload(stream=True))
        assert status == code and len(upstream["attempts"]) == 1


def test_unlimited_auth_is_owner_lifetime_and_revoked_on_close():
    with _upstream() as upstream, new_broker(upstream) as broker:
        broker._start_mono -= 100000  # Advance only admission age, not fabricate events.
        assert _request(broker)[0] == 200
        assert broker.metadata["token_lifetime_seconds"] is None
        assert broker.metadata["request_budget"] is None
    assert broker._token is None and not broker.socket_path.exists()


def test_no_wall_watchdog_keeps_idle_child_but_other_limits_unchanged():
    limits = replace(PARTICIPANT_LIMITS,wall_seconds=None)
    process = subprocess.Popen(["/usr/bin/python3.12","-c","import time;time.sleep(.25)"])
    watchdog = ResourceWatchdog(process.pid,limits).start()
    process.wait(2)
    result = watchdog.close()
    assert result["violation"] is None
    assert result["limits"]["cpu_seconds"] == 600
    assert result["limits"]["memory_bytes"] == 2*1024**3


def test_real_adapter_completion_aware_long_work_is_natural_submission(tmp_path,monkeypatch):
    from benchmark.runner import BenchmarkRunner
    from benchmark.participant import build_participant
    from integrations.agents import ExecutionContext,TaskInput
    monkeypatch.setattr("integrations.codex_agent.ModelBroker",ContractBroker)
    config = fixture_config(tmp_path)
    # Actual process boundary: delay represents local work, not a fixed PASS result.
    source = config.binary.read_text().replace("if behavior=='change':","time.sleep(.4)\nif behavior=='change':")
    config.binary.write_text(source)
    config = replace(config,completion_policy="completion-aware",timeout_seconds=None)
    prepared = BenchmarkRunner(tmp_path/"runs").prepare("A")
    archive = Path(prepared["artifacts"]["workspace"]).parent
    participant = build_participant(archive/"workspace",archive/"participant")
    result = CodexAgentAdapter(config).execute(TaskInput("A","1.0.0","Public incident"),ExecutionContext(archive.name,str(participant),constraints={"archive":str(archive),"baseline":str(archive/"workspace")}))
    assert result.status.value == "SUBMITTED" and result.runtime_metadata["elapsed_seconds"] >= .4
    assert result.submission and result.runtime_metadata["timeout_seconds"] is None
    assert status_run(archive)["status"] == "PASS"


def test_operator_cancel_control_is_run_bound_and_partial_snapshot(tmp_path):
    archive = tmp_path/str(uuid4());archive.mkdir()
    control = RuntimeControl(archive,archive.name,completion_policy="completion-aware",agent_mode="multi")
    control.publish()
    snapshot = status_run(archive)
    assert snapshot["evidence_status"] == "PARTIAL_SNAPSHOT"
    assert cancel_run(archive,"explicit test cancellation")["status"] == "CANCEL_REQUESTED"
    assert control.cancellation()["classification"] == "CANCELLED_BY_OPERATOR"
    control.finish("CANCELLED","CANCELLED_BY_OPERATOR")
    with pytest.raises(ValueError): cancel_run(archive)


def test_real_adapter_cancel_stops_running_process_and_keeps_original_result(tmp_path, monkeypatch):
    from benchmark.runner import BenchmarkRunner
    from benchmark.participant import build_participant
    from integrations.agents import ExecutionContext, TaskInput
    monkeypatch.setattr("integrations.codex_agent.ModelBroker", ContractBroker)
    config = replace(fixture_config(tmp_path, "timeout"), completion_policy="completion-aware", timeout_seconds=None)
    prepared = BenchmarkRunner(tmp_path/"runs").prepare("A")
    archive=Path(prepared["artifacts"]["workspace"]).parent
    participant=build_participant(archive/"workspace",archive/"participant")
    def operator():
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if (archive/"runtime_status.json").exists() and (archive/"codex_events.pending").exists():
                cancel_run(archive,"explicit running-process cancellation")
                return
            time.sleep(.01)
        raise AssertionError("No running control appeared")
    thread=threading.Thread(target=operator);thread.start()
    result=CodexAgentAdapter(config).execute(TaskInput("A","1.0.0","Public incident"),ExecutionContext(archive.name,str(participant),constraints={"archive":str(archive),"baseline":str(archive/"workspace")}))
    thread.join(2)
    assert not thread.is_alive()
    assert result.status.value=="CANCELLED" and result.submission is None
    assert result.runtime_metadata["failure_kind"]=="CANCELLED_BY_OPERATOR"
    assert result.runtime_metadata["exit_code"] != 0
    assert status_run(archive)["status"]=="CANCELLED"
    assert (archive/"codex_events.jsonl").exists() and not (archive/"codex_events.pending").exists()


def test_real_collector_interrupt_is_classified_and_adapter_cleanup_finishes(tmp_path):
    binary=fixture_config(tmp_path,"timeout").binary
    archive_parent=tmp_path/"runs"
    trusted_script=tmp_path/"collector_fixture.py"
    trusted_script.write_text('''import sys,json\nfrom pathlib import Path\nfrom benchmark.runner import BenchmarkRunner\nfrom benchmark.participant import build_participant\nfrom integrations.agents import TaskInput,ExecutionContext\nfrom integrations.codex_agent import CodexAgentAdapter,CodexConfig\nimport integrations.codex_agent as module\nclass Broker:\n base_url='http://127.0.0.1:1/v1'\n secret_values=()\n metadata={'transport':'SYNTHETIC_CONTRACT_FIXTURE'}\n def __init__(self,*args,**kwargs):pass\n def __enter__(self):return self\n def __exit__(self,*args):return False\nmodule.ModelBroker=Broker\nr=BenchmarkRunner(Path(sys.argv[2])).prepare('A')\na=Path(r['artifacts']['workspace']).parent\np=build_participant(a/'workspace',a/'participant')\nc=CodexConfig(Path(sys.argv[1]),Path('/unused'),timeout_seconds=None,completion_policy='completion-aware')\nresult=CodexAgentAdapter(c).execute(TaskInput('A','1.0.0','Public synthetic task'),ExecutionContext(a.name,str(p),constraints={'archive':str(a),'baseline':str(a/'workspace')}))\nprint(json.dumps({'status':result.status.value,'failure_kind':result.runtime_metadata['failure_kind']}))\n''')
    environment=dict(os.environ,PYTHONPATH=str(Path.cwd()))
    process=subprocess.Popen([sys.executable,str(trusted_script),str(binary),str(archive_parent)],env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+8
    active=[]
    while time.monotonic()<deadline:
        active=list(archive_parent.glob("*/codex_events.pending"))
        if active:break
        time.sleep(.02)
    assert active,"Collector never entered adapter"
    process.send_signal(signal.SIGTERM)
    stdout,stderr=process.communicate(timeout=10)
    assert process.returncode==0,stderr.decode()
    assert json.loads(stdout)=={"status":"CANCELLED","failure_kind":"COLLECTOR_INTERRUPTED"}
    archive=active[0].parent
    assert status_run(archive)["status"]=="CANCELLED"
    assert not (archive/"codex_events.pending").exists()


def test_wrong_run_cancel_cannot_signal_another_session(tmp_path):
    first=tmp_path/str(uuid4());second=tmp_path/str(uuid4());first.mkdir();second.mkdir()
    a=RuntimeControl(first,first.name,completion_policy="completion-aware",agent_mode="multi")
    b=RuntimeControl(second,second.name,completion_policy="completion-aware",agent_mode="multi")
    cancel_run(first)
    (second/"operator_cancel.json").write_bytes((first/"operator_cancel.json").read_bytes())
    with pytest.raises(ValueError): b.cancellation()
    assert a.cancellation()["run_id"] == first.name
    a.finish("CANCELLED");b.finish("ERROR")


def test_swapped_pair_of_control_and_status_files_cannot_rebind_run(tmp_path):
    first=tmp_path/str(uuid4());second=tmp_path/str(uuid4());first.mkdir();second.mkdir()
    a=RuntimeControl(first,first.name,completion_policy="completion-aware",agent_mode="multi")
    b=RuntimeControl(second,second.name,completion_policy="completion-aware",agent_mode="multi")
    for name in ("runtime_control.json","runtime_status.json"):
        (second/name).write_bytes((first/name).read_bytes())
    with pytest.raises(ValueError): status_run(second)
    with pytest.raises(ValueError): cancel_run(second)
    assert a.cancellation() is None
    a.finish("ERROR");b.finish("ERROR")


@pytest.mark.parametrize("variant",["fifo","root_symlink","parent_symlink","hardlink"])
def test_live_source_unsafe_entries_never_block_or_hash_outside_files(tmp_path, variant):
    archive=tmp_path/str(uuid4());archive.mkdir()
    workspace=tmp_path/"workspace";workspace.mkdir()
    app=workspace/"app";app.mkdir()
    outside=tmp_path/"maintainer-private";outside.mkdir()
    (outside/"private.py").write_text("DO_NOT_READ_THIS_PRIVATE_SOURCE")
    if variant=="fifo":os.mkfifo(app/"evil.py")
    if variant=="root_symlink":app.rmdir();app.symlink_to(outside,target_is_directory=True)
    if variant=="parent_symlink":(app/"linked").symlink_to(outside,target_is_directory=True)
    if variant=="hardlink":os.link(outside/"private.py",app/"evil.py")
    control=RuntimeControl(archive,archive.name,completion_policy="completion-aware",agent_mode="multi")
    started=time.monotonic();control.publish(workspace=workspace)
    assert time.monotonic()-started < .5
    snapshot=status_run(archive)
    assert snapshot["patch_snapshot"]["availability"]=="UNAVAILABLE"
    assert "files_sha256" not in snapshot["patch_snapshot"]
    cancel_run(archive,"verify responsive cancellation")
    assert control.cancellation()["classification"]=="CANCELLED_BY_OPERATOR"
    control.finish("CANCELLED")


def test_runtime_control_rejects_publicly_readable_control_file(tmp_path):
    archive=tmp_path/str(uuid4());archive.mkdir()
    control=RuntimeControl(archive,archive.name,completion_policy="completion-aware",agent_mode="multi")
    (archive/"runtime_control.json").chmod(0o644)
    with pytest.raises(ValueError): status_run(archive)
    with pytest.raises(ValueError): cancel_run(archive)
    control.finish("ERROR")


def test_live_snapshot_refuses_to_hash_known_synthetic_credentials_in_source(tmp_path):
    archive=tmp_path/str(uuid4());archive.mkdir()
    workspace=tmp_path/"workspace";(workspace/"app").mkdir(parents=True)
    marker="synthetic-only-credential-not-a-real-key"
    (workspace/"app"/"leak.py").write_text("x="+repr(marker))
    control=RuntimeControl(archive,archive.name,completion_policy="completion-aware",agent_mode="single")
    control.publish(workspace=workspace,secret_values=(marker,))
    snapshot=status_run(archive)
    assert snapshot["patch_snapshot"]["availability"]=="UNAVAILABLE"
    assert "files_sha256" not in snapshot["patch_snapshot"]
    assert marker not in (archive/"runtime_status.json").read_text()
    control.finish("ERROR")


def test_secure_broker_failure_before_start_preserves_startup_classification(tmp_path, monkeypatch):
    from benchmark.runner import BenchmarkRunner
    from benchmark.participant import build_participant
    from integrations.agents import ExecutionContext, TaskInput
    class StartupFailure:
        metadata={"transport":"SYNTHETIC_HOST_STARTUP_FAILURE", "started_at":None,
                  "upstream_requests":0, "active_requests":0}
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):raise RuntimeError("Synthetic trusted broker startup failure")
        def __exit__(self,*args):return False
    monkeypatch.setattr("integrations.codex_agent.SecureModelBroker",StartupFailure)
    config=fixture_config(tmp_path)
    helper=config.binary.with_name("codex-code-mode-host")
    helper.write_text("#!/usr/bin/python3.12\nraise SystemExit(0)\n");helper.chmod(0o700)
    config=replace(config,provider_id="gateway",model="gpt-5.6-terra",reasoning_effort="max")
    prepared=BenchmarkRunner(tmp_path/"runs").prepare("A")
    archive=Path(prepared["artifacts"]["workspace"]).parent
    participant=build_participant(archive/"workspace",archive/"participant")
    result=CodexAgentAdapter(config).execute(TaskInput("A","1.0.0","Public synthetic task"),ExecutionContext(archive.name,str(participant),constraints={"archive":str(archive),"baseline":str(archive/"workspace")}))
    assert result.status.value=="ERROR" and result.submission is None
    assert result.runtime_metadata["failure_kind"]=="MODEL_BROKER_STARTUP_FAILED"
    assert result.runtime_metadata["model_broker"]["started_at"] is None
    assert result.runtime_metadata["resource_cgroup"]["cleanup_complete"]
    assert status_run(archive)["failure_kind"]=="MODEL_BROKER_STARTUP_FAILED"


@pytest.mark.parametrize("mode",["single","multi"])
def test_native_mode_is_enforced_with_supported_flags(mode):
    config=CodexConfig(Path("/unused/codex"),Path("/unused/key"),completion_policy="completion-aware",timeout_seconds=None,request_budget=None,agent_mode=mode)
    command=native_command(config,"http://127.0.0.1:9180/v1")
    index=command.index("multi_agent")
    assert command[index-1] == ("--disable" if mode=="single" else "--enable")
    assert 'agents.enabled='+str(mode=="multi").lower() in command
    assert "model_providers.orderflow_broker.stream_idle_timeout_ms=600000" in command
    assert not any("request_timeout_ms" in item for item in command)


@pytest.mark.parametrize("value",[0,float("inf"),float("nan")])
def test_wall_does_not_accept_pseudo_unlimited_values(value):
    with pytest.raises(ValueError): ResourceLimits(wall_seconds=value)
    with pytest.raises(ValueError): CodexConfig(Path("/unused"),Path("/unused"),timeout_seconds=value)
