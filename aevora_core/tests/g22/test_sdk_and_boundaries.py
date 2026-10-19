from datetime import datetime,timezone,timedelta
from dataclasses import replace
from pathlib import Path
import os,json,tempfile,secrets
import pytest
from aevora.contracts import *
from aevora.host_pins import PinMap
from aevora.mcp_v2 import ReadGrant
from aevora.mcp_broker import MCPBroker,MAX_MESSAGE_BYTES
from aevora_core.tests.test_mcp_real_graph import connect,tool,rpc
from aevora_maintainer.host_v2 import TrustedHost
from tools.validation.g22_fixture import ready,admitted,proposal


def sdk(host,facts,tmp_path,monkeypatch,generation='one'):
    root=Path(os.environ.get('AEVORA_G22_ARTIFACT_ROOT',tmp_path))/'sdk'/host.repo.binding.graph_name/generation
    root.mkdir(parents=True)
    monkeypatch.setenv('AEVORA_FALKORDB_GRAPH',host.repo.binding.graph_name)
    grant=ReadGrant(host.repo.tenant,'g22-sdk-run','fresh-session-'+generation,generation,
                    (datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(),authz_epoch=host.repo.state()['authz_epoch'])
    host.repo.put_node(record(host.repo.tenant,'Session',[grant.run_id,grant.session_id,grant.generation],
        run_id=grant.run_id,session_id=grant.session_id,grant_generation=grant.generation,
        profile=PROFILE,state='ACTIVE',valid_until=grant.valid_until))
    cfg=root/'HOST_CONFIG.json';cfg.write_text(canonical_json(dict(binding=host.repo.binding.__dict__,registry={'pin_root':str(host.pins.root)},facts=facts,grant=grant.__dict__)));cfg.chmod(0o600)
    token=secrets.token_hex(32);sock=Path(tempfile.mkdtemp(prefix='g22sdk-'))/'m.sock'
    b=MCPBroker(run_id=grant.run_id,public_context={},socket_path=sock,run_token=token,
                event_path=root/'events.jsonl',server_environment={'AEVORA_V2_QUERY_AUDIT':str(root/'RAW_CYPHER.jsonl')},
                enable_proposals=True,protocol_profile=PROFILE,v2_config_path=str(cfg))
    return b,token


def test_real_official_sdk_reads_host_pins_and_fresh_reissued_grant(host,tmp_path,monkeypatch):
    c,r,p=ready(host);receipt=host.publish(p)
    b,t=sdk(host,r['facts'],tmp_path,monkeypatch)
    with b:
        conn,stream=connect(b,t)
        try:
            names={x['name'] for x in rpc(conn,stream,2,'tools/list')['tools']}
            assert names=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}
            q=tool(conn,stream,4,'resolve_experience',{'task_context':{}})
            assert not q['isError'];q=q['structuredContent'];rec=q['recommendations'][0]
            assert rec['core_verdict']=='APPLY'
            original=tool(conn,stream,5,'build_evidence_bundle',dict(query_id=q['query_id'],experience_id=rec['experience_id'],view='recommendation'))
            assert not original['isError']
            prepared=host.prepare_authority_withdrawal(host.verifier.authority_id,reason='Actual verifier withdrawal during read session',request_key='sdk-withdraw',expected_epoch=1)
            host.commit_authority_withdrawal(prepared)
            conn.sendall((json.dumps(dict(jsonrpc='2.0',id=6,method='tools/call',params=dict(name='build_evidence_bundle',arguments=dict(query_id=q['query_id'],experience_id=rec['experience_id'],view='recommendation'))))+'\n').encode())
            try:
                raw=stream.readline();assert not raw or json.loads(raw).get('result',{}).get('isError') is True
            except ConnectionResetError:pass
        finally:stream.close();conn.close()
    b2,t2=sdk(host,r['facts'],tmp_path,monkeypatch,generation='two')
    with b2:
        conn,stream=connect(b2,t2)
        try:
            q2=tool(conn,stream,2,'resolve_experience',{'task_context':{}})
            assert not q2['isError'] and q2['structuredContent']['recommendations'][0]['core_verdict']!='APPLY'
        finally:stream.close();conn.close()
    assert b.metadata['handler_cleanup_complete'] and b2.metadata['handler_cleanup_complete']
    events=[json.loads(line) for line in b.event_path.read_text().splitlines()]
    assert any(e['category']=='V2_RESPONSE_DELIVERED' for e in events)
    assert max(e.get('delivered_bytes',0) for e in events)<=MAX_MESSAGE_BYTES


