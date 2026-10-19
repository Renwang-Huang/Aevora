from audit import *
labels=['g3-regression-final','g3-public-build','g3-console-six-js','g3-physical-isolation','g3-independent-benchmark','g3-independent-dv02','g3-clean-wheel-install','g3-clean-public-real-mcp-console','g3-public-members-credential-scan-attempt2','g3-full-graph-governance-attempt2','g3-codex-actual-official-cli-capabilities']
receipts={}
for label in labels:
 p=E/'commands'/label/'receipt.json';r=json.loads(p.read_text());assert r['exit_code']==0,label;assert sha(p.parent/'stdout.log')==r['stdout_sha256'] and sha(p.parent/'stderr.log')==r['stderr_sha256'];receipts[label]={'receipt_sha256':sha(p),'exit_code':r['exit_code']}
checks=['03_regression/STRICT_IDENTITY_RECHECK.json','03_regression/clean-smoke/RESULT.json','03_regression/package-scan-retry1/PUBLIC_PACKAGE_MEMBER_SCAN.json','03_regression/governance_retry1/RESULT.json','02_fix/capacity/RESULT.json']
for name in checks:assert json.loads((E/name).read_text())['status']=='PASS',name
f=json.loads((E/'source/SOURCE_TRUST_MANIFEST.json').read_text())
for name,h in f['files'].items():assert sha(E/'owned_runtime/source'/name.removeprefix('frozen_source_snapshot/'))==h
write(E/'03_regression/G3_LIVE_ADMISSION.json',{'status':'PASS','at':now(),'commands':receipts,'receipts':{n:sha(E/n) for n in checks},'source_manifest_sha256':sha(E/'source/SOURCE_TRUST_MANIFEST.json'),'patch_freeze_sha256':sha(E/'02_fix/PATCH_FREEZE.json'),'full_graph_no_initial_edge_deletion':True,'security_overall':'PARTIAL shared-kernel legacy limit preserved; actual tested boundaries pass','model_requests_before_admission':0,'preregistered_input_sha256':sha(E/'04_live/FROZEN_EXPERIMENT_INPUTS.json'),'no_dollar_token_total_request_quota':True,'next':'Exactly one new S1 and one new S2 under fixed preregistration; preserve all original outcomes'})
(E/'03_regression/MCP_SECURITY_AND_GRAPH_NEGATIVE_CONTROLS.md').write_text('''# G3 real controls

PASS for tested contracts; global hostile shared-kernel security remains PARTIAL.

Final1897PASS = inherited1868 (original1836+V5C32) plus29 new cases; zero fail/error/skip/duplicate. Raw JUnit/STRICT_IDENTITY_RECHECK use Full original identities, without Lite redaction normalization. Initial1896PASS precedes the memory-retention fix and is preserved separately, not attributed to final code.

Real full84-node125-edge graph control:25 checks on a complete isolated copy, not the old pruned22-check subset. Actual public SDK covers A/D/unknown/lease facts, three states, invalid schema/oversized context, no graph write from refused calls, scoped auth, foreign query, forged cursor/decision authority, forbidden Host tools, edge cut/byte restoration, synthetic conflict and lifecycle withdrawal, forged Host trust pin rejection, actual refused DB connection and reconnection. Raw SDK, client, Cypher and graph receipts are under governance_retry1. First collector chose the legacy schema1.1 default graph and refused schema1.2 checkpoint; that failed command remains. Explicit full-graph retry passed without product changes.

New29 tests include lossless multibyte/RFC6901 reconstruction, exact262143/262144/262145 boundaries, continuation tamper/cross-connection/experience/query/view/expiry, replay/eviction/capacity errors, oversized/nested/invalid UTF8 claims, real graph evidence growth, actual continued-page authorization after CONSIDERED removal/restoration, complete competitor pagination and cache-retention bound. Pure synthetic serialization/contract fixtures do not claim actual Agent outcomes. Full graph scale/feedback contract matrix uses real SDK/DB with synthetic growth labeled.

Public wheels built/clean-installed from explicit product allowlist; independent namespace exposes only public product, clean venv and owned Core DB authority. Maintainer Benchmark and host identity are absent. Genuine installed MCP full graph query/bundle and real Console LIVE HTTP/read-only/error/no-fallback and no-write checks passed. Six JS contracts passed. Actual nested physical isolation probes pass with shared-kernel limitations retained. Independent CLI suites preserve positive/negative/error/timeout/planned behavior; original D-v02 buggy28/36 and Reference36/36 validate36-case Oracle sensitivity. No source/Oracle assertions were weakened.

All commands, exit codes, hashes and source epochs are in commands and G3_LIVE_ADMISSION.json. Public member scan excludes private Oracle/Reference/maintainer data and known credential values/hashes. Two collector path/schema mistakes are recorded, not product PASS substitutes. Real container stop/restart and post-genuine-feedback health remain mandatory G5 work, not implied by these controls.
''')
print('G3_LIVE_ADMISSION_PASS')
