"""New owned world: one explicitly Host-controlled real RLock seed, never Agent output."""
from audit import *
import uuid,copy
from datetime import datetime,timezone,timedelta
from benchmark.runner import BenchmarkRunner
from benchmark.episodes.episode_a import create_episode_a
from integrations.aevora import public_runtime_context
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora_maintainer.host_v2 import TrustedHost
root=E/'03_world_accepted';root.mkdir(mode=0o700);cases=json.loads((E/'02_source/cases/CASES.json').read_text())
w=create_episode_a(root/'seed-rlock-workspace');s=w/'app/service.py'
s.write_text(s.read_text()+'''\nimport threading
_create_lock = threading.RLock()
_unlocked_create = OrderFlow.create_order
def _serialized_create(self, *args, **kwargs):
    with _create_lock:
        return _unlocked_create(self, *args, **kwargs)
OrderFlow.create_order = _serialized_create
''')
report=BenchmarkRunner(root/'seed-runs').evaluate('A',w);assert report['overall_status']=='PASS'
run=root/'seed-runs'/report['run_id'];files={str(f.relative_to(run)):sha(f) for f in run.rglob('*') if f.is_file() and not f.is_symlink()};write(run/'HOST_RUN_MANIFEST.json',{'files':files})
anchor=TrustAnchor(run,sha(run/'HOST_RUN_MANIFEST.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='HOST_RUN_MANIFEST.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json')
r=GraphRepository.from_environment();repo=r.v2(TenantBinding('tenant-g23-live',r.graph_name),TrustRegistry());repo.initialize();pins=root/'private_host_pins'
grant=TrustedHost.bootstrap(repo,pins,principal='g23-seed-operator',allowed_scope={'task.shared_state_kind':['sqlite_file']})
h=TrustedHost(repo,pins,grant);v=h.register_orderflow(anchor,report['fingerprints']['evaluator']['sha256'],report['fingerprints']['test_suite']['sha256'])
p=dict(candidate_key='bounded-process-local-critical-section',title='Shared process-local critical section',strategy='Serialize the complete stale-read and reservation path with the same process-local RLock when every participant shares that process and lock object.',public_summary='Host-controlled complete critical section passed a fresh independent threaded Oracle. It does not coordinate independent worker processes.',necessary_conditions={'task.concurrency_scope':['single_process_threads'],'task.synchronization_scope':['shared_process_object']},inapplicable_conditions={'task.concurrency_scope':['independent_processes']},scope={'task.shared_state_kind':['sqlite_file'],'task.concurrency_scope':['single_process_threads']},unknown_fields=[],limitations=['HOST_CONTROLLED_STRATEGY_SEED, not a new Agent result','Not a cross-process coordination mechanism'],source_references=[])
c=h.propose(p,run_id=run.name,tree_sha=report['submission']['evaluated_sha256'],patch_sha=None)
source=h.verify_source(c['id'],v.authority_id,'evaluation_report.json');out=h.verify_outcome(c['id'],source['id']);review=h.review(c['id'],source['id'],out['id'],approved_scope=p['scope'],reason='Actual source critical section inspected; scope restricted to shared process object; independent A14 passed')
assert review['verification']=='REVIEW_APPROVED',review
head=h.transition(c['id'],'PUBLISHING',expected_head=digest(h.head(c['id'])),reason='Bounded explicit controlled seed')
prepared=h.prepare(c['id'],review['id'],request_key='seed-only',expected_head=digest(head),expected_epoch=repo.state()['epoch']);receipt=h.publish(prepared)
write(root/'SEED_RECEIPT.json',dict(origin='HOST_CONTROLLED_GRAPH_SEED',candidate=c,source=source,outcome=out,review=review,publication=receipt,graph=repo.binding.__dict__))
manifest=json.loads((P/'benchmark/scenarios/D/public.json').read_text());public=root/'public_inputs/D/public.json';public.parent.mkdir(parents=True);public.write_bytes((P/'benchmark/scenarios/D/public.json').read_bytes())
fs={};authority=grant.capability_id;firstline=public.read_bytes().splitlines(keepends=True)[0]
for key,value in public_runtime_context(manifest).items():
 if 'task.'+key not in schema('fact')['properties']['key']['enum']:continue
 known=value is not None
 f=dict(key='task.'+key,phase='task',availability='KNOWN' if known else 'UNKNOWN',value=value,authority_class='HOST_DECLARED_TASK' if known else None,authority_ref=authority if known else None,source_refs=[dict(file='public_inputs/D/public.json',file_sha256=sha(public),line=1,line_sha256=__import__('hashlib').sha256(firstline).hexdigest(),byte_scope='ARCHIVED_BYTES_INCLUDING_NEWLINE')] if known else [],observed_at=now() if known else None)
 fact(f);fs[f['key']]=f
 if known:h.pins.put('fact_sources',digest(f),authority)
until=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()
body=dict(binding=repo.binding.__dict__,registry={'pin_root':str(pins)},facts=fs,grant=dict(tenant=repo.tenant,session_id='capability-session-'+uuid.uuid4().hex,generation=uuid.uuid4().hex,valid_until=until,authz_epoch=repo.state()['authz_epoch'],profile=PROFILE))
write(root/'S1_BOOTSTRAP.json',body);(root/'S1_BOOTSTRAP.json').chmod(0o600)
write(root/'WORLD_REGISTERED.json',dict(seed_sha256=sha(root/'SEED_RECEIPT.json'),seed_run=run.name,seed_origin='HOST_CONTROLLED',seed_experience=receipt.get('experience_id'),S1_task='D/v01 new independent defective instance',S2_task='D/v01 independently initialized defective instance; no patch/session inheritance',task_input_sha=sha(public),bootstrap_sha=sha(root/'S1_BOOTSTRAP.json'),native_model='gpt-5.6-terra',effort='max',agent_mode='multi',request_budget=None,wall_timeout=None,capability_ttl_hours=24,capability_session_is_not_official_native_identity=True))
print(json.dumps({'seed_run':run.name,'seed_tests':report['test_results'],'receipt':receipt,'state':repo.state()}));r.close()
