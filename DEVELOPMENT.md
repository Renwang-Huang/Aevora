# Developing Aevora

Start with the [repository layout](docs/REPOSITORY_LAYOUT.md), [architecture](docs/ARCHITECTURE.md) and [Quickstart](docs/QUICKSTART.md). Core and Console install independently of the optional OrderFlow Benchmark. [Source and licensing scope](FULL_PROJECT_SCOPE_AND_LICENSE.md) covers the complete engineering repository.

## Set up the engineering environment

Use Linux, Python 3.12, Docker Engine with Compose v2, Node 24.15.0 and npm 11.12.1. Strict Benchmark/native validation also requires bubblewrap and a delegated cgroup v2 parent with memory and pids controls. Do not disable resource controls to obtain a passing result.

```sh
python3.12 -m venv .venv
make setup-public PYTHON=.venv/bin/python
.venv/bin/python -m pip install -e '.[dev,benchmark]'
npm --prefix console ci
make check-sources console-build console-test PYTHON=.venv/bin/python
```

For product-only installation, follow the Quickstart. For optional evaluator reproduction, use [Benchmark](docs/BENCHMARK.md) and [reproduction profiles](docs/REPRODUCIBILITY.md). Each developer supplies their own credentials outside the checkout; no private maintainer directory is an installation prerequisite.

## Work on a component

[Product and engineering workspaces](docs/WORKSPACES.md) provide editor navigation over the same Git checkout. They do not define a security or release boundary.

```sh
python3 tools/workspace_check.py
python3 tools/dev.py --help
```

`tools/dev.py` dispatches existing commands; it does not add an Agent orchestration runtime. Edit public evidence tools in `tools/public_evidence/`, then run `python3 tools/sync_public_evidence.py` and its `--check` mode. Console source is in `console/web`; its build writes the packaged static assets.

## Run services and tests

The [Quickstart](docs/QUICKSTART.md) creates an owned local synthetic demo. For an ordinary unseeded project use [standalone Core](docs/STANDALONE_CORE.md). The optional Observatory example is in `examples/observatory/`; its deployment template creates a separate database project and its replay requires the independently pinned contract hash.

Keep passwords, Host registries and model credentials outside source. Use fresh external outputs, new graph names and explicitly owned database resources. Never delete existing database volumes or operate on historical experiment deployments. [Debugging](docs/DEBUGGING.md) describes graph/Host prerequisites.

```sh
# Export HOST/PORT/GRAPH/PASSWORD_FILE from your own local configuration.
.venv/bin/python tools/dev.py db-init
.venv/bin/python tools/dev.py db-health
.venv/bin/python tools/dev.py mcp-config -- --help
.venv/bin/python tools/dev.py console-replay --port 17804

# Use new output paths outside the checkout and your owned database port.
make core-test PYTHON=.venv/bin/python OUTPUT=/external/new-core-run
make test PYTHON=.venv/bin/python OUTPUT=/external/new-full-run OWNED_PORT=17701
make benchmark-check PYTHON=.venv/bin/python OUTPUT=/external/new-cli-run
make dv02-check PYTHON=.venv/bin/python OUTPUT=/external/new-dv02-run
```

LIVE graph errors return UNAVAILABLE without replay fallback. MCP exposes four scoped tools; Agent claims do not grant Host approval, publication, arbitrary Cypher or Outcome-writing authority. Oracle tests and answers are public historical evaluation materials, so subsequent runs are not future blind tests.

The published full-source baseline records 51 legacy G1 SKIPs requiring an exact authenticated historical import. B/C remain NOT_IMPLEMENTED, G24 remains NOT_RUN with causal benefit UNKNOWN, and the FalkorDB SIGSEGV/139/AOF limitations remain unresolved. New validation receipts must retain their actual failures and environmental prerequisites; a synthetic fixture cannot substitute for authentic history.

## Package and inspect

```sh
make public-build PYTHON=.venv/bin/python OUTPUT=/external/new-public-build
docker build -f /external/new-public-build/source/deploy/Dockerfile \
  -t aevora-demo:review /external/new-public-build/source
```

The source ZIP and three package wheel/sdist pairs use the reviewed source selection. Inspect actual members, hashes and security scans before distribution. Use an independent Playwright Chromium profile for [browser verification](console/README.md); generated recordings and receipts belong outside the repository.

Earlier phase instructions, migration matrices and test outcomes remain in [engineering history](docs/history/README.md). They describe their original source epoch and do not authorize a new experiment or certify the current checkout.
