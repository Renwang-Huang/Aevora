# M1 Design Review — preimplementation decision and current-state addendum

**Review version:** `1.2.0` · **Reviewer marker:** `maintainer_codex:m1_blueprint` · **Review kind:** static design self-review plus evidence-aware status addendum, not an external independent certification.

**Design conclusion: PASS for implementation readiness.** This review accepts the contracts in [TASK_SYSTEM_DESIGN.md](../../TASK_SYSTEM_DESIGN.md), [TASK_ADMISSION_GATES.md](../../TASK_ADMISSION_GATES.md) and [TASK_RELATIONS.md](../../TASK_RELATIONS.md). **Episode D Engineering/Research/Pilot gates are UNVERIFIED at this preimplementation review.** Their final conclusions require new dynamic evidence and must not be inferred from this design PASS.

The original review and four design documents are preserved in `design_preimplementation/` with `DESIGN_GATE.json` inside the archive identified by [m1_validation/CURRENT](../m1_validation/CURRENT). This working-document update does not edit those historical bytes. **Current D status is IMPLEMENTED**, Scenario `2.0.0`, Fixture `1.0.0`, Suite `1.2.0` with **28** required identities, Evaluator `3.1.0`. It has a real 2/4-worker supervisor, trusted peer/process/FD identity, a direct D Oracle and a stable-flock legal alternative. Earlier exact-artifact A/D strategy measurements and the old Suite `1.0.0` 30-run series remain preserved; new Suite `1.2.0` exact-artifact transfer and 30-run validation are separately linked in [Task Relations](../../TASK_RELATIONS.md). The new cohort has 10 Buggy FAIL, 10 Reference PASS and 10 flock PASS; regression is 664/664 PASS with all 499 old test identities retained. These executed findings are current evidence, while terminal root reports record Research/Overall CONDITIONAL PASS and original closure1/3.

### Newly found falsifier: custom transaction hides an incorrect split commit

The [actual probe output](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/custom-split-observer-probe-command/stdout.log) records Run `f9089592-c528-4904-a72d-b6965eba99a4`: the incorrect split-ledger strategy using custom transaction plumbing received **24/24 PASS**. This falsifies the earlier assumption that wrapping only the existing `persistence.transaction` method gives adequate recovery discrimination. It is a discovered harness defect, not successful validation of that wrong strategy, and the original output remains evidence.

The implemented common Python SQLite observer `1.1.0` targets the real business-file device/inode and transactions with actual row writes, excluding auxiliary/read-only connections and only notifying committed after a successful SQLite commit. It observes supported common APIs independently of the original Persistence method. Require final fresh positive legal custom/staged and negative incorrect custom-split controls and disclose per-window coverage. Deliberate instrumentation replacement, opaque/native direct calls and documented unsupported boundaries remain limitations, not assumed coverage. In an otherwise-passing evaluation, missing mandatory committed or successful-response interruption produces **ERROR / RECOVERY_EVIDENCE_UNVERIFIED**, not business FAIL; autocommit without a precommit point can report PARTIAL coverage. Unknown/no-ack state may be absent, a coherent pending creation or a complete reservation, judged by direct invariants and retry. A reached `before_response` with `ok=True` requires complete reservation/ledger. No acceptance criterion forces one transaction count.

### Suite fairness correction before the final cohort

The new concurrent-release draft required release to succeed before cancellation, although the preserved API correctly raises `InvalidOrderState` for that request. [PREFINAL_VALIDATION_ABORT.json](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/PREFINAL_VALIDATION_ABORT.json) records stopped producers, completed/cleaned active evaluations and retained failures before amendment. Suite `1.2.0` exercises concurrent cancellation first, audits exactly-once release, then legally repeats cancellation/release. This corrects a new test's invalid call ordering; it does not weaken the original business API or discard its failures. Earlier suite results and the aborted prefinal cohort are not final frozen-version evidence.

### Executed multi-stage fairness controls

