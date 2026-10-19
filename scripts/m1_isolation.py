"""D public-package audit and actual three-layer offline isolation probes."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from benchmark.participant_sandbox import participant_command
from benchmark.sandbox import sandbox_command,runtime_python
from evaluator.control import WorkerControl


def main():
    archive=Path(sys.argv[1]).resolve()
    archive.mkdir(parents=True,exist_ok=False)
    prepared=BenchmarkRunner(archive/"runs").prepare("D")
    workspace=archive/"runs"/prepared["run_id"]/"workspace"
    participant=build_participant(workspace,archive/"participant")
    state=archive/"state";state.mkdir()
    public_files={str(p.relative_to(participant)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(participant.rglob("*")) if p.is_file() and ".git" not in p.relative_to(participant).parts}
    allowed=lambda name:name.startswith(("app/","tests/public/",".codex/agents/")) or name in {
        "AGENTS.md","ISSUE.md","TASK.md","public.json"}
    assert all(allowed(p) for p in public_files),public_files
    documents="\n".join((participant/p).read_text() for p in public_files if not p.startswith(("app/","tests/")))
    forbidden=["RLock cannot","RLock 无法","Negative Transfer","负迁移标准答案","use database atomic","使用数据库原子更新","episode_d_applicability","D-v01.diff","TASK_SYSTEM_DESIGN"]
    leaks=[term for term in forbidden if term.lower() in documents.lower()]
    assert not leaks,leaks
    auth=archive/"synthetic-auth-canary";auth.write_text("synthetic boundary canary");auth.chmod(0o600)
    targets={"hidden_tests":ROOT/"evaluator/hidden_tests","private_manifest":ROOT/"evaluator/private_manifests/D.json",
             "private_labels":ROOT/"evaluator/private_labels/episode_d_applicability.json",
             "reference":ROOT/"evaluator/reference_patches/D-v01.diff","maintainer_business":ROOT/"app/service.py",
             "maintainer_modules":ROOT/"benchmark","other_historical_run":ROOT/"runs/339f7d73-29df-4242-8920-9e566bce8a9c/evaluation_report.json",
             "other_m1_run":archive/"runs"/prepared["run_id"]/"evaluation_report.json",
             "maintainer_guide":ROOT/"AGENTS.md","task_design":ROOT/"docs/TASK_SYSTEM_DESIGN.md",
             "user_directory":Path.home(),"synthetic_auth":auth}
    assert all(p.exists() for p in targets.values()),targets
    paths={k:str(p) for k,p in targets.items()}
    paths.update({"proc_root_"+k:"/proc/1/root"+v for k,v in list(paths.items())})
    paths["traversal"]="/workspace/../../"+str(ROOT/"app/service.py").lstrip("/")
    records=[]
    def run(label,command):
        started=datetime.now(timezone.utc).isoformat()
        p=subprocess.run(command,capture_output=True,text=True,timeout=30)
        (archive/(label+".stdout.log")).write_text(p.stdout)
        (archive/(label+".stderr.log")).write_text(p.stderr)
        try:observations=json.loads(p.stdout)
        except ValueError:observations=None
        record={"label":label,"argv":command,"started_at":started,"ended_at":datetime.now(timezone.utc).isoformat(),
                "exit_code":p.returncode,"result":observations,
                "stdout_sha256":hashlib.sha256(p.stdout.encode()).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr.encode()).hexdigest()}
        records.append(record)
        (archive/"commands.json").write_text(json.dumps(records,indent=2)+"\n")
        return record
    def probe_code(values):
        return '''import os,json,pathlib
targets=VALUES
observed={}
for label,path in targets.items():
 try:
  if pathlib.Path(path).is_dir():os.listdir(path)
  else:
   descriptor=os.open(path,os.O_RDONLY);os.close(descriptor)
  observed[label]={"readable":True}
 except OSError as error:observed[label]={"readable":False,"errno":error.errno}
print(json.dumps({"paths":observed,"public_source":pathlib.Path('/workspace/app/service.py').is_file()}))
assert all(not x['readable'] for x in observed.values())
'''.replace("VALUES",repr(values))
    binary=Path(os.environ["ORDERFLOW_CODEX_BINARY"])
    common=[runtime_python(),"-I","-c",probe_code(paths)]
    run("outer-files",participant_command(participant,state,binary,common,network_isolated=True))
    run("native-files",participant_command(participant,state,binary,
        ["/opt/codex/codex","sandbox","-c",'sandbox_mode="workspace-write"',"-c",'approval_policy="never"',"--",*common],network_isolated=True))
    run("candidate-files",sandbox_command(participant,common))
    control=WorkerControl(2)
    try:
        control.prepare_restart(0)
        extra={**paths,"socket_parent":str(control.directory),"other_worker_socket":str(control.paths[1])}
        code=probe_code(extra)+'''\nimport socket
connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);connection.connect('/control.sock')
connection.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\\n')
assert connection.recv(100)==b'{"command":"continue"}\\n'
connection.close()
'''
        run("candidate-files-with-control",sandbox_command(participant,[runtime_python(),"-I","-c",code],control_socket=control.paths[0]))
        (archive/"control-probe.json").write_text(json.dumps(control.observation(),indent=2)+"\n")
    finally:control.close()
    listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen(8);listener.settimeout(.2)
    port=listener.getsockname()[1];stop=threading.Event();accepted=[]
    def listen():
        while not stop.is_set():
            try:connection,_=listener.accept();accepted.append(True);connection.close()
            except socket.timeout:pass
            except OSError:break
    thread=threading.Thread(target=listen);thread.start()
    network=f'''import socket,json
try:
 s=socket.socket();s.settimeout(2);s.connect(('127.0.0.1',{port}));s.close();result={{'connected':True}}
except OSError as error:result={{'connected':False,'errno':error.errno}}
print(json.dumps(result));assert not result['connected']
'''
    try:
        common=[runtime_python(),"-I","-c",network]
        run("outer-owned-network",participant_command(participant,state,binary,common,network_isolated=True))
        run("native-owned-network",participant_command(participant,state,binary,
            ["/opt/codex/codex","sandbox","-c",'sandbox_mode="workspace-write"',"-c",'approval_policy="never"',"--",*common],network_isolated=True))
        run("candidate-owned-network",sandbox_command(participant,common))
    finally:stop.set();listener.close();thread.join(timeout=2)
    success=all(r["exit_code"]==0 for r in records) and not accepted
    summary={"mandatory_boundary_result":"PASS" if success else "FAIL","overall_security":"CONDITIONAL",
             "public_files":public_files,"public_diagnostic_root_cause_leaks":leaks,"prepared_run_id":prepared["run_id"],
             "records":records,"model_calls":0,"actual_secret_read_attempted":False,"synthetic_auth_probe_only":True,
             "limitations":["Linux namespaces, not VM isolation","CPU/output sampling retains detection windows",
                            "Local evidence has no third-party attestation","Model-channel live use is verified by the subsequent Pilot"]}
    (archive/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"mandatory_boundary_result":summary["mandatory_boundary_result"],"probes":len(records),"model_calls":0}))
    return 0 if success else 1


if __name__=="__main__":raise SystemExit(main())
