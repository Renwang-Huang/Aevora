# Task Admission Gates — M1 contract v1.2.0

**Maintainer/private review checklist. Do not publish this document or the required hidden cases to Participants.** This is the admission contract, not a completed result sheet. Evidence must be newly linked by the final validation report; an unchecked item is not PASS.

Current source has D `IMPLEMENTED`, **28** required suite identities, Scenario `2.0.0`, Fixture `1.0.0`, Suite `1.2.0` and Evaluator `3.1.0`; B/C remain PLANNED. The original preimplementation checklist is preserved in the archive identified by [m1_validation/CURRENT](../m1_validation/CURRENT). The [accepted frozen-version repeat cohort](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability-accepted/summary.json) now records 10 Buggy business FAIL, 10 Reference PASS and 10 flock PASS, each with 28 cases. Current regression is 664/664 PASS with 499 old identities retained. The suite `1.0.0` custom split-ledger false PASS exposed an observation blind spot; current SQLite observer `1.1.0` adds common API/business-file/write-transaction observation. Fresh recovery controls include correct compensated staging PASS and naive uncompensated staging FAIL. These evidence facts support individual checks; the checklist remains a reusable contract, and final reports record the completed pilots and CONDITIONAL Research/Overall admission.

## 1. Reporting rules

Every review item records `PASS / FAIL / CONDITIONAL / BLOCKED / UNVERIFIED`, an actual artifact reference and its source kind: `historical`, `current_dynamic`, `static`, or `synthetic_control`. Never infer current PASS from an old report. A gate cannot be established solely by test quantity, reference patch existence or a single good run.

Use separate conclusions: Task System Design, Episode Engineering Gate, Episode Research Gate, Agent Pilot and Overall. PASS requires all required evidence; unresolved scope/threat-model limits may justify CONDITIONAL PASS with named conditions. An unexecuted necessary condition remains UNVERIFIED/BLOCKED and must affect the aggregate verdict.

## 2. Package and design gate

- [ ] Family, scenario, material variant, fault mechanism, context, evidence condition and relation are distinguished.
- [ ] Current executable services and planned contracts are explicitly separated; B/C remain PLANNED in M1.
- [ ] Public business semantics define ordinary behavior, retries/conflicting payloads, insufficient capacity, cancellation and supported recovery; SLA is discoverable and reasonable.
- [ ] Private engineering truth and private decision reference have different responsibilities and independent versions.
- [ ] Package contains public inputs, fixtures/fault/reset, private suite/Oracle, buggy/reference, alternative fixes, wrong mutants, fingerprints and evidence recipe.
- [ ] A new variant states a material causal, topology-assumption or information difference; parameter changes are not counted as new research tasks.
- [ ] Preimplementation design self-review identifies falsifying observations and unresolved implementation obligations.

## 3. Engineering Quality Gate

| ID | Required evidence | Falsifier or forbidden substitute |
|---|---|---|
| E1 fault reality | Executed causal path; normal single-worker path; recorded schedule/read/write interleaving and raw DB discrepancy | A fabricated return value, intentionally raised exception or altered test assertion is not fault evidence |
| E2 topology | At least 2 and 4 independent trusted process identities, overlapping operations, actual same DB file identity and writes by multiple workers | Host thread count, equal path strings, child self-report, or one serial service proxy |
| E3 deterministic reproduction | At least 10 fresh Buggy runs, all business FAIL; IDs, exact JUnit, Oracle reason and schedule evidence | Startup ERROR/TIMEOUT, old DB/JUnit reuse, sleep/random load alone |
| E4 solvability | Reference 10/10 PASS and mechanism-distinct legal alternative 10/10 PASS at 2/4 workers and key recovery contexts | Cosmetic patch variants or a test that requires the author's exact SQL/lock |
| E5 discrimination | Process-local lock-only and another realistic wrong mechanism fail for the intended business reason; obvious bypass mutants fail | Counting syntax errors as mutant detection or requiring irrelevant internal implementation shape |
| E6 business oracle | Trusted direct raw SQLite audit against trusted fixtures, actual response IDs, rows/ledger and live constraint semantics | Candidate audit(), a stored fixture claim or candidate-selected PASS |
| E7 recovery | Recorded abnormal exit/restart; valid unknown-ack state, lost-response retry and subsequent writes/cancellation; duplicate identity/payload checks; legal custom/staged transaction accepted and incorrect custom split-ledger rejected using supported common SQLite APIs; exact per-window coverage | Declaring a killed request successful, ignoring corrupt state, enforcing one transaction count, treating auxiliary/read-only commits as business proof, or assuming internal Persistence hooks cover all commits |
| E8 evaluator integrity | Actual pytest exit, parseable JUnit, exact unique required identities, complete count, no required skip/error; real suite/private-manifest/Oracle fingerprints | Only a total count, stdout containing PASS or reduced/renamed/skipped failing cases |
| E9 fidelity/lifecycle | Baseline/Patch/Expected/Applied digests, per-file equality, bad submission rejected before evaluator; prepare/report/reset and no residue | Git exit 0, collecting a patch without applying it, stale evidence, changed source mid-run |
| E10 backwards compatibility | Full current regression; Smoke/A positive/negative and alternatives; Manual, Codex contracts, ERROR/TIMEOUT, resets and trace; B/C NOT_IMPLEMENTED | Deleting old identities or weakening unrelated assertions |
| E11 safety | Actual private-file, network/model-channel and resource/cleanup regression after topology changes; run-owned shared data only | Directory names, prompt instructions, unrestricted fallback or exposing credentials |

