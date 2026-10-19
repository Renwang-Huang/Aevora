# M1.1 R0 — Baseline and Failure Hypotheses

## Scope and provenance

This is the pre-edit R0 record. Existing M1 working-tree bytes, not Git HEAD alone, define the baseline. Historical results remain TIMEOUT / PASS / TIMEOUT (automatic closure 1/3). Two separate postmortem evaluations passed 28 tests; they do not change those original results. New evidence lives under `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/`.

Current branch: `m1-1-runtime-calibration-evidence`; HEAD `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`. Dirty M1 source and user files were preserved. `M1_BASELINE_SOURCES.json` records 159 source/document hashes, `PROTECTED_HISTORY.json` records 82,740 protected historical hashes. Dynamic pre-edit byte verification passed both collections. Local hashes are not third-party attestations.

## Actual pre-edit execution

- `python3 scripts/phase35_record.py <archive>/r0-developer-command scripts/python312 -m pytest -q --junitxml=<archive>/r0-developer.junit.xml`: exit 0, 664 tests, zero failures/errors/skips, 2026-10-10T15:48:54.161554Z–15:50:59.189617Z, 125.028 seconds. All 664 identities were saved separately, original test source bytes copied into `baseline_tests/`.
- `python3 scripts/phase35_record.py <archive>/r0-integrity-command python3 <archive>/verify_baseline.py`: exit 0, 82,740 historical +159 source files unchanged, 30.775 seconds. Receipts/stdout/stderr are retained.
- `codex --version`: exit 0, actual CLI 0.162.1. `codex exec --help` and `codex features list`: exit 0; raw outputs saved. Official config documents support `agents.enabled`, `features.multi_agent`, provider `stream_idle_timeout_ms`, retry counts. No unsupported request timeout setting will be invented.

## Historical terminal evidence versus hypotheses

| Original Run | Original runtime | Watchdog wall / process-tree CPU | Meaning |
|---|---|---|---|
| fbaae2cb-586f-4573-9cda-035eb7f608a0 | TIMEOUT | 1200.011 /121.91 seconds | Actual wall-clock resource violation, not measured CPU/OOM or hidden business FAIL; original evaluation NOT_RUN |
| 48cddbed-6410-44e1-b860-142edef5e3ab | PASS | natural completion1139.1185 seconds; CPU120.04 | Actual automatic closure, 28 hidden tests PASS |
| 463674bc-afba-4959-bb63-cda945c63b5a | TIMEOUT | 1200.032 /127.69 seconds | Actual wall-clock violation; child task included genuine 429 exhaustion; original evaluation NOT_RUN |

These fields originate in the old M1 raw runtime/watchdog/Broker records and timeline. They do not prove exactly when a correct patch first existed, nor that either interrupted team had finished collaboration. Those claims remain UNVERIFIED. Trial1 offline evaluation overlapped Trial2 live execution; new pilots will avoid concurrent heavy maintainer work.

## Layer inventory and minimal intended changes

| Layer / actual location | Trigger | Observed or static status | Minimal change |
|---|---|---|---|
| `integrations/codex_agent.py:35,56,252` | positive timeout<=7200; communicate kills process group on wall deadline | static + historical two terminations | explicit bounded versus completion-aware; None means no total deadline; preserve old defaults |
| `benchmark/resources.py:32,44,216` and inner Participant watchdog | unconditional total wall comparison | historical violation + static | allow explicit None wall only; retain CPU/memory/pids/output and cleanup |
| `benchmark/cli.py:35-36` | defaults900 seconds/160 requests | static | explicit policy/budget-none, mode/status/cancel/snapshot |
| `integrations/gateway_broker.py:142,383,396` | 120-second total HTTP response timer, even with streaming progress | historical request timeouts + static | distinguish first-response/real SSE idle from total response, append complete request events |
| Gateway Broker token lifecycle, lines144/455 | TTL1800 independent of live owner | static hidden ceiling | bind active run/token revocation to lifecycle; no fixed research total cutoff |
| `integrations/participant_bridge.py` | HTTP bridge130-second socket wait | static | coordinate nonsecret transport policy; preserve UDS-only auth/network boundary |
| native CLI config `codex_agent.py:99-101` | idle120000ms/retry2 per request/stream | static official supported knobs | explicit truthful idle/retry settings; no binary modification/fake SSE |
| Gateway error propagation | Retry-After lost; permanent4xx may become502 | static | forward valid real Retry-After; finite retries/permanent classifications |
| `integrations/model_broker.py:44,170,196` | legacy broker timeout<=120 | static, legacy production path already blocked | preserve legacy compatibility; document inactive scope |
| `scripts/m1_live_pilots.py:23,38` | Agent1200 + collector1380 and fixed Gate | static | new separate M1.1 collector without total cutoff; old sealed collector/results unchanged |
| Runtime cleanup/control | current kill-group/watchdog cleanup; no trusted Run-specific cancel index | static existing cleanup tested baseline | atomic host control bound to Run/process identity, classify operator cancellation distinctly |
| `benchmark/evidence_export.py` / standalone verifier (new) | old archive huge, duplicate reports/workspaces | measured below | independent read-only export, CAS/compression, honest omitted pointers, strict offline verification |

Slow first byte/ongoing SSE/actual child work are not evidence of deadlock. Liveness must come from transport bytes, official events and process observations; missing attribution is UNAVAILABLE. Provider permanent errors, real resource violations and operator cancellation stay separate from task correctness.

## Actual archive scale (read-only)

Old M1 sealed manifest covers 44,085 regular files /6,444,877,841 bytes. Manifest SHA+actual lstat grouping:25,652 unique hashes,18,433 duplicate files; duplicate bytes2,582,644,201 (40.07%). No nonregular entries or same-SHA/size conflicts were found. This grouping used sealed hashes; the independent current byte scan above verified actual protected bytes.

Largest classes: JSON about4.20GB, logs about2.22GB. Largest directory groups: repeatability-accepted about2.20GB, repeatability about1.30GB, recovery matrix about1.01GB. Repeated full reports/stdout commonly25–33MB. Exact provenance is the original sealed manifest, not a claim that every duplicate may be deleted. Historical full archive will remain intact. Audit-Lite will contain complete necessary small raw events/reports or explicit slices, and NOT_INCLUDED pointers for omitted heavy assets; it cannot independently verify omitted bytes.

## Additional environment risks

Python3.12.13 /SQLite3.46.1 /pytest9.1.1 are the existing M1 execution stack. Current SQLite official WAL documentation describes a WAL-reset race version range including3.46.1. Occurrence in this Benchmark is UNVERIFIED; no historical score, D-v01 truth or dependency is changed on that basis. Future v02 implementation should freeze a fixed library or isolate the library-level risk.

## R0 decision

PASS for pre-edit baseline/diagnosis only. R1–R4 are not completed by this gate. No core/test source edits preceded the 664-test and byte-integrity checks. Next gates must provide real dynamic evidence, including six new sessions after runtime and export safety gates.

Primary capability sources: https://learn.chatgpt.com/docs/config-file/config-reference ; https://learn.chatgpt.com/docs/agent-configuration/subagents ; https://learn.chatgpt.com/docs/non-interactive-mode . Archive format references: Python zipfile and RFC8493. Local installed help/config validation remains authoritative when capabilities differ.
