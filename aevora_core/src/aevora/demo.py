"""Explicit, owned public Graph v2 demo. Synthetic trust is never production trust.

Only this trusted CLI creates the example graph. Browser and MCP cannot publish
or seed. All displayed recommendations call the unchanged production resolver.
"""
from datetime import datetime, timedelta, timezone
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid
from .contracts import TenantBinding, TrustRegistry, canonical_json, record, digest
from .graph_repository import GraphRepository
from .experience_resolver import resolve_v2
from .models import utc_now

CONTEXTS={
    "threads":{"task__shared_state_kind":"sqlite_file","task__concurrency_scope":"single_process_threads"},
    "workers":{"task__shared_state_kind":"sqlite_file","task__concurrency_scope":"independent_processes"},
    "unknown":{"task__shared_state_kind":"sqlite_file","task__concurrency_scope":None},
}
STAGES={"before":"baseline","after":"withdrawn"}
TENANT="aevora-public-synthetic-demo"
MAX_STATE=1024*1024

def state_path(directory, stage):
    if stage not in STAGES:raise ValueError("Unknown demo stage")
    directory=Path(directory).absolute()
    if any(p.is_symlink() for p in [directory,*directory.parents]):raise ValueError("Demo state may not follow links")
    return directory/(STAGES[stage]+".json")

def read_state(directory, stage):
    p=state_path(directory,stage)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_size>MAX_STATE:
            raise ValueError("Demo state must be bounded, owned and mode0600")
        raw=os.read(fd,MAX_STATE+1)
        if len(raw)!=s.st_size:raise ValueError("Demo state changed")
        return json.loads(raw)
    finally:os.close(fd)

def connect(directory, stage):
    body=read_state(directory,stage)
    transport=GraphRepository.from_environment()
    # Configured graph is a namespace prefix; no arbitrary browser graph selector.
    expected=transport.graph_name+"_"+STAGES[stage]
    transport.close()
    if body["binding"]!={"tenant_id":TENANT,"graph_name":expected}:raise ValueError("Demo binding conflict")
    env=dict(os.environ,AEVORA_FALKORDB_GRAPH=expected)
    transport=GraphRepository.from_environment(env)
    repo=transport.v2(TenantBinding(**body["binding"]),TrustRegistry(**body["registry"]))
    return transport,repo,body

def seed(directory):
    from .demo_fixture import facts, seed as fixture_seed
    root=Path(directory).absolute()
    state_path(root,'before')  # Reject linked ancestors before any mutation.
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError("Demo state directory must be owned and mode0700")
    # A separate process executes the public example; the graph does not grade itself.
    proc=subprocess.run([sys.executable,"-m","aevora.demo_verify"],capture_output=True,text=True,timeout=30)
    if proc.returncode:raise RuntimeError("Public verifier failed; no seed publication")
    verification=json.loads(proc.stdout)
    if verification["verdict"]!="PASS":raise RuntimeError("Public verifier did not pass")
    for stage,suffix in STAGES.items():
        dest=state_path(root,stage)
        if dest.exists():raise ValueError("Fresh demo state required; choose a new project/state directory")
        original=GraphRepository.from_environment();prefix=original.graph_name;original.close()
        env=dict(os.environ,AEVORA_FALKORDB_GRAPH=prefix+"_"+suffix)
        t=GraphRepository.from_environment(env)
        try:
            if t.graph_name.encode() in t._client.connection.execute_command("GRAPH.LIST"):
                raise ValueError("Demo graph already exists; never overwrite another graph")
            registry=TrustRegistry();repo=t.v2(TenantBinding(TENANT,t.graph_name),registry);repo.initialize()
            example=fixture_seed(repo,key="process-local-critical-section",required={"task.concurrency_scope":["single_process_threads"]},withdraw=stage=="after",verification=verification)
            all_facts={name:facts(registry,**values) for name,values in CONTEXTS.items()}
            body=dict(schema="aevora.public.synthetic-demo/1",origin="LIVE_SYNTHETIC_DEMO",
                      binding=repo.binding.__dict__,registry=registry.__dict__,contexts=all_facts,
                      experience_id=example["experience"]["id"],public_verifier=verification,
                      publication="SYNTHETIC_FIXTURE_NOT_PRODUCTION_Q07",created_at=utc_now())
            fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"w") as f:f.write(canonical_json(body))
        finally:t.close()
    return {"status":"SEEDED","origin":"LIVE_SYNTHETIC_DEMO","public_verifier":verification,"production_host":"NOT_EXERCISED"}

def observe(directory, context="threads", stage="before"):
    if context not in CONTEXTS or stage not in STAGES:raise ValueError("Unknown selector")
    t,repo,body=connect(directory,stage)
    try:
        query="public-demo-"+uuid.uuid4().hex
        state,rows=resolve_v2(repo,body["contexts"][context],query,utc_now())
        if len(rows)!=1:raise ValueError("Expected complete owned demo witness")
        recommendation,witness=rows[0]
        nodes=[dict(id=n["id"],label=n["kind"],**{k:v for k,v in n.items() if k in {"title","strategy","scope","fact_key","allowed_values","verdict","event_type"}}) for n in witness["nodes"].values()]
        edges=[dict(id=e["id"],source=e["source_id"],target=e["target_id"],relation=e["kind"]) for e in witness["edges"].values()]
        return dict(schema="aevora.public.decision-journey/1",mode="LIVE_SYNTHETIC_DEMO",observed_at=utc_now(),
                    recommendation=recommendation,witness_sha256=digest(witness),graph=dict(nodes=nodes,edges=edges),
                    query_receipts=repo.query_receipts,state=state,context=context,stage=stage,
                    public_verifier=body["public_verifier"],
                    agent_decision="NOT_RUN_SYNTHETIC_SCENARIO",model_execution=False,
                    publication=body["publication"],causal_benefit="UNKNOWN",fallback=False)
    finally:t.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=["seed","observe"]);p.add_argument("--state-dir",type=Path,required=True);p.add_argument("--context",choices=list(CONTEXTS),default="threads");p.add_argument("--stage",choices=list(STAGES),default="before");a=p.parse_args()
    result=seed(a.state_dir) if a.command=="seed" else observe(a.state_dir,a.context,a.stage)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":main()
