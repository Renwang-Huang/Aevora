from audit import *
import csv,xml.etree.ElementTree as ET
J=lambda p:json.loads((E/p).read_text())
source=J('source/SOURCE_IDENTITY.json');public=J('final/PUBLIC_GIT_RECEIPT.json');build=J('final/approved-build/RESULT.json');safety=J('final/security/PUBLIC_BOUNDARY.json');accept=J('final/acceptance_verified/CLEAN_INSTALL_RESULT.json');browser=J('final/browser-framed/RESULT.json');video=J('final/video-framed/VIDEO_RECEIPT.json');necessity=J('final/graph-necessity/FALKORDB_NECESSITY_RECEIPT.json');identities=J('12_release_regression/EXACT_IDENTITY_RECEIPT.json');cli=J('12_release_regression/benchmark-cli15/summary.json')
assert all(v['status']=='PASS' for v in [safety,accept,browser,video,necessity,identities,cli])
assert source['clean'] and source['head']==public['source_commit'] and public['files']==164
rows=ET.parse(E/'01_tests/RELEASE_NEW32.xml').findall('.//testcase');assert len(rows)==32 and all(not any(x.tag in {'failure','error','skipped'} for x in r) for r in rows)
status='RELEASE_CONDITIONAL'
components={'PRODUCT_CORE':'PASS — scoped public Graph v2/Core/MCP and inherited compatibility','DEMO':'PASS — live synthetic + sanitized historical replay, actual browser/video','PUBLIC_CLEAN_INSTALL':'PASS — fresh independent public Clone/volumes, installed packages, 9 public tests, official MCP','PUBLIC_SECURITY':'PASS_BOUNDED — selected tree/full proposed history/distributions/image; no general vulnerability-free claim','HACKATHON_PROVENANCE':'DOCUMENTED; ELIGIBILITY_UNVERIFIED — actual Git dates and AI/source disclosure','SUBMISSION_ASSETS':'LOCAL_READY; URL/PUBLICATION_USER_ACTION_REQUIRED','G24_CAUSAL_EXPERIMENT':'NOT_RUN; CAUSAL_BENEFIT_UNKNOWN','FALKORDB_RELIABILITY':'CONDITIONAL; SIGSEGV139_ROOT_CAUSE_UNVERIFIED; explicit SAVE normal restart only'}
commands=[]
for p in sorted((E/'commands').glob('*/receipt.json')):
 d=json.loads(p.read_text());commands.append(dict(label=p.parent.name,receipt=str(p.relative_to(E)),receipt_sha256=sha(p),**d))
write(E/'G2_FINAL_COMMAND_INDEX.json',commands)
reasons={
 'public-graph-seed':('RUNTIME_CONFIGURATION','New test namespace lacked required aevora_v2_ prefix. Own configuration corrected; no policy changed.','commands/public-graph-seed-prefix-corrected/receipt.json'),
 'final-inherited-1897':('ACTUAL_REGRESSION_AND_FIXTURE_ERROR','73 failures from accidental maintainer/public script name collision; 32 errors from missing historical graph fixture. Maintainer script restored byte-for-byte, public launcher renamed, unchanged historical corpus imported read-only.','12_release_regression/EXACT_IDENTITY_RECEIPT.json'),
 'final-graph-v2-108':('SOURCE_EPOCH_GUARD','108 pytest cases passed but wrapper correctly rejected concurrent execution source edits; this first result is not accepted as a valid passing epoch.','commands/release-graph-v2-108/receipt.json'),
 'browser-actual-attempt2':('ACTUAL_UI_DEFECT','Offline message lacked explicit fallback wording and Cytoscape attempted inline stylesheet rejected by CSP. External stylesheet and explicit offline error fixed; no CSP weakening.','final/browser-framed/RESULT.json'),
 'staged-whitespace-check':('LINT_AND_GENERATED_ASSET','CSV CRLF normalized. Upstream generated Cytoscape shader whitespace preserved, excluded only from authored whitespace lint; no test exclusion.','commands/authored-whitespace-check/receipt.json'),
 'public-final-clean-install':('ACTUAL_DEPLOYMENT_DEFECT','Fresh Docker state directory0755 correctly rejected by new0700 guard. Dockerfile now creates0700 state before volume initialization.','commands/safe-public-clean-install/receipt.json'),
 'historical-audit-receipt-kind-assumption':('COLLECTOR_ASSUMPTION','Audit expected nonexistent PublicationReceipt label. Actual production Q07 stores SourceVerification with PUBLICATION_COMMITTED and manifest/head/epoch. Auditor now checks the actual Host receipt and original status/hash, not a fabricated schema.','13_historical_review_final/HISTORICAL_SUMMARY_RECEIPT.json'),
 'safe-install-import-all-core':('COLLECTOR_CONTRACT_ASSUMPTION','Optional legacy aevora.audit_capsule intentionally refuses private MAINTAINER_ONLY import. Corrected auditor requires exactly this refusal and all30 ordinary module imports. Product/old tests unchanged.','commands/verified-safe-install-import-all-core/receipt.json'),
 'verified-safe-clean-public-junit-copy':('ARTIFACT_COLLECTION','docker cp could not see the live tmpfs JUnit; direct owned container exec read succeeds. Original9 PASS and exact XML preserved; no score regeneration.','commands/verified-safe-junit-exec-stream/receipt.json')}
