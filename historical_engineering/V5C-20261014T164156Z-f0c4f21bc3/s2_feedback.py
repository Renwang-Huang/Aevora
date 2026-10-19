"""Verify actual S2 outcome; distinguish retrieval from explicit new-experience decision."""
from pathlib import Path
import sys,json
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.feedback import ingest_outcome
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'03_feedback/s2_outcome';out.mkdir();r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r)
try:
 s=json.loads((E/'04_live_s2/ORIGINAL_RUN_SUMMARY.json').read_text());run=E/'04_live_s2/runs'/s['run_id']
 anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=E/'source',source_manifest_sha256=sha(E/'source/SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
 write(out/'graph_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 verified=verify_outcome(anchor,'evaluation_report.json');write(out/'verified_outcome_receipt.json',verified)
 feedback=ingest_outcome(r,anchor,'evaluation_report.json');write(out/'trusted_feedback.json',feedback)
 write(out/'graph_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION));r._client.connection.save()
 calls=[json.loads(l) for l in (E/'04_live_s2/mcp_timeline.jsonl').read_text().splitlines()];eid=json.loads((E/'03_feedback/S2_SELECTION.json').read_text())['new_published_experience_id']
 queries=[x for x in calls if x['tool']=='resolve_experience' and not x.get('isError') and any(y['experience_id']==eid for y in x['result']['candidates'])]
 bundles=[x for x in calls if x['tool']=='build_evidence_bundle' and not x.get('isError') and x['arguments'].get('experience_id')==eid]
 decisions=[x for x in calls if x['tool']=='record_decision' and not x.get('isError') and x['arguments'].get('decision',{}).get('experience_id')==eid]
 s1=json.loads((E/'02_live_s1/ORIGINAL_RUN_SUMMARY.json').read_text())
 write(E/'04_live_s2/inheritance_trace.json',{'status':'COMPLETE' if queries and bundles and decisions else 'PARTIAL_RETRIEVAL_WITHOUT_EXPLICIT_NEW_EXPERIENCE_DECISION','new_experience_id':eid,'s1_session_id':s1['session_id'],'s2_session_id':s['session_id'],'fresh_distinct_session':s1['session_id']!=s['session_id'],'s2_run_id':run.name,'new_experience_returned_by_agent_query':len(queries),'new_experience_explicit_bundle_calls':len(bundles),'new_experience_explicit_decision_calls':len(decisions),'query_references':[x['response_reference'] for x in queries],'actual_selected_experience_ids':[x['arguments']['decision']['experience_id'] for x in calls if x['tool']=='record_decision' and not x.get('isError')],'native_exit':s['native_exit'],'independent_outcome':verified['verdict'],'independent_tests':verified['test_count'],'same_template_instance_only':True,'code_strategy_relevant':True,'adoption_of_new_experience':'UNVERIFIED','causal_benefit':'UNKNOWN','no_replacement_or_followup_prompt_to_force_tool_use':True,'at':now()})
 print('S2_STRICT_ORIGINAL_OUTCOME',verified['verdict'],'NEW_INHERITANCE_EXPLICIT',bool(queries and bundles and decisions))
finally:raw.close();r.close()
