# G21 — Graph-native arbitration

Status is in external G21_IMPLEMENTATION_REPORT and final delivery receipt. This directory revises rc1 entry contracts and describes the actual rc2 read-side implementation. Original docs/gen2/g20 stays unchanged.

Use `python tools/dev.py test-graph-v2 --output <fresh-external> --owned-port <owned-port>` with authenticated loopback owned FalkorDB and installed project/Core/Console. This runs real graph tests via the mature pytest collector, never a mock. Full inherited command: `python tools/dev.py test-maintainer --output <fresh-external> --owned-port <owned-port> -- -q tests aevora_core/tests --ignore=aevora_core/tests/gen2 -p no:cacheprovider`; run G21 separately so identity counts remain explicit.

Host constructs GraphRepository.v2(TenantBinding(...), TrustRegistry(...)); no Caller selector. MCPBroker opt-in requires `protocol_profile="aevora.mcp/2.0.0-rc2"`, private `v2_config_path`, and four-tool capability. Config contains binding/registry/facts/grant; DB password stays external. The existing proxy/client remains unchanged. Default legacy profile retains1.2 behaviour. No standalone public v2 Host publisher or live Codex challenge is claimed in this Gate.

Read G21_QUERY_AND_WITNESS_SPEC, G21_CONTRACT_AMENDMENT_DIFF, G21_CONTRACT_ADR, Q07_PUBLICATION_PRECONDITIONS and external trust/performance/legacy reports. This is a maintainer review, not a Participant task or public release approval.
