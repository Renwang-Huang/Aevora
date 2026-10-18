# Aevora Codex MCP integration

## Supported transport and scope

Aevora uses the official MCP Python SDK, pinned to 1.26.0, on the trusted host.
The isolated Codex runtime starts a standard-library stdio proxy. Its fixed
Unix socket is the only additional participant capability. FalkorDB authority,
its password file, private evaluation files and the trusted server source never
enter Participant. This transport does not schedule agents; official Codex
continues to create its own subagents.

The trusted launch header supplies a dedicated per-run bearer to the native
runtime. Codex forwards `AEVORA_RUN_TOKEN` and `AEVORA_RUN_ID` to its MCP child
through an explicit `env_vars` allowlist. The bearer is not placed in CLI
configuration overrides or command arguments. Its lifetime ends when the host
broker closes. Child sessions in the same run can share graph Query records;
they cannot turn a foreign run's Query into decision authority.

## Verified CLI configuration contract

Installed Codex 0.162.1 accepted the following configuration in an actual
fresh-CODEX_HOME `codex mcp list --json` probe. That probe verifies parsing only;
the gate evidence separately records transport and actual model tool calls.

```toml
[mcp_servers.aevora]
command = "/usr/bin/python3.12"
args = ["-I", "-B", "/aevora_mcp_proxy.py"]
env_vars = ["AEVORA_RUN_TOKEN", "AEVORA_RUN_ID"]
required = true
enabled = true
enabled_tools = ["resolve_experience", "build_evidence_bundle", "record_decision"]
startup_readiness = "connection"
startup_timeout_sec = 20
tool_timeout_sec = 60
default_tools_approval_mode = "auto"
```

`default_tools_approval_mode="never"` was rejected by the installed CLI. Its
accepted enum differs from the global `approval_policy`. The original failed
probe must remain a failure record in the H1 archive. The precise official
[v0.162.1 schema](https://raw.githubusercontent.com/openai/codex/rust-v0.162.1/codex-rs/core/config.schema.json)
has SHA256 `7933a70506e753a6e98c16800d2a76770b2af2b7295491f8f0b8e713e952027e`.

## Public tools and authority

- `resolve_experience(task_context)`: actual graph resolver; known facts in the
  pinned public environment cannot be overwritten by caller claims. Absent and
  unknown facts stay unknown even when Participant claims a concrete value.
  Only trusted pinned facts enter the applicability resolver. Participant claims
  are recorded separately in Query and response as
  `UNVERIFIED_NOT_USED_FOR_APPLICABILITY`; they cannot promote VERIFY to APPLY.
  A Query record binds returned candidates to Run.
  Its MCP readOnlyHint is false because this audit record is a real graph write.
- `build_evidence_bundle(experience_id)`: allowed only for an Experience
  actually returned to this Run. Its projection excludes private paths and
  verification implementation details.
- `record_decision(decision)`: requires actual current-run `query_id` and a
  candidate `experience_id`, `decision`, and bounded `reason`. VERIFY requires
  concrete `verification_steps`. Records are explicitly untrusted claims.
  Caller verdicts, verified flags, feedback and arbitrary authority fields fail.

There is no Participant `submit_outcome` or Cypher tool. Graph exceptions yield
an explicit error, with no fallback memory corpus and no inferred PASS.
The SDK's standard resources/prompts discovery routes may return empty
catalogs; the broker checks that they are empty. Resource reads, prompt fetches
and arbitrary URI requests remain denied. This supports native discovery
without adding resource or prompt capabilities to the three tools.

## Bounds, cancellation and evidence

The broker enforces kernel peer UID, run-bound bearer, fresh 256-bit connection
nonce, request-ID replay rejection, JSON size/depth bounds, a finite request
budget, at most four connections, and finite active-request waits. An idle MCP
connection does not impose a wall-clock deadline on a healthy completion-aware
agent. Owner exit closes sockets, revokes the bearer and reaps SDK children.

Authenticated raw JSONRPC messages and official SDK responses are archived with
direction, host timestamps, connection IDs and hashes of archived message
bytes. Headers containing credentials are never archived. Necessary redaction
is explicit. A host connection ID or kernel PID is not a Codex Agent ID; absent
native identity remains UNAVAILABLE. Official Codex JSONL and native rollouts
are independent evidence channels. Their actual tool events must be correlated
with the MCP records; prose is not a substitute for a native invocation.

Development tests contain clearly labeled synthetic service data to test the
real official SDK transport and denial behavior. Those tests do not prove a
live FalkorDB query or model challenge. G3 evidence must additionally include
the real deployment, an isolated participant probe and the fresh model run.

## Primary implementation references

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official SDK v1.26.0 stdio framing](https://github.com/modelcontextprotocol/python-sdk/blob/v1.26.0/src/mcp/server/stdio.py)
- [Official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Official Codex v0.162.1 exec MCP event fields](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/exec/src/exec_events.rs)
