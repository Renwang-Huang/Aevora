# Aevora H2 — Execution Plan

Authoritative task: `Aevora_H2_Governance_Robustness_Generalization_Codex_Task_v1.0.md`.
This is authorized engineering implementation, deployment and dynamic validation.

## Audited baseline

- H1 remains CONDITIONAL PASS; its 1214/1214, native D Run and read-only observation are historical results, not new H2 results.
- The accepted H1 Audit-Lite SHA was rechecked: `d38db23087f702b5f5320428b5e622a56de7aa2eacad25ad4ed8373e0bc4708e`.
- Current post-live Broker SHA `1026f28623ffcbec3e2739004e817c16178fef3659968d01ba925bb2ff1fd4e4` and demo SHA `051821f1497d4ca02fab22e950cd3fe6d2aeb2b8d5efd8acc423943cbf1b2bc7` are distinct from H1-live frozen bytes.
- H2 capture verifies 252 source files, 101,084 protected historical files, 1214 inherited identities and 57 frozen task-truth files. The current dirty checkout is retained on `aevora-h2-governance-20261011`.
- A new isolated local source commit `65f0ee7a9004b08b4ea49c163476a94f041c2cb1` identifies captured post-live bytes; it is not a fabricated historical H1 commit.
- H1 database remains running/healthy. Its sole volume is protected; H2 uses a separate Compose project, volume, authenticated service and port 17679. Destructive recovery experiments use additional private projects/volumes/ports.
- The named optional Context Handoff document was not found in the workspace.

## Implementation order

1. **H2-G0:** source/history freeze; freshly downloaded Python3.12.13, empty venv and public dependency installation; executable clean-source rebuild; independent real graph/MCP/core regression; checkpoint/backup/restore and failure injection; authorization/replay/disconnect/isolation checks. Retain AOF and shared-kernel limitations.
2. **H2-G1:** reuse immutable records, Cypher paths and Resolver; add explicit conflict/scope/revision/evidence-lifecycle and replayable query-snapshot semantics. Preserve legacy hash/API and UNKNOWN attribution. All controlled fixtures stay outside challenge graphs.
3. **H2-G2:** fully review D-v02 Lease/Authority design; implement a separately registered D-family variant, public package, private Oracle, Buggy/Reference/legal alternatives and known-invalid controls. Freeze before Participants; run each required control at least10 times.
4. **H2-G3:** freeze final sources, private Oracle fingerprint and a reviewed graph baseline; native fresh Codex Multi-Agent/MCP challenge; original submission and independent outcome; trusted ingestion; different fresh real Session rereads updated evidence. All started Runs remain in the denominator.

## Compatibility and trust risks

Revision selection, evidence scope and snapshot semantics must not silently reinterpret old H1 records. D-v02 must preserve A/D-v01 fixtures, Oracle and API; the generic Runner remains the lifecycle authority. Participant never receives reference/private labels, graph admin or trusted-feedback capabilities. MCP calls, Decisions, observed action, task verdict and causal attribution remain distinct. Completion-aware continues with finite transport/concurrency/resource limits and explicit cancel.

## First executable validation

```sh
scripts/aevora-python -m pytest -q tests aevora_core/tests --junitxml=<new-H2-archive>/G0_JUNIT.xml
```

Actual commands, exits, timestamps and log hashes are recorded under `aevora_validation/H2_CURRENT`. Fresh-source tests additionally use the newly downloaded interpreter/venv, not the maintainer's cached environment. Each Gate receives its own verdict and local source commit/hash; final Full/Lite publication occurs after writers stop. Stop at H2; no B/C or H3 implementation and no formal randomized research experiment.
