#!/usr/bin/env python3
"""Real official isolated CLI, exclusively synthetic loopback model responses.

This is transport/configuration evidence, never a blind benchmark challenge.
No real model endpoint, host authentication file, or upstream key is mounted.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts import phase35_codex_retry_probe as established


class Upstream:
    def __init__(self,scenario):
        self.scenario=scenario;self.records=[];self.attempts=0;self.lock=threading.Lock()
        self.release=threading.Event();self.received=threading.Event()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version="HTTP/1.0"
            def log_message(self,*args):pass
            def do_GET(self):
                with owner.lock:owner.records.append({"method":"GET","status":200,"at":time.time()})
                data=b'{"models":[]}'
                self.send_response(200);self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert body["model"]==established.MODEL and body["reasoning"]["effort"]=="max" and body["stream"] is True
                with owner.lock:
                    owner.attempts+=1;attempt=owner.attempts
                    owner.records.append({"method":"POST","attempt":attempt,"at":time.time(),"scenario":scenario})
                owner.received.set()
                if scenario=="cancel":
                    owner.release.wait(180)
                if scenario=="delayed-header":time.sleep(.5)
                if scenario=="permanent-auth" or (scenario=="rate-limit" and attempt==1):
                    code=401 if scenario=="permanent-auth" else 429
                    self.send_response(code);self.send_header("Content-Type","application/json")
                    if code==429:self.send_header("Retry-After","1")
                    self.end_headers()
                    try:self.wfile.write(b'{"error":{"type":"synthetic_fault","message":"public local fixture"}}')
                    except OSError:pass
                    return
                self.send_response(200);self.send_header("Content-Type","text/event-stream");self.end_headers()
                try:
                    if scenario in ("disconnect","idle-retry") and attempt==1:
                        self.wfile.write(established.sse({"type":"response.created","response":established.public_response(attempt,completed=False)}));self.wfile.flush()
                        if scenario=="idle-retry":time.sleep(1.5)
                        return
                    frames=established.successful_events(attempt).split(b"\n\n")
                    for frame in frames:
                        if frame:
                            if scenario=="slow-sse":time.sleep(.4)
                            self.wfile.write(frame+b"\n\n");self.wfile.flush()
                except OSError:pass
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler);self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":.02},daemon=True)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*args):
        self.release.set();self.server.shutdown();self.server.server_close();self.thread.join(2)


def probe(args):
    from benchmark.participant_sandbox import participant_command
    from benchmark.resources import CgroupScope,PARTICIPANT_LIMITS,ResourceWatchdog
    from integrations.codex_agent import CodexConfig,native_command
    from integrations.codex_trace import redact_text
    from integrations.gateway_broker import SecureModelBroker
    from integrations.providers import ProviderConfig
    archive=args.archive.resolve();archive.mkdir(parents=True,exist_ok=False)
    limits=replace(PARTICIPANT_LIMITS,wall_seconds=None)
    binary=Path("/tools/codex");helper=binary.with_name("codex-code-mode-host")
    started=time.monotonic();process=None;watchdog=None
    with tempfile.TemporaryDirectory(prefix="ofm11-") as temporary,Upstream(args.scenario) as upstream:
        root=Path(temporary);workspace=root/"workspace";state=root/"state";workspace.mkdir();state.mkdir(mode=0o700)
        (workspace/"AGENTS.md").write_text("Public synthetic transport probe. Single Agent; no tools or child agents are needed.\n")
        subprocess.run(["/tools/git","init","-q",str(workspace)],check=True)
        key=root/"synthetic.key";key.write_text("synthetic-only-not-a-live-upstream-credential");key.chmod(0o600)
        token=secrets.token_urlsafe(32)
        config=CodexConfig(binary,key,model=established.MODEL,provider_id="gateway",reasoning_effort="max",
                           timeout_seconds=None,completion_policy="completion-aware",request_budget=None,
                           agent_mode="single",connect_timeout_seconds=.1,
                           stream_idle_timeout_ms=1000 if args.scenario=="idle-retry" else 600000)
        broker=SecureModelBroker(ProviderConfig(),key,run_id="synthetic-m11-"+args.scenario,
                 socket_path=root/"broker.sock",run_token=token,request_budget=None,request_timeout=None,
                 token_ttl_seconds=None,completion_policy="completion-aware",connect_timeout_seconds=.1,
                 event_path=archive/"gateway_transport_events.jsonl",
                 test_upstream_base_url=f"http://127.0.0.1:{upstream.server.server_port}/v1")
        scope=CgroupScope.create(limits)
        try:
            with broker:
                native=native_command(config,"http://127.0.0.1:9180/v1")
                assert "--strict-config" in native
                inner=["/usr/bin/python3.12","-I","-B","/model_bridge.py","--",*native]
                command=scope.wrap_command(participant_command(workspace,state,binary,inner,broker_socket=broker.socket_path,
                    network_isolated=True,code_mode_host_binary=helper,resources=limits))
                (archive/"command.json").write_text(json.dumps({"argv":command,"native_config":native,
                    "source":"real official Codex CLI; synthetic loopback Responses only","real_gateway_requests":0,
                    "binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "helper_sha256":hashlib.sha256(helper.read_bytes()).hexdigest(),
                    "synthetic_fixture_safety_timeout_seconds":180},indent=2)+"\n")
                payload=json.dumps({"run_token":token,"completion_policy":"completion-aware"}).encode()+b"\nReturn only the public synthetic final text.\n"
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
                watchdog=ResourceWatchdog(process.pid,limits,output_roots=(workspace,state,archive)).start()
                if args.scenario=="cancel":
                    def stop():
                        if upstream.received.wait(30):os.killpg(process.pid,signal.SIGTERM)
                    canceller=threading.Thread(target=stop);canceller.start()
                try:
                    stdout,stderr=process.communicate(payload,timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=10)
                    raise RuntimeError("Synthetic fixture itself failed its explicit safety deadline")
                finally:
                    if args.scenario=="cancel":canceller.join(2)
                scrub=(*broker.secret_values,token)
                (archive/"codex_events.jsonl").write_text(redact_text(stdout.decode(errors="replace"),secret_values=scrub))
                (archive/"codex_stderr.log").write_text(redact_text(stderr.decode(errors="replace"),secret_values=scrub))
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.wait(10)
            observation=watchdog.close(cleanup=True) if watchdog else None
            cgroup=scope.close()
        events=[json.loads(line) for line in (archive/"codex_events.jsonl").read_text().splitlines()]
        result={"source":"real official CLI; fake local Responses; NOT a benchmark challenge","scenario":args.scenario,
                "real_gateway_requests":0,"cli_exit_code":process.returncode,"elapsed_seconds":time.monotonic()-started,
                "turn_completed":any(e.get("type")=="turn.completed" for e in events),
                "turn_failed":any(e.get("type")=="turn.failed" for e in events),
                "child_tool_observed":any(e.get("item",{}).get("type")=="collab_tool_call" for e in events),
                "broker":broker.metadata,"upstream_records":upstream.records,"response_attempts":upstream.attempts,
                "resource_watchdog":observation,"resource_cgroup":cgroup,
                "broker_socket_removed":not broker.socket_path.exists()}
        (archive/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        assert observation["violation"] is None and not observation["remaining_pids"] and cgroup["cleanup_complete"]
        assert result["broker_socket_removed"] and result["broker"]["handler_cleanup_complete"]
        assert not result["child_tool_observed"]
        if args.scenario in ("permanent-auth","cancel"):
            assert process.returncode!=0 and not result["turn_completed"]
            # Installed exec's stream recovery retries also wrap a permanent
            # HTTP 401. Preserve this actual finite behavior (two reconnects),
            # rather than inventing a no-retry capability the CLI lacks.
            assert upstream.attempts==(3 if args.scenario=="permanent-auth" else 1)
        else:
            assert process.returncode==0 and result["turn_completed"]
            assert upstream.attempts==(2 if args.scenario in ("rate-limit","disconnect","idle-retry") else 1)
        if args.scenario=="delayed-header":
            assert max(item.get("http_first_response_seconds",0) for item in result["broker"]["request_records"])>=.4
        print(json.dumps({"result":"PASS",**{k:result[k] for k in ("scenario","cli_exit_code","turn_completed","response_attempts","elapsed_seconds")}}))
        return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--scenario",required=True,choices=("delayed-header","slow-sse","rate-limit","disconnect","permanent-auth","idle-retry","cancel"))
    parser.add_argument("--inside-runtime",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.inside_runtime:
        # Reuse the proven secret-free maintainer bootstrap, substituting only
        # this script entry. No existing file is edited or authentication read.
        established.__file__=str(Path(__file__).resolve())
        return established.bootstrap(sys.argv[1:])
    return probe(args)


if __name__=="__main__":raise SystemExit(main())
