# Aevora

**AI agents shouldn't just remember what worked. They should know when to trust it.**

*Evidence-governed experience reuse for coding agents, powered by FalkorDB.*

**[▶ Watch the demo on YouTube](https://youtu.be/g5KCv_stZhg)**

[Run locally](docs/QUICKSTART.md) · [Explore the graph](docs/GRAPH_MODEL.md) · [Connect via MCP](docs/CODEX_MCP_SETUP.md)

## When yesterday's fix becomes today's bug

A coding agent fixes an inventory race with **one shared process-local lock** around the read/write. Another agent encounters a similar race, but its workers run in **different processes**. The remembered fix is relevant; the assumption that made it safe is not.

**Aevora treats past experience as evidence to evaluate, not advice to obey.**

### One remembered fix. Three decisions.

| Context | Core | Reason |
| --- | --- | --- |
| **Shared threads** | **APPLY** | Every writer shares the process and lock. |
| **Unknown topology** | **VERIFY** | Check the missing process premise. |
| **Separate processes** | **ABSTAIN** | The lock cannot span processes. |

These are real FalkorDB-backed recommendations in the public **synthetic demo**, not claims that an LLM executed these examples. [Reproduce the cases](docs/DEMO_WALKTHROUGH.md).

## Why a graph changes the decision

Aevora connects experience to prerequisites, supporting and contradictory evidence, verified outcomes, trusted authorities and revisions. **FalkorDB is queried to determine the recommendation, not just to store retrieved text.**

- **WHEN** — Check scope, premises, active revisions and permissions.
- **WHY** — Return a complete graph **Witness** of support and counterevidence.
- **ACCOUNTABILITY** — Separate Core advice, the agent's recorded choice, code action and independent evaluation.
- **FEEDBACK** — Trusted Host review gates publication, revision and withdrawal. A proposal alone is untrusted.

A false premise can lead to **ABSTAIN**; a missing premise to **VERIFY**. Withdrawal changes which revisions are admissible. [Graph model](docs/GRAPH_MODEL.md) · [Actual Cypher](docs/CORE_CYPHER.md) · [Arbitration source](aevora_core/src/aevora/arbitration.py)

## Across real agent sessions

**S1: patch + independent Oracle → Trusted Host: source/Outcome verification + Q07 publication → Fresh S2: retrieval + its own patch + independent Oracle**

The historical G2-3 Codex Native Multi-Agent runs each had three verified children and **28/28 original independent Oracle checks**. In S2, **Core recommended APPLY; the agent recorded VERIFY**. S2's added support was a **Host-approved follow-up**, not direct publication of its natural proposal.

This is cross-session mechanism evidence. The bundled G2-4 comparison is **NOT_RUN**; statistical causal benefit remains **UNKNOWN**. Original private model/Oracle records are not shipped. [Evidence and limitations](docs/NATIVE_TRANSFER.md).

## Try it locally

Docker Compose and Python 3.10+; no model API key required:

```sh
python3 scripts/aevora_public_demo.py start \
  --project aevora-gen2-demo \
  --secret-dir "$HOME/.config/aevora/public-demo"
```

Open `http://127.0.0.1:19064/journey.html`. Live panels read real FalkorDB using **LIVE SYNTHETIC** inputs. Historical native-agent records are separately labeled **REPLAY**.

<details>
<summary><strong>View actual Console screenshots</strong></summary>

[Activity & Decisions](docs/assets/activity-decisions.png) · [Experience Explorer](docs/assets/experience-explorer.png) · [Governance Timeline](docs/assets/governance-timeline.png)

![Actual Console capture: APPLY, LIVE_SYNTHETIC_DEMO, observation time and no-model-execution labels intact](docs/assets/rc12-activity-decisions-viewport.png)

Archived browser pixels are unchanged. [Capture provenance](docs/assets/RC12_VISUAL_PROVENANCE.json).

</details>

[Quickstart](docs/QUICKSTART.md) · [Reproducibility & tests](docs/REPRODUCIBILITY.md) · [MCP setup](docs/CODEX_MCP_SETUP.md)

## Technical documentation

[Architecture](docs/ARCHITECTURE.md) · [Graph v2 & Cypher](docs/GRAPH_MODEL_AND_CYPHER.md) · [Standalone Core](docs/STANDALONE_CORE.md) · [Documentation index](docs/README.md)

**Boundaries:** The Console is a local read-only viewer. The public synthetic publisher is separate from production Trusted Host/Q07. Historical FalkorDB SIGSEGV/139 root cause remains **UNVERIFIED**. [Limitations](docs/LIMITATIONS.md) · [Security](SECURITY.md) · [Contribution provenance & AI disclosure](docs/HACKATHON_CONTRIBUTIONS.md).

MIT licensed. [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md).
