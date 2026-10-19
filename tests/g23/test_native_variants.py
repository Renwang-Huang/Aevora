"""Synthetic contracts for two observed official 0.162.1 event variants."""
from copy import deepcopy
import pytest
from tests.test_native_rollout_trace import fixture,analyze,row,item

def legacy():
    old=fixture();lead=[deepcopy(old['lead'][0]),deepcopy(old['lead'][1])];lead[0]['payload']['agent_path']=None
    files={'lead':lead}
    for n in range(1,3):
        child=f'child-{n}';turn=f'{child}-turn';prompt=f'Independently inspect module {n}; return actual commands.'
        lead.append(item('lead','lead-turn',dict(type='CollabAgentToolCall',id=f'spawn-{n}',tool='spawn_agent',status='completed',sender_thread_id='lead',receiver_thread_ids=[child],prompt=prompt,agents_states={child:'pending_init'})))
        rows=[deepcopy(r) for r in old[child] if r['type']!='inter_agent_communication_metadata' and r['payload'].get('type')!='agent_message']
        rows[0]['payload']['agent_path']=None;rows[0]['payload']['source']['subagent']['thread_spawn']['agent_path']=None
        ownstart=next(i for i,r in enumerate(rows) if r['payload'].get('type')=='task_started' and r['payload'].get('turn_id')==turn)
        rows.insert(ownstart+1,row('response_item',dict(type='message',role='user',content=[dict(type='input_text',text=prompt)],internal_chat_message_metadata_passthrough=dict(turn_id=turn))))
        files[child]=rows
        lead.append(item('lead','lead-turn',dict(type='CollabAgentToolCall',id=f'wait-{n}',tool='wait',status='completed',sender_thread_id='lead',receiver_thread_ids=[child],agents_states={child:{'completed':f'Actual findings for {child}'}}),second=8))
    return files

def test_official_legacy_typed_spawn_task_and_completed_receipt(tmp_path):
    s=analyze(tmp_path,legacy())['summary'];assert s['subagents']['verified_count']==2
    assert s['subagents']['task_plaintext_count']==2
    assert all(a['agent_path']=='UNAVAILABLE' for a in s['subagents']['agents'])

@pytest.mark.parametrize('damage',['sender','prompt','turn','receipt','completion','final','metadata_parent','inherited_only'])
def test_legacy_chain_cannot_be_inferred_or_completed_by_prose(tmp_path,damage):
    files=legacy()
    if damage=='sender':files['lead'][2]['payload']['item']['sender_thread_id']='forged-parent'
    if damage=='prompt':
        for r in files['child-1']:
            if r['payload'].get('role')=='user' and r['payload'].get('internal_chat_message_metadata_passthrough'):
                r['payload']['content'][0]['text']='I claim the parent assigned me this task'
    if damage=='turn':
        for r in files['child-1']:
            if r['payload'].get('role')=='user' and r['payload'].get('internal_chat_message_metadata_passthrough'):
                r['payload']['internal_chat_message_metadata_passthrough']['turn_id']='lead-turn'
    if damage=='receipt':files['lead'][3]['payload']['item']['agents_states']['child-1']['completed']+=' '
    if damage=='completion':files['child-1']=[r for r in files['child-1'] if r['payload'].get('type')!='task_complete']
    if damage=='final':files['child-1']=[r for r in files['child-1'] if r['payload'].get('role')!='assistant']
    if damage=='metadata_parent':files['child-1'][0]['payload']['source']['subagent']['thread_spawn']['parent_thread_id']='forged'
    if damage=='inherited_only':
        files['child-1']=[r for r in files['child-1'] if not r['payload'].get('internal_chat_message_metadata_passthrough')]
    s=analyze(tmp_path,files)['summary'];assert s['subagents']['verified_count']<2

def test_root_terminal_needs_exact_own_final_and_completion(tmp_path):
    files=legacy();files['lead'] += [row('response_item',dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='Final exact answer\n')])),row('event_msg',dict(type='task_complete',turn_id='lead-turn',last_agent_message='Final exact answer\n'))]
    assert analyze(tmp_path,files)['summary']['root_terminal']['completed']

@pytest.mark.parametrize('damage',['error','text','turn'])
def test_root_cannot_be_completed_by_exit_metadata_or_nearby_final(tmp_path,damage):
    files=legacy();files['lead'] += [row('response_item',dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='exact')])),row('event_msg',dict(type='task_complete',turn_id='lead-turn',last_agent_message='exact'))]
    if damage=='error':files['lead'][-1]['payload']['error']={'message':'provider failed'}
    if damage=='text':files['lead'][-1]['payload']['last_agent_message']='exact '
    if damage=='turn':files['lead'][-1]['payload']['turn_id']='other-turn'
    assert not analyze(tmp_path,files)['summary']['root_terminal']['completed']
