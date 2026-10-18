# Reproduce the local release

## Clean Docker installation

Use the public source root only, not a maintainer checkout or Full evidence root.
Docker Compose v2, Python3.10+ launcher and at least4GB available RAM are required.
Images pin Python3.12.14 and FalkorDB4.20.4 by digest; Python dependencies are exact
pins in the two pyproject.toml files. No browser CDN or model credential is needed.

```sh
python3 scripts/aevora_public_demo.py start --project aevora-demo-clean1 --secret-dir "$HOME/.config/aevora/demo-clean1"
# Open http://127.0.0.1:19064/journey.html
curl --fail 'http://127.0.0.1:19064/api/journey?context=threads&stage=before'
```

Check the first result's actual `core_verdict`, Witness and query receipts. Use
`context=workers` and`context=unknown`, then`stage=after`. Expected representative
results are APPLY, ABSTAIN, VERIFY and withdrawal ABSTAIN. These expectations are
tested; the HTTP implementation never selects an answer from those labels.

For a second independent install stop the first services, then use a new project
and secret directory. Never reuse an old graph volume as evidence of a clean
installation. The stop command performs an explicit owned RDB SAVE, then retains volumes and secrets. Unflushed writes after that SAVE are not guaranteed. Reset means a new
owned demo project; destructive cleanup is an explicit user responsibility.

## Native Python installation

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install ./aevora_core ./console
# Set AEVORA_FALKORDB_HOST/PORT/GRAPH/PASSWORD_FILE on the trusted host.
# Graph v2 names must start with aevora_v2_. Choose a new namespace.
.venv/bin/python -m aevora.demo seed --state-dir /outside-source/demo-state
.venv/bin/python -m aevora.demo observe --state-dir /outside-source/demo-state
```

No model is run by these commands. The public example verifier is available as
`python -m aevora.demo_verify`. Official MCP calls can use the existing trusted
Demo container:`python -m aevora.demo_mcp --state-dir /state --context threads`.

## Browser source

```sh
npm --prefix console ci --ignore-scripts
npm --prefix console run build
npm --prefix console test
```

With the [owned demo](QUICKSTART.md) running, install Chromium and run the actual
Decision Journey browser checks (no private helper or empty-graph service):

```sh
./console/node_modules/.bin/playwright install chromium
AEVORA_BROWSER_URL=http://127.0.0.1:19064 \
AEVORA_BROWSER_OUTPUT=/absolute/new/external-evidence-directory \
npm --prefix console run test:browser
```

An optional `PLAYWRIGHT_BROWSERS_PATH` must be identical for installation and test.
The explicit output directory receives real screenshots, trace and RESULT.json.
No model/API credential is involved. See the [Console guide](../console/README.md#browser-verification).

The release archive includes static assets; Node is only needed to rebuild or
run developer browser checks. Private Oracle/Benchmark tests are intentionally
not public dependencies. Historical test counts describe their pinned code and
are not automatically the test result of this release.

## Public source checks

After Python installation, install pytest9.1.1 and run
`python -m pytest -q aevora_core/public_tests`. To exercise the real official MCP
SDK with your configured owned graph/state, run
`python aevora_core/public_tests/check_live_mcp.py /outside-source/demo-state`.
That SDK acceptance client is explicitly not a model Agent or Native challenge.
