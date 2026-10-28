"""Bounded PUBLIC views from authoritative Core or independently pinned replay."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from ._hero_verify import verify,read,strict_json
from ._public_projection import project,decision_view

CONTEXTS={
 'threads':{'concurrency_scope':'single_process_threads','shared_state_kind':'sqlite_file','synchronization_scope':'shared_process_object','transaction_guarantees':'sqlite_atomic_write_transactions','worker_count_known':True},
 'workers':{'concurrency_scope':'independent_processes','shared_state_kind':'sqlite_file','synchronization_scope':'per_process','transaction_guarantees':'sqlite_atomic_write_transactions','worker_count_known':True},
 'unknown':{'shared_state_kind':'sqlite_file','concurrency_scope':None,'synchronization_scope':None},
}


def now():return datetime.now(timezone.utc).isoformat()


def focus(graph,identity,max_nodes=64):
    if identity is None:
        chosen=graph['nodes'][:max_nodes];ids={n['id'] for n in chosen}
    else:
        if identity not in {n['id'] for n in graph['nodes']}:return {'nodes':[],'edges':[],'status':'EMPTY','total_nodes':len(graph['nodes'])}
        ids={identity};front={identity}
        for _ in range(3):
            found={n for e in graph['edges'] if e['source'] in front or e['target'] in front for n in [e['source'],e['target']]}
            new=sorted(found-ids)[:max_nodes-len(ids)];ids.update(new);front=set(new)
            if not front or len(ids)>=max_nodes:break
        chosen=[n for n in graph['nodes'] if n['id'] in ids]
    edges=[e for e in graph['edges'] if e['source'] in ids and e['target'] in ids]
    return {'nodes':chosen,'edges':edges,'status':'PARTIAL' if len(chosen)<len(graph['nodes']) else 'AVAILABLE',
            'total_nodes':len(graph['nodes']),'total_edges':len(graph['edges']),'node_limit':max_nodes,
            'disclosure':'Actual bounded subgraph, no invented nodes/edges. Layout is presentation only.'}


class ReplayReader:
    def __init__(self,root,pin):self.root=Path(root);self.pin=pin;verify(self.root,pin)

    def load(self):
        verify(self.root,self.pin) # fail closed if a loaded archive changes
        c=strict_json(read(self.root,'hero_scenario_contract.json'))
        data={k:strict_json(read(self.root,v['artifact_path'])) for k,v in c['artifacts'].items()}
        return c,data

    def overview(self,case,experience=None,stage='before'):
        contract,data=self.load();act=next(x for x in contract['acts'] if x['case_id']==case)
        origin=data['origin'];readback=data['readback'];pilot=data['pilot'];graph=data['graph'];life=data['lifecycle']
        sessions=[{'run_id':origin['run_id'],'session_id':origin['session_id'],'status':origin['runtime_status'],'evaluation_status':'PASS','authority':'VERIFIED_WITHIN_RECORDED_SCOPE','started_at':origin['started_at'],'ended_at':origin['ended_at'],'native_children':origin['children'],'source_commit':origin['source_commit']},
            {'run_id':readback['run_id'],'session_id':readback['thread_id'],'status':readback['runtime_result'],'failure_kind':readback['failure_kind'],'evaluation_status':readback['evaluation'],'observation_status':readback['status'],'authority':'SUPPORTING'},
            *[{'run_id':p['run_id'],'session_id':p['session_id'],'status':'PASS','evaluation_status':'EXTERNAL_UNVERIFIED','authority':'EXTERNAL_UNVERIFIED','public_tests':p['passed']} for p in [pilot['governance'],pilot['raw_memory']]],
            {'run_id':pilot['failed_attempt_run_id'],'session_id':None,'status':'ERROR','failure_kind':pilot['failed_attempt_status'],'authority':'EXTERNAL_UNVERIFIED','evaluation_status':'NOT_EXECUTED'}]
        decisions=[]
        for context,rows in data['views'].items():
            decisions.extend({**row,'context_name':context,'authority':'AUTHORITATIVE_CORE_READ_ONLY_VIEW'} for row in rows)
        if case=='case-c':
            ev=data['evolution'];decisions=[{**ev[k],'context_name':k,'authority':'MAINTAINER_CONTROLLED_ABLATION'} for k in ['before','after','restored']]
            graph=ev['after_graph'] if stage=='after' else ev['before_graph']
        experiences=[n['public'] for n in data['graph']['nodes'] if n['label']=='Experience']
        selected=experience or act['experience_id']
        decisions=[d for d in decisions if d['experience_id']==selected]
        outcomes=[n['public'] for n in data['graph']['nodes'] if n['label']=='VerifiedOutcome']
        return {'mode':'REPLAY','visibility':'PUBLIC','captured_at':contract['captured_at'],'archive':contract['source_archive'],'contract_sha256':self.pin,
            'status':'AVAILABLE','case':act,'sessions':sessions,'decisions':decisions,'experiences':experiences,
            'graph':focus(graph,selected),'lifecycle':life if case=='case-a' else None,
            'timeline':life['events'] if case=='case-a' else ([{'id':q['id'],'event_type':q['operation'],'created_at':q['started_at'],'cypher':q['cypher'],'line':q['line'],'line_sha256':q['line_sha256'],'authority':'MAINTAINER_CONTROLLED_ABLATION'} for q in data['queries']['queries']] if case=='case-c' else []),
            'outcomes':{'trusted':outcomes,'external':pilot,'authority_policy':'External observations are never VerifiedOutcome'},
            'evolution':data['evolution'] if case=='case-c' else None,'evolution_stage':stage if case=='case-c' else None,'comparison':pilot,'claims':contract['claims'],
            'sources':contract['artifacts'],'health':{'database':'NOT_PROBED_REPLAY','mcp':'NOT_PROBED_REPLAY','live_fallback':False},
            'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN','ordering':'Original per-source order; no inferred total cross-stream causality'}

    def proof(self,name):
        contract,data=self.load()
        if name=='contract':return contract
        if name not in data:raise KeyError('Unknown PUBLIC artifact')
        return {'mode':'REPLAY','visibility':'PUBLIC','source':contract['artifacts'][name],'data':data[name]}


def activity(root):
    """Only typed status/metadata headers; no raw MCP/model/private file data."""
    if root is None:return []
    base=Path(root).absolute();result=[]
    if base.is_symlink():raise ValueError('Linked activity root')
    for run in sorted(base.glob('g*/native/*/runs/*')):
        if not run.is_dir() or run.is_symlink():continue
        rel=str(run.relative_to(base));p=run/'runtime_metadata.json'
        if p.exists():
            member=rel+'/runtime_metadata.json';raw=read(base,member);data=strict_json(raw);keys='run_id session_id thread_id runtime_result failure_kind started_at ended_at elapsed_seconds fresh_session model exit_code'.split()
            row={k:data[k] for k in keys if k in data};row['status']=data.get('runtime_result','UNAVAILABLE')
        elif (run/'runtime_status.json').exists():
            member=rel+'/runtime_status.json';raw=read(base,member);data=strict_json(raw);keys='run_id status failure_kind started_at observed_at evidence_status'.split();row={k:data[k] for k in keys if k in data};row['session_id']=None
        else:continue
        row.update(source='TRUSTED_TYPED_RUNTIME_HEADER',authority='EXTERNAL_UNVERIFIED',source_sha256=sha256(raw).hexdigest(),
                   source_artifact=member,process_liveness='UNAVAILABLE_NOT_PROBED',header_observed_at=row.get('observed_at') or row.get('ended_at') or row.get('started_at'))
        row['tool_events']=[]
        if (run/'aevora_mcp_events.jsonl').is_file():
            log=read(base,rel+'/aevora_mcp_events.jsonl')
            lines=log.splitlines(keepends=True)
            incomplete=len(lines[-1]) if lines and not lines[-1].endswith(b'\n') else 0
            row['event_stream_status']='PARTIAL_INCOMPLETE_TAIL' if incomplete else 'COMPLETE_OBSERVED_PREFIX'
            row['incomplete_tail_bytes']=incomplete
            for line,data in enumerate(lines,1):
                if incomplete and line==len(lines):break
                event=strict_json(data)
                if event.get('category')!='JSONRPC':continue
                message=strict_json(event['raw_json'])
                if message.get('method')=='tools/call':
                    row['tool_events'].append({'tool':message.get('params',{}).get('name') if message.get('params',{}).get('name') in {'resolve_experience','build_evidence_bundle','record_decision','propose_experience'} else 'UNAVAILABLE_NOT_PUBLIC_TOOL_NAME','timestamp':event.get('timestamp'),
                        'source_artifact':rel+'/aevora_mcp_events.jsonl','line':line,'line_sha256':sha256(data).hexdigest(),
                        'authority':'ACTUAL_RUN_SCOPED_MCP_REQUEST; individual child author UNAVAILABLE'})
            row['tool_events']=row['tool_events'][-100:]
        result.append(row)
    return result[:100]


def channel_activity(path):
    """Owned Core channel headers; never infer a Codex Session/Agent identity."""
    if path is None:return []
    path=Path(path).absolute();raw=read(path.parent,path.name);lines=raw.splitlines(keepends=True)
    complete=lines[:-1] if lines and not lines[-1].endswith(b'\n') else lines
    events=[];run_id=None
    for number,line in enumerate(complete,1):
        event=strict_json(line)
        native=event.get('source')=='aevora.native_host' and event.get('schema_version')=='aevora.runtime-event/1'
        if not native and event.get('source')!='aevora.authenticated_mcp_broker':raise ValueError('Not a Core broker event file')
        identity=event.get('run_id')
        if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}',identity):raise ValueError('Invalid owned channel identity')
        if run_id is not None and run_id!=identity:raise ValueError('Mixed channel identity')
        run_id=identity
        if native:
            tool=event.get('category')
            if tool in {'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}:
                events.append({'tool':tool,'timestamp':event.get('timestamp'),'line':number,
                    'line_sha256':sha256(line).hexdigest(),'source_artifact':'OWNER_CONFIGURED_CORE_MCP_LOG',
                    'operation_id':event.get('operation_id'),'operation_state':event.get('state'),
                    'source_kind':'NATIVE_HOST_OPERATION_METADATA'})
            continue
        if event.get('category')!='JSONRPC':continue
        message=strict_json(event['raw_json'])
        if message.get('method')!='tools/call':continue
        tool=message.get('params',{}).get('name')
        events.append({'tool':tool if tool in {'resolve_experience','build_evidence_bundle','record_decision','propose_experience'} else 'UNAVAILABLE_NOT_PUBLIC_TOOL_NAME',
            'timestamp':event.get('timestamp'),'line':number,'line_sha256':sha256(line).hexdigest(),'source_artifact':'OWNER_CONFIGURED_CORE_MCP_LOG',
            'authority':'ACTUAL_CORE_MCP_REQUEST; client/native identity UNAVAILABLE'})
    if not events:return []
    return [{'run_id':run_id,'session_id':None,'status':'MCP_REQUESTS_OBSERVED','source':'ACTUAL_OWNER_CONFIGURED_CORE_CHANNEL',
        'authority':'EXTERNAL_UNVERIFIED','source_sha256':sha256(raw).hexdigest(),'source_artifact':'OWNER_CONFIGURED_CORE_MCP_LOG',
        'header_observed_at':events[-1]['timestamp'],'process_liveness':'UNAVAILABLE_NOT_PROBED','tool_events':events[-100:],
        'event_stream_status':'PARTIAL_INCOMPLETE_TAIL' if len(complete)!=len(lines) else 'COMPLETE_OBSERVED_PREFIX',
        'native_identity':'UNAVAILABLE; a channel request is not native Runtime proof'}]


class LiveReader:
    def __init__(self,activity_root=None,mcp_events=None,session_root=None):
        self.activity_root=activity_root;self.mcp_events=mcp_events;self.session_root=session_root

    def proof(self,candidate):
        """Inspect exactly one current candidate through Core's checked event chain."""
        from aevora.graph_repository import GraphRepository
        from aevora.candidate import CandidateLifecycle
        from .live_graph import BoundedRepository
        repo=BoundedRepository(GraphRepository.from_environment())
        try:
            if repo.get_node('Candidate',candidate) is None:return None
            full=CandidateLifecycle(repo).inspect(candidate)
            if full['candidate']['id']!=candidate or full['head']['candidate_id']!=candidate:
                raise ValueError('Lifecycle identity mismatch')
            return {'mode':'LIVE','visibility':'PUBLIC','status':'AVAILABLE','observed_at':now(),
                'candidate_id':candidate,'fallback':False,
                'source':{'core':'CandidateLifecycle.inspect','graph':repo.graph_name},
                'data':{'candidate':project('Candidate',full['candidate']),
                    'head':project('LifecycleHead',full['head']),
                    'events':[project('CandidateEvent',e) for e in full['events']],
                    'head_sha256':full['head_sha256'],'consistency':full['consistency']}}
        finally:repo.close()

    def runtime_activity(self):
        sessions = activity(self.activity_root) + channel_activity(self.mcp_events)
        if self.session_root and (Path(self.session_root).exists() or Path(self.session_root).is_symlink()):
            from aevora.local_session import current_session
            current = current_session(self.session_root, required=False)
            if current:
                managed = channel_activity(current['events'])
                if any(s['run_id'] != current['run_id'] for s in managed):
                    raise ValueError('Session activity identity mismatch')
                sessions += managed
        merged = {}
        for session in sessions:
            previous = merged.get(session['run_id'], {})
            merged[session['run_id']] = {**previous, **session,
                'tool_events': previous.get('tool_events', []) + session.get('tool_events', [])}
        return list(merged.values())

    def overview(self,case=None,experience=None,context=None,run=None,*,resource='overview',limit=20,offset=0,after=None):
        """Only requested pages and local graph records; no whole-project payload scan."""
        from aevora.graph_repository import GraphRepository
        from .live_view import overview
        repo = GraphRepository.from_environment()
        try:
            return overview(repo, observed_at=now(), runtime=self.runtime_activity, resource=resource,
                            run=run, experience=experience, limit=limit, offset=offset, after=after)
        finally:
            repo.close()
