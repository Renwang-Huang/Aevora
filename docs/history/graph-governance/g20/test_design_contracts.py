"""G20 design-only checks. No product/graph/model/Oracle execution.
These are contract artifact tests, not Gen2 functionality or inherited regression.
"""
from pathlib import Path
import copy,csv,hashlib,json,re,datetime
import pytest
from jsonschema import Draft202012Validator,FormatChecker
D=Path(__file__).resolve().parent;K=D/'contracts'
def load(p):return json.loads(p.read_text())
def formats():
 checker=FormatChecker()
 @checker.checks('date-time')
 def aware_timestamp(value):
  if not isinstance(value,str):return True
  try:
   parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
   return parsed.tzinfo is not None and 'T' in value
  except ValueError:return False
 return checker
SCHEMAS=sorted(p for p in K.glob('*.schema.json'))
EX=load(K/'examples.json')
@pytest.mark.parametrize('path',SCHEMAS,ids=lambda p:p.name)
def test_json_schema_is_valid(path):Draft202012Validator.check_schema(load(path))
@pytest.mark.parametrize('case',EX['positive'],ids=lambda c:c['name'])
def test_positive_synthetic_protocol_shape(case):Draft202012Validator(load(K/case['schema']),format_checker=formats()).validate(case['value'])
@pytest.mark.parametrize('case',EX['negative'],ids=lambda c:c['name'])
def test_negative_synthetic_protocol_shape_is_rejected(case):
 assert list(Draft202012Validator(load(K/case['schema']),format_checker=formats()).iter_errors(case['value']))
def test_four_tool_names_and_legacy_real_snapshot():
 current=load(K/'mcp_v2.schema.json');legacy=load(K/'legacy_mcp_v1_2.schemas.json')
 expected={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}
 assert set(current['$defs'])==expected
 assert {x['name'] for x in legacy['tools']}==expected
 resolve=next(t for t in legacy['tools'] if t['name']=='resolve_experience')
 assert set(resolve['inputSchema']['properties'])=={'task_context','cursor'}
 assert len(resolve['inputSchema']['properties']['task_context']['properties'])==8
 assert legacy['status']=='SCHEMA_EXTRACTION_ONLY_NO_TOOL_EXECUTION'
def test_apply_requires_complete_nonempty_evidence_not_a_high_score():
 s=load(K/'recommendation.schema.json');base=copy.deepcopy(EX['positive'][1]['value']);base.update(core_verdict='APPLY',unknown_required=[],verification_steps=[])
 val=Draft202012Validator(s);val.validate(base)
 for key,value in [('witness_refs',[]),('revision_ids',[]),('required_fact_count',0),('integrity_issues',['missing-edge']),('contradiction_ids',['conflict']),('completeness','INCOMPLETE')]:
  d=copy.deepcopy(base);d[key]=value;assert list(val.iter_errors(d)),key
 assert 'confidence_score' not in s['properties']
def test_verify_may_describe_an_incomplete_rule_without_inventing_ids():
 d=copy.deepcopy(EX['positive'][1]['value']);d.update(revision_ids=[],required_fact_count=0,completeness='INCOMPLETE',integrity_issues=['missing-rule'])
 Draft202012Validator(load(K/'recommendation.schema.json')).validate(d)
def test_rejection_does_not_require_fabricated_source_verification():
 val=Draft202012Validator(load(K/'host_review.schema.json'))
 body={'contract_version':'aevora.host.review/2.0.0-rc1','candidate_id':'candidate:synthetic','expected_head_sha256':'a'*64,'expected_semantic_epoch':0,'idempotency_key':'review-1','action':'REJECTED','reason':'Independent evidence is missing.'}
 val.validate(body);body['action']='ADMITTED_BOUNDED';assert list(val.iter_errors(body))
def test_postcondition_cannot_be_required_task_premise():
 d=copy.deepcopy(next(x for x in EX['positive'] if x['name']=='untrusted-proposal')['value']['arguments']);d['proposal']['necessary_conditions']={'artifact_after.authority_validation':['confirmed']}
 assert list(Draft202012Validator(load(K/'propose_experience.arguments.schema.json')).iter_errors(d))
def test_unknown_fact_cannot_gain_a_value_and_timestamp_is_strict():
 val=Draft202012Validator(load(K/'fact.schema.json'),format_checker=formats());d=copy.deepcopy(EX['positive'][0]['value']);d['availability']='UNKNOWN';assert list(val.iter_errors(d))
 d['value']=None;val.validate(d);d['observed_at']='not-a-time';assert list(val.iter_errors(d))
def test_budget_catalog_keeps_distinct_graph_record_and_wire_limits():
 l=load(K/'graph_v2_catalog.json')['limits']
 assert l['wire_bytes']==196608<l['broker_bytes']==262144
 assert l['record_bytes']==262144 and l['document_bytes']==8388608
 assert l['snapshot_chunk_utf8_bytes']*l['snapshot_chunks']==l['document_bytes']
 assert l['cache_bytes']==16777216 and l['cursor_seconds']==900
 assert l['candidates']==256 and l['paths_per_experience']==512
