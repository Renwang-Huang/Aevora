# Gen 2 development baseline handoff

Gen1.5 consolidation is complete locally with CONDITIONAL PASS qualifications in
GEN1_5_VALIDATION_REPORT. Worktree `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5`, branch aevora-gen1-5-consolidation-20261013.
No new Gen2 feature has started. Final Commit/Tree and clean state are in the
outside-Full delivery receipt, not retrospectively inserted into history.

## Canonical ownership

- Core aevora_core/src/aevora: existing resolver, evidence, graph, governance,
  candidate/lifecycle, trusted feedback, CLI and scoped MCP APIs unchanged.
- Console console/src + web: bounded read-only projections, three pages, LIVE and
  externally pinned Replay. Decisions remain Core/FalkorDB authority.
- Public Hero/deployment/bootstrap: stable h4/ and scripts/aevora_bootstrap.py.
  Canonical evidence authoring source is tools/public_evidence; consumers are
  generated. Run sync + --check, never manually edit generated copies.
- Private maintainer: app/benchmark/evaluator/integrations and aevora_maintainer.
  Audit Capsule body is unique private implementation; legacy public import is
  optional same-module alias, unchanged capsule protocol version.
- Current developer tools: tools/dev.py, Make, public_release.py, paths.py,
  validation/regression.py. Existing phase adapters remain for proven callers.
- Historical authority: docs/history index + external original immutable Full/Lite.
  Current product/maintainer guides are README/DEVELOPMENT/docs/current.

Read GEN1_5_MIGRATION_MATRIX (pre-change501-source map) and
GEN1_5_APPLIED_MIGRATIONS (actual source changes/additions). Old imports/CLI and
all1802 test IDs are preserved. Original85 test sources and39 truth files unchanged.

## Safe working sequence

Create another linked Git worktree for future tasks. Use nativePython3.12 setup
from DEVELOPMENT, or this machine's exact external namespace driver in `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5_evidence/Gen1.5-20261013T133642Z-e7abe600-8887-4394-91b0-0aceef13353e`.
Actual Python3.12.14/SQLite3.51.3 source and argv are in current command receipts.
Only trusted validators mount original archives readonly. Participant sandbox
must remain narrower; no maintainer AGENTS, Oracle, reference, identity or key.
Use fresh external output and an explicitly owned new database port/volume;
current output guard refuses linked parents and sealed Full ancestors.

Current commands cover Core/Console install, locked build/test, DB init/health,
MCP config, public build, full developer test, CLI and D-v02 regression. Physical
probe, official SDK, image/browser and cold-control examples have actual receipts.
Do not run historical default writers against sealed Full. Source/ZIP/wheel/sdist/
image/member checks precede public distribution. No remote target is authorized.

## Protected contracts and future review items

Do not alter WHEN/WHY/APPLY/VERIFY/ABSTAIN, scope/version/withdrawal, snapshot or
lifecycle authority simply to pass tests. External public tests never create VO;
Agent proposal is untrusted, Host independent source/outcome/admission separate.
Preserve native completion-aware runtime, patch fidelity, independent OrderFlow
Oracle, public/private release boundary and historical identifiers/results.

Next separately authorized work may review preexisting oversized-UDS rejection
close/send race; exact kernel chronology remains unverified. AOF139, nativeUDS
EPERM, shared kernel/EOL, RDB unsaved tail and causal/adoption UNKNOWN remain.
No broad phase-script deletion was justified: keep ambiguous callers and evaluate
before deprecation. Further directory churn has no independent acceptance value.

Final regression1820PASS incl1802 inherited IDs. Actual D-v02 buggy28/8
and reference36/36; all actual SDK/Graph/browser/image/physical checks have records.
Historic three-native-child verification is a recheck, not a new paid challenge.
Stop at Gen1.5 and wait for the next architecture/product objective.
