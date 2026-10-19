#!/usr/bin/env python3
"""Actual H2 graph migration/test evidence, never a mocked graph backend.

Raw SQL/Cypher results remain trusted-host evidence; Participant snapshots
contain only the repository's allowlisted public projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from contextlib import nullcontext
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2); stream.write("\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause-auto-save",action="store_true",
        help="H2-only temporary test window; original SAVE config restored and explicit SAVE recorded")
    parser.add_argument("operation",choices=["migrate","tests","audit-history"])
    parser.add_argument("output",type=Path)
    parser.add_argument("pytest_arguments",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if os.environ.get("AEVORA_FALKORDB_PORT")!="17679":
        raise SystemExit("Dedicated H2 database on port17679 required")
    output=args.output.absolute(); output.mkdir(mode=0o700,parents=True,exist_ok=False)
    from aevora.graph_repository import GraphRepository
    from aevora.models import SCHEMA_VERSION,QUERY_VERSION,RULE_VERSION
    epoch={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
           for path in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))}
    write(output/'SOURCE_EPOCH.json',{"files_sha256":epoch,"schema_version":SCHEMA_VERSION,
        "query_version":QUERY_VERSION,"rule_version":RULE_VERSION,"recorded_at":datetime.now(timezone.utc).isoformat(),
        "collector_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "maintenance_helper_sha256":hashlib.sha256((ROOT/'scripts/aevora_h2_graph_maintenance.py').read_bytes()).hexdigest(),
        "environment_versions":{"python":sys.version,"sqlite":__import__('sqlite3').sqlite_version,
            **{package:__import__('importlib.metadata',fromlist=['version']).version(package)
               for package in ('falkordb','redis','mcp','pytest')}},
        "classification":"H2_CURRENT_SOURCE; NOT_H1_LIVE_SOURCE"})
    original=GraphRepository.query; lock=threading.Lock(); count=0; total=0
    from falkordb.graph import Graph
    original_copy=Graph.copy; copies=[]
    def observed_copy(graph,clone):
        receipt={'source':graph.name,'destination':clone,'started_at':datetime.now(timezone.utc).isoformat(),
            'before_persistence':graph.client.connection.info('persistence'),'policy':'OBSERVE_ONLY; NO_COPY_RETRY_OR_ASSERTION_CHANGE'}
        try:
            result=original_copy(graph,clone)
            receipt.update(status='RETURNED',actual_destination=result.name)
            return result
        except Exception as error:
            receipt.update(status='ERROR',error_type=type(error).__name__,
                recognized_fork_refusal=str(error)=='GRAPH.COPY failed, could not fork')
            raise
        finally:
            try:
                receipt['after_persistence']=graph.client.connection.info('persistence')
            except Exception as error:
                receipt['after_persistence']={'status':'UNAVAILABLE','error_type':type(error).__name__}
            receipt['ended_at']=datetime.now(timezone.utc).isoformat()
            copies.append(receipt)
    pending_reads={}; snapshot_bindings=[]
    with (output/'trusted_cypher_results.jsonl').open('x') as log:
        def observed(self,statement,params=None,*,read_only=True):
            nonlocal count,total
            started=datetime.now(timezone.utc).isoformat()
            try:
                result=original(self,statement,params,read_only=read_only)
                record={"status":"RETURNED","result":result}
            except Exception as error:
                record={"status":"ERROR","error_type":type(error).__name__}
                raise
            finally:
                record.update(graph_name=self.graph_name,query=statement,params=params or {},read_only=read_only,
                    started_at=started,ended_at=datetime.now(timezone.utc).isoformat(),
                    provenance="ACTUAL_OFFICIAL_FALKORDB_QUERY; TRUSTED_HOST_RAW_NOT_PARTICIPANT_PROJECTION")
                with lock:
                    record['sequence']=count+1
                    encoded=json.dumps(record,sort_keys=True,ensure_ascii=False,allow_nan=False)
                    total+=len(encoded.encode())+1;count+=1
                    if total>128*1024*1024:
                        raise RuntimeError("Query evidence bound exceeded")
                    log.write(encoded+'\n');log.flush()
                    reference={'line':count,'line_sha256':hashlib.sha256((encoded+'\n').encode()).hexdigest()}
                    if read_only:
                        pending_reads.setdefault(self.graph_name,[]).append(reference)
                    if 'MERGE (n:QuerySnapshot ' in statement and record['status']=='RETURNED':
                        payload=json.loads((params or {})['payload'])
                        snapshot_bindings.append({'graph_name':self.graph_name,
                            'snapshot_id':payload['id'],'content_sha256':payload['content_sha256'],
                            'capture_write_reference':reference,
                            'preceding_actual_read_references':pending_reads.pop(self.graph_name,[]),
                            'query_version':payload['content'].get('query_version'),
                            'decision_engine_version':payload['content'].get('decision_engine_version'),
                            'consistency':'MULTI_QUERY_COLLECTION_NOT_ATOMIC; REFERENCES_INCLUDE_PREPARATORY_READS'})
            return result
        GraphRepository.query=observed
        Graph.copy=observed_copy
        try:
            if args.operation=='migrate':
                repository=GraphRepository.from_environment()
                try:
                    before_nodes=repository.query("MATCH(n) RETURN labels(n),n.id,n.payload_sha256 ORDER BY n.id")
                    before_edges=repository.query("MATCH(s)-[r]->(t) RETURN s.id,type(r),r.id,r.payload_sha256,t.id ORDER BY r.id")
                    result=repository.migrate_governance()
                    after_nodes=repository.query("MATCH(n) RETURN labels(n),n.id,n.payload_sha256 ORDER BY n.id")
                    after_edges=repository.query("MATCH(s)-[r]->(t) RETURN s.id,type(r),r.id,r.payload_sha256,t.id ORDER BY r.id")
                    assert all(row in after_nodes for row in before_nodes) and all(row in after_edges for row in before_edges)
                    result.update(old_node_payloads_preserved=True,old_edge_payloads_preserved=True)
                    write(output/'MIGRATION.json',result); code=0
                finally: repository.close()
            elif args.operation=='audit-history':
                from aevora.experience_resolver import ExperienceResolver
                from aevora.historical_import import public_context,ATOMIC_ID,LOCK_ID
                repository=GraphRepository.from_environment()
                try:
                    before=repository.state_fingerprint()
                    contexts={'threads':public_context('single_process_multi_thread'),
                        'workers':public_context('multi_process_shared_sqlite'),'unknown':public_context(None)}
                    contexts['irrelevant_identifier']={**contexts['workers'],'episode_id':'NEBULA-817'}
                    contexts['new_public_contract']={**contexts['workers'],
                        'operation_semantics':'request_lease_authority','authority_model':'lease_token_authority',
                        'authority_validation':None,'clock_domain':'shared_monotonic_query',
                        'supported_operation_set':'order_inventory_and_two_phase_requests',
                        'observed_failure_mode':'request_receipt_order_inventory_inconsistency'}
                    resolver=ExperienceResolver(repository)
                    outputs={key:resolver.resolve(context,persist_snapshots=False) for key,context in contexts.items()}
                    by_id=lambda output:{row['experience_id']:row for row in output['candidates']}
                    expected={'threads':{ATOMIC_ID:'APPLY',LOCK_ID:'APPLY'},
                        'workers':{ATOMIC_ID:'APPLY',LOCK_ID:'ABSTAIN'},
                        'unknown':{ATOMIC_ID:'VERIFY',LOCK_ID:'VERIFY'},
                        'new_public_contract':{ATOMIC_ID:'VERIFY',LOCK_ID:'ABSTAIN'}}
                    for key,decisions in expected.items():
                        assert {identifier:by_id(outputs[key])[identifier]['decision'] for identifier in decisions}==decisions
                    assert [(r['experience_id'],r['decision'],r['reason'],r['retrieval_snapshot_sha256'])
                        for r in outputs['workers']['candidates']]==[(r['experience_id'],r['decision'],r['reason'],r['retrieval_snapshot_sha256'])
                        for r in outputs['irrelevant_identifier']['candidates']]
                    assert by_id(outputs['new_public_contract'])[ATOMIC_ID]['principle_decision']=='APPLY'
                    assert repository.state_fingerprint()==before
                    write(output/'HISTORICAL_EVIDENCE_CURRENT_ENGINE.json',{'status':'PASS',
                        'classification':'CURRENT_ENGINE_REAL_HISTORICAL_PATHS; NOT_NEW_AGENT_RUN; NO_NEW_OUTCOME',
                        'source_evidence':'VERIFIED_H1_STRATEGY_REPLAYS; NATURAL_ORIGIN_AND_MAINTAINER_CONTROL_DISTINCT',
                        'graph_before':before,'graph_after':repository.state_fingerprint(),'outputs':outputs,
                        'as_of_authority':'TRUSTED_HOST_CURRENT_UTC','assertions':expected})
                    code=0
                finally:repository.close()
            else:
                import pytest
                from scripts.aevora_h2_graph_maintenance import paused_auto_save
                arguments=args.pytest_arguments or ['-q','aevora_core/tests']
                with paused_auto_save(output) if args.pause_auto_save else nullcontext():
                    code=pytest.main([*arguments,'--junitxml='+str(output/'JUNIT.xml')])
        finally:
            GraphRepository.query=original
            Graph.copy=original_copy
            write(output/'GRAPH_COPY_OBSERVATIONS.json',{'calls':copies,
                'classification':'ACTUAL_OFFICIAL_SDK_COPY; OBSERVATIONS_DO_NOT_CHANGE_SUCCESS_OR_FAILURE'})
    assert epoch=={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))},'Source changed during acceptance'
    write(output/'QUERY_EVIDENCE_SUMMARY.json',{'official_query_count':count,'raw_bytes':total,
        'exit_code':int(code),'raw_sha256':hashlib.sha256((output/'trusted_cypher_results.jsonl').read_bytes()).hexdigest(),
        'disclosure':'TRUSTED_HOST_FULL; RAW PRIVATE PAYLOADS MUST NOT ENTER PARTICIPANT',
        'synthetic_fixtures':'RULE_CONTRACTS_NOT_NATURAL_AGENT_OR_BUSINESS_SUCCESS'})
    write(output/'QUERY_SNAPSHOT_REFERENCES.json',{'source_epoch_sha256':
        hashlib.sha256((output/'SOURCE_EPOCH.json').read_bytes()).hexdigest(),
        'raw_archive':'trusted_cypher_results.jsonl','snapshots':snapshot_bindings,
        'disclosure':'HOST_ONLY_RAW_QUERY_LINE_REFERENCES; PUBLIC_SNAPSHOT_CONTENT_IS_ALLOWLISTED'})
    return int(code)


if __name__=='__main__':raise SystemExit(main())