The [original recovery matrix](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-matrix-final/summary.json) retains result **FAIL**: thirteen common-API positive/negative controls matched expectations, but the naive two-phase sample was incorrectly expected to be a legal reference. Its actual Run `1e5ea0fb-641d-4c68-a43f-5b2fe43e75e8` is 16 PASS / 12 FAIL because failed capacity checks leave a newly created order behind. This is an API rollback defect, not a ban on multiple transactions. The [sample-correction receipt](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/RECOVERY_CONTROL_SAMPLE_CORRECTION.json) records reclassification and addition of a genuinely compensated sample without changing the hidden suite or original records.

The legal sample persists a provisional creation marker, then performs coherent reservation and removes the marker; on capacity rejection it compensates only that unfinished provisional creation. Explicit `reserve=False` created orders remain valid. [Run `38b3b658-67f4-433b-9e79-eb1ab87bba16`](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/compensated-full-suite-command/stdout.log) passed 28/28 with **36/36 consistent raw Oracle records** and COMPLETE actual before-commit/committed/before-response interruption coverage. The [new closure pair](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-closure/summary.json) independently records uncompensated Run `9d6026b8-ab32-4d5c-b5d6-d78d484a9208` FAIL 16/12 and compensated Run `ef7442ea-6992-49bc-8cb6-4ead81de4e8a` PASS 28/28, each with COMPLETE three-window observations. The wrapper's PASS means the expected negative and positive outcomes were both observed. Its old `strategy=reference` path label for the naive sample is qualified by `control_semantics=Known-bad`; it does not convert that failed sample into a legal fix.

### Current bounded safety and live admission

[Isolation-final](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/isolation-final/summary.json) reports mandatory private-file/network boundaries PASS and overall security CONDITIONAL. D's aggregate memory/pids cgroup is required; CPU/output sampling windows, Linux namespaces, supported observer APIs and local evidence mutability remain stated limits. [LIVE_GATE.json](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json), recorded at `2026-10-10T11:50:10.948314+00:00`, reports mandatory live admission PASS and security CONDITIONAL PASS, binding the frozen cohort, 499 retained identities, 664 developer passes, topology/cleanup proofs, model-connectivity preflight and a 42,423-regular-file secret-content scan whose receipt records that no secret value or digest was stored. It establishes admission to bounded blind trials, not their completion or a full hostile-code safety claim.

## 1. Inputs actually reviewed

- Original root [taskbook](../taskbooks/OrderFlow_M1_Task_System_and_Episode_D_Codex_Implementation.md) in full; Roadmap v1.0 including M1, M3 variant and M4 exposure boundaries; overall specification v1.0.
- Root maintainer guide, README, architecture, Episode A and Registry documents.
- Current manifest/Registry/suite protocol, A fixture, business service/persistence/payments/events, generic RPC worker/client, submission boundary and Codex/public-workspace entry points.
- Phase 2 actual alternative-strategy report and construction code; Phase 3.5 root report, corresponding original final report and recovery aggregate evidence.
- Actual observed baseline HEAD `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`, branch `phase3.5-hardening`. Existing untracked `.vscode/`, maintainer `AGENTS.md`, M1 task document and `benchmark_roadmap/` were observed and preserved.

This helper did not execute business tests, read secrets, edit existing source/history or start model challenges. The addendum reads actual new M1 artifacts produced by the main agent, distinguishing them from static review. The main agent owns predevelopment regression, source snapshots and all dynamic M1 acceptance. The documents are maintainer artifacts, not participant benchmark outputs.

## 2. Review matrix and falsifiers

