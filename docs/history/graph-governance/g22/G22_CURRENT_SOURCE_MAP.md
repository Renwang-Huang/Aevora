# G22 current source authority

Tested implementation checkpoint: `6c2893f2f589aea236dfcecbbf25a61af20f9cfc`. Final documentation commit is recorded separately in the delivery receipt.
Independent local worktree: `<MAINTAINER_HOME>/data_storage/aevora_validation_runs/G22-20261015T174846Z-88fad40ffd/worktree`. Frozen maintainer and G21 roots remain untouched.

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
