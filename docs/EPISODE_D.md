# Episode D — shared-worker inventory incident

**Maintainer document; not Participant material.** Publish only [the separate public Issue](../benchmark/scenarios/D/ISSUE.md), current public manifest, allowlisted business source and public tests to the candidate. This document explains private fault mechanisms, recovery windows and evaluation strategy; it must never be copied into the blind workspace or model prompt.

**Documentation state:** Episode D is `CURRENT / IMPLEMENTED`; M1 terminal admission is CONDITIONAL PASS. The corrected Suite `1.2.0` 30-run cohort, full effective regression, recovery fairness controls and mandatory live admission have now executed; their specific outcomes are linked below. Three Pilot outcomes and final Research/Overall verdicts are in the root reports: original closure1/3, Research/Overall CONDITIONAL PASS. A manifest's `IMPLEMENTED` flag means a registered code package exists; it is not a task quality or validation PASS. [m1_validation/CURRENT](../m1_validation/CURRENT) identifies the active independent archive.

## 1. Package and business contract

| Item | Current implementation/configuration |
|---|---|
| Episode / scenario version | `D / 2.0.0` |
| CLI variant | `v01` |
| Fixture / suite version | `1.0.0 / 1.2.0` |
| Evaluator / SQLite observer version | `3.1.0 / 1.1.0` |
| Execution strategy | `shared-db-workers` |
| Topologies | 2 and 4 independent OS worker processes |
| Persistence | One actual file-backed SQLite database and shared run-owned data directory |
| Public initial fixture | `SKU-1: 50`, `SKU-2: 9`; private cases use additional sizes/quantities |
| Current required suite | 28 exact test identities in the private manifest; number is not a quality score |
| Full hidden evaluation timeout | 120 seconds; an override may only reduce it |
| Experience | `DISABLED`; applicability labels are private review references |

Public task text describes expansion, inconsistent orders/inventory/reservations, retries and worker interruption. It discloses independent workers sharing SQLite and requires normal API/capacity, persistence, identical retry idempotency, conflicting-ID errors, cancellation and rollback-journal/WAL support. It does not disclose the private synchronization diagnosis or a preferred repair.

Stock is `initial_stock = available + reserved + committed`, all nonnegative. Active order quantities and persisted ledger deltas must independently reconcile with those fields. The existing business model has no operational payment/consumption service, so D does not introduce paid orders, external charges or invented event effects. B/C remain PLANNED.

Supported public methods remain `create_order`, `reserve_inventory`, `cancel_order`, `release_inventory`, `get_order`, `get_inventory` and initialization/query behavior. A successful create/reserve has exactly one durable order and reserve entry. Identical same-ID retries do not reserve again; conflicting payloads are explicit business errors. Insufficient capacity rolls back the operation. Repeated cancellation/release cannot release twice, including after restart.

Preserve the existing release precondition: calling `release_inventory()` before cancellation raises `InvalidOrderState`. The concurrent release tests must use legal cancellation-before-release ordering rather than force an API change. The discarded prefinal test-order mistake is recorded in the maintainer design review and new evidence, with original failing runs retained.

## 2. Real fault and its scope

`benchmark/episodes/episode_d.py` constructs the versioned defect from the existing application baseline. It retains the original schema, CHECK/FK/unique constraints and transaction implementation. The factory is private; only the resulting app tree is public.

The Buggy path first reads a stock snapshot outside the write transaction. Inside a later transaction it accepts an order using that snapshot, writes absolute stock values calculated from the old read, and records the order/reserve entry. A local `threading.RLock` wraps all writer APIs—initialization, creation, reserve, cancel and release—inside each service process. This makes the earlier read and later write mutually exclusive among cooperating calls **in the same process**.

