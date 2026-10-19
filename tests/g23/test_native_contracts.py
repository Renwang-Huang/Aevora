"""Synthetic protocol unit controls, never new Agent/Oracle proof."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from aevora.contracts import PROFILE,V2Error,digest
from aevora_maintainer.native_source import join_proposal
from integrations.codex_agent import CodexConfig

def sample():
    body={'candidate_key':'unit'}
    value=dict(candidate_id='candidate:unit',body_sha256=digest(body),read_scope=dict(protocol_profile=PROFILE,tenant_id='tenant-unit',run_id='unit-run',connection_id='conn-one',session_id='cap-session'))
    item=dict(id='official-call',server='aevora',tool='propose_experience',status='completed',arguments={'proposal':body},result={'structuredContent':value},own_turn_id='own-turn')
    events=[dict(event_type='native.McpToolCall',payload=dict(thread_id='actor-one',event=item,raw_reference={'path':'fixture.jsonl','line':4,'sha256':'a'*64}))]
    request=dict(jsonrpc='2.0',id=3,method='tools/call',params=dict(name='propose_experience',arguments=item['arguments']))
    reply=dict(jsonrpc='2.0',id=3,result={'structuredContent':value})
    broker=[dict(category='JSONRPC',connection_id='conn-one',direction=d,raw_json=json.dumps(msg)) for d,msg in [('PARTICIPANT_TO_OFFICIAL_SDK',request),('OFFICIAL_SDK_TO_PARTICIPANT',reply)]]
    return events,broker,dict(run_id='unit-run',candidate_id='candidate:unit',body_sha256=digest(body),eligible_actors={'actor-one','actor-two'},expected_tenant='tenant-unit')

def test_protocol_exact_actor_connection_body_and_reply_join():
    e,b,kw=sample();m=join_proposal(e,b,**kw)
    assert m[0]['actor_thread_id']=='actor-one' and m[0]['calls'][0]['request_id']==3

@pytest.mark.parametrize('damage',['actor','connection','body','reply','run','candidate','status','profile','only_prose','no_completion','same_body_other_actor'])
def test_source_confusion_is_rejected(damage):
    e,b,kw=sample();i=e[0]['payload']['event']
    if damage=='actor':e[0]['payload']['thread_id']='fake-actor'
    if damage=='connection':i['result']['structuredContent']['read_scope']['connection_id']='other'
    if damage=='body':i['arguments']['proposal']['candidate_key']='changed'
    if damage=='reply':i['result']['structuredContent']['publication']='PUBLISHED'
    if damage=='run':kw['run_id']='other'
    if damage=='candidate':kw['candidate_id']='candidate:other'
    if damage=='status':i['status']='failed'
    if damage=='profile':i['result']['structuredContent']['read_scope']['protocol_profile']='legacy'
    if damage=='only_prose':e[0]['event_type']='agent_message'
    if damage=='no_completion':e=[]
    if damage=='same_body_other_actor':
        e.append(deepcopy(e[0]));e[-1]['payload']['thread_id']='actor-two'
    with pytest.raises(V2Error):join_proposal(e,b,**kw)

def test_same_actor_idempotent_repetition_is_not_two_actors():
    e,b,kw=sample();e.append(deepcopy(e[0]));assert len(join_proposal(e,b,**kw))==2

def test_genuine_coherent_foreign_tenant_reply_cannot_certify_this_host_tenant():
    e,b,kw=sample()
    e[0]['payload']['event']['result']['structuredContent']['read_scope']['tenant_id']='foreign-tenant'
    reply=json.loads(b[1]['raw_json']);reply['result']['structuredContent']['read_scope']['tenant_id']='foreign-tenant'
    b[1]['raw_json']=json.dumps(reply)
    with pytest.raises(V2Error,match='SOURCE_MISMATCH'):join_proposal(e,b,**kw)

@pytest.mark.parametrize('profile,path,enabled',[('invalid',None,False),('aevora.mcp/1.2',Path('/private'),False),(PROFILE,None,True),(PROFILE,Path('/private'),False)])
def test_native_v2_configuration_is_explicit(profile,path,enabled):
    with pytest.raises(ValueError):CodexConfig(Path('/native'),Path('/secret'),provider_id='gateway',model='gpt-5.6-terra',reasoning_effort='max',experience_mode='aevora',enable_experience_proposals=enabled,experience_protocol_profile=profile,experience_v2_bootstrap_path=path)
