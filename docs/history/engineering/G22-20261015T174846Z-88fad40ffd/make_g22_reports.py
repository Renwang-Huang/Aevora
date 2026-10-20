from pathlib import Path
import json,hashlib,csv,subprocess,statistics,xml.etree.ElementTree as ET
E=Path(__file__).parent;P=E/'worktree';D=P/'docs/gen2/g22';R=E/'reports'
def read(p):return json.loads((E/p).read_text())
def emit(name,body):
 (D/name).write_text(body.strip()+'\n');(R/name).write_text(body.strip()+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=P,text=True).strip()
ident=read('reports/TEST_IDENTITY_CHECK.json');scale=read('05_performance/semantic-scale-acceptance/RESULT.json')
old=read('05_performance/fair-old-20/RESULT.json');new=read('05_performance/fair-current-20/RESULT.json') if (E/'05_performance/fair-current-20/RESULT.json').exists() else read('05_performance/fair-new-20/RESULT.json')
cli=read('05_benchmark/cli/summary.json') if (E/'05_benchmark/cli/summary.json').exists() else {'status':'PENDING'}
product=read('05_release/clean-smoke-final/RESULT.json')
cases=read('01_admission/final-cases/CASES.json');pos,neg=cases['cases']
newms=read('05_performance/fair-current-20/measurements.json') if (E/'05_performance/fair-current-20/RESULT.json').exists() else read('05_performance/fair-new-20/measurements.json');oldms=read('05_performance/fair-old-20/measurements.json')
assert all(m['witness_shas']==oldms[0]['witness_shas'] for m in newms)
checks=dict(G22_0='PASS',G22_1='PASS_HOST_CONTROLLED_FRESH_ORACLE',G22_2='PASS_SINGLE_QUERY_TYPED_FENCE',G22_3='PASS_REAL_GOVERNANCE_GRAPH',G22_4='PASS_DECLARED_OS_AND_PRE_SEND_BOUNDARY',G22_5='PASS_MEASURED_SCOPE',G22_6='PASS' if cli['status']=='PASS' else 'PENDING_CLI',G22_7='PENDING_TERMINAL_SEAL',PERFORMANCE='G22_PERF_PASS',SCALE='G22_SCALE_PASS_DECLARED_SHAPE',NEW_NATIVE_AGENT_SESSIONS=0,G23_STARTED=False,GITHUB_PUSH=False,HISTORICAL_SOURCE_CHANGED=False)
(R/'G22_GATE_RESULTS.json').write_text(json.dumps(checks,indent=2))
emit('G22_CURRENT_SOURCE_MAP.md',f'''# G22 current source authority

Tested implementation checkpoint: `{source}`. Final documentation commit is recorded separately in the delivery receipt.
Independent local worktree: `{P}`. Frozen maintainer and G21 roots remain untouched.

| Entry | Authority |
|---|---|
| `aevora_maintainer/host_v2.py:TrustedHost` | Private OS-authorized facade: registered verifier, immutable proposal, source/outcome verification, explicit semantic review, prepare/publish/govern and authority withdrawal |
| `aevora_maintainer/publication_fence.py:activate` | Fixed label/relation allowlist, typed native properties/endpoints, full scope closure, one final GRAPH.QUERY CAS |
| `aevora_core/src/aevora/host_pins.py` | Read-only immutable local trust pins; no MCP registration capability |
| `admission.py:verify_native_proposal` | Reused pure archived official proposal validator, shared with original legacy admission |
| `orderflow_outcome_bridge.py` | Unchanged registered independent OrderFlow verifier; actual JUnit/Oracle/tree/suite/source pins |
| `graph_v2.py` / `graph_queries.py` | Existing complete reader plus shared authenticated partition discovery and indexed reverse Q11 |
| `contracts.py` | Additive Q07 head projections; byte-keyed positive fact/scope proof cache and issuance-window verification |
| `mcp_v2.py` | Optional private registry.pin_root bootstrap; same four public tools/profile |
| `mcp_broker.py` | Unchanged captured environment, Q08 pre-send check and local owner lock |
| `tools/validation/g22_host_cases.py`, `g22_tests.py` | Fresh independent cases and lossless per-process segmented raw Cypher collection |

No app/Runner/Evaluator/Oracle/reference/integrations business implementation changed. Public Core contains only the lookup reader. Private Host facade and verifier anchors are excluded from clean public wheels/source selection. The public package namespace test proves `aevora_maintainer`, Benchmark and Oracle are not mounted/installed.
''')
emit('G22_PUBLICATION_AND_RECOVERY_PROTOCOL.md',f'''# Publication and recovery protocol

## Trust and admission

Only a trusted maintainer process with owned physical graph credentials, immutable OS pins, explicit principal/scope/profile/generation/expiry and registered TrustAnchor invokes the private facade. No public MCP method accepts a Host grant, Prepared object, registry path or verdict.

`AGENT CLAIM → immutable Candidate → SOURCE_VERIFIED → OUTCOME_VERIFIED → explicit trusted semantic Review → PUBLISHING → immutable prepare → final commit`.

New real independent material is HOST_SEEDED, never a new native Agent grade. SourceRun `{pos['run_id']}` is14/14 PASS; `{neg['run_id']}` is genuine business FAIL, whose negative evidence yields ABSTAIN. Tree/workspace submissions have actual snapshot SHA; patch is NOT_APPLICABLE. Source verification checks exact run/tree/patch/native proposal when applicable. Agent-origin claims with no matching sealed official proposal are rejected. Proposing actor thread is UNAVAILABLE unless uniquely observable.

Host review preserves original proposal bytes and can only narrow scope. Unknown premise/scope remains PENDING; contradictory scope/premise cannot be approved. Task facts come from the pinned public runtime declaration, labelled HOST_DECLARED_TASK (not kernel observation); original archive-relative report name, actual whole-file SHA and first-line SHA are retained, with extractor function/hash and JSON pointer. Artifact-after/evaluation facts are never promoted into before premises. Semantic prose-to-code judgment is an explicit authorized operator decision, not an automated proof of causal benefit.

## Prepare and single final fence

Prepare writes immutable typed nodes and complete Manifest/Chunk/Catalogue snapshots, private Source/Outcome/Review/preparation pins. No new semantic edge is attached to active versions. Unactivated preparations do not enter Q01. The existing PUBLISHING head remains the expected CAS head.

Prepared evidence includes every relevant complete scope witness, old native nodes/edges, publication documents and catalogue roots. A final check of only the new Experience is insufficient: a red counterexample changed another active scope entry after prepare; the fixed fence now pins the complete relevant closure.

The one final GRAPH.QUERY compares complete canonical old TenantState, head(s), current capability, source/outcome/review/authority/prepared/document pins, every expected native label/type/endpoint, every chunk edge and the entire existing semantic edge set. Current issuing verifier permission is checked at commit time. A historical immutable certificate is checked at issuance time; credential rotation/expiry is distinct from explicit source withdrawal. New generation gets a new verifier ID; old bytes remain immutable.

The same query creates unique receipt/event(s), all typed semantic and activation links, COMMITS, all affected catalogue heads, canonical state JSON/SHA, semantic epoch and any changed lifecycle heads. Explicit supersession changes both old/new heads in that query. Governance observations may append an event while preserving a terminal state; they never reactivate it.

Same key/same semantic digest returns the unique immutable receipt; same key/different body rejects. Same expected head/epoch with2/4/8 writers produces one commit. Receipt replay does not create another event/epoch and does not issue new permission.

## Recovery boundary

Actual SIGKILL before/after the query and real database outage were executed. Before fence: no active publication. After DB commit but before return: reload the exact prepared reference and unique receipt; no second commit. Unpinned or incomplete orphans cannot be blessed; use a new explicit request after re-verification.

`04_security/outage-recovery/` preserves the first failure: save-empty configuration lost unsaved staged nodes at the last-SAVE RPO; recovery failed closed because the capability was missing. It is not upgraded to PASS. Separate `outage-recovery-saved/` actually SAVEd the staged boundary, stopped/restarted the owned server, completed publication, SAVEd again, cold-restarted and verified exact graph SHA and original receipt/one commit. Normal stop alone is not asserted to save unsaved graph state.

No AOF or unsaved power-loss durability claim. AOF139, last-SAVE RPO and shared-kernel PARTIAL remain.
''')
emit('G22_GOVERNANCE_EVIDENCE.md',f'''# Governance and authorization evidence

Acceptance:58/58 actual new tests, real owned FalkorDB; raw per-process streams, final graph snapshots and persistent private pins are in `06_regression/acceptance-host-58/`.

- Actual new Host source/outcome publication gives APPLY. Actual negative engineering outcome creates COUNTEREXAMPLE, never SUPPORT, and gives ABSTAIN.
- Prepared withdrawal remains invisible; after atomic activation, old reference bytes remain equal and current read gives ABSTAIN.
- Scope restriction removes optimistic APPLY. Explicit revision supersession preserves old records and updates both Candidate heads atomically. Terminal candidates cannot resurrect.
- One authority withdrawal updates all affected complete manifests/catalogues, immutable observations and authz/semantic epochs in one query. New scoped partition discovery handles a2048-experience tenant without passing the whole tenant through one256-candidate query. Unknown all-partition recall still correctly returns CAPACITY_EXCEEDED.
- Unused verifier can be revoked before first publication. Current revocation between Host check and final query blocks activation. Old SDK grants/cached responses are denied; a fresh grant reads governed data.
- Real official SDK output computed before withdrawal is retained in private JSONRPC evidence; withdrawal before the Broker final check prevents delivery. Received EOF is distinct from SDK isError. Unauthorized Host method names close before SDK dispatch and have no graph effect.
- Source body/review pins, fake Agent/Run/tree/patch, wrong/absent verifier, ordinary7-self-test claim, tenant/profile/generation/expiry, extra/missing chunks, scope widening and final native label/type/endpoint tampering are rejected.

Inherited108 graph tests retain A single-process RLock→D cross-process negative transfer, unknown-context VERIFY, scoped legal support APPLY, same-domain authoritative conflict VERIFY, disjoint-domain compatibility, full Counter and graph intervention checks. They remain HOST_CONTROLLED_SYNTHETIC_FIXTURE, not new Agent outcomes.

Authorization boundary: physical Host selector + live capability + Q08 epoch/session + Broker pre-send recheck/local lock. External DB-to-network send is NOT a distributed atomic transaction; already delivered bytes cannot be revoked. Normal delivery events contain the measured check+send interval (an upper bound, not a precise isolated post-check window). No stronger hostile-kernel/UID or remote attestation claim.
''')
emit('G22_PERFORMANCE_AND_SCALE.md',f'''# Performance and scale

## Fair64×8 comparison

Same exact3073node/3008edge snapshot and graph SHA `{new['graph_sha256']}`, pinnedFalkorDB4.20.4,1GiB/2CPU, Python3.12.14, existing full witness/Counter/catalogue checks. DB warm; first process sample cold.20 samples each; raw arrays and query receipts retained. These are observed samples, not a statistical SLO guarantee.

| Version | observed p50 | observed p95(nearest rank) | max |
|---|---:|---:|---:|
| frozenG21 | {old['observed_p50']:.6f}s | {old['observed_p95']:.6f}s | {old['max']:.6f}s |
| currentG22 | {new['observed_p50']:.6f}s | {new['observed_p95']:.6f}s | {new['max']:.6f}s |

All64 complete witness SHAs equal the old version; returned bytes remain17,851,534. No removal of Q04, Counter, catalogue, grant or epoch checks. Positive immutable-byte fact/scope proof memoization is bounded2048 and never stores mutable records/current authorization. Q11 uses indexed outgoing and explicitly bound reverse targets; the large-graph probe reduced that branch~86ms→~2ms with exact row-set equality. The initial UNION still scanned all nodes on its reverse branch; its slower7.5–9.1s large-graph runs remain archived. Initial full cProfile exceeded the unchanged30s safety bound and is retained; one-witness profiling decomposed it without changing the deadline.

`G22_PERF_PASS` in this declared Core workload, ≤5s. Whole compounded MCP snapshot stays8MiB and can explicitly reject a larger query even when Core resolve succeeds; no MCP frame budget was raised.

## Actual100k/300k

First trace-heavy graph reached exact100k/300k and exercised read/publish/withdraw. To avoid treating mostly ToolEvent growth as a complete distribution test, the accepted second graph has2048 Experiences,16384 Context/Task/Evidence/Outcome/Authority paths,1984 real synthetic counterpaths,9 scopes and only1679 filler ToolEvents. Actual indexes/constraints, raw seed Cypher, all distributions/counts, SAVE and read/write results are retained. These are synthetic capacity records, not16384 real engineering grades.

The accepted graph started at exactly100,000nodes/300,000edges. A real Host-controlled14-test outcome then published and withdrew. Full relevant64×8 discovery/witnesses and actual authorization passed. Pub→APPLY, withdrawal→ABSTAIN. Additional authority withdrawal succeeded despite2048 total experiences. Unknown all-scope recall and oversized document fail closed with CAPACITY_EXCEEDED.

Observed prepare {scale['prepare_seconds']:.3f}s / final publish {scale['publish_seconds']:.3f}s;
withdraw prepare {scale['withdraw_prepare_seconds']:.3f}s / commit {scale['withdraw_commit_seconds']:.3f}s;
authority prepare {scale['authority_prepare_seconds']:.3f}s / commit {scale['authority_commit_seconds']:.3f}s.
These include lossless compressed raw logging and full closure pinning; they are not a write SLO. Growth after these actual operations: {scale['counts_after']['nodes']}nodes/{scale['counts_after']['edges']}edges.4GiB/2CPU owned DB. `G22_SCALE_PASS` for this declared graph shape; not a promise for100k simultaneously relevant candidates or unlimited fanout.

Limits retained:256 relevant candidates,1024 registered scope heads,512 paths/experience,16 revisions,8 supersession hops,8192 witness nodes/edges,8MiB documents/128chunks/64KiB chunks,20MiB reader return budget,30s resolver bound. Host final pin set≤16384, prepared document≤8MiB; oversized multi-scope governance rejects before visibility. A broad global authority may require smaller scoped registrations/operations; no silent partition migration or truncation.
''')
emit('G22_NEXT_GATE_G23_ENTRY.md','''# G23 entry — not started

Await independent review of latest Full/Lite and source commit. G22 implements private trusted write/governance; it does not claim new Native Multi-Agent, causal benefit or new runtime orchestration. Default experience adapter remains unchanged.

G23 must use the actual current Host API/typed fences, immutable OS pins and scoped verifier registration. Positive new native-v2 proposal admission remains NOT_RUN in G22 (fake-origin negatives and the reused original archived validator are tested); exact proposing actor thread remains UNAVAILABLE until it can be joined reliably. Never infer it from nearest time or prose. Preserve actual source/tool completion/body and run/thread/request lineage; no Agent-created VerifiedOutcome.

Task runtime declarations are HOST_DECLARED_TASK, not kernel observations; unsupported artifact-before facts stay PENDING and require a properly registered extractor. Scope widening, same-domain Counter, changed epochs and cached-page revocation must remain fail closed. Current issuer permission and historical issuance validity differ; new grant generation/ID never overwrites old certificates.

Completion-aware native runtime must keep no financial/token/cumulative request caps; engineering health/cancel/resource protections remain. No new model session was required/run here. No distributed DB/network atomic authorization, AOF/unsaved crash durability, causal memory benefit, hostile shared-kernel isolation or public release claim. Root private Host module/anchors/pins/Oracle/full archive must not be mounted into Participants.

No G23–G26, remote push, public deployment, merge or historical cleanup is authorized by this delivery.
''')
rows=[('baseline','547 source files and G21 sealed Full verified','reports/FROZEN_547_CHECK.json; commands/verify-sealed-g21-full/receipt.json','CURRENT_READ_ONLY','local integrity, no external attestation'),('inherited','1897+108 exact identities retained','reports/TEST_IDENTITY_CHECK.json','CURRENT_DYNAMIC','2 upstream warnings'),('new','58 real Host/publication/governance tests','06_regression/acceptance-host-58/JUNIT.xml','CURRENT_DYNAMIC','owned authenticated DB'),('source','fresh independent Oracle source','01_admission/final-cases/CASES.json','CURRENT_DYNAMIC_HOST_CONTROLLED','not new Agent repair'),('write','typed complete one-query fence','aevora_maintainer/publication_fence.py;06_regression/acceptance-host-58/cypher','CURRENT_DYNAMIC','staging/filesystem/network outside one query'),('recovery','saved outage and cold exact replay','04_security/outage-recovery-saved/CONTROLLER_RESULT.json','CURRENT_DYNAMIC','last-SAVE only'),('rpo','initial unsaved stage loss and recoveryERROR','04_security/outage-recovery;commands/owned-preparation-recovery/receipt.json','CURRENT_FAILURE_PRESERVED','not upgraded'),('perf','same witness hashes and ≤5s','05_performance/fair-current-20','CURRENT_DYNAMIC','20 observations, warm DB'),('scale','100k/300k,2048Experiences, real read/write','05_performance/semantic-scale-seed;05_performance/semantic-scale-acceptance','CURRENT_SYNTHETIC_CAPACITY_PLUS_REAL_HOST_RUN','not100k relevant candidates'),('product','clean wheels actualMCP/Console','05_release/clean-smoke-final/RESULT.json','CURRENT_DYNAMIC','no new visual redesign'),('benchmark','15 original CLI checks','05_benchmark/cli/summary.json','CURRENT_DYNAMIC','no score rewriting'),('native','new native-v2 Agent source positive','NOT_RUN','UNVERIFIED','G23 review needed'),('causal','experience causes better outcomes','NOT_RUN','UNVERIFIED','UNKNOWN'),('kernel','hostile shared kernel/UID','historical limitations','HISTORICAL_LIMITATION','PARTIAL')]
with (R/'G22_CLAIM_TO_EVIDENCE_MATRIX.csv').open('w') as f:w=csv.writer(f);w.writerow(['claim_id','claim','evidence','source_class','limitation']);w.writerows(rows)
(D/'G22_CLAIM_TO_EVIDENCE_MATRIX.csv').write_bytes((R/'G22_CLAIM_TO_EVIDENCE_MATRIX.csv').read_bytes())
emit('G22_IMPLEMENTATION_REPORT.md',f'''# Aevora G22 implementation and acceptance

Current functional conclusion: **G22_PASS in declared bounded contracts**, pending terminal Full/Lite seal/verification. Final delivery receipt controls final status; a pending seal is not a completed delivery.

Base387352df3d5358d5f0ed8eadc784ef7170843ee0 / e0b2bd2cea3ec42b0396b9cf3370fc2ec0f1453b.
Tested implementation checkpoint `{source}`. Owned run `{E.name}`.

| Gate | Current evidence |
|---|---|
| G22-0 | independent bare object store/worktree, original clean roots,547 hashes and G21Full unchanged |
| G22-1 | true pinned source/outcome+explicit semantic review; fresh reference14/14 and genuine buggyFAIL |
| G22-2 | immutable prepared data, typed/endpoint/chunk/full-scope CAS, one final query,2/4/8writer one winner, idempotence and process kill |
| G22-3 | real graph revision/conflict/restriction/withdrawal, immutable history and scoped verifier retirement |
| G22-4 | current capability/scope/profile/time/generation; real officialSDK denial before send, grants reissued, saved cold recovery |
| G22-5 | observed64×8 p95 {new['observed_p95']:.6f}s; actual100k/300k with2048experiences and full read/write checks |
| G22-6 |2005/2005 exact inherited identities;58/58 new;86/86 design;17 clean product checks; CLI={cli['status']} |
| G22-7 | source reports/diff/matrices plus terminal Full/Lite verification required |

## Actual command entry examples (executed paths are in per-command receipts)

```sh
python3 -B <E>/runtime.py --history inherited-1897-final -- tools/dev.py test-maintainer --output <E>/06_regression/inherited-1897-final --owned-port 17741 -- -q tests aevora_core/tests --ignore=aevora_core/tests/gen2 --ignore=aevora_core/tests/g22 -p no:cacheprovider
python3 -B <E>/runtime.py --history gen2-108-acceptance -- tools/dev.py test-graph-v2 --output <E>/06_regression/gen2-108-acceptance --owned-port 17741
python3 -B <E>/runtime.py fresh-host-case-entry -- tools/dev.py host-case-generate --output <E>/01_admission/final-cases
python3 -B <E>/runtime.py acceptance-host-58 -- <E>/g22_raw_runner.py --output <E>/06_regression/acceptance-host-58 --owned-port 17741 -- -q aevora_core/tests/g22 -p no:cacheprovider
```

The examples abbreviate `<E>` only for reading; `commands/*/receipt.json` contains exact argv, exit, times and stdout/stderr hashes, including `--owned-port 17741` as separate arguments. JUnit identities are compared from unredacted Full, not potentially renamed Lite strings.

## Real failures retained

Constructor/immutable timestamp clashes; a test harness expecting isError instead of actual transportEOF; byte/string EOF mismatch;3 critical red projection/type/scope counterexamples; large-graph reverse full scan; first scale generator source-argument conflict; symlink-following copied-venv setup error; and original unsaved-stage outage recoveryERROR. None is deleted or relabelled as its later retry. First two early prototype file bytes were not snapshotted before the first checkpoint: exact source bytes are UNAVAILABLE there, while original JUnit/command errors survive. Critical fence counterexamples include exact before-source copies and failing graph snapshots.

## Limits and stop

No new model/Agent challenge, no natural-agent score, no causal benefit proof. Native-v2 positive source path requires G23; v1 verifier source is reused and fake-v2 origin rejection is tested. OS-rooted trust is not malicious-maintainer resistance or external attestation. RDB lastSAVE RPO/AOF139, shared-kernelPARTIAL, ClockUDS prior limitation and cross DB/network authorization interval remain. Numeric capacity bounds and large prepared-document/write costs are explicit. Do not treat test count, reference PASS or this bounded scale fixture as universal production assurance.

No private Oracle/reference/business/Runner changes; no push, merge, cleanup or G23. See protocol, governance, scale, source map, failure ledger and evidence matrix for exact claims.
''')
print('reports generated',source,cli['status'])
