"""Actual official SDK calls against the owned synthetic demo; no model run."""
import asyncio,json,os,sys,uuid
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    state=sys.argv[1];events=[]
    params=StdioServerParameters(command=sys.executable,args=['-m','aevora.demo_mcp','--state-dir',state,'--context','threads'],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize();tools=await session.list_tools();names={t.name for t in tools.tools};assert names=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}
            async def call(name,args):
                r=await session.call_tool(name,args);data=r.structuredContent;assert not r.isError,(name,r);events.append(dict(tool=name,arguments=args,result=data));return data
            q=await call('resolve_experience',{'task_context':{}});r=q['recommendations'][0];assert r['core_verdict']=='APPLY'
            b=await call('build_evidence_bundle',{'experience_id':r['experience_id'],'query_id':q['query_id']});assert b['witness']['completeness']=='COMPLETE'
            d=await call('record_decision',{'decision':dict(query_id=q['query_id'],experience_id=r['experience_id'],recommendation_id=r['recommendation_id'],idempotency_key=uuid.uuid4().hex,decision='VERIFY',reason='Public SDK acceptance checks; no autonomous Agent claim.',verification_steps=['Inspect actual public SQLite verifier'])});assert d['status']=='RECORDED_UNTRUSTED'
            p=await call('propose_experience',{'proposal':dict(candidate_key=uuid.uuid4().hex,title='Synthetic SDK observation',strategy='Verify the scope before reuse.',public_summary='Non-model public SDK acceptance only.',necessary_conditions={'task.concurrency_scope':['single_process_threads']},inapplicable_conditions={'task.concurrency_scope':['independent_processes']},scope={'task.shared_state_kind':['sqlite_file']},unknown_fields=[],limitations=['Synthetic test only; no production publication'],source_references=[dict(kind='Decision',id=d['decision_id'])])});assert p['status']=='PROPOSED_UNTRUSTED' and p['publication']=='NOT_PUBLISHED'
            denied=await session.call_tool('resolve_experience',{'task_context':{},'authority':'host'});assert denied.isError
    print(json.dumps(dict(status='PASS',source='OFFICIAL_MCP_SDK_NOT_MODEL',tool_names=sorted(names),events=events,unauthorized_extra_field='REJECTED',candidate_published=False),sort_keys=True))
asyncio.run(main())
