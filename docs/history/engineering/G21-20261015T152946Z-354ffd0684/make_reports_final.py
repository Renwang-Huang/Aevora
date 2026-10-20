from audit import *
import xml.etree.ElementTree as ET,csv,ast,stat
BASE='a54d9972aba2adb77a09667a8b656c63e089264f'
R=E/'reports';R.mkdir(exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=P,text=True).strip()
def junit(path):
 cs=list(ET.parse(path).getroot().iter('testcase'));return dict(total=len(cs),failed=sum(bool(c.findall('failure')) for c in cs),errors=sum(bool(c.findall('error')) for c in cs),skipped=sum(bool(c.findall('skipped')) for c in cs),duplicates=len(cs)-len({(c.get('classname'),c.get('name')) for c in cs}))
old=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/V5C1-20261015T054437Z-fb77b23eff/03_regression/RAW_JUNIT.xml');new=E/'05_regression/inherited-acceptance/JUNIT.xml';new2=E/'05_regression/gen2-acceptance-final/JUNIT.xml'
def ids(p):return [c.get('classname','')+'::'+c.get('name','') for c in ET.parse(p).getroot().iter('testcase')]
a,b=ids(old),ids(new);identity=dict(original=len(a),current=len(b),missing=sorted(set(a)-set(b)),extra=sorted(set(b)-set(a)),duplicate=len(b)-len(set(b)),source_junit_sha256=sha(old),current_junit_sha256=sha(new));write(R/'TEST_IDENTITY_CHECK.json',identity)
assert len(a)==len(b)==1897 and not identity['missing'] and not identity['extra'] and not identity['duplicate']
assert junit(new)==dict(total=1897,failed=0,errors=0,skipped=0,duplicates=0)
assert junit(new2)==dict(total=108,failed=0,errors=0,skipped=0,duplicates=0)
with (R/'G21_TEST_IDENTITY_DELTA.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['identity','category','status'])
 for i in sorted(b):w.writerow([i,'INHERITED_UNCHANGED','PASS'])
 for i in sorted(ids(new2)):w.writerow([i,'NEW_G21_REAL_DB_OR_CONTRACT','PASS'])
perf=json.loads((E/'05_graph_accepted/PERFORMANCE.json').read_text());dataset=json.loads((E/'05_graph_accepted/performance-before.json').read_text());truth=json.loads((E/'05_graph_accepted/TRUTH_TABLE.json').read_text());inter=json.loads((E/'05_graph_accepted/INTERVENTIONS.json').read_text());bench=json.loads((E/'05_benchmark/cli/summary.json').read_text());assert bench['status']=='PASS'
status=dict(G21_FINAL='G21_CONDITIONAL',BASE_SHA=BASE,CODE_COMMIT=git('rev-parse','HEAD'),G21_0_CONTRACT='PASS_AMENDED_RC2',GRAPH_V2_REAL='PASS_MEASURED_SCOPE',WITNESS_COMPLETE='PASS_MEASURED_CONTROLS',ARBITRATION_REAL='PASS_MEASURED_CONTROLS',LEGACY_1_2='PASS',AUTHZ_SDK_BROKER='PASS_LOCAL_BOUNDARY_WITH_DOCUMENTED_DB_SEND_INTERVAL',REGRESSION=dict(inherited=junit(new),new=junit(new2),design_and_entry=junit(E/'05_regression/FINAL_CONTRACT_JUNIT.xml')),G22_HOST_PUBLICATION='NOT_RUN',G23_NATIVE_MULTI_AGENT='NOT_RUN',CAUSAL_BENEFIT='UNKNOWN',PUBLIC_PUSH=False,HISTORICAL_SOURCE_CHANGED=False,REAL_AGENT_RUNS=0,PERFORMANCE='PERFORMANCE_LIMITED',FULL=str(E),limits=['64x8 observed p95 exceeds5s','100k nodes/300k edges NOT_AT_TARGET','DB check/socket send not globally atomic','G20 independent audit attachment NOT_FOUND','cross-partition revision/migration needs review'])
write(R/'G21_GATE_RESULTS.json',status)
with (R/'G21_ARBITRATION_TRUTH_TABLE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['case','independent_expected','actual','reasons','manifest_sha256','witness_sha256','synthetic']);w.writeheader()
 for row in truth:w.writerow({k:json.dumps(row[k]) if isinstance(row[k],list) else row[k] for k in w.fieldnames})
with (R/'G21_GRAPH_INTERVENTION_EVIDENCE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(inter[0]));w.writeheader();w.writerows(inter)
# Every current changed asset is classified, without claiming copied contracts are new algorithms.
changed=set(git('diff','--name-only',BASE).splitlines())|set(git('ls-files','--others','--exclude-standard').splitlines())
with (R/'SOURCE_DIFF_AND_ORIGINALITY_MATRIX.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['path','current_sha256','base_sha256','origin','scope','AI_assisted','first_g21_commit','eligibility'])
 for n in sorted(changed):
  p=P/n
  if not p.is_file():continue
  q=subprocess.run(['git','show',BASE+':'+n],cwd=P,capture_output=True)
  base_sha=hashlib.sha256(q.stdout).hexdigest() if q.returncode==0 else ''
  origin='INCREMENTAL_EXISTING_IMPLEMENTATION' if base_sha else 'NEW_G21_IMPLEMENTATION_OR_ACCEPTANCE'
  if '/schemas_v2/' in n:origin='COPIED_G20_STRUCTURAL_CONTRACT_RC2; NOT_ALL_SCHEMAS_IMPLEMENTED'
  if n.startswith('docs/gen2/g21'):origin='G21_CONTRACT_AND_REVIEW_DOCUMENT'
  scope='PUBLIC_PRODUCT' if n.startswith('aevora_core/src/') or n.startswith('aevora_core/docs/') or n=='aevora_core/pyproject.toml' or n=='docs/THIRD_PARTY_NOTICES.md' else 'MAINTAINER_ACCEPTANCE'
  commits=git('log','--reverse','--format=%H',BASE+'..HEAD','--',n).splitlines();w.writerow([n,sha(p),base_sha,origin,scope,True,commits[0] if commits else 'PENDING_DOC_COMMIT','ELIGIBILITY_UNCERTAIN; commit_date_not_authorship'])
# Actual symbols/lines are derived from current AST, not copied from design line numbers.
with (R/'G21_SOURCE_ENTRYPOINT_MAP.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['path','symbol','line','end_line','sha256'])
 for n in sorted(changed):
  p=P/n
  if p.suffix!='.py' or not p.is_file():continue
  for obj in ast.parse(p.read_text()).body:
   if isinstance(obj,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):w.writerow([n,obj.name,obj.lineno,obj.end_lineno,sha(p)])
claims=[
 ('Q01_COMPLETE_RECALL','aevora_core/src/aevora/graph_v2.py','gen2-acceptance-final','native scope projection corruption red->repaired; authenticated scope catalogue exact set','05_regression/gen2-acceptance-final/RAW_CYPHER.jsonl','NEW_REAL_DB_SYNTHETIC'),
 ('Q04_COMPLETE_WITNESS','aevora_core/src/aevora/graph_v2.py','gen2-acceptance-final','Task/Context/Authority/hash/edges/counter/phase negatives','05_graph_accepted/support-witness.json','NEW_REAL_DB_SYNTHETIC'),
 ('DETERMINISTIC_WHEN_WHY','aevora_core/src/aevora/arbitration.py','gen2-acceptance-final','independent expectations + cut/restore','05_graph_accepted/TRUTH_TABLE.json','NEW_REAL_DB_SYNTHETIC'),
 ('Q08_COMPOSED_AUTHORIZATION','aevora_core/src/aevora/mcp_v2.py','gen2-acceptance-final','real SDK/Broker; foreign session/tenant/cursor/revoke/cached damage/time boundary','05_regression/gen2-acceptance-final/SDK_RAW','NEW_REAL_SDK_SYNTHETIC_HOST_SESSION'),
 ('LEGACY1897','aevora_core/src/aevora/mcp_server.py','inherited-acceptance','all original identities preserved; actualpytest exit0','05_regression/inherited-acceptance/JUNIT.xml','NEW_DYNAMIC_INHERITED_TESTS'),
 ('BENCHMARK15','benchmark/runner.py','inherited-benchmark-cli','actual CLI; separate PASS/FAIL/NOT_IMPLEMENTED/reset/report','05_benchmark/cli/summary.json','NEW_ORIGINAL_ORACLE_REGRESSION_NOT_AGENT'),
 ('PUBLIC_PACKAGE_BOUNDARY','tools/public_release.py','g21-clean-public-real-mcp-console-catalogue','clean wheels, Benchmark absent, legacy+v2 SDK and real Console HTTP','05_release/clean-smoke-catalogue/RESULT.json','NEW_DYNAMIC_PUBLIC_WHEELS'),
 ('Q07_PRECONDITIONS','docs/gen2/g21/cypher/Q07_prepared_publication_fence.cypher','q07-native-explain-only','engine EXPLAIN + identical graph before/after; publisher/CAS NOT_RUN','reports/Q07_ENGINE_EXPLAIN.json','STATIC_CONTRACT_AND_REAL_ENGINE_EXPLAIN_ONLY'),
 ('PERFORMANCE','aevora_core/src/aevora/graph_queries.py','accepted-native-graph-controls-performance','64x8 five samples; p95 target missed;100k/300k notvalidated','05_graph_accepted/PERFORMANCE.json','NEW_REAL_DB_SYNTHETIC_PERFORMANCE'),
 ('HISTORY_PRESERVED','SOURCE_AND_HISTORY_RECEIPT','sealed-g20-full-recheck','current547/551 source and sealed G20/V51 bytes metadata checks','reports/V51_HISTORICAL_FULL_RECHECK.json','NEW_READONLY_HASH_RECHECK'),
]
with (R/'G21_CLAIM_TO_EVIDENCE_MATRIX.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['claim','source','test_or_command','independent_expectation','raw_evidence','classification','evidence_sha256','limitation'])
 for row in claims:
  ep=E/row[4];w.writerow([*row,sha(ep) if ep.is_file() else 'DIRECTORY_MEMBER_HASHES_IN_FULL_MANIFEST','Synthetic graph is not new Agent/Outcome; documented scope only'])
# Preserve first failures and distinguish expected negative controls from engineering failures.
fail=[]
for receipt in sorted((E/'commands').glob('*/receipt.json')):
 v=json.loads(receipt.read_text())
 if v['exit']!=0:fail.append(dict(command=receipt.parent.name,exit=v['exit'],receipt=str(receipt.relative_to(E)),stdout_sha256=v['stdout_sha256'],stderr_sha256=v['stderr_sha256']))
write(R/'G21_FAILURE_LEDGER.json',dict(unexpected_or_deliberate_red_attempts=fail,expected_business_failures='05_benchmark/cli/summary.json expected_exit/status; these are sensitivity success, not successful submissions',source_edit_script_error='One shell patch script syntax error; subsequent five actual red tests preserved. No separately archived stderr for that edit command.',early_sdk_raw_loss='First SDK attempt used ephemeral namespace /tmp: child event files UNAVAILABLE; pytest/JUnit retained. All final SDK raw events archived externally.',superseded_derived_reassembly='Earlier derived successful reassembly summaries were replaced; all source raw streams and command stdout remain replayable. Final summary is catalogue-specific.'))
base_text=f'''# Aevora Gen 2 / G21 implementation validation

## G21_FINAL: G21_CONDITIONAL

Base `{BASE}`. Independent owned worktree `{P}`. Current code commit `{status['CODE_COMMIT']}`; final documentation commit/tree are pinned by FINAL_SOURCE.json and the external delivery receipt. Frozen main, V5C.1, G20, original Oracle, reference repairs and old test assertions are unchanged. No push, merge, archive cleanup, paid Agent challenge or G22 development occurred.

The read slice is implemented and independently testable: actual owned authenticated FalkorDB, Graph v2 schema/indices, complete canonical typed witness, authenticated scope discovery catalogue, deterministic WHEN/WHY, explicit v2 four-tool SDK/Broker, bounded snapshots/pages, current permission/epoch/time lifecycle checks. It reuses the mature official SDK/transport/governance/equality and projection. G22 production Host review/publication/concurrent CAS and G23 Native Multi-Agent remain NOT_IMPLEMENTED/NOT_RUN. Every trusted graph outcome in this acceptance is explicitly HOST_CONTROLLED_SYNTHETIC_FIXTURE, not a new Agent or independent engineering grade.

## Actual accepted execution

| Gate | Result | Primary raw evidence |
|---|---|---|
| G21-0 | PASS amended rc2 contracts; missing independent audit attachment disclosed | entry amendments; FINAL_CONTRACT_JUNIT86; Q07 engine EXPLAIN only |
| G21-1 | PASS owned real Graph v2,64 operational constraints across31 domain labels+V2Record | native schema/index dumps, raw queries, Docker image/version |
| G21-2 | PASS complete reached-set/declared-set/source/authority/phase/scope/catalogue checks |108 real DB/control tests and full native paths |
| G21-3 | PASS actual APPLY/VERIFY/ABSTAIN, two reversible interventions | truth table, support/counter cuts/restores, complete witnesses |
| G21-4 | PASS measured local SDK/Broker boundary; distributed interval qualified | real four tools, two tenants, lossless reassembly, delivery SHA/scope |
| G21-5 |1897/1897 inherited +108/108 G21 +86/86 design/entry, actual exit0 | all original JUnit and argv/stdout/stderr/hash receipts |
| G21-6 | local source/artifact freeze and Full/Lite review delivery | final clean commit/tree, manifests/verifier/negative controls |

Accepted inherited command: `python3 runtime.py --history inherited-final-acceptance -- tools/dev.py test-maintainer --output {E}/05_regression/inherited-acceptance --owned-port 17731 -- -q tests aevora_core/tests --ignore=aevora_core/tests/gen2 -p no:cacheprovider` (receipt contains exact separated argv). It collected1897, zeroFAIL/ERROR/SKIP/duplicate, exit0. New command `python3 runtime.py gen2-final-acceptance -- tools/dev.py test-graph-v2 --output {E}/05_regression/gen2-acceptance-final --owned-port 17731` collected108, allpass/exit0. New and inherited identities are separated in G21_TEST_IDENTITY_DELTA.csv.86 design/entry checks are additional, not counted as production tests. Two upstream Starlette/Pydantic warnings remain.

15 actual CLI checks preserve Smoke8/A14/D-v01 28 correct/buggy outcomes, B/C NOT_IMPLEMENTED, prepare/report/reset and historical Agent patch replay. These fresh Oracle regressions are not new Agent challenges and are not used as v2 support. Clean standalone Core/Console wheels passed16 checks with no Benchmark installed/mounted: actual legacy four tools, v2 empty query, real loopback Console LIVE HTTP and denied mutation/private/mode requests.

## Four repaired contract gaps

Q01 now compares native scoped seek results to complete immutable graph-native per-scope catalogues pinned by TenantState, not Caller IDs. This closes the reproduced native scope projection omission before witness validation. Selected publication root ID/SHA must equal its catalogue entry; obsolete/missing commit cannot become EMPTY. Relevant257 refuses;258 total with only one relevant resolves. Scope catalogues/epoch must be updated together by the future Host fence.

Q04 uses actual joins through Task and Authority, complete canonical records/typed edges and exact publication lists. Registered ordinary ENGINEERING_VERIFIER and INDEPENDENT_ORACLE require exact Host pins; EXTERNAL_UNVERIFIED cannot support. Context/Task/Authority/phase/hash/native mismatch, missing FOR_TASK/counter etc all deny completeness. Only actual scoped business FAIL counters veto; ERROR/TIMEOUT/NOT_RUN remain observations.

Q08 composes bearer/kernel Host capability, fixed physical selector, graph Session/state, grant TTL/generation/profile/run/session, immutable query/view/document and current epoch, full catalogue/witness recheck and final Broker output. Real simultaneous tenant test found and repaired global-environment binding drift: output now uses each Broker's captured Host environment. Non-sensitive metadata uses read_scope to avoid blanket credential-key redaction; delivered frame hashes match archived unredacted frames. Cached recommendations are re-arbitrated at current time, so future-effective withdrawal/expiry cannot reuse a prior APPLY without epoch movement. Product record time is actual UTC; fixed fixture times are explicit synthetic inputs.

Q07 prepared/head/source/outcome/authority/root/chunk/request/epoch/authz preconditions and replay/crash requirements are frozen. The template passed engine EXPLAIN with identical graph before/after, not actual publication/CAS. Full Host admission and source verification remain G22 NOT_RUN. Synthetic test writers are outside the public source allowlist.

## Graph intervention and performance

Support APPLY→cut GRAPH_INTEGRITY_ERROR→restore APPLY; support+counter VERIFY→cut counter GRAPH_INTEGRITY_ERROR→restore VERIFY. Exact before/restored graph and recommendation hashes match. Five independently declared expectation cases match actual Core results; raw Cypher/params/results and every witness/root SHA are retained.

Final performance dataset: {dataset['node_count']} nodes/{dataset['edge_count']} edges,64 relevant candidates×8 paths. Five complete resolves: {', '.join(f"{m['seconds']:.3f}s" for m in perf['measurements'])}; observed p95 (five-sample maximum)={perf['observed_p95_seconds']:.3f}s.5s goal missed,100k/300k NOT_AT_TARGET. This is exploratory warm measured scope, not a statistically established SLO. Final measurement uses a fresh dedicated1GiB/2CPU DB containing only the five small control graphs and the performance graph. Earlier shared-DB measurements remain archived. Process RSS and actual query bytes/rows/plans are recorded, not attributed to a pristine single-graph server. Index scans were observed; this does not establish scope-only cost at100k.

## Failure preservation

First inherited attempt1884PASS/13FAIL: copied editable finder pointed outside the new namespace; isolated -I evaluator failed loading. Fixed only the owned environment by reinstalling the three local packages; complete reruns passed. First graph probes exposed incomplete native edge projections and missing legacy governance field adaptation. First SDK startup failed unsupported bare dict structured return, then fixed to dict[str,Any]. Initial new controls also found message metadata redaction, namespace and staging issues. Two-tenant drift and index-only recall were actual red controls before repair. Eight-hop acceptance versus nine-hop/cycle refusal and explicit parent Broker read-client cleanup have real red/green controls too. All failed JUnit/command outputs remain. No old assertions were removed or relaxed. One new missing-COMMIT expectation was strengthened from EMPTY to integrity ERROR after authenticated recall was added.

Source edit/collector issues and early ephemeral child-log loss are explicitly described in G21_FAILURE_LEDGER.json. All final raw SDK events, direct query/results, page hashes, original JUnit and independent reconstruction are retained. A later pass never replaces an earlier fail. Historical data uses read-only namespace mappings; this is not Participant access.

## Remaining boundaries

PERFORMANCE_LIMITED is the reason for CONDITIONAL.100k/300k not executed. DB state check and socket send are not a distributed atomic transaction; successful delivery records expose the real interval, and already delivered bytes cannot be recalled. Local owner revocation/send is serialized, while malicious/external DB administrators are outside the promise. Registry pins are local OS-rooted authority, not signatures. Material shared-state partition is fixed per Experience; cross-partition revision/migration requires a reviewed contract. Current finite bounds256 candidates/512paths/20MiB intermediate/8MiB doc/128×64KiB/32cached docs/16MiB remain explicit refusals, not truncation. No full hostile-host/HA/SLO assertion.

The G20 independent review file was not found; the supplied taskbook's explicit four findings were applied and tested, not falsely read as an attachment. RDB last-save RPO/AOF139, shared-kernel partial safety, old ClockUDS constraints and competition eligibility uncertainty remain inherited; no regrading. No new Native Agent or causal benefit claim. No automatic G22 authorization.

## Reproducibility and audit

Full directory `{E}` is PRIVATE_MAINTAINER, contains the independent Git and original private truth copy. Audit-Lite is INTERNAL_MAINTAINER_REVIEW, not public/Participant input; no private Oracle/reference source, DB credential or Gateway key. It retains necessary local paths, IDs and nonsecret hashes for traceability rather than claiming anonymization. Full/Lite pin exact source members, receipts and source links. Independent stdlib verifier never executes product code, DB or model; positive/wrong-pin/actual-byte-tamper checks are recorded. Local hashes are not external timestamps or protection against a malicious maintainer. Final delivery SHA/paths live in the separate external receipt to avoid seal self-reference.
'''
(R/'G21_IMPLEMENTATION_REPORT.md').write_text(base_text)
(R/'G21_LEGACY_COMPATIBILITY_REPORT.md').write_text('''# Legacy compatibility\n\n1897 original identities, zero removed/added/duplicate in the inherited set; final actual exit0/JUnit attached. Original models/schema1.x, four-tool1.2 schemas and legal payloads retained. New .v2 factory/profile only; old graphs refuse implicit upgrade. Legacy compatibility DB is owned/fresh, seeded by four currently pinned historical M1 replays (27nodes/24edges), not a claim to have replayed the full V5C.1 feedback graph. Larger capacity is separately tested by G21 owned synthetic fixtures. All old tests/assertions/private task truth remain byte-identical.15 fresh CLI checks and clean public legacy/v2/Console checks supplement JUnit. Remaining original runtime/sandbox/RDB limitations are not upgraded.\n''')
(R/'G21_GRAPH_SCHEMA_AND_INDEX_REPORT.md').write_text('''# Actual Graph v2 schema/index\n\nSee05_graph_accepted/*-schema.json and RAW_CYPHER for64 operational UNIQUE/MANDATORY constraints on31 domain labels plus indexing helper V2Record, and actual scope index. The official async constraint API is awaited; missing native payload/hash/typed endpoints deny records. Physical graph/tenant binding is Host-only. Query plans include native IndexScan and PROFILE sampled costs, not100k-scale proof. Scope catalogue state heads reuse bounded QuerySnapshot/HAS_CHUNK storage and form the authenticated recall set; published manifests pin all semantic records. All graph data in these probes is HOST_CONTROLLED_SYNTHETIC_FIXTURE; no real source/outcome review is certified. Q07 EXPLAIN is syntax/planning only.\n''')
(R/'G21_PERFORMANCE_AND_CAPACITY_REPORT.md').write_text(f'''# Measured performance and capacity\n\nPERFORMANCE_LIMITED. Real owned FalkorDB, CPU2/memory1GiB dedicated fresh final DB (prior test DB2GiB;3GiB archive-only SAVE headroom);64×8, {dataset['node_count']}nodes/{dataset['edge_count']}edges. Five samples: {json.dumps(perf['measurements'])}. Observed p95={perf['observed_p95_seconds']},5s goal missed;100k/300k NOT_AT_TARGET. Source map, actual EXPLAIN/PROFILE, query rows/bytes and process maxRSS retained. Only five small control graphs share the fresh final DB; this is not a statistical SLO claim. Earlier shared-DB runs remain original.\n\nActual boundaries: total258 with1related succeeds; relevant257 explicit capacity;66 seek identities complete;512 full paths include last counter;513 fails;65536-byte chunks +/-1,128/129 chunks,8MiB +/-1, duplicate/missing/SHA/tenant/index corruption all tested; Unicode survives actual DB and lossless SDK.262144 broker cap unchanged, actual delivered frames/pydantic double encoding checked. Snapshot/cached data never bypass current authority/epoch/time/integrity. Resource safety limits are not an upstream API cost quota.\n''')
(R/'G21_LIMITATIONS_AND_HANDOFF.md').write_text('''# Limitations / stop\n\nG21_CONDITIONAL:64×8 observedp95 above5s;100k/300k nottested. Auth check/socket send non-atomic across DB/network; already delivered bytes unretractable. Current OS-rooted registry trusts authorized Host setup, not malicious DB admins/signatures. Cross-partition revision/migration and1024 scope-head bound need review; prepared catalogue heads must be fenced with publication epoch in G22. Snapshot whole documents remain8MiB and may explicitly reject larger compound query snapshots. Native tool identity/join/new Agent outcomes NOT_RUN; all acceptance graph grades synthetic. G20 independent review attachment NOT_FOUND. Original AOF139/RDBRPO/sharedkernel/ClockUDS/eligibility limits remain.\n\nG22 source/admission/Host review/publication/concurrent CAS/crash-retry NOT_IMPLEMENTED. G23 native multi-agent, G24 causal controls, G25 final UI and G26 public release NOT_RUN. See NEXT_GATE_G22_ENTRY; await independent review and new authorization. No push or merge.\n''')
# Keep a source-side report that refers to the separately sealed terminal receipt instead of self-hashing a commit.
(P/'docs/gen2/g21/G21_IMPLEMENTATION_REPORT.md').write_text(base_text)
print(json.dumps(status,indent=2))
