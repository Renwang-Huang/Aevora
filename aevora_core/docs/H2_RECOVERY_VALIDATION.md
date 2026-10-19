# H2-G0 RDB reliability subtask — actual validation

Verdict: **PASS for the declared RDB/checkpoint recovery scope**. AOF remains a
known failing path. These are newly executed H2 tests, not relabeled H1 results.
Full G0 security/rebuild and later H2 Gates are independently assessed by the
maintainer's root report.

## Current admitted-source commands and results

Archive: `aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9`. Final recovery artifact: `g0_recovery_admitted/`.

```sh
python3 -m scripts.aevora_h2_audit record "<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9" h2-g0-rdb-recovery-admitted \
  -- python3 scripts/aevora_h2_recovery.py run --archive "<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9" \
  --historical-archive "<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e" \
  --trial-label g0_recovery_admitted
python3 -m scripts.aevora_h2_audit record "<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9" h2-g0-admitted-closure-review \
  -- python3 aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/g0_recovery_admitted/derive_closure.py
```

Outer exit **0**, elapsed **30.591s**,
UTC 2026-10-11T08:51:13.631034+00:00 → 2026-10-11T08:51:44.221961+00:00.
`g0_recovery_admitted/commands/` retains **36 exact receipts** and matching
stdout/stderr hashes, including two expected exit-2 refusals and final cleanup.
`h2-g0-admitted-closure-review/command.json` newly checks these bytes, actual
JUnit identities, the source epoch, all graph states and cleanup; exit **0**.
The controller Gate is written before its final `finally` cleanup, so that Gate's
35 listed commands alone are not cleanup proof. Closure includes raw command 99
and an independently executed Docker inspection of all three stopped services.

| Probe | Newly executed result |
|---|---|
| Current checkpoint suites | **42/42 PASS**, unique identities, no failure/error/skip |
| Normal SAVE → stop → restart | Actual pinned server load; exact graph/constraints/paths match |
| Two independent cold restore volumes | **2/2**, real load and exact graph/constraints/paths match |
| Unsaved trusted historical feedback tail | 27 nodes/24 edges → 43/61 before crash |
| SIGKILL | Actual isolated Redis container exit **137** |
| Crash recovery | Returns to saved **27/24**, exact four historical evidence chains |
| Tail Outcome/Feedback | Actually absent after recovery; exact four lost IDs in Gate JSON |
| Re-ingestion twice | Actual trusted Outcome verification and exact idempotence; returns to same 43/61 |
| Corrupt backup | Exit **2**, no restore directory publication; approved original remains valid |
| Tail graph against old checkpoint | Exit **2**, actual divergence rejected |
| Fresh SDK connection query | Real Resolver and graph query; **not a Codex Session** |
| Cleanup | All three isolated services actually stopped; independent raw Docker state proof |

The 42 cases are the unchanged original 28 checkpoint tests, 4 additional real
subprocess FIFO/deep-JSON controls, and 10 explicit schema-value validation
controls (1 valid and 9 invalid). Schema-value controls do not simulate a
FalkorDB execution or database verdict. The full workflow separately validates
the actual SDK constraint set against its real graph before SAVE and after load.

## Security hardening and preserved earlier epochs

- `g0_recovery/`: first real complete workflow, **25/25 PASS**.
- `g0_recovery_final/`: complete permissions/read-window/schema-marker hardening
  workflow, **28/28 PASS**. Its pre-security delivery text is preserved as
  `g0_recovery_final/H2_RECOVERY_VALIDATION_PRE_SECURITY.md`.
- `g0_recovery_release/`: complete FIFO/deep-JSON hardened workflow,
  **32/32 PASS**, outer exit 0, elapsed 32.261s.
- `g0_recovery_admitted/`: final exact-schema hardened complete workflow,
  **42/42 PASS**. Earlier results and source epochs remain unchanged.

A real named FIFO exposed blocking before `fstat` in the earlier implementation:
`h2-g0-checkpoint-fifo-before` ran the preserved source in a subprocess, observed
one-second blocking and killed that child with exit **-9**. The additive
`...fifo-after` executed the hardened source, which rejected the same file with
classified exit **2** in approximately **0.056s**. Both collector outer exits are
0 because each checks its predeclared negative-control result. The current
42-case JUnit reruns both ordinary-read and manifest-read cases in bounded real
subprocesses. Deep JSON at depth 65 and decode recursion depth 2000 also receives
classified rejection, not an unhandled RecursionError.

An independent review identified that same-sized OPERATIONAL constraint lists
could contain a wrong label, property or duplicate. Current capture requires the
exact per-label UNIQUE `[id]` and MANDATORY `[id,payload_json,payload_sha256]` NODE
set; malformed/non-operational rows are rejected. It uses current schema LABELS,
not a fixed H1 label count. The new test file carries these additional controls;
the original 28-test source remains byte-identical at SHA256
`7d42b48ce6e1374d808b0bad0534d2ae579c0e8c4dd2a3893bc12291cfc18b8f`.

## Pins and source epoch

Checkpoint ID: `20261011T085121Z-60246ed0-e34f-4018-bc63-5154d470e665`.

