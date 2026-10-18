# Aevora H2 RDB checkpoint and recovery

This is a maintainer operation. The graph credential, binary RDB, private
checkpoint and historical Outcome archive are never Participant inputs. Aevora
uses the actual FalkorDB/Redis RDB file; JSON inventories are verification data.

## Consistency boundary

Stop trusted graph writers before `SAVE` and keep them stopped until publication.
The trusted CLI captures actual node/edge identities and payload SHA256 values,
independently verifies payload bytes, checks the complete actual constraint set, and queries
all public premise and evidence paths. It performs synchronous Redis `SAVE` and
compares the graph before and after. The host copies the Redis-produced RDB, then
the CLI re-reads the actual graph and compares it to the SAVE boundary before
publishing. The supplied SAVE receipt is pinned by SHA256.

This is a maintenance window, not an online multi-statement transaction. Equal
before/after observations do not detect an administrator's write-and-revert
between observations. The caller must control all authorized writers. This
operation snapshots the server's Redis database, so an isolated server is the
default test target; graph inventory covers the specified Aevora graph.

The actual SDK rows must be NODE/OPERATIONAL and contain exactly one UNIQUE
`[id]` and one MANDATORY `[id,payload_json,payload_sha256]` for every label in
the current source epoch's schema. Duplicate, unexpected, wrongly targeted or
malformed constraints are rejected even when their total count is correct.
Property order does not change constraint semantics. A snapshot does not repair
constraints by calling `initialize()`; an invalid existing graph is refused.

Each checkpoint has a timestamp/UUID, image digest, schema/query version, actual
Redis version and SAVE boundary, node/edge/path inventory, RDB byte count and
SHA256. Files are mode 0600 in a mode-0700 directory. A staging directory is
fsynced, renamed into the private backup directory and the parent is fsynced.
The Redis-generated RDB is never modified in place by this tooling.

## Cold restore

An approved manifest SHA256 is mandatory. Verification refuses corrupt bytes,
unsupported versions, changed inventory digest, duplicate JSON keys, symlink or
hard-linked inputs, unexpected files and non-private directories. The staging
API creates a **new** mode-0700 directory and cannot overwrite an existing target.
It opens nonblocking before checking file type, so named pipes cannot hang
before `fstat`. Input reads are bounded; JSON depth is limited to 64 and traversed
values to 500000, with decode recursion failures classified as rejection.
Header/hash validation is not an
RDB semantic loader: the actual pinned server must subsequently load the file.

The host deployment controller independently inspects a stopped target and its
new isolated volume, installs the checked RDB only into that empty volume,
starts the actual server, then checks all nodes, edges, constraints and public
paths against the checkpoint. Repeated restore means a second fresh target,
not overwriting a live database. The API's `server_stopped` flag is a caller
precondition; the dynamic controller records actual Docker state/mount proof.

## Executable H2-G0 probe

Run from the repository root, using a **new** H2 archive. The script exclusively
creates its own Compose project, volumes and loopback ports 17680–17682. It uses
the H1 pinned image digest, administrator secret files mounted read-only by
Docker and the existing trusted Python launcher. Passwords never enter argv,
reports or the Participant environment. All commands, output, timestamps,
exit codes and SHA256 values are retained.

```sh
python3 -m scripts.aevora_h2_audit record "$h2_archive" h2-g0-recovery \
  -- python3 scripts/aevora_h2_recovery.py run --archive "$h2_archive" \
  --historical-archive m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e
```

The probe imports four already byte-verified historical applicability chains.
For the unsaved tail it joins original sealed official MCP Query/Decision
result digests to read-only H1 graph records, copies those **unchanged** exposures
into the isolated graph, and re-verifies/ingests the actual sealed H1 Outcome
through the trusted bridge. This is a controlled historical feedback replay,
not a new model Session or new Benchmark score. Feedback remains
`outcome_observed_no_attribution`, attribution `UNKNOWN`.

The server disables automatic SAVE and AOF for the controlled experiment. After
an explicit checkpoint it adds the real verified feedback without SAVE, records
the diverging actual graph, kills only its isolated primary with SIGKILL,
restarts and proves that the unsaved Outcome/Feedback tail is absent while the
saved chains remain. It exercises normal SAVE/restart, two cold restores,
corrupt backup rejection with no publication, repeated Outcome idempotence and
a separate SDK connection's real query. **An SDK connection is not a Codex
Session**; the task's different genuine Session validation belongs to H2-G3.

## RPO and remaining limits

RPO is the completed explicit SAVE. Every later write may be lost until the
next completed checkpoint; the controlled tail loss demonstrates that risk.
Report the actual SAVE/injection/kill timestamps and IDs lost. This is a local
process crash test, not power failure, disk controller durability, cross-host
disaster recovery, zero-data-loss or externally signed origin proof.

The known AOF replay issue is investigated separately on a read-only mount of
the preserved H1 volume, copied into disposable tmpfs with no network or
credential mount. Original files and the live H1 container remain untouched.
No AOF repair or engine upgrade is claimed by selecting the verified RDB path.
The reproduction keeps the failing exit code and raw stack; fixing AOF does
not indefinitely block the remaining H2 work.

## Mature implementation references

- [Redis persistence](https://redis.io/docs/latest/management/persistence/):
  RDB snapshot boundary, atomic replacement and loss of unsaved tail data.
- [Redis SAVE](https://redis.io/docs/latest/commands/save/): synchronous save.
- [FalkorDB Docker persistence](https://docs.falkordb.com/operations/durability/persistence):
  persistent volume and actual restart/query validation.
- [FalkorDB issue 2201](https://github.com/FalkorDB/FalkorDB/issues/2201):
  upstream reports GRAPH.EFFECT replay crashes. Similarity does not prove the
  precise root cause of the preserved local H1 data.

This code uses supported SAVE/RDB behavior of the installed version; it does
not assume newer Redis BACKUP/preload APIs exist in the pinned image.
