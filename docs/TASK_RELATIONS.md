# Task Relations — maintainer reference v1.2.0

**Visibility: maintainer/private.** These relationships are not part of the blind Participant input. M1 does not enable retrieval or history injection. The terms below describe strategy validity and possible future experimental hypotheses, not actual experience governance effects.

## 1. Exact provenance before narrative

| Strategy source | Real evidence | Origin and supported statement |
|---|---|---|
| A complete critical section protected by process-local RLock | Phase 2 validation `fb67fd4e-939b-41cd-ab60-90e14194e6e5`, Run `b07ce31c-2038-4935-ac35-887d5b2d60cb`; `scripts/validate_phase2.py` constructs the wrapper; full 14-case suite PASS | `maintainer_seed`; one Worker/one shared object and actual threaded ingress. **Not a strategy naturally chosen by Codex** |
| A alternative conditional DB update | Same Phase 2 validation, Run `46baa9fd-1740-4559-ab41-fc9066dca821`; full suite PASS | `maintainer_seed`; changing capacity state atomically can remain useful with shared DB access |
| Codex's actual A patch | Original Phase 3 Run `339f7d73-29df-4242-8920-9e566bce8a9c`; actual patch SHA256 `0525c9650546d438589bd26e7bafd46cd0b1e51b6e469fd67bcb8458138d9f0f`; new Phase 3.5 replay `119461d5-b551-4fa1-80f3-3158816ff931` PASS 14/14 | `natural` patch/outcome evidence; DB conditional-update strategy. Do not infer an unobserved reasoning process or experience record |
| Fresh A recovery challenges | `272384f8-eb91-4eb1-9c37-52f46157dfbe` and `1fa7ec49-e9f3-480a-b5f3-4e67ff4e7d38`: automatic PASS 14/14; `7cec1187-72a0-4ee5-b12c-addc4758f5b1`: TIMEOUT, automatic NOT_RUN | `natural`; exact patch and official child evidence are archived. Its separate `2ba58809-fc3e-4f95-9b8f-2b70c93fdaa9` replay PASS is not automatic success |

The Phase 2 results and construction are historical sources, not proof the samples pass a later checkout; the fresh M1 checks below supply their own IDs and versioned evidence. Natural means real agent-produced artifact, not an implemented natural-experience database. References: [Phase 2 report](../PHASE2_VALIDATION_REPORT.md), [Phase 3 report](../PHASE3_VALIDATION_REPORT.md), [Phase 3.5 report](../PHASE3_5_VALIDATION_REPORT.md).

### Current M1 exact-artifact measurements

D is now IMPLEMENTED, Scenario `2.0.0`, Fixture `1.0.0`, current Suite `1.2.0` with **28** cases and Evaluator `3.1.0`. The active archive is identified by [m1_validation/CURRENT](../m1_validation/CURRENT); the inspected [exact strategy transfer record](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/current-offline/exact-strategy-transfer.json) records the following **earlier suite `1.0.0`** executed outcomes. Source and target evaluated-tree hashes match for each pair; the target is not a conceptually similar substitute.

| Origin and strategy | Fresh source A Run / result | Fresh target D Run / result | Identical evaluated tree SHA256 |
|---|---|---|---|
| `maintainer_seed`, complete local RLock | `af877ab0-2f7b-4c46-bf8e-93ef59b1fb6b`, 14/14 PASS | `09ca4469-dfe3-40a6-8b56-41a641b030a5`, 10 PASS / 14 FAIL of 24 | `85127c72226424724269e005543f81c61fb80ab8cebdf1dc15e84d62f15917a5` |
| `natural`, original historical agent DB repair | `982d4aa3-c511-4e60-9558-8e256e884a43`, 14/14 PASS | `9e79a91a-058b-4070-a88c-31c888ec3479`, 24/24 PASS | `5011b878e81cb73aa604867e866cfc52d5db25f37a21c4b22e3721277eeba2b5` |

