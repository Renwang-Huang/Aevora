"""Derive final reports from actual receipts; no changes to product or sealed Runs."""
from audit import *
import csv,collections
out=E/'07_audit'
def doc(n,s):
 p=out/n
 with p.open('x') as f:f.write(s.strip()+'\n')
s1=json.loads((E/'02_live_s1/NATIVE_LIFECYCLE_RESULT.json').read_text());s2=json.loads((E/'04_live_s2/NATIVE_LIFECYCLE_RESULT.json').read_text());inherit=json.loads((E/'04_live_s2/inheritance_trace.json').read_text());freeze=json.loads((E/'01_c1_repairs/PATCH_FREEZE.json').read_text())
assert json.loads((out/'FINAL_SOURCE_IDENTITY.json').read_text())['status']=='PASS'
assert json.loads((out/'HISTORICAL_FULL_FINAL_REHASH.json').read_text())['status']=='PASS'
commands=[json.loads(p.read_text()) for p in sorted((E/'commands').glob('*/receipt.json'))]
with (out/'COMMAND_INDEX.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['label','started_at','ended_at','exit_code','argv','stdout_sha256','stderr_sha256']);w.writeheader()
 for c in commands:w.writerow({k:json.dumps(c[k]) if k=='argv' else c[k] for k in w.fieldnames})
ledger=[];sessions=[]
for label in ['01_c1_repairs/native_preflight','02_live_s1','04_live_s2']:
 run=next((E/label/'runs').iterdir());m=json.loads((run/'runtime_metadata.json').read_text());r=json.loads((run/'evaluation_report.json').read_text());sent=0
 for i,x in enumerate(m['model_broker']['request_records']):
  sent+=x.get('request_sent_at') is not None
  ledger.append({'session_label':label,'run_id':run.name,'record_index':i,'actual_record':x,'source_file':str((run/'runtime_metadata.json').relative_to(E)),'source_sha256':sha(run/'runtime_metadata.json'),'json_pointer':'/model_broker/request_records/'+str(i),'retry_parent':'UNAVAILABLE unless explicitly in actual_record; no timing inference'})
 sessions.append({'label':label,'run_id':run.name,'session_id':m['session_id'],'thread_id':m['thread_id'],'native_exit':m['exit_code'],'runtime_result':r['runtime_result'],'evaluation_result':r['evaluation_result'],'integration_result':r['integration_result'],'overall_status':r['overall_status'],'test_counts':{k:r['test_results'][k] for k in ['collected','passed','failed','errors','skipped']},'forwarded_requests':sent,'request_budget':m['request_budget'],'timeout_seconds':m['timeout_seconds'],'native_mode':m['agent_mode'],'elapsed_seconds':m['elapsed_seconds'],'usage':m['usage'].get('totals'),'patch_sha256':sha(run/'submission.diff')})
with (out/'REQUEST_LEDGER.jsonl').open('x') as f:
 for row in ledger:f.write(json.dumps(row)+'\n')
write(out/'SESSION_TERMINAL_INDEX.json',sessions)
records=[x['actual_record'] for x in ledger];counts={'total_forwarded':sum(x.get('request_sent_at') is not None for x in records),'catalog_get':sum(x.get('route')=='/v1/models' for x in records),'model_post':sum(x.get('route')=='/v1/responses' for x in records),'completed':sum(x.get('outcome')=='COMPLETED' for x in records),'provider_429':sum(x.get('upstream_http_status')==429 for x in records),'local_budget_429':sum(x.get('category')=='RUN_REQUEST_BUDGET_EXHAUSTED' for x in records),'stream_interrupted':sum(x.get('category')=='UPSTREAM_STREAM_INTERRUPTED' for x in records)}
write(out/'REQUEST_POLICY_RESULT.json',{'status':'PASS','counts':counts,'session_budgets':[s['request_budget'] for s in sessions],'wall_timeouts':[s['timeout_seconds'] for s in sessions],'usd_budget':None,'token_budget':None,'provider_concurrency':2,'sequential_sessions':True,'actual_model':'gpt-5.6-terra','actual_effort':'max','model_weights_and_charges':'UNVERIFIED','retry_parent_lineage':'UNAVAILABLE; no failed/retried request observed in this cohort','scoped_mcp_request_guard':4096,'scoped_mcp_guard_scope':'Existing local resource guard, not an upstream model/financial quota; no guard exhaustion observed','causal_benefit':'UNKNOWN'})
rows=[('C0','PASS','Frozen main clean;547 baseline identities; independent object store;548 patched snapshot','00_environment/BASELINE_IDENTITY.json;07_audit/FINAL_SOURCE_IDENTITY.json'),('C1','PASS_WITH_PREFLIGHT_TASK_FAIL','Public eight-field strict schema;32added tests; real wire14controls; actual native handoff; S0 taskFAIL0/8 preserved','01_c1_repairs/C1_RESULT.json'),('C2','PASS','New S1 native0; original28/28; actual scoped+typed proposal; strict source verification','02_live_s1/NATIVE_LIFECYCLE_RESULT.json;03_feedback/source/RESULT.json'),('C3','PARTIAL','S1 Agent source published; fresh S2 sees new experience but explicit bundle/decision select OLD experience; original28/28','04_live_s2/inheritance_trace.json'),('C4','PARTIAL','22 bounded real governance controls pass; full post-S2-feedback response exceeds262144-byte transport bound; real outage/restart pass','05_negative_controls/FULL_CORPUS_MESSAGE_LIMIT_FAILURE.json;05_negative_controls/governance_retry2/RESULT.json;05_negative_controls/db_outage/RESULT.json'),('C5','PASS','1868/1868 exact1836retained;15CLIcontracts;6JScontracts; actual public build/privacy scan; source/history rehash; Full/Lite seal follows','06_regression/REGRESSION_IDENTITY_RESULT.json;07_audit/FINAL_SOURCE_IDENTITY.json')]
with (out/'CLAIM_EVIDENCE_MATRIX.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['gate','verdict','claim_and_boundary','evidence']);w.writerows(rows)
write(out/'GATE_RESULTS.json',{'overall':'V5C_CONDITIONAL','gates':[dict(zip(['gate','verdict','finding','evidence'],r)) for r in rows],'native':'SINGLE','cross_session':'NEW_SESSION_RETRIEVAL_YES; EXPLICIT_NEW_EXPERIENCE_ADOPTION_UNVERIFIED','causal_benefit':'UNKNOWN','control':'CONTROL_NOT_RUN','pre_gen2_admission':'NOT_GRANTED; independent review required','at':now()})
doc('V5C_FULL_VALIDATION_REPORT.md',f'''# Aevora Pre-Gen2 V5 Closure — Validation Report

## Conclusion

**V5C_CONDITIONAL**. C0/C1/C2/C5 have the evidence described below. C3 and C4 remain PARTIAL. This is not Pre-Gen2 admission; independent review is still required. No Gen2, merge, remote push or public release was performed.

## Source and boundaries

Frozen primary HEAD737f1746631774251a2c504aaf0ceafd9c3ff0c0 / Tree7fad4fffdad4c9a85ae9e521928b6a6592a4dcb9 is clean; all547 G5-defined paths unchanged. These include docs/config and are not547 executable modules. Independent clone patch commit **{freeze['closure_patch_commit']}**, tree **{freeze['closure_tree']}**, diff SHA256 **{freeze['patch_sha256']}**. Two product files changed;32 additive test cases in one new file. All business/Runner/Oracle/reference bytes remain unchanged.548 patched source pins are separately verified; they are not claimed identical to the old547.

Owned copied Python3.12, official Codex0.162.1 binary/helper, real authenticated FalkorDB4.20.4 on dedicated loopback17707 and isolated graph keys. Actual online model route is gpt-5.6-terra/max without downgrade. Secrets stayed external0600/0700 and trusted-host-only. Participant had no historical mounts. Runtime/permission controls pass within the existing shared-kernel model; hostile-kernel isolation remains PARTIAL. Only the owned DB was stopped/restarted, then left stopped with forensic data retained.

## Gates and actual execution

| Gate | Result | Evidence |
|---|---|---|
'''+ '\n'.join('|'+g+'|'+v+'|'+d+'|' for g,v,d,e in rows)+f'''

Every command, UTC start/end, exit, argv and stdout/stderr SHA is in COMMAND_INDEX.csv and commands/<label>/receipt.json. Key invocations use external `runtime.py` to call existing code:

```text
tools/dev.py test-maintainer --output {E}/06_regression/attempt1 --owned-port 17707
live_agent.py preflight
live_agent.py s1
host_source.py
host_publish.py
live_agent.py s2
s2_feedback.py
negative_controls.py
db_probe.py before|offline|after
tools/dev.py benchmark-check --output {E}/06_regression/benchmark-cli
tools/dev.py public-build --output {E}/06_regression/public-build
owned_runtime/node --test console/web/*.test.mjs
```

These are actual archived invocations, not commands to rerun against sealed output directories. Exact bwrap/env/graph/argv appear in individual receipts. Real upstream credential values never appear in the argv or archive.

## Native results

| Session | Run | Native | Original Oracle | Integration | Requests |
|---|---|---|---|---|---|
'''+ '\n'.join(f"|{x['label']}|{x['run_id']}|{x['native_exit']}|{x['evaluation_result']} {x['test_counts']['passed']}/{x['test_counts']['collected']}|{x['integration_result']}|{x['forwarded_requests']}|" for x in sessions)+f'''

S0's actual agent patch omitted restoration of the Smoke stock-conservation constraint: FAIL0/8 was preserved. It verified natural handoff and honest scoring, not task success. S1 was already correctly sealed by Runner; the external collector's redundant second seal raised FileExistsError, leaving its outer command exit1. The original Run is genuinely native0/PASS28; a subsequent read-only rehash verified the existing seal. Neither the seal nor grade was rewritten. The collector was corrected for S2.

S1 made one initial pinned-context conflict and two invalid truncated-query bundle calls, then recovered using actual IDs. S2 made one context conflict then recovered with empty claims. All failed tool calls remain in complete native/MCP streams. None were suppressed or converted to successful calls.

## Request policy

Actual totals: **{counts['total_forwarded']} authenticated forwards = {counts['catalog_get']} model-catalog GET + {counts['model_post']} Responses POST**, all completed;0 local budget rejection,0 observed Provider429/stream interruption. All3 Sessions use real `request_budget=None` and `timeout_seconds=None`; no USD/token or cross-session request allocation. Resource, authentication, TLS, connection, stream-idle and finite fault-retry protections remain. No retry ancestry or unobserved Provider behavior is invented. Model weights, provider billing and universal availability remain UNVERIFIED.

## Regression and evidence

1868 PASS = all1836 original exact identities +32new,0fail/error/skip. Raw JUnit SHA85633c14909c72447000f648bc7582cc8e10b35dcdd010850ba2d8d3af25da7e. The trusted regression still requires explicitly read-only historical corpus mappings inside its namespace; no permanent mappings or Participant history access were added.15 inherited CLI checks pass, including expected Smoke/A/D buggy FAIL, reference PASS, alternative flock PASS, B/C NOT_IMPLEMENTED, ERROR and TIMEOUT. Six unchanged JS contracts and actual public source/wheel/sdist selection/build/privacy scans pass. No new browser tour or claim of new UI visual acceptance is made.

Old Full was freshly rehashed:35792 ordinary files /2374193252 bytes plus stored symlink records unchanged. Historical S1 ERROR/NOT_RUN, its later28/28 diagnostics, Host-controlled seed and old S2 no-inheritance remain historical facts. Full/Lite checksum roots, independent verifier, privacy scan and extracted verification are in the external delivery receipt, produced after this report and terminal Full seal to avoid hash cycles.

## Remaining conditions

S2 retrieved S1's published experience but did not explicitly build/record a decision for it. The selected prior SQLite experience and both actual patches are strategy-compatible; this does not establish adoption of the newly published item. Also, the post-feedback full graph currently fails MCP resolve at the262144-byte wire limit.22 controlled checks on a disclosed COPY excluding only later S2 OBSERVED_OUTCOME links are bounded evidence, not recovery of that full-corpus failure. These two gaps prevent candidate PASS.

No Memory/Raw Memory comparison: CONTROL_NOT_RUN. CAUSAL_BENEFIT=UNKNOWN. Native mode is SINGLE, no new multi-agent claim. Same-template D-v01 instances do not establish broad generalization.
''')
doc('NATIVE_AGENT_LIFECYCLE_REPORT.md',f'''# Native lifecycle

New official authenticated Sessions, not developer SDK simulations: S1 `{s1['session_id']}`, S2 `{s2['session_id']}`. Complete official rollout and exec JSONL, typed MCP calls, scoped JSONRPC, actual Gateway transport, original patches and Runner/JUnit live under each Run. RAW_EVIDENCE_INDEX.json and typed_event_index.jsonl pin original bytes/line numbers. Official exec events without timestamps retain arrival order; no clocks are invented.

S1 patch `{s1['patch_sha256']}`: removes the stale-snapshot absolute inventory branch; keeps conditional relative write inside existing transaction with order/ledger coherence. Decision precedes first observed patch, source verifier matches actual proposal body/request/reply plus official typed completion. Candidate begins UNTRUSTED, passes strict same-run source verification, then Host scope/semantic review and bounded publication. Source verification is local trusted authority, not outside attestation. The existing verifier's historical source_epoch string H3_NEW_NATIVE_SESSION was not relabeled; actual V5C source commit/tree/hashes and Run identities identify this execution.

S2 patch `{s2['patch_sha256']}` independently formed in a fresh faulty task workspace, not copied by Host. Original native exit0, original independent28/28 and fresh Session are verified. Natural S2 proposal remains PROPOSED and is not automatically published. Host feedback records observed exposure, not proof of adoption; attribution remains UNKNOWN.

The outer S1 collector exit1 is a post-run duplicate seal error, retained separately. Preflight FAIL0/8 is preserved. Actual tool errors and all first failed infrastructure/control attempts are retained. No original Run is rescored or replaced.
''')
doc('CROSS_SESSION_INHERITANCE_REPORT.md',f'''# Cross-session inheritance — PARTIAL

S1 Agent candidate was independently verified and published as `{inherit['new_experience_id']}`. Host-only selection checked A=ABSTAIN/D=APPLY, following the pre-registered rule. S2 received only a fresh D-v01 public task, not that ID, S1 patch/grade/messages or old session state. Same template supports instance-level transfer only.

S2 actual resolve returned the new item with APPLY and actual support paths tied to S1's VerifiedOutcome. Query and official event raw references are in inheritance_trace.json. However, **new-item explicit bundle calls=0; new-item record_decision calls=0**. Its actual selected ID is `experience:sqlite-atomic-reservation`, which predates S1. A strategy-compatible diff and28/28 cannot prove which returned item caused the action. Consequently the specific positive inheritance requirement is NOT ACHIEVED and new-item adoption remains UNVERIFIED.

No follow-up prompt forced a designated ID or tool metric. No extra main challenge was launched to replace this result. Host-controlled graph tests are separately labeled and do not fill the model-action gap. CAUSAL_BENEFIT UNKNOWN; CONTROL_NOT_RUN; NATIVE SINGLE.
''')
doc('SOURCE_AND_TRUST_BOUNDARY_DELTA.md','''# Source and trust boundary delta

Only public MCP typed schema, safe repairable errors, and discretionary reflection wording changed; plus32 additive tests. Host-pinned authority, unknown semantics, internal public-fact vocabulary, Core graph evaluation, business/Runner/Oracle/reference and original test assertions are unchanged. Public context exposes exactly8 optional scalar facts; worker_count_known is strict bool/null. No invented closed enums or private pinned values. Claim types cannot upgrade unknown trusted facts.

Official MCP SDK public list_tools/call_tool hooks and Pydantic schema are reused. See ROOT_CAUSE_AND_FIX.md and closure_source_patch.diff. Provider/request policy is external configuration, real None semantics, not an enormous finite cap. Default historic bounded behavior remains available and is not misrepresented as this cohort's configuration.

Physical namespace regression6checks passes and all3 actual native Runs report isolated credential-free participant and complete cgroup cleanup. This is a shared-kernel boundary, not hostile-kernel/VM proof. DB/admin/Gateway secrets remain trusted-host-only external files. Public builds are allowlisted and scanned; Full and Audit-Lite are maintainer audit evidence, never Participant inputs. Full contains private Oracle and history source; Lite excludes them and supplies scored projections and byte hashes.

The full post-S2 graph hits the pre-existing262144-byte MCP bound. No bound was enlarged, source changed, edge deleted in the live graph or synthetic fallback installed. The control COPY's explicit omission of only later S2 exposure links is recorded, not an equivalence claim. Future minimal transport/projection remediation would need a separately frozen patch, preserved snapshots, size/fail-closed/authority regression and fresh integration verification; no such fix is delivered here.
''')
doc('FAILURES_AND_LIMITATIONS.md','''# Failures and limitations

## Newly executed failures (retained)

- Physical precheck first launch: missing native-binary environment, before physical execution; external launch corrected and six checks passed.
- Live graph initializer first call: keyword-only API incorrectly called positionally; corrected outside product; no fake graph/Outcome.
- First preflight harness: nonexistent validate() API, before native Session/model request; corrected to real dataclass validation.
- Real S0 original Oracle FAIL0/8. Natural native0/submission/integration PASS, task failed at conservation-constraint audit. Untouched patch/grade preserved.
- S1 outer collector duplicate seal FileExistsError after already completed native0/PASS28 sealed Run. Existing manifest byte-verified; no reseal/regrade/rerun. S2 collector respects existing seal.
- S1 three actual MCP errors, S2 one actual MCP error. Context conflicts were safely generic and query IDs were not accepted when malformed. Models recovered; raw failures retained.
- C4 complete post-S2-feedback corpus: actual MCP MESSAGE_SIZE_LIMIT and EOF. No static success fallback. Remains UNFIXED.
- Bounded-copy C4 retry1: harness expected SDK isError for forbidden publication tool; actual broker correctly closed at TOOL_NOT_ALLOWED. New retry asserts EOF+exact broker reason+unchanged graph in separate channels.22 controls pass; no original assertions/product changes.
- S2 natural new-item adoption incomplete despite retrieval and engineering PASS. No forced follow-up/replacement.

## Historical boundaries retained

Old S1 ERROR/NOT_RUN and postmortem28/28, Host seed, failed old S2 are not upgraded. AOF reload139, native D-v02 UDS EPERM and historical Gateway large-request race are not fixed or revalidated as resolved. Graceful RDB SAVE/stop/start proves only saved-state normal restart, not crash-tail/power-loss durability. Shared kernel/CPU-controller limits remain. Provider weights/billing, model prompt-injection immunity, hostile-host security, causal benefit and broad task generalization remain UNVERIFIED/UNKNOWN. No new retry failure was observed; retry ancestry beyond actual recorded fields is UNAVAILABLE.

Full/Lite are local integrity chains, not third-party attestations. Finite redaction scans cannot prove absence of all unknown secret encodings. No comparable no-memory cohort or new multi-agent child proof. No new browser visual tour. No merge/push/Gen2 authorization was exercised.
''')
doc('UNRESOLVED_ISSUES.csv','''id,status,issue,evidence
U1,UNVERIFIED,S2 did not explicitly decide on newly published S1 experience,04_live_s2/inheritance_trace.json
U2,FAIL_UNFIXED,Post-feedback complete graph exceeds MCP message bound,05_negative_controls/FULL_CORPUS_MESSAGE_LIMIT_FAILURE.json
U3,UNKNOWN,Causal benefit without comparable control,07_audit/GATE_RESULTS.json
U4,PARTIAL,Shared-kernel and CPU controller limits,07_audit/OWNED_RESOURCE_CLOSURE.json
U5,UNVERIFIED,Historical AOF139 and nativeDv02UDS recovery not newly fixed,07_audit/FAILURES_AND_LIMITATIONS.md
U6,UNVERIFIED,Provider internal weights and billing,07_audit/REQUEST_POLICY_RESULT.json
''')
doc('REVIEW_GUIDE.md','''# Independent review entry

Read V5C_FULL_VALIDATION_REPORT.md, CLAIM_EVIDENCE_MATRIX.csv, FAILURES_AND_LIMITATIONS.md and CROSS_SESSION_INHERITANCE_REPORT.md first. Verify external ZIP SHA and externally supplied stdlib verifier before opening the Lite. Full manifest pins complete local evidence; Lite maps original SHA to sanitized/projection SHA and every native/MCP JSONL line without reordering. Gate results remain conditional even when package integrity passes. Terminal packaging receipts outside the sealed Full identify final ZIP/file count/hash and read-only verifier results.

Agent/code/Oracle/Host are distinct authorities. A successful package verification checks archival consistency, not causal benefit, universally correct business code or complete S1→S2 adoption. Nothing here authorizes Gen2 or merging the isolated patch.
''')
print('REPORTS_WRITTEN',len(commands),'commands',counts)
