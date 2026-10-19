# G0 residual debt audit

## Facts and method

The baseline contains532 tracked files and80 visible tracked root files; physical
root entries are106 at Gen1.5 and91 at the original root. The197-row classification
lists every top-level entry, including mixed directories. Original root HEAD differs
from Gen1.5; no dirty root content is used to substitute the frozen source commit.
A source-only AST scan records2744 import edges. Exact `rg` callers/argv, shallow
entries, tracked hashes, status/index and task pin are in external `g0/` receipts.
AST/caller evidence is static, not proof that every dynamic plugin caller is known.

## Architecture debt

- Audit Capsule has one private body and the tested optional legacy alias. Keep it.
- Public ordinary Core/MCP imports remain independent of Benchmark/Evaluator.
  The deferred `orderflow_outcome_bridge` Host path is an intentional privileged
  integration, not an ordinary product dependency; it is not eligible for merging.
- Four standalone verifier/projection copies are deterministic consumers of
  `tools/public_evidence`, required by inherited byte-equality and deployment
  contracts (`tools/sync_public_evidence.py`, `test_gen15_repository.py`). Keep them.
- `tools/dev.py` calls H2 CLI/D-v02 and H4 regression collectors. Stage names alone
  do not prove obsolescence. Current release builder and Make callers are explicit.
- Oversized UDS close/send race remains real debt outside this hygiene iteration.
  Ambiguous historical adapters remain UNRESOLVED rather than dead-code claims.

No new safe structural migration was proven. No business refactor is authorized
by the classification. This is not a declaration of an architecture free of debt.

## Repository organization

- `.venv`, pytest/egg-info/node_modules are ignored; no such tracked files found.
- Tracked Console static files are intentional generated package resources;
  `console/build.mjs`, package-data/MANIFEST and Docker need them. Do not untrack.
- Gen1.5 history-named directories inspected here are empty namespace bind targets;
  the original root holds actual histories. Neither is copied/moved/deleted.
- Root `src/aevora_observatory` has no tracked files; actual package authority is
  `console/src`. Local build artifacts are classified as GENERATED, retained.
- Root frozen reports and taskbooks retain inbound provenance paths. New current
  navigation provides an index without rewriting sealed documents.

## VS Code visual issues

User-added `.vscode` points to unrelated ROS/mapping Python3.10 paths and has no
role views. Preserve it in both prior trees; new relative multi-root views do not
include the root folder, so those folder settings are not inherited. Product view
omits private Benchmark/Oracle and host-dependent Core tests. Maintainer adds those
explicitly. Full root remains accessible on demand; no files change location.

## Four distinct boundaries

| Mechanism | Authority |
|---|---|
| Workspace files/search/watcher filters | Editor UX only; same trusted local user |
| `.gitignore` | Untracked generated paths; no security or untracking guarantee |
| Generated public `.dockerignore` | Build-context filtering after allowlist selection |
| `tools/public_release.py` allowlist + real artifact scans | Public release boundary |

None provides Participant isolation. Existing bubblewrap/scoped MCP/Host authority
remain the actual execution boundary. No cross-boundary widening is proposed.

## Mature solution references

Native relative multi-root folders, named cwd/process tasks and parent Git discovery
reuse [VS Code documentation](https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces)
and the [official Git extension configuration](https://github.com/microsoft/vscode/blob/main/extensions/git/package.json).
Installed VS Code schema/CLI verification determines local support; upstream main
is guidance, not proof of the installed version. No custom IDE/project manager.

## Static dependency recheck

The full501-row old ownership map was parsed. Current AST resolves817
local import edges across319 modules. Tarjan finds three **static**
cycle candidates: candidate/governance/models; cli/connection; manifest/registry.
They are unchanged inherited relationships. The reverse edges are deferred inside
functions: models.py:194, connection.py:20, cli.py:69 and manifest.py:114. Ordinary
Core-only SDK/CLI and full imports actually pass; this does not prove future
call-order safety. They are retained dependency-review candidates, with no
authorized semantic refactor justified by this workspace iteration. Raw resolved
edges and SCC groups are in external `g3/STATIC_DEPENDENCY_RECHECK.json`.

G5 detected two late new-worktree `.vscode` files, exact Gen15 ROS-config bytes;
writer UNVERIFIED. Dated scope addendum preserves files with a root-only ignore
rule. This is a local environment issue, not architecture debt; prior tree
ignore/status are preserved. Full root may still inherit them, role views do not.
