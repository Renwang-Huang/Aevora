# Aevora H3 — baseline and implementation boundary

## Actual starting evidence

Read-only baseline capture exited **0**, 101.607824 seconds, on 2026-10-12.
Its receipt is in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/baseline-capture/command.json`.
The collector re-read **195,885 protected historical files**, verified the
**331** H2 final-release source files, and copied **332** current source files
(the additional file is the new H3 task specification). It retained the dirty
root Git status and binary diff without staging the user's working tree.

| Epoch | Actual identity / qualification |
|---|---|
| Original root HEAD | `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`; dirty branch `aevora-h2-governance-20261011` |
| H2 model challenges | `6a8e3d7831c27acb27703a7dba0a5d47d90fdbe0`; two new Runs, each 36 hidden PASS, three verified children |
| H2 final delivery source | `81ab7edd53c0308e072231a6983f501970198c99`; export fix, 1655 historical tests; no new model challenge at this epoch |
| H2 original Full manifest | `243df294b70fd41b595752906a8d68196deeebf782a16c1eeddf59de28df967d` |
| H2 post-seal companion manifest | `5776a0a335be4f4aa3b99a8dbbc3a69aeb0be8e73e72d0805c88172eec773ed1` |
| H2 main Audit-Lite | `2f2bc3af1ac85ac8a094e31c8d685f007ad9b9b5622e75080a62bca00a1d8f1c`; original G0–G3 epoch, companion required for export fix |

These are historical results, **not H3 regression results**. The captured
1655 JUnit identities and original test source hashes are independent H3
regression requirements. Old business, hidden suites, Oracle and reference
patch hashes are additionally frozen. Neither Full archive is writable by H3.

## Reuse and actual gaps

| Existing module | H3 use | Actual gap / narrow extension |
|---|---|---|
| `GraphRepository`, canonical immutable records and real constraints | Remain the FalkorDB authority | Candidate and append-only review history, atomic state transition fence |
| H2 Rule revisions, governance events, QuerySnapshot | Preserve WHEN/WHY and immutable replay | Newly formed Experience must stay invisible until Host publication completes |
| `ExperienceService`, official MCP SDK, scoped broker/proxy | Existing three tools remain compatible | Optional untrusted proposal tool; no privileged publish tool |
| Outcome bridge and feedback | Retain independently verified outcomes and UNKNOWN attribution | Thin source binding for Candidate review; external results remain unverified |
| Official native CLI, isolated model broker, completion-aware resources | Reuse actual Runtime, no new orchestrator | Standalone Core connection and independent ordinary-project pilot |
| RDB checkpoint, bounded secret reads, real Cypher journal | Reuse safe deployment/evidence primitives | H3 lifecycle catalog and controlled fresh volume recovery |
| Full/Lite independent verifier | Reuse content hashes and fail-closed verification | H3 public export selection, candidate timeline and provenance view |

Current source inspection confirms that the root distribution explicitly
includes `evaluator/private_manifests`, `private_labels`, reference diffs and
Evaluator Python. This is **MAINTAINER_ONLY** material and needs an explicit
build boundary. The independent `aevora-core` package is the ordinary-user
distribution. The root and Core READMEs still describe H1/M1.1 and incorrectly
leave D-v02 unimplemented; only current guides will be updated.

The original six D-v02 public tests create a local AF_UNIX Clock listener.
H2 native command execution returns EPERM on bind. G0 will reproduce the
permission difference and preserve this original result. An in-process local
Clock entry can exercise the identical six business assertions without adding
network/IPC capabilities; it cannot claim to validate the UDS transport.

## Live environment and limitations

At baseline, official Codex is **0.162.1**. H1 and H2 FalkorDB containers are
healthy on loopback 16379 and 17679. H3 will use its own credential directory,
graph, port and volume; it will not restart/delete historical services.
Credentials stay outside source/evidence, and their values and hashes are
never reported. The reusable Python runtime is 3.12.14 with SQLite 3.51.3;
its Flatpak 24.08 base is EOL. An upgrade needs fresh sandbox and full regression
qualification; H3 does not claim that an upgrade has already occurred.

AOF exit139 is retained and out of scope. RDB recovery guarantees only a
completed SAVE/checkpoint, not unsaved-tail durability. Shared-kernel hostile
isolation, model prompt-injection immunity, underlying model weights, billing
and causal benefit remain PARTIAL/UNVERIFIED. Proposed text is data, not
authority. PASS of an engineering submission does not prove strategy benefit.

## Execution sequence

1. **G0:** reproduce native compatibility and distribution exposure; provide
   safe boundaries, clean install/query and inherited Episode regressions.
2. **G1:** add the minimal Candidate→Host review→bounded publication lifecycle;
   run actual FalkorDB positive/negative/race/recovery tests and a fresh native
   proposal; verify independent source before publication.
3. **G2:** connect a version-controlled non-OrderFlow Python project in a new
   native Session; keep external observations explicitly unverified.
4. **G3:** real graph interventions and finite honest Raw Memory comparison;
   retain every attempt and distinguish recommendations from task outcomes.
5. **G4:** reproducible read-only demo/verify, provenance timeline, Full/Lite,
   deterministic export/tamper rejection and current complete regression.

Every Gate gets a separate source epoch, command receipts, original failures
and verdict. Completion-aware model execution retains finite per-connection
and resource bounds and operator cancellation. Stop at H3; no H4/B/C or large
formal randomized study.