Independent workers load separate lock objects. They can each read the same stock before either writes. SQLite serializes subsequent write transactions, but the later transaction still writes its precomputed absolute values, erasing an earlier worker's stock change while both order/ledger records remain. Row-level conservation and per-order uniqueness can still hold; cross-table sums and accepted capacity do not. The failure is caused by actual reads and commits, not an injected wrong number or fake exception. SQLite's normal cross-process isolation and single-writer behavior do not repair application state calculated before that transaction. [SQLite isolation](https://www.sqlite.org/isolation.html)

### Why D is a separate engineering task from A

A's executing topology is one RPC process with concurrent threads and one object. D supplies genuinely separate process identities, independently opened connections and one shared persistent authority. It additionally requires interruption, same-ID retry, lost-response reconciliation and restarted processes. The local-lock strategy's tested A scope is a valid historical boundary; it is not a globally wrong primitive.

D still uses a related stale-state business defect, but its scope failure, supervisor, independent process evidence, persistence and recovery obligations are independently executed. Merely changing a thread-count label would not meet D's admission gate.

## 3. Strategy artifacts and discrimination

| Maintainer sample | Mechanism | Expected behavior to verify, not a prefilled result |
|---|---|---|
| `buggy` | Local writer RLock plus transaction-external snapshot/absolute update | Ordinary single-worker operations work; independent-worker competition violates stock/order/ledger relations |
| `reference` | Original coherent write transaction and conditional relative inventory UPDATE | Capacity decision and order/ledger effects commit together; legal under shared DB and recovery |
| `flock` | Keep snapshot path, protect the complete writer operation with one stable shared-inode advisory lock | Different legal coordination mechanism; all relevant writer APIs use matching scope |
| `local-lock-only` | Exactly the same actual app artifact as Buggy | Deliberate named wrong-strategy sample; evaluated as a workspace, never as a fabricated empty repair patch |
| `split-ledger` | Stock/order commit in one transaction, reserve ledger recorded in a second | Ordinary path can appear correct; killing after the first commit exposes a durable order/reservation without its ledger |
| Additional recovery positive control: `compensated-phase` | Durable provisional creation plus coherent reservation and capacity-rejection compensation | Legal multi-stage business operation; accepted by the same Oracle and interruption tests |
| Additional recovery negative control: naive `two-phase` | Creation commits before reserve, with no compensation on inventory rejection | Leaves unwanted newly created orders after failure; rejected for real API rollback violations |

Reference and alternative have real generated diffs against D's defect baseline. The file-lock sample opens a stable `.write.lock` next to the shared database per operation, closes the FD afterward and does not unlink/recreate that lock while writers are active. Its local lock also coordinates same-process use. All relevant APIs must share the file-lock scope, because an unlocked cancellation can otherwise race a stale creation snapshot. `fcntl.flock` is an existing Unix API; correctness still depends on full operation scope and compatible writers. [Python fcntl](https://docs.python.org/3.12/library/fcntl.html)

The wrong split-ledger strategy uses ordinary transactions and side effects. The test does not invent missing ledger state: an actual supervisor kill between commits leaves the persisted first transaction visible. Restart and retry expose whether business accounting remains complete.

The evaluator accepts equivalent legal strategies. It does not require use/removal of RLock, the exact reference SQL, a particular internal method or preservation of a defect hook. Known-bad detection is only established by a real business violation, not a syntax error, inability to start or harness timeout. Additional bypass checks must catch rejecting valid traffic, enabling only one worker, returning hardcoded results and suppressing persistence; successful execution alone is not evidence of correct task discrimination.

## 4. Trusted execution topology

`evaluator/supervisor.py` owns a pool of 2 or 4 `BusinessRPC` clients. Each starts a separate bubblewrap candidate with the same app snapshot and run-owned data mount. Host dispatch threads send independent operations; the candidate code actually runs in separate OS processes. This supervisor coordinates business execution and recovery, not Agent planning or subagent delegation.

The private `evaluator/control.py` server communicates through a dedicated mounted Unix control socket. Kernel `SO_PEERCRED`, launch ancestry and process-start identity establish the executing peer. Archive host PID, worker index/generation, namespace identity, launch relationship and host-monotonic operation intervals. Candidate-local PIDs may be equal in independent namespaces and are not sufficient identity evidence.

Record the shared database's device/inode, and when available actual `/proc/<host_pid>/fd` matches at a paused transaction. Same path strings alone do not establish one shared file. Each Worker must make real durable writes; a separate ample-stock, fixed-assignment phase proves this without requiring every Worker to win a scarce-stock race. Later stock exhaustion is judged by full responses and invariants.

The pool uses the existing candidate resource controls and an aggregate pool cgroup for memory/pids when required. Individual watchdogs and cleanup remain active. Failure to establish required security controls must fail closed. Multiple workers do not receive the Participant model token/socket or network channel, private tests, labels, reference patches, maintainer source or other runs.

### Bounded competition window

A generic `inventory_read` notification marks the actual old-read window. The trusted controller releases the first wave when its parties arrive or after a bounded 0.3-second wait, then releases permanently. No expected inventory value, success count or hidden assertion is sent over that control channel.

A legal transaction or global lock can serialize access such that only one operation reaches the checkpoint; bounded release allows it to proceed. A repair can remove that call and still be evaluated by ordinary concurrent requests and independent state. A controller cannot demand that all workers enter a region while the first holds an exclusive lock.

## 5. Crash, response loss and recovery

The initial generic Worker wrapped only the existing Persistence context-manager; that is now known to be insufficient. The current `SQLiteObserver` in the generic Worker targets supported common Python SQLite APIs. It verifies each main connection against the actual business-file device/inode, tracks real row-write transactions, excludes auxiliary/read-only connections and emits `transaction_committed` only after SQLite actually commits successfully. It supports connection/cursor SQL commit, `connection.commit`, compatible subclass factories, context exit and documented completed autocommit statements. It does not mistake failed COMMIT, a pending RETURNING cursor or trigger activity for a completed transaction; unsupported paths are reported.

A generic `before_response` observation occurs before writing the RPC response. The supervisor arms a stop point, starts a real call, waits within a finite deadline, kills the reached worker and records actual exit/control state. It then starts a new process against the same database and performs real retries/subsequent operations. Fresh frozen-version recovery controls described below now exercise these paths; coverage remains explicit for each strategy and each actual reached window.

| Window | Required semantic check |
|---|---|
| `before_commit` | In-flight transaction rolls back; earlier coherent pending creation may remain. State is audited and same-ID retry completes once |
| `transaction_committed` | A real business row-write commit survives process exit; no-ack state may be coherent pending creation or complete reservation; retry has no duplicate accounting |
| `before_response` | Protocol-level response loss; at `ok=True`, a complete successful reservation/ledger must already be durable before retry |

**Observed earlier recovery blind spot:** [Run `f9089592-c528-4904-a72d-b6965eba99a4`](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/custom-split-observer-probe-command/stdout.log) used an incorrect split-ledger strategy with custom transaction plumbing and received **24/24 PASS under suite `1.0.0`** and the internal-Persistence observer. It escaped the actual interruption window; passing all case identities did not establish correct recovery. Preserve this failure of harness discrimination and do not count the wrong implementation as a legal alternative.

The current observer implements supported common Python SQLite boundaries rather than requiring one candidate `persistence.transaction` implementation. A correct custom or coherent staged transaction remains legal and must pass positive controls; an incorrect custom split-ledger must reach a real between-commit interruption and fail direct Oracle. An interrupted unacknowledged call may leave no order, `created/none`, or complete `reserved/active`, provided direct invariants hold and same-ID retry produces exactly one complete reservation. This is behavior-based acceptance, not a one-transaction requirement.

### Executed fairness evidence for multiple transactions

The [common-API recovery matrix](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-matrix-final/summary.json) retains original overall FAIL: thirteen commit/SQL/cursor/context/read-first/cache-first/auxiliary-metrics positive or wrong-split controls behaved as expected, but a naive two-phase sample incorrectly classified as a reference failed 16 PASS / 12 FAIL. It leaves a newly committed created order when reservation returns insufficient inventory. That violates preserved rollback semantics; coherent pending state after an interrupted unknown outcome does not permit leaking an unwanted new order after a completed failure.

The corrected legal `compensated-phase` control persists a provisional-creation marker and removes only its own unfinished newly created order on capacity rejection, without deleting legitimate `reserve=False` created orders. Reservation state and its ledger remain coherent. [Full-suite Run `38b3b658-67f4-433b-9e79-eb1ab87bba16`](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/compensated-full-suite-command/stdout.log) is **28/28 PASS, 36/36 raw Oracle records consistent**, with all three actual interruption points COMPLETE. The [new closure pair](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-closure/summary.json) independently records naive Run `9d6026b8-ab32-4d5c-b5d6-d78d484a9208` FAIL 16/12 and compensated Run `ef7442ea-6992-49bc-8cb6-4ead81de4e8a` PASS 28/28. Both retain three-window observations. The [correction receipt](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/RECOVERY_CONTROL_SAMPLE_CORRECTION.json) preserves sample provenance and the earlier failed matrix; it does not change the hidden criteria. This comparison directly tests multi-stage fairness and rejects the assertion that only single-transaction strategies can pass.

Observer API coverage and reached windows are archived per strategy. In an otherwise-passing evaluation, missing mandatory `transaction_committed` or successful `before_response` interruption produces **ERROR / RECOVERY_EVIDENCE_UNVERIFIED**, not business FAIL. A legal autocommit scheme can lack a precommit observation and have PARTIAL recovery coverage; it is not declared complete. Deliberate instrumentation replacement, direct `_sqlite3`/native entrypoints, opaque factories, unsupported scripts/savepoints and documented boundary gaps remain explicit limitations. A response boundary cannot be relabelled as proof of precommit interruption.

Missing responses have unknown commit outcome until durable state and retry are checked. Do not treat an intentionally killed call as a successful response, confuse enforced death with a business error or turn SQLite busy/transport errors into stock exhaustion. A split-ledger first commit can satisfy normal response counts while leaving a real recovery error; the Oracle checks actual state.

After all workers stop, the trusted D recovery helper may open the existing database in SQLite `mode=rw` to let SQLite perform its own journal recovery. It does not create a missing DB, discard sidecars, modify business rows or run candidate code. It records storage fingerprints before/after, verifies identity and `integrity_check`; the subsequent business Oracle reads recovered raw state. This explicit recovery action must be distinguished from a strictly read-only inspection. SQLite's transaction and error semantics are the established recovery mechanism. [SQLite transaction control](https://www.sqlite.org/lang_transaction.html)

## 6. Independent Oracle and hidden coverage

`evaluator/episode_d_oracle.py` composes the existing trusted schema/constraint Oracle with D response checks and per-worker write witnesses. The host does not import candidate code. Audits run only after workers and writers stop, use trusted fixture quantities, and reject unsafe database/sidecar files or mismatched identity.

Checks include actual inventory/active orders/ledger conservation; duplicate and orphan effects; persistent response identity and payload correspondence; unique successful create requests assigned to every required worker; SQLite/FK integrity and constraint semantics. Candidate `audit()` cannot select PASS. Constraint probes occur only in disposable trusted memory backups, never by repairing the candidate's original rows.

The currently registered private suite covers ordinary single-worker behavior; assigned writes and concurrent capacity at 2/4 workers; varied stock/quantity; identical and conflicting retries; cross-worker cancellation/release; create-then-reserve; invalid input and rollback; separate SKUs; mixed cancellations/purchases; WAL; independent reset/reexecution; ordinary competition without the schedule hook; and three interruption/restart windows. Current Suite `1.2.0` includes the added 2/4-worker concurrent reserve/cancel/release and conflicting-payload winner cases, taking the necessary identity set from the original 24 to 28, together with corrected recovery semantics. Required test identities stay only in the private manifest.

PASS requires the actual pytest exit, valid JUnit, exact unique required identity set, complete counts and no required skips/errors/failures, plus required recovery evidence. Business assertions produce FAIL, infrastructure/protocol/evidence failures ERROR and enforced suite limits TIMEOUT. A total of 28 collected tests alone cannot establish task quality or PASS; the earlier 24-case false-positive recovery probe is a concrete counterexample.

Every run must archive topology/control/operation evidence, direct Oracle JSON, real JUnit and errors before failed assertions discard diagnostics. Fingerprints cover the actual supervisor/control/Oracle, suite/private manifest, fixture/source, public input and runtime. D uses distinct versions and suite identity; it does not call A's tests to impersonate a completed D scenario.

## 7. CLI and reproduction — command templates

The following are usage templates, **not statements these commands have already passed**. Use a new M1 archive/root; never direct scripts at historical Phase 1–3.5 archives. Global `--runs-root` precedes the subcommand.

```sh
scripts/orderflow --runs-root <new_m1_archive>/runs validate --episode D --variant v01
scripts/orderflow --runs-root <new_m1_archive>/runs prepare --episode D --variant v01

# Default defect: expected task FAIL / exit 1.
scripts/orderflow --runs-root <new_m1_archive>/runs evaluate --episode D --variant v01

# Trusted maintainer samples, never Participant inputs.
scripts/orderflow --runs-root <new_m1_archive>/runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01.diff
scripts/orderflow --runs-root <new_m1_archive>/runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01-flock.diff
scripts/orderflow --runs-root <new_m1_archive>/runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01-split-ledger.diff

scripts/orderflow --runs-root <new_m1_archive>/runs report --run-id <run_id>
scripts/orderflow --runs-root <new_m1_archive>/runs reset --episode D

# Fresh nonexistent archive; each round creates a new CLI run and DB.
scripts/python312 scripts/reproduce_episode_d.py \
  --archive <new_m1_archive>/repeatability --rounds 10 --strategy all
scripts/python312 scripts/reproduce_episode_d.py \
  --archive <new_m1_archive>/split-ledger-repeatability --rounds 10 --strategy split-ledger

# Only after private-material, secret, resource and isolation gates pass.
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root <new_m1_archive>/pilot-runs \
  run-codex --episode D --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --agent-timeout 1200 --request-budget 160
```

`--strategy all` runs Buggy, Reference and flock independently; it is not all known mutants. The `local-lock-only` sample equals Buggy byte-for-byte and is evaluated through a generated workspace, not an empty diff. The split-ledger mutant has its own strategy command. CLI exits retain PASS=0, FAIL=1, ERROR=2, TIMEOUT=3, NOT_IMPLEMENTED=4. A recorder/summary exit 0 means its expected outcomes were checked, not that Buggy passed.

All submissions reuse Phase 3.5's strict app-Python allowlist, independent patch interpretation, isolated Git application, four SHA256 values and per-file expected/applied equality before Hidden Evaluation. Public test modifications archive separately and cannot replace private evaluation.

## 8. Applicability references and Pilot interpretation

Private `evaluator/private_labels/episode_d_applicability.json` records label versions, reviewers, strategy assumptions, real supporting/counterexample references and origin. A RLock success is a `maintainer_seed` source; it was not the historical Codex team's autonomous strategy. Natural A patches are separately referenced. Unknown-topology VERIFY can remain an explicitly design-level label until a real evidence variant is authorized and built.

Fresh identical-artifact checks at Suite `1.2.0` establish maintainer local-lock A PASS/D FAIL and natural historical DB-repair A/D PASS; their exact IDs, evaluated-tree hashes and origin are in [Task Relations](TASK_RELATIONS.md), separately from the retained Suite `1.0.0` measurements. The stable-flock sample is a distinct legal mechanism. These measurements do not demonstrate actual blind-Agent experience inheritance.

D's blind pilots receive no A history, private labels or controlled seeds. They measure task solvability, diagnosis, runtime/budget and real native collaboration. They cannot measure actual experience inheritance, decision-reference accuracy or governance improvement. Retain every trial and independently report Runtime, native child evidence, Submission Fidelity, automatic closure and Engineering Outcome. A timeout's separate patch replay does not rewrite the original run.

The M1 admission targets are Buggy 10/10 business FAIL, Reference and mechanism-distinct alternative each 10/10 PASS, known wrong strategy discrimination, full effective regression, security checks and three independent frozen Pilot attempts. The [initial Suite `1.0.0` repeatability record](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability/summary.json) remains early evidence. The [accepted Suite `1.2.0` cohort](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability-accepted/summary.json) now contains 30 independent runs, each with 28 cases: **Buggy 10/10 business FAIL, Reference 10/10 PASS and flock 10/10 PASS**. Its [actual command receipt](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/final2-repeat-command/command.json) exits 0 at `2026-10-10T11:47:12.120625+00:00`; the negative CLI runs still exit 1. Current [developer JUnit](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/final2-developer.junit.xml) is 664/664 PASS, and [identity migration](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/TEST_IDENTITY_MIGRATION_FINAL.json) retains all 499 prior identities with 165 additions. Test quantity, one PASS or reference success cannot replace the [Engineering and Research gates](TASK_ADMISSION_GATES.md). Terminal Pilot/aggregate verdicts are in the root reports: original closure1/3, Overall CONDITIONAL PASS.

## 9. Limits and final evidence

The common-API recovery observer is implemented and has fresh supported-API positive/negative controls, including the compensated staged comparison. Deliberate adversarial instrumentation bypass and documented unsupported paths remain limits; missing-window classification stays visible. Kernel peer identity establishes process origin but not third-party attestation of locally mutable evidence. The [isolation audit](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/isolation-final/summary.json) records mandatory private-file/network boundaries PASS with overall security CONDITIONAL. Required D-pool memory/pids cgroups enforce that pool's aggregate boundary; CPU/output sampling windows, Linux namespaces and ordinary Candidate aggregate boundaries still have narrower guarantees. None is a claim of arbitrary hostile-code safety.

[LIVE_GATE.json](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json) binds final offline cohort/topology/cleanup/regression, connectivity preflight and no-secret-content archive checks, reporting mandatory live admission PASS and security CONDITIONAL PASS. Its fixed trial configuration is three independent serial trials, Gateway `gpt-5.6-terra` / `max`, 1,200-second agent timeout and 160-request budget each. Admission is not proof of a completed native Multi-Agent Pilot; completed original runtime/child/evaluator artifacts are linked by the final Pilot report.

Final M1 reports must bind real command receipts, complete result denominators, new Run IDs, patch/tree hashes, exact test/fingerprint data, PID/shared-DB/operation records, crash-window coverage, original failures and unresolved limitations. Preserve all historical archives and old D=PLANNED assertions in their original baseline snapshots; current-state assertion migrations are explicit.

See [task design](TASK_SYSTEM_DESIGN.md), [task relations and exact A origins](TASK_RELATIONS.md), and [preimplementation self-review](history/orderflow/M1_DESIGN_REVIEW.md). Stop after M1; B/C, governance systems and formal G0–G3 remain outside this implementation.

## Final M1 execution addendum — 2026-10-10

Final evidence: [engineering](history/orderflow/M1_EPISODE_D_VALIDATION_REPORT.md), [design review](history/orderflow/M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](history/orderflow/M1_PILOT_REPORT.md), [matrix](history/orderflow/M1_EVIDENCE_MATRIX.md), [limits](history/orderflow/M1_REMAINING_ISSUES.md). Design PASS; D Engineering PASS within declared tested scope; Research/Overall CONDITIONAL PASS. OriginalPilot TIMEOUT/PASS/TIMEOUT, closure1/3; two separate unchanged-Agent offline28PASS results do not upgrade original trials. This update does not rewrite archived preimplementation/history or assert arbitrary hostile safety. Stop atM1; B/C planned, Experience disabled.
