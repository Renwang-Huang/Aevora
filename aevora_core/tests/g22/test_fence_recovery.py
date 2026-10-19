import os,signal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from aevora_maintainer.host_v2 import TrustedHost
from tools.validation.g22_fixture import ready

@pytest.mark.parametrize('writers',[2,4,8])
def test_single_fence_same_head_writers_only_one_commits(host,writers):
    c,r,p=ready(host,'first')
    head=host.head(c['id']);epoch=host.repo.state()['epoch']
    preps=[p]+[host.prepare(c['id'],r['id'],request_key='writer-'+str(i),expected_head=digest(head),expected_epoch=epoch) for i in range(writers-1)]
    barrier=Barrier(writers)
    def run(pp):
        barrier.wait()
        try:return host.publish(pp)['verification']
        except V2Error as e:return e.code
    with ThreadPoolExecutor(max_workers=writers) as pool:results=list(pool.map(run,preps))
    assert results.count('PUBLICATION_COMMITTED')==1 and results.count('CONFLICT')==writers-1
    assert host.repo.state()['epoch']==epoch+1
    assert host.repo.transport.query('MATCH(:TenantState)-[r:COMMITS]->() RETURN count(r)')==[[1]]

@pytest.mark.parametrize('which',['manifest','catalogue','prepared'])
def test_missing_chunk_blocks_without_any_activation(host,which):
    c,r,p=ready(host)
    root=host.repo.node(p.identifier);doc=host.repo.load_document(root)
    target={'manifest':doc['manifest'],'catalogue':doc['catalogue'],'prepared':root}[which]
    chunk=target['document']['chunks'][0]['id']
    host.repo.transport.query('MATCH(n:SnapshotChunk {id:$id}) DETACH DELETE n',{'id':chunk},read_only=False)
    with pytest.raises(V2Error):host.publish(p)
    assert host.repo.state()['epoch']==0 and host.repo.discover({},host.repo.state())==[]


def test_stale_head_rejected_after_prepare(host):
    c,r,p=ready(host)
    host.transition(c['id'],'WITHDRAWN',expected_head=digest(host.head(c['id'])),reason='Abort preparation')
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p)
    assert host.repo.state()['epoch']==0


def test_review_then_capability_revocation_blocks_fence(host):
    c,r,p=ready(host)
    host.revoke_capability(reason='Host authorization revoked before finalize')
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.publish(p)
    assert host.repo.state()['epoch']==0

@pytest.mark.parametrize('where',['before','after'])
def test_actual_process_kill_before_and_after_single_fence(host,where):
    c,r,p=ready(host)
    child=os.fork()
    if child==0:
        original=host.repo.transport.query
        def injected(statement,*args,**kwargs):
            fence='SET s=$new_state RETURN s.payload_sha256' in statement
            if fence and where=='before':os.kill(os.getpid(),signal.SIGKILL)
            result=original(statement,*args,**kwargs)
            if fence and where=='after':os.kill(os.getpid(),signal.SIGKILL)
            return result
        host.repo.transport.query=injected
        host.publish(p)
        os._exit(99)
    _,status=os.waitpid(child,0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
    assert host.repo.state()['epoch']==(0 if where=='before' else 1)
    recovered=TrustedHost(host.repo,host.pins.root,host.grant,host.verifiers.values())
    receipt=recovered.publish(p)
    assert receipt['verification']=='PUBLICATION_COMMITTED'
    assert recovered.publish(p)==receipt and host.repo.state()['epoch']==1
    assert resolve_v2(host.repo,r['facts'],'query:recovered',utc_now())[1][0][0]['core_verdict']=='APPLY'


def test_replay_from_fresh_host_returns_original_immutable_receipt(host):
    c,r,p=ready(host);receipt=host.publish(p)
    other=TrustedHost(host.repo,host.pins.root,host.grant,host.verifiers.values())
    assert other.publish(p)==receipt
    assert other.repo.transport.query('MATCH(n:SourceVerification) WHERE n.id=$id RETURN count(n)',{'id':receipt['id']})==[[1]]


def test_request_digest_conflict_and_original_prepare_replay(host):
    c,r,p=ready(host);head=host.head(c['id']);epoch=host.repo.state()['epoch']
    receipt=host.publish(p)
    assert host.prepare(c['id'],r['id'],request_key='principle',expected_head=digest(head),expected_epoch=epoch)==p
    with pytest.raises(V2Error,match='IMMUTABLE_CONFLICT'):
        host.prepare(c['id'],r['id'],request_key='principle',expected_head='0'*64,expected_epoch=epoch)
    assert host.publish(p)==receipt


def test_extra_counter_edge_injected_at_fence_is_rejected(host):
    c,r,p=ready(host);root=host.repo.node(p.identifier);doc=host.repo.load_document(root)
    original=host.repo.transport.query;injected=[]
    rev=next(n for n in doc['nodes'].values() if n['kind']=='ExperienceRevision')
    ev=next(n for n in doc['nodes'].values() if n['kind']=='Evidence')
    # Actual DB damage occurs AFTER final Python validation and immediately
    # BEFORE the single commit query. The query's full incident-edge fence
    # must still catch it; a list of only known edge IDs would miss it.
    extra=edge(host.repo.tenant,'COUNTEREXAMPLE',rev,ev)
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not injected:
            injected.append(True);host.repo.put_edge(extra)
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p)
    assert host.repo.state()['epoch']==0


