# H3 candidate lifecycle and trusted boundary

This extends the real FalkorDB repository and Schema 1.1, rather than replacing
them. `aevora.graph/1.2` retains the original 17 labels and adds Candidate,
LifecycleHead, CandidateEvent, SourceVerification and ExternalObservation.
Initialization verifies 44 unique/mandatory constraints. Legacy graphs and the
three original MCP tools retain their default behavior. Proposals are opt-in.

## State and provenance

```text
PROPOSED → EVIDENCE_PENDING → ADMITTED_BOUNDED → PUBLISHING → PUBLISHED
    ↓             ↓                  ↓              ↓           ↓
 REJECTED      REJECTED           WITHDRAWN       WITHDRAWN   WITHDRAWN/SUPERSEDED
```

The candidate body is immutable. The Host binds an actual run capability to
the proposal; caller-supplied authority, outcome, run identity and source type
are rejected. Public source references can identify actual same-run Queries,
Decisions and ObservedActions. The proposal is not a VerifiedOutcome and is
never a published retrieval candidate merely because it exists.

Trusted source verification re-reads sealed OrderFlow reports, JUnit, patch
integrity and the separate frozen evaluator source through the existing strict
Outcome bridge. For new native candidates it additionally matches the actual
MCP request/reply, typed official native tool completion and fresh thread ID.
An independent PASS supports bounded admission in the verified factual scope;
it does not prove adoption, useful transfer, universal validity or causal gain.
Every causal-benefit field remains UNKNOWN. Per-run authority does not identify
which individual child Agent authored a tool invocation.

Unverified external test output is stored as ExternalObservation with
EXTERNAL_UNVERIFIED/NOT_CREATED. It cannot acquire verified status through a
public proposal or a self-reported PASS.

## Concurrency and recovery

Each transition checks the expected head digest and appends its immutable event
and canonical edges while updating the head in **one actual GRAPH.QUERY write**.
Competing writers cannot both win the same head fence. Stale, illegal, changed
duplicate and lost-fence requests append audit records or fail closed. Event
IDs and request hashes make identical retries distinguishable from conflicting
reuse. A review grant is host-only, expires, and is never an MCP tool argument.

Publication uses retryable staging: PUBLISHING may already contain materialized
Experience/Rule/Evidence nodes, but the resolver excludes them. Only the final
PUBLISHED event and canonical PUBLISHED_FROM edge expose the experience. An
interruption requires a Host to inspect and retry the current staged head or
withdraw it. Multi-statement materialization is not a database transaction.
Retired candidates cannot be revived; replacement uses a separate candidate
and append-only history. Legacy QuerySnapshots retain their original epoch.

Inspection and source verification involve multiple real queries. They are
bounded validated observations, **not a serializable read snapshot proof**.
The immutable event chain and fenced state transition do not make arbitrary
multi-query graph read operations atomic. A compromised graph administrator
can alter the store; local hashes are not third-party attestation.

## Public package and Host CLI

Install `aevora_core/` independently. The root Benchmark package is explicitly
MAINTAINER_ONLY and contains private evaluation material. Never distribute that
package or install the administrative Core executable in a Participant with
database credentials.

The following is the supported command structure; deployment-specific values
belong in a trusted environment, never in Agent config or evidence exports:

```sh
python -m aevora init
python -m aevora health
python -m aevora query --run-id <new-id> --context <public-context.json>
python -m aevora inspect --candidate <candidate-id>
python -m aevora review --candidate <candidate-id> --state EVIDENCE_PENDING \
  --expected-head <sha256> --event-key <unique-key> --principal <host-id> --reason <public-reason>
```

Admission adds `--metadata` containing a verified source ID, restricted factual
scope and BOUNDED_SUPPORT_NOT_CAUSAL strength. Publication uses the same Host
review command with state PUBLISHED. Source verification is separately explicit
through `source-orderflow --anchor <host-pin.json>`. No review command is
available through the Participant MCP catalog.

`serve` starts the existing official-SDK broker, accepts a public context JSON,
writes a short-lived capability to an owned 0700 directory/0600 file, and
revokes it on SIGINT/SIGTERM. A consumer receives only the stdlib proxy and the
scoped Unix socket mounted at `/aevora-channel/mcp.sock`; it receives no Redis
client, password or admin CLI. The public package itself does not implement a
VM/container system. The deployment must isolate the Host account/credential
files from the consumer. Merely setting cwd is not a security guarantee.

## Security and known platform limits

Inputs are length/count/type bounded, facts use the existing semantic allowlist,
queries are parameterized, references must belong to the scoped run, and public
text rejects credential-like strings, private paths and common instruction
payloads. Treat retrieved text as untrusted data. These checks do not prove
general prompt-injection immunity. Grant possession is an operating-system
trust decision, not a public-key signature protocol.

H3 retains RDB SAVE/checkpoint recovery at its last completed boundary. It does
not fix the known AOF exit139, guarantee zero RPO, remove the runtime EOL issue,
or upgrade shared-kernel hostile isolation to unconditional PASS. Original
Native UDS public-test EPERM evidence remains; the safe in-process public entry
preserves business assertions but does not test cross-process Clock transport.