failures=[]
for r in commands:
 if not r['exit']:continue
 c,reason,recheck=reasons.get(r['label'],('UNCLASSIFIED','See raw receipt and stdout/stderr.',''))
 failures.append(dict(label=r['label'],exit=r['exit'],start=r['start'],receipt=r['receipt'],receipt_sha256=r['receipt_sha256'],classification=c,explanation=reason,recheck=recheck,original_preserved=True))
failures += [dict(label='browser-attempt1',classification='ENVIRONMENT_MISSING_BROWSER',evidence='04_browser/attempt1/RESULT.json',explanation='Chromium missing; actual official Playwright browser installed, later browser runs passed.',original_preserved=True),dict(label='first-public-boundary-audit',classification='PUBLIC_EXPORT_BOUNDARY_DEFECT',evidence='10_security/PUBLIC_BOUNDARY.json',explanation='Original broad Core doc selection included private absolute paths in historical H2 recovery validation. Original report unchanged; explicit public doc list now excludes it and H1 private reproduction instructions. Rejected candidates remain private and are not for publication.',recheck='final/security/PUBLIC_BOUNDARY.json',original_preserved=True),dict(label='pre-freeze-launch-administration',classification='COLLECTOR_ORDERING',explanation='A requested frozen regression driver was absent after whitespace lint aborted the preceding commit. The shell exited2 before pytest ran; it is not a regression score. Driver generated after successful commit and complete regression then executed.',capture='Conversation tool receipt; no fabricated original timestamp/log file'),dict(label='initial-historical-audit-direct-run',classification='COLLECTOR_ASSUMPTION',explanation='Same incorrect PublicationReceipt assumption as recorded follow-up; original direct tool output and unchanged attempt1 script retained.',capture='Conversation tool receipt and historical_receipts.py; recorded repeat has exact stdout/stderr'}]
write(E/'G2_FINAL_FAILURE_LEDGER.json',dict(status='PRESERVED',failures=failures,expected_negative_cli='Business FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED are separately checked expected results in CLI15; not repaired into PASS.',scope='No original test assertion deleted or relaxed; previous candidates/epochs are superseded, not rewritten.'))
write(E/'G2_FINAL_GIT_RECEIPT.json',dict(base=source['base'],release_commit=source['head'],release_tree=source['tree'],private_worktree=str(P),public=public,tag='aevora-gen2-rc1',public_history='One fresh product-only commit; all proposed history scanned. Maintainer history not exported.',private_history_preserved=True,remote_head='UNVERIFIED_SSH_AUTHENTICATION_FAILURE',github_push=False,visibility_change=False,competition_submission=False))
claims=[
 ('C01','Independent G23 product baseline and protected implementation retained','PASS','source/BASELINE_PRESERVATION.json','Git tracked scope; not a new full historical-disk scan'),
 ('C02','2109 inherited identities and86 contracts pass with no missing/skip','PASS','12_release_regression/EXACT_IDENTITY_RECEIPT.json','No new model experiment is inferred from developer tests'),
 ('C03','32 new release product/public checks','PASS','01_tests/RELEASE_NEW32.xml','23 private product cases plus9 public cases; do not double-count clean repeat'),
 ('C04','Independent Benchmark CLI15 preserves real positive/negative outcomes','PASS','12_release_regression/benchmark-cli15/summary.json','Expected buggy FAIL is not a passing submission'),
 ('C05','Public Core installs/imports without private Benchmark/Host body','PASS','commands/verified-safe-install-import-all-core/stdout.log','One deliberately unavailable private legacy alias is required to refuse'),
 ('C06','Clean public installed tests9 cases pass','PASS','final/acceptance_verified/PUBLIC_JUNIT.xml','Public synthetic verifier; not private OrderFlow Oracle'),
 ('C07','Actual official MCP four tools and unauthorized field refusal','PASS','commands/verified-safe-official-mcp-four-tools/stdout.log','SDK acceptance, no model/Native execution; proposal remains untrusted/unpublished'),
 ('C08','Actual FalkorDB APPLY/ABSTAIN/VERIFY and withdrawal','PASS','final/acceptance_verified/CLEAN_INSTALL_RESULT.json','Two owned synthetic states, no production Q07 claim'),
 ('C09','FalkorDB disconnection fails503 with no replay fallback','PASS','final/graph-necessity/FALKORDB_NECESSITY_RECEIPT.json','Normal explicit SAVE/restart; no crash/engine fix'),
 ('C10','Public164 files, Git history, ZIP/wheel/sdist boundary','PASS_BOUNDED','final/security/PUBLIC_BOUNDARY.json','No known-secret/private-byte/path matches; not proof of no vulnerability'),
 ('C11','Owned image layer known-credential scan','PASS_BOUNDED','final/image-audit/IMAGE_SCAN.json','6764 regular layer members; known credential values only'),
 ('C12','Real browser10 checks with zero JS errors','PASS','final/browser-framed/RESULT.json','No mocked HTTP/model responses'),
 ('C13','Actual unedited video with optional time-aligned captions','PASS','final/video-framed/VIDEO_RECEIPT.json','Hosted URL remains USER_ACTION_REQUIRED'),
 ('C14','Historical G23 report/patch/child raw-reference links rechecked','PASS_HISTORICAL','13_historical_review_final/HISTORICAL_SUMMARY_RECEIPT.json','285 original line hashes; not a new model challenge or independent attestation'),
 ('C15','S2 Core APPLY versus actual Agent VERIFY preserved','PASS_HISTORICAL','13_historical_review_final/HISTORICAL_SUMMARY_RECEIPT.json','Host follow-up distinct from natural proposal publication'),
 ('C16','Public source ZIP deterministic on this environment','PASS','final/approved-build/RESULT.json','Wheel/sdist byte reproducibility not claimed'),
 ('C17','Actual source/contribution/AI provenance documented','DOCUMENTED','00_baseline/PRODUCT_PROVENANCE.json','Organizer eligibility UNVERIFIED; dates not rewritten'),
 ('C18','FalkorDB SIGSEGV139 root cause fixed','UNVERIFIED','PUBLIC_RELEASE_RISK_MATRIX.json','No crash diagnosis/reproduction attempted'),
 ('C19','G24 comparative causal gain','UNKNOWN_NOT_RUN','G2_FINAL_RECOVERY_RECEIPT.json','Pilot/formal NOT_RUN; separate DeepSeek protocol unchanged'),
 ('C20','Future reproducibility of every transitive dependency','LIMITED','final/DEPENDENCY_LIMIT.json','Direct deps/images pinned; resolved full versions captured, no transitive lock claim')]
