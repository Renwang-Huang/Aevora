# H2 independently pinned SQLite runtime

The G0 clean rebuild used the independently downloaded Freedesktop Platform
24.08.37, Python 3.12.14 / SQLite 3.46.1. Its exact result remains frozen.
Before the new lease scenario, an additional runtime was built without
modifying that deployment or historical evidence.

SQLite's documented WAL reset race affects simultaneous write/checkpoint
connections in releases through 3.51.2. The official 3.51.3 fix is pinned here;
an occurrence in the old OrderFlow runs is **UNVERIFIED**.
See [SQLite WAL reset description](https://www.sqlite.org/wal.html#walresetbug)
and [3.51.3 release record](https://www.sqlite.org/changes.html#version_3_51_3).
Lease authorization remains an application protocol; an engine upgrade is not
a proposed answer to the new business incident. The public task still supports
both DELETE and WAL and independent workers.

## Rebuild

```sh
python3 aevora_core/scripts/build_h2_sqlite_runtime.py \
  --runtime-root /absolute/newly-acquired-platform/files \
  --destination /absolute/absent/sqlite-3.51.3-runtime \
  --evidence-directory /absolute/absent/build-evidence
```

The script downloads the official release archive over verified TLS, checks
bounded ordinary archive members, checks the published SHA3-256 of `sqlite3.c`,
builds a shared library using gcc, copies the runtime into a new directory and
checks actual SQLite source ID/Python/pidfd capabilities inside bubblewrap.
The source runtime is not mutated; receipts preserve command argv, exits,
stdout/stderr and hashes. No cache is used as source authority. Prerequisites
are documented external tools, not a self-contained compiler image.

The new trusted launcher requires explicit inputs:

```sh
AEVORA_H2_RUNTIME=/absolute/sqlite-3.51.3-runtime \
AEVORA_FALKORDB_PORT=17679 AEVORA_FALKORDB_GRAPH=aevora_h2_g0 \
AEVORA_FALKORDB_PASSWORD_FILE=/external/owner-only/falkordb.password \
scripts/aevora-h2-python -m pytest -q
```

Model-enabled runs additionally use `ORDERFLOW_ENABLE_CODEX=1`. The upstream
key is mounted only in the trusted maintainer namespace. Participant and
candidate commands retain their separate existing sandbox construction;
their file/network boundaries must be dynamically rechecked after any runtime
change. The launcher refuses the H1 DB endpoint and unsafe credential file
types/permissions. It has no personal `.runtime.env` fallback.

## Measured build, without business credit

H2 build command exit **0**, 32.414 seconds. Actual SQLite is **3.51.3**, source
ID `2026-03-13 10:38:09 737ae4a34738ffa0c3ff7f9bb18df914dd1cad163f28fd6b6e114a344fe6d618`.
Official `sqlite3.c` SHA3-256 is
`32d5424f97e0a7fc5ed2f6335afbb58be4e0298bd7117a34e39d345ff13d859e`;
built library SHA256 is
`5b15d6a13dd6b2c474611c12ff73b20ed820178a6513e94a320463517a475b37`.
These capabilities are not business or model test results. Nine new launcher
refusal contracts passed after correcting a missing standard `/bin` symlink;
the initial nine failures remain archived. A first capability collector's
constant Participant-visibility annotation is explicitly discarded as
nonmeasurement; v2 records only actual runtime fields.

The base Platform branch remains **EOL**. This narrowly fixes a known SQLite
engine risk; it does not establish full runtime security maintenance or
third-party signed build provenance. Existing A/D-v01 assertions and hidden
Oracle bytes have not been altered. Subsequent Gate reports must identify
their actual runtime/library fingerprint and newly executed regressions.
