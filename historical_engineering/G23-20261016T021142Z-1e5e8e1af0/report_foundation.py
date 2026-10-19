from audit import *
R=E/'reports';R.mkdir(exist_ok=True)
(R/'G23_SOURCE_AND_TRUST_BOUNDARY_MAP.md').write_text('''# G23 Source and Trust Boundary Map

## Authority and reuse

Base e9e7a7a422828e847b237fa8d3e0450b98a97804 / tree b63c0dda2fc0451eba6ee76a9196aadb8c7bf2e7. Independent bare clone, no alternates or shared object hardlinks; worktree and evidence are external to all frozen sources. No remote push. G21/G22 Full manifests and frozen 547-file first-generation checkout are independently checked; original independent G22 audit document was not found at the supplied location (UNAVAILABLE document bytes). Existing G22 Full handoff, source and raw validation remain the baseline authority.

| Responsibility | Current authoritative code | Privilege |
|---|---|---|
| Official native execution | integrations/codex_agent.py | official codex exec --json; no bespoke agent scheduler |
| Actor lineage | integrations/native_rollout_trace.py, codex_trace.py | official child own-turn tool records and exact parent completion receipts |
| Public experience v2 | integrations/aevora_v2.py, aevora.py | opt-in four tools only, scoped Broker capability |
| Precise source verification | aevora_maintainer/native_source.py, host_v2.py | maintainer only; protected original seals and actual tenant required |
| Independent Outcome | unchanged OrderFlow Runner, Evaluator, hidden suites | candidate code in separate process; host DB Oracle |
| Q07 | unchanged publication_fence.py, host_pins.py, host_v2 prepare/publish | immutable preparation, CAS and authorization fences |
| Arbitration | existing graph_v2.py, graph_queries.py, arbitration.py | real owned FalkorDB, complete witness and catalogue |

Core compatibility change: premise uniqueness is (mode,fact_key), matching the already-declared schema/arbitration, so a necessary condition and an exclusion may concern the same fact. Same-mode duplicate rejection remains. First failing red JUnit is retained. No old assertions, hidden suites, reference patches or app business code are changed.

## Isolation layers

Trusted maintainer namespace sees current source, read-only historical fixtures only when explicitly requested, owned DB credentials and source pins. Participant namespace sees only its new public workspace, public manifest/tests/tool contract, official CLI and scoped model/MCP Unix proxy. Long-term Gateway and graph credentials remain host-only. Child business commands use official workspace-write sandbox; native session state is read-only to those commands. Separate candidate sandbox receives only validated app source and controls; no hidden-test implementation or maintainer source.

Physical reads/forged writes are tested, not just described in prompt. Isolation remains ISOLATION_PARTIAL: shared kernel and host UID, no independent VM or third-party attestation. Native protected logs are local collection authority, not cryptographic provider-signed provenance. No Gateway full HTTP body is invented; metadata and original official tool streams are the captured evidence.

## Runtime profiles and real failure

Original shared owned server 17751 suffered signal11 / exit139, OOMKilled=false. It remains stopped with crash log/RDB retained; root cause UNVERIFIED. Recovery restores only the last explicit SAVE, preserving RPO. New LIVE17752 is isolated from REGRESSION17753; RECOVERY17754 was used for independent restore then stopped. All are newly owned resources. No old H1-H4/G21/G22 DB is touched. See G23_DATABASE_FAILURE_AND_RECOVERY.md and raw Docker command receipts.

## Nonclaims

Model label gpt-5.6-terra/max and authenticated completed transport do not prove internal provider weights. No native role/path is invented where official variant omits it. Timestamp adjacency never assigns proposal actor. Unknown before/artifact facts remain unknown; public declarations are HOST_DECLARED_TASK, not kernel observations. No unseen-task generalization, causal benefit, G24 experiment, new Console or publication is claimed.
''')
(R/'G23_LIMITATIONS_AND_UNKNOWN.md').write_text('''# G23 Limitations and Unknowns

- CAUSAL_BENEFIT=UNKNOWN; Graph/Raw/No Memory controls NOT_RUN in this gate. Oracle PASS is engineering correctness in the bounded task, not proof of memory benefit.
- D/v01 fresh instances do not establish unseen-family generalization. D-v02 Clock UDS historical EPERM is not bypassed or newly claimed fixed.
- ISOLATION_PARTIAL: shared kernel/UID, local seals rather than third-party attestation. Tested file boundaries do not assert protection against a kernel exploit or hostile privileged maintainer.
- Gateway model label is transport evidence, not internal weights. Full upstream HTTP bodies NOT_CAPTURED; original metadata, official JSONL and MCP request/reply bytes are retained where available. Some native role labels/initial encrypted task text can be UNAVAILABLE.
- FalkorDB4.20.4 actual signal11/139 in original shared owned server, OOM false. Root cause UNVERIFIED. Separate resource profiles reduce cross-workload blast radius, not proof the engine defect is fixed.
- RDB last-SAVE recovery and graceful cold restart are bounded durability checks. Unsaved tail, power loss, arbitrary AOF recovery and independent failure-domain backup are not established here.
- 64×8 paired real read measurements are current; no new 100k/300k expansion claimed. Prior G22 scope remains bounded.
- Clean product test is real wheel/HTTP/official MCP SDK validation; it is not a new Chromium visual Console acceptance.
- S1/S2 source claims require exact actor -> own tool -> MCP bytes -> native candidate -> original patch/tree -> independent Oracle. Missing/mismatched facts remain rejected or PENDING; failed original Runs are never upgraded by later diagnostics.
- Historical frozen assets stay unchanged. No GitHub push, cleanup, baseline merge, G24/25/26 or new Gen2 scope has started.
''')
print('foundation reports written')
