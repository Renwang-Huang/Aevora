# OrderFlow Task System Design — M1

**Contract version:** `1.2.0` · **Initial design baseline:** 2026-10-10, commit `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf` observed before M1 source changes. **Current-state addendum:** Episode D is implemented; final M1 admission is CONDITIONAL PASS; see the terminal root reports.

This is a **maintainer document**. Do not copy it, the repository's root `AGENTS.md`, or its private strategy analysis into a Participant workspace. It defines the task system and records implementation-time status separately from the design accepted before coding. The original four-document design and gate are preserved in the M1 archive's `design_preimplementation/` and `DESIGN_GATE.json`. Current M1 outcomes belong in the new validation reports and original artifacts; [m1_validation/CURRENT](../m1_validation/CURRENT) identifies the active independent archive.

## 1. Status and authority

Use these labels consistently:

| Label | Meaning |
|---|---|
| `CURRENT / IMPLEMENTED` | Existing code or an executed artifact supports the named capability; cite its version and scope |
| `PLANNED` | A requirement or interface design; no claim that it executes |
| `REFERENCE-ONLY` | Maintainer analysis, controlled strategy sample, or private applicability reference; not a running experience service |
| `UNVERIFIED` | Necessary evidence is absent or has not been checked; never silently convert to PASS |

At the **initial preimplementation baseline**, Smoke and A, Manual/Codex adapters, the trusted Oracle and submission fidelity were `CURRENT / IMPLEMENTED`; D was `PLANNED` and authorized for M1 implementation. That archived state is not the current D registration. B/C remain `PLANNED`. Payment and event classes are interface contracts, not operational services. Experience remains `DISABLED`.

**Current implementation state:** D is now `CURRENT / IMPLEMENTED`, scenario `2.0.0`, variant `v01`, fixture `1.0.0`, suite `1.2.0`, Evaluator `3.1.0`, execution strategy `shared-db-workers`; its current private identity set has **28 cases**. The generic supervisor, 2/4 independently sandboxed workers, stable-flock alternative and direct D Oracle exist. The frozen-version 30-run cohort records Buggy 10/10 FAIL, Reference 10/10 PASS and flock 10/10 PASS; full current developer regression is 664/664 PASS with all 499 baseline identities retained. Exact strategy transfer was remeasured at this version with identical evaluated trees: maintainer local-lock A PASS/D FAIL and historical natural DB repair A/D PASS. The linked artifacts and qualifications are in [Task Relations](TASK_RELATIONS.md) and [the current design review](history/orderflow/M1_DESIGN_REVIEW.md). Under suite `1.0.0`, an incorrect custom-transaction split-ledger strategy passed 24/24 when internal-Persistence observation missed its commit boundaries. The current common Python SQLite observer `1.1.0` adds supported API/business-file/write-context observation, with fresh positive/negative recovery controls. Legal compensated multi-stage creation passes 28/28; a naive uncompensated staged sample fails real API rollback obligations. The mandatory pre-Pilot live gate is PASS, with overall security explicitly CONDITIONAL PASS. Three Pilot results are complete; Research/Overall CONDITIONAL PASS, original closure1/3 in the terminal reports.

The Phase 3.5 result is **CONDITIONAL PASS**, not an unconditional security claim. Its final 499 developer tests and 2/3 automatic recovery challenges are historical evidence at their frozen versions. The Roadmap v1.0 statement that Phase 3.5 has no completion report is an older planning snapshot, superseded for baseline facts by [the actual report](history/phase1-3/PHASE3_5_VALIDATION_REPORT.md). Historical documents and results remain unchanged.

M1 implements task design, D, private reference labels, engineering validation and three blind native-agent pilots. It does not implement B/C, an experience exposure controller, GraphSwarm, FalkorDB, MCP, decision/feedback algorithms or formal G0–G3 experiments.

## 2. One business world

The business world is one OrderFlow API and persistent state, rather than four unrelated toy applications.

