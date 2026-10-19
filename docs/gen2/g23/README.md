# G23 Native collaboration and accountable transfer

G23 extends the existing Native Codex Adapter, four-tool v2 MCP Broker and private
TrustedHost. It does not implement a planner, scheduler or Agent runtime.

## Runtime contract

The maintainer CLI accepts `--experience-profile aevora.mcp/2.0.0-rc2`,
`--experience-v2-bootstrap /private/owned-bootstrap.json`, and explicit
`--enable-experience-proposals`. Legacy defaults and the Disabled Adapter remain.
Completion-aware runs use `--completion-policy completion-aware --agent-timeout
none --request-budget none`. Model concurrency, per-operation authorization,
finite transport retries, kernel/resource checks and trusted cancellation remain.

The owned bootstrap has exactly `binding`, `registry`, `facts`, `grant`.
`registry` must contain an immutable OS-owned `pin_root`. `grant` contains the
existing ReadGrant fields except run_id, which comes from the unchanged Runner.
The bootstrap's session_id names a scoped MCP capability session. It is never
presented as an official Codex thread. Every ancestor is opened without following
links; the file is owned, mode0600, single-link, regular and bounded to1MiB.
Known task facts must match this run's actual public manifest. Unknown before
facts remain unknown. No tool accepts this file, an executable, a pin root or
Host publication authority.

The bridge writes its run-specific SDK configuration into its private temporary
channel directory; Participant receives only the scoped socket and public proxy.
An empty initialized v2 graph is valid. No fallback to the legacy graph is allowed.

## Native source admission

The private `aevora_maintainer.native_source` verifies sealed original runtime,
Gateway, MCP, official exec and all own rollout files. The existing native parser
strips inherited child history, verifies typed spawn/session/task/tool/completion/
final/parent-receipt evidence, and now exposes official own-turn `McpToolCall`.
A successful proposal joins exact body SHA, native candidate ID, full structured
reply, connection ID, capability session and profile with its scoped Broker
request/reply. The actual proposing actor must be the completed root or a verified
child. At least one of that actor's official response IDs must match a completed
Gateway Responses request. Neither time proximity nor prose supplies identity.
Two actors proposing the same candidate are ambiguous and fail closed. Same
actor idempotent repeats remain possible. Host candidate idempotence also pins
the original native candidate ID. Patch/tree/run/suite/Outcome validation remains
in the original strict independent bridge, followed by the existing Q07 fence.

Legacy source validation remains available in the public package; the new Host
admission facade and source verifier stay private and outside product wheels.
Local protected collection is not third-party runtime attestation.

## Compatibility correction

A real controlled RLock seed exposed a G22 publication defect: necessary and
exclusion predicates on the same fact were schema-valid but rejected by witness
uniqueness. The validator now requires distinct `(mode,fact_key)` pairs; duplicate
same-mode predicates still fail. Existing arbitration evaluates their conjunction.
The actual red Host publication, red JUnit and green independent controls are
retained in the external G23 archive. No Oracle, reference or old assertion changed.

## Evidence and scope

Each new Native attempt has a distinct original Run/Session and is retained,
including Provider errors and missing contributions. Original grades are never
upgraded from offline diagnostics. A proposal is not approval; a recommendation
is not adoption; a successful code grade is not causal memory benefit. G24 formal
controls, G25 product work and G26 public release are not part of G23.

External authoritative reports and terminal manifest identify the final outcome.