def test_single_query_observer_never_sees_partial_catalogue_commit(host):
    c,r,p=ready(host);root=host.repo.node(p.identifier);doc=host.repo.load_document(root)
    observations=[]
    statement='MATCH(s:TenantState {id:$s}),(h:LifecycleHead {id:$h}) OPTIONAL MATCH(s)-[c:COMMITS]->() RETURN properties(s),properties(h),count(c)'
    params=dict(s=host.repo.state_id,h=host.head(c['id'])['id'])
    def sample():
        row=host.repo.transport.query(statement,params)[0]
        state,head=decode(row[0],host.repo.tenant),decode(row[1],host.repo.tenant)
        observations.append((state['epoch'],head['state'],row[2],state['discovery_heads']))
    sample()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(host.publish,p)
        for _ in range(40):sample()
        future.result()
    sample()
    assert any(x[0]==0 for x in observations) and any(x[0]==1 for x in observations)
    for epoch,status,count,heads in observations:
        assert (epoch,status,count,heads) in [(0,'PUBLISHING',0,{}),(1,'PUBLISHED',1,doc['new_state']['discovery_heads'])]


def test_stale_epoch_from_another_real_publication_conflicts_and_recovers(host):
    c1,r1,p1=ready(host,'pending')
    c2,r2,p2=ready(host,'other');host.publish(p2)
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p1)
    newer=host.prepare(c1['id'],r1['id'],request_key='retry-after-epoch',expected_head=digest(host.head(c1['id'])),expected_epoch=1)
    host.publish(newer)
    state,rows=resolve_v2(host.repo,r1['facts'],'query:epoch-recovered',utc_now())
    assert state['epoch']==2 and len(rows)==2


def test_extra_chunk_inserted_after_python_check_fails_final_fence(host):
    c,r,p=ready(host);root=host.repo.node(p.identifier)
    original=host.repo.transport.query;once=[]
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not once:
            once.append(True)
            ch=record(host.repo.tenant,'SnapshotChunk','injected-chunk',document_id=root['id'],chunk_index=99,text='{}',chunk_sha256=hashlib.sha256(b'{}').hexdigest())
            host.repo.put_node(ch);host.repo.put_edge(edge(host.repo.tenant,'HAS_CHUNK',root,ch))
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p)
    assert host.repo.state()['epoch']==0


def test_actual_verifier_revocation_between_check_and_commit_blocks_activation(host):
    c1,r1,p1=ready(host,'already-published');host.publish(p1)
    c2,r2,p2=ready(host,'pending')
    withdrawal=host.prepare_authority_withdrawal(host.verifier.authority_id,reason='Verifier revoked at the commit race window',request_key='race-revoke',expected_epoch=1)
    original=host.repo.transport.query;once=[]
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not once:
            once.append(True);host.commit_authority_withdrawal(withdrawal)
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p2)
    state,rows=resolve_v2(host.repo,r1['facts'],'query:after-race',utc_now())
    assert state['epoch']==2 and state['authz_epoch']==1 and len(rows)==1
    assert rows[0][0]['core_verdict']!='APPLY'


def test_unused_verifier_can_be_revoked_before_first_publication(host):
    c,r,p=ready(host)
    withdrawal=host.prepare_authority_withdrawal(host.verifier.authority_id,reason='Revoke unused verifier before its first publish',request_key='unused-revoke',expected_epoch=0)
    receipt=host.commit_authority_withdrawal(withdrawal)
    assert receipt['affected_experience_ids']==[]
    assert host.repo.state()['revoked_authorities']==[host.verifier.authority_id]
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.publish(p)
    assert host.repo.discover({},host.repo.state())==[]