| Concern | Design disposition | Concrete observation that would fail final acceptance |
|---|---|---|
| One business world | Orders/inventory/persistence are current; payments/events are contracts and B/C planned | Claiming a running payment/event system without real side-effect/recovery artifacts |
| Classification | Separate family/scenario/material variant/context/evidence/relation; parameters are robustness | Counting 2/4 workers as two independent research faults without another material difference |
| D independence from A | Cross-process coordination, durable shared state, supervisor, crash/retry semantics required | One threaded worker or A's old suite simply relabelled “D” |
| Fault reality | Keep schema protections; stale-state commits create cross-table contradiction | Fake stock values, forced business exception or removed constraints as sole failure cause |
| Topology proof | Trusted host identity plus namespace mapping, intervals, shared file identity | Candidate `pid=1` in every namespace treated as proof of distinct processes; paths-only shared-state claim |
| Scheduling fairness | Bounded IPC windows; a fix can omit hooks; correct lock/transaction path releases | Barrier requiring all processes enter while one holds an exclusive DB/file lock |
| Recovery semantics | Valid unknown-ack state, successful-ack completeness and durable retry identity; target/write-filtered common SQLite API observation with legal staged/incorrect split controls; exact window classification | Requiring a killed worker to answer, accepting orphan rows/duplicate ledger, forcing one transaction count, auxiliary commits impersonating business writes, or treating unavailable coverage as complete |
| Multiple legal fixes | Distinct DB transaction/atomic and shared-file-lock strategies; behavior-based Oracle | Suite enforcing an RLock-free function, exact SQL spelling or one author patch |
| Oracle independence | Stop workers, inspect raw DB against trusted fixture and response IDs; constraint probes | Candidate `audit()` defines truth or writes in one supervisor proxy impersonate workers |
| Actual worker use | Fixed valid ample-capacity operations per worker, plus scarce-stock tests | Reject-most-requests/disable-concurrency workaround PASS or chance-based unfair winners test |
| Labels versus outcomes | Private versioned applicability reference independent from engineering task result | Participant sees ABSTAIN/RLock-failure narrative or task PASS relabelled correct experience decision |
| Source provenance | A RLock result is maintainer seed; real A agent patches preserved separately | RLock presented as a strategy discovered by historical Codex |
| Framework continuity | Registry/transport extension; same lifecycle/fidelity and exact JUnit set | D-specific scoring in Runner, hidden suite edits by candidate, old Smoke/A behavior lost |
| Pilots | Three fresh blind native sessions and frozen cohort; all results, not guaranteed success | Reference substitution, maintainer repair counted as agent work, timeout replay counted as automatic success |
| Research scope | Disabled Experience; no governance or causal method claim | “Negative transfer prevented” or G0–G3 benefit claimed without exposure/control experiment |

## 3. Issues identified before coding

1. **Public metadata leakage:** baseline D `research_role` is `Negative Transfer Prevention`. Replace this with a neutral operational description in the new public version. All title/issue/tests/role input must avoid explaining lock scope or the private desired label. Public topology and business obligations remain explicit enough to investigate.
2. **Namespace PID ambiguity:** candidate-local PIDs are not necessarily globally unique. The supervisor must retain actual host process identity and worker assignment; add real DB inode/mount identity and operation overlap, not merely an array of self-reported PIDs.
3. **Crash result ambiguity:** a missing response does not determine whether commit occurred. Define both precommit and after-commit/lost-response checks. Preserve actual exits and reconcile through durable same-ID retries.
4. **Fairness trap:** stock-exhaustion competition cannot guarantee each process wins. Prove per-worker writes in a separate ample-capacity assigned phase.
5. **Historic state assertion migration:** initial baseline tests legitimately asserted D=PLANNED. Record exact current semantic transitions and preserve originals; do not weaken B/C or unrelated old checks.
6. **Security limitations:** sharing a data directory must not broaden private source or model access. Existing CPU/output sampling and aggregate-candidate limitations remain conditional until genuinely closed. New multiprocess cleanup/denial probes are mandatory.
7. **Old Roadmap baseline:** its Phase 3.5 “not completed” paragraph is a planning-time statement. Adopt the actual CONDITIONAL PASS record and retain the Roadmap unchanged.

These concerns are design decisions and required checks, not claims they have already been fixed.

