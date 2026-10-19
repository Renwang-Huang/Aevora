# Aevora Gen 1.5.1 Validation Report

## Conclusion: CONDITIONAL PASS

G0/G1 source/debt plan PASS; G2 native functional workspace checks PASS with
`VISUAL_UNVERIFIED`; G3 PASS (`NO_SAFE_STRUCTURAL_MIGRATION`); G4 behavior/release
contracts PASS; G5 local handoff qualifies inherited platform/security limits.
This hygiene task introduces no Gen2 feature and makes no new model/causal claim.
The qualification is explicit visual/Test Explorer non-attestation plus inherited
runtime/security limits, not a failed1836-test or Oracle result.

Full evidence: `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5_1_evidence/Gen1.5.1-20261013T162319Z-ef51c9fa-f047-4bd1-ac6d-c602b237761f`. The maintainer review ZIP, final Commit/Tree, manifest/ZIP
SHA and independent member verification are in sibling `Gen1.5.1-20261013T162319Z-ef51c9fa-f047-4bd1-ac6d-c602b237761f-delivery/`.
The Full seal is terminal; final export receipts never write into it.

## Source identity and protected trees

Baseline Commit `47bd9101126f5b5fb8d8dc7cec88f0dfe3712c93`, Tree
`b6d6e4aa2552a2fd6e999e4fa7310ac3e440a63d`. G3 validated Commit
`27d97e02fac1671342c75fa626064a5da20d6477`, Tree `9d848bc728707cc368ee682b93d8185963c3cc44`. Final report/handoff additions are pinned
separately with runtime-byte equality in the delivery receipt; they are not
retrospectively attributed to the test start. New branch `aevora-gen1-5-1-workspace-20261014`,
worktree `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5_1`. Both prior HEAD/Tree/index/status and all2061 selected tracked/
untracked source/user files match the G0 snapshots (1527 original +534 Gen1.5).
Gen1.5's preexisting untracked `.vscode/` remains; clean is required only for the
new source handoff. Shared Git worktree registration/new refs are authorized;
protected original indexes and checkouts did not change.

Of532 inherited tracked files,528 are byte-identical. Only README/DEVELOPMENT/
AGENTS current navigation and the new root-local `.gitignore` environment rule change. All86 inherited test source files and39
private truth files are byte-identical; app/Benchmark/Evaluator/Core/Console/
Gateway/phase adapters/Reference retain their prior bytes. Moves0/deletions0.
320 named historical seal/delivery files, Gen1.5 Full manifest and Lite ZIP were
actually rehashed. This iteration **did not rehash236011 historical payloads**;
that number belongs to the prior sealed receipt. New namespace mount targets
are empty ordinary directories outside validation; original archives stay put.

## Actual regression and integration

- First current full:1836 PASS, exit0,189.85s; retained as preliminary validation.
- Final G3-source full:1836 PASS, exit0,189.92s;
 1820/1820 inherited identities present,16 new identities,0 failed/error/skip,
 no duplicates. Runtime source epoch unchanged. JUnit SHA256:
 `19146a8b3a5fedd58b68c268dbde46d5a25eb769d0cee932b073070cd3ef3032`.
- Two actual upstream warnings: Starlette TestClient httpx deprecation and the
 SDK/Pydantic settings unresolved forward reference. Assertions unchanged.
- Node locked install/build and actual public state tests pass; no old generated
 static/verifier byte drift. Canonical-source `--check` passes.
- Clean Core-only independent venv:10 real onboarding/official MCP SDK checks,
 four scoped tools; actual untrusted proposal, denied Host publish, zero
 VerifiedOutcome/SourceVerification and grant/socket cleanup. No Benchmark import.
- Real FalkorDB4.20.4 pinned image in new bounded tmpfs container, owned17702,
 fresh external0700/0600 secret; no named/historical volume operation. Actual
 verified M1 history imported as declared control corpus, not new model evidence.
