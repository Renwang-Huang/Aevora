# Gen2 synthetic MCP quick integration

The public demonstration uses the existing official SDK and V2Service. It is an
owned synthetic environment, not a production TrustedHost. Start the local Docker
demo first. The two path variables below are the same external files created by
the launcher; their contents must never be placed in a prompt or workspace.

```toml
[mcp_servers.aevora_demo]
command = "docker"
args = ["compose", "-p", "aevora-gen2-demo", "-f", "/absolute/public-clone/deploy/compose.yaml", "exec", "-T", "console", "python", "-m", "aevora.demo_mcp", "--state-dir", "/state", "--context", "threads"]
[mcp_servers.aevora_demo.env]
AEVORA_REDIS_CONFIG_FILE = "/outside-source/private-demo/falkordb.conf"
AEVORA_FALKORDB_PASSWORD_FILE = "/outside-source/private-demo/falkordb.password"
```

Only expose the four scoped tools to the Agent. Verify the exact configuration
in your installed Codex version; see the official documentation at
https://developers.openai.com/codex/mcp . This release tests actual MCP SDK calls,
not a new live Codex challenge. `record_decision` is CLAIM_ONLY;
`propose_experience` is PROPOSED_UNTRUSTED, not publication. Follow bounded pages
and keep query/recommendation/decision IDs from the same connection.

The demo graph identity and current public context are fixed by the trusted
launcher. Model claims cannot change them. DB credentials are read only by the
trusted server process. The Console has no write controls. Do not run the whole
trusted MCP server inside an untrusted business-code environment.

## Existing ordinary-project integration (legacy compatibility)

# Ordinary Codex MCP integration

Use an independently installed Core, a trusted Host `aevora serve` process and
one private scoped grant. The ordinary connector is stdlib and does not carry
the FalkorDB SDK/password. It reuses the existing byte proxy; the fixed-path
Benchmark Participant proxy is unchanged.

```sh
python3 h4/mcp_config.py --python "$(pwd)/.venv/bin/python" \
  --capability-file "$HOME/.local/state/aevora/product-session/grant.json"
```

Copy the generated stanza to your chosen Codex home/config.toml. It contains
only executable/argument paths. Keep an independent new Session; do not paste
maintainer instructions, hidden suites or old benchmark answers into it.
`codex mcp list` confirms configuration, not a successful real call. Verify
actual tools and structured results in the raw MCP events. Current pinned CLI
capability is checked dynamically; requested model labels do not prove weights.

The four tools are resolve_experience, build_evidence_bundle, record_decision,
and opt-in propose_experience. No Cypher, review, publish, withdraw,
source-orderflow or outcome-writing tool is exposed. Foreign Query IDs and
revoked owner grants fail closed. No request turns an external7-test result
into a VerifiedOutcome. A graph outage is an explicit error, never Replay.

Official references checked for H4:
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and
[official Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0).
The source uses installed SDK1.26.0; latest upstream v2 APIs are not substituted.

Local same-UID developer mode is not a hostile execution sandbox. Host
credentials must remain with the trusted owner; an untrusted Participant uses
the separately validated physical namespace and per-run transport. Ordinary
user authentication for a model service is configured by that user, not stored
in this package. The maintainer live demo uses the existing trusted Gateway
and physically isolated native runtime, with complete actual source pins.