### Recovery and scheduling fairness

Bound scheduling waits and release a correct transaction/lock path even if it never invokes the defect hook or serializes entry. The harness does not require all parties to reach a checkpoint while holding an exclusive lock. Use another valid write-assignment phase to prove each worker acts; do not demand a worker win scarce-stock contention by chance.

Expected stock/results derive from real fixture and requests. For uniform unique one-SKU orders without cancellation, accepted capacity is `min(request_count, initial_stock // quantity)`; parameterized and multi-SKU tests use their corresponding semantics. Requests interrupted at an uncertain commit point are reconciled by persistent identity and retry, not guessed from missing responses. No order, a valid pending created order, or a fully reserved order can be legitimate unknown-ack states if the independent Oracle is consistent and retry results in one complete reservation. A reached `before_response` with `ok=True` instead requires already complete successful business state.

Treat SQL busy/transport/startup/time-limit failures separately from violated business invariants. Preserve the recorded context to distinguish an environment defect from a legitimate candidate error. Do not mask all exceptions as stock exhaustion.

Record the observer's actual API and per-window availability for each strategy. It must identify the real business database device/inode and written transactions, exclude read-only/auxiliary paths and only emit postcommit after actual successful commit. The internal Persistence implementation and one transaction count are not acceptance requirements. In an otherwise-passing evaluation, missing mandatory committed/successful-response interruption is **ERROR / RECOVERY_EVIDENCE_UNVERIFIED**, not a business FAIL; autocommit can lack a precommit point and report PARTIAL coverage without fabricating it. Deliberately bypassed instrumentation/native extensions and documented unsupported APIs remain declared limitations. A green JUnit total does not upgrade unavailable coverage.

Require both a coherent staged positive control and an incomplete staged negative control. A persistent provisional marker plus bounded compensation can preserve intentional `reserve=False` created orders while removing only a failed new provisional creation. The [actual compensated full-suite run](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/compensated-full-suite-command/stdout.log) is 28/28 PASS with 36 consistent raw Oracle records and COMPLETE three-window coverage. The [closure pair](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-closure/summary.json) independently reproduces legal staging PASS and uncompensated staging FAIL. Preserve the [original matrix FAIL](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-matrix-final/summary.json) where a naive sample was incorrectly expected to be legal; documenting its correction is not permission to relabel or delete that execution.

### D state transition migration

Old tests asserting D=PLANNED were valid at their version. On actual D registration, preserve their original source bytes in the M1 baseline archive, keep identity where possible, and document each current assertion transition with rationale and replacement check. B/C assertions remain unchanged. No test is silently skipped or removed to make the historical 499 count look green.

## 4. Research Quality Gate

