# Aevora daily workspaces

Open these files from this checkout (do not open its parent research workspace):

```sh
code --new-window Aevora.Product.code-workspace
code --new-window Aevora.Maintainer.code-workspace
python3 tools/workspace_check.py
```

## Choose a view

| Product Dev — eight roots | Why it is editable |
|---|---|
| Core | `aevora_core/src`: actual Core/MCP/CLI source |
| Core Docs / Receipt Example | Public contracts and ordinary project example |
| Console Runtime | `console/src`: readonly API and generated vendored/static assets |
| Public Tests and UI | `console/web`: UI sources and actual Node public tests |
| Public UX | `h4`: active Hero/Replay/deployment compatibility resources |
| Current Docs | `docs/current`: current architecture and workspace guide |
| Dev Tools | `tools/public_evidence`: unique editable evidence-tool sources |

Maintainer Dev adds OrderFlow, Benchmark, Trusted Evaluator, Host Integrations,
Private Audit, Maintainer Tests, Core Maintainer Tests, Maintainer Tools,
Reproduction Scripts, Evidence Index and History Index. It has19 roots including
intentional nested canonical-tool view. Core's full test directory includes
privileged outcome/audit tests; it is deliberately not a Product root. These are
local trusted development views, **not release selectors or security sandboxes**.
The historic `Private Audit` label names owner-side tooling whose source is now
included; generated sensitive audit/session data remains outside publication.
The [full-project scope](../../FULL_PROJECT_SCOPE_AND_LICENSE.md) defines source
inclusion independently of which editor view is open.

Package metadata and root navigation stay in their stable paths. Use File → Open
File, or these links: [README](../../README.md), [DEVELOPMENT](../../DEVELOPMENT.md),
[public Quickstart](../QUICKSTART.md), [MCP](../CODEX_MCP_SETUP.md),
[ownership](../../GEN1_5_1_ROOT_CLASSIFICATION.csv),
[release boundary](../../PUBLIC_RELEASE_BOUNDARY.md). No source copies or phase
path migration is necessary. Edit generated evidence only at its canonical root;
use `tools/sync_public_evidence.py` and `--check`. Build static assets from
`console/web` with `npm --prefix console run build`.

## Git, terminal, tasks, search and tests

All roots belong to the **same parent linked Git worktree**. Built-in Git opens
parent repositories (`git.openRepositoryInParentFolders=always`), with recursive
repository scanning disabled. SCM changes are repository-wide and may include
engineering files even in Product view. Package only the reviewed source selection;
local generated files and secrets are not publication inputs.

A new terminal starts at `${workspaceFolder:Core}/../..`, the true checkout root.
Every provided process task explicitly uses that cwd. Tasks → Run Task offers
view check, canonical-source check, current CLI map, Console build and public Node
tests. No task launches a model, database, publisher or hidden evaluator by default.
Python's default interpreter points to this checkout's own `.venv`; set up the
Python3.12 environment using DEVELOPMENT first. On this machine the Python/SQLite
runtime needs the trusted external namespace driver; bare-host venv is not assumed
working. See the current validation receipts for actual argv/runtime/version.

Global search spans selected roots; it does not include omitted archives. Cache
filters cover only `.venv`, pytest/pycache, node_modules, build/dist and egg-info.
They do not hide source, valid tests, failures or tracked static package resources.
Search follows no symlinks. The older 1820-test profile is historical. Current
full-source tests require an engineering environment, owned real FalkorDB and
fresh external outputs; legacy G1 history prerequisites retain 51 SKIPs in the
approved source baseline. Public UI has its own Node tests. See the current
[reproduction profiles](../REPRODUCIBILITY.md). The Python testing extension is
optional: test discovery
via terminal commands is authoritative, extension Test Explorer is unverified.

## Full root / history inspection

To inspect every root file (including old taskbooks/reports and local artifacts):

```sh
code --new-window .
git status --short --branch
```

Use History Index and Evidence Index to find actual immutable archives in their
original external/original-root locations. Do not add large archives as everyday
workspace roots. Explorer exclusions may be temporarily disabled in Workspace
settings; omitted folders must be explicitly opened/added. Neither action moves
or deletes a file. The existing unrelated user `.vscode` in old worktrees remains
untouched; opening those old roots may still apply their ROS settings.

## Verification scope and manual visual acceptance

The checker actually parses relative folders, verifies directories/real Git roots,
checks named cwd and allowed process tasks, and rejects source-hiding filters
or unlisted Product-view roots. View membership is not a publication boundary. The historical native Extension
Host receipts confirm actual8/19 roots, builtin Git SCM,
native findFiles search, three process tasks and the UI New Terminal command cwd.
These do not prove GUI rendering. The extension API createTerminal default instead
uses the first folder; its two original failed checks are retained. When writing
extensions, provide an explicit cwd. UI New Terminal uses the workspace setting.

`VISUAL_UNVERIFIED`: no native Explorer/SCM/Test Explorer screenshot or click is
claimed. Locally open both views, check the8/19 named roots, Source Control's one
linked repo, a new terminal's `pwd`, Run Task checks, search for `GraphRepository`
and switch to full root/history. Browser Console acceptance is separate and uses
real isolated Chromium; it is not VSCode visual acceptance.

## Late local editor files

Two identical ROS `.vscode` files appeared in this new checkout during validation;
writer UNVERIFIED. They are preserved and ignored only by this checkout's root-local
`/.vscode/` rule. Role views omit root and do not inherit them; opening full root
may still apply these user settings. Shared Git excludes and previous trees were
not changed. This ignore rule is not a security or public release boundary.