- Public114 source files,2 wheels/2 sdists, deterministic ZIP
 SHA `53b825e505f654434914e659e140b12ca001198fb1a58cc9ce5a4e04e5b04aab` (460344bytes), exactly
 byte-identical selected sources/ZIP to Gen1.5. Existing builder's gen15 ZIP name
 retained. New workspace/private checker/docs are excluded by public allowlist.
- Actual source/archive members/Docker layers inspected: private-path/exact-copy
 matches0 and known secret/individual secret hash matches0. Public image built
 from fresh allowed context (cache use is recorded), ID
 `sha256:2f94763c7b78653059eb811e678f2d6bc9281fdab4cd5c9ea4e76b3247c9e12b`.
- Actual isolated Chromium17 checks against owned graph and initialized empty
 graph; no mocked routes. Three-page click/navigation/Live/Replay checks pass.
 Separate real disconnected endpoint: LIVE503/fallbackfalse, explicit REPLAY200.
- Actual physical outer/native-command/candidate boundaries and channel cleanup:
 six checks PASS, **overall_security PARTIAL**. No authenticated model session.

Actual runtime: Python3.12.14, SQLite3.51.3, pytest9.1.1, FalkorDB SDK1.7.1,
MCP SDK1.26.0, Core/Console0.1.0, OrderFlow0.3.0; exact module origins point to
this worktree. Host VSCode1.141.0; Node24.15.0/npm11.12.1. Codex0.162.1 version/
features inventoried only. No paid challenge or remote push.

### 15 inherited CLI contracts (candidate verdict ≠ harness verdict)

| Command case | Exit | Actual status | Passed/Failed | New Run ID |
|---|---:|---|---|---|
| validate-d | 0 | IMPLEMENTED | None/None | None |
| prepare-d | 0 | PREPARED | None/None | d698b6ef-6c60-4184-bbc2-388238064569 |
| report-prepared | 0 | PREPARED | None/None | d698b6ef-6c60-4184-bbc2-388238064569 |
| reset-d | 0 | RESET | None/None | None |
| smoke-buggy | 1 | FAIL | 0/8 | ca266c12-75d5-4adf-a687-34770fbee49e |
| smoke-reference | 0 | PASS | 8/0 | bb27ae57-0cc3-4cb4-a85b-13d4c3a2ebf3 |
| a-buggy | 1 | FAIL | 5/9 | cc7ad838-889c-4bbe-a101-4378e6d3dff2 |
| a-reference | 0 | PASS | 14/0 | 4aa4d183-dbbf-4e91-adbe-02da34f91811 |
| d-buggy | 1 | FAIL | 14/14 | 38854d0d-a4d8-4698-9202-7e6f870257cb |
| d-reference | 0 | PASS | 28/0 | 1ef2106a-b2a7-4e03-85e4-3bdde7833ccb |
| d-flock-alternative | 0 | PASS | 28/0 | 6013b36a-5b44-49c6-b48f-dfe06af63083 |
| b-planned | 4 | NOT_IMPLEMENTED | None/None | 059dd955-1f7e-497a-8632-fbb189b8e958 |
| c-planned | 4 | NOT_IMPLEMENTED | None/None | 3dd17122-89fc-42ce-b412-366f2a189cab |
| invalid-submission | 2 | ERROR | None/None | f0aa3294-c920-4b1e-a24e-d08b371f8e4c |
| evaluation-timeout | 3 | TIMEOUT | 0/0 | d5010769-611b-4bd7-ab0d-be2e562e9efa |

All15 checks match required exits/statuses, reset/report and submission fidelity.
Expected buggy FAIL, invalid ERROR/2, timeout TIMEOUT/3 and B/C
NOT_IMPLEMENTED/4 are genuine outcomes; they are never relabelled successful tasks.

### D-v02 unchanged independent36-case Oracle

