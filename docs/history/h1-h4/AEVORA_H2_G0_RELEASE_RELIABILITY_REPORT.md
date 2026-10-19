# Aevora H2-G0 — Release, Recovery and Security

## Verdict and source boundary

**G0 required functional evidence: PASS. Security remains PARTIAL; this is not an unconditional adversarial isolation or zero-loss durability claim.** New Codex model calls are deferred to G3 and are not credited here.

All new evidence is under `aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/` (below, `A`). `A/G0_GATE.json` contains relative references and actual file hashes.

The inherited root worktree was already dirty. H1 live input, post-live corrections and the current tree are recorded separately in `A/g0/BASELINE.json` and `BASELINE_SOURCES.json`. A new local source repository was created under `aevora_validation/h2_worktrees/`; the frozen G0 source commit is **`bfa5db6a71ee2f85324f94b67d25c2dcc4319d9f`**. It is a new H2 commit, not a reconstructed historical H1 commit. No push, root-index staging, reset or history rewriting occurred.

## Actual clean rebuild

`g0-final-clean-rebuild/command.json` records the exact argv, UTC times, exit **0**, and **198.465 s**. The command executed `aevora_core/scripts/rebuild_h2.py` with the source repository/commit, a previously absent destination, independently downloaded runtime, inherited identity manifest and an isolated FalkorDB endpoint.

The entry cloned without hardlinks, checked out the pinned commit, created a new venv, downloaded pinned dependencies without the personal pip/uv cache, installed both projects, made authenticated real schema/graph queries, ran the full tests and checked the source remained unchanged. `g0-clean-rebuild/REBUILD_RESULT.json` records **1295/1295 PASS**, no failures/errors/skips/duplicate identities, and all **1214** inherited identities. Python **3.12.14**, SQLite **3.46.1** and `pidfd_open` were observed inside the new runtime. JUnit SHA256: `caa93ef9727e75b76c36a4ce27c80cd225ff73a543cd415671dc47dec0c180de`.

The fresh runtime download has separate command receipts. Its deployment commit is `0ad7bef7a8e69b26b7e0d666a11b60dca10461c23cc0d2ee5391991c559c28c7`, SDK 24.08.37. This upstream branch is **EOL**; reproducibility does not imply current security maintenance. Linux namespaces, delegated cgroups, Docker, Git, uv and public network access remain explicit prerequisites, not bundled infrastructure.

Earlier attempts remain archived: inherited host ROS pytest contamination; isolated invocation unable to import the checkout namespace; standalone Python lacking the `/usr/bin/python3.12` layout and `pidfd_open` (**1161 PASS / 53 FAIL**); and an explicitly cancelled optional GPU extension download. No assertion was weakened. `g0/RUNTIME_COMPATIBILITY_FAILURES.json` identifies these failures and the corrected environment.

## Existing Benchmark regression

`g0-inherited-cli-regression/command.json`: exit **0**, **172.062 s**. `g0-cli-regression/summary.json` retains all 15 inner commands and real reports:

- SMOKE-001: Buggy **FAIL / 8 tests**, Reference **PASS / 8**.
- Episode A: Buggy **FAIL / 14**, Reference **PASS / 14**, reference Run `4044295c-9917-4af9-84cb-132aae11da6c`.
- D-v01: Buggy **FAIL / 28**, Reference **PASS / 28**, alternative flock **PASS / 28**. Reference Run `c6976173-932a-49bb-9b0d-a1d10a822b2e`.
- B/C: **NOT_IMPLEMENTED**; invalid submission **ERROR / exit 2**; explicitly reduced evaluator timeout **TIMEOUT / exit 3**; prepare/report/reset passed their own checks.

The aggregate exit 0 means these expected classifications were verified, not that every business submission passed.

## RDB recovery and AOF failure

`h2-g0-rdb-recovery-admitted/command.json`: exit **0**, **30.591 s**. `g0_recovery_admitted/RECOVERY_GATE.json` and its independent closure review cover **42/42 tests**, 36 raw command receipts including final cleanup, exact schema constraints, graph nodes/edges and evidence paths. The isolated graph moved from **27 nodes / 24 relationships** to **43 / 61** after an actual trusted historical feedback replay. SIGKILL produced real container exit **137**. Restart restored **27 / 24**; the unsaved tail was demonstrably lost. Re-ingesting the same trusted Outcome twice restored identical **43 / 61**, idempotently.

Two separate empty-volume cold restores loaded the actual RDB and matched paths/constraints. Damaged backup and divergent-tail verification each rejected with exit **2**. The three trial services were stopped. H1's volume was not written or stopped.

Checkpoint Manifest SHA256: `6abaee47cff8c6b0efea767fcf954bddece3142abaa657c93746e33bfbe5201c`. Actual RDB SHA256: `f64e8e8db33e6f5db87e25c0b40dc322b2e04dcba2d89007577554fbe476b097`.

AOF replay used an isolated copy of historical bytes and reproduced **exit 139 / SIGSEGV 11**. Its first collector parsing failure is retained separately from the corrected collector. An exact causal match to an upstream issue is **UNVERIFIED**. AOF was not repaired and did not block the verified RDB workflow. The RPO boundary is the last explicit SAVE. Power failure, storage-controller behavior, cross-host recovery and zero-loss durability are **UNVERIFIED**. Writer quiescence remains a trusted-maintainer precondition. A new SDK connection is not a new Codex Session; a real post-recovery Session belongs to G3.

## Authorization and isolation

`security/SECURITY_GATE.json` records **56 actual MCP/real-graph checks**, **61 raw JSON-RPC messages**, **134/134 runtime contract tests** (105 inherited + 29 new), and actual three-layer probes. Unauthorized tools/Cypher/resources, forged Verified Outcome, wrong run/token/nonce/peer UID, replay, revocation, SDK disconnection and database disconnection were rejected or classified. The four historical Outcome records remained unchanged. Gateway TTL expiration yielded actual HTTP 401 with zero upstream calls. The upstream in those contracts is explicitly synthetic, not credited as a model challenge.

Outer Participant, native command sandbox and candidate business sandbox denied the tested private paths and private TCP endpoints. The initial EPERM probe-classification failure is retained; only the probe was corrected. No sandbox boundary was loosened. The per-run MCP capability identifies a Run, not an individual child Agent. Untrusted text being data does not prove model-level prompt-injection immunity. Shared-kernel/admin/side-channel security remains **PARTIAL**.

## Reproduce and limitations

See `aevora_core/docs/H2_REBUILD.md`, `H2_CHECKPOINT_RECOVERY.md` and `H2_SECURITY.md` for exact executable commands and secret injection. Root secrets are external owner-only files; no credential contents or hashes are archived. Each command directory preserves stdout/stderr bytes, hashes and timestamps.

`G0_FINAL_HISTORY_IDENTITY_GATE.json` checks all **101084** protected historical files, **57** old task-truth files, inherited developer-test source bytes and the 1214 identities against the new clean JUnit. Local hashes and self-review are not third-party immutable attestation. AOF/EOL/shared-kernel risks remain explicit inputs to the final H2 risk verdict. Governance benefit is **UNVERIFIED**; G0 establishes engineering reproducibility and measured boundaries.
