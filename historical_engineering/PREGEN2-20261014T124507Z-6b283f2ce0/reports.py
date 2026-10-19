from audit import *
import csv,shutil,collections
A=E/'07_audit';reg=json.loads((E/'02_regression/regression_summary.json').read_text());ses=json.loads((E/'06_live_agent/session_manifest.json').read_text());v5=json.loads((E/'06_live_agent/V5_RESULT.json').read_text());diag=json.loads((E/'06_live_agent/postmortem/RESULT.json').read_text());control=json.loads((E/'06_live_agent/host_controlled_feedback/RESULT.json').read_text());pub=json.loads((E/'05_product/PUBLIC_RELEASE_SCAN.json').read_text())
v5['overall_reason']='New authenticated model/MCP/code and independently verified stopped artifact are real. Original native sessions exhausted hard budgets; no native proposal; S2 made invalid MCP input and did not retrieve updated graph. Host-controlled publication and Host-only retrieval do NOT establish native cross-session inheritance.'
(E/'06_live_agent/V5_RESULT.json').write_text(json.dumps(v5,indent=2,sort_keys=True)+'\n')
def md(name,s): (A/name).write_text(s.strip()+'\n')
for n in ['CURRENT_ARCHITECTURE_MAP.md','SOURCE_AND_TRUST_BOUNDARY_AUDIT.md','SOURCE_547_INVENTORY.csv','SOURCE_TRACEABILITY_MATRIX.csv','ENTRYPOINT_DEPENDENCY_GRAPH.mmd','EVENT_AND_CLAIM_SCHEMA.md','RISK_REGISTER.csv']:shutil.copyfile(E/'01_source'/n,A/n)
commands=[json.loads(l) for l in (E/'00_environment/commands.jsonl').read_text().splitlines()]
with (A/'COMMAND_INDEX.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=['label','started_at','ended_at','cwd','argv_json','exit_code','stdout_sha256','stderr_sha256']);w.writeheader()
 for x in commands:w.writerow({**{k:x[k] for k in ['label','started_at','ended_at','cwd','exit_code','stdout_sha256','stderr_sha256']},'argv_json':json.dumps(x['argv'])})
gates={'V0':'PASS','V1':'PASS','V2':'PASS','V3':'PASS','V4':'PASS_WITH_DOCUMENTED_PUBLIC_STAGING','V5':'CONDITIONAL_PASS / INCOMPLETE','V6':'PASS_PENDING_SEAL_VERIFY'}
write(A/'00_EXECUTION_MANIFEST.json',{'run_id':C['run_id'],'out':str(E),'at':now(),'source_head':C['head'],'source_tree':C['tree'],'source_files':547,'source_scope':'MAINTAINER_ONLY','gates':gates,'provisional_admission':'PRE-GEN2 CONDITIONAL','final_gen2_admission':'RESERVED_FOR_USER_AND_INDEPENDENT_REVIEW','model_sessions':3,'forwarded_upstream':ses['forwarded_upstream_total'],'model_completed_responses':sum(x['completed_model_responses'] for x in ses['sessions']),'model_cost':'UNAVAILABLE; soft20USD not hardfee control','source_code_changed':False,'remote_push':False,'full_manifest':str(E/'private_full/FULL_MANIFEST.sha256'),'historical_G5_not_reused_as_new_execution':True})
md('REGRESSION_1836_IDENTITY_REPORT.md',f'''# Current full regression

**PASS**:1836 collected,1836 unique IDs,0 duplicates,0 FAIL,0 ERROR,0 SKIP, actual process exit0. JUnit classname::name identity multiset exactly equals historical G5. Both identity files SHA256 `{reg['actual_ids_sha256']}`. New JUnit SHA256 `{reg['junit_sha256']}`.

Actual command: external `runtime.py --history` equivalent argv recorded under `commands/v2-full-1836-attempt1/receipt.json`; mature `tools/dev.py test-maintainer --output {E}/02_regression/attempts/attempt1 --owned-port17705` executed on the547-byte-identical owned clone. Frozen active source was not mounted. Python3.12.14/SQLite3.51.3, fresh editable installs and actual FalkorDB. Readonly historical corpus dependency **YES**. Expected/actual IDs and zero diff:02_regression. Raw JUnit:02_regression/junit_full.xml; raw Cypher and source epochs:attempts/attempt1. Current source epoch unchanged.

This fresh run is distinct from G5's historical1836. Additional Node/browser/Host diagnostics are not counted inside1836. No assertion/test identity deletion or weakening.''')
cli=json.loads((E/'03_benchmark/cli/summary.json').read_text());lines=[]
for x in cli['commands']:lines.append(f"|{x['label']}|{x['expected_status']}|{x['status']}|{x['exit_code']}|{x.get('run_id') or 'N/A'}|")
md('BENCHMARK_ORACLE_AND_CLI_REPORT.md','''# Independent Benchmark

**15 original CLI contracts PASS**, exact labels/expected exits retained from G5. CLI expected FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED are genuine negative results, not successful submissions. New Sandbox/SQLite data per Run. Original suites and reference patches unchanged.

|case|expected|observed|exit|new Run|
|---|---|---|---|---|
'''+ '\n'.join(lines)+f'''

Smoke8:buggy0PASS/8FAIL,reference8PASS. A14:buggy5PASS/9FAIL,reference14PASS. D-v01_28:buggy15PASS/13FAIL,reference28PASS,flock alternative28PASS. D-v02_36:newbuggy68af46f1-6e1c-4215-b7cc-adb2a7d7a1b7 =28PASS/8FAIL; newreference5c9da12c-9a68-4fb4-a1a3-14474bad57ab =36PASS. D-v02 request recovery COMPLETE. Buggy item failure counts can vary with schedule; verdict FAIL is real, not a claimed count-identical replay. B/C remain NOT_IMPLEMENTED/exit4.

Host database Oracle, Worker topology and recovery receipts are original item-level artifacts in03_benchmark. Actual3physical boundaries:6checksPASS, no model calls. Actual absent-Codex startup returns STARTUP_FAILED. Real oversized Unix HTTP send-close yields413/BrokenPipeError and0upstream calls; cleanup completes. Old D-v02 specific native UDS EPERM is **not re-certified** by generic boundary probes; retain UNVERIFIED for that exact route.

Untouched S1 stopped artifact:diagnosticRun{diag['diagnostic_run_id']} independently28/28PASS; workspace-protocol diagnostic81c04e2c-28d3-4202-9534-af096919d2cb also28/28PASS and strictVerifier accepted. These are postmortem Host evaluations; originalS1 stays ERROR/NOT_RUN. No reference artifact substituted. PatchSHA `{diag['submission_sha256']}`.''')
md('FALKORDB_AND_TRUSTED_FEEDBACK_REPORT.md',f'''# Actual graph and trusted feedback

Owned authenticated FalkorDB4.20.4 pinned digest, new17705DB/secret/graph; old H1/H2/H3/Gen1.5 services untouched. Runtime config and actual raw Graph/Cypher/Redis receipts retained. **15 real graph controls +3 head/revision/fakeOracle controls PASS**. New empty initialization, authorized real historical4outcome import/idempotency, genuine APPLY/VERIFY/ABSTAIN RLock scopes, exact evidence-edge cut/WHY change/restore, Host bounded lifecycle publication/withdrawal and immutable historical query snapshots were exercised.

Actual concurrent head2contenders yields1winner/1stale. Actual contradictory revisions forceVERIFY. Fake Oracle report allowlist and unproved source/authority/body denied; VerifiedOutcome counts do not increase from untrusted input. All successful controlled source uses authentic historical or newly tested evidence, never synthetic trusted PASS. Original valid developer tests contain explicitly synthetic contract fixtures; those are OFFLINE_REGRESSION, not live-model outcomes.

New RDB bytes cold-loaded into a separately owned17706replica, normal stop/start restores exact graph. Original Docker cp of tmpfs file returned notfound; actual Docker exec cat bytes were then separately recorded and genuinely reloaded, initial failure kept. New main DB finalSAVE bytes:{E}/commands/v6-owned-final-rdb-bytes/stdout.log. AOF139 remains historical unresolved; no crash-tail/power-loss assurance.

For new S1, strict Host verification rejects original ERROR/NOT_RUN. Two real untouched-code diagnostics pass28tests; workspace diagnostic supplies a valid trustedOutcome. Host-controlled candidate {control['candidate_id']} is published as maintainer_seed with explicit stopped-runtime limitations, not a native proposal. Before/after actual graph SHA `{control['source_before_sha256']}` / `{control['source_after_sha256']}`. No original S1 VerifiedOutcome minted; causal benefit UNKNOWN. Source code/old graph facts never edited. Graph multi-step materialization is not globally atomic.''')
md('MCP_CONSOLE_RELEASE_BOUNDARY_REPORT.md',f'''# Product and boundary

Fresh public-only namespace mounts runtime/public source/probe/owned install/ownedDBsecret only; **no private Benchmark, hidden Oracle, frozen source or fullE mount**. Original official SDK assertions retained; actual4tools/10checksPASS, scoped owner grant revoked,0fakeOutcomes, Core importability without Benchmark checked. Raw registrations/schema/calls:05_product/clean_install_retry2/g1/pregen2-clean-onboarding. This is SDK evidence, not model evidence.

Two independent mature public builds:2Core/Console wheels per build,2sdists per build, repeated114-file sourceZIP. ZIP SHA `{pub['public_source_zip_sha256']}` unchanged vsG5. Wheels byte-identical; sdists differ in archive metadata but exact member paths/payloadSHAs equal. Detailed PACKAGE_REPEATABILITY.json. Actual new image source/member/layers scan:{pub['files_and_members_scanned']}members/{pub['uncompressed_bytes_scanned']}bytes,0known-secret/solehash hits,0privatepath/exactcopy hits,4known-secret classes. Finite rules do not prove absence of unknown secrets.

Original17actualChromium checks PASS plus4additional LIVE conflict/withdrawal/read-only denial/actualHost edge cut+restore checks PASS. REPLAY remains explicit historical evidence. Real coldDB stop yields LIVE503/fallbackfalse and explicitREPLAY200; normal restart returns LIVE200 with identical graph/decisions. Earlier mainDB pause HTTP probe exceeded collector10s timeout and was resumed without claiming503. Browser/rawHTTP/screenshots retained. Main/source package files are byte-identical; only public staging permissions normalized because secureumask077 clone yielded0600 files. Both failed images/startups retained; no frozen Dockerfile change.

Product8/Maintainer19 folders; actual native6APIchecks each (SCM,search,3process tasks,terminalcwd/settings). Canonical configs unchanged. Human Explorer/Python Test Explorer remain VISUAL_UNVERIFIED. Views are not sandboxes. Maintenance repo/public release distinct; no push/public deployment.''')
network='''# New authenticated Agent challenge — INCOMPLETE

All3sessions are genuinely new official Codex0.162.1 processes/contexts with scoped private model and MCP channels. Actual model responses are new authenticated Gateway200/COMPLETED, observedlabels gpt-5.6-terra/max. Labels do not attest weights. Native single mode, no new subagent/collaboration claim. completion-aware/None totalwall deadline; finite3600000ms officialstreamidle/connect/retry/resource/request controls. No1200s task cutoff.

|session|new Run|new thread|native exit|runtime|forwarded requests|completed model responses|
|---|---|---|---|---|---|---|
'''
for s in ses['sessions']:network+=f"|{s['label']}|{s['run_id']}|{s['thread_id']}|{s['native_exit']}|{s['runtime_result']}|{s['forwarded_upstream_requests']}|{s['completed_model_responses']}|\n"
network+=f'''
All3native exits1:hard request budget exhaustion, not silent success. Total40forwarded (6catalogGET +34modelPOST;33completed modelresponses +1S1interrupted stream),8local budget rejections. S1 retains UPSTREAM_STREAM_INTERRUPTED and all retry/catalog/rejection evidence. Costs UNAVAILABLE; soft20USD is not hardfee cap. No additional paid retry, optional fourth session or unfair comparator run.

S1 actual WHEN/WHY:real MCPresolve and2bundles beforefirstpatch; native decisions ABSTAIN for per-processRLock/APPLY for SQLite relativeatomic write. Actual actor changed inventory.py/service.py and public regression files. Original runtime ERROR/evaluationNOT_RUN/integrationPARTIAL stays sealed. Actual untouched patchSHA `{diag['submission_sha256']}` independently28/28PASS in diagnostic391767c0-6678-42df-ac5b-23621db61054. Same tree verified underworkspace81c04e2c-28d3-4202-9534-af096919d2cb. No manualrepair. Action is consistent with queried principle; causal benefit UNKNOWN.

Agent did not invoke propose_experience. Strict Host rejects original incomplete source; publishes only explicitly Host-controlled diagnostically verified candidate. This is **not Agent-originated lifecycle completion**. Core source verification source_epoch H3 literal is a historical label risk; this audit pins actual737fHEAD separately and does not assign H3bytes to current executions.

S2 new authenticated session startedafterHoststatecommit. Its only resolve_experience used prose/list/undocumented facts rather than the service's typed semantic facts; real service returned AEVORA_INVALID_OR_UNAUTHORIZED_INPUT. It exhausted8requests before correctedretrieval/bundle/decision. **NO_CROSS_SESSION_INHERITANCE**. Later Host-only resolve{{}}/bundle successfully reads publication, explicitly TRUSTED_HOST_GRAPH_CONTROL; this does not repair S2's result or stand for a model retrieval. Original raw typed events/rollouts/MCP logs/transport are untouched.

Thus V5=CONDITIONAL_PASS, LIVE_AGENT=INCOMPLETE. New model execution, graph-supported decisions, actual codeaction and independent repair evidence exist; natural proposal/automaticsubmission and updated-state native successor retrieval do not. No REAL_ONLINE_AGENT_E2E_PASS, no successful original completedsubmission, no nativeMulti, no causal/statistical claim.

Actual invocations/UTC/exits/hashes:COMMAND_INDEX.csv andcommands/v5-*. Typed projections contain references to original file/line/SHA and label DERIVED_INDEX. Budget protocol/source547/currentOracle pinnedbeforecalls. Host feedback andScopeViewer failures are separately documented. Full raw logs are private; Lite includes bounded evidence indices only.

Official runtime docs read duringthisaudit:[non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),[CodexMCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Installed CLIhelp/features/raw runtime remain authority foractual flags and events.
'''
md('NETWORK_CHALLENGE_REPORT.md',network);shutil.copyfile(A/'NETWORK_CHALLENGE_REPORT.md',E/'06_live_agent/NETWORK_CHALLENGE_REPORT.md')
md('LIMITATIONS_AND_UNKNOWN.md','''# Limitations and admission gap

**PRE-GEN2 CONDITIONAL**, independent review required; not authorized Gen2 development.

- Critical V5 completeness gap:3new native sessions exhaust budgets; originalS1ERROR/NOT_RUN despite untouched-artifact28PASS. No native proposal and no updated-state S2retrieval. Full automatic/natural cross-session loop UNVERIFIED/INCOMPLETE.40upstream hardcap reached; no moremodelattempt authorizedwithinthisrun.
- MCP public task_context schema is open-dict while service expects bounded semantic enums/boolean facts and rejects unknown authority keys. S1 first4resolve calls needed correction; S2 sent prose/list/extra keys and was rejected. Current inherited generic prompt says factsfromenvironment but does not expose a ready pinned-context schema. This is observed integration/usability friction, not a fabricated engine failure. Frozen source not repaired.
- Official runtime budgets count catalogGET/retry forwards too; S1 had4catalogGET and1interruptedstream. Successful authentication/33completedresponses does not prove complete sessions. Request cap is not exact token/USD limit; actualcharges and underlyingweights UNVERIFIED.
- Public source staging underumask077 requires ordinaryfiles0644/executable0755 anddirs0755 fornonrootDockerCOPY. First2startup failures retained. ActualWfiles0664; ownedclone0600. Payloads unchanged. Packaging normalization is explicit externalconfiguration, not a frozenDockerfile fix.
- Sharedkernel/sameUID, Flatpak24.08EOL:physical boundary probes PASS in declared scope, hostileVM/kernel/prompt-injection immunity PARTIAL/UNVERIFIED.
- Specific D-v02nativeUDSEPERM historical; no new end-to-end attestation for that exactroute. Generic nativecommand denial/MCPscope are differenttests.
- AOF139 remains unresolved historical; genuineRDBSAVE/coldrestore/normalrestart only. Unsavedtail/power-lossRPO UNVERIFIED. Arbitrarymulti-query graph writes not globallyatomic.
- 60archive+backup and66G5receipt files freshlyhashed atstart/end; not full24GB archive rehash. Old read-only aliases were ephemeral. Gitobjectindependence is separate from readonlyhistoricaltestdependency.
- SAME_FAILURE_DOMAIN backups accepted previously, not independentdisk disasterrecovery.
- NativeVSCode API checks are real, humanExplorer/PythonTestExplorer VISUAL_UNVERIFIED. Console3pagesactualChromium separate.
- Finite known-secret/privatebyte scans cover actual members/layers; unknownsecrets cannot be mathematically excluded. Localhashpins not thirdpartyattestation.
- NewSingle only. HistoricalH3children are historical, not currentMulti. No comparablecontrol/statisticalcausalbenefit. B/CNOT_IMPLEMENTED; noGen2code orpush.
''')
md('FULL_VALIDATION_REPORT.md',f'''# Aevora Pre-Gen2 Full System Revalidation

## Provisional conclusion

**PRE-GEN2 CONDITIONAL**. V0/V1/V2/V3/V4 actual scopes verified; V5 **INCOMPLETE** duehardbudgets/noS2retrieval/noAgentproposal. V6 source/history/cleanup checks PASS; sealing/export independentlyverifiedbelow. Gen2 admission reservedforuser and anotherindependentreview.

Frozenactive `{W}` branchaevora-gen2-baseline HEAD`{C['head']}` /Tree`{C['tree']}`.547G5definedfileSHAs unchanged, cleanordinary.git/noalternates/noobjecthardlinks/no remotes. Externalowned evidence `{E}`. Currentfull1836/1836PASS, identical1836IDs,0fail/error/skip/dup,exit0. All originalassertions/suites/privatepatches unchanged.

## Gates

|Gate|new actual evidence|status|
|---|---|---|
|V0|547SHAs/HEAD/Tree/branch/fsck;60archive/backup+66G5sample hashes; owned3.12runtime/venv/17705DB/TLS/CLI|PASS|
|V1|547inventory,actual ASTsymbols/imports/SQL/Cypher,criticaltrustpathreview,line-linkedmatrix|PASS_STATIC_SCOPE|
|V2|1836uniquePASS;15originalCLIcases;Smoke8/A14/D1_28/D2_36positive/negative;6physicalchecks;realstartup/413negative|PASS|
|V3|15realgraphcontrols+3head/revision/fakeOracle;actualRDBcoldrestore/normalrestart|PASS_WITH_RETAINED_COLLECTOR_FAILURES|
|V4|cleanpublic-only4SDKtools/10checks;2publicbuilds;6999memberscan;original17Chrome+4newLIVEchecks;actualDB503/replay200/recovery200;nativeworkspaces|PASS_WITH_PUBLIC_STAGING_CONDITION|
|V5|3freshauthenticatedsessions,33completedresponses;WHEN/WHYbeforeactualpatch;unchangedcode28PASS;strictoriginalrejection/Hostcontrolledpublication;S2invalidquery/noinheritance|CONDITIONAL / INCOMPLETE|
|V6|547/frozenGit/endhistorysamples/ownedservicesstopped;Fullmanifest/Liteverification|PASS_PENDING_TERMINAL_RECEIPT|

## Evidence authority

HistoricalG5/H1–H4 scores are historical, not thisrun. Thisrun regressions/Oracle/SDK/Chrome/modelrequests are genuinelynew. StaticASTdependencies are syntactic; uncertainruntimebinding UNVERIFIED. SDK/onboarding/Hostgraph controls do not count asAgentMCP/modelinheritance. Postmortem28PASS does not overwriteoriginalERROR. Host-controlledcandidate isnotnativeproposal. No Mock/PASS stub/reference substitution orhiddenOracle mutation. Context/nonce only addedin externaltaskinput; Participant nevermountsH/oldhistory/frozenrepository.

## Retained failures and recovery

1.V3collector importPathError (beforeDB); thenpublicprojection privatefieldKeyError (graphcontrolscompleted,pendingcandidate retained); thenrevisionwrapperKeyError (concurrentheadcompleted). Externalcollector corrections only; freshgraph/outputattempts. Originalerrors/rawGraph persisted.
2.Docker cp tmpfsRDBnotfound; actualexecbytes+verifiedcoldreload succeed. NoJSONfakeRDB.
3.Public-onlybootstrap lackedpip thenMCPclientSDK. Newisolatedbootstrap+realSDK fixedenvironment; original10SDKassertions unmodified.
4.TwoactualDockerstartupPermissionError traces:secureclone0600/publiccontext. Explicitpublicpermissionnormalization; bytes/Dockerfile/frozenW unchanged; imagesretained.
5.FirstactualpausedDBHTTPprobe timedout10s; ownedDBresumed. SeparateownedpersistentcoldDB realstop503/replay200/restore200 verified. Timeout notsilentlyrelabeled503.
6.All3nativeCLIexits1atrequestcaps; S1streaminterruption preserved. No additionalpaidretry/quotaincrease. S2 malformedMCPcontext doesnotproveinheritance. Originalresultsremain.

## New task and financial limits

S1Run4307051f-fb90-49b7-8eb6-b25e9f0b35e1 ERROR/NOT_RUN/PARTIAL. PatchSHA`{diag['submission_sha256']}` realcode fromactor, noHostrepair. Independentpostmortem391767c0-6678-42df-ac5b-23621db61054 andworkspace81c04e2c-28d3-4202-9534-af096919d2cb both28PASS. Hostpublication is explicitdiagnosticmaintainerseed. S2 c9990331-7bb8-4560-892a-6acd3daeccd7 ERROR andNO_CROSS_SESSION_INHERITANCE. Total40forwarded,3sessions,SINGLE,33completedmodelresponses. No hardUSD20guarantee; actualcost/weightsunverified; causalbenefitUNKNOWN.

## Review and stop

RawJUnit/commands/source/patch/rollouts/MCP/Oracle/graphdifferences are linkedinmatrix andprivateFull. PublicLite excludesprivateSource/Oracle/reference/Githistory/credentials. Keep firstfailures. Old services andarchives notchanged; ownedDBstopped afteractuallatestSAVE. NoGen2feature/refactor/push. Independentreview must assessBudget/usablecontext contract andcompleteNativeS1→S2gap beforeunconditionaladmission. Full/Lite receipts areterminal, not selfauthorization.
''')
md('NOT_INCLUDED.md',f'''# Not included in Lite

Fullprivateauditroot `{E}`. Fullmanifest `{E}/private_full/FULL_MANIFEST.sha256` coversrawmaterials. Lite deliberatelyexcludes547private/fullsource snapshots,hiddenOracle source/completefailuretraces,referencepatches,privateHostimplementation,privateGithistory,venvs/runtime binaries/RDBdata andfullrawrollouts. These remainprivateFullwith hashes andboundedpublicindices. NeitherLite nor Full containsprojectcredentialvalues byknownsecretchecks. Full is MAINTAINER_AUDIT, notParticipantinput orpublicrelease. No secretvalue orsolehash isexported. Unknownsecretabsence notguaranteed.''')
md('NEXT_CHAT_README.md',f'''# Independent reviewer entry

1.FINAL_DELIVERY_RECEIPT.json andexternalZIP SHA → private_full/FULL_MANIFEST.sha256.
2.FULL_VALIDATION_REPORT.md / LIMITATIONS_AND_UNKNOWN.md:provisionalCONDITIONAL, notREADY.
3.REGESSION identity02_regression expected/actual/zeroDiff +rawjunit_full.xml SHA `{reg['junit_sha256']}`.
4.CURRENT_ARCHITECTURE_MAP/SOURCE_AND_TRUST_BOUNDARY/source547+matrices. Source547includesdocs/configs perG5definition; not547hand-reviewedmodules.
5.NETWORK_CHALLENGE_REPORT →06_live_agent actualnative/provider/MCP/sourceindices →untouchedpatchSHA `{diag['submission_sha256']}`.
6.OriginalS1 sealedERROR/NOT_RUN → independentpostmortem2OracleRun receipts; no originalgradeupgrade.
7.Strictoriginalsource rejection → actualHost-controlleddiagnosticpublication/graphdiff. No nativeproposal.
8.S2actualnewresponse/thread butinvalidMCPinput/noinheritance. Host-onlyfinalquery isnotS2evidence.
9.Failure/runtimebudget/state/UNKNOWN matrix. Root `{E}`; allsha/commandsinFull; Lite bounded, noOracle/reference/sourceleak. FinalGen2approval remainswithuser andindependentreview. Do notlaunchnewpaidcalls orGen2work merelytoinspectthispackage.''')
fields=['claim_id','gate','old_or_new','source_head','source_path','source_sha','agent_session_id','provider_request_id','parent_child_identity','retrieval_event_id','decision_event_id','actual_action_event_id','patch_sha','oracle_run_id','oracle_outcome','host_feedback_id','graph_before_hash','graph_after_hash','successor_session_id','new_query_event_id','confidence_scope','limitations','raw_evidence_paths'];rows=[]
for s in ses['sessions']:
 rows.append({'claim_id':'native-'+s['label'],'gate':'V5','old_or_new':'NEW','source_head':C['head'],'source_path':'integrations/codex_agent.py','source_sha':sha(W/'integrations/codex_agent.py'),'agent_session_id':s['thread_id'],'provider_request_id':'NOT_OBSERVED;actualresponseIDsinrawbroker','parent_child_identity':'SINGLE;0observedchildren','patch_sha':diag['submission_sha256'] if s['label']=='s1' else '', 'oracle_run_id':diag['diagnostic_run_id'] if s['label']=='s1' else '', 'oracle_outcome':'POSTMORTEM28PASS;ORIGINALNOT_RUN' if s['label']=='s1' else 'NOT_RUN','confidence_scope':'Actualonline/model/runtime/typedraw; NOTcompleteautomaticE2E','limitations':s['failure_kind']+';nativeexit1;noquotaextension','raw_evidence_paths':s['raw_native_path']+';'+s['model_transport_path']})
rows.append({'claim_id':'host-controlled-feedback','gate':'V5','old_or_new':'NEW_HOST_CONTROL','source_head':C['head'],'source_path':'aevora_core/src/aevora/candidate.py','source_sha':sha(W/'aevora_core/src/aevora/candidate.py'),'patch_sha':diag['submission_sha256'],'oracle_run_id':control['diagnostic_run_id'],'oracle_outcome':'PASS28','host_feedback_id':control['candidate_id'],'graph_before_hash':control['source_before_sha256'],'graph_after_hash':control['source_after_sha256'],'successor_session_id':next(x['thread_id'] for x in ses['sessions'] if x['label']=='s2'),'new_query_event_id':'NONE_SUCCESSFUL','confidence_scope':'VerifiedHostdiagnostic/privatepublication;notAgentproposal','limitations':'NoactualnativeS2inheritance;causalUNKNOWN','raw_evidence_paths':str(E/'06_live_agent/host_controlled_feedback')})
for gate,path in [('V0','00_environment/V0_RESULT.json'),('V1','01_source/V1_RESULT.json'),('V2','02_regression/regression_summary.json'),('V3','04_falkordb/V3_RESULT.json'),('V4','05_product/V4_RESULT.json')]:rows.append({'claim_id':gate.lower(),'gate':gate,'old_or_new':'NEW','source_head':C['head'],'source_sha':sha(E/path),'confidence_scope':'Actualdeclaredscope;static/model/SDKdistinct','limitations':'SeeLIMITATIONS_AND_UNKNOWN','raw_evidence_paths':str(E/path)})
with (A/'RUN_PROVENANCE_MATRIX.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print('Reports built; V5explicitINCOMPLETE; no source/historical grade mutation')
