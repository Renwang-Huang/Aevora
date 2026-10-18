# Ordinary Codex project integration

Aevora Core can be installed and queried without the OrderFlow package. The
H3 clean-install receipt uses a fresh Python 3.12 venv, the public Core wheel,
`pip check`, an actual empty FalkorDB graph, and installation/uninstallation
checks. `benchmark` and `integrations` are not installed in that environment.
The Core's explicit `source-orderflow` and legacy maintainer audit helpers are
optional trusted adapters; they are not dependencies of health/query/serve.

## Host deployment

Install only `aevora_core/`, not the root MAINTAINER_ONLY Benchmark distribution.
The tested public command structure is:

```sh
python -m pip install /path/to/aevora_core-0.1.0-py3-none-any.whl
python -m pip check
python -m aevora init
python -m aevora health
python -m aevora query --run-id ordinary-project-check --context public-context.json
```

Host-only environment variables are `AEVORA_FALKORDB_HOST`,
`AEVORA_FALKORDB_PORT`, `AEVORA_FALKORDB_GRAPH`, and
`AEVORA_FALKORDB_PASSWORD_FILE`. The password is loaded from an owned ordinary
0600 file outside the project, never passed in command arguments or consumer
environment. Use a separately owned graph/Volume/loopback endpoint. H3 uses
17689; cold restore/control uses 17690. Historical H1/H2 stores remain separate.

`public-context.json` contains factual scalars from the existing allowlist,
for example `concurrency_scope`, `shared_state_kind`,
`transaction_guarantees`, and `worker_count_known`. Unknown facts stay unknown.
Do not supply Episode IDs as applicability rules. The Host pins this context;
Participant claims do not overwrite known facts. A consumer can call
`resolve_experience` with an empty `task_context` to use that pinned context.

Create an owned private runtime directory, and run the tested server structure:

```sh
python -m aevora serve --run-id ordinary-project-session \
  --context public-context.json --socket /private-runtime/mcp.sock \
  --capability-file /private-runtime/cap.json --events /trusted-archive/mcp.jsonl \
  --enable-proposals
```

The capability directory must be 0700. The generated capability file is 0600,
is runtime state, and must never enter an archive or repository. SIGINT/SIGTERM
revokes the capability and removes both file and socket. A new server has a new
capability; the prior session does not regain authority after reconnecting.
The official SDK returns explicit errors if FalkorDB is unavailable. An empty
real graph returns no candidates rather than a static recommendation.

## Consumer boundary and native Codex

The server runs in a trusted Host account. Mount only its scoped socket at
`/aevora-channel/mcp.sock` and a read-only copy of `aevora/mcp_proxy.py` at
`/aevora_mcp_proxy.py` into an already isolated Codex consumer. The proxy needs
only Python's standard library. Forward only the short-lived `AEVORA_RUN_ID`
and `AEVORA_RUN_TOKEN`; keep the database SDK, admin executable, password,
long-term model key and maintainer files outside that consumer.

The installed Codex 0.162.1 and real H3 sessions used:

```toml
[mcp_servers.aevora]
command = "/usr/bin/python3.12"
args = ["-I", "-B", "/aevora_mcp_proxy.py"]
env_vars = ["AEVORA_RUN_TOKEN", "AEVORA_RUN_ID"]
enabled = true
required = true
enabled_tools = ["resolve_experience", "build_evidence_bundle", "record_decision", "propose_experience"]
startup_readiness = "connection"
startup_timeout_sec = 20
tool_timeout_sec = 60
default_tools_approval_mode = "auto"
```

This is a verified configuration contract, not a universal claim about future
Codex versions. `serve` does not itself isolate Codex. Setting cwd or enabling
the native workspace-write sandbox alone does not protect Host read access.
The H3 validation harness reuses the existing physical outer boundary and
Codex adapter; it invokes no OrderFlow Registry, Runner or hidden Evaluator for
the ordinary project. The separately installed product server works without
that Benchmark sandbox library. Deploy it behind an equivalent mature
container/namespace/VM boundary before granting a consumer channel.

## Engineering example and result authority

`examples/receipt_store` is a controlled maintainer-authored independent Python
project, not a copied Episode or production deployment claim. It records
durable delivery receipts, idempotency conflicts and channel totals, with seven
public tests and an independently initialized Git repository. No correct repair
is preinstalled. The pristine baseline really fails concurrent thread/process
totals while five other public checks pass.

Ordinary-project self-tests and Host replay of its public tests are
`EXTERNAL_UNVERIFIED`. They never become VerifiedOutcome merely because a
command succeeds. Agent proposals remain PROPOSED/PENDING without an independent
trusted source/Oracle. Only Host review can publish, and source verification
and bounded support are distinct from causal usefulness.

Uninstall the tested public package with:

```sh
python -m pip uninstall -y aevora-core
```

Stop the Host server first. Delete only the session's private runtime state;
retain evidence and intentionally owned graph/Volume according to its policy.
H3 does not implement production multitenancy, general prompt-injection
immunity, model-weight attestation, an AOF fix or zero-RPO recovery.
