"""Clean standalone Core install and real official SDK onboarding on an empty graph."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now


def main(label='clean-onboarding'):
    a=archive();out=a/'g1'/label;out.mkdir(parents=True,mode=0o700)
    source=out/'source';source.mkdir();shutil.copytree(ROOT/'aevora_core',source/'aevora_core',ignore=shutil.ignore_patterns('build','dist','*.egg-info','__pycache__','.pytest_cache','.venv'))
    commands=[];checks=[]
    def cmd(argv,cwd=source,env=None):
        started=now();r=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,capture_output=True,timeout=300)
        d=out/('command-'+str(len(commands)+1));d.mkdir();(d/'stdout.log').write_bytes(r.stdout);(d/'stderr.log').write_bytes(r.stderr)
        row={'argv':list(map(str,argv)),'cwd':str(cwd),'exit_code':r.returncode,'started_at':started,'ended_at':now(),
             'stdout_sha256':digest(d/'stdout.log'),'stderr_sha256':digest(d/'stderr.log')}
        write(d/'command.json',row);commands.append(row)
        if r.returncode:raise ValueError('Standalone command failed; evidence retained')
        return r.stdout
    def check(name,ok,data):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL','actual':data})
        write(out/(name+'.json'),data)
        if not ok:raise ValueError('Onboarding check failed: '+name)
    dist=out/'dist';dist.mkdir();cmd([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',dist,source/'aevora_core'])
    wheel=next(dist.glob('*.whl'))
    with zipfile.ZipFile(wheel) as z:
        names=z.namelist();bad=[n for n in names if any(x in n for x in ['benchmark/','integrations/','evaluator/','reference_patches/','private_manifests/','hidden_tests/'])]
    check('public_wheel_no_private_members',not bad,{'members':names,'private_matches':bad,'wheel_sha256':digest(wheel)})
    venv=out/'venv';cmd([sys.executable,'-m','venv',venv]);python=venv/'bin/python'
    cmd([python,'-m','pip','install',wheel]);cmd([python,'-m','pip','check'])
    ordinary=out/'ordinary-project';ordinary.mkdir();context=json.loads((ROOT/'examples/observatory/context.json').read_text());write(ordinary/'context.json',context)
    env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']};env['AEVORA_FALKORDB_GRAPH']='aevora_h4_user_'+uuid.uuid4().hex
    cmd([python,'-I','-c',"import importlib.util;assert importlib.util.find_spec('benchmark') is None;assert importlib.util.find_spec('integrations') is None;import aevora.mcp_connect;print('STANDALONE_CORE_ONLY')"],ordinary,env)
    cmd([python,'-I','-m','aevora','init'],ordinary,env)
    result=json.loads(cmd([python,'-I','-m','aevora','query','--run-id','h4-clean-onboarding','--context',ordinary/'context.json'],ordinary,env))
    check('actual_empty_volume_graph_query',result['status']=='AVAILABLE' and result['candidates']==[],result)
    # A clearly labelled unsupported principle lets the actual tools exercise
    # bundle/claim semantics without inventing an independent trusted Outcome.
    seed="""from aevora.graph_repository import GraphRepository
r=GraphRepository.from_environment()
try:
 r.import_experience({'id':'experience:public-unverified-example','title':'Unverified SQLite principle','strategy':'Investigate one coherent durable write transaction','public_summary':'Explicit public onboarding example; no supporting Oracle exists.','source_type':'synthetic_or_test_fixture'}, {'id':'rule:public-unverified-example','version':'1','premises':[{'id':'premise:public-sqlite','fact_key':'shared_state_kind','allowed_values':['sqlite_file'],'required':True}]})
 print('UNSUPPORTED_EXAMPLE_IMPORTED_NO_OUTCOME')
