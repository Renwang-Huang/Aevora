from audit import *
import csv
S=json.loads((E/'01_source/AST_SYMBOLS.json').read_text());expected=(E/'02_regression/expected_test_ids.txt').read_text().splitlines()
claims=[
 ('graph','aevora_core/src/aevora/graph_repository.py','GraphRepository.query','test_aevora_graph','V3','Real FalkorDB SDK GRAPH query, no text fallback'),
 ('when','aevora_core/src/aevora/experience_resolver.py','ExperienceResolver._resolve_one','test_aevora','V3/V5','Premises, support/counterexample paths, governance and operation coverage'),
 ('mcp','aevora_core/src/aevora/mcp_server.py','create_server','test_aevora_mcp','V4/V5','Official FastMCP typed tools; proposal opt-in'),
 ('claim','aevora_core/src/aevora/mcp_server.py','ExperienceService.record_decision','test_aevora_mcp','V3/V5','UNTRUSTED_PARTICIPANT_CLAIM; not adoption or Outcome'),
 ('proposal','aevora_core/src/aevora/candidate.py','CandidateLifecycle.propose','test_h3_lifecycle','V3/V5','Run-bound candidate; no natural-origin claim before Host verification'),
 ('approval','aevora_core/src/aevora/candidate.py','CandidateLifecycle.transition','test_h3_lifecycle','V3/V5','One GRAPH write fences head; materialization spans queries'),
 ('hostsource','aevora_core/src/aevora/admission.py','verify_orderflow_candidate','test_h3','V3/V5','Host-only strict same-run sealed proposal/native thread/patch/Oracle source'),
 ('outcome','aevora_core/src/aevora/orderflow_outcome_bridge.py','verify_outcome','test_aevora_outcome','V3/V5','Local TrustAnchor allowlist, nofollow bounded read, suite/patch/source agreement'),
 ('feedback','aevora_core/src/aevora/feedback.py','ingest_outcome','test_aevora_feedback','V3/V5','Independent verified report before graph evidence; attribution UNKNOWN'),
 ('runtime','integrations/codex_agent.py','CodexAgentAdapter.execute','test_codex_agent','V2/V5','Official CLI executes; fresh state; raw native collection; no handmade team scheduler'),
 ('model','integrations/gateway_broker.py','SecureModelBroker.__enter__','test_gateway_broker','V2/V5','Private scoped Unix transport and upstream trusted credential; bounded requests'),
 ('participant','benchmark/participant_sandbox.py','participant_command','test_participant_sandbox','V2/V5','Physical mounts, unshare-net, never bypass native sandbox'),
 ('submission','benchmark/submission.py','apply_verified_patch','test_submission_fidelity','V2/V5','Expected actual tree equality and atomic renameat2'),
 ('runner','benchmark/runner.py','BenchmarkRunner.run_agent','test_runner','V2/V5','Native patch reused through manual validation and independent evaluator'),
 ('score','evaluator/runner.py','evaluate','test_evaluator','V2/V5','Exit/JUnit exact identities/skips/errors/recovery coverage'),
 ('public','tools/public_release.py','chosen','test_gen15','V4','Explicit public allowlist; internal repo never public'),
 ('console','console/src/aevora_observatory/server.py','create_app','test_h4','V4','LIVE/REPLAY explicit; live errors fallback=false'),
 ('canonical','tools/sync_public_evidence.py','synchronize','test_gen15','V4','Canonical tools/public_evidence check, vendored bytes not alternative authority')]
matrix=[]
for cid,path,symbol,pattern,gate,note in claims:
 hits=[s for s in S if s['path']==path and s['symbol']==symbol];assert len(hits)==1,(path,symbol)
 ids=[i for i in expected if pattern in i]
 matrix.append({'claim_id':cid,'function_path_line':path+':'+str(hits[0]['line'])+':'+symbol,'source_sha256':sha(W/path),'test_ids':';'.join(ids),'new_dynamic_receipt':'PENDING_'+gate,'negative':'Referenced valid test identities; new actual outcomes pending','allowed_wording':note,'disallowed_wording':'Static source alone proves live model success, hostile VM safety, adoption or causal benefit'})
