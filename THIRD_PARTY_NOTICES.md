# Third-party source and runtime notices

Aevora source has its own MIT license. Dependency and database licenses remain separate; no historical Git/document license is rewritten.

- Cytoscape.js3.34.3: upstream license is included as `console/third_party/CYTOSCAPE_LICENSE`; source [Cytoscape.js v3.34.3](https://github.com/cytoscape/cytoscape.js/blob/v3.34.3/LICENSE). Its license text is also retained by the frontend bundle's legal comments.
- esbuild0.28.2: MIT; development/build dependency, not a second runtime graph engine.
- Playwright1.64.0: Apache2.0; maintainer browser validation only, not required by the Core/Console runtime.
- FalkorDB server4.20.4: separately downloaded official image, pinned digest; its upstream [LICENSE.txt](https://github.com/FalkorDB/FalkorDB/blob/v4.20.4/LICENSE.txt) is Server Side Public License v1. It is not relicensed as Aevora MIT or embedded into Aevora's public source ZIP.
- Python, FalkorDB Python SDK, Redis SDK, MCP SDK, Starlette, Uvicorn and their transitive dependencies retain their installed license metadata. Runtime package versions and image bytes are recorded during delivery checks.

The local product image contains Aevora packages and their installed dependencies. The graph server remains a separate Compose service. No claim of production hosting or third-party legal certification is made here.

## Gen 2 G21 runtime addition

`jsonschema==4.26.0` (MIT; https://github.com/python-jsonschema/jsonschema) is reused for the explicit v2 structural contracts. It was already used by maintainer contract validation; G21 adds it as a declared Core runtime dependency. Structural schema validation does not establish Host authority or independent Outcome truth. Local distribution COPYING/metadata and installed version are pinned in the G21 audit evidence. Existing licenses and historical provenance remain intact.