def test_cypher_catalog_hashes_params_and_execution_labels():
 for row in load(K/'QUERY_CATALOG.json'):
  p=D/'cypher'/row['file'];raw=p.read_bytes()
  assert hashlib.sha256(raw).hexdigest()==row['sha256']
  assert sorted(set(re.findall(r'\$([A-Za-z_][A-Za-z0-9_]*)',raw.decode())))==row['parameters']
  assert '$tenant' in raw.decode()
  assert 'TESTED_SYNTHETIC' in row['execution_status'] or row['execution_status']=='PROPOSED_NOT_EXECUTED'
def test_future_gates_are_ordered_and_not_claimed_implemented():
 rows=list(csv.DictReader((D/'GEN2_GATES_AND_DEPENDENCIES.csv').open()))
 assert [r['gate'] for r in rows]==['G2-1','G2-2','G2-3','G2-4','G2-5','G2-6']
 assert all(r['completion_status']=='PLANNED_NOT_IMPLEMENTED_OR_RUN' for r in rows)
 assert '60Run' in rows[3]['demo_evidence']
def test_contribution_does_not_credit_planned_source_as_implemented():
 rows=list(csv.DictReader((D/'HACKATHON_CONTRIBUTION_MATRIX.csv').open()))
 inherited=[r for r in rows if r['classification'] in {'GEN1_PRE_EVENT_VISIBLE_CONTENT','INHERITED_V5C_OR_V5C1_REPAIR_AT_G20_START','THIRD_PARTY_ASSET_INHERITED'}]
 assert len(inherited)==551
 assert all('NOT_NEW_GEN2' in r['new_competition_claim'] for r in inherited)
 planned=[r for r in rows if r['classification']=='PLANNED_GEN2_IMPLEMENTATION_NOT_AUTHORED']
 assert len(planned)>=8 and all(r['content_sha256']=='NOT_IMPLEMENTED' for r in planned)
def test_required_documents_exist_and_have_substance():
 names=['00_BASELINE_AND_AUTHORITY.md','01_AS_IS_ARCHITECTURE_AUDIT.md','02_GEN2_FINAL_ARCHITECTURE.md','03_EXPERIENCE_GRAPH_V2_SCHEMA.md','GRAPH_CYPHER_CONTRACTS.md','04_AGENT_LIFECYCLE_AND_TRUST_CONTRACT.md','MCP_COMPATIBILITY_AND_VERSIONING.md','05_BENCHMARK_AND_CAUSAL_EVIDENCE_PLAN.md','HERO_STORYBOARD_AND_EVIDENCE_SHOTS.md','06_IMPLEMENTATION_AND_RELEASE_PLAN.md','PUBLIC_PRIVATE_BOUNDARY.md','ARCHITECTURE_DECISIONS.md']
 assert all((D/n).stat().st_size>1500 for n in names)
 text=(D/'ARCHITECTURE_DECISIONS.md').read_text();assert len(re.findall(r'^## ADR-[0-9]+',text,re.M))==13
 assert 'ELIGIBILITY_UNCERTAIN' in (D/'06_IMPLEMENTATION_AND_RELEASE_PLAN.md').read_text()

@pytest.mark.parametrize('bad',['2026-10-15T11:00:00','2026-02-30T11:00:00Z'])
def test_timestamp_requires_valid_calendar_and_timezone(bad):
 d=copy.deepcopy(EX['positive'][0]['value']);d['observed_at']=bad
 assert list(Draft202012Validator(load(K/'fact.schema.json'),format_checker=formats()).iter_errors(d))

@pytest.mark.parametrize('bad',[True,'4',0,4097])
def test_registered_worker_count_type_cannot_be_coerced(bad):
 d=copy.deepcopy(EX['positive'][0]['value']);d.update(key='task.worker_count',value=bad)
 assert list(Draft202012Validator(load(K/'fact.schema.json')).iter_errors(d))

def test_entire_legacy_host_fact_vocabulary_has_explicit_v2_mapping():
 legacy={'concurrency_scope','worker_count','worker_count_known','shared_state_kind','synchronization_scope','transaction_guarantees','observed_failure_mode','shared_object_scope','sqlite_journal_mode','operation_semantics','authority_model','clock_domain','failure_domain','contract_version','lease_expiry_semantics','authority_validation','supported_operation_set'}
 keys=set(load(K/'fact.schema.json')['properties']['key']['enum'])
 assert {'task.'+k for k in legacy-{'authority_validation'}}<=keys
 assert {'artifact_before.authority_validation','artifact_after.authority_validation'}<=keys
 assert 'task.authority_validation' not in keys