with (E/'G2_FINAL_CLAIM_TO_EVIDENCE.csv').open('w') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['claim_id','claim','status','evidence','sha256','limit'])
 for ident,text,state,path,limit in claims:
  assert (E/path).is_file(),path;w.writerow([ident,text,state,path,sha(E/path),limit])
component_table='\n'.join('| '+k+' | '+v+' |' for k,v in components.items())
report=f'''# Aevora Gen2 FINAL release validation

Final status: **{status}**. Local productization and bounded delivery checks completed. This is a local release candidate; production reliability, remote identity and official eligibility are not certified.

## Source identity and authority

- Current user override: Codex/GPT-6.1 Sol xhigh is primary engineering/review Agent. No new Participant model experiment was run.
- Base commit `{source['base']}`, Tree `68fdf6d3b045040d2b52d181e05cf84d7f36ce9e`.
- Release commit `{source['head']}`, Tree `{source['tree']}`.
- Product-only public commit `{public['commit']}`, Tree `{public['tree']}`, tag `aevora-gen2-rc1`.
- Private independent worktree: `{P}`. Final public staging: `{public['stage']}`. Local clean clone: `{public['clone']}`.
- G23/G24 original clean commits and protected source bytes rechecked. No frozen Oracle, reference patch, historical score, G24 protocol or remote changed. See source/BASELINE_PRESERVATION.json.
- Regressions started at f1bf13c; only deploy/Dockerfile state mode changed subsequently. All execution-source epoch hashes stayed identical; final fresh Docker installation separately verifies that deployment fix. See RELEASE_SOURCE_FREEZE.json and each RUNTIME_SOURCE_EPOCH.json.

## Component results

| Component | Result |
|---|---|
{component_table}

## Gate completion

| Gate | Local result | Evidence |
|---|---|---|
| G25-0 | Baseline/provenance/release scope verified; remote read UNVERIFIED | IDENTITY, recovery receipt, provenance, risk matrix |
| G25-1 | Independent public install and real Graph/MCP path PASS | final/acceptance_verified, graph-necessity |
| G25-2 | Three-page Decision Journey and historical/source separation PASS | final/browser-framed, historical review |
| G26-0 | English README/graph/Cypher/deployment/limits/AI disclosure delivered | public164-file selection |
| G26-1 | Public boundary, proposed history, distributions and image checks PASS_BOUNDED | final/security, image-audit |
| G26-2 | Local tag, packages, real138-second video and submission fields delivered | final/approved-build, video-framed |
| G26-3 | Reports, exact hashes, Full/Lite and verifier provided | final delivery receipts outside sealed Full |

## Implementation and reuse

The existing Graph v2 repository, complete Witness/arbitration, bounded four-tool MCP service, Q07/TrustedHost private implementation and read-only Console boundaries were reused. Existing WHEN/WHY and private Host logic did not change. New modules provide a separately executed public SQLite verifier, explicitly synthetic owned graph states and a trusted local MCP example. The optional `/api/journey` projection reuses the resolver; no fixed answer table or replay fallback was added. Public source excludes production Host authentication/pins and private OrderFlow. The legacy maintainer `scripts/aevora_demo.py` is byte-identical to base; the public launcher is `scripts/aevora_public_demo.py`.

The three Console pages show actual graph paths and three-state recommendations, followed by separate sanitized historical G23 evidence. S1_05 and S2 original reports are28/28 each; both have3 verified/completed native children and parent receipts. This review rechecked285 original line hashes plus reports/patches. S2 Core APPLY is distinct from its actual recorded VERIFY; subsequent support was Host-approved follow-up, not direct natural S2 publication. These are historical selected final runs, not a new challenge or an all-attempt success-rate estimate. Original failed G23 attempts remain in their prior Full. Public hashes do not externally attest private Oracle assertions.

## New dynamic verification

| Suite/check | Actual result | Primary receipt |
|---|---|---|
| Inherited developer |1897/1897 PASS|12_release_regression/inherited-1897/JUNIT.xml|
| Graph v2 |108/108 PASS|12_release_regression/graph-v2-108/JUNIT.xml|
| Host/Q07 and Native source |104/104 PASS (58+46)|12_release_regression/host58-native46/JUNIT.xml|
| Contracts |86/86 PASS|12_release_regression/CONTRACT86.xml|
| New product/public |32/32 PASS|01_tests/RELEASE_NEW32.xml|
| Public installed repeat |9/9 PASS|final/acceptance_verified/PUBLIC_JUNIT.xml|
| Existing frontend |6 PASS|commands/node-tests|
| Final actual browser |10/10 PASS, zero JS errors|final/browser-framed/RESULT.json|
| Actual independent CLI lifecycle |15/15 expected checks|12_release_regression/benchmark-cli15/summary.json|

The inherited developer union is exactly2109 identities; with32 new identities and86 contracts this is2227 unique pytest checks. The public9 are repeated clean-install checks, not9 additional unique cases. Counts are validated from raw JUnit, not CLI labels. Actual regression wrappers returned0 with source-epoch guards intact. Starlette/httpx deprecation and upstream warnings are retained.

CLI15 includes SMOKE buggy FAIL/reference8 PASS, A buggy FAIL/reference14 PASS, D buggy FAIL/reference28 PASS, valid flock alternative28 PASS, B/C NOT_IMPLEMENTED, invalid submission ERROR/2 and evaluation TIMEOUT/3. Prepare/report/reset remain independent lifecycle results. No old Oracle assertion changed.

The public container uses Python3.12.14, SQLite3.46.1 for its small default-journal synthetic example; the separate private regression runtime uses Python3.12.14/SQLite3.51.3. They are not claimed as one environment. Direct package/image pins and the actual resolved dependency list are archived; no comprehensive transitive lock or deterministic wheel/sdist build is claimed.

## Reproducible commands

Exact argv/cwd/UTC/elapsed/exit/stdout/stderr digests are in G2_FINAL_COMMAND_INDEX.json and commands/*/receipt.json. These shorter examples describe already executed commands (owned endpoint was19063):

```sh
python regression_release.py
python final_acceptance.py {E}/12_release_regression
# Above trusted maintainer scripts use read-only historical mounts; no Participant model.
python3 scripts/aevora_public_demo.py start --project aevora-safe-6312c046 \\
  --secret-dir "$HOME/.config/aevora/final-6312c046/public-safe" --db-port19082 --console-port19084
```

For copy/paste use spaced options: `--db-port 19082 --console-port 19084` (exact original argv is in safe-public-clean-install/receipt.json). Public setup needs only its exported root; the full source worktree is not a public dependency. The verified running viewer is **http://127.0.0.1:19084/journey.html**. DB and Console publish only loopback; secrets remain outside evidence/source0700/0600. Older owned previews/regression are stopped with data retained.

## Failures and repairs

The first inherited pass attempt actually failed73 and errored32; it is not erased. The original script collision was fixed, the unchanged historical fixture imported, and complete suites re-executed. Other retained failures include missing Chromium, CSP/offline wording, source edits during a validation epoch, generated whitespace/CSV lint, private paths in a rejected public doc export,0755 fresh Docker state, two collector schema/import assumptions and docker-cp tmpfs artifact collection. See G2_FINAL_FAILURE_LEDGER.json for exact references and corrective receipts. None was corrected by deleting tests, loosening Oracle assertions or upgrading a historical grade.

## Public release artifacts and audit boundary

- Public source: final/approved-build/aevora-gen2-rc1-public-source.zip,164 files, {build['source_zip_bytes']} bytes; SHA256 `{build['source_zip_sha256']}`. Repeat ZIP equal on this environment.
- Wheels/sdists: final/approved-build/dist; all actual hashes in RESULT.json and FINAL_RELEASE_MANIFEST.json.
- Video: {video['mp4']}, {video['duration_seconds']} seconds,1440×1000; SHA256 `{video['mp4_sha256']}`. Original WebM, actual clicks/screenshots/trace, separate SRT and external framing-script provenance retained. No UI/model results synthesized; only viewport navigation and format encoding.
- Only `final/PUBLIC_STAGING` and `final/approved-build` are authoritative. Earlier09/root staging candidates are rejected and kept private for failure evidence.
- Full/Lite are **INTERNAL_MAINTAINER_REVIEW**, never product/Participant/competition uploads. Public source/video are separate from these archives.

## Remaining limits and user actions

FalkorDB139 remains root-cause UNVERIFIED. Normal explicit-SAVE restart and unavailable-path refusal pass; unsaved crash tail, AOF recovery and cross-host disaster guarantees are not certified. Shared UID/kernel and in-flight permission revocation limits persist. The public demo uses synthetic authority and an actual public verifier; it is not a public production TrustedHost/Q07 service or new native outcome. G24 Pilot/formal controls remain NOT_RUN and causal gain UNKNOWN; its separate DeepSeek protocol/model are untouched.

Remote `ls-remote` failed SSH publickey authentication, so remote HEAD/content are UNVERIFIED. Owner must review/authenticate the existing repository before any push and approve exact publication/history reconciliation. Upload video and fill its accessible URL, decide repository visibility, verify registration/track/eligibility and submit the competition form manually or by a later explicit authorization. No dates were rewritten; AI/source attribution cannot certify eligibility.

**Stop at G2-FINAL. No new Gen2 feature, G24 challenge, GitHub publication or official submission was started.**
'''
# Keep the illustrative actual launcher command valid rather than requiring correction prose.
report=report.replace('--db-port19082 --console-port19084','--db-port 19082 --console-port 19084').replace('For copy/paste use spaced options: `--db-port 19082 --console-port 19084` (exact original argv is in safe-public-clean-install/receipt.json).','The exact original argv is in commands/safe-public-clean-install/receipt.json.')
(E/'G2_FINAL_RELEASE_REPORT.md').write_text(report)
(E/'G2_FINAL_PUBLIC_SAFETY_AUDIT.md').write_text(f'''# Public safety audit — bounded local release\n\nStatus: **PASS_BOUNDED**. Authoritative stage `{public['stage']}`, commit `{public['commit']}`.\n\n## Verified\n\n- Explicit164 selected ordinary files; no symlink traversal, Benchmark/Oracle/reference/private Host body/credential root.\n- Gitleaks v8.30.1 verified official release checksum; final directory and complete one-commit public history scans exit0. Scanner binary/source receipts: security-tools/SOURCE_RECEIPT.json.\n-485 selected/source-ZIP/wheel/sdist members inspected, zero known credential-byte matches, private original-file hash matches or maintainer absolute-path findings; zero missing relative Markdown links.\n- All9 owned image layers:6764 regular members/171580370 expanded bytes; no known scoped credential values or excluded private payload paths. No general upstream vulnerability scan claimed.\n- Installed ordinary Core imports without OrderFlow/evaluator/maintainer; private optional alias denial remains enforced. No private source/Oracle mount in public containers. External secret-file mounts target only /run/secrets, not build context/image.\n- Actual HTTP loopback Host/origin, closed context/stage selectors, readonly mutation refusals, CSP, concurrency bounds, browser offline data clearing, and real graph-outage503/no fallback checked.\n\n## Failures retained\n\nFirst boundary check rejected H2_RECOVERY_VALIDATION.md's maintainer absolute paths. Original historical documentation stayed unchanged; final explicit doc selection excludes it and private H1 reproduction instructions. Original rejected source/history/ZIP remain private audit evidence and are not publication candidates. Fresh-state0755 install failed, then Dockerfile0700 fixed and new empty volumes passed. Collector expectation and tmpfs-copy failures are not represented as product PASS; raw receipts and exact rechecks remain in the ledger.\n\n## Limits\n\nThis proves the inspected candidate's bounded file boundary and known-secret checks, not absence of every vulnerability or secret in the private maintainer history. Public history is a fresh product-only export. Local Compose is trusted developer deployment, not hostile Participant containment or authenticated remote cloud. Production Host publication/authentication is deliberately not available through the public MCP/browser. Public sources, synthesized fixtures, historical summaries and raw private audit artifacts have distinct visibility.\n\nSourceZIP SHA256: `{build['source_zip_sha256']}`. Core/Console package version remains0.1.0 for compatibility; actual Git/Tree/artifact hashes identify this Gen2 RC. Do not upload Full/Lite or earlier rejected candidates.\n''')
(E/'G2_FINAL_SUBMISSION_CHECKLIST.md').write_text(f'''# Owner publication/submission checklist\n\nLocal status: **{status}**; bounded product/demo/security checks complete.\n\n## Prepared locally\n\n- Product-only Git: final/PUBLIC_STAGING, `{public['commit']}`, tag aevora-gen2-rc1; public source ZIP/wheels/sdists/hashes.\n- Real138-second MP4/WebM, optional SRT, actual UI screenshots, walkthrough and source labels.\n- English README, setup, Graph model, actual Cypher, trust boundaries, limits, licenses, contribution/AI disclosure and submission fields.\n- Full/Lite internal audit with raw failures and JUnit; these are not competition/public artifacts.\n\n## Requires owner decision or later explicit authorization\n\n1. Review final public allowlist, source/video and known reliability/Host limits.\n2. Authenticate and read existing `https://github.com/Renwang-Huang/Aevora`; compare remote history. No force push or remote reconciliation is preapproved.\n3. Approve the exact source commit/branch to push; keep existing private history safe.\n4. Decide when to change repository visibility to public. This task made no change.\n5. Upload the actual MP4 to an owner-selected accessible host and fill Demo Video URL: USER_ACTION_REQUIRED.\n6. Confirm team registration, organizer eligibility, human contribution and proposed Track02 Agent Memory and Coordination. Optional Track01 claims must remain limited to demonstrated connected graph action.\n7. Review docs/SUBMISSION_FIELDS.md and submit the official form; no submission is performed here.\n\nRunning local viewer: http://127.0.0.1:19084/journey.html . This loopback URL is not a remotely accessible Live URL; complete Docker local reproduction is supplied.\n\nStop boundary: no G24 Pilot/formal run, no new Terra/G23 challenge, no Gen2 feature expansion, no push or cleanup of historical data.\n''')
manifest=dict(status=status,at=now(),components=components,base=source['base'],release_commit=source['head'],release_tree=source['tree'],public=public,source_zip={'path':'final/approved-build/aevora-gen2-rc1-public-source.zip','sha256':build['source_zip_sha256'],'bytes':build['source_zip_bytes'],'files':164},distributions=build['artifacts'],docker_images={'python':'python:3.12.14-slim@sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b','falkordb':'falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','built_image':J('final/acceptance_verified/console-runtime.json')['image']},video=video,regression={'inherited':2109,'contracts':86,'new':32,'clean_public_repeat':9,'cli_expected_checks':15,'frontend':6,'browser':10},publication=False,submission=False,remote_head='UNVERIFIED',g24_pilot='NOT_RUN',g24_formal='NOT_RUN',causal_benefit='UNKNOWN',falkordb139='UNVERIFIED_ROOT_CAUSE',artifacts={str(p.relative_to(E)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in [E/'G2_FINAL_RELEASE_REPORT.md',E/'G2_FINAL_CLAIM_TO_EVIDENCE.csv',E/'G2_FINAL_FAILURE_LEDGER.json',E/'G2_FINAL_PUBLIC_SAFETY_AUDIT.md',E/'G2_FINAL_SUBMISSION_CHECKLIST.md',E/'G2_FINAL_GIT_RECEIPT.json',E/'final/security/PUBLIC_BOUNDARY.json',E/'12_release_regression/EXACT_IDENTITY_RECEIPT.json']})
write(E/'FINAL_RELEASE_MANIFEST.json',manifest)
(E/'README_FINAL_DELIVERY.md').write_text(f'''# Aevora G2-FINAL local delivery\n\nStatus **{status}**. Start with G2_FINAL_RELEASE_REPORT.md and FINAL_RELEASE_MANIFEST.json.\n\nAuthoritative public candidate: final/PUBLIC_STAGING and final/approved-build ONLY. Earlier root PUBLIC_STAGING/CLEAN_PUBLIC_CLONE/02/06/08/09 builds are rejected or superseded audit evidence; never publish them. Full/Lite are private maintainer audit material, not product uploads.\n\nLocal viewer: http://127.0.0.1:19084/journey.html . Source commit {source['head']}; public commit {public['commit']}. All old owned preview/regression services are stopped with data retained. Current safe demo remains running for owner review. No remote push, visibility change, contest submission or new model challenge.\n\nSee deliverables for independently checked Full/Lite packages, and DELIVERY_RECEIPT.json for final hashes after sealing. Local hashes are integrity receipts, not external attestation.\n''')
print(status,source['head'],public['commit'])
