from audit import *
D=P/'docs/gen2/g20'
text=r'''"""G20 design-only checks. No product/graph/model/Oracle execution.
These are contract artifact tests, not Gen2 functionality or inherited regression.
"""
from pathlib import Path
import copy,csv,hashlib,json,re
import pytest
from jsonschema import Draft202012Validator,FormatChecker
D=Path(__file__).resolve().parent;K=D/'contracts'
def load(p):return json.loads(p.read_text())
SCHEMAS=sorted(p for p in K.glob('*.schema.json'))
EX=load(K/'examples.json')
@pytest.mark.parametrize('path',SCHEMAS,ids=lambda p:p.name)
def test_json_schema_is_valid(path):Draft202012Validator.check_schema(load(path))
@pytest.mark.parametrize('case',EX['positive'],ids=lambda c:c['name'])
def test_positive_synthetic_protocol_shape(case):Draft202012Validator(load(K/case['schema']),format_checker=FormatChecker()).validate(case['value'])
@pytest.mark.parametrize('case',EX['negative'],ids=lambda c:c['name'])
def test_negative_synthetic_protocol_shape_is_rejected(case):
 assert list(Draft202012Validator(load(K/case['schema']),format_checker=FormatChecker()).iter_errors(case['value']))
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
 d=copy.deepcopy(EX['positive'][-1]['value']['arguments']);d['proposal']['necessary_conditions']={'artifact_after.authority_validation':['confirmed']}
 assert list(Draft202012Validator(load(K/'propose_experience.arguments.schema.json')).iter_errors(d))
def test_unknown_fact_cannot_gain_a_value_and_timestamp_is_strict():
 val=Draft202012Validator(load(K/'fact.schema.json'),format_checker=FormatChecker());d=copy.deepcopy(EX['positive'][0]['value']);d['availability']='UNKNOWN';assert list(val.iter_errors(d))
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
 text=(D/'ARCHITECTURE_DECISIONS.md').read_text();assert text.count('## ADR-')==13
 assert 'ELIGIBILITY_UNCERTAIN' in (D/'06_IMPLEMENTATION_AND_RELEASE_PLAN.md').read_text()
'''
with (D/'test_design_contracts.py').open('x') as f:f.write(text)
index='''# Aevora Gen 2 / G2-0 审查入口

**Status: ARCHITECTURE_AND_CONTRACT_FREEZE_CANDIDATE, NOT_GEN2_IMPLEMENTED。** 以真实V5C.1 fc539c8524250b53af5353bfce13f1ee857b3695为parent，仅本目录新增设计/协议/合成探针合同和设计检查。生产Core、Runner、Evaluator及历史结果不变。完成后等待独立审查，不自动进入G2-1。

阅读顺序：

1. [基线与验证级别](00_BASELINE_AND_AUTHORITY.md)、[AS-IS源码审计](01_AS_IS_ARCHITECTURE_AUDIT.md)、[源码映射](SOURCE_ENTRYPOINT_MAP.csv)。
2. [最终架构](02_GEN2_FINAL_ARCHITECTURE.md)、[13项ADR](ARCHITECTURE_DECISIONS.md)。
3. [Graph v2](03_EXPERIENCE_GRAPH_V2_SCHEMA.md)、[Cypher合同](GRAPH_CYPHER_CONTRACTS.md)、[typed catalog](contracts/graph_v2_catalog.json)。
4. [生命周期/身份/Host合同](04_AGENT_LIFECYCLE_AND_TRUST_CONTRACT.md)、[MCP兼容](MCP_COMPATIBILITY_AND_VERSIONING.md)、[typed JSON schemas](contracts/mcp_v2.schema.json)。
5. [独立验收和对照](05_BENCHMARK_AND_CAUSAL_EVIDENCE_PLAN.md)、[四幕Evidence计划](HERO_STORYBOARD_AND_EVIDENCE_SHOTS.md)。
6. [开发顺序/发布](06_IMPLEMENTATION_AND_RELEASE_PLAN.md)、[公开私有边界](PUBLIC_PRIVATE_BOUNDARY.md)、[逐文件来源](HACKATHON_CONTRIBUTION_MATRIX.csv)、[Gate](GEN2_GATES_AND_DEPENDENCIES.csv)、[主张证据](CLAIM_TO_EVIDENCE_PLAN.csv)。

`contracts/examples.json`全是明确标记的合成协议形状，不是新Agent行为、真实Source或Outcome。ID示例只演示字段结构，实际存在性/确定性身份、context authority、canonicalSHA、权限和body语义仍需生产Host验证。`test_design_contracts.py`验证schema与合同文件一致性，不替代生产权限/图裁决/原1897项测试。

复核设计文件可使用Python3.12 + 已安装pytest/jsonschema：`python -m pytest -q docs/gen2/g20/test_design_contracts.py --junitxml=<FRESH_EXTERNAL>/JUNIT.xml -p no:cacheprovider`。真实执行环境/argv、当前SDK schema抽取、图探针、失败/回收收据及G20最终报告在独立Evidence目录；不可运行旧历史脚本向封存结果写入。

新协议示例MCP args应从schema读取：先`resolve_experience(task_context={})`，保留query/candidate/recommendation references；真实返回newID才Bundle，依据证据作自主claim；不强制APPLY/固定经验ID。源代码审查足以指导后续实现，不是新机制已PASS。
'''
with (D/'README.md').open('x') as f:f.write(index)
print('DESIGN_CHECKS_AND_INDEX_WRITTEN')
