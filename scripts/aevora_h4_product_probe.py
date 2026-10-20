"""Run inside the public-only image: installed Core + real SDK, no Benchmark imports."""
import asyncio,importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from aevora.graph_repository import GraphRepository
from aevora_observatory.projection import channel_activity

out=Path('/evidence');out.mkdir(exist_ok=True);channel=Path('/channel');cap=channel/'grant.json';sock=channel/'mcp.sock';events=channel/'mcp_events.jsonl';checks=[]
def check(name,ok,actual):
    checks.append({'name':name,'status':'PASS' if ok else 'FAIL','actual':actual})
    (out/'CHECKPOINT.json').write_text(json.dumps(checks,indent=2)+'\n')
    if not ok:raise AssertionError(name)

assert importlib.util.find_spec('benchmark') is None and importlib.util.find_spec('evaluator') is None
init_argv=[sys.executable,'-I','-m','aevora','init']
initialized=subprocess.run(init_argv,capture_output=True)
(out/'init-stdout.log').write_bytes(initialized.stdout);(out/'init-stderr.log').write_bytes(initialized.stderr)
check('documented_public_cli_initialization',initialized.returncode==0,{'argv':init_argv,'exit_code':initialized.returncode,'result':json.loads(initialized.stdout) if initialized.returncode==0 else None})
repo=GraphRepository.from_environment();check('new_volume_empty_published_graph',repo.experience_ids()==[],{'experiences':repo.experience_ids(),'graph':repo.graph_name});repo.close()
run_id='fresh-user-sdk';argv=[sys.executable,'-I','-m','aevora','serve','--run-id',run_id,'--context','/opt/aevora/examples/observatory/context.json','--socket',str(sock),'--capability-file',str(cap),'--events',str(events),'--enable-proposals']
stdout=(out/'serve-stdout.log').open('wb');stderr=(out/'serve-stderr.log').open('wb');proc=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
try:
    deadline=time.monotonic()+30
    while not cap.exists():
        if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Public Core serve not ready')
        time.sleep(.05)
    async def protocol():
        params=StdioServerParameters(command=sys.executable,args=['-I','-m','aevora.mcp_connect','--capability-file',str(cap)],env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/home/aevora'})
        with (out/'consumer-stderr.log').open('w') as errors:
            async with stdio_client(params,errlog=errors) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();tools=await session.list_tools();names={t.name for t in tools.tools};check('installed_official_sdk_four_tools',names=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'},sorted(names))
                    query=(await session.call_tool('resolve_experience',{'task_context':{}})).structuredContent
                    check('actual_query_zero_candidates_not_fake_hit',query['status']=='AVAILABLE' and query['candidates']==[],query)
                    absent=await session.call_tool('build_evidence_bundle',{'experience_id':'experience:not-present','query_id':query['query_id']})
                    check('absent_experience_explicit_error',absent.isError,absent.model_dump(mode='json'))
                    proposal={'candidate_key':'explicit-sdk-fixture','title':'Unreviewed protocol fixture','public_summary':'Explicit protocol check, not a natural model experience or verified test outcome.','strategy':'Inspect current source before reuse.','scope':{'shared_state_kind':['sqlite_file']},'necessary_conditions':{'shared_state_kind':['sqlite_file']},'inapplicable_conditions':{},'unknown_fields':['failure_domain'],'limitations':['No independent Oracle exists in this protocol fixture.'],'source_references':[{'kind':'Query','id':query['query_id']}]}
                    proposal_result=await session.call_tool('propose_experience',{'proposal':proposal})
                    (out/'PROPOSAL_RESULT.json').write_text(json.dumps(proposal_result.model_dump(mode='json'),indent=2)+'\n')
                    p=proposal_result.structuredContent
                    check('proposal_untrusted_not_published',not proposal_result.isError and isinstance(p,dict) and p.get('status')=='PROPOSED_UNTRUSTED',proposal_result.model_dump(mode='json'))
                    forged=await session.call_tool('propose_experience',{'proposal':{**proposal,'verified':True}});check('deny_self_claimed_verification',forged.isError,forged.model_dump(mode='json'))
                    headers=channel_activity(events);check('ordinary_owner_console_actual_headers',len(headers)==1 and headers[0]['run_id']==run_id and headers[0]['session_id'] is None and len(headers[0]['tool_events'])>=4,headers)
                    (out/'PUBLIC_MCP_HEADERS.json').write_text(json.dumps(headers,indent=2)+'\n')
                    try:
                        forbidden=await session.call_tool('publish',{})
                    except Exception as e:
                        from mcp.shared.exceptions import McpError
                        check('privileged_publish_denied',isinstance(e,McpError) and e.error.message=='Connection closed',{'error_type':type(e).__name__,'method_in_catalogue':False})
                    else:check('privileged_publish_denied',forbidden.isError,forbidden.model_dump(mode='json'))
    asyncio.run(protocol())
finally:
    proc.send_signal(signal.SIGTERM);exit_code=proc.wait(15);stdout.close();stderr.close();check('owner_revokes_channel',exit_code==0 and not cap.exists() and not sock.exists(),{'exit':exit_code,'grant_removed':not cap.exists(),'socket_removed':not sock.exists(),'argv':argv})
repo=GraphRepository.from_environment()
try:
    counts={label:repo.query('MATCH(n:'+label+') RETURN count(n)')[0][0] for label in ['Experience','VerifiedOutcome','SourceVerification','Candidate']}
    check('no_trusted_outcome_no_publication',counts['Experience']==counts['VerifiedOutcome']==counts['SourceVerification']==0 and counts['Candidate']==1,counts)
finally:repo.close()
import sqlite3,platform,importlib.metadata
versions={n:importlib.metadata.version(n) for n in ['aevora-core','aevora-console','falkordb','redis','mcp','starlette','uvicorn']}
(out/'RESULT.json').write_text(json.dumps({'status':'PASS','checks':checks,'versions':versions,'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'model_calls':0,'authority':'ACTUAL_PUBLIC_INSTALLED_CORE_OFFICIAL_SDK_PROTOCOL; NOT_A_NATIVE_MODEL_SESSION'},indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':len(checks),'model_calls':0,'versions':versions}))
