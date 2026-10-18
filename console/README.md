# Gen2 Decision Journey — current public entry

From the public source root, follow the [release README](../README.md). The new
`/journey.html` presents live synthetic Graph v2 observations separately from
the sanitized G23 historical evidence. The legacy server/pages below remain
available with their explicit source classifications.

# Aevora Experience Console

A read-only companion to Aevora's MCP interface. The existing Core resolves WHEN/WHY using actual FalkorDB relationships. This Console displays public projections; it does not approve candidates or create trusted outcomes.

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

Viewer HTTP exposes no arbitrary Cypher, filesystem paths, approval or writes. Bind address is loopback. Browser credentials are unnecessary. Raw MCP/model logs and private Oracle are outside the product package. Ordinary local MCP connection is a same-user developer boundary, not hostile participant isolation.

## Browser verification

The repository validation uses Playwright 1.64.0 and its independently installed Chromium. No personal browser profile or intercepted synthetic API response is used.

```sh
PLAYWRIGHT_BROWSERS_PATH=/your/separate/browser/cache ./console/node_modules/.bin/playwright install chromium
AEVORA_BROWSER_OUTPUT=/your/new/evidence/path \
AEVORA_EMPTY_BROWSER_URL=http://127.0.0.1:17805 \
PLAYWRIGHT_BROWSERS_PATH=/your/separate/browser/cache \
npm --prefix console run test:browser
```

The second URL must be an actual Console connected to an initialized empty FalkorDB graph. The maintainer helper `scripts/aevora_h4_browser.py` creates and removes that owned graph, records commands and preserves failures. It is not a public runtime dependency. Browser tracing/screenshots contain only public Viewer projections; they remain validation evidence rather than model proof.

Cytoscape 3.34.3's fixed container CSS is preloaded from the external application stylesheet with its expected stylesheet identifier. This avoids its default inline style injection while preserving the strict self-only CSP. Public evidence tools are exact vendored copies with a source hash receipt, not a second Core decision engine.
