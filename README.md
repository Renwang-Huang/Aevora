# Aevora

**AI agents shouldn't just remember what worked. They should know when to trust it.**

Evidence-grounded experience reuse, powered by FalkorDB.

[View Demo Walkthrough](docs/DEMO_WALKTHROUGH.md) · [Quickstart](docs/QUICKSTART.md) · [Graph Model](docs/GRAPH_MODEL.md)

## 02 · SEE THE PRODUCT

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/rc12-activity-decisions-mobile.png">
  <img src="docs/assets/rc12-activity-decisions-viewport.png" alt="Activity &amp; Decisions: actual FalkorDB-backed APPLY, with LIVE synthetic demo, observation time and no-model-execution labels visible" width="1024">
</picture>

*Actual browser capture · LIVE synthetic demo · No model is executing.*
[Capture provenance](docs/assets/RC12_VISUAL_PROVENANCE.json) · [Original full capture](docs/assets/activity-decisions.png)

One remembered fix: **one shared process-local lock around the complete inventory
read/write**. Its boundary: every writer shares the same process and lock object.

- **APPLY · Shared Threads** — the known premise matches complete applicable support.
- **VERIFY · Unknown Premise** — establish the missing process-topology premise before reuse.
- **ABSTAIN · Independent Workers** — a process-local lock cannot coordinate separate processes.

These verdicts are **Core recommendations**, not claims that an agent acted.
Inspect [Experience Explorer](docs/assets/experience-explorer.png) and
[Governance Timeline](docs/assets/governance-timeline.png), including the distinct historical REPLAY labels.

## 03 · WHY IT WORKS

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/rc12-mechanism-mobile.svg">
  <img src="docs/assets/rc12-mechanism-desktop.svg" alt="WHEN checks applicability; WHY inspects a complete graph Witness; ACCOUNTABILITY separates advice and action; FEEDBACK is gated by trusted review." width="1000">
</picture>

**WHEN** checks context, premises, scope, active revisions and permissions.
**WHY** returns a complete Witness linking support, counterexamples, VerifiedOutcome
and Authority. **ACCOUNTABILITY** keeps Core advice, the agent's recorded choice,
code action and independent evaluation distinct. **FEEDBACK** requires Trusted Host
review for publication, revision, supersession and withdrawal; natural proposals
alone remain untrusted.

FalkorDB traverses this linked evidence and governance structure to determine
which recommendation is admissible. Changes to those relationships can change
the answer; graph storage alone does not certify an Oracle's truth.

[Graph model](docs/GRAPH_MODEL.md) · [Actual Cypher](docs/CORE_CYPHER.md) · [Arbitration source](aevora_core/src/aevora/arbitration.py)

## 04 · PROVEN IN REAL AGENT SESSIONS

*Historical G2-3 Codex Native Multi-Agent · separate genuine sessions · sanitized public summary.*

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/rc12-transfer-mobile.svg">
  <img src="docs/assets/rc12-transfer-desktop.svg" alt="Historical S1: patch, independent Oracle and natural proposal; Trusted Host: verify source and outcome, then Q07 publish; fresh S2: retrieve Witness, decide and create its own patch." width="1000">
</picture>

**S1 → Trusted Host → Fresh S2.** Each historical run had three verified native
children and an original independent Oracle result of **28/28**. S1's natural
proposal became trusted only after source/Outcome verification and Q07 publication.

Fresh S2 retrieved the published experience and Witness, then produced its own
patch: **Core recommended APPLY; S2 Agent recorded VERIFY.** S2's additional
support was a **Host-approved follow-up**, not direct publication of its natural proposal.

[Evidence and limitations](docs/NATIVE_TRANSFER.md) · [Public historical summary](console/web/gen2_history.json)

Original Oracle assertions and model conversations are private. These historical
results do not establish statistical improvement; the archived G2-4 comparison
status is **NOT_RUN** and causal benefit is **UNKNOWN**.

## Get started

[Run the local demo](docs/QUICKSTART.md) · [Two-minute walkthrough](docs/DEMO_WALKTHROUGH.md) · [Reproduce and test](docs/REPRODUCIBILITY.md)

The public demo needs no model API key. For your own project, connect the
[four scoped MCP tools](docs/CODEX_MCP_SETUP.md); proposals remain untrusted until Host review.

## Explore the implementation

[Architecture](docs/ARCHITECTURE.md) · [Graph Model](docs/GRAPH_MODEL.md) · [Core Cypher](docs/CORE_CYPHER.md) · [MCP](docs/CODEX_MCP_SETUP.md) · [Documentation](docs/README.md)

Core and Console run independently of the private OrderFlow Benchmark. The Console
is a **local read-only viewer**, not an authenticated hosted service. Live synthetic
observations and historical REPLAY are separate. The public synthetic publisher
is not the production TrustedHost/Q07 service. Historical FalkorDB SIGSEGV/139
root cause remains **UNVERIFIED**; durability and isolation limits remain explicit.

[Known limitations](docs/LIMITATIONS.md) · [Security](SECURITY.md) · [Contributions and AI disclosure](docs/HACKATHON_CONTRIBUTIONS.md)

MIT licensed. [LICENSE](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
