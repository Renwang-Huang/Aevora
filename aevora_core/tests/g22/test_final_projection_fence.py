"""Fault injection after Host verification; native graph projections are facts."""
import pytest
from aevora.contracts import *
from tools.validation.g22_fixture import ready


def test_final_fence_rejects_typed_label_changed_after_host_check(host):
    c,r,p=ready(host);root=host.repo.node(p.identifier);doc=host.repo.load_document(root)
    revision=next(n for n in doc['nodes'].values() if n['kind']=='ExperienceRevision')
    original=host.repo.transport.query;once=[]
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not once:
            once.append(True)
            original('MATCH(n:ExperienceRevision {id:$id}) REMOVE n:ExperienceRevision SET n:Task',dict(id=revision['id']),read_only=False)
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p)
    assert host.repo.state()['epoch']==0


def test_final_fence_rejects_relationship_type_changed_after_host_check(host):
    c,r,p=ready(host);first=host.publish(p)
    new=host.govern(c['id'],r['id'],experience_id=first['experience_id'],target_id=host.repo.load_document(host.repo.node(p.identifier))['nodes'][next(i for i,n in host.repo.load_document(host.repo.node(p.identifier))['nodes'].items() if n['kind']=='Evidence')]['id'],event_type='withdraw',bounded_scope=r['approved_scope'],reason='Withdraw evidence',request_key='govern')
    doc=host.repo.load_document(host.repo.node(new.identifier))
    supported=next(e for e in doc['prior_edges'].values() if e['kind']=='SUPPORTED_BY')
    original=host.repo.transport.query;once=[]
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not once:
            once.append(True)
            common=','.join(k+':$row.'+k for k in sorted(COMMON|{'payload_json','payload_sha256'}))
            original('MATCH(a)-[old:SUPPORTED_BY {id:$id}]->(b) CREATE(a)-[changed:COUNTEREXAMPLE {'+common+'}]->(b) SET changed += $row DELETE old',dict(id=supported['id'],row=native(supported)),read_only=False)
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(new)
    assert host.repo.state()['epoch']==1


def test_final_fence_rechecks_existing_scope_entries_before_catalogue_refresh(host):
    c1,r1,p1=ready(host,'old-scope-entry');first=host.publish(p1)
    c2,r2,p2=ready(host,'new-scope-entry')
    old=host.repo.node(first['experience_id']);changed={**old,'scope_token':'foreign-partition'}
    original=host.repo.transport.query;once=[]
    def query(statement,*args,**kwargs):
        if 'SET s=$new_state RETURN s.payload_sha256' in statement and not once:
            once.append(True)
            original('MATCH(n:Experience {id:$id}) SET n=$p',dict(id=old['id'],p=native(changed)),read_only=False)
        return original(statement,*args,**kwargs)
    host.repo.transport.query=query
    with pytest.raises(V2Error,match='CONFLICT'):host.publish(p2)
    assert host.repo.state()['epoch']==1
