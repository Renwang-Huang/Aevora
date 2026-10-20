from runtime import *
import shutil,uuid
review=W.parent/'Aevora_PreGen2_V5_Supplement_Final_Independent_Review_2026-10-15.md'
assert review.is_file();shutil.copyfile(review,E/'00_environment/INDEPENDENT_REVIEW.md')
write(E/'00_environment/INDEPENDENT_REVIEW_RECEIVED.json',{'at':now(),'status':'READ_IN_FULL','source_path':str(review),'sha256':sha(review),'prior_missing_status':'NOT_FOUND at initial locator; supplied subsequently','accepted_historical_verdict':'EVIDENCE_PACKAGE VERIFIED; V5 INCOMPLETE; PRE-GEN2 CONDITIONAL; NATIVE SINGLE; CAUSAL UNKNOWN'})
versions="import json,sys,sqlite3,importlib.metadata as m;print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'packages':{n:m.version(n) for n in ['mcp','pydantic','falkordb','redis','pytest','aevora-core']}}))"
assert record('c0-runtime-versions',runtime('-c',versions))==0
assert record('c0-cli-version',runtime('-c',"import subprocess;subprocess.run(["+repr(str(E/'owned_runtime/native/codex'))+",'--version'],check=True)"))==0
assert record('c0-cli-help',runtime('-c',"import subprocess;subprocess.run(["+repr(str(E/'owned_runtime/native/codex'))+",'exec','--help'],check=True)"))==0
assert record('c0-cli-features',runtime('-c',"import subprocess;subprocess.run(["+repr(str(E/'owned_runtime/native/codex'))+",'features','list'],check=True)"))==0
assert record('c0-provider-tls',runtime('-c',"from scripts.m11_calibration import tls_probe;import json;print(json.dumps(tls_probe('https://api.renwang-huang.top/v1')))"))==0
seed="from aevora.graph_repository import GraphRepository;from aevora.historical_import import import_verified_history;from pathlib import Path;p=Path("+repr(str(R/'m1_validation'))+");a=Path((p/'CURRENT').read_text().strip());a=a if a.is_absolute() else p/a;r=GraphRepository.from_environment();r.initialize();print(import_verified_history(r,a));r.close()"
assert record('c0-owned-legacy-verified-history',runtime('-c',seed,history=True))==0
graph='aevora_v5c_live_'+uuid.uuid4().hex
write(E/'00_environment/LIVE_GRAPH_ID.json',{'graph':graph,'separate_from_regression_graph':True})
(E/'00_environment/C0_BASELINE_AND_PROTOCOL.md').write_text('''# V5 Closure C0 baseline and pre-registered protocol

Frozen active repository HEAD737f1746631774251a2c504aaf0ceafd9c3ff0c0 / Tree7fad4fffdad4c9a85ae9e521928b6a6592a4dcb9 remains clean. All547 G5-defined paths match. Independent review received/read; supplement ZIP and old Full manifest hashes freshly matched. Historical ERROR/NOT_RUN, postmortem28PASS and failed S2 remain unchanged.

Independent ordinary Git clone uses --no-hardlinks and own v5-closure branch; no shared objects/alternates or changes to active Git. Patch scope: typed public MCP context/errors plus discretionary experience/reflection prompt; original Oracle/fixtures/truth remain unchanged. Full1836 identities must be retained after product changes, additive new tests separate.

Owned copied Python3.12/SQLite toolchain, official Codex binary/helper, fresh venv and authenticated FalkorDB4.20.4 instance17707. Credentials remain external0600/0700; Host holds upstream key. Private history driver only trusted regression/import; no permanent host aliases and no historical mount into Participant.

Preflight S0: originalSMOKE-001, real native single-mode repair with existing8-test independent Oracle; checks natural submission/strict patch extraction. Not S1/S2 grade and no experience seed/proposal. C1 live challenge blocked until real MCP, request policy, transport/isolation and submission gates pass.

S1: fresh D-v01 faulty participant, original28 hidden cases. Single native Session; actual MCP four-tool proposal capability. Neutral public Issue only, no previous patch/source/hidden answer; experience graph seeded with four genuinely verified historical outcome controls and bounded public strategy summaries. Reflection is encouraged, tool calls and proposals are not emitted by Host or forced to fabricated IDs/answers.

S2 selection rule fixed before S1: after actual Agent-source publication, prefer existing A-v01 if Core says newly published bounded conditions APPLY for A public facts; otherwise use fresh D-v01. This is a public-scope compatibility choice, not grade-driven selection. Save Host selection check separately; it is not S2 retrieval. S2 must itself query/bundle/decide, act and naturally submit. A uses original14 checks, D uses original28. Same-template fallback supports instance-level inheritance only; no broad generalization/causal claim. No S1 messages, patch or grades given to S2, no designated experience ID in its task.

Policy: request_budget=None; timeout_seconds=None; completion-aware; gpt-5.6-terra/max, no silent downgrade; Provider concurrency2, sequential Sessions, no dollar/token/request-total stop or cumulative40 allocation. Finite retry2/streamretry2, TLS/authentication/framing/body limits, memory2GiB/pids768/file bounds, official SSE idle guard and runtime cancel remain. Slow inflight requests/collaboration waiting do not trigger a total task deadline.

Pre-registered faults: security/credential/original asset drift fail closed; real Provider401/403/429/stream failure recorded separately; native retry exhaustion preserves exit/error. Alert on absent progress, inspect actual inflight/child/process/tool activity; never classify healthy waiting as timeout. Same semantic error without any corrective progress is an operator-review fault, not a request quota. No automatic fresh main-task rerun to erase failures. No originalERROR may be upgraded by diagnostics. Oracle failure remains taskFAIL. No valid native proposal/publication makes positive succession incomplete; no Host seed substitute.

C4: actual MCP APPLY/VERIFY/ABSTAIN/negative transfer, foreignQuery/proposal/Outcome/publication denials, graph edge cut/restore and owned DB outage with no success fallback. Host controls are distinct from model decisions. C5 seals original native events/JUnit/patch/outcomes/graph receipts, raw failures and minimal source diff; Full/Lite original/export hash maps and read-only independent verifier. No Memory comparison CONTROL_NOT_RUN; CAUSAL_BENEFIT UNKNOWN; no new multi-agent claim without child proof.

After delivery: stop. No merge/push/public release/Gen2 or historical Oracle rewrite.
''')
write(E/'00_environment/CONFIG_EFFECTIVE_REDACTED.json',{'at':now(),'completion_policy':'completion-aware','timeout_seconds':None,'request_budget':None,'usd_budget':None,'token_total_budget':None,'cumulative_request_quota':None,'model':'gpt-5.6-terra','reasoning_effort':'max','agent_mode':'single','max_request_concurrency':2,'parallel_sessions':1,'native_stream_idle_timeout_ms':3600000,'http_retries':2,'stream_retries':2,'security':'Original physical participant/candidate isolation and scoped MCP/Gateway; Host-only credentials','manual_cancel':'Existing RuntimeControl/status/snapshot/cancel','frozen_Oracle':'Original8/14/28 suites selected by existing episode/variant','historical_native_scores_unchanged':True})
print('C0_PREREQUISITES_AND_PROTOCOL_RECORDED',flush=True)
