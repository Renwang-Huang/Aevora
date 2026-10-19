> Current full-project source scope: [FULL_PROJECT_SCOPE_AND_LICENSE.md](FULL_PROJECT_SCOPE_AND_LICENSE.md). Product-only and optional engineering installs are separate [reproduction profiles](docs/REPRODUCIBILITY.md). Gen1.5/1.5.1 reports and original phase stop rules remain historical records.

# Current development entrypoint

This is the **maintainer** guide. Ordinary product users start with
[public Quickstart](docs/QUICKSTART.md), [MCP registration](docs/CODEX_MCP_SETUP.md)
and [product limitations](docs/PRODUCT_LIMITATIONS.md). Public Core/Console can
install without OrderFlow. Historical phase commands/results are reproduction
assets; current commands require new external outputs.

## Workspace entry

Use [Product Dev](Aevora.Product.code-workspace) for public source/UI or
[Maintainer Dev](Aevora.Maintainer.code-workspace) for the included engineering
tests/Oracle/Host/tools. These are navigation views, not publication boundaries.
[Workspace guide](docs/current/WORKSPACE.md) explains terminal/task cwd, parent Git
discovery, public test scope and full-root inspection. All current commands below
retain their Gen1.5 paths and behavior.

## Environment

Use Linux/Python3.12 and real authenticated FalkorDB. Git, bubblewrap and an owned
cgroup v2 parent with delegated memory/pids controls are required for strict
Benchmark/native isolation. Console build
uses the locked Node24.15.0/npm11.12.1 configuration already in `console/`.

```sh
python3.12 -m venv .venv
make setup-public PYTHON=.venv/bin/python
.venv/bin/python -m pip install -e '.[dev,benchmark]'
.venv/bin/python -m pip install setuptools==76.1.0 wheel==0.45.1
npm --prefix console ci
make check-sources console-build console-test PYTHON=.venv/bin/python
```

`tools/dev.py --help` is the complete current command map; Make is only an alias.
It runs one existing command, not an Agent orchestration layer. Host-specific
Python/SQLite recovery runtime and readonly history mounts are documented by
this validation run's external driver/receipts. Do not substitute an old editable
install from the original maintainer root.

## Database and public services

Bootstrap external secrets with the existing `scripts/aevora_bootstrap.py`, use
`h4/deploy/compose.yaml` with a **new** compose project/volume/loopback port. Keep
password/config owner-only outside source and archives. The selected instance
must be explicitly owned before SAVE maintenance; never operate on H1–H4 volumes.

```sh
# Export HOST/PORT/GRAPH/PASSWORD_FILE from trusted local secret configuration.
.venv/bin/python tools/dev.py db-init
.venv/bin/python tools/dev.py db-health
.venv/bin/python tools/dev.py mcp-config -- --help
.venv/bin/python tools/dev.py console-replay --port 17804
# Read-only HTTP mode is explicitly selected in the URL:
# http://127.0.0.1:17804/?page=activity&case=case-a&mode=REPLAY
# http://127.0.0.1:17804/?page=explorer&case=case-b&mode=LIVE
```

The server handles both explicit modes. `console-live` starts the same bounded
read-only API; it cannot silently fall back to Replay. Clean MCP registration
and scoped four-tool protocol are detailed in CODEX_MCP_SETUP. Agent capabilities
never grant Host admission/publication or arbitrary Cypher. Cold recovery uses
the existing owned RDB procedure after explicit SAVE; AOF139 and unsaved-tail RPO
remain limitations, not promises repaired by consolidation.

## Tests and optional public Benchmark

Choose a fresh output **outside the checkout** for every command. Original
Gen1.5 reports retain their historical 1802-test results. The approved full-source
baseline recorded 2103 PASS, 51 SKIP and zero failures/errors; the 51 legacy G1
cases require an exact authenticated history import. This documentation hotfix
does not rerun or replace those original receipts. Use the current
[Benchmark reproduction](docs/BENCHMARK.md) and [graph/Host prerequisites](docs/DEBUGGING.md).
Clean product onboarding uses a new empty graph; synthetic fixtures never
substitute for authentic historical evidence.

```sh
make core-test PYTHON=.venv/bin/python OUTPUT=/external/new-core-run
make test PYTHON=.venv/bin/python OUTPUT=/external/new-full-run OWNED_PORT=17701
make benchmark-check PYTHON=.venv/bin/python OUTPUT=/external/new-cli-run
make dv02-check PYTHON=.venv/bin/python OUTPUT=/external/new-dv02-run
```

The full command reuses existing JUnit/raw-Cypher collection with a checked owned
endpoint and restored SAVE config. CLI validation preserves actual expected
FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED exits; it does not relabel them PASS submissions.
D-v02 executes the disclosed historical 36-case suite separately for
buggy/reference. Developer, Trusted Host, Oracle and reference source are included
in the full project; ordinary Core/Console deployment does not depend on that
optional evaluation package. Production keys, original private model sessions
and some historical run evidence remain unpublished. Published answers are no
longer future blind tests. B/C remain NOT_IMPLEMENTED, G24 Pilot/formal remains
NOT_RUN and the FalkorDB SIGSEGV/139/AOF limitations remain unresolved.

## Packaging, browser and isolation

```sh
make public-build PYTHON=.venv/bin/python OUTPUT=/external/new-public-build
# The output source is the only Docker build context.
docker build -f /external/new-public-build/source/h4/deploy/Dockerfile \
  -t aevora-gen15-local:review /external/new-public-build/source
# Trusted host scan of source/wheel/sdist/ZIP/image bytes must precede handoff.
```

Core/Console and optional OrderFlow wheels/sdists use setuptools; the full source
ZIP uses the reviewed deterministic archive format. Scan actual members and
known host-secret values/derivatives **in memory**; never archive secrets or
their individual hashes. Current command receipts cover installation in an
independent venv with
`-I`, official MCP SDK calls, public Docker layers, actual browser HTTP and
negative controls. Use an independent Playwright Chromium, not a personal profile.
`console/browser/validate.mjs` requires explicit output/main/empty-graph URLs and
performs real clicks/offline-network checks without mocked routes. The physical
probe is the existing `scripts.aevora_h2_security.physical_probes` on new evidence.

The Gen1.5 validation commands/results remain in
[Gen1.5 validation](docs/history/gen1.5/GEN1_5_VALIDATION_REPORT.md) as historical evidence. Current profiles are in
[reproducibility](docs/REPRODUCIBILITY.md). Historical native collaboration is read-only evidence;
no new paid multi-round challenge is necessary for this consolidation. Any future
native challenge must keep completion-aware mode and the existing Host/Participant
boundary. Old phase stop rules describe their original tasks; new work requires
its own owner authorization.

## Gen 1.5.1 verified handoff

See [current validation](docs/history/gen1.5/GEN1_5_1_VALIDATION_REPORT.md),
[Gen 2 starting point](docs/history/gen1.5/GEN1_5_1_GEN2_HANDOFF.md), and
[migration record](docs/history/gen1.5/GEN1_5_1_MIGRATION_RECORD.csv). Previous reports stay unchanged.
