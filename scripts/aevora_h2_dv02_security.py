#!/usr/bin/env python3
"""D-V02 pre-model security probes over existing actual boundaries.

No Codex Agent or model challenge is launched. Official CLI sandbox is a command
boundary probe. Real credentials are only existence-checked; read attempts open
and immediately close a descriptor without ever reading contents. Gateway uses
a temporary synthetic key and owned upstream. Every archive must be new.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib,json,os
from pathlib import Path
import secrets,shutil,socket,subprocess,sys,tempfile,threading,time

from scripts.aevora_h2_security import (
    Evidence,broker_case,mcp_probes,now,require_h2_graph,runtime_contracts,sha,write,
)

ROOT=Path(__file__).resolve().parents[1]
VERSION="aevora.h2-dv02-security/1.0"
SOURCES=("scripts/aevora_h2_dv02_security.py","scripts/aevora_h2_security.py",
    "benchmark/participant_sandbox.py","benchmark/sandbox.py","benchmark/participant.py",
    "integrations/gateway_broker.py","integrations/aevora.py",
    "evaluator/dv02_clock.py","evaluator/dv02_worker.py","evaluator/dv02_supervisor.py",
    "benchmark/h2_cli.py","benchmark/scenarios/D-V02/public.json")


def source_epoch():
    import aevora
    files={name:sha(ROOT/name) for name in SOURCES}
    files.update({"aevora/"+p.name:sha(p) for p in sorted(Path(aevora.__file__).parent.glob("*.py"))})
    return files


class DV02Evidence(Evidence):
    def __init__(self,output):
        super().__init__(output)
        self.sources_before=source_epoch()
        write(self.output/"SOURCE_BEFORE.json",{"files":self.sources_before})

    def finish(self,mode,error=None):
        import sqlite3
        after=source_epoch()
        write(self.output/"SOURCE_AFTER.json",{"files":after,"identical_to_before":after==self.sources_before})
        self.check("source_unchanged",after==self.sources_before,{"identical":after==self.sources_before},
                   scope="Actual source SHA256 epoch")
        status="PASS" if self.checks and all(row["status"]=="PASS" for row in self.checks) and error is None else "FAIL"
        result={"version":VERSION,"mode":mode,"status":status,"mandatory_boundary_result":status,
            "overall_security":"PARTIAL","model_calls":0,"official_codex_session":"NOT_STARTED",
            "native_subagent_evidence":"NOT_COLLECTED","provider_compatibility":"UNVERIFIED_SYNTHETIC_ONLY",
            "checks":self.checks,"error":error,"recorded_at":now(),
            "runtime":{"python":sys.version,"sqlite":sqlite3.sqlite_version},"source_sha256":self.sources_before,
            "limitations":["Shared Linux kernel; no VM/hostile-kernel attestation",
                "Official CLI sandbox command probe is not a multi-Agent challenge",
                "Scoped capability identifies a run, not an individual Agent",
                "Synthetic Gateway transport is not model/reasoning compatibility",
                "Protocol text-as-data is not model prompt-injection immunity"]}
        write(self.output/"summary.json",result)
        print(json.dumps({"status":status,"checks":len(self.checks),"overall_security":"PARTIAL","model_calls":0}))
        return 0 if status=="PASS" else 1


@contextmanager
def synthetic_upstream(output,key):
    rows=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
            authorized=self.headers.get("Authorization")=="Bearer "+key
            row={"source":"EXPLICIT_SYNTHETIC_HTTP","path":self.path,"body":body,
                 "synthetic_host_auth_verified":authorized,"observed_at":now()}
            rows.append(row)
            with (output/"synthetic_upstream.jsonl").open("a") as target:target.write(json.dumps(row)+"\n")
            response={"id":"resp_dv02_synthetic","object":"response","status":"completed",
                "model":"gpt-5.6-terra","reasoning":{"effort":"max"},
                "output":[{"type":"message","role":"assistant","content":[{"type":"output_text",
                    "text":"SYNTHETIC TRANSPORT; NOT MODEL INFERENCE"}]}]}
            data=json.dumps(response).encode()
            self.send_response(200 if authorized else 401)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,name="dv02-synthetic-upstream",daemon=True);thread.start()
    try:yield f"http://127.0.0.1:{server.server_port}/v1",rows
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        write(output/"synthetic_upstream_cleanup.json",{"thread_stopped":not thread.is_alive(),"requests":len(rows)})


BOUNDARY_CODE=r'''import os,json,socket,pathlib,sys,secrets,http.client
paths=PATHS
observed={}
for label,path in paths.items():
 try:
  if pathlib.Path(path).is_dir():os.listdir(path)
  else:
   fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK);os.close(fd)
  observed[label]={'readable':True}
 except OSError as error:observed[label]={'readable':False,'errno':error.errno}
public_source=pathlib.Path('/workspace/app/requests.py').is_file()
public=json.loads(pathlib.Path('/workspace/public.json').read_text())
assert public['id']=='D-V02' and public_source
connection=None
try:
 connection=socket.socket();connection.settimeout(1);connection.connect(('127.0.0.1',PORT));network_denied=False
except OSError:network_denied=True
finally:
 if connection is not None:connection.close()
protocol=[];catalog=[];mcp_authorized=False;model_authorized=False;denied_channels={}
if MODE=='outer':
 authority=json.loads(sys.stdin.buffer.readline(8192))
 channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);channel.settimeout(12);channel.connect('/aevora-channel/mcp.sock')
 channel.sendall(json.dumps({'protocol':'aevora-mcp-uds-v1','run_id':authority['run_id'],'token':authority['mcp_token'],'nonce':secrets.token_hex(32)}).encode()+b'\n')
 reader=channel.makefile('rb');assert json.loads(reader.readline())=={'aevora_transport':'READY'}
 def call(value):
  channel.sendall(json.dumps(value).encode()+b'\n');response=json.loads(reader.readline());protocol.append({'request':value,'response':response});return response
 init=call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'D-V02 physical boundary only','version':'1.0'}}})
 assert init['result']['serverInfo']['name']=='Aevora'
 channel.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
 listed=call({'jsonrpc':'2.0','id':2,'method':'tools/list'})
 catalog=sorted(entry['name'] for entry in listed['result']['tools'])
 assert catalog==['build_evidence_bundle','record_decision','resolve_experience']
 query=call({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'resolve_experience','arguments':{'task_context':{}}}})
 assert not query['result'].get('isError'),query
 assert query['result']['structuredContent']['run_id']==authority['run_id']
 mcp_authorized=True;reader.close();channel.close()
 class UnixHTTP(http.client.HTTPConnection):
  def connect(self):
   self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(12);self.sock.connect('/model-channel/broker.sock')
 model=UnixHTTP('model-channel',timeout=12)
 model.request('POST','/v1/responses',body=json.dumps({'model':'gpt-5.6-terra','reasoning':{'effort':'max'},'input':'SYNTHETIC D-V02 BOUNDARY CHECK; NOT INFERENCE'}),headers={'Authorization':'Bearer '+authority['model_token'],'Content-Type':'application/json'})
 response=model.getresponse();body=json.loads(response.read());status=response.status;model.close()
 protocol.append({'source':'SYNTHETIC_HTTP','status':status,'response':body})
 assert status==200 and body['status']=='completed'
 model_authorized=True
else:
 for label,path in [('mcp','/aevora-channel/mcp.sock'),('model','/model-channel/broker.sock')]:
  channel=None
  try:
   channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);channel.settimeout(1);channel.connect(path);denied_channels[label]=False
  except OSError:denied_channels[label]=True
  finally:
   if channel is not None:channel.close()
result={'layer':MODE,'public_source':public_source,'public_episode':public['id'],'denied_targets':observed,
 'owned_loopback_denied':network_denied,'mcp_authorized':mcp_authorized,'model_transport_authorized':model_authorized,
 'denied_channels':denied_channels,'catalog':catalog,'protocol':protocol,'model_calls':0,'credential_contents_read':False}
print(json.dumps(result))
assert network_denied and all(not row['readable'] for row in observed.values())
assert mcp_authorized and model_authorized if MODE=='outer' else all(denied_channels.values())
'''


def denied_targets(evidence,archive):
    targets={"new_hidden_tests":ROOT/"evaluator/hidden_tests/episode_d_v02",
        "new_reference":ROOT/"evaluator/reference_patches/D-V02-reference.diff",
        "new_private_manifest":ROOT/"evaluator/private_manifests/D-V02.json",
        "new_oracle":ROOT/"evaluator/episode_d_v02_oracle.py",
        "old_hidden_tests":ROOT/"evaluator/hidden_tests/episode_d",
        "old_reference":ROOT/"evaluator/reference_patches/D-v01.diff",
        "old_private_labels":ROOT/"evaluator/private_labels/episode_d_applicability.json",
        "maintainer_source":ROOT/"app/service.py","maintainer_guide":ROOT/"AGENTS.md",
        "governance_source":ROOT/"aevora_core/src/aevora",
        "g1_raw_cypher":archive/"g1/full_project_v2/trusted_cypher_results.jsonl",
        "trusted_db_credential":Path("/maintainer/aevora-db.password"),
        "trusted_gateway_credential":Path("/maintainer/gateway.key"),
        "other_run":evidence.output/"other-run-private-result.json"}
    write(targets["other_run"],{"source_type":"EXPLICIT_SECURITY_TEST_FIXTURE","not_a_benchmark_outcome":True})
    missing=[key for key,path in targets.items() if not path.exists()]
    if missing:raise ValueError("Denied target absent in trusted host: "+",".join(missing))
    write(evidence.output/"target_existence.json",{key:{"path":str(path),"exists_before":True,
        "kind":"directory" if path.is_dir() else "file","credential_contents_read":False} for key,path in targets.items()})
    paths={key:str(path) for key,path in targets.items()}
    paths.update(host_home=str(Path.home()),host_codex_identity=str(Path.home()/".codex/auth.json"),
        original_gateway_credential=os.environ.get("ORDERFLOW_GATEWAY_SECRET_PATH",str(Path.home()/".config/orderflow/gateway_api_key")),
        original_db_credential=os.environ.get("AEVORA_FALKORDB_PASSWORD_FILE",str(Path.home()/".config/aevora/falkordb.password")))
    paths.update({"proc_root_"+key:"/proc/1/root"+value for key,value in list(paths.items())})
    paths["workspace_traversal"]="/workspace/../../"+str(ROOT/"app/service.py").lstrip("/")
    return paths


def boundary(evidence,archive):
    from benchmark.h2_cli import register_h2
    from benchmark.runner import BenchmarkRunner
    from benchmark.participant import build_participant
    from benchmark.participant_sandbox import participant_command
    from benchmark.sandbox import sandbox_command,runtime_python
    from integrations.aevora import public_runtime_context
    from integrations.gateway_broker import SecureModelBroker
    from integrations.providers import ProviderConfig
    import aevora.mcp_proxy
    register_h2()
    prepared=BenchmarkRunner(evidence.output/"runs").prepare("D-V02")
    run=evidence.output/"runs"/prepared["run_id"]
    participant=build_participant(run/"workspace",run/"participant")
    manifest=json.loads((participant/"public.json").read_text())
    paths=denied_targets(evidence,archive)
    listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen(8);listener.settimeout(.1)
    accepted=[];stop=threading.Event()
    def accept():
        while not stop.is_set():
            try:connection,_=listener.accept();accepted.append(True);connection.close()
            except socket.timeout:pass
            except OSError:break
    thread=threading.Thread(target=accept,name="dv02-denied-listener",daemon=True);thread.start()
    model_token=secrets.token_urlsafe(32)
    synthetic_key="SYNTHETIC_UPSTREAM_NOT_REAL_"+secrets.token_hex(16)
    try:
        with tempfile.TemporaryDirectory(prefix="dv02-gateway-") as temporary:
            secret=Path(temporary)/"fake-key";secret.write_text(synthetic_key);secret.chmod(0o600)
            with synthetic_upstream(evidence.output,synthetic_key) as (upstream,rows):
                with SecureModelBroker(ProviderConfig(base_url="https://api.renwang-huang.top/v1"),secret,
                    run_id=prepared["run_id"],socket_path=Path(temporary)/"model.sock",run_token=model_token,
                    test_upstream_base_url=upstream,max_concurrency=2,request_budget=8,request_timeout=12,
                    event_path=evidence.output/"synthetic_gateway_events.jsonl") as gateway:
                    with broker_case(evidence,"dv02_physical_mcp",context=public_runtime_context(manifest)) as (broker,token,directory):
                        paths.update(unmounted_mcp_socket=str(broker.socket_path),unmounted_mcp_parent=str(broker.socket_path.parent),
                            unmounted_model_socket=str(gateway.socket_path),unmounted_model_parent=str(gateway.socket_path.parent))
                        for label in ("outer","native","candidate"):
                            code=BOUNDARY_CODE.replace("PATHS",repr(paths)).replace("PORT",str(listener.getsockname()[1])).replace("MODE",repr(label))
                            command=[runtime_python(),"-I","-c",code]
                            state=run/("state-"+label);state.mkdir(mode=0o700)
                            if label=="candidate":argv=sandbox_command(participant,command)
                            else:
                                if label=="native":command=["/opt/codex/codex","sandbox","-c",'sandbox_mode="workspace-write"',
                                    "-c",'approval_policy="never"',"--",*command]
                                argv=participant_command(participant,state,Path(os.environ["ORDERFLOW_CODEX_BINARY"]),command,
                                    network_isolated=True,broker_socket=gateway.socket_path,aevora_socket=broker.socket_path,
                                    aevora_proxy=Path(aevora.mcp_proxy.__file__))
                            header=json.dumps({"run_id":broker.run_id,"mcp_token":token,"model_token":model_token}).encode()+b"\n" if label=="outer" else b""
                            started,clock=now(),time.monotonic()
                            result=subprocess.run(argv,input=header,capture_output=True,timeout=90)
                            for kind,data in (("stdout",result.stdout),("stderr",result.stderr)):
                                (evidence.output/f"{label}.{kind}.log").write_bytes(data)
                            write(evidence.output/(label+".command.json"),{"argv":argv,"exit_code":result.returncode,
                                "started_at":started,"ended_at":now(),"elapsed_seconds":time.monotonic()-clock,
                                "capability_input":"SCOPED_STDIN_VALUES_NOT_ARCHIVED",
                                "stdout_sha256":sha(evidence.output/(label+".stdout.log")),"stderr_sha256":sha(evidence.output/(label+".stderr.log"))})
                            observations=json.loads(result.stdout) if result.stdout else {}
                            authorized=(observations.get("mcp_authorized") and observations.get("model_transport_authorized")) if label=="outer" else observations.get("denied_channels")=={"mcp":True,"model":True}
                            evidence.check(label+"_dv02_boundary",result.returncode==0 and observations.get("public_episode")=="D-V02"
                                and observations.get("public_source") is True and observations.get("owned_loopback_denied") is True
                                and authorized and bool(observations.get("denied_targets"))
                                and all(not item["readable"] for item in observations.get("denied_targets",{}).values()),
                                {"exit_code":result.returncode,"observations":observations},
                                scope="Unchanged actual namespace/native/business boundary; synthetic transport only")
                metadata=gateway.metadata;write(evidence.output/"synthetic_gateway_metadata.json",metadata)
                evidence.check("synthetic_gateway_cleanup",metadata.get("active_requests")==0
                    and metadata.get("handler_cleanup_complete") is True and metadata.get("server_thread_stopped") is True
                    and not gateway.socket_path.exists(),metadata,scope="Actual handler/socket shutdown")
                evidence.check("synthetic_gateway_authorized_once",len(rows)==1 and rows[0]["synthetic_host_auth_verified"],rows,
                    scope="Actual owned synthetic HTTP; no model inference credit")
        evidence.check("no_archived_test_tokens",all(value not in p.read_text(errors="replace")
            for p in evidence.output.glob("*.log") for value in (model_token,synthetic_key)),
            {"known_test_values_absent":True},scope="Known synthetic credentials/capabilities only")
        evidence.check("owned_listener_not_reached",not accepted,{"accepted":len(accepted)},scope="Owned denied listener; no service scan")
    finally:
        stop.set();listener.close();thread.join(timeout=3)
        evidence.check("owned_listener_cleanup",not thread.is_alive(),{"thread_stopped":not thread.is_alive()},scope="Actual owned listener shutdown")

CLOCK_PAYLOADS=[b"ADVANCE 999\n",b"SET 0\n",b"READ /maintainer/aevora-db.password\n",
    b"SQL MATCH(n) DETACH DELETE n\n",b'{"command":"advance","tick":"999999"}\n',
    b"now\n",b"NOW\r\n",b"NOW extra\n",b"X"*100+b"\n"]

CLOCK_CODE=r'''
# EXPLICIT SECURITY CONTROL; not a Benchmark repair or Agent submission.
import json as _pjson,os as _pos,socket as _psocket
_security_original_now=now
def now():
    rows=[]
    for payload in PAYLOADS:
        channel=_psocket.socket(_psocket.AF_UNIX,_psocket.SOCK_STREAM);channel.settimeout(3)
        try:
            channel.connect(_pos.environ['ORDERFLOW_CLOCK_QUERY']);channel.sendall(payload)
            raw=channel.recv(256);rows.append({'request_hex':payload.hex(),'response_hex':raw.hex()})
        finally:channel.close()
    denied={}
    for path in TARGETS:
        try:
            fd=_pos.open(path,_pos.O_RDONLY|_pos.O_NONBLOCK);_pos.close(fd);denied[path]=False
        except OSError:denied[path]=True
    tick=_security_original_now()
    with open('/data/clock-security-probe.jsonl','a') as target:
        target.write(_pjson.dumps({'requests':rows,'denied_paths':denied,'now':tick,
            'source':'ACTUAL_CANDIDATE_WORKER_SECURITY_CONTROL'})+'\n')
    return tick
'''


def clock_probe(evidence):
    from benchmark.h2_cli import register_h2
    from benchmark.runner import BenchmarkRunner
    from evaluator.dv02_supervisor import DV02WorkerSupervisor
    from evaluator.episode_d_v02_oracle import inspect_episode_d_v02_database
    register_h2()
    prepared=BenchmarkRunner(evidence.output/"clock-runs").prepare("D-V02")
    run=evidence.output/"clock-runs"/prepared["run_id"]
    workspace=run/"clock-security-candidate";shutil.copytree(run/"workspace",workspace)
    artifacts=evidence.output/"clock-artifacts";artifacts.mkdir()
    pool=DV02WorkerSupervisor(workspace,run/"clock-data",artifacts,worker_count=2,clock_tick=742).start()
    baseline=pool.clock.tick
    try:
        source=workspace/"app/request_clock.py";original=source.read_text()
        targets=[str(pool.clock.directory),str(pool.clock.path),
            "/maintainer/aevora-db.password","/maintainer/gateway.key",
            str(ROOT/"evaluator/hidden_tests/episode_d_v02"),str(ROOT/"evaluator/episode_d_v02_oracle.py")]
        addition=CLOCK_CODE.replace("PAYLOADS",repr(CLOCK_PAYLOADS)).replace("TARGETS",repr(targets))
        source.write_text(original+"\n"+addition)
        write(evidence.output/"clock_control_source.json",{"workspace":str(workspace),"path":str(source),
            "sha256":sha(source),"original_sha256":hashlib.sha256(original.encode()).hexdigest(),
            "classification":"PUBLIC_CLOCK_ABSTRACTION_SECURITY_CONTROL_NOT_AGENT_PATCH"})
        pool.stop_all();pool.start();pool.initialize({"SKU-1":5},reset=True)
        for index in range(2):
            result=pool.call(index,"claim_request",request_id=f"security-{index}",order_id=f"security-order-{index}",
                sku="SKU-1",quantity=1,ttl=10)
            evidence.check("clock_query_worker_"+str(index),result["outcome"]=="CLAIM_GRANTED"
                and result["request"]["deadline"]==baseline+10,
                {"outcome":result["outcome"],"deadline":result["request"]["deadline"]},
                scope="Actual isolated D-V02 Worker public API with real Clock NOW")
        topology=pool.evidence();write(evidence.output/"clock_topology.json",topology)
        records=[json.loads(line) for line in (run/"clock-data/clock-security-probe.jsonl").read_text().splitlines()]
        refused=[row for row in topology["clock"]["events"] if row["event"]=="clock.request_denied"]
        pids={row["host_pid"] for row in topology["identity_generations"]}
        evidence.check("clock_protocol_refusal",len(refused)==len(CLOCK_PAYLOADS)*2
            and all(row["peer"]["host_pid"] in pids for row in refused) and pool.clock.tick==baseline,
            {"denied_events":refused,"tick_before":baseline,"tick_after":pool.clock.tick},
            scope="Host Clock events/kernel SO_PEERCRED; no candidate boolean truth")
        evidence.check("clock_parent_and_credential_denial",len(records)==2
            and all(all(row["denied_paths"].values()) for row in records),records,
            scope="Actual candidate open/close path probes; true contents never read")
        pool.stop_all()
        audit=inspect_episode_d_v02_database(run/"clock-data/business.sqlite",expected_stock={"SKU-1":5},
            data_dir=run/"clock-data")
        write(evidence.output/"clock_oracle.json",audit)
        evidence.check("clock_no_business_corruption",audit["consistent"] and not audit["orders"]
            and not audit["ledger"] and len(audit["requests"])==2,audit,
            scope="Independent raw host database Oracle after workers stopped")
    finally:
        pool.close();topology=pool.evidence();write(evidence.output/"clock_cleanup.json",topology)
        evidence.check("clock_worker_cleanup",topology["clock"]["cleanup"]["complete"] is True
            and topology["clock"]["cleanup"]["query_socket_removed"] is True
            and topology["clock"]["cleanup"]["remaining_threads"] == []
            and topology["cleanup"]["complete"] is True
            and topology["cleanup"]["control_directory_removed"] is True
            and topology["cleanup"]["remaining_pids"] == []
            and topology["pool_cgroup"]["cleanup_complete"] is True,topology["cleanup"],
            scope="Actual owner cgroup/process/query socket teardown")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("all","boundary","clock","mcp","contracts"))
    parser.add_argument("output",type=Path)
    parser.add_argument("--archive",type=Path,required=True)
    args=parser.parse_args(argv)
    require_h2_graph()
    evidence=DV02Evidence(args.output)
    error=None
    try:
        for mode in (("boundary","clock","mcp","contracts") if args.mode=="all" else (args.mode,)):
            if mode=="boundary":boundary(evidence,args.archive.resolve())
            else:{"clock":clock_probe,"mcp":mcp_probes,"contracts":runtime_contracts}[mode](evidence)
    except Exception as failure:
        error={"type":type(failure).__name__,"classification":"D_V02_SECURITY_PROBE_EXECUTION_ERROR"}
        evidence.check("execution_error",False,error,scope="Failure retained; exception text not logged to avoid credentials")
    return evidence.finish(args.mode,error)


if __name__=="__main__":
    raise SystemExit(main())