| Strategy | Result | Pytest exit | Passed/Failed | New Run ID | Recovery |
|---|---|---:|---|---|---|
| buggy | FAIL | 1 | 28/8 | b9afb4e6-f11d-4be1-81f0-2552474d8f72 | COMPLETE |
| reference | PASS | 0 | 36/0 | 9cf23cb8-50bb-4905-967a-ab7d38fdb2b1 | COMPLETE |

Both source epochs unchanged; reset COMPLETE. No new scenario or weakened oracle.

## Workspace user acceptance

Product8 roots / Maintainer19 relative roots. Official VSCode Extension Host
loaded actual folder sets; builtin Git API discovered one correct parent linked
worktree; actual findFiles search scopes matched; three process tasks exited0;
UI `workbench.action.terminal.new` writes the actual repo-root pwd. Dedicated
empty test profiles isolate editor state; third-party extensions disabled, no
personal profile reused. Their local test-profile Workspace Trust setting permits
our explicitly trusted source tests; it is not a Participant permission change
or distributed workspace setting. Regular users still choose trust locally.
Explorer layout/screenshots and Python extension Test Explorer remain
`VISUAL_UNVERIFIED`; a reproducible manual checklist is in WORKSPACE.md. Browser
Console evidence does not substitute for VSCode visual evidence.

G2 supplemental native probes overlapped preliminary G3/G4 validation. After the
terminal distinction was resolved, the final G3 slice was frozen and the formal
final G4 suite/CLI/Oracle/security completed; timestamps retain that chronology.
No earlier failed probe is retrospectively marked PASS.

## Failures retained and classification

1. Two first native Extension Host checks: direct extension API createTerminal()
 used first Core folder, so the repository-root assertion failed. Wrapper CLI
 exit0 does **not** override their FAIL JSON. Raw FAILURE/SCM/search/tasks/pwd and
 both original profiles remain. Corrected collector uses the real user's UI New
 Terminal command, and both actual runs pass. Workspace source setting unchanged;
 documentation explicitly records the API default distinction.
2. Physical collector first exit1: nonexistent `scripts.aevora_h2_common` import,
 before any probe. Original stdout/stderr/argv retained. Correct existing
 `scripts.aevora_h2_security.Evidence/physical_probes/finish` runs six checks PASS.
 No runtime/security assertion was changed.
3. Read-only exploratory path lookups failed at incorrect cwd/file names; task
 or source was not altered. Their tool-transcript excerpts are listed in
 `g0/DIAGNOSTIC_FAILURES.json`; missing original timestamps are UNAVAILABLE.
4. First G5 final commit succeeded, but normal clean-status assertion failed: two
 untracked ROS `.vscode` files appeared at16:50:59UTC. Their bytes exactly match
 protected Gen1.5 local files; writer identity UNVERIFIED. Preserve them. A dated
 G1 addendum adds only `/.vscode/` to this new worktree ignore file, not shared Git
 excludes or old roots. Initial FAIL receipt retained; new tests/build and final
 status follow separately. Role views omit root so they do not inherit these
 settings. This is environment classification, not security or source deletion.
5. Sealed-output negative control intentionally exits1 with the immutable-archive
 rejection and no created output. Actual old seal SHA remains equal. CLI expected
 FAIL/ERROR/TIMEOUT statuses above are required negative evidence, not discarded.

## Actual commands and raw receipts

Every row links an exact argv/cwd/UTC start/end/exit and stdout/stderr SHA receipt.
Trusted bwrap prefix/clearenv/readonly original archives, writable only new source/
evidence and explicit owned credentials are included in raw argv. Examples of
actual interpreter payloads (prefix in receipt):

```sh
.venv/bin/python tools/dev.py test-maintainer --output <Full>/g4/final-full-regression --owned-port 17702
.venv/bin/python tools/dev.py benchmark-check --output <Full>/g4/cli-regression
.venv/bin/python tools/dev.py dv02-check --output <Full>/g4/dv02-regression
.venv/bin/python tools/dev.py public-build --output <Full>/g4/public-product
npm --prefix console ci
npm --prefix console run build
npm --prefix console test
```