finally:r.close()
"""
    cmd([python,'-I','-c',seed],ordinary,env)
    with tempfile.TemporaryDirectory(prefix='aevora-h4-core-') as temporary:
        private=Path(temporary);private.chmod(0o700);cap=private/'grant.json';sock=private/'mcp.sock'
        argv=[str(python),'-I','-m','aevora','serve','--run-id','h4-ordinary-onboarding','--context',str(ordinary/'context.json'),
              '--socket',str(sock),'--capability-file',str(cap),'--events',str(out/'actual_mcp_events.jsonl'),'--enable-proposals']
        stdout=(out/'serve-stdout.log').open('wb');stderr=(out/'serve-stderr.log').open('wb')
        process=subprocess.Popen(argv,cwd=ordinary,env=env,stdout=stdout,stderr=stderr)
        deadline=time.monotonic()+15
        while not cap.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        if not cap.exists():process.terminate();process.wait(10);raise ValueError('Core serve did not become READY')
        token=json.loads(cap.read_text())['AEVORA_RUN_TOKEN']
        async def protocol():
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
            consumer={'PATH':'/usr/bin:/bin','HOME':str(private)}
            params=StdioServerParameters(command=str(python),args=['-I','-m','aevora.mcp_connect','--capability-file',str(cap)],env=consumer,cwd=str(ordinary))
            with (out/'consumer-stderr.log').open('w') as errors:
                async with stdio_client(params,errlog=errors) as (reader,writer):
                    async with ClientSession(reader,writer) as session:
                        await session.initialize();tools=await session.list_tools();names={t.name for t in tools.tools}
                        check('official_sdk_four_tools',names=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'},{'tools':sorted(names)})
                        resolved=(await session.call_tool('resolve_experience',{'task_context':{}})).structuredContent
                        check('unsupported_example_requires_verification',resolved['candidates'][0]['decision']=='VERIFY',resolved)
                        eid=resolved['candidates'][0]['experience_id'];qid=resolved['query_id']
                        bundle=(await session.call_tool('build_evidence_bundle',{'experience_id':eid,'query_id':qid})).structuredContent
                        check('actual_bundle_no_fake_support',bundle['support_paths']==[],bundle)
                        decision=(await session.call_tool('record_decision',{'decision':{'query_id':qid,'experience_id':eid,'decision':'VERIFY','reason':'No trusted support; inspect own ordinary source.','verification_steps':['Run original public tests.']}})).structuredContent
                        check('actual_decision_untrusted',decision['status']=='RECORDED_UNTRUSTED',decision)
                        proposal={'candidate_key':'ordinary-example','title':'Unreviewed ordinary observation','public_summary':'No independent evaluator exists in this onboarding example.','strategy':'Investigate coherent SQLite writes before reuse.','scope':{'shared_state_kind':['sqlite_file']},'necessary_conditions':{'shared_state_kind':['sqlite_file']},'inapplicable_conditions':{},'unknown_fields':['failure_domain'],'limitations':['External observations are unverified.'],'source_references':[{'kind':'Query','id':qid}]}
                        created=(await session.call_tool('propose_experience',{'proposal':proposal})).structuredContent
                        check('actual_proposal_untrusted',created['status']=='PROPOSED_UNTRUSTED',created)
                        from mcp.shared.exceptions import McpError
                        try:
                            forbidden=await session.call_tool('publish',{})
                        except McpError as denied:
                            # The existing broker deliberately closes an
                            # unauthorized tool channel. Preserve the actual
                            # SDK denial rather than requiring a fabricated
                            # isError tool result from an unavailable method.
                            check('host_publish_not_an_agent_tool',denied.error.message=='Connection closed',
                                  {'error_type':'McpError','message':denied.error.message,'tool_not_in_catalogue':'publish' not in names})
                        else:check('host_publish_not_an_agent_tool',forbidden.isError,forbidden.model_dump(mode='json'))
        try:asyncio.run(protocol())
        finally:
            process.send_signal(signal.SIGTERM);code=process.wait(15);stdout.close();stderr.close()
            check('owner_revocation_removes_grant_socket',code==0 and not cap.exists() and not sock.exists(),{'exit_code':code,'capability_removed':not cap.exists(),'socket_removed':not sock.exists(),'argv':argv})
            check('known_capability_not_archived',all(token.encode() not in p.read_bytes() for p in out.glob('*.log')) and token.encode() not in (out/'actual_mcp_events.jsonl').read_bytes(),{'capability_value_matches':0})
    cmd([python,'-I','-c',"from aevora.graph_repository import GraphRepository;r=GraphRepository.from_environment();assert r.query('MATCH(n:VerifiedOutcome) RETURN count(n)')==[[0]];assert r.query('MATCH(n:SourceVerification) RETURN count(n)')==[[0]];r.close();print('ZERO_VERIFIED_OUTCOMES_ZERO_HOST_SOURCES')"],ordinary,env)
    write(out/'RESULT.json',{'status':'PASS','checks':checks,'commands':commands,'graph':env['AEVORA_FALKORDB_GRAPH'],
        'wheel_sha256':digest(wheel),'core_without_benchmark':'PASS','authority':'ACTUAL_INSTALLED_CORE_OFFICIAL_SDK; NOT_A_MODEL_SESSION',
        'model_calls':0,'at':now()})
    print(json.dumps({'status':'PASS','checks':len(checks),'commands':len(commands),'model_calls':0}));return 0


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='clean-onboarding');a=p.parse_args()
    if not a.label.replace('-','').isalnum():raise ValueError('Simple output label required')
    raise SystemExit(main(a.label))