| Responsibility | Actual baseline | Family and future boundary |
|---|---|---|
| Orders | `app/service.py` and `orders.py`: create/query/cancel; created/reserved/cancelled state | Shared by A/D; B/C must later define paid and compensation state semantics |
| Inventory | `inventory.py`: reserve/release, per-order ledger; repeated cancellation does not release twice | A investigates within-process concurrency; D changes the coordination and recovery context |
| Persistence | Independent SQLite connections, bounded busy timeout, `BEGIN IMMEDIATE`, CHECK/FK/unique constraints | Shared state authority for A/D; D adds independent processes, not a new database engine |
| Payments | `PaymentIntent`, `PaymentResult`, `PaymentService` protocol only | B is `PLANNED`: an independent durable simulated-charge ledger, idempotency key and crash ambiguity; no real money |
| Events | `BusinessEvent`, delivery result and `EventWorker` protocol only | C is `PLANNED`: durable delivery, duplicate/out-of-order control, recovery and compensation |
| Worker topology | A's RPC worker executes a real thread pool; D now has a trusted supervisor and independent sandboxed OS workers sharing one file | D recovery and final admission must still satisfy the new gates |

The currently implemented stock equation, for each trusted fixture SKU, is:

```text
initial_stock = available + reserved + committed
reserved = sum(quantity of orders with an active reservation)
current stock fields = initial fields + sum(persisted ledger deltas)
```

All terms must be nonnegative and match actual order/ledger identities. `committed` exists but confirmation/consumption is not operational in the baseline. M1 must not invent paid, replenished or event-derived stock to describe D. Future B/C changes must extend the explicit business model and Oracle together; replenishment requires a real durable record before entering the equation.

An acknowledged successful creation/reservation or cancellation/release must have coherent durable side effects; correctness does not prescribe one transaction count. Before an acknowledgement, interruption may leave no order, a valid pending `created/none` order, or a complete `reserved/active` order, provided the Oracle's invariants hold and identical retry finishes with exactly one consistent reservation. The same order ID and identical payload have one durable business identity; conflicting payloads are explicit business errors. Insufficient capacity must leave no partial order or ledger under the established API semantics. Cancellation/release remain idempotent after restart. A real legal multi-stage sample persists a provisional-creation marker and compensates only an unfinished creation on capacity rejection; it passed the full suite and all three observed interruption windows. This positive control establishes that coherent staging is accepted, while an uncompensated partial creation is correctly rejected. These are maintainer validation artifacts, not additional deployed business services.

## 3. Classification model

These are logical design concepts. M1 should map them to the existing manifest, Registry and evidence instead of introducing an unnecessary plugin framework or pretending every concept is a runtime class.

| Concept | Definition | Example and distinction |
|---|---|---|
| `TaskFamily` | The principal engineering responsibility and failure domain | A Inventory, B Payment, C Event, D Distributed coordination; Smoke is a framework diagnostic, outside the four families |
| `Scenario` | A concrete, versioned public incident and matching private evaluation context | Episode `D`, issue version, fixture, topology and independently registered suite |
| `TaskVariant` | A material change in failure mechanism, deployment assumptions or observable evidence | Cross-process stale state versus durable recovery omission; changing 2 to 4 workers alone is a robustness parameter |
| `FaultMechanism` | A causal defect on an actual code path | Read before the protected persistent operation, then write stale absolute values; state loss on crash is a different mechanism |
| `ExecutionContext` | Runtime assumptions that determine semantics and strategy scope | Process/thread count, shared database identity, journal mode, connections, retry and crash/restart policy |
| `EvidenceCondition` | Which true symptoms, topology facts and uncertainties the participant can observe | Expanded workers and ledger disagreement are observable; exact defect location is not disclosed; an unknown-topology case is a future evidence variant |
| `ExperienceRelation` | A conditional statement linking a specific verified historical strategy to a target context | A process-local RLock can protect a shared in-process object; that evidence alone is insufficient for independent workers |

Stock size, SKU count, quantity, worker count and seed are recorded parameters of a scenario. They do not become independent research tasks merely because a test is parameterized. A new variant needs a stated causal/evidence difference and its own package and gate review. Do not derive relationships solely from matching words such as “concurrency”.

Each relation must identify the exact strategy artifact, source origin and assumptions. A successful task outcome does not identify the reasoning that produced it. Relationships are private maintainer references until a separately authorized experiment defines controlled history exposure.

## 4. Two independent truths

### Engineering Truth — `CURRENT / IMPLEMENTED` base and D extension