| ID | Required evidence | Limit on conclusions |
|---|---|---|
| R1 blindness | Participant allowlist/tree/input hashes; review issue/title/metadata/tests for root cause or strategy labels; dynamic private reads denied | Public topology facts are allowed; private anticipated decision is not |
| R2 relationships | Concrete historical strategy patch and report; origin natural/maintainer_seed/synthetic; assumptions; target positive/counterexample runs | An A task outcome does not prove its agent chose RLock or that experience later caused a decision |
| R3 independent labels | Versioned private APPLY/VERIFY/ABSTAIN conditions, reviewer, sources, limitations; strategy-level reference separate from code result | Do not derive a gold decision from the final task PASS, force a technique or send labels to a blind agent |
| R4 observable strategy differential | Actual A local-lock success and D local-lock failure, plus shared-DB strategy results and context | This is an offline strategy validity check, not measured Agent negative transfer or governance benefit |
| R5 calibration | Three fresh blind native-agent sessions after security gate, fixed source/evaluator/public inputs/budget; complete attempts and real trace | Three pilots are not a statistically valid success-rate comparison or proof of multi-agent superiority |
| R6 metrics/provenance | Separate runtime/submission/integration/task outcome; actual elapsed/usage with missing fields labelled; original failures retained | A timeout's separately replayed patch cannot become original automatic success |
| R7 boundary | Experience DISABLED, no G0–G3/feedback/control-history implementation; verified facts versus unknowns explicit | No governance improvement, historical inheritance or research-grade maturity claim |

R2/R4 certify only the specifically tested artifacts and assumptions. Private unknown-topology VERIFY labels may be `REFERENCE-ONLY / design-level` until a real evidence variant is implemented; do not count that as a third executable task.

## 5. Pilot admission and analysis recipe

1. Freeze the new cohort's source/fixture/suite/private-label versions and public material hashes; record any prior failure or compatibility run outside that cohort.
2. Confirm actual provider/model/effort, bounded timeout/request/agent concurrency, secret handling and mandatory security controls. If unavailable, report BLOCKED; no unrestricted fallback.
3. Use new Run/session/state for each trial. Provide current public issue/code/tests only; no maintainer context, A archive, root maintainer guide or seeded experience.
4. Collect official raw JSONL and real native parent/child/task/tool/completion/receipt references; exclude inherited parent history. Configuration and prose are insufficient evidence.
5. Extract the agent's actual patch without repair or replacement, apply trusted fidelity checks and evaluate the frozen private suite/Oracle.
6. Publish all three attempts: Runtime, native evidence, submission, automatic closure, task result, errors, time and available usage. Give absolute counts and the full denominator.
7. Review ceiling/floor signals and issue/budget adequacy. Proposed changes require a new version and new cohort; preserve the original one. No statistical or causal method claim is made in M1.

## 6. Evidence sufficiency and release

Mandatory file/network boundaries can be PASS while overall security remains CONDITIONAL. The current D pool's required memory/pids cgroup closes its specific aggregate boundary; ordinary candidate topologies, sampled CPU/output limits, supported SQLite API coverage, Linux namespaces and locally mutable evidence have narrower guarantees. The [live admission gate](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json) is a prerequisite check with real connectivity evidence, not a finished trial or research-quality verdict.

- [ ] Commands are exact argv with cwd, UTC start/end, elapsed and inner/outer exit codes; wrappers do not relabel candidate outcomes.
- [ ] Every repeated run has a new ID and independent initialization; raw data and failed attempts are reachable.
- [ ] Fingerprints come from actual files/runtime; public-input and evaluated-tree identity match their declared versions.
- [ ] Current, historical, static, synthetic and unverified claims are separated in the matrix.
- [ ] All writers stop before evidence manifest/checksums; the manifest's own receipt/exclusion rule is explicit.
- [ ] Historical Phase 1–3.5 artifacts are unchanged; new M1 artifacts live in a dedicated archive.
- [ ] Safety limits and local-hash/non-attestation limits remain stated; no key value or key digest enters an artifact.
- [ ] Final review reports unfinished gates and stops at M1.

See [Task System Design](TASK_SYSTEM_DESIGN.md), [Task Relations](TASK_RELATIONS.md) and [preimplementation design review](M1_DESIGN_REVIEW.md). This file intentionally does not prefill PASS checkboxes before dynamic validation.

## Final M1 execution addendum — 2026-10-10

Final evidence: [engineering](history/orderflow/M1_EPISODE_D_VALIDATION_REPORT.md), [design review](history/orderflow/M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](history/orderflow/M1_PILOT_REPORT.md), [matrix](history/orderflow/M1_EVIDENCE_MATRIX.md), [limits](history/orderflow/M1_REMAINING_ISSUES.md). Design PASS; D Engineering PASS within declared tested scope; Research/Overall CONDITIONAL PASS. OriginalPilot TIMEOUT/PASS/TIMEOUT, closure1/3; two separate unchanged-Agent offline28PASS results do not upgrade original trials. This update does not rewrite archived preimplementation/history or assert arbitrary hostile safety. Stop atM1; B/C planned, Experience disabled.
