# M1.1 Remaining Issues

> Six new Sessions are closed: 3 Single / 3 Multi. One real Provider failure remains in the denominator; five submitted patches passed the unchanged 28-test suite. Acceptance, exact Run IDs and measured counts are recorded in `M1_1_VALIDATION_REPORT.md` and `M1_1_DIFFICULTY_CALIBRATION_REPORT.md`. This document does not alter an older grade.

## Observable boundaries

- **Realtime Code Mode child indexing is PARTIAL.** `codex exec --json` does not expose every Code Mode fork association. A live `child_states={}` is not proof that there are no children. Official child `session_meta` and the final own-session rollout can establish actual children; the terminal verifier remains authoritative for delegation, own work, completion and parent receipt. Do not invent live child states or completion events.
- **Initial assignment plaintext is UNAVAILABLE** where the installed runtime records encrypted or opaque Code Mode messages. Actual IDs, parent associations, own tool activity and return receipts remain separately verifiable. Role configuration alone is not evidence of a role being run.
- **First changed tree is not hidden-test readiness.** Live snapshots are non-atomic observations. No hidden evaluation occurs at that first observation. The later submitted patch and applied tree have their own hashes and independent results.
- **Phase timing is incomplete.** HTTP first response, observed SSE gaps, request terminal durations and overlapping request intervals are recorded. Their sum is not elapsed wall time. The remainder is not pure reasoning time, and exact causal attribution of client disconnects is unavailable without supported native telemetry.
- **An active request's provisional `outcome` field is not a terminal error.** Use its event type/activity and the later `REQUEST_FINISHED` record, plus terminal error counters, when interpreting the raw transport log.

## Runtime and security boundaries

- `completion-aware` removes total wall-clock and optional total request-budget limits; it preserves finite connection checks, configurable native stream-idle handling, finite supported retries, model concurrency, cgroup memory/pids and sampled CPU/output limits. These limits can still terminate a real fault. This is not unlimited resource access.
- The external Gateway can fail even when the integration behaves correctly. Keep every started Session in the denominator. Operator continuation of a stopped collector is not native Session resume or replacement of a failed Run.
- Isolation uses actual Linux namespaces, mounts, scoped Broker access and cgroups. It is not a VM or proof against every hostile exploit. CPU controller delegation and ordinary Candidate resource limits retain the prior declared boundaries. Canary probes do not establish that an untrusted process safely attempted to read a real secret.
- A normal operator cancellation is verified. Abrupt trusted-host `SIGKILL`, host power loss or kernel failure can bypass `finally`; automatic recovery/resume from those events has not been implemented or validated.
- A host project credential scan can establish absence of its exact bytes and selected encodings in inspected files. It does not prove absence of arbitrary encryption, split encodings, unrelated credentials or covert channels. The key and its digest must never be retained.

## Evidence and research boundaries

- Local SHA256 manifests and deterministic exports prove byte consistency under the declared source references. They are not third-party execution attestation or immutable storage. An independently obtained verifier and externally supplied digest are required for a meaningful external check.
- Audit-Lite validates included, sanitized evidence and original-byte pointers. `NOT_INCLUDED` data is not independently byte-verified by the package. Full Archive remains the source for private replay and omitted raw data; neither archive is Participant input.
- API response labels establish observed provider/model/effort labels; they do not prove remote model weights. An actual monetary bill is unavailable.
- Six interleaved trials are exploratory. Provider failure, prompt differences needed to enable/disable native collaboration, shared host conditions and Gateway variability limit causal inference. No statistical Single/Multi superiority or experience-governance benefit is established.
- D-v02 is a reviewed design only. No business implementation, hidden suite, reference patch, registry entry, dynamic difficulty result or migration benefit is claimed. The old SQLite library's applicability to a newly proposed backup scenario requires a separately frozen, supported future environment; no old score may be changed based on a speculative library issue.

## Resolved post-calibration evidence defect

- Trial 6 originally recorded three spawned and two verified children. Its investigator had real own-session work, exact final answer, typed `task_complete` and a matching parent receipt. A one-sided whitespace normalization produced a false negative. A separate replay uses the unchanged raw bytes and records the correction; the original summary, score, seal and analysis are retained.
- Both runtime parser and independent verifier were tightened to preserve final-answer whitespace and compare the complete typed parent receipt body. Changed body or whitespace is rejected. New strict tests are additional to all original tests. These parser versions were finalized **after** the six challenge Sessions; they are not attributed to the frozen challenge runtime. Current hashes, actual regression counts and correction receipts are in the final evidence index.

## Stop boundary

Stop after M1.1. Episode B/C, D-v02 implementation, GraphSwarm, FalkorDB, MCP and formal G0–G3 experiments remain outside this authorization.
