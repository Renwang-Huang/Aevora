# Aevora G22 implementation and acceptance

Current functional conclusion: **G22_PASS in declared bounded contracts**, pending terminal Full/Lite seal/verification. Final delivery receipt controls final status; a pending seal is not a completed delivery.

Base387352df3d5358d5f0ed8eadc784ef7170843ee0 / e0b2bd2cea3ec42b0396b9cf3370fc2ec0f1453b.
Tested implementation checkpoint `6c2893f2f589aea236dfcecbbf25a61af20f9cfc`. Owned run `G22-20261015T174846Z-88fad40ffd`.

| Gate | Current evidence |
|---|---|
| G22-0 | independent bare object store/worktree, original clean roots,547 hashes and G21Full unchanged |
| G22-1 | true pinned source/outcome+explicit semantic review; fresh reference14/14 and genuine buggyFAIL |
| G22-2 | immutable prepared data, typed/endpoint/chunk/full-scope CAS, one final query,2/4/8writer one winner, idempotence and process kill |
| G22-3 | real graph revision/conflict/restriction/withdrawal, immutable history and scoped verifier retirement |
| G22-4 | current capability/scope/profile/time/generation; real officialSDK denial before send, grants reissued, saved cold recovery |
| G22-5 | observed64×8 p95 2.970855s; actual100k/300k with2048experiences and full read/write checks |
| G22-6 |2005/2005 exact inherited identities;58/58 new;86/86 design;17 clean product checks; CLI=PASS |
| G22-7 | source reports/diff/matrices plus terminal Full/Lite verification required |

## Actual command entry examples (executed paths are in per-command receipts)

```sh
python3 -B <E>/runtime.py --history inherited-1897-final -- tools/dev.py test-maintainer --output <E>/06_regression/inherited-1897-final --owned-port 17741 -- -q tests aevora_core/tests --ignore=aevora_core/tests/gen2 --ignore=aevora_core/tests/g22 -p no:cacheprovider
python3 -B <E>/runtime.py --history gen2-108-acceptance -- tools/dev.py test-graph-v2 --output <E>/06_regression/gen2-108-acceptance --owned-port 17741
python3 -B <E>/runtime.py fresh-host-case-entry -- tools/dev.py host-case-generate --output <E>/01_admission/final-cases
python3 -B <E>/runtime.py acceptance-host-58 -- <E>/g22_raw_runner.py --output <E>/06_regression/acceptance-host-58 --owned-port 17741 -- -q aevora_core/tests/g22 -p no:cacheprovider
```

The examples abbreviate `<E>` only for reading; `commands/*/receipt.json` contains exact argv, exit, times and stdout/stderr hashes, including `--owned-port 17741` as separate arguments. JUnit identities are compared from unredacted Full, not potentially renamed Lite strings.

## Real failures retained

Constructor/immutable timestamp clashes; a test harness expecting isError instead of actual transportEOF; byte/string EOF mismatch;3 critical red projection/type/scope counterexamples; large-graph reverse full scan; first scale generator source-argument conflict; symlink-following copied-venv setup error; and original unsaved-stage outage recoveryERROR. None is deleted or relabelled as its later retry. First two early prototype file bytes were not snapshotted before the first checkpoint: exact source bytes are UNAVAILABLE there, while original JUnit/command errors survive. Critical fence counterexamples include exact before-source copies and failing graph snapshots.

## Limits and stop

No new model/Agent challenge, no natural-agent score, no causal benefit proof. Native-v2 positive source path requires G23; v1 verifier source is reused and fake-v2 origin rejection is tested. OS-rooted trust is not malicious-maintainer resistance or external attestation. RDB lastSAVE RPO/AOF139, shared-kernelPARTIAL, ClockUDS prior limitation and cross DB/network authorization interval remain. Numeric capacity bounds and large prepared-document/write costs are explicit. Do not treat test count, reference PASS or this bounded scale fixture as universal production assurance.

No private Oracle/reference/business/Runner changes; no push, merge, cleanup or G23. See protocol, governance, scale, source map, failure ledger and evidence matrix for exact claims.

## Product repeat build

First two wheel files differed only in ZIP timestamps; all member payloads were identical. The failure is retained in BUILD_REPEAT_INITIAL.json. Two further builds used the standard SOURCE_DATE_EPOCH from the actual implementation commit timestamp: source ZIP and both wheels match byte-for-byte (BUILD_REPEAT_FINAL.json). No source timestamp, Git date, historic evidence or score was rewritten. The clean17-check install tested the same exact wheel member bytes in an isolated product-only namespace.
