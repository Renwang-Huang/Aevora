from audit import *
import csv,json,ast,datetime,re,shutil
D=P/'docs/gen2/g20'
def csvout(name,rows):
 for root in [E,D]:
  with (root/name).open('x',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
idx={r['path']:r for r in json.loads((E/'source_audit/SYMBOL_AND_IMPORT_INDEX.json').read_text())['files']}
items=[
('WHEN','aevora_core/src/aevora/experience_resolver.py','ExperienceResolver._resolve_one','Recommendation/current_scope','aevora_core/tests/test_applicability.py','INCREMENTAL_POLICY_V2','Task conditions vs artifact phases; no score'),
('WHY','aevora_core/src/aevora/evidence_bundle.py','build_evidence_bundle','Support/counter/observed paths','aevora_core/tests/test_mcp_real_graph.py','INCREMENTAL_WITNESS','Complete manifests and authority source'),
('GRAPH_SCHEMA','aevora_core/src/aevora/graph_repository.py','GraphRepository.initialize','Schema/constraints','aevora_core/tests/test_graph_repository.py','EXPLICIT_NEW_SCHEMA_PROFILE','Exact old constraint set cannot mix'),
('GRAPH_IMMUTABLE','aevora_core/src/aevora/graph_repository.py','GraphRepository.put_node','Payload SHA/stableID','aevora_core/tests/test_graph_repository.py','REUSE','Not global transactions'),
('GRAPH_PATH','aevora_core/src/aevora/graph_repository.py','GraphRepository.snapshot_public_paths','Revision-Evidence-Outcome-Context-Task','aevora_core/tests/test_mcp_real_graph.py','ADD_BOUNDED_NATIVE_TENANT_QUERIES','Current properties mostly payload_json'),
('REVISION','aevora_core/src/aevora/graph_repository.py','GraphRepository.append_rule_revision','Revision/Rule/SUPERSEDES','aevora_core/tests/test_h2_governance.py','REUSE_WITH_MANIFEST_FENCE','Scoped revisions not timestamp winner'),
('WITHDRAW','aevora_core/src/aevora/governance.py','project','GovernanceEvent/active scope','aevora_core/tests/test_h2_governance.py','REUSE_EXTEND_EPOCH','No current semantic cursor epoch in legacy'),
('PUBLIC_TOOL','aevora_core/src/aevora/mcp_server.py','create_server','Four SDK schemas','aevora_core/tests/test_v5c_context_contract.py','VERSIONED_PROFILE','Do not silently relax old claims schema'),
('TRUSTED_CONTEXT','aevora_core/src/aevora/mcp_server.py','ExperienceService.resolve_experience','Query/claims/Host facts','aevora_core/tests/test_mcp_service.py','ADD_PHASED_HOST_FACT_RECEIPTS','Claims never become independent facts'),
('DECISION','aevora_core/src/aevora/mcp_server.py','ExperienceService.record_decision','Untrusted Decision','aevora_core/tests/test_mcp_service.py','ADD_RECOMMENDATION_ID','agent_thread_id currently UNAVAILABLE'),
('TRANSPORT','aevora_core/src/aevora/mcp_projection.py','PublicProjection.bundle','Lossless RFC6901/document SHA','aevora_core/tests/test_v5c1_bounded_transport.py','REUSE_ADD_EPOCH_AUTHZ','Graph record limit still256KiB; chunk storage needed'),
('CURSOR','aevora_core/src/aevora/mcp_projection.py','PublicProjection.continuation','HMAC connection/run/document','aevora_core/tests/test_v5c1_bounded_transport.py','ADD_REVOCATION_EPOCH','TTL900 is not Agent wall budget'),
('BROKER','aevora_core/src/aevora/mcp_broker.py','MCPBroker._handle','Scoped request/reply/peer credentials','aevora_core/tests/test_mcp_broker.py','REUSE_ADD_DELIVERY_RECEIPT','Peer PID not native thread'),
('CANDIDATE','aevora_core/src/aevora/candidate.py','CandidateLifecycle.propose','Candidate/Head/Event','aevora_core/tests/test_h3_proposal_contract.py','REUSE_VERSION_BODY_VALIDATION','Proposal is untrusted, not published'),
('PUBLICATION','aevora_core/src/aevora/candidate.py','CandidateLifecycle.transition','Single-query CAS lifecycle','aevora_core/tests/test_h3_lifecycle.py','EXTEND_SAME_QUERY_COMMIT_EPOCH','Multi-step publish currently explicitly not atomic'),
('SOURCE','aevora_core/src/aevora/admission.py','verify_orderflow_candidate','SourceVerification/native typed proposal','aevora_core/tests/test_h3_candidate_scope.py','REUSE_FIX_NEW_EPOCH_LABEL','Host source verifier is not semantic reviewer'),
('OUTCOME','aevora_core/src/aevora/orderflow_outcome_bridge.py','verify_outcome','Pinned original report/JUnit/source','aevora_core/tests/test_orderflow_outcome_bridge.py','REUSE_GENERIC_AUTHORIZED_VERIFIER_CONTRACT','Local pin is not third party attestation'),
('FEEDBACK','aevora_core/src/aevora/feedback.py','ingest_outcome','Observed feedback/query snapshot epoch','aevora_core/tests/test_feedback.py','REUSE_ADD_PRECISE_DELIVERY_ASSOCIATION','CONSIDERED not delivered/adopted'),
('RUNTIME','integrations/codex_agent.py','CodexAgentAdapter.execute','Native officialCLI/patch/archive','tests/test_aevora_h2_runtime.py','REUSE','No new orchestrator'),
('NATIVE_IDENTITY','integrations/native_rollout_trace.py','analyze_native_rollouts','Own child session/turn/final/parent receipt','tests/test_native_rollout_trace.py','REUSE_NORMALIZE_TYPED_IDS','No newly verified children in G20'),
('EXEC_EVENTS','integrations/codex_trace.py','parse_trace','CLI typed events/usage/source refs','tests/test_aevora_trace_audit.py','REUSE','CLI output does not expose all child internals'),
('BRIDGE','integrations/aevora.py','AevoraRuntimeBridge.__enter__','Opt-in graph scoped channel','tests/test_aevora_h4_empty_bridge.py','ADD_HOST_PROFILE_BINDING','Empty graph legitimate'),
('RUNNER','benchmark/runner.py','BenchmarkRunner.run_agent','Run lifecycle/runtime/evaluation/report','tests/test_aevora_integration.py','REUSE_PRIVATE','Do not import Runner into public Core'),
('SUBMISSION','benchmark/submission.py','apply_verified_patch','Expected/applied source trees','tests/test_submission_fidelity.py','UNCHANGED','Exact bytes; no human reference substitution'),
('JUNIT','evaluator/runner.py','read_junit','Required complete tests/exit/result','tests/test_aevora_h2_junit.py','UNCHANGED','Do not lower expected counts'),
('DB_ORACLE','evaluator/episode_d_v02_oracle.py','inspect_episode_d_v02_database','Independent SQLite state/constraints','tests/test_aevora_h2_graph_e2e_contract.py','UNCHANGED_PRIVATE','Outcome not Agent audit() truth'),
('CONSOLE_API','console/src/aevora_observatory/server.py','create_app','Loopback read-only LIVE/REPLAY','tests/test_aevora_h4_api.py','REUSE_ADD_V2_PUBLIC_PROJECTION','No Host write authority in browser'),
('CONSOLE_LIVE','console/src/aevora_observatory/projection.py','LiveReader.overview','Live graph and bound public records','tests/test_aevora_h4_console.py','REPLACE_H4_SELECTORS_INCREMENTALLY','Legacy defaults not generic arbitration'),
('PUBLIC_BUILD','tools/public_release.py','chosen','Explicit source allowlist','tests/test_aevora_h2_source_allowlist.py','EXTEND_ONLY_G26_AFTER_REVIEW','Tracked is not public'),
('AUDIT','aevora_maintainer/audit_capsule.py','build_capsule','Full/Lite original-export hashes','aevora_core/tests/test_audit_capsule.py','REUSE','Public Core cannot require private archives')]
rows=[];deltas=[]
for req,path,sym,typ,test,delta,risk in items:
 r=idx[path];s=next(x for x in r['symbols'] if x['symbol']==sym);assert (P/test).is_file(),test
 row={'requirement':req,'path':path,'symbol':sym,'line':s['line'],'end_line':s['end_line'],'file_sha256':r['sha256'],'data_or_event_type':typ,'existing_test_source':test,'historical_evidence':'V5C1 original RAW_JUNIT1897; NOT_RERUN_G20','audit_level':'STATIC_SOURCE_AUDIT','gen2_change':delta,'risk':risk,'ownership':'PRIVATE_MAINTAINER' if path.startswith(('benchmark/','evaluator/','aevora_maintainer/','integrations/')) else 'PUBLIC_PRODUCT_OR_BUILD_REVIEW'}
 rows.append(row);deltas.append({'requirement':req,'as_is_path_symbol':path+'::'+sym,'implemented':'YES_AS_IS_STATIC_VERIFIED','gen2_mechanism':delta,'new_mechanism_status':'PROPOSED_NOT_IMPLEMENTED' if delta not in ['UNCHANGED','UNCHANGED_PRIVATE','REUSE','REUSE_PRIVATE'] else 'REUSE_EXISTING','gate':'G2-3' if req in ['RUNTIME','NATIVE_IDENTITY','EXEC_EVENTS'] else 'G2-5' if req.startswith('CONSOLE') else 'G2-6' if req in ['PUBLIC_BUILD','AUDIT'] else 'G2-2' if req in ['SOURCE','OUTCOME','FEEDBACK','PUBLICATION','CANDIDATE','WITHDRAW'] else 'G2-1','acceptance':risk})
csvout('SOURCE_ENTRYPOINT_MAP.csv',rows);csvout('AS_IS_TO_GEN2_DELTA.csv',deltas)
# Current source history: actual Git visibility is evidence, never an authorship clock.
log=subprocess.check_output(['git','--no-optional-locks','-C',str(P),'log','--reverse','--format=@@%H%x09%cI','--name-only',C['base_head']],text=True)
write(E/'source_audit/GIT_PATH_VISIBILITY.log',log)
first={};last={};meta=None
for line in log.splitlines():
 if line.startswith('@@'):meta=line[2:].split('\t',1)
 elif line and meta:
  first.setdefault(line,meta);last[line]=meta
files=gitfiles=subprocess.check_output(['git','-C',str(P),'ls-tree','-r','--name-only',C['base_head']],text=True).splitlines();assert len(files)==551
frozen=set(json.loads((BASE.parents[1]/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256'])
contrib=[]
for n in files:
 p=P/n;f=first.get(n,['UNAVAILABLE','UNAVAILABLE']);l=last.get(n,f)
 samefrozen=n in frozen and sha(p)==sha(W/n)
 origin='GEN1_PRE_EVENT_VISIBLE_CONTENT' if samefrozen else 'INHERITED_V5C_OR_V5C1_REPAIR_AT_G20_START'
 if '/third_party/' in n:origin='THIRD_PARTY_ASSET_INHERITED'
 visibility='PRIVATE_NOT_PRODUCT_EXPORT' if n.startswith(('benchmark/','evaluator/','tests/','integrations/','app/','aevora_maintainer/','scripts/')) else 'EXPLICIT_PUBLIC_ALLOWLIST_REVIEW_REQUIRED'
 contrib.append({'path_or_module':n,'classification':origin,'content_sha256':sha(p),'origin_evidence':'Frozen Gen1 fingerprint' if samefrozen else 'Real source at '+C['base_head']+' and actual Git visibility log','first_visible_commit':f[0],'first_visible_commit_time':f[1],'last_touch_commit':l[0],'last_touch_commit_time':l[1],'new_competition_claim':'NONE_INHERITED_NOT_NEW_GEN2_CORE','license_or_release':visibility,'uncertainty':'Git time is visibility, not first design/coding time; organizer reuse boundary uncertain'})
for p in sorted(D.rglob('*')):
 if p.is_file():contrib.append({'path_or_module':str(p.relative_to(P)),'classification':'G20_NEW_DESIGN_CONTRACT_ASSET','content_sha256':sha(p),'origin_evidence':'This owned G20 write command + design freeze Manifest','first_visible_commit':'PENDING_DESIGN_COMMIT','first_visible_commit_time':'ACTUAL_COMMIT_WILL_BE_RECORDED_EXTERNALLY','last_touch_commit':'NOT_COMMITTED_YET','last_touch_commit_time':'NOT_COMMITTED_YET','new_competition_claim':'NEW_ARCHITECTURE_CONTRACT_NOT_PRODUCTION_FUNCTION','license_or_release':'MAINTAINER_REVIEW_NOT_AUTO_PUBLIC_EXPORT','uncertainty':'Not proof of main FalkorDB implementation; future source Gate needed'})
planned=['aevora_core/src/aevora/contracts.py','aevora_core/src/aevora/graph_queries.py','aevora_core/src/aevora/arbitration.py','aevora_core/src/aevora/graph_repository.py (v2 extension)','aevora_core/src/aevora/candidate.py (commit/epoch extension)','aevora_core/src/aevora/mcp_projection.py (authz/semantic epoch)','integrations/native_rollout_trace.py (exact identity associations)','console/src/aevora_observatory/projection.py (v2 read projection)']
for n in planned:contrib.append({'path_or_module':n,'classification':'PLANNED_GEN2_IMPLEMENTATION_NOT_AUTHORED','content_sha256':'NOT_IMPLEMENTED','origin_evidence':'G20 design only','first_visible_commit':'NOT_RUN','first_visible_commit_time':'NOT_RUN','last_touch_commit':'NOT_RUN','last_touch_commit_time':'NOT_RUN','new_competition_claim':'FUTURE_REAL_GRAPH_NATIVE_CORE_DELTA_MUST_BE_PROVEN','license_or_release':'LATER_LICENSE_AND_PUBLIC_BOUNDARY_REVIEW','uncertainty':'Cannot be credited before actual implementation and verification'})
for name,origin in [('FalkorDB4.20.4','https://github.com/FalkorDB/FalkorDB'),('falkordb-py1.7.1','https://github.com/FalkorDB/falkordb-py'),('mcp1.26.0','https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0'),('codex-cli0.162.1','https://github.com/openai/codex/tree/rust-v0.162.1')]:
 contrib.append({'path_or_module':'THIRD_PARTY:'+name,'classification':'THIRD_PARTY_RUNTIME_NOT_AEVORA_ORIGINAL','content_sha256':'See current installed package/image receipts','origin_evidence':origin,'first_visible_commit':'UPSTREAM','first_visible_commit_time':'NOT_AEVORA_AUTHORSHIP','last_touch_commit':'UPSTREAM','last_touch_commit_time':'NOT_AEVORA_AUTHORSHIP','new_competition_claim':'DEPENDENCY_REUSE_ONLY','license_or_release':'Server SSPL separate image; SDK/CLI license per upstream and existing THIRD_PARTY_NOTICES','uncertainty':'No legal certification; distribution review required'})
csvout('HACKATHON_CONTRIBUTION_MATRIX.csv',contrib)
gates=[
('G2-1','Graph-native bounded WHEN/WHY','G20_APPROVED','models/graph_repository/graph_queries/arbitration/evidence_bundle/mcp_projection','T01 T02 T03 T04 T05 T06 T10 T11 T13','real Cypher/epoch/cutrestore/fullwire','All original1897 plus new tests, genuine graph sensitivity, no Oracle edit'),
('G2-2','Trusted lifecycle/feedback/phase/source/authority','G2-1_PASS','candidate/admission/feedback/outcome bridge/mcp_broker','T07 T08 T14','original Outcome/source + Host review/fence + revoke','No half publication; exact provenance/scope; stale/replay rejection'),
('G2-3','Native Multi-Agent and cross-session lifecycle','G2-2_PASS_AND_LIVE_SAFETY','integrations/codex_agent/native_rollout_trace/aevora','T09 T12 plus isolation','fresh official parent and2children; natural proposal/patch/Oracle','Runtime/evaluation/inheritance separated; no synthetic identity'),
('G2-4','Graph Raw NoMemory and interventions','G2-3_PROTOCOL_READY_AND_PREREG','owned experiment driver/aevora_maintainer','T03 T04 T05 T06 T09','60Runs+intervention cohorts; all failures retained','Same task/model/Oracle/resources; causal boundaries honest'),
('G2-5','Three-page Console and four-act truthful Hero','G2-1_TO_G2-4_EVIDENCE','console/src/web/h4 versioned assets','LIVE REPLAY READONLY OFFLINE SOURCE_LINKS','real browser/network/Run/Graph/raw receipts','No invented outcomes/causality; four-act completeness or explicit gaps'),
('G2-6','Complete regression/install/public release','ALL_PRIOR_GATES_REVIEWED','tools/public_release/publicdocs/packaging','all inherited/new contracts + member/secret scan','JUnit/cleanSDK/MCP/DB/Console/FullLite/tamper/license/AI disclosure','User separate publish approval; no private truth or credential leak')]
grows=[dict(zip(['gate','feature','dependencies','source_entrypoints','positive_and_negative_tests','demo_evidence','exit_criteria'],r),completion_status='PLANNED_NOT_IMPLEMENTED_OR_RUN') for r in gates]
csvout('GEN2_GATES_AND_DEPENDENCIES.csv',grows)
claims=[
('Graph is essential','tenant context→real multi-hop→complete support/counter→Recommendation→tool result','raw Cypher+epoch+publicMCP+Native refs','cut/restore,withdraw,DB outage','Decision sensitivity is not automatically Agent behavioral benefit','Recreate fresh syntheticgraph, execute bounded templates and compare source-pinned Core outputs'),
('Bounded when/why','registered facts+rule declarations+scope+authority+reason paths','witness manifest/context/policy hash','unknown,hardconflict,different scope,overflow','APPLY is conditional principle not proof of correct patch','Run independent T01–T06/T10/T13 corpus with same context'),
('Trusted evolution','natural proposal→sealed native/body→originalOracle→Hostsource/semantic review→fencedpublish','typed proposal/bodySHA/source/Outcome/commit/graphdiff','forgedOutcome,staleCAS,scopebroaden,withdraw','Bounded observed support not universal/causal truth','Verify sources/Oracle pins and publication time order outside Participant'),
('Cross-session transfer','newSession→newIDresolve→fullbundle→Decision→actualpatch→originalOracle→feedback','CLI/MCP/Diff/JUnit/directDB/Host lineage','onlyretrieved;oldIDdecision;humanpatch;missingbundle','Temporal/action correlation not mental causation','Read complete sanitized logs and raw-original SHA links; compare sealed initial fixtures'),
('Native Multi-Agent','parenttypedspawn→twochildownsession/newturn/task/action/final→parentcompletion','pinned official native rollouts/parser','inheritedparenthistory,fakeprose,threeSingle,ambiguoustoolactor','Role configs and parallelAPI calls do not prove children','Match own session IDs, parent turn refs and exact final receipts'),
('Generalization benefit','preregistered matched Graph/Raw/NoMemory+interventions→allrunoriginalscores','cohortallocation/sourcepins/rawresults/faildenominators','scopeflip/counterexample and noactiondifference','Small sample and confounds; CAUSAL_UNKNOWN if insufficient','Rebuild same publicfixture/corpus, new independent sessions, unchanged independentOracle'),
('Safe public product','publicallowlist→freshinstall→realMCP/DB/Console→scan','package members/sourcehash/browser/secret scan','privateOracle/credential/otherRun/crossTenant requests','Shared kernel PARTIAL; no external notarization','Install only released wheels/source with new owned DB; verify public artifact hashes')]
crows=[dict(zip(['future_claim','required_evidence_chain','observation_tools','counterexamples','causal_boundary','recipient_reproduction'],r),status='PLANNED_NOT_CLAIMED_AS_ACHIEVED') for r in claims];csvout('CLAIM_TO_EVIDENCE_PLAN.csv',crows)
write(E/'source_audit/MATRIX_SUMMARY.json',{'source_entrypoints':len(rows),'delta_rows':len(deltas),'contribution_rows':len(contrib),'inherited_files':len(files),'future_gates':len(grows),'claims':len(crows)})
print('MATRICES_COMPLETE',len(rows),len(contrib))