with (E/'01_source/SOURCE_TRACEABILITY_MATRIX.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
graph='''flowchart TD
 Agent[New native Codex Participant] -->|codex_agent.native_command/execute| MCP[MCP scoped broker]
 MCP -->|mcp_server.ExperienceService.resolve_experience| Resolver[ExperienceResolver]
 Resolver -->|graph_repository.query / evidence_bundle| DB[(Actual FalkorDB)]
 Agent -->|participant.extract_submission| Patch[Actual patch]
 Patch -->|submission.apply_verified_patch| Runner[Host BenchmarkRunner]
 Runner -->|evaluator.runner.evaluate| Oracle[Independent pytest and DB Oracle]
 Oracle -->|orderflow_outcome_bridge.verify_outcome| Host[Host TrustAnchor]
 Host -->|feedback.ingest_outcome / admission.verify_orderflow_candidate| DB
 Host -->|candidate.transition / fenced head| DB
 DB -->|new MCP Query| S2[Fresh successor Session]
 DB -->|readonly live projection| UI[Console LIVE]
 Replay[Explicit pinned historical Replay] -->|mode REPLAY only| UI
'''
(E/'01_source/ENTRYPOINT_DEPENDENCY_GRAPH.mmd').write_text(graph)
mapping='''# Current architecture — frozen source audit

All547 path/SHA pairs were read and compared to G5. All Python source was AST parsed; static symbols, imports, call expressions and SQL/Cypher literals are independently indexed. AST call expressions have **dynamic binding UNVERIFIED**: no claim of a complete runtime call graph. The full repository includes documentation, historical reports and private tests;547 is the exact G5 manifest definition, not547 executable modules.

Public Aevora Core owns GraphRepository, evidence bundles, ExperienceResolver WHEN/WHY, immutable Query snapshots, untrusted Decision/Candidate, Host CandidateLifecycle and source verification types. Actual FalkorDB graph paths supply support, counterexample, revision/governance and provenance. Conditional premises and scope drive decisions; no Episode ID branches were observed in ExperienceResolver. Versioned graph facts exclude Query/Decision self-reference from support strength.

MCP create_server registers official SDK4tools (proposal opt-in). Public input cannot select authority/run identity/Oracle verdict/approval. MCPBroker authenticates owner capability and scoped Run, launches the actual SDK privately. Participant receives only a stdlib proxy and scoped socket. Credentials, repository and admission functions remain Host process assets. Public Core includes verifier/admission Python types, so **publicly distributed code is not secrecy of authority**; actual authority comes from pinned Host TrustAnchor, DB credentials and unreachable privileged endpoints. No publish/Cypher/outcome tools are registered.

Private OrderFlow owns public task/fixture factory, strict patch/tree fidelity, Candidate and Participant namespaces, independent hidden suites, direct SQLite Oracle and recovery coverage. Runner.run_agent collects native artifact and calls the same validated manual submission path. evaluate checks real exit, exact necessary identity multiset, no skipped items and required crash windows. Agent audit() is not Host database truth.

CodexAgentAdapter calls native codex exec --json. Its gateway uses private Unix connection with Host-held upstream key; completion-aware avoids total wall verdict but retains finite retry/idle/connect/resource controls and explicit cancellation. Official rollout/typed events and actual child lineage are independently collected; text assignments alone never count. Existing adapters and old phase scripts are compatibility/history, not this audit's write destinations.

Console has bounded readonly graph projection and three pages. Explicit LIVE failure yields unavailable/fallback=false; explicit Replay reads pinned historical Hero. Canonical standalone Hero verifier is tools/public_evidence, sync/check generates distribution copies. Public_release.chosen is explicit; internal547-file Git history remains MAINTAINER_ONLY. Product8/Maintainer19 views are convenience, not a security sandbox.

Each arrow in ENTRYPOINT_DEPENDENCY_GRAPH.mmd maps to actual symbols in SOURCE_TRACEABILITY_MATRIX.csv / AST_SYMBOLS.json. New dynamic receipts are filled after V2–V5. This static review neither certifies Provider access nor repairs.
'''
(E/'01_source/CURRENT_ARCHITECTURE_MAP.md').write_text(mapping)
(E/'01_source/EVENT_AND_CLAIM_SCHEMA.md').write_text('''# Evidence and event authority

Native thread.started.thread_id and official rollout session IDs are authoritative runtime sources; child spawn/terminal and tool lineage must be actually present. ExecutionTrace refers to raw file/line/hash; unavailable fields stay UNAVAILABLE. Broker request_records correlate actual request id, start/end, model/effort label, terminal/HTTP outcome, usage where provided; labels are not weight attestation.

MCP JSONRPC records connection_id, direction, raw_json and UTC; correlated tools/call id and structuredContent identify query_id/decision_id/candidate_id. Query records pinned trusted public facts separately from participant claims. record_decision authority=UNTRUSTED_PARTICIPANT_CLAIM, adoption=CLAIM_ONLY. Candidate provenance=UNVERIFIED_UNTIL_HOST_REVIEW.

Candidate states actually present: PROPOSED,EVIDENCE_PENDING,REJECTED,ADMITTED_BOUNDED,PUBLISHING,PUBLISHED,WITHDRAWN,SUPERSEDED. SourceVerification requires trusted Host origin and natural-agent outcome reference; ReviewGrant is local owner authority, not cryptographic third-party attestation. Lifecycle head transition is one write but publish materialization is staged.

Host TrustAnchor separately pins Run seal/source archive/allowed report; verify_outcome validates actual JUnit/source/patch/independent report. VerifiedOutcome is independent testing, not model language/self-test. ingest_outcome stores observed evidence with causal attribution UNKNOWN. New S2 must have new process/thread/model request after graph write; historical snapshots/Replay are not new inheritance.

Detailed actual SQL/Cypher/schema literals: DATABASE_STATEMENTS.json; source functions: AST_SYMBOLS.json. Future new dynamic lineage and graph diffs:06_live_agent and04_falkordb. No Agent ID or event fabricated from prose.
''')
risks=[('R01','HIGH','Shared kernel/same UID resources are PARTIAL hostile isolation','benchmark/participant_sandbox.py','Physical negative probes required; no VM/prompt injection immunity claim'),('R02','HIGH','AOF reload139 historical not repaired; RDB only lastSAVE','h4/deploy/compose.yaml','New owned RDB recovery does not prove crash-tail durability'),('R03','MEDIUM','FalkorDB multi-query materialization not globally atomic','aevora_core/src/aevora/candidate.py','Fenced head plus staged publication, verify actual retry/conflicts'),('R04','MEDIUM','Native cross-process UDS EPERM remains possible','aevora_core/src/aevora/mcp_broker.py','Must preserve native failure; inprocess is distinct'),('R05','MEDIUM','Phase-specific scripts hardcode old port/archive and may write history','scripts/','Use current command map; external wrappers only, never invoke old main blindly'),('R06','LOW','WORKSPACE docs say parent linked worktree and1820; actual independent ordinaryGit and1836','docs/current/WORKSPACE.md','Document drift recorded; frozen bytes unchanged'),('R07','MEDIUM','admission SourceVerification.source_epoch fixed H3_NEW_NATIVE_SESSION','aevora_core/src/aevora/admission.py','Retain native fixed label but new audit separately pins actual current HEAD and UTC; never imply H3 source executed'),('R08','MEDIUM','Provider costs/weights and statistical causal benefit unverified','integrations/providers.py','Budget bounded real request count; soft20USD, no hardcost claim'),('R09','MEDIUM','Public privileged Python types require trusted OS owner','aevora_core/src/aevora/admission.py','No public admin MCP; clean install alone is not adversarial sameUID fence'),('R10','MEDIUM','Unknown secrets cannot be mathematically excluded by finite scan','tools/public_release.py','Allowlist plus actual private-path/known-secret byte scan coverage')]
with (E/'01_source/RISK_REGISTER.csv').open('x') as f:w=csv.writer(f);w.writerow(['id','severity','finding','source','scope_and_action']);w.writerows(risks)
(E/'01_source/SOURCE_AND_TRUST_BOUNDARY_AUDIT.md').write_text('''# Source and trust audit

Frozen source not modified. V1 is static review plus machine symbol/hash inventory; pending dynamic proof is explicitly marked. No CRITICAL defect confirmed at this point. Known HIGH limitations are in RISK_REGISTER, not silently treated as solved.

S frozen source is unmounted from the owned trusted runtime. H alone receives DB password/Oracle/source pins and eventual upstream model key. P narrower participant_command mounts only public workspace/new state/native tool binaries/scoped model+MCP sockets/proxies, unshare-net and native workspace sandbox. P never uses this audit's trusted-maintainer driver or readonly history mappings. E alone contains writable copy, owned service evidence and raw records. Product workspace is not P isolation. Private APIs in public Python distribution are Host types, not remotely exposed powers.

Explicit negative obligations: P cannot read private tests/reference/source/history/keys or other run; public MCP cannot mint Outcome or publish; cross-run Query and poisoned proposal rejected without graph contamination; source-fidelity catches apply-success with wrong bytes; hidden pytest never imports candidate package/plugins; typed natural-source proposal required before Host admission; LIVE outage has no Replay fallback. Current static error paths sanitize public inputs. Dynamic test receipts are needed before asserting these paths exercised.

Caller/callee archive is syntactic, not invented dispatch. V1 does not claim all547 files manually line-reviewed. Core decision/feedback/candidate, independent evaluator/Runner, Participant/model boundary and release/Console critical paths were directly read; all others indexed with explicit scope. Old AGENTS stop rules/phase labels and old docs counts describe history; this user task is current authority. No source correction authorized here.
''')
write(E/'01_source/V1_RESULT.json',{'at':now(),'status':'PASS','scope':'547identity/index and critical static path review complete; security/live behavior requires subsequent dynamic gates','critical_confirmed':0,'risks':len(risks)})
print('V1 static audit PASS; dynamic claims pending')
