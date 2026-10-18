# Aevora

**Know when to reuse experience. See why.**

Aevora gives coding Agents scoped, graph-grounded engineering memory. FalkorDB
connects a principle to its prerequisites, supporting outcomes, contradictions,
authority and revision history. The unchanged Gen2 policy returns **APPLY**,
**VERIFY** or **ABSTAIN** with a complete Witness. Agents can record a decision
and propose an experience; only a trusted Host can verify and publish it.

## Run the product locally

Requirements: Docker Engine + Docker Compose v2, Python3.10+ for the launcher,
Linux with at least4GB available memory and available loopback ports19062/19064.
The application image uses Python3.12.14. No model API key is needed for this demo.

```sh
python3 scripts/aevora_public_demo.py start \
  --project aevora-gen2-demo \
  --secret-dir "$HOME/.config/aevora/public-demo"
```

Open **http://127.0.0.1:19064/journey.html**. The first start builds the public
Core and Console, creates new Docker volumes and runs the public SQLite verifier
in a separate process before seeding two owned synthetic graph states.
Secrets are generated outside the source tree and are never printed.

```sh
python3 scripts/aevora_public_demo.py status --project aevora-gen2-demo --secret-dir "$HOME/.config/aevora/public-demo"
python3 scripts/aevora_public_demo.py stop --project aevora-gen2-demo --secret-dir "$HOME/.config/aevora/public-demo"
```

Stop explicitly SAVEs the owned graph, then retains volumes. For a clean reset choose a **new project name and secret
directory**, for example`aevora-demo-second` and`$HOME/.config/aevora/demo-second`.
Nothing deletes another project's graph or historical evidence. See
[reproducibility](docs/REPRODUCIBILITY.md) for a second clean installation and tests.

## A three-page Decision Journey

1. **Activity & Decisions:** change the public process context. Shared threads →
   APPLY; independent workers → ABSTAIN; unknown premise → VERIFY. These are
   actual reads from FalkorDB, not a lookup table of expected answers.
2. **Experience Explorer:** inspect the actual nodes and relationships behind the
   recommendation and its Witness hash.
3. **Governance Timeline:** compare a real synthetic withdrawal with the baseline,
   then inspect the distinct historical Codex source, code action and Outcome.

Every live panel is labelled **LIVE synthetic demo**. No Agent/model is executing
in those panels. The historical G23 section is **Historical verified evidence
(sanitized) / REPLAY**: two original independent Oracle results28/28, each with
three verified native children. S2's **Core recommended APPLY; Agent recorded
VERIFY**. S2 support was a Host-approved follow-up, not direct automatic
publication of its natural proposal. Public hashes identify a sanitized summary;
the private Oracle and original model conversations are intentionally excluded.

**Causal benefit remains UNKNOWN. G24 Pilot and formal Graph/Raw/No Memory
comparisons have NOT RUN.** The product does not claim a statistical advantage.

## Graph data model and real work

```text
Experience ─HAS_REVISION→ ExperienceRevision ─USES_RULE→ Rule ─REQUIRES→ Premise
                                 │
                                 ├─SUPPORTED_BY / COUNTEREXAMPLE→ Evidence
                                 │                                  └─VERIFIES→ VerifiedOutcome
                                 │                                                └─ATTESTED_BY→ Authority
                                 └─PUBLISHED_BY→ PublicationManifest ←COMMITS─ TenantState
```

Context, scope, permission epoch and complete manifests are checked before WHEN/
WHY arbitration. Removing an essential relationship causes an integrity failure;
withdrawing a revision changes the recommendation. Disconnecting FalkorDB makes
the live path unavailable, with **no replay fallback**. See [graph model](docs/GRAPH_MODEL.md),
[actual Cypher](docs/CORE_CYPHER.md) and [architecture/trust boundaries](docs/ARCHITECTURE.md).

## MCP integration

The four tools are`resolve_experience`,`build_evidence_bundle`,`record_decision`
and`propose_experience`. They do not expose arbitrary Cypher, trusted Outcome
registration, or publication. Follow every bounded response page.

For the synthetic example, launch the official SDK server **on your trusted host**:

```sh
# Uses the existing running demo's configured container environment and state.
AEVORA_REDIS_CONFIG_FILE="$HOME/.config/aevora/public-demo/falkordb.conf" \
AEVORA_FALKORDB_PASSWORD_FILE="$HOME/.config/aevora/public-demo/falkordb.password" \
docker compose -p aevora-gen2-demo -f deploy/compose.yaml exec -T console \
  python -m aevora.demo_mcp --state-dir /state --context threads
```

This is an MCP stdio endpoint, not an interactive shell; configure your MCP client
to launch that command with the same two external secret-file environment paths
used by the launcher. Model-visible arguments contain no database password.
See [MCP setup](docs/CODEX_MCP_SETUP.md) for exact configuration and the distinction
between this synthetic environment and production Host authority.

## Scope, evidence and limitations

- Core and Console install without OrderFlow. OrderFlow Incident Lab remains an
  independent, private Benchmark/Outcome provider; FalkorDB is the actual database.
- The public demo uses a clearly synthetic publisher and actual public verifier.
  It is **not** the private production TrustedHost/Q07 admission service. The
  historical Q07 chain has separate evidence and no public publication endpoint.
- G23 functionality was accepted with reliability conditions. A real FalkorDB
  SIGSEGV139 remains unexplained; pinned engine, AOF and unsaved-tail limits are
  disclosed in [limitations](docs/LIMITATIONS.md), not advertised as fixed.
- This is a local read-only Console, not an authenticated multi-user hosted product.

## Build and contribution disclosure

Prebuilt browser assets are included. Rebuilding uses Node24.15.0 / npm11.12.1:

```sh
npm --prefix console ci
npm --prefix console run build
npm --prefix console test
```

Primary proposed hackathon track: **Agent Memory and Coordination**. Optional
Agents That Act on Connected Data claims are limited to the demonstrated graph
path. No submission has been made. See [contribution provenance and AI
assistance](docs/HACKATHON_CONTRIBUTIONS.md), [demo script](docs/DEMO_WALKTHROUGH.md)
and [submission fields](docs/SUBMISSION_FIELDS.md). Codex/GPT-6.1 Sol led this local
release; DeepSeek's separate G24 assets are not pooled into its claims.

MIT source license; see LICENSE, THIRD_PARTY_NOTICES.md and SECURITY.md.
