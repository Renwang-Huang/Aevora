# Aevora H2 — authorization, isolation and failure closure

## Scope and authority

H2 retains the H1 architecture: official Codex owns native collaboration,
Aevora's trusted host runs the official MCP Python SDK, and OrderFlow owns
Submission Fidelity and independent engineering evaluation. No security probe
in this document calls a model or executes an Agent challenge.

The H2 probe source is `scripts/aevora_h2_security.py`; new contracts are in
`tests/test_aevora_h2_security.py`. These additions do not modify the existing
MCP Broker, native sandbox, Evaluator, business code or historical results.
They reuse current production interfaces, actual Unix sockets, kernel
`SO_PEERCRED`, the pinned official SDK and existing bubblewrap boundaries.

MCP's stdio authorization is a host transport responsibility rather than the
HTTP OAuth flow. The separate Run capability is never passed through as the
database password or upstream provider credential. This follows the
[official MCP transport guidance](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/basic/index.mdx)
and its [scope minimization and proxy security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).
Kernel peer UID establishes a local process boundary, as specified by
[Linux unix(7)](https://kernel.googlesource.com/pub/scm/docs/man-pages/man-pages/+/refs/tags/man-pages-6.13/man/man7/unix.7).
It does not establish an individual Codex Agent identity.

## Current-run authorization and evidence

The authenticated channel authorizes only `resolve_experience`,
`build_evidence_bundle` and `record_decision`. The actual SDK catalog is checked
against those three names. Admin, arbitrary Cypher, Outcome submission, URI
reads and replayed request IDs close the connection and leave a Broker rejection
event. Wrong token, foreign Run and wrong kernel UID fail before starting the
official SDK. Already used nonces fail on a new connection.

The actual H2 graph probes preserve both the client request/response stream and
the Broker's official SDK stream. Raw JSONRPC bytes have hashes scoped to the
archived bytes. Authentication headers are explicitly sanitized before archival;
the removed token is not claimed to be recoverable from the archive. The token
is never a command-line argument. Connection IDs and local PIDs remain different
from official Codex thread IDs; unavailable Agent identity stays `UNAVAILABLE`.

`build_evidence_bundle` requires a Query that returned the experience to this
Run. A different Run cannot claim that Query or request the same bundle without
its own query. Private verification, hidden tests, private Manifest paths and
reference patches must not appear in the public bundle.

`record_decision` accepts a bounded untrusted claim. A reason containing
`MATCH(n) DETACH DELETE n`, a forged Outcome instruction or a private file URI
is stored as data through the existing parameterized repository. It remains
`UNTRUSTED_PARTICIPANT_CLAIM / CLAIM_ONLY / UNKNOWN`. Caller `verified`,
`verdict`, `authority` and `outcome` fields are rejected. The probe compares
every existing VerifiedOutcome ID and payload digest before and after the
attacks; telemetry may grow, trusted outcomes must not change.

Known public premises cannot be overwritten by claims. An empty trusted context
remains empty even when a Participant supplies concrete topology claims; those
claims cannot promote a candidate to APPLY. This tests the machine authority
boundary. It **does not prove that a model is immune to prompt injection**.

## Expiry, slow healthy sessions, cancellation and errors

Two authorization modes have different purposes:

| Channel policy | Admission and expiry |
|---|---|
| Bounded Gateway test/legacy mode | Finite TTL and owner lifetime; actual elapsed expiry yields 401 without contacting upstream |
| Completion-aware Gateway | TTL is `None`; identity ends on owner cancellation/close |
| Aevora MCP | Owner lifetime; idle gaps do not trigger a fixed wall deadline; each active request has a finite deadline |

H2 does not reintroduce a fixed lifetime that kills normally active long Codex
sessions. The new TTL contract first completes an authorized request, waits for
the actual monotonic expiry, then observes 401 and unchanged upstream request
count. It uses an owned fake upstream and a dedicated test key, never a real
provider key. A separate actual MCP probe closes the owner while a connection
remains open, verifies that its next request has no successful response, and
verifies that a new connection to the removed socket fails.

The runtime-contracts mode replays existing real socket/process contracts for
slow first responses, SSE intervals, 429/Retry-After, permanent 4xx, cancellation,
wrong-run control, timeout, no patch, invalid patch, incomplete trace, startup
failure, process cleanup and resource limits. Their upstream and CLI fixtures
remain labeled synthetic. Passing these tests proves transport/classification
behavior; genuine provider compatibility and native collaboration require the
separate H2-G3 new Sessions.

Existing result semantics remain intact:

| Human-facing category | Existing archived fields |
|---|---|
| ERROR | `ExecutionStatus.ERROR`, exact `failure_kind` retained |
| TIMEOUT | `ExecutionStatus.TIMEOUT` |
| CANCELLED | `ExecutionStatus.CANCELLED` |
| PROVIDER_ERROR | ERROR + `failure_kind=PROVIDER_FAILURE`, correlated last response evidence |
| NO_PATCH | ERROR + `failure_kind=NO_PATCH`; no invented submission or engineering Outcome |

An owned non-listening port gives an actual graph connection failure. The
official SDK returns `AEVORA_GRAPH_UNAVAILABLE` with `isError=true`, no structured
success and no fallback corpus. Killing only the dedicated probe SDK process
produces channel closure and cleanup, without a fake successful tool result.

## Physical three-layer verification

The same generated public D-v01 package is run under three existing policies:

1. **Outer Participant Runtime:** receives only the selected per-Run read-only
   Unix socket and stdlib proxy. Actual MCP initialization and exact tool catalog
   work; original host socket path and parent are not visible.
2. **Official Native Command Sandbox:** retains workspace-write/never policy.
   The command cannot create/use the MCP/network socket. `EPERM` during socket
   construction is recorded as a real denial, not treated as absence of a test.
3. **Candidate Business Sandbox:** has no MCP capability, no model capability
   and no host network. Public `app/service.py` remains available.

All three attempt existing hidden/reference/private/source/maintainer targets,
an explicitly synthetic admin credential and another synthetic Run result.
`/proc/1/root` and workspace traversal forms are included. The script only opens
and closes denied files or lists directories; it never asks a Participant to
read a genuine credential's contents. Every target must first exist on the
trusted host, preventing nonexistent-path probes from masquerading as access
control. A dedicated owned loopback listener records zero successful
connections. No unknown services or production database are scanned.

The first H2 physical execution correctly observed Outer and Candidate denial,
but its Native probe placed `socket()` outside the exception boundary and exited
1 on the native sandbox's real `EPERM`. That failed execution is preserved. The
probe-only correction moves construction inside the denial check; it does not
change any sandbox policy or weaken the requirement that access fail.

## Reproduction commands

Create a new output directory for each invocation. The required H2 graph is
loopback 17679 and has an `aevora_h2_` name; the script refuses H1's 16379/graph.
The administrator password is supplied only through the existing trusted
launcher slot. The shell variables below denote paths, never credential values.

```sh
# Direct new contract verification; existing synthetic contracts are also reused.
scripts/aevora-python -m pytest -q tests/test_aevora_h2_security.py
scripts/aevora-python scripts/aevora_h2_security.py runtime-contracts "$new_evidence/runtime"

# Official SDK calls against the separately prepared real H2 graph.
AEVORA_FALKORDB_PASSWORD_FILE="$trusted_h2_password_file" \
AEVORA_FALKORDB_PORT=17679 AEVORA_FALKORDB_GRAPH=aevora_h2_g0 \
scripts/aevora-python scripts/aevora_h2_security.py mcp "$new_evidence/mcp"

# ORDERFLOW_ENABLE_CODEX mounts the current official binary in the trusted
# launcher only. This physical probe performs zero model requests.
ORDERFLOW_ENABLE_CODEX=1 \
AEVORA_FALKORDB_PASSWORD_FILE="$trusted_h2_password_file" \
AEVORA_FALKORDB_PORT=17679 AEVORA_FALKORDB_GRAPH=aevora_h2_g0 \
scripts/aevora-python scripts/aevora_h2_security.py isolation "$new_evidence/isolation"
```

Wrap commands with the H2 recorder so argv, UTC timestamps, exit code, stdout,
stderr and their hashes remain traceable. No command should reuse H1 Full or
overwrite a previous H2 evidence directory.

## Acceptance and remaining limitations

The probe `summary.status` describes only its necessary checks. It always
reports `overall_security=PARTIAL`. Linux namespaces, sampled CPU/output limits,
administrator authority, timing channels and local attestation do not become a
VM or hostile-kernel guarantee because ordinary tests pass. A database password
remaining outside the namespace is a tested path/capability property, not a
proof against every kernel vulnerability. H2-G3 must separately freeze final
source fingerprints and verify real model connection, true Subagent events,
unaltered original submissions and independent evaluation.

Exact current commands, denominators, hashes, first failure and corrected
execution are in the independent H2 archive's `security/` and recorder receipts;
they are current H2 results, not retroactive credit for the older H1 live source.
