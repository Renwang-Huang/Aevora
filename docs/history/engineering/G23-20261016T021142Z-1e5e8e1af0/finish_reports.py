from audit import *
import shutil,csv,subprocess
R=E/'reports';s1=json.loads((E/'04_live/S1_05/ORIGINAL_RUN_SUMMARY.json').read_text());s2=json.loads((E/'04_live/S2/ORIGINAL_RUN_SUMMARY.json').read_text());tr=json.loads((E/'04_live/S2/TRANSFER_VERIFICATION.json').read_text());fb=json.loads((E/'04_live/S2/HOST_TRUSTED_FEEDBACK.json').read_text());assert fb['status']=='PUBLICATION_COMMITTED';assert json.loads((E/'06_cold_recovery/RESULT.json').read_text())['status'].startswith('PASS')
(R/'G23_CROSS_SESSION_TRANSFER_REPORT.md').write_text(f'''# G23 Accountable Cross-Session Transfer

## Observed closed chain

S1 original run `{s1['run_id']}`, official session `{s1['session_id']}`, original28/28PASS, patch `{s1['patch_sha256']}`. Three verified actual native children. Natural proposal was independently admitted and Q07 published, epoch2. Receipt and stable Experience are in G23_NATIVE_SOURCE_ADMISSION_REPORT.md.

S2 original run `{s2['run_id']}`, **different** official session `{s2['session_id']}`, three verified actual native children, original28/28PASS, patch `{s2['patch_sha256']}`.93 actual upstream requests, request_budget=None. New public defective workspace and SQLite execution; no S1 patch, conversation, native state or hidden answer mounted. The unchanged public issue and generic optional tool reference contain no selected Experience ID.

Actual observed Experience `{tr['experience_id']}`; Query `{tr['query_id']}`; Recommendation `{tr['recommendation_id']}`; Decision `{tr['decision_id']}`. Core recommendation **{tr['core_verdict']}**, participant decision **{tr['agent_decision']['decision']}**. These are different authorities. Do not upgrade VERIFY to APPLY.

`04_live/S2/TRANSFER_VERIFICATION.json` asserts the exact successful MCP request/reply joins and actor, full witness/document SHA equality, COMPLETE recommendation and no integrity issues, actual S1 revision/receipt, query -> complete bundle -> persisted decision -> official business file edit order, new original independent Outcome, and patch/report SHA. Original raw line/file hashes are retained. Host semantic review reads actual patch bytes: transaction-local guarded relative SQLite mutation, atomic order/ledger update, no process-local lock reliance. The public facade/concurrency/recovery passes the original Oracle. S2 removes the internal optional snapshot keyword; broad undocumented-internal-API compatibility is not claimed.

This supports **observed accountable transfer with a VERIFY-led engineering action**, not proof that the result would differ without memory. Both are independent instances of D/v01, not unseen task-family generalization. The supplied principal was explicitly treated as a hypothesis and checked with actual investigations/tests.

## Trusted feedback

S2's actual natural proposal is separately source/outcome/review verified in `NATURAL_SOURCE_ADMISSION.json`, retained in its original wording, not silently republished as a new S1 principle. Trusted Host uses the exact S1 principle bytes with the **actual S2 independent Original Oracle**, bounded scope and explicit Host-authored follow-up. This follow-up is classified `HOST_TRUSTED_FOLLOWUP_NOT_NATURAL_AGENT_PROPOSAL`, never mislabeled Agent-origin.

Q07 new receipt `{fb['receipt']['id']}`, epoch{fb['receipt']['epoch']}, same Experience `{fb['experience_id']}`. A new revision/supporting independent Outcome supersedes the prior revision through real graph relations while retaining original nodes, failures and immutable receipts. `GRAPH_BEFORE_FEEDBACK.json` and `GRAPH_AFTER_FEEDBACK.json` plus raw Host receipts provide exact graph deltas. Causal attribution remains UNKNOWN.

First Host follow-up helper attempt used an invalid colon in its **Host-authored candidate key** and was rejected by unchanged schema. The helper key was corrected; all original failure receipts and first graph snapshot were preserved. No participant proposal, Oracle or old source was altered to recover.

## Final limits

Causal benefit UNKNOWN, CONTROL_NOT_RUN. No statistical Graph/Raw/No Memory conclusion. Same kernel/UID remains ISOLATION_PARTIAL. Original owned DB SIGSEGV139 root cause UNVERIFIED despite exact lastSAVE recovery, instance separation and current cold verification. No internal model weights proof or full Gateway HTTP bodies are manufactured.
''')
with (R/'G23_NATIVE_MULTI_AGENT_REPORT.md').open('a') as f:f.write(f'\n## S2 terminal supplement\n\nOfficial fresh session `{s2["session_id"]}`, original Run `{s2["run_id"]}`: runtime/integration/native Multi PASS, three verified children, original28PASS, actual new-Experience full bundle/VERIFY/action.93 upstream requests. Every actual429/resource rejection and stream disconnect remains in its raw transport log, not silently reported as error-free.\n')
for n in ['G23_AGENT_IDENTITY_AND_TOOL_TIMELINE.csv','G23_ORIGINAL_RUN_OUTCOME_MATRIX.csv']:shutil.copyfile(E/'analysis'/n,R/n)
claims=[
 ('REAL_AUTHENTICATED_MODEL','PASS','04_live/S1_05/runs/'+s1['run_id']+'/gateway_transport_events.jsonl','Authenticated new official native sessions; labels do not attest weights'),
 ('NATIVE_MULTI_AGENT','PASS','analysis/S1_05-official-analysis.json','Three verified children in S1 and S2; own tools and typed completion receipts'),
 ('GRAPH_GROUNDED_DECISION','PASS','04_live/S2/MCP_EXACT_JOIN.json','Core APPLY and Agent VERIFY retained separately'),
 ('REAL_CODE_ACTION','PASS','04_live/S2/runs/'+s2['run_id']+'/submission.diff','Actual participant app patch, original extraction; no reference substitution'),
 ('ORIGINAL_INDEPENDENT_OUTCOME','PASS','04_live/S2/runs/'+s2['run_id']+'/evaluation_report.json','S1_05 and S2 original28/28PASS; old ERROR/NOT_RUN retained'),
 ('NATIVE_PROPOSAL_TO_TRUSTED_PUBLICATION','PASS','04_live/S1_05/HOST_PUBLICATION.json','Exact root actor/body/candidate, Host original Outcome/Scope, real Q07'),
 ('CROSS_SESSION_ACCOUNTABLE_TRANSFER','PASS','04_live/S2/TRANSFER_VERIFICATION.json','Observed VERIFY -> aligned engineering action -> original Oracle, not causal benefit'),
 ('TRUSTED_FEEDBACK','PASS','04_live/S2/HOST_TRUSTED_FEEDBACK.json','Actual independent S2 Outcome, stable Experience, explicit Host follow-up Q07'),
 ('NEGATIVE_TRANSFER_AND_GOVERNANCE','PASS','05_controls/native-source-copy-2/RESULT.json','Real native ABSTAIN old lock; controlled real-graph mechanisms separately classified'),
 ('NATIVE_SOURCE_POLLUTION_CONTROLS','PASS','05_controls/ACTUAL_NATIVE_SOURCE_NEGATIVES.json','12 actual-input positive/negative checks, plus new46 tests'),
 ('REGRESSION_2063_PLUS46_CONTRACT86','PASS','10_regression_final/EXACT_IDENTITY_RECEIPT.json','Exact unredacted inherited JUnit identities; no skip/failure/error'),
 ('PUBLIC_PRODUCT_AND_BENCHMARK','PASS_BOUNDED','09_release_final/clean-smoke-final/RESULT.json','17 real wheel/SDK/HTTP checks,15 CLI contracts; no new Chromium claim'),
 ('PERFORMANCE','PASS_BOUNDED','05_performance/PAIRED_COMPARISON.json','64x8 actual paired20 samples, no new100k/300k claim'),
 ('ISOLATION','ISOLATION_PARTIAL','01_native/physical/summary.json','Actual physical/official command probes; shared kernel/UID'),
 ('OWNED_DB_RECOVERY','CONDITIONAL','reports/G23_DATABASE_FAILURE_AND_RECOVERY.md','Actual signal11/139 OOMfalse, root causeUNVERIFIED; lastSAVE and cold restore pass'),
 ('EVIDENCE_ACCOUNTABILITY','PASS_LOCAL_PINNED_NOT_EXTERNAL_ATTESTATION','04_live/S2/TRANSFER_VERIFICATION.json','Exact raw joins, original outcomes and receipts; final Full/Lite pins external'),
 ('CAUSAL_BENEFIT','UNKNOWN','reports/G23_LIMITATIONS_AND_UNKNOWN.md','CONTROL_NOT_RUN; G24 not started')]