For literal absolute argv, read `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5_1_evidence/Gen1.5.1-20261013T162319Z-ef51c9fa-f047-4bd1-ac6d-c602b237761f/g4/COMMAND_INDEX.json`. The history is
read-only for trusted validators; Participant retains its smaller physical fence.
Fresh outputs are required for any replay, not the sealed directories above.

| Actual command label | Exit | Elapsed | Full raw receipt |
|---|---:|---:|---|
| `g2-fresh-dependency-install` | 0 | 81.26s | `commands/g2-fresh-dependency-install/command.json` |
| `g2-additive-workspace-tests` | 0 | 0.51s | `commands/g2-additive-workspace-tests/command.json` |
| `g3-console-build` | 0 | 0.24s | `commands/g3-console-build/command.json` |
| `g3-console-public-tests` | 0 | 0.22s | `commands/g3-console-public-tests/command.json` |
| `g4-full-current-regression` | 0 | 189.85s | `commands/g4-full-current-regression/command.json` |
| `g4-final-source-full-regression` | 0 | 189.92s | `commands/g4-final-source-full-regression/command.json` |
| `g4-inherited-cli-contracts` | 0 | 174.64s | `commands/g4-inherited-cli-contracts/command.json` |
| `g4-dv02-independent-oracle` | 0 | 70.07s | `commands/g4-dv02-independent-oracle/command.json` |
| `g4-clean-public-install-official-sdk` | 0 | 69.04s | `commands/g4-clean-public-install-official-sdk/command.json` |
| `g4-public-build` | 0 | 0.98s | `commands/g4-public-build/command.json` |
| `g4-source-distribution-image-private-secret-scan` | 0 | 0.99s | `commands/g4-source-distribution-image-private-secret-scan/command.json` |
| `g4-actual-chromium-three-page-image-contract` | 0 | 14.25s | `commands/g4-actual-chromium-three-page-image-contract/command.json` |
| `g4-real-physical-participant-boundaries` | 1 | 0.07s | `commands/g4-real-physical-participant-boundaries/command.json` |
| `g4-real-physical-boundaries-corrected-collector` | 0 | 1.19s | `commands/g4-real-physical-boundaries-corrected-collector/command.json` |
| `g4-actual-disconnected-live-no-fallback` | 0 | 1.13s | `commands/g4-actual-disconnected-live-no-fallback/command.json` |
| `g4-real-sealed-output-refusal` | 1 | 0.07s | `commands/g4-real-sealed-output-refusal/command.json` |

## Remaining limitations / stop

Inherited AOF reload139, native D-v02 UDS EPERM, shared Linux kernel/EOL, RDB unsaved
crash-tail RPO, oversized UDS BrokenPipe/413 close-send race, actual authenticated
Codex0.162.1 model compatibility and adoption/causal benefit UNKNOWN remain. Two
passing full suites do not prove the sporadic Gateway race fixed. Tmpfs validation
is not durable-storage/cold-restart certification. Local hashes/pins are not
independent cryptographic attestation. Static SCC/lazy dependencies and ambiguous
phase callers remain review candidates. Visual/Test Explorer not verified.
Stop at Gen1.5.1. No remote publication, database-volume migration, new core/
Benchmark functionality, Gen2 or extra model trial occurred.

## G5 final addendum acceptance

The dated local-environment ignore addendum was actually checked:34/34 Gen15 +
Gen151 development contracts PASS,0skip/error/failure; fresh public build ZIP
SHA unchanged. All final regression runtime-epoch files still byte-match.
Protected old tree/status/index/source hashes remain equal. The new tmpfs DB
is actually stopped (exit0), with no named volume mounted/operated. New source
worktree is clean with local editor files preserved/ignored. Final Commit/Tree,
Full seal/member verification and Audit-Lite hashes are in the outside-Full
delivery receipt. Source/Git identity changes reflect docs and local ignore only.
