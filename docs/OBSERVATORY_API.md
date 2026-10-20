# Aevora controlled Observatory API

The thin `aevora-console` package wraps existing authoritative Core reads and
independently pinned public Hero replay. It does not import OrderFlow, create
an Orchestrator, decide WHEN independently, or expose database administration.

## Read-only resources

GET `/api/overview` and `/api/{sessions,decisions,experiences,graph,timeline,outcomes,health}`.
Named PUBLIC proof GET `/api/proof/{contract,origin,lifecycle,views,evolution,queries,pilot,readback,graph}`.
Selectors: mode LIVE/REPLAY, explicit case-a/b/c, actual experience ID, controlled
context threads/workers/unknown, replay evolution stage before/after/restored,
bounded limit1..100/offset0..1000. No arbitrary Cypher, path or runtime command.

- LIVE: new real GraphRepository reads; WHEN/WHY comes only from
  ExperienceResolver.resolve(persist_snapshots=False). Zero HTTP read writes.
  Context is visibly a maintainer-controlled public demonstration, not an
  invented actual Agent task. Actual Agent Query/Decision records are separate.
- REPLAY: fixed contract pin and revalidation of every evidence artifact on
  every read. Captured archive/time/SHA and original partial ordering are visible.
  It is not current model execution or graph mutation.
- Missing current natural publication: UNAVAILABLE; empty graph: EMPTY; DB
  outage:503/GraphUnavailable; changed archive:422. No automatic static fallback.
- Published/seed experiences, pending candidate headers, actual bounded graph
  and lifecycle records, typed actual runtime headers/tool names/references.
  Raw MCP/model payload, private verification/body fields, hidden tests and
  Host credentials remain excluded. Individual child authorship is UNAVAILABLE.
- Trusted graph VerifiedOutcome records and external observations are separate;
  a self-test cannot create a trusted outcome through any HTTP action.

## Security / bounded read budget

Loopback listener only, fixed allowed Host/Origin, four concurrent read slots,
16 HTTP concurrency, no-store responses, restrictive CSP/no-sniff/referrer policy,
input/page bounds, actual SDK query timeouts; graph≤500 nodes/1200 edges/16
experiences/8MiB raw graph payload, displayed focus≤64 actual nodes. Graph
layout/filtering is presentation, not new relationship inference. Viewer has
no write endpoint, admin credentials, arbitrary file reader or script runner.
MCP availability is NOT_ACTIVE_PROBED rather than an invented connected state.
Local same-UID/shared-kernel restrictions remain known limitations.

## Run the actual API

```sh
python3.12 -m pip install ./aevora_core ./console
python3 console/sync_evidence_tools.py
python3.12 -m aevora_observatory.server --replay-root h4 \
  --replay-sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776
```

Host-only graph environment is the Quickstart's own configuration. Optional
--activity-root points to a trusted runtime archive for typed headers only;
no browser chooses this path. The proof verifier/policy are exact vendored
public source bytes; no duplicate Core resolver logic. G2 serves API_READY
JSON before G3 supplies static UI assets.
