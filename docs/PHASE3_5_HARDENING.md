# Phase 3.5: hardened Gateway runtime

This phase repairs submission fidelity and adds a project-specific Gateway transport. It does not implement Episode B/C/D or experience governance. Historical Phase 1–3 reports remain unchanged; current evidence is under `phase3_5_validation/`, selected by `CURRENT`.

## Submission authority

The trusted Runner interprets a bounded UTF-8 unified diff independently, checks the original file sections with Git in a fresh repository with an empty template and explicit configuration, and compares exact bytes. It publishes `app` using Linux atomic directory exchange only after all checks pass. Empty additions/deletions, mixed operations, no trailing newline and parent Git layouts are covered. Rename/copy/binary, traversal, symlinks, hardlinks and special source files are rejected.

Every patch records baseline tree, original patch, expected tree, applied candidate tree SHA256 and per-file hashes. Automatic submissions must also match the runtime artifact digest and all extraction-time hashes. A missing or changed extraction record prevents hidden evaluation. Manual submission remains supported by the same verifier.

## Model and credentials

New live CLI runs use `gateway`, the authorized HTTPS hostname `api.renwang-huang.top`, Responses wire protocol, `gpt-5.6-terra` and explicitly selected `max`. The API root is `/v1` only after the archived live discovery verifies it. There is no automatic provider, model, effort, proxy or TLS fallback.

The trusted broker alone opens the project API key. The participant receives a bounded, short-lived per-run channel token through a private stdin pipe; it never receives the upstream key. The token is not part of archived command arguments or the exact native prompt. The bridge passes the original prompt bytes to Codex stdin after consuming the private launch header.

This is a third-party Gateway: public issue text, public source and public test observations may be sent to that service. Hidden assertions, private manifests, reference repairs, other runs and maintainer files are outside the participant mounts. Model and effort fields returned by the Gateway are reported as observed API metadata, not independent attestations of upstream model weights or compute.

## Three boundaries

1. Outer participant: explicit public workspace and fresh state, read-only official Codex/Code Mode binaries and tools, private network namespace. The sole external channel is a per-run Unix socket to the trusted broker. The namespace-local loopback bridge has bounded clients and timeouts.
2. Native command sandbox: official Codex `workspace-write` with `approval_policy=never`; no bypass or custom agent scheduler. Code Mode and `code_mode_only` are explicitly enabled and uses the official bundled helper. The tagged `gpt-5.6-terra` catalog declares `code_mode_only`; the new runtime verifies actual outgoing tool schemas instead of assuming flat shell tools are compatible. Native v1 collaboration is explicitly retained for the verified exec evidence contract.
3. Candidate: read-only business code plus temporary SQLite data, separate PID/mount/network namespaces, no model socket, token or credentials.

Broker authentication checks per-run token, TTL and peer UID; only models and responses routes, the nominated model/effort, bounded requests/concurrency/body/output and validated TLS are allowed. Wrong and cross-run tokens fail before upstream access. HTTP redirects and environment proxies are disabled.

The historical low-level participant helper retains its old default for offline contract compatibility. New live entry selects strict mode explicitly. `--provider legacy` is blocked by the new live CLI until that transport is hardened. Existing legacy broker contracts and historical evidence remain available; they are not a Phase 3.5 security guarantee.

## Resources and limits

Outer runs require delegated cgroup v2 memory/pids controls, and fail with `BLOCKED_SECURITY_GATE` if unavailable. The initial frozen validation series used 900 seconds wall. The corrected recovery series overrides wall time to 1200 seconds for all three runs; the CLI default remains finite. Both profiles retain 600 sampled aggregate CPU seconds, 2 GiB memory, 768 tasks, 2 TiB per-process virtual address space, 64 MiB per file, 128 MiB sampled output and 10,000 entries. Native maximum concurrent agent threads is four; broker concurrency is four and total upstream request budget is 160.

Candidate limits preserve 200 simultaneous real threads: 90s wall, 45s CPU, 512 MiB sampled RSS, 4 GiB address space, 512 tasks, 16 MiB per file, 32 MiB sampled output and 2,000 entries. The independent kernel probe also validates 200 threads under a 512-task cgroup.

CPU controller delegation is unavailable on this host: inherited hard per-process RLIMIT_CPU and a 50ms aggregate watchdog are used. Very short reaped children may evade CPU accounting. Output/count limits are sampled, not filesystem quota. Candidate aggregate memory/task limits in ordinary evaluator runs are sampled rather than dedicated kernel cgroups. These boundaries require a CONDITIONAL security conclusion for a fully adversarial workload, even when file/network and cooperative runtime gates pass.

Gateway uses the official CLI finite retry fields: two HTTP retries and two stream retries, with unbounded connection retries disabled. Every retry consumes the same 160-request broker budget; a persistently failing nested HTTP/stream path can make at most nine Responses attempts before the CLI error, with wall and request caps still applying. Local synthetic tests verify recovery and exhaustion; real challenge results are archived separately. Legacy retry fields remain zero.

No container escape resistance or third-party immutable storage is claimed. Public inputs and exact stdin are sealed before launch; final manifests use exclusive creation and local hash linkage. A trusted host owner can still change local bytes and hashes. Gateway sessions use a fresh per-run CODEX_HOME without `--ephemeral`: native child context forks need this run’s public rollout. After all writers are stopped, bounded regular session JSONL files are credential-redacted and archived under `artifacts/native_rollouts/`; the state directory is then removed. No prior maintainer or participant history is reused. Tool and lineage evidence must be read from actual structured records; missing child records remain UNAVAILABLE. The official Code Mode helper reserves roughly 1.35 TiB of virtual space in the local probe, while physical RSS remains small. The 2 TiB virtual limit permits that reservation; cgroup physical memory remains 2 GiB.
