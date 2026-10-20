# Standalone Core and ordinary-project integration

This public path needs Python3.12, Docker Compose and the official Codex CLI.
It installs the independent `aevora-core` and optional `aevora-console` packages. No OrderFlow Runner, hidden tests, private
archive, old Volume, author `.env` or Gateway key is required for installation,
MCP protocol checks or the verified historical public replay.

## 1. Install and create your own private database configuration

From a clean public source checkout:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install ./aevora_core
python3 scripts/aevora_bootstrap.py "$HOME/.config/aevora/product"
export AEVORA_REDIS_CONFIG_FILE="$HOME/.config/aevora/product/falkordb.conf"
export AEVORA_FALKORDB_PASSWORD_FILE="$HOME/.config/aevora/product/falkordb.password"
export AEVORA_FALKORDB_HOST=127.0.0.1
export AEVORA_FALKORDB_PORT=17692
export AEVORA_FALKORDB_GRAPH=aevora_product
export AEVORA_DB_PORT=17692
```

Secrets stay outside the checkout: directory0700/files0600. Do not put these
exports or DB credentials into Codex's environment. A normal same-UID local
account is a trusted owner, not an adversarial isolation boundary.

## 2. Start the actual graph and Core

```sh
docker compose -f examples/observatory/deploy/compose.yaml up -d --wait
.venv/bin/python -I -m aevora init
.venv/bin/python -I -m aevora health
.venv/bin/python -I -m aevora query --run-id first-query --context examples/observatory/context.json
```

A new Volume has **no experiences**. `AVAILABLE` with `candidates: []` is the
correct result, not a failed seed import or a hidden static fallback. Your
own ordinary project may create untrusted proposals; its public tests cannot
mint a VerifiedOutcome. Historic Hero evidence is a separately marked Replay.

## 3. Grant a scoped MCP channel for your ordinary project

```sh
mkdir -p "$HOME/.local/state/aevora/product-session"
chmod 700 "$HOME/.local/state/aevora/product-session"
.venv/bin/python -I -m aevora serve --run-id ordinary-project \
  --context examples/observatory/context.json \
  --socket "$HOME/.local/state/aevora/product-session/mcp.sock" \
  --capability-file "$HOME/.local/state/aevora/product-session/grant.json" \
  --events "$HOME/.local/state/aevora/product-session/mcp_events.jsonl" \
  --enable-proposals
```

Keep that trusted Host command running. In another terminal generate the
config using absolute paths, then place the stanza in your separate Codex
configuration (see [MCP setup](CODEX_MCP_SETUP.md)). Grant files are private
ephemeral state; never commit/export their contents. Ctrl-C revokes the owner
channel and deletes its grant/socket. An optional `--capability-ttl 3600` is an
explicit local expiry, not the default Agent runtime completion deadline.

## 4. Use your own project and inspect the evidence

Ask a fresh Codex Session to inspect its actual source and call
`resolve_experience`, then obtain `build_evidence_bundle` for any returned
experience. Empty results must be reported honestly. `record_decision` records
an untrusted claim. `propose_experience` creates an untrusted candidate only.
Host source verification/admission and Oracle are never Agent tools.

The supplied `aevora_core/examples/receipt_store` is an owned controlled
ordinary SQLite project with original public tests. It is not an independent
Benchmark and is not already repaired. Actual H3 Gov/Raw observations both
passed7 tests; their results remain EXTERNAL_UNVERIFIED.

Start the read-only Console (prebuilt static files are delivered):

```sh
.venv/bin/python -m pip install ./console
.venv/bin/python -I -m aevora_observatory.server --replay-root ./h4 \
  --replay-sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776 \
  --mcp-events "$HOME/.local/state/aevora/product-session/mcp_events.jsonl"
```

Open `http://127.0.0.1:17804`. Fresh-volume LIVE remains EMPTY; choose REPLAY
for the independently pinned historical three-case walkthrough. The optional Host-configured `--mcp-events` displays only actual tool request
headers; client/native Session identity remains UNAVAILABLE unless independently
collected. No raw payload, DB key or grant file enters the browser. See [Demo](DEMO_WALKTHROUGH.md) and
[Console](../console/README.md). To rebuild static assets use Node24.15.0 and
`npm --prefix console ci --ignore-scripts && npm --prefix console run build`.
The native validation owner/Benchmark scripts are not product dependencies.

## 5. Save and clean up

Ctrl-C Core serve, then `docker compose -f examples/observatory/deploy/compose.yaml stop` for a
graceful stop. The named Volume is retained. Use `down` to remove only the owned
containers/network; `down -v` permanently deletes that project's data and is
an explicit disposable-demo choice. Do not run it on a historical deployment.

Persistence is RDB at the latest completed SAVE/graceful stop. AOF is disabled
because the pinned engine reproduced reload139. Unsaved crash-tail durability,
shared-kernel hostile isolation and general prompt-injection immunity are not
claimed. See [Troubleshooting](TROUBLESHOOTING.md).