These are evidence of a specific context-dependent strategy difference in the inspected earlier harness. They do not certify Suite `1.2.0`, three-Pilot outcomes or measured Agent experience inheritance. A distinct custom split-ledger wrong implementation passed the old 24-case harness when commit observation was bypassed; preserve that false-positive result as a limitation of the earlier harness.

The [new frozen-version transfer record](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/offline-final/exact-strategy-transfer.json) now supplies distinct source and target runs at D Suite `1.2.0` / Evaluator `3.1.0`, again with exact evaluated-tree equality:

| Origin and strategy | Source A Run / result | Target D Run / result | Identical evaluated tree SHA256 |
|---|---|---|---|
| `maintainer_seed`, complete local RLock | `6a312f02-3e28-406a-81f7-86b2636e836f`, PASS | `c39773d4-33fe-408b-81af-2b3dcd19fa84`, FAIL | `85127c72226424724269e005543f81c61fb80ab8cebdf1dc15e84d62f15917a5` |
| `natural`, original historical agent DB repair | `4943e873-6e9d-4905-a281-dfb621b56748`, PASS | `cf083714-0a91-4392-81ed-1070f2cdef71`, PASS | `5011b878e81cb73aa604867e866cfc52d5db25f37a21c4b22e3721277eeba2b5` |

The [accepted new repeat cohort](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability-accepted/summary.json) has 30 independent D runs at this version: 10/10 Buggy business FAIL, 10/10 Reference PASS and 10/10 stable-flock PASS, each with 28 cases. The current common Python SQLite observer was also validated by correct custom transaction controls and incorrect split-ledger controls. A coherent compensated multi-stage sample passes 28/28 and all three observed recovery windows, while a naive uncompensated sample fails 16 PASS / 12 FAIL; [the final closure pair](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-closure/summary.json) preserves both actual outcomes. These are strategy and evaluator-fairness measurements, not historical inheritance by blind Agents. Three pilots are complete; Research/Overall CONDITIONAL PASS and original closure1/3 in the terminal reports.

The [initial repeatability summary](../m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability/summary.json) has 30 fresh runs under Suite `1.0.0`: Buggy 10/10 FAIL, Reference 10/10 PASS and flock 10/10 PASS. It remains early evidence, not a substitute for corrected Suite `1.2.0` final rounds. The current common-API observer filters by actual business DB device/inode and written transactions; auxiliary/read-only commits cannot supply migration/recovery evidence. Unknown-ack coherent pending creation is legal, while an acknowledged successful reservation must already be complete. Do not reject a coherent staged solution merely because it uses more than one transaction.

## 2. A → D: conditional positive transfer

**Candidate premise:** Both contexts use one shared, file-backed SQLite authority; all orders and their inventory/ledger effects are committed atomically with persistent identities. A tested DB capacity update prevents stale stock acceptance and preserves coupled side effects.

**Target support condition:** D's independent worker connections operate on that same DB, and the complete order/reservation operation still uses valid transaction boundaries, bounded contention handling and durable retry semantics. Test the actual strategy artifact under 2/4 workers, variable stock/quantity, cancellation and restart. “Uses SQL UPDATE” alone is insufficient: a detached ledger commit can still fail recovery.

**Private reference:** APPLY may be supported for the capacity-atomicity principle under these premises. The engineer must still verify missing recovery/idempotency obligations. This is partial reuse of a principle, not a claim that an A patch automatically solves every D requirement.

**Falsifier:** A passes but D exposes orphan rows, duplicated reserve/release entries, lost updates, incorrect response-to-persistence correspondence or nonrecoverable contention. Such a result updates the private scope/reference; it does not justify rewriting A history.

## 3. A → D: process-local synchronization boundary

**Historical premise:** The maintainer's A wrapper serializes the entire stale read/create/reserve path inside one process. All relevant calls share the same RLock. The thread pool remains real; the critical section is serialized. This explains why that exact controlled sample can pass A.