- Approved manifest SHA256: `6abaee47cff8c6b0efea767fcf954bddece3142abaa657c93746e33bfbe5201c`
- Actual RDB SHA256: `f64e8e8db33e6f5db87e25c0b40dc322b2e04dcba2d89007577554fbe476b097`
- Saved/restored graph SHA256: `7e832bea8972915ec0878c95f7e676cf43debd8be3bc74bb35c00483d43cb1a9`
- Tail/re-ingested graph SHA256: `f3a4f28dc2a5ff9705593264dd219cd60914f59ed27349c6d21517fdb88c3857`
- Final JUnit SHA256: `5be26d5c58ecb1db513cd3f2f2daaf16ce3509e93b3afcb4810268e20bfd2f11`
- `RECOVERY_GATE.json` SHA256: `1e4aa8ef6c0fa6a80110828d46c4498025778cb31f85cc5035910b478482092f`
- Additive closure SHA256: `e029d5731830a596bd49e8056496e04f9480174a263cf799290b9f8c9890b43e`

`SOURCE_EPOCH.json` records nine real implementation/dependency hashes and
validates that bytes did not change during this workflow. The root source
freeze/Commit is separately archived; no historical Commit is invented here.

| New source | Admitted SHA256 |
|---|---|
| `aevora_core/src/aevora/checkpoint.py` | `9528422fe0a520b02575c976742b2c21165bca22ebed8035587fd0010fa47da9` |
| `aevora_core/scripts/aevora_checkpoint.py` | `75be834da0b72a084b66af7f6b1bba092a64691e1521fd82713e2ea6a31a180f` |
| `aevora_core/tests/test_checkpoint.py` | `7d42b48ce6e1374d808b0bad0534d2ae579c0e8c4dd2a3893bc12291cfc18b8f` |
| `aevora_core/tests/test_checkpoint_fifo.py` | `9cc83a85b5612fda11b2796f5f6d65aa1900006e6932c9af0d779f96aad80ab7` |
| `scripts/aevora_h2_recovery.py` | `fb1c8a40210942cab7d6e96c21ed1a5025ee947501f0042a641bd1e7175d60e7` |

## RPO and integrity boundaries

Last preserved explicit SAVE: **2026-10-11T08:51:25.511633+00:00**.
Tail injection began: **2026-10-11T08:51:25.536665+00:00**.
SIGKILL command began: **2026-10-11T08:51:29.349786+00:00**, **3.838s** after that SAVE.
This measured interval is not a configured RPO SLA. Every unsaved write can be
lost until another completed checkpoint. The actual new Outcome, completion
AuditEvent and two Feedback IDs were lost in this controlled crash; no zero loss
is claimed.

Only new Compose project `aevora-h2-recovery-67bc7fa7-f4ba8b`, independent volumes and loopback
ports 17680–17682 were write targets. H1 volume
`aevora-h1_aevora-experience-data` was not changed. Secrets are read-only trusted
mounts, not argv values or Participant inputs. Private binary backups are never
public task material.

The tail replay joins exact original sealed official MCP Query/Decision pins to
read-only H1 records, then verifies the sealed H1 Outcome through the existing
trusted bridge. It is **controlled historical replay**, not a new Agent challenge
or causal experience adoption. Attribution is **UNKNOWN**. Future source/schema
changes do not change this frozen run's original source epoch.

## AOF failure and preserved collector failures

`g0_aof_replay/retained-aof-isolated-replay/command.json` records a new isolated
read-only replay of preserved H1 AOF files, same image digest, network none,
no credentials and disposable tmpfs. Engine exit **139**; actual log reports
`signal: 11`, `GraphContext_GetSchemaByID` and `GRAPH.EFFECT`. Before/after source
AOF hashes match; live H1 container and original volume remain unchanged.

The first collector exit **1** and its original UNEXPECTED result are preserved:
it searched `signal 11` while actual Redis printed `signal: 11`. An additive
read-only `AOF_REPLAY_REVIEW_V2.json` with exit-0 collector rechecks raw hashes,
actual exit139 and crash observations without rewriting the initial failure.
An optional earlier cleanup inspection also returned **1** for a wrong container
name; its corrected lookup derives the name from the recorded actual project.
These collector failures remain archived and are not successful DB operations.

## Remaining limitations

- Controlled process crash and normal stop/load are demonstrated; power loss,
  disk-controller behavior and cross-host disaster recovery are **UNVERIFIED**.
- Writer quiescence is a maintainer precondition. Two equal observations are not
  an ABA-proof fence against a privileged administrator.
- Pin/header/hash checks do not parse every RDB module record. Real server load
  plus full graph/constraint/path equality is the dynamic semantic evidence.
- AOF still fails on the pinned engine; exact identity with upstream issue2201
  is **UNVERIFIED**. No AOF repair/engine upgrade is claimed.
- Matching schema/source versions are required; migrations need a separate Gate.
- A new SDK connection is not a new Codex Session; genuine Session proof is H2-G3.
- H2-G0 overall security/rebuild and later Gates are outside this subtask verdict.

Operational controls and researched primary references are in
[H2_CHECKPOINT_RECOVERY.md](H2_CHECKPOINT_RECOVERY.md).