The trusted evaluator owns stock fixtures, expected business semantics and test identities. After candidate workers stop, it reads the actual SQLite state and audits orders, inventory, ledger, constraints and response-to-commit correspondence. Candidate `audit()` and agent claims are auxiliary observations, never the final truth.

D adds topology and recovery facts: distinct trusted host process identities, overlapping operations, one shared DB identity, actual writes assigned to multiple workers, abnormal exits, restarts, durable retry outcomes and absence of partial side effects. These are implemented measurement responsibilities, with final coverage separately admitted. The Oracle must accept equivalent legal strategies. SQLite serializes writers across connections and processes; application requests may overlap while correct commits serialize. That is valid concurrent service operation, not evidence that concurrency was disabled. [SQLite isolation](https://www.sqlite.org/isolation.html)

### Decision Reference — `REFERENCE-ONLY`

The versioned private applicability labels state whether a **specified strategy** is supported under specified environmental and information assumptions. Record APPLY/VERIFY/ABSTAIN with evidence, scope, label version, reviewer identity and `natural / maintainer_seed / synthetic` origin. A label is not an Experience Adapter implementation.

An APPLY reference does not prescribe the only legal fix. ABSTAIN from one historical strategy can coexist with a correct alternative solution. VERIFY means the available context does not establish the premise; it is not a code-task failure. Do not infer a participant's decision quality from its final PASS/FAIL or parse prose into fabricated decision events. Without controlled exposure and observable decisions, M1 reports **strategy applicability reference only**, not actual inheritance, negative-transfer rate or governance benefit.

## 5. Episode package contract

Package items are logical responsibilities; keep the existing directory layout.

| Item | Existing or proposed location | Visibility and admission requirement |
|---|---|---|
| Public manifest, issue, API/SLA constraints | `benchmark/scenarios/<ID>/public.json`, allowlisted public issue | Participant; neutral symptoms, accurate topology, no root cause, private labels or suite paths |
| Public source and tests | Registry factory output, `tests/public/` | Current episode only; enough to investigate and reproduce ordinary behavior |
| Fixture, fault variant, reset recipe | `benchmark/episodes/`, Registry | Trusted host; real fault, exact fixture version, independent initial state |
| Private manifest and exact test identity set | `evaluator/private_manifests/` and `suites.py` | Trusted host; complete JUnit identity checks, suite version and timeout |
| Hidden tests and direct database Oracle | `evaluator/hidden_tests/`, `oracle.py` and D extension | Trusted host; no candidate imports, direct state and external observations |
| Buggy, reference, legal alternatives, wrong mutants | Fixture and `evaluator/reference_patches/` plus maintainer samples | Private analysis; mechanisms and actual result matrices, not only patch existence |
| Applicability labels | `evaluator/private_labels/episode_d_applicability.json` | `REFERENCE-ONLY`; predeclared assumptions and evidence, no participant exposure |
| Repeatability and quality reports | New M1 archive and reports | Trusted host; all attempts, real IDs/exits, failures, mutation discrimination and limits |
| Run artifacts and fingerprints | Existing Runner reports plus topology/recovery evidence | Trusted host; baseline/patch/expected/applied tree hashes, fixture/suite/oracle/environment versions |

Admission is not defined by “has 14 tests”. Necessary identities, semantics and supported contexts are scenario-specific. Hash the actual manifest, fixture sources, suite, Oracle and execution strategy used; record model/provider/effort, public input digest, budget and fresh session for agent trials. Existing public manifest has a strict field contract; optional design concepts should use validated metadata or a deliberately versioned extension, not unvalidated schema drift.

Reset must stop all workers and writers, close pipes/FDs, remove only run-owned temporary data, initialize a new trusted database and publish it safely. Preserve submissions, logs and Oracle evidence. A fresh run gets a new UUID and never reuses previous test results. A source/suite change requires new fingerprints and a new frozen cohort, not an edit to an earlier result.

## 6. D design accepted before coding and current implementation

**Private design, originally `PLANNED`, now implemented:** Multiple independent workers each have their own local synchronization object and SQLite connection lifecycle. A faulty read/modify/write path can appear sound within one process, yet independent workers take stale snapshots and later commit inconsistent cross-table state. Schema constraints remain; the defect is not manufactured by dropping all protections.

D differs from A in the trusted execution topology, scope of coordination, shared durable state, process death, response ambiguity and restart requirements. It must independently demonstrate these differences. A's thread pool cannot be relabelled a process benchmark.

The trusted supervisor starts at least 2 and 4 separately sandboxed workers with the same controlled data-directory mount. It never imports candidate modules. It dispatches real operations to each worker and records worker ID, trusted host PID/start identity, relevant namespace PID mapping, timings and shared file `st_dev/st_ino`. Namespace-local `os.getpid()` values may be equal in different PID namespaces, so those values alone do not prove independent processes. Path strings alone do not prove a shared database.

Use a bounded IPC schedule gate to expose an actual read/write window. The control channel carries scheduling facts, not an expected stock result or Oracle assertion. Correct transactions or cross-process locks must be able to complete when fewer workers reach the hook; a bounded release prevents an artificial lock/barrier deadlock. A fix may remove a faulty checkpoint. Correctness cannot depend on preserving a defect-specific function.

Recovery tests distinguish:

1. **Before commit:** a killed in-flight transaction rolls back; an earlier coherent pending creation may remain. Later requests and same-ID retry complete without corrupt rows or ledger.
2. **After commit, response unavailable:** persisted state survives, whether a coherent pending creation or a complete reservation; retry completes or discovers the result without duplicating reservation or release.
3. **Restart:** a new process opens the same database; subsequent real writes and cancellations remain consistent.

**Recovery observation correction:** Wrapping only `persistence.transaction` is not sufficient to establish these windows. The current common Python SQLite observer verifies the main database against the real business-file device/inode, tracks real row-write transactions, excludes read-only/auxiliary connections and emits committed notification only after SQLite successfully commits. It supports common connection/cursor commit APIs without requiring the original Persistence method. A legal custom or coherent staged transaction remains valid; an incorrect stock/order-then-ledger split must be interrupted and rejected by direct state audit. Positive legal-custom-transaction and negative custom-split-ledger tests and final coverage are required. Deliberate instrumentation replacement, opaque/native direct SQLite paths and documented unsupported boundaries remain separate limitations, not assumed coverage. In an otherwise-passing evaluation, missing mandatory `transaction_committed` or successful `before_response` interruption yields Evaluator **ERROR / RECOVERY_EVIDENCE_UNVERIFIED**, not business FAIL. A valid autocommit path with no precommit observer may have `recovery_coverage=PARTIAL`; this cannot be described as complete precommit proof. At a verified `before_response` with `ok=True`, full reserved state/ledger must already exist.

Do not count an intentionally killed request as a successful response, require an impossible immediate answer from a dead worker, or hide SQL/environment errors as stock exhaustion. Separate business assertion FAIL, infrastructure ERROR, enforced TIMEOUT and expected crash/recovery observations.

To exclude “only one worker works” without relying on lottery fairness when stock is scarce, use a separate ample-capacity phase with fixed valid work assigned to every worker. Audit each returned order ID and its durable entry. Scarce-stock phases evaluate conservation and explicit responses, not a requirement that every worker wins.

Validate a DB-atomic/transactional reference and a genuinely different legal strategy, such as a shared-inode advisory file lock covering the complete read/modify/write operation. A file-lock strategy requires all relevant writers to coordinate, bounded acquisition and safe FD/restart behavior; no unlink-and-recreate of the shared lock while workers remain active. A Python `fcntl.flock` is an existing Unix API, not a new distributed lock service. [Python fcntl documentation](https://docs.python.org/3.12/library/fcntl.html)

Wrong strategies include lock-only per process and at least one distinct error such as separated capacity check and update or duplicate side effects on recovered retries. Also check reject-most-requests, single-worker gating and hardcoded inventory responses. A mutant is “detected” only when a real business obligation fails; syntax/startup failures do not establish discrimination against its intended strategy.

## 7. Engineering and research gates

[TASK_ADMISSION_GATES.md](TASK_ADMISSION_GATES.md) contains the reusable evidence checklist. Engineering admission requires fault reality, legal multi-solution correctness, Oracle independence, repeatability, lifecycle/fidelity, recovery, regression and isolation. Research admission additionally requires nonleaking public material, grounded relationships, predeclared reference labels, difficulty calibration and honest limits on claims.

For M1, a task can be engineering-correct while its pilot outcome is FAIL or TIMEOUT. A valid pilot task FAIL is not automatically a broken adapter. Conversely a successful runtime with an invalid submission or missing Oracle cannot establish engineering correctness. Publish separate gate conclusions, and retain all failed attempts.

## 8. Difficulty calibration and future interfaces

| Dimension | What to observe | What cannot be concluded from test count |
|---|---|---|
| Software difficulty | Extent of code changes, concurrency, retry/recovery obligations, regressions | More lines or more cases are not necessarily harder |
| Diagnostic difficulty | Root-cause investigation, usable symptoms, reproduction and tool time | An opaque issue is not a high-quality difficult task |
| Experience-judgment difficulty | Context assumptions, conflicting evidence and strategy scope | A task PASS does not prove correct historical judgment |

Freeze public input, source, evaluator, model/effort and budgets before three independent blind native-agent pilots. Each needs a new Run and session and at least two independently executed native children with verified completion/receipt evidence. Record runtime, submission fidelity, automatic integration, engineering outcome, wall time and actual available usage separately. Preserve API errors, timeouts, invalid/no patches and incomplete trace; do not remove them from the denominator or count postmortem replay as original success.

Three pilots are a solvability and ceiling/floor signal, not statistical evidence of a method advantage. If all easily pass, document potential ceiling effects; if all fail, inspect issue adequacy, solvability and budget. Do not alter the frozen suite mid-cohort merely to obtain a preferred result. No stable easy/medium/hard label is assigned without evidence across contexts and budgets.

M3 variant expansion, M4 controlled exposure/checkpoints and M5 G0–G3 analysis are `PLANNED`. Existing four Experience methods remain disabled. Stable run/submission/outcome references can later connect exposure and decision records, but M1 does not implement their controller or governance algorithms.

## 9. Reuse and security limits

Reuse SQLite transactions and standard Unix locking, pytest/JUnit, Git, bubblewrap and Codex-native scheduling. SWE-bench separates patch evaluation and execution evidence; bubblewrap provides namespace primitives whose actual policy is owned by its caller. These inform the package and boundary contracts rather than introducing a second orchestrator. [SWE-bench harness](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/harness.md), [bubblewrap](https://github.com/containers/bubblewrap)

Multi-worker sharing must expose only the run-owned database/control data, never hidden tests, reference/alternative patches, private manifests/labels, maintainer source, other runs, home credentials or model channel. Recheck Outer Participant, Native Command and Candidate layers after any sandbox change. The project key stays solely on the trusted host; use synthetic targets for probes.

The new [isolation result](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/isolation-final/summary.json) records mandatory private-file/network boundaries PASS with overall security CONDITIONAL. D pools require an aggregate memory/pids cgroup in addition to per-worker controls; this does not retroactively establish aggregate enforcement for every ordinary candidate topology. Phase 3.5 CPU/output sampling windows, the Linux-namespace rather than VM threat model, supported SQLite observer boundaries and lack of third-party immutable attestation remain limits. The [live admission gate](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json) verifies bounded model connectivity and secret-content scan prerequisites; it is not a completed Pilot or a claim of arbitrary hostile-code safety.

See [TASK_RELATIONS.md](TASK_RELATIONS.md) for exact historical strategy sources and [M1_DESIGN_REVIEW.md](history/orderflow/M1_DESIGN_REVIEW.md) for preimplementation self-review and remaining execution obligations.

## Final M1 execution addendum — 2026-10-10

Final evidence: [engineering](history/orderflow/M1_EPISODE_D_VALIDATION_REPORT.md), [design review](history/orderflow/M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](history/orderflow/M1_PILOT_REPORT.md), [matrix](history/orderflow/M1_EVIDENCE_MATRIX.md), [limits](history/orderflow/M1_REMAINING_ISSUES.md). Design PASS; D Engineering PASS within declared tested scope; Research/Overall CONDITIONAL PASS. OriginalPilot TIMEOUT/PASS/TIMEOUT, closure1/3; two separate unchanged-Agent offline28PASS results do not upgrade original trials. This update does not rewrite archived preimplementation/history or assert arbitrary hostile safety. Stop atM1; B/C planned, Experience disabled.
