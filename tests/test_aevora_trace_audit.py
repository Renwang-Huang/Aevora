"""Synthetic postprocessing contracts; these are never native runtime evidence."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import uuid

import pytest

from integrations.runtime_evidence import seal_run
from scripts.aevora_trace_audit import TraceAuditError, audit_run, main, verify_run_seal


def timestamp(second):
    return f"2026-10-11T00:00:{second:02d}.000+00:00"


def native(kind, payload, second=0):
    return {"timestamp": timestamp(second), "type": kind, "payload": payload}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def fixture(tmp_path, *, inherited=True, prose_only=False, with_patch=True, with_submission=True,
            outcome_id="outcome:trusted:contract"):
    run = tmp_path / str(uuid.uuid4());run.mkdir()
    query_id = "query:" + run.name + ":contract"
    decision_id = "decision:" + run.name + ":contract"
    query = {"status": "AVAILABLE", "query_id": query_id, "run_id": run.name,
             "candidates": [{"experience_id": "experience:contract", "decision": "VERIFY"}]}
    path = {"relation": "OBSERVED_OUTCOME", "records": {"VerifiedOutcome": {"id": outcome_id,
             "verdict": "PASS", "attribution": "UNKNOWN"}},
            "path": ["experience:contract", "revision:contract", "evidence:contract", outcome_id],
            "edge_types": ["HAS_REVISION", "OBSERVED_OUTCOME", "VERIFIES"]}
    bundle = {"status": "AVAILABLE", "experience_id": "experience:contract",
              "observed_outcome_paths": [path], "attribution": "UNKNOWN"}
    decision = {"status": "RECORDED_UNTRUSTED", "query_id": query_id, "decision_id": decision_id,
                "run_id": run.name, "experience_id": "experience:contract", "trusted_outcome": "NOT_SUBMITTED"}
    messages = []
    for index, (tool, result, second) in enumerate((('resolve_experience',query,4),
            ('build_evidence_bundle',bundle,9),('record_decision',decision,14))):
        request = {"jsonrpc": "2.0", "id": index, "method": "tools/call",
                   "params": {"name": tool, "arguments": {}}}
        response = {"jsonrpc": "2.0", "id": index, "result": {"content": [],
                    "isError": False, "structuredContent": result}}
        for direction, rpc, moment in (("PARTICIPANT_TO_OFFICIAL_SDK", request, second),
                                      ("OFFICIAL_SDK_TO_PARTICIPANT", response, second+1)):
            raw = json.dumps(rpc)+"\n"
            messages.append({"sequence": len(messages)+1, "timestamp": timestamp(moment), "run_id": run.name,
                             "category": "JSONRPC", "connection_id": "contract-connection",
                             "direction": direction, "raw_json": raw,
                             "archived_message_sha256": sha256(raw.encode()).hexdigest()})
    write_rows(run/'aevora_mcp_events.jsonl', messages)
    lead = [native('session_meta', {'id':'lead','session_id':'lead','parent_thread_id':None,'agent_path':'/root'}),
            native('event_msg', {'type':'task_started','turn_id':'lead-turn'})]
    for number, (name, result, second) in enumerate((('resolve_experience',query,5),
            ('build_evidence_bundle',bundle,10),('record_decision',decision,15))):
        identifier = f'call-{number}'
        lead.append(native('response_item',{'type':'function_call','name':'functions.exec',
                            'call_id':identifier,'arguments':'actual code-mode contract'},second-1))
        if prose_only:
            lead.append(native('response_item', {'type':'message','role':'assistant',
                        'content':[{'type':'output_text','text':json.dumps(result)}]},second))
        else:
            lead.append(native('response_item', {'type':'function_call_output','call_id':identifier,
                        'output':'Chunk ID: synthetic\nOutput:\n'+json.dumps(result)},second))
            lead.append(native('event_msg', {'type':'mcp_tool_call_end','turn_id':'lead-turn',
                        'call_id':identifier,'invocation':{'server':'aevora','tool':name,'arguments':{}},
                        'result':{'Ok':{'content':[],'isError':False,'structuredContent':result}}},second))
    if with_patch:
        changes = {'/participant/app/service.py':{'type':'update','unified_diff':'synthetic'}}
        lead.extend([native('event_msg', {'type':'patch_apply_begin','turn_id':'lead-turn',
                        'call_id':'patch-1','changes':changes},19),
                     native('event_msg', {'type':'patch_apply_end','turn_id':'lead-turn',
                        'call_id':'patch-1','changes':changes,'success':True,'status':'completed'},20)])
    lead.extend([native('response_item', {'type':'message','role':'assistant','phase':'final_answer',
                    'content':[{'type':'output_text','text':'Synthetic completed contract'}]},39),
                 native('event_msg', {'type':'task_complete','turn_id':'lead-turn','error':None,
                    'last_agent_message':'Synthetic completed contract'},40)])
    records=[]
    for identifier, values in [('lead',lead)]:
        native_path=run/'artifacts/native_rollouts'/f'{identifier}.jsonl';write_rows(native_path,values)
        records.append({'path':str(native_path),'sha256':sha256(native_path.read_bytes()).hexdigest()})
    if inherited:
        child=[native('session_meta',{'id':'child','session_id':'lead','parent_thread_id':'lead',
                 'agent_path':'/root/child','source':{'subagent':{'thread_spawn':{
                     'parent_thread_id':'lead','agent_path':'/root/child'}}}}),*lead,
               native('event_msg',{'type':'task_started','turn_id':'child-turn',
                   'turn_attribution':{'parent_turn_id':'lead-turn'}},41),
               native('event_msg',{'type':'item_completed','thread_id':'child','turn_id':'child-turn',
                   'item':{'type':'CommandExecution','id':'own-child-command','status':'completed',
                           'command':['true'],'exit_code':0}},42),
               native('event_msg',{'type':'task_complete','turn_id':'child-turn','error':None,
                   'last_agent_message':'Actual own child contract'},43)]
        native_path=run/'artifacts/native_rollouts/child.jsonl';write_rows(native_path,child)
        records.append({'path':str(native_path),'sha256':sha256(native_path.read_bytes()).hexdigest()})
    metadata={'run_id':run.name,'thread_id':'lead','session_id':'lead','ended_at':timestamp(45),
              'native_rollouts':{'files':records},'runtime_result':'PASS'}
    write_json(run/'runtime_metadata.json',metadata)
    write_json(run/'input_seal.json',{'run_id':run.name,'files':{}})
    activity=[]
    if with_patch:
        activity.append({'run_id':run.name,'timestamp':timestamp(21),
                         'event_type':'PATCH_TREE_CHANGE_FIRST_OBSERVED','detail':{'observed_at':timestamp(21)}})
    write_rows(run/'runtime_activity.jsonl',activity)
    receipts=[]
    if with_submission:
        (run/'submission.diff').write_text('Synthetic contract patch; not executable benchmark evidence\n')
        receipts.append({'run_id':run.name,'timestamp':timestamp(30),'event_type':'submission.received',
                         'payload':{'submission':{'sha256':sha256((run/'submission.diff').read_bytes()).hexdigest(),
                                                  'received_at':timestamp(30)}}})
    write_rows(run/'execution_trace.jsonl',receipts)
    seal_run(run)
    return run, query_id, decision_id, outcome_id


def test_real_references_ids_and_timeline_join_only_typed_own_outputs(tmp_path):
    run,query_id,decision_id,outcome=fixture(tmp_path)
    before={p.relative_to(run).as_posix():sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}
    result=audit_run(run,tmp_path/'audit',trusted_outcome_id=outcome)
    assert result['host_tool_count']==result['host_tools_with_typed_native_join']==3
    assert result['native_session_id']=='lead' and result['native_integrity']['status']=='COMPLETE'
    calls=result['tool_calls'];assert calls[0]['query_id']==query_id and calls[2]['decision_id']==decision_id
    for call in calls:
        assert call['native_agent_id']=='lead'
        assert all(match['thread_id']=='lead' for match in call['native_matches'])
        assert call['before_first_host_patch_observation'] is True
        assert call['before_first_successful_patch_request'] is True
        assert call['before_final_submission_receipt'] is True
        for reference in [call['request_reference'],call['response_reference']]:
            raw=Path(reference['path']).read_bytes().splitlines(keepends=True)[reference['line']-1]
            assert sha256(raw).hexdigest()==reference['sha256']
        assert any(match.get('server')=='aevora' for match in call['native_matches'])
        assert call['mental_causality']=='UNVERIFIED'
    assert result['patch_evidence']['first_major_patch']=='UNKNOWN'
    assert result['new_session_outcome_observation']['status']=='OBSERVED_IN_HOST_AND_TYPED_NATIVE_OUTPUT'
    assert result['new_session_outcome_observation']['mental_influence']=='UNVERIFIED'
    after={p.relative_to(run).as_posix():sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}
    assert before==after
    assert (tmp_path/'audit/timeline.jsonl').is_file()


def test_assistant_prose_never_becomes_mcp_use_or_outcome_observation(tmp_path):
    run,_,_,outcome=fixture(tmp_path,prose_only=True)
    result=audit_run(run,tmp_path/'audit',trusted_outcome_id=outcome)
    assert result['host_tools_with_typed_native_join']==0
    assert result['new_session_outcome_observation']['status']=='UNVERIFIED'
    assert all(call['native_agent_id']=='UNKNOWN' for call in result['tool_calls'])


def test_unknown_timestamps_absent_patch_and_no_submission_are_not_invented(tmp_path):
    run,*_=fixture(tmp_path,with_patch=False,with_submission=False)
    result=audit_run(run,tmp_path/'audit')
    assert result['final_submission']=={'status':'NOT_PRODUCED','timestamp':'UNKNOWN'}
    assert result['patch_evidence']['first_host_patch_observation']=='UNKNOWN'
    assert all(call['before_first_host_patch_observation']=='UNKNOWN' for call in result['tool_calls'])
    assert all(call['before_final_submission_receipt']=='UNKNOWN' for call in result['tool_calls'])


@pytest.mark.parametrize('fault',['modified','missing','extra','pending','state','seal_runid','seal_pin','linked_file','linked_parent','input_chain'])
def test_full_seal_gate_refuses_live_changed_or_unsafe_source(tmp_path,fault):
    run,*_=fixture(tmp_path)
    expected=None
    if fault=='modified':(run/'submission.diff').write_text('tampered')
    elif fault=='missing':(run/'submission.diff').unlink()
    elif fault=='extra':(run/'unexpected.json').write_text('{}')
    elif fault=='pending':(run/'codex_events.pending').write_text('{}')
    elif fault=='state':(run/'codex-state').mkdir()
    elif fault=='seal_pin':expected='0'*64
    elif fault=='linked_file':
        (run/'submission.diff').unlink();(run/'submission.diff').symlink_to(tmp_path/'outside')
    elif fault=='linked_parent':
        target=tmp_path/'linked-native';(run/'artifacts/native_rollouts').rename(target)
        (run/'artifacts/native_rollouts').symlink_to(target)
    else:
        seal=json.loads((run/'run_evidence_manifest.json').read_text())
        if fault=='seal_runid':seal['run_id']='foreign'
        else:seal['previous_seal_sha256']='0'*64
        write_json(run/'run_evidence_manifest.json',seal)
    with pytest.raises((TraceAuditError,OSError,ValueError)):
        audit_run(run,tmp_path/'audit',expected_seal_sha256=expected)
    assert not (tmp_path/'audit').exists()


def test_outputs_cannot_mutate_run_even_through_linked_ancestor(tmp_path):
    run,*_=fixture(tmp_path)
    with pytest.raises(TraceAuditError):audit_run(run,run/'audit')
    link=tmp_path/'output-link';link.symlink_to(run)
    with pytest.raises(TraceAuditError):audit_run(run,link/'new-parent'/'audit')
    assert not (run/'new-parent').exists()
    audit_run(run,tmp_path/'audit')
    with pytest.raises(TraceAuditError):audit_run(run,tmp_path/'audit')


def test_expected_outcome_id_needs_actual_path_not_other_outcome_or_prose(tmp_path):
    run,*_=fixture(tmp_path)
    result=audit_run(run,tmp_path/'audit',trusted_outcome_id='outcome:trusted:different')
    assert result['new_session_outcome_observation']['status']=='UNVERIFIED'


def test_missing_native_rollouts_remains_unverified(tmp_path):
    run,*_=fixture(tmp_path)
    metadata=json.loads((run/'runtime_metadata.json').read_text());metadata['native_rollouts']={'files':[]}
    write_json(run/'runtime_metadata.json',metadata);(run/'run_evidence_manifest.json').unlink();seal_run(run)
    result=audit_run(run,tmp_path/'audit')
    assert result['native_integrity']['status']=='INCOMPLETE'
    assert result['host_tools_with_typed_native_join']==0


def test_host_embedded_message_hash_must_match_even_if_outer_seal_is_valid(tmp_path):
    run,*_=fixture(tmp_path)
    rows=[json.loads(x) for x in (run/'aevora_mcp_events.jsonl').read_text().splitlines()]
    rows[0]['archived_message_sha256']='0'*64
    write_rows(run/'aevora_mcp_events.jsonl',rows);(run/'run_evidence_manifest.json').unlink();seal_run(run)
    with pytest.raises(TraceAuditError):audit_run(run,tmp_path/'audit')


def test_cli_requires_final_seal_and_returns_traceable_failure(tmp_path,capsys):
    run=tmp_path/'not-sealed';run.mkdir()
    assert main([str(run),str(tmp_path/'audit')])==2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='ERROR' and result['source_modified'] is False
    assert not (tmp_path/'audit').exists()


def test_full_seal_validates_supplied_pin_and_every_file(tmp_path):
    run,*_=fixture(tmp_path)
    pin=sha256((run/'run_evidence_manifest.json').read_bytes()).hexdigest()
    result=verify_run_seal(run,pin)
    assert result['status']=='VERIFIED' and result['trusted_pin_supplied'] is True
    assert result['checked_files']==len(result['files'])


def test_official_exec_mcp_fields_preserved_without_inventing_event_timestamps(tmp_path):
    run,*_=fixture(tmp_path,prose_only=True)
    host=[json.loads(line) for line in (run/'aevora_mcp_events.jsonl').read_text().splitlines()]
    events=[{'type':'thread.started','thread_id':'lead'},{'type':'turn.started'}]
    for number,event in enumerate(host):
        raw=json.loads(event['raw_json'])
        if 'result' not in raw:continue
        tool=json.loads(host[number-1]['raw_json'])['params']['name']
        events.append({'type':'item.completed','item':{'id':f'exec-mcp-{number}',
                      'type':'mcp_tool_call','server':'aevora','tool':tool,'arguments':{},
                      'result':raw['result'],'error':None,'status':'completed'}})
    events.append({'type':'turn.completed','usage':{'input_tokens':4,'cached_input_tokens':0,'output_tokens':2}})
    write_rows(run/'codex_events.jsonl',events);(run/'run_evidence_manifest.json').unlink();seal_run(run)
    result=audit_run(run,tmp_path/'audit')
    assert result['exec_integrity']['status']=='COMPLETE'
    assert result['host_tools_with_typed_native_join']==3
    for call in result['tool_calls']:
        match=call['native_matches'][0]
        assert match['source']=='codex.exec.typed_mcp_output' and match['server']=='aevora'
        assert match['timestamp']=='UNKNOWN' and match['timestamp_source']=='UNAVAILABLE_IN_EXEC_STREAM'
        assert match['call_id'].startswith('exec-mcp-') and match['thread_id']=='lead'
    assert (tmp_path/'audit/exec_trace_derived.jsonl').is_file()


def test_exec_thread_from_another_session_is_not_correlated(tmp_path):
    run,*_=fixture(tmp_path)
    events=[{'type':'thread.started','thread_id':'foreign'},{'type':'turn.started'},
            {'type':'turn.completed','usage':{'input_tokens':4,'cached_input_tokens':0,'output_tokens':2}}]
    write_rows(run/'codex_events.jsonl',events);(run/'run_evidence_manifest.json').unlink();seal_run(run)
    with pytest.raises(TraceAuditError):audit_run(run,tmp_path/'audit')


def test_empty_structured_response_never_joins_empty_native_objects(tmp_path):
    run,*_=fixture(tmp_path)
    rows=[json.loads(x) for x in (run/'aevora_mcp_events.jsonl').read_text().splitlines()]
    response=json.loads(rows[1]['raw_json']);response['result']={'content':[],'isError':False}
    rows[1]['raw_json']=json.dumps(response)+'\n';rows[1]['archived_message_sha256']=sha256(rows[1]['raw_json'].encode()).hexdigest()
    write_rows(run/'aevora_mcp_events.jsonl',rows);(run/'run_evidence_manifest.json').unlink();seal_run(run)
    result=audit_run(run,tmp_path/'audit')
    assert result['tool_calls'][0]['response_status']=='NO_STRUCTURED_RESULT'
    assert result['tool_calls'][0]['native_matches']==[]


def rewrite_native_metadata(run, update):
    """Reseal synthetic contracts; never touch a historical Run."""
    metadata = json.loads((run / 'runtime_metadata.json').read_text())
    update(metadata)
    write_json(run / 'runtime_metadata.json', metadata)
    (run / 'run_evidence_manifest.json').unlink()
    seal_run(run)
    return metadata


def test_repo_relative_native_paths_project_exact_sealed_files_without_identity_changes(tmp_path, monkeypatch):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path)
    def update(metadata):
        metadata['session_id'] = 'UNAVAILABLE'
        metadata['runtime_result'] = 'ERROR'
        metadata['failure_kind'] = 'NO_PATCH'
        for record in metadata['native_rollouts']['files']:
            record['path'] = Path(record['path']).relative_to(tmp_path).as_posix()
    metadata = rewrite_native_metadata(run, update)
    before = {p.relative_to(run).as_posix():sha256(p.read_bytes()).hexdigest()
              for p in run.rglob('*') if p.is_file()}
    result = audit_run(run, tmp_path / 'audit')
    assert result['native_integrity']['status'] == 'COMPLETE'
    assert result['native_session_id'] == 'lead'
    projection = result['native_metadata_path_projection']
    assert projection['status'] == 'PROJECTED'
    assert projection['original_metadata_sha256'] == before['runtime_metadata.json']
    assert projection['native_parser_source_sha256'] == sha256(Path(module.analyze_native_rollouts.__code__.co_filename).read_bytes()).hexdigest()
    assert projection['postprocessor_source_sha256'] == sha256(Path(module.__file__).read_bytes()).hexdigest()
    assert projection['identities_modified'] is projection['content_modified'] is False
    assert len(projection['mappings']) == len(metadata['native_rollouts']['files'])
    for mapping, original in zip(projection['mappings'], metadata['native_rollouts']['files']):
        assert mapping['before'] == original['path']
        assert mapping['after'] == str(tmp_path / original['path'])
        assert mapping['source_scope'] == 'REPOSITORY_RELATIVE_SEALED_PATH'
        assert mapping['sealed_file_sha256'] == original['sha256']
        assert mapping['changed'] is True and mapping['identity_and_content_modified'] is False
    after = {p.relative_to(run).as_posix():sha256(p.read_bytes()).hexdigest()
             for p in run.rglob('*') if p.is_file()}
    assert before == after
    assert json.loads((run / 'runtime_metadata.json').read_text()) == metadata
    assert metadata['session_id'] == 'UNAVAILABLE' and metadata['failure_kind'] == 'NO_PATCH'


def test_run_relative_native_paths_remain_supported_and_explicit(tmp_path):
    run, *_ = fixture(tmp_path)
    def update(metadata):
        for record in metadata['native_rollouts']['files']:
            record['path'] = Path(record['path']).relative_to(run).as_posix()
    rewrite_native_metadata(run, update)
    result = audit_run(run, tmp_path / 'audit')
    assert result['native_integrity']['status'] == 'COMPLETE'
    assert all(m['source_scope'] == 'RUN_RELATIVE_SEALED_PATH'
               for m in result['native_metadata_path_projection']['mappings'])


def test_native_repo_path_from_other_run_is_rejected_even_when_it_exists(tmp_path, monkeypatch):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path)
    foreign, *_ = fixture(tmp_path)
    foreign_file = foreign / 'artifacts/native_rollouts/lead.jsonl'
    def update(metadata):
        metadata['native_rollouts']['files'][0].update(
            path=foreign_file.relative_to(tmp_path).as_posix(),
            sha256=sha256(foreign_file.read_bytes()).hexdigest())
    rewrite_native_metadata(run, update)
    with pytest.raises(TraceAuditError, match='outside this sealed Run'):
        audit_run(run, tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()


@pytest.mark.parametrize('spelling', ['traversal', 'dot', 'double_slash', 'basename', 'suffix_only'])
def test_native_projection_never_uses_traversal_or_basename_guessing(tmp_path, monkeypatch, spelling):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path)
    target = f'{run.name}/artifacts/native_rollouts/lead.jsonl'
    unsafe = {'traversal':f'{run.name}/../{target}', 'dot':'./' + target,
              'double_slash':target.replace('/artifacts/', '//artifacts/'),
              'basename':'lead.jsonl', 'suffix_only':'native_rollouts/lead.jsonl'}[spelling]
    rewrite_native_metadata(run, lambda metadata: metadata['native_rollouts']['files'][0].update(path=unsafe))
    with pytest.raises((TraceAuditError, ValueError)):
        audit_run(run, tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()


def test_native_record_hash_disagreement_rejected_with_valid_outer_seal(tmp_path, monkeypatch):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path)
    def update(metadata):
        record = metadata['native_rollouts']['files'][0]
        record.update(path=Path(record['path']).relative_to(tmp_path).as_posix(), sha256='0' * 64)
    rewrite_native_metadata(run, update)
    assert verify_run_seal(run)['status'] == 'VERIFIED'
    with pytest.raises(TraceAuditError, match='record hash differs'):
        audit_run(run, tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()


def test_repository_symlink_alias_cannot_rebase_native_metadata(tmp_path, monkeypatch):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path)
    alias = tmp_path / 'alias'; alias.symlink_to(run)
    rewrite_native_metadata(run, lambda metadata: metadata['native_rollouts']['files'][0].update(
        path='alias/artifacts/native_rollouts/lead.jsonl'))
    assert verify_run_seal(run)['status'] == 'VERIFIED'
    with pytest.raises(TraceAuditError):
        audit_run(run, tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()


def test_native_projection_refuses_duplicate_file_under_different_spellings(tmp_path, monkeypatch):
    import scripts.aevora_trace_audit as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    run, *_ = fixture(tmp_path, inherited=False)
    def update(metadata):
        original = metadata['native_rollouts']['files'][0]
        metadata['native_rollouts']['files'].append({**original,
            'path':Path(original['path']).relative_to(tmp_path).as_posix()})
    rewrite_native_metadata(run, update)
    with pytest.raises(TraceAuditError, match='Duplicate native file identity'):
        audit_run(run, tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()
