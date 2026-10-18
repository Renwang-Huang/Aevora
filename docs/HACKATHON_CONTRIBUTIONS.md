# Hackathon contribution and development provenance

**Aevora's hackathon entry centers on the Gen2 system designed, implemented and integrated during October 15–18, 2026: graph-native experience arbitration, trusted publication/evolution, accountable native-agent transfer, and the working product delivery.** Reusable infrastructure is credited separately below.

Primary track: **Agent Memory and Coordination**.

## Core work completed during the event

The official event window is October15 00:01 to October18 23:59 IST (UTC+05:30). The table uses original Git timestamps in UTC+08:00. Both author and committer times are preserved in the [verified contribution timeline](CONTRIBUTION_TIMELINE.csv).

| Contribution | Original implementation/design record (UTC+08:00) | Source commit |
|---|---|---|
| Gen2 architecture and contract freeze | Oct15 19:08 | `0aa5f25fab28` |
| Graph v2 schema, tenant/scope contracts and complete Witness reader | Oct15 23:42 | `3a638b76c5c9` |
| Deterministic graph-native WHEN/WHY arbitration | Oct15 23:42 | `d03de43ff4d4` |
| Trusted v2 Source/Outcome admission and immutable preparation | Oct16 02:03 | `bf319920e53d` |
| Q07 fenced publication, governance and revocation | Oct16 02:27 | `a1167d1be8a9` |
| Native-v2 actor/proposal provenance and accountable transfer integration | Oct16 10:30 | `b2b4ff5c65cc` |
| Gen2 Decision Journey, real graph demo and reproducible delivery | Oct18 15:03 | `d7215350c2a7` |

These are substantive source/design changes, rather than dates assigned by a later public export. The timeline identifies new v2 mechanisms and extensions to reused components. Earlier WHEN/WHY ideas, Host interfaces and native tooling are not represented as having first existed during this event.

G21/G22 source seals and the historical G23 Native evidence associate these implementations with actual validation. The historical S1/S2 runs each have28/28 original Oracle checks; **S2 Core APPLY / Agent VERIFY** and Host-approved follow-up remain distinct. See [Native transfer](NATIVE_TRANSFER.md). The final product integrates these mechanisms with public setup, real FalkorDB reads and a [working demo video](https://youtu.be/g5KCv_stZhg).

## Reusable foundations and their role

Preparatory work provided OrderFlow Benchmark research, first-generation Core/lifecycle and Host interfaces, an SDK/scoped MCP transport, native Codex integration, isolation, an earlier Observatory and packaging tools. These supported development and validation; they are attributed as reused foundations, not counted as newly written Gen2 mechanisms. The private Benchmark and raw records remain separate from the public product. Historical GraphSwarm names identify origin/compatibility, not the current brand.

The submitted contribution is the event-developed Gen2 design, core implementation and integrated Aevora product described above. The existence of those foundations does not by itself date completion of this submitted system.

## Evidence and AI assistance

- [Contribution timeline](CONTRIBUTION_TIMELINE.csv): specific event contributions, source hashes, original author/committer timestamps and affected paths.
- [Earlier source map](CONTRIBUTION_SOURCE_MAP.csv): retained last-change snapshot, including reused files. A last-change timestamp alone is not a file-creation date.
- Source commits come from the maintained engineering history; the public product export has its own Git history. Source hashes are provenance references, not claims that private maintainer commits or raw Oracle evidence are hosted in this public repository.
- OpenAI Codex / GPT-6.1 Sol (xhigh) supported final engineering and review. Earlier Codex native teams supported implementation/validation. Separate DeepSeek G24 work and its protocol/failures are not pooled with Codex results. The human owner directed scope, reviewed and verified the work, and is responsible for explaining it.
- The bundled G24 controlled comparison remains NOT_RUN and statistical causal benefit UNKNOWN. Final presentation work does not constitute a new Native model challenge.

Original dates, prior code, failures and historical evidence are preserved. Registration and formal submission are owner actions. [Official rules](https://www.wemakedevs.org/hackathons/falkordb/rules).