def test_host_registry_symlink_and_permissions_rejected(host,tmp_path):
    name=digest(['authorities',host.verifier.authority_id])+'.json';p=host.pins.root/name
    p.chmod(0o644)
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.repo.registry.authorities.get(host.verifier.authority_id)
    p.chmod(0o600)
    fake=tmp_path/'alias';fake.symlink_to(host.pins.root,target_is_directory=True)
    with pytest.raises(OSError):PinMap(fake,'authorities').get(host.verifier.authority_id)


def test_registered_verifier_expired_and_future_windows_rejected(host):
    # Mutated source is still rejected before any verified Outcome. The
    # immutable Host pin prevents rewriting an active registered Authority.
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    a=host.repo.node(host.verifier.authority_id)
    for start,end in [('2020-01-01T00:00:00Z','2020-01-02T00:00:00Z'),('2099-01-01T00:00:00Z','2099-01-02T00:00:00Z')]:
        changed={**a,'valid_from':start,'valid_until':end}
        host.repo.transport.query('MATCH(n:Authority {id:$id}) SET n=$p',dict(id=a['id'],p=native(changed)),read_only=False)
        with pytest.raises(V2Error,match='UNAUTHORIZED'):host.verify_source(c['id'],a['id'],'evaluation_report.json')
    assert host.repo.transport.query('MATCH(n:VerifiedOutcome) RETURN count(n)')==[[0]]


@pytest.mark.parametrize('denied',['publish','verify_outcome','review','govern'])
def test_public_broker_closes_unauthorized_host_tool_without_effect(host,tmp_path,monkeypatch,denied):
    c,r,p=ready(host);host.publish(p);before=host.repo.state()
    b,t=sdk(host,r['facts'],tmp_path,monkeypatch)
    with b:
        conn,stream=connect(b,t)
        try:
            msg=dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name='__host_'+denied,arguments={}))
            conn.sendall((json.dumps(msg)+'\n').encode())
            raw=stream.readline()
            assert raw==b'', 'Unauthorized Host tool must be rejected by the allowlist before official SDK dispatch'
        finally:stream.close();conn.close()
    assert host.repo.state()==before
    events=[json.loads(line) for line in b.event_path.read_text().splitlines()]
    assert not any(e.get('direction')=='PARTICIPANT_TO_OFFICIAL_SDK' and denied in e.get('raw_json','') for e in events)


def test_real_host_withdrawal_after_sdk_result_before_broker_send_is_denied(host,tmp_path,monkeypatch):
    c,r,p=ready(host);host.publish(p)
    prepared=host.prepare_authority_withdrawal(host.verifier.authority_id,reason='Revoke between real SDK completion and final broker check',request_key='presend-withdrawal',expected_epoch=1)
    b,t=sdk(host,r['facts'],tmp_path,monkeypatch);original=b._event;trigger=[]
    def event(category,connection_id=None,**kwargs):
        original(category,connection_id,**kwargs)
        raw=kwargs.get('raw')
        if category=='JSONRPC' and kwargs.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and raw:
            msg=json.loads(raw)
            if msg.get('id')==2 and msg.get('result',{}).get('structuredContent',{}).get('recommendations') and not trigger:
                trigger.append(True);host.commit_authority_withdrawal(prepared)
    b._event=event
    with b:
        conn,stream=connect(b,t)
        try:
            conn.sendall((json.dumps(dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name='resolve_experience',arguments={'task_context':{}})))+'\n').encode())
            assert stream.readline()==b''
        finally:stream.close();conn.close()
    assert trigger and host.repo.state()['authz_epoch']==1
    events=[json.loads(line) for line in b.event_path.read_text().splitlines()]
    # Official computation is preserved, but no such successful response was delivered.
    assert any(e['category']=='JSONRPC' and e.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and json.loads(e['raw_json']).get('id')==2 for e in events)
    denied_frames={hashlib.sha256(e['raw_json'].encode()).hexdigest() for e in events if e['category']=='JSONRPC' and e.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and json.loads(e['raw_json']).get('id')==2}
    assert not any(e['category']=='V2_RESPONSE_DELIVERED' and e.get('delivered_sha256') in denied_frames for e in events)
