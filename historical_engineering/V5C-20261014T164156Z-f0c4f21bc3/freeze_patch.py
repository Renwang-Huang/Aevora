from audit import *
import csv,subprocess,xml.etree.ElementTree as ET
P=E/'owned_runtime/source'
names=['aevora_core/src/aevora/mcp_server.py','integrations/codex_agent.py','aevora_core/tests/test_v5c_context_contract.py']
for n in ['existing-mcp-contracts.xml','runtime-submission-contracts.xml','final-context-contract.xml']:
 cases=list(ET.parse(E/'01_c1_repairs'/n).iter('testcase'));assert cases and not any(c.find(t) is not None for c in cases for t in ['failure','error','skipped'])
assert json.loads((E/'01_c1_repairs/physical-boundaries-retry1/summary.json').read_text())['status']=='PASS'
assert json.loads((E/'01_c1_repairs/mcp-wire/RESULT.json').read_text())['status']=='PASS'
assert record('c1-stage-named-diff',['git','-C',P,'add',*names])==0
assert record('c1-local-patch-commit',['git','-C',P,'commit','-m','Fix public MCP context contract and preserve discretionary native experience workflow'])==0
assert record('c1-patch-head',['git','-C',P,'rev-parse','HEAD'])==0
assert record('c1-patch-tree',['git','-C',P,'rev-parse','HEAD^{tree}'])==0
assert record('c1-patch-status',['git','-C',P,'status','--porcelain=v1'])==0
assert not (E/'commands/c1-patch-status/stdout.log').read_text()
patch=subprocess.run(['git','-C',str(P),'diff',C['head'],'HEAD','--',*names],capture_output=True,check=True).stdout
(E/'01_c1_repairs/closure_source_patch.diff').write_bytes(patch)
old=json.loads((E/'00_environment/BASELINE_IDENTITY.json').read_text())['source547_sha256']
changed=[n for n,h in old.items() if sha(P/n)!=h];assert sorted(changed)==sorted(names[:2])
private=[n for n in old if n.startswith(('app/','evaluator/','benchmark/'))];assert all(sha(P/n)==old[n] for n in private)
rows=[{'path':n,'baseline_sha256':old.get(n,'ADDED'),'patched_sha256':sha(P/n),'classification':'ADDITIVE_TEST' if n not in old else 'MINIMAL_PRODUCT_FIX'} for n in names]
with (E/'00_environment/SOURCE_DELTA_MANIFEST.csv').open('x') as f:w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
source=E/'source';snapshot=source/'frozen_source_snapshot';snapshot.mkdir(parents=True)
import shutil
files={}
for n in [*old,names[2]]:
 q=snapshot/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/n,q);files['frozen_source_snapshot/'+n]=sha(q)
head=(E/'commands/c1-patch-head/stdout.log').read_text().strip();tree=(E/'commands/c1-patch-tree/stdout.log').read_text().strip()
write(source/'SOURCE_TRUST_MANIFEST.json',{'files':files,'source_commit':head,'source_tree':tree,'created_at':now(),'authority':'TRUSTED_LOCAL_PIN; not external attestation','kind':'V5C_CURRENT_PATCH_TREE'})
write(E/'01_c1_repairs/PATCH_FREEZE.json',{'at':now(),'baseline_commit':C['head'],'baseline_tree':C['tree'],'closure_patch_commit':head,'closure_tree':tree,'patch_sha256':sha(E/'01_c1_repairs/closure_source_patch.diff'),'source_manifest_sha256':sha(source/'SOURCE_TRUST_MANIFEST.json'),'source_snapshot_files':len(files),'source_changes':rows,'original_Oracle_business_fixtures_unchanged':True,'frozen_main_source_unchanged':all(sha(W/n)==h for n,h in old.items()),'preflight_policy':{'request_budget':None,'timeout_seconds':None,'completion_policy':'completion-aware','max_request_concurrency':2,'model':'gpt-5.6-terra','effort':'max'},'C1_offline_gate':'PASS; C1 native live handoff pending S0'})
(E/'01_c1_repairs/ROOT_CAUSE_AND_FIX.md').write_text('''# Minimal fixes and compatibility

Original evidence proves overly broad task_context dict schema, scalar/pinned runtime restrictions and generic errors. Public schema now comes from a strict eight-field Pydantic model; official SDK public list_tools/call_tool hooks ensure top-level extra keys and SDK JSON-string coercion cannot bypass that schema. Field errors omit supplied values/unsafe unknown names; pinned conflicts remain generic. Host extended fact vocabulary and applicability authority are unchanged, unknown trusted facts cannot be promoted by claims. No fake/default APPLY fact or Episode/patch answer is added.

Natural experience workflow: inherited adapter imperatively required tool calls/proposal. The patched prompt encourages evidence use/reflection conditionally; the actual Agent chooses and emits every call, and may fail to propose. All grades must reflect this rather than Host filling a missing proposal.

Original defaults/bounded replay contracts remain for compatibility. New live launcher always supplies actual None request budget/total wall limit with completion-aware mode, concurrency2 and existing finite retries/security/resource/manual-cancel controls. No cumulative allocation/dollar/token stop exists in this closure driver.

Evidence:68 existingMCP tests,197 runtime/submission contracts,32 additive context tests including real authenticated SDK/STDIO/FalkorDB;14 raw MCP controls;6 physical boundaries/checks. A first physical collector lacked ORDERFLOW_CODEX_BINARY, fixed via existing runtime(native=True). A first schema seed passed initialize positionally, corrected to its real keyword-only API. Both failures remain, only external harness changed. Original test assertions and Oracle/fixture bytes untouched.

Mature references: official MCP Python SDK1.26 FastMCP public methods and Pydantic WithJsonSchema/model_validate; source snapshots/API docs are recorded separately. Legacy internal extended facts remain; public tool deliberately follows eight documented fields. Text examples are not fabricated closed enums. Exposing public claim constraints grants no Host approval/Outcome authority. Shared-kernel/AOF139/D-v02 UDS limits remain.
''')
print('PATCH_FROZEN',head,tree,flush=True)