with (R/'G23_CLAIM_TO_EVIDENCE_MATRIX.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['claim','status','evidence_path','sha256','scope']);w.writerows((a,b,c,sha(E/c),d) for a,b,c,d in claims)
gates={str(i):'PASS_BOUNDED' for i in range(9)};gates['6']='CONDITIONAL_ENGINE_ROOT_CAUSE_UNVERIFIED';gates['8']='FINAL_LOCAL_INTEGRITY_CHECKS_REQUIRED_BEFORE_SEAL'
# This initial terminal draft is replaced only before sealing, after integrity
# checks. Old intermediate receipts are never changed.
write(R/'G23_GATE_FINAL_STATE.json',dict(at=now(),authority='FINAL_SOURCE_AND_TERMINAL_DELIVERY_POINTER_AFTER_SEAL',overall='G23_CONDITIONAL',reason='Functional Native/Q07/S1-S2/Oracle/feedback/governance chain PASS; pinned FalkorDB engine SIGSEGV root cause remains UNVERIFIED and shared-kernel isolation remains PARTIAL',gates=gates,claims={a:b for a,b,c,d in claims},causal_benefit='UNKNOWN',control='CONTROL_NOT_RUN',G24_STARTED=False,GITHUB_PUSH=False,runtime_code_commit='8e148f0852a961ca9f2e81bbdb5b9cb69022f450',runtime_gate_sha256=sha(E/'G23_LIVE_GATE_V4.json'),final_source_identity='source/SOURCE_IDENTITY.json',final_delivery_external='/home/PRIVATE_MAINTAINER/data_storage/aevora_review_exports/'+E.name+'/FINAL_DELIVERY_RECEIPT.json'))
(R/'G23_G24_ENTRY.md').write_text('''# Stop at G23 / Independent Review Handoff

G24_STARTED=false. No next phase, push, baseline merge, cleanup or model challenge after G23 closure is authorized here. Review the Full/Lite exact raw provenance and outcomes first.

Carry forward: actual source epoch, official protocol variants and actor identity contract; default disabled/legacy four-tool compatibility; explicit v2 profile and bounded transport; unknown before-fact PENDING; original Oracle and trusted Host only. Follow up the real engine139 root cause and native resource429 behavior with preserved diagnostics before any reliability expansion. Same-kernel/UID remains PARTIAL. No causal benefit or unseen-family generalization is established. Future Graph/Raw/No Memory experimental design requires separate authorization.\n''')
(R/'G23_FINAL_IMPLEMENTATION_REPORT.md').write_text(f'''# Aevora Gen2 G23 Final Implementation Validation

## Rating: G23_CONDITIONAL

**The functional Native Multi-Agent -> exact native Source -> Original Oracle -> Q07 -> fresh Session retrieval/decision/code -> new Original Oracle -> trusted feedback chain is PASS.** Overall remains CONDITIONAL because a real pinned owned FalkorDB SIGSEGV139 occurred during this gate; its root cause is UNVERIFIED, although isolated re-execution and explicit cold recovery pass. Physical isolation is tested but remains shared-kernel/UID PARTIAL. This is not G24 or a causal learning-benefit claim.

## Source and changes

Base e9e7a7a422828e847b237fa8d3e0450b98a97804/tree b63c0dda2fc0451eba6ee76a9196aadb8c7bf2e7, independent bare clone/worktree. Tested/live code commit8e148f0852a961ca9f2e81bbdb5b9cb69022f450. Final Git/tree/diff/SHA and documentation-only follow-up are recorded in source/SOURCE_IDENTITY.json. Frozen first-generation547 bytes unchanged; G21/G22 Full manifests reverified. No protected business/Oracle/reference/scenario/old-test bytes changed.

Reused official CLI/Runner/Oracle/Broker/Q07 and current graph arbitration. Added explicit v2 native Runtime bootstrap/profile, protected exact actor/proposal source admission, official observed typed event compatibility, public exact tool/fact reference and 46 new tests. One proven Core predicate-mode compatibility fix; original red reproduction retained. See SOURCE_AND_TRUST_BOUNDARY_MAP and source diff.

## Actual acceptance

| Check | Current observation |
|---|---|
| Inherited developer regression |2063 PASS, exact original classname/name identities|
| New G23 tests |46 PASS|
| Contract checks |86 PASS|
| Independent Benchmark CLI |15 contracts PASS, including expected buggy FAIL and ERROR/TIMEOUT classifications|
| Clean public wheels/Core/MCP/Console |17 PASS, actual official SDK/HTTP, public source bytes unchanged by final adapter notes|
| Paired 64×8 read perf |20+20 real samples, currentp95 3.09725s vs baseline3.13414s; complete witness equivalence|
| S1_05 |original28PASS,3 verified children, actual natural Source/Q07 committed|
| S2 |original28PASS,3 verified children, fresh session actual new-Experience VERIFY/action|
| New actual-input source controls |12 PASS, separately classified|
| Actual native-publication graph copy |8 PASS, includes true MCP cache revocation|
| Post-feedback recovery |explicit SAVE+graceful restart, exact graph fingerprint retained andAPPLY|

## Commands and raw receipts

Every formal invocation is in COMMAND_LOG.jsonl with commands/<label>/receipt.json plus stdout/stderr hashes, argv, exact start/end/exit. Relevant labels: epoch4-inherited-1897, epoch4-gen2-108, epoch4-host58-exact-root, public-fact-contract-host58-new46-parent-present, epoch4-contracts-86, epoch4-benchmark-cli-15, epoch4-exact-test-identity; native-s1-05, host-native-s1-05, native-s2, exact-mcp-s2, verify-s2-new-experience-transfer, s2-trusted-host-feedback-key-schema-correct; actual-native-source-positive-negative, real-native-publication-graph-controls-policy-correct; live-post-feedback-before-cold, owned-live-graceful-stop, owned-live-cold-start, live-post-feedback-after-cold. Production runtime calls use E/runtime.py profiles; full exact argv is the authority, not abbreviated prose.

## Failures and limits

No first failure omitted: initial Provider ERROR/NOT_RUN, S1_02 invalid proposal, S1_03 engine outage/no candidate, S1_04 two exact-source PENDING unknown premises, actual429/disconnects, original regression errors under crashed shared DB, helper fixture/argument errors, initial wrong revocation audit expectation and invalid Host feedback key. See FAILURE_LEDGER and original outcome matrix; successful new runs never overwrite earlier scores. The old stopped crashed container/RDB/bugreport remain.

Full is PRIVATE_MAINTAINER_FULL; Lite is INTERNAL_MAINTAINER_REVIEW, never Participant/public. Secret/individual-key-hash scanning and actual independent package positive/wrong-pin/tamper verification are recorded at final delivery. SourceLinks preserve original/export hashes for redaction and lossless gzip. Full upstream HTTP bodies NOT_CAPTURED; local seals are not external attestation. CAUSAL_BENEFIT=UNKNOWN, CONTROL_NOT_RUN.

All next-phase work is stopped; no GitHub push, cleanup, frozen merge, Oracle modification, model-weight attestation or new Console visual claim.
''')
print('Reports and matrix generated; final seal/gate validation still required')
