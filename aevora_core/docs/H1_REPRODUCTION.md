# Aevora H1 — Same-host reproduction and read-only review

OrderFlow Incident Lab is the independent Benchmark. Aevora supplies experience
evidence through real FalkorDB and official MCP; native Codex owns delegation.
This document is maintainer material and must never enter a Participant package.

## Review the completed chain without another model call

The completed H1 archive is identified by `aevora_validation/CURRENT`. Obtain
its approved `CLOSURE_INDEX_V2.json` SHA through a trusted channel, then:

```sh
scripts/aevora-python scripts/aevora_demo.py verify-existing \
  --archive aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288 \
  --index-reference CLOSURE_INDEX_V2.json \
  --index-sha256 82631e9fa7f2ab03dba4b4b99be58d2258fd44182aa4312b4822782db55295c7
```

This command rechecks pinned source bytes, full Run seals, necessary independent
JUnit/Oracle/patch-derived outcome, trusted ingestion, SAVE/stop/up provenance,
exact persisted graph paths and typed new-Session visibility. It performs no
model call, database query, candidate execution or source mutation. The index
pin is local maintainer authority, not an external execution attestation.
Earlier V1 index/review failures remain in the archive.

## Plan a fresh demonstration

Use a new UTC/UUID directory and an authenticated dedicated RDB-mode graph.
Never reuse an old Run, Session, graph namespace or frozen Gate as a fresh result.
`plan` prints existing commands and unresolved approval parameters:

```sh
scripts/aevora-python scripts/aevora_demo.py plan \
  --archive aevora_validation/<new-UTC-UUID> \
  --historical-archive m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e
```

Read the emitted preconditions. Independently import verified history, run G2
graph ablations and G3 isolation/regression, and publish actually reviewed Gates
for that namespace. Freeze current sources **before** model execution. Pass
explicit `--gate-file` paths matching the newly published Gates; default plan
paths are templates and do not manufacture those files.

The live entry reuses the existing collector only:

```sh
ORDERFLOW_ENABLE_CODEX=1 scripts/aevora-python scripts/aevora_demo.py run \
  --archive <fresh-admission-directory> --authority-root <fresh-Full-root> \
  --gate-sha256 <approved-LIVE_GATE-sha256> --trial <new-unique-label> \
  --authorize-live
```

The outer trusted launcher requires `ORDERFLOW_ENABLE_CODEX=1` for the real
collector and host-only upstream credential injection. It clears that flag
inside the environment. There, the demo verifies the actual Python 3.12,
maintainer mounts and executable official tools, then calls the existing
collector with `sys.executable`; it never nests another launcher. Missing
capabilities are rejected before any model call. From a normal host process,
the demo uses one launcher invocation. Participant gets a scoped Run channel, never the
long-lived project credential. New model requests use `gpt-5.6-terra/max` and
completion-aware `None` total timeout/budget; connection, idle, retries,
concurrency, message and physical resource limits and manual cancel remain.
No fallback model/effort or unisolated execution is authorized.

## Trusted feedback and independent observation

After the fresh native session closes, inspect its actual Runtime, Submission,
Evaluation and Isolation statuses separately. Approve the exact sealed Run and
pre-live source manifest pins, then use
`aevora_core/scripts/ingest_orderflow_outcome.py --help` for the strict host CLI.
Caller-supplied verdicts do not create VerifiedOutcome. Observed feedback retains
`UNKNOWN` attribution and does not turn a final PASS into causal support.

Explicitly SAVE through the authenticated host SDK, stop and restart the
FalkorDB service, and record before/after full fingerprints and public paths.
The original H1 probe and exact commands are archived; keep their source SHA,
stdout/stderr SHA and aware timestamps. AOF is disabled because its retained
replay genuinely crashes; unsaved crash-tail/power-loss recovery is UNVERIFIED.

Use `scripts/aevora_new_session_probe.py <fresh-admission-directory>` through
the trusted Codex launcher to create a **different** fresh read-only Session.
It receives no new Outcome ID hint, queries the returned experience candidates
and bundles, and makes no business submission. The existing repair Adapter
classifies no patch as ERROR/NO_PATCH; preserve that original result. Official
completed tool/Turn and unchanged source prove the observation separately.

Seal both stopped Runs and recheck native raw references using
`scripts/aevora_trace_audit.py --help`. Parser changes after execution must be
labelled POST_RUNTIME_DERIVATION_ONLY; never rewrite Runtime metadata or raw
events to fit a parser. Build an explicit new closure index, approve its local
hash and execute `verify-existing`. Source/run/seal changes fail closed.

## Full and Audit-Lite

Follow [Evidence Archive](EVIDENCE_ARCHIVE.md). Finish reports and readable design
assets, include all required capsule categories and complete raw MCP files,
stop every writer, then seal the new Full Archive. Export outside Full with a
fixed `created_at`; retain all failed attempts and omitted-source pointers.

The unchanged standalone verifier checks OrderFlow consistency. The trusted
installed `aevora.audit_capsule.verify_exported_capsule` additionally checks
actual included Aevora design/schema/query/Gate/JUnit/MCP/Outcome/source bytes.
Neither runs package code or contacts a model/database. Obtain verifier source
and ZIP digest separately; checksums from the same untrusted ZIP do not
authenticate origin. Full and Audit-Lite are MAINTAINER_AUDIT, never task input.

H1 proves an engineering chain. It does not establish causal adoption,
statistical governance improvement, hostile multi-tenant security or a general
experience evolution algorithm. Stop after H1; further phases need authorization.
