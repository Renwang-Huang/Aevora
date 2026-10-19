# Gen 1.5.1 G1 scope freeze

Baseline: `47bd9101126f5b5fb8d8dc7cec88f0dfe3712c93` / tree
`b6d6e4aa2552a2fd6e999e4fa7310ac3e440a63d`. Changes occur only in the third
linked worktree `aevora_gen1_5_1`, dedicated branch. The original root is dirty;
Gen1.5 has user-added untracked ROS `.vscode` files. Both states are protected.

## Authorized slices

1. Native VS Code relative multi-root views and an additive stdlib checker/tests.
2. Current navigation/documentation and audit metadata.
3. Real inherited regression and public/Benchmark/runtime acceptance, using new
   external outputs and an isolated tmpfs-backed test database, no old volume operations.
4. Local commits and a bounded maintainer review export, never a public release of
   the maintainer tree.

`NO_SAFE_STRUCTURAL_MIGRATION`: zero existing directory moves/deletions, zero
business/Runner/Evaluator/Gateway/Core/Console semantic changes. The new validator
checks developer-view contracts; it does not introduce product functionality.

## Non-targets

All H1-H4/Gen1.5 sealed Full/Lite/Run/source epochs and original failures, private
truth/Oracle/Reference/labels, existing test sources and identities, root taskbooks,
old reports, user `.vscode`, history paths/DB volumes and all governance/model/MCP
permissions remain unchanged. No blanket ignore/hide for source, no paid model
challenge, no remote push, no Gen2 feature. Visual filters are not security fences.
Known risks remain as listed in the handoff and validation report.
