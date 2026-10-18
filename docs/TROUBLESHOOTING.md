# Aevora troubleshooting

| Observed state | Check / action | Truth boundary |
|---|---|---|
| Empty graph | `aevora health`, then actual query | Empty candidates are correct; no synthetic PASS/history seed |
| GraphUnavailable | Owned Compose health, loopback port and private secret permissions | Do not return cached Replay as LIVE |
| MCP unavailable | Host READY, grant0600/private parent0700, same scoped Run and socket | Configuration alone is not a real call |
| Grant revoked/expired | Start a new Host grant and new Session/config; old grant remains invalid | Do not widen permissions or reuse token |
| API forbidden | Use the configured Viewer capability/origin | No browser DB/admin credentials |
| Provider/SSE/429 | Preserve failure/retry logs, check the user's configured provider | No silent provider/model downgrade or fake completion |
| Native UDS EPERM | Known H3 native cross-process limitation | In-process checks are not transport proof |
| Persistence | RDB last successful SAVE/graceful stop | AOF reload139/unsaved crash tail unresolved |
| Replay rejected | Check externally pinned contract SHA, ordinary bounded files and original package | Recomputing an untrusted checksum is not authenticity |

Keep failed attempts and use new output paths. Do not modify the historical
Oracle, reference patches or grades. Revoke capabilities and stop owned
processes before archiving; never include grant contents or actual secrets.