**Changed target premise:** Independent workers load their own Python objects and share a database rather than one lock object. Each worker can hold its own local lock while another reaches the same business read/write window. Real stale reads and later commits can disagree with the order/ledger totals despite per-process exclusion.

**Private reference:** ABSTAIN from claiming the *local lock alone* supplies cross-worker coordination. This reference does not ban local locks: a legal DB-level solution may also use one internally. Evaluate final business behavior, not the presence of `RLock` in source.

**Measured M1 counterexample:** Both the preserved earlier pair and the new Suite `1.2.0` identical-artifact pair above establish fresh A success and D business FAIL, not a startup error or timeout. Preserve source/patch hashes, separate PID identities, shared DB identity, schedule arrivals and Oracle discrepancy; a subsequent harness change requires another fresh versioned review. This measured strategy boundary does not prefill the Pilot or Research gate.

**What M1 may say:** A specifically tested strategy has a context-dependent validity boundary.

**What M1 may not say:** A blind D participant inherited that strategy, an actual Agent suffered negative transfer, or a governance method improved its decision. Those require separately authorized exposure, decision observations and controlled comparisons.

## 4. Insufficient topology evidence

If a future task says “workers” without establishing whether this means threads in one process, independent processes, one shared database or separate replicas, the premise is unresolved. The private design reference is VERIFY: inspect process identities, shared state and persistence assumptions before transferring a synchronization claim.

This is currently **REFERENCE-ONLY / design-level**, not a third executable D variant. Do not covertly withhold essential topology from the M1 public issue or invent a VERIFY event for a participant who was never given experience. If implemented later, version its real evidence condition, public diagnostics and Oracle, then pass the same admission gates.

## 5. Future relationships — PLANNED

| Relationship | Hypothesis and required future evidence | Current status |
|---|---|---|
| A → B | Concurrent exclusion is not durable payment idempotency; require a separate persisted gateway side-effect ledger and crash/retry counterexamples | PLANNED; no simulated charge service or B evaluation exists |
| B → C | Durable duplicate prevention can help, but event ordering, legal state transitions and compensation require additional semantics | PLANNED; no C delivery/compensation task exists |
| A/B/C → new variants | Reuse may be conditional when mechanism, topology, evidence or constraints change | PLANNED; parameterized cases alone do not establish generalization |
| A → D controlled exposure | Compare raw history and governed history using the same corpus and budget | M4/M5 PLANNED; M1 blind pilots receive no historical material |

The framework's Disabled Experience methods are interfaces only. Private labels are review data, not the implementation of APPLY/VERIFY/ABSTAIN reasoning or an experience evolution algorithm.

## 6. Relation record and final evidence

Each private relation should preserve relation/label version, strategy ID and patch hash, source episode/run/report and origin, source/target assumptions, information condition, predeclared label, positive/counterexample refs, reviewer identity and limitations. Use `UNVERIFIED` when a supporting artifact is missing. Store the label file solely under trusted `evaluator/private_labels/`; verify it is absent from the Participant tree and inaccessible dynamically.

Do not turn an engineering result into a decision label after seeing whether a participant passed. A private applicability reference and an independently evaluated code outcome may both be present, but M1 has no measured experience decision or feedback effect to score. Updated M1 evidence must be linked in new reports; historical references above stay immutable.

## Final M1 execution addendum — 2026-10-10

Final evidence: [engineering](../M1_EPISODE_D_VALIDATION_REPORT.md), [design review](../M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](../M1_PILOT_REPORT.md), [matrix](../M1_EVIDENCE_MATRIX.md), [limits](../M1_REMAINING_ISSUES.md). Design PASS; D Engineering PASS within declared tested scope; Research/Overall CONDITIONAL PASS. OriginalPilot TIMEOUT/PASS/TIMEOUT, closure1/3; two separate unchanged-Agent offline28PASS results do not upgrade original trials. This update does not rewrite archived preimplementation/history or assert arbitrary hostile safety. Stop atM1; B/C planned, Experience disabled.
