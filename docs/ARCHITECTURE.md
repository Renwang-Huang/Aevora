# Aevora architecture

```text
Agent / official MCP client
  └─ four scoped MCP tools (official Python SDK; bounded, lossless continuation)
      └─ Graph v2 repository + trust registry + deterministic WHEN/WHY
          └─ real FalkorDB: authenticated catalogue, complete paths, revisions

Local Console browser → read-only bounded HTTP projection → same Core/graph
Trusted Host → source + independent Outcome verification → Q07 publication
```

Core: `aevora_core/src/aevora`. Console: `console/src/aevora_observatory` and
`console/web`. This full engineering repository also includes `app/`, `benchmark/`,
`evaluator/`, `integrations/` and `aevora_maintainer/`: the actual task world,
Runner, Oracle/tests/reference answers, Agent adapters, native source verifier and
Trusted Host/Q07 implementation. See the [source scope](../FULL_PROJECT_SCOPE_AND_LICENSE.md)
and [source map](FULL_PUBLIC_SOURCE_MAP.md). Formerly hidden evaluation material
is labelled [public historical evaluation](../docs/history/evaluation/README.md);
it is no longer a future blind test.

Product-only Core/Console installation and the demo image remain independent of
the optional Benchmark/evaluator. Repository inclusion does not grant production
Host authority: keys, capability/registry data, original private model sessions
and some historical run evidence remain unpublished. Optional Host verification
uses explicit authority and matching sealed source pins; ordinary query and
participant MCP tools do not acquire those privileges.

## Demo and production boundaries

`aevora.demo` runs the public SQLite verifier in a subprocess and seeds explicitly
synthetic examples through existing Graph v2 record/manifests APIs. It does not
replace Q07 or bypass production authentication. Its local registry is synthetic
and meaningful only in that owned demo namespace. `aevora.demo_mcp` creates a
short-lived synthetic session and uses the existing V2Service and official SDK.
Only untrusted claims/Candidates can be written through those tools.

The browser cannot seed, publish, submit Outcomes, choose arbitrary graph names,
read arbitrary files or send Cypher. `/api/journey` accepts only context/stage
selectors, bounds concurrent reads and fails closed. Existing HTTP Host/origin,
CSP and response restrictions remain. The container listens internally on8080;
Compose publishes only loopback. Production remote hosting needs separate auth,
TLS, tenant lifecycle and deployment review.

Historical G23 summaries are separate local public assets with explicit REPLAY
classification. They are not fallback responses for a failed live query.
