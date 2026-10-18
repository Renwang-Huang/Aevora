# Aevora Gen2 public architecture

```text
Agent / official MCP client
  └─ four scoped MCP tools (official Python SDK; bounded, lossless continuation)
      └─ Graph v2 repository + trust registry + deterministic WHEN/WHY
          └─ real FalkorDB: authenticated catalogue, complete paths, revisions

Local Console browser → read-only bounded HTTP projection → same Core/graph
Trusted Host → source + independent Outcome verification → Q07 publication
```

Core:`aevora_core/src/aevora`. Console:`console/src/aevora_observatory` and
`console/web`. Neither ordinary query nor Console requires OrderFlow. The private
Benchmark, hidden Oracle, reference patches, Native source verifier and production
TrustedHost implementation are excluded from this source distribution. Deferred
legacy Host bridges in Core are compatibility interfaces, not public authority.

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
