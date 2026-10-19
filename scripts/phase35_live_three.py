"""Three bounded benchmark repetitions. All agent delegation stays native Codex."""
import datetime,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
archive=pathlib.Path(sys.argv[1]).resolve()
agent_timeout=int(sys.argv[2]) if len(sys.argv)>2 else 900
if not 0 < agent_timeout <= 1500:
 raise ValueError('Finite validation wall budget must be within (0, 1500] seconds')
collection=archive/'validated-challenges';collection.mkdir()
runroot=archive/'validated-challenge-runs'
for index in range(1,4):
 directory=collection/f'challenge-{index}';directory.mkdir()
 command=[sys.executable,'-m','benchmark.cli','--runs-root',str(runroot),'run-codex','--episode','A','--provider','gateway','--model','gpt-5.6-terra','--reasoning-effort','max','--agent-timeout',str(agent_timeout),'--request-budget','160']
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
 with (directory/'stdout.log').open('wb') as out,(directory/'stderr.log').open('wb') as err:
  process=subprocess.run(command,stdout=out,stderr=err,timeout=agent_timeout+120)
 try:result=json.loads((directory/'stdout.log').read_text())
 except ValueError:result={}
 record={'challenge':index,'argv':command,'started_at':started,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':process.returncode,'elapsed_seconds':time.monotonic()-t,'run_id':result.get('run_id'),'overall_status':result.get('overall_status'),'runtime_status':result.get('runtime_status'),'multi_agent_status':result.get('multi_agent_status'),'submission_integrity_status':result.get('submission_integrity_status'),'evaluation_status':result.get('evaluation_status'),'isolation_status':result.get('isolation_status'),'integration_status':result.get('integration_status'),'tests':result.get('test_results'),'submission':result.get('submission')}
 with (directory/'command.json').open('x') as output:json.dump(record,output,indent=2);output.write('\n')
 print(json.dumps({key:value for key,value in record.items() if key not in ('tests','submission','argv')}),flush=True)
 if result.get('execution_errors') and any('BLOCKED_SECURITY_GATE' in error for error in result['execution_errors']):
  raise RuntimeError('Security gate blocked; no unsafe continuation')
