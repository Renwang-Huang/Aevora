# Aevora Experience Console

A read-only companion to Aevora's MCP interface. The existing Core resolves WHEN/WHY using actual FalkorDB relationships. This Console displays public projections; it does not approve candidates or create trusted outcomes.

The current product entry is `/journey.html`, started through the [Quickstart](../docs/QUICKSTART.md). It displays live synthetic Graph v2 observations separately from historical Agent evidence. The optional pinned Observatory replay below serves the same read-only API with explicit source classifications.

## Build and run

Use Python 3.12, Node 24.15.0 and npm 11.12.1. From the public source directory:

```sh
npm --prefix console ci --ignore-scripts
npm --prefix console run test
npm --prefix console run build
python -m pip install ./aevora_core ./console
python -m aevora_observatory.server --replay-root ./h4 \
  --replay-sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776
```

Open `http://127.0.0.1:17804`. Configure actual FalkorDB using the environment variables in [Quickstart](../docs/QUICKSTART.md) to use LIVE. REPLAY does not require a running database or a model provider. The independently supplied contract pin is required; do not substitute the hash of an untrusted download without checking the release receipt.

Three pages share Case/Run/Mode selection in the URL:

- Activity & Decisions: actual runtime states, native child identities when available, tool requests and authoritative recommendations.
- Experience Explorer: genuine node/relationship IDs, bounded graph focus, accessible list, property inspection and public proof.
- Governance Timeline: actual lifecycle events, historical/current queries and outcome authority.

The graph initially displays up to 24 actual neighboring nodes from the bounded API response. “Show loaded graph” expands only the already loaded nodes. Counts disclose both limits. Layout positions convey no causal semantics.

## Modes and trust

REPLAY is a pinned, independently checked projection of sealed history. Its archive, capture time and SHA are visible. The three cases have different sources. LIVE queries actual Core/Graph state; missing publication, database failure and empty graphs do not fall back to Replay. Controlled `threads`, `workers` and `unknown` contexts are explicit public demonstration inputs, not claimed Agent task facts.

Viewer HTTP exposes no arbitrary Cypher, filesystem paths, approval or writes. Bind address is loopback. Browser credentials are unnecessary. The product-only image does not install the optional Benchmark/evaluator. Their Oracle/tests/reference answers and Trusted Host source are included in the full engineering repository; production credentials, original private model sessions and some historical run evidence remain unpublished. Ordinary local MCP connection is a same-user developer boundary, not hostile participant isolation.

## Browser verification

`test:browser` uses the existing `web/record_demo.mjs` Playwright script against a
running **Decision Journey**, not the legacy empty-graph test harness. Start your
[owned local demo](../docs/QUICKSTART.md) first. The script performs actual clicks,
checks live verdicts, graph and withdrawal, separates historical Core/Agent
choices, checks read-only HTTP boundaries, offline behavior and layout, and saves
RESULT.json, screenshots and a trace. It uses no mocked API responses.

Use Playwright 1.64.0 and its Chromium, independently of a personal browser profile:

```sh
./console/node_modules/.bin/playwright install chromium
AEVORA_BROWSER_URL=http://127.0.0.1:19064 \
AEVORA_BROWSER_OUTPUT=/absolute/new/external-evidence-directory \
npm --prefix console run test:browser
```

`AEVORA_BROWSER_OUTPUT` must be explicit and outside the source checkout. An
optional external `PLAYWRIGHT_BROWSERS_PATH` selects your own browser cache;
use the same value when installing Chromium and running the test. No second
empty-graph URL or private maintainer helper is required. A failing check returns
nonzero and preserves FAILURE.txt/RESULT.json. Video is off by default; use
`AEVORA_RECORD_VIDEO=1 npm --prefix console run demo:record` with the same URL and
output variables to add actual video and narration pauses. These browser results
are product validation evidence, never proof of a new model run.

Cytoscape 3.34.3's fixed container CSS is preloaded from the external application stylesheet with its expected stylesheet identifier. This avoids its default inline style injection while preserving the strict self-only CSP. Public evidence tools are exact vendored copies with a source hash receipt, not a second Core decision engine.