Current implementation has neutralized public D research metadata and added actual topology/Oracle mechanisms. New exact strategy-transfer, complete 30-run cohort, effective regression, recovery controls and live admission supply separate frozen-version evidence. The blind Pilots, final aggregate gate and final history/evidence seal must still be reviewed independently; they are not inferred from implementation readiness or the completed offline checks.

## 4. Implementation-ready decisions

- Reuse the two trusted registries, existing Manifest and Runner lifecycle. Add a generic multi-worker supervisor/transport only where required; no new Agent Orchestrator.
- Keep the stock/order/ledger schema truth and public API; D faults are versioned fixture variants, not changes that make the correct base globally wrong.
- A bounded scheduling/control channel is permitted; it neither computes stock nor returns hidden expected results.
- Accept coherent DB transactions/conditional updates and safe shared-file locking as different possible coordination mechanisms. Require whole-business-operation and recovery correctness, not only one inventory UPDATE.
- Version private labels as maintainer references; link only actual strategy runs. Unknown-context VERIFY may remain explicitly design-level in M1.
- Record independent Engineering/Research/Pilot verdicts. A pilot task FAIL can be a valid measurement with working runtime/evaluator; missing core fault/Oracle evidence cannot receive PASS.

## 5. Dynamic obligations left to final review

No box below is a result at design time:

- [ ] New baseline/core regression, version/fingerprint and historical-byte protection manifest.
- [ ] Real 2/4-worker topology and shared DB, deterministic Buggy 10/10 business FAIL.
- [ ] Reference 10/10 PASS; mechanism-distinct alternative 10/10 PASS; recovery and retry checks.
- [ ] Lock-only A success/D failure and another realistic wrong/bypass strategy detected by Oracle.
- [ ] Complete valid current developer regression with explicit D-state assertion migration.
- [ ] Submission fidelity, reset/report, exact JUnit/test identity, process/FD cleanup and new boundary probes.
- [ ] Public/private package leakage review and private-label provenance binding.
- [ ] Three new bounded Gateway native-agent blind pilots with source/input freeze, raw child evidence, real submissions and independent evaluator results.
- [ ] Final command/result/claim matrix, all failures, source hashes and local sealing limits.

The main agent's final [design review](M1_TASK_SYSTEM_DESIGN_REVIEW.md) may reference this preimplementation review and add actual evidence. It must preserve the distinction between this static readiness decision and dynamic admission.

## 6. Mature implementation sources checked

The design reuses established primitives rather than inventing a lock/database/test/orchestration framework. SQLite supports isolated connections across processes and one writer; `BEGIN IMMEDIATE` acquires a write transaction before reading, with contention handled explicitly. These properties inform the legal reference choices but do not alone prove candidate correctness. [SQLite isolation](https://www.sqlite.org/isolation.html), [SQLite transaction control](https://www.sqlite.org/lang_transaction.html)

Python's Unix `fcntl.flock` is a supported shared-file coordination API; all writers still need compatible scope and FD lifecycle. [Python 3.12 fcntl](https://docs.python.org/3.12/library/fcntl.html)

SWE-bench's existing harness and bubblewrap's caller-owned namespace primitives inform artifact/evaluation separation and sandbox reuse. They do not constitute evidence that this project's particular policy or task has passed. [SWE-bench harness](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/harness.md), [bubblewrap source](https://github.com/containers/bubblewrap)

## Final M1 execution addendum — 2026-10-10

Final evidence: [engineering](M1_EPISODE_D_VALIDATION_REPORT.md), [design review](M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](M1_PILOT_REPORT.md), [matrix](M1_EVIDENCE_MATRIX.md), [limits](M1_REMAINING_ISSUES.md). Design PASS; D Engineering PASS within declared tested scope; Research/Overall CONDITIONAL PASS. OriginalPilot TIMEOUT/PASS/TIMEOUT, closure1/3; two separate unchanged-Agent offline28PASS results do not upgrade original trials. This update does not rewrite archived preimplementation/history or assert arbitrary hostile safety. Stop atM1; B/C planned, Experience disabled.
