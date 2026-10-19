# Safe Gateway configuration and execution

The upstream project key belongs in a trusted directory outside this repository. Use a secret manager or a local terminal with echo disabled to create `<MAINTAINER_HOME>/.config/orderflow/gateway_api_key`; directory mode must be 0700, key file owner must be the maintainer and mode exactly 0600. Never paste its value into shell arguments, source, patches, a Participant environment or evidence. The existing chat-supplied key should be rotated for continued use.

The supplied Python 3.12 launcher mounts only that file into the trusted maintainer namespace at `/maintainer/gateway.key`. It also mounts delegated cgroup controls into the trusted namespace. Neither mount is passed to participant or candidate namespaces.

```sh
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root phase3_5_validation/my-new-validation/runs run-codex \
  --episode A --provider gateway --model gpt-5.6-terra --reasoning-effort max \
  --agent-timeout 1200 --request-budget 160
```

The executable and official `codex-code-mode-host` must come from the same installed Codex release. The launcher discovers the bundled helper beside the selected executable and mounts it read-only. Missing facilities fail closed; no unisolated subprocess fallback exists.

Non-secret environment overrides: `ORDERFLOW_GATEWAY_URL` (authorized hostname, explicit root), `ORDERFLOW_CODEX_BINARY`, `ORDERFLOW_CGROUP_PARENT`; project key location may be selected with `ORDERFLOW_GATEWAY_SECRET_PATH`. Use these on the trusted host only. Do not pass a plaintext API key environment to untrusted code.

For this host the delegated parent is `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.gnome.Terminal.slice`, with memory and pids controllers. On a different host configure an actual writable delegated parent and rerun the local gates. The fixed fallback path is host-specific and is not evidence that another host has working delegation.

Runtime, multi-agent, submission-integrity, evaluation, isolation and integration statuses are separate. A correctly archived agent patch may fail the hidden task while the engineering integration closes successfully. Provider responses record their actual model/effort labels and usage; missing observations stay UNAVAILABLE. An unsupported requested effort must not silently downgrade.

Original ChatGPT broker tests are retained. The new live entry blocks `legacy` as an unhardened profile. No source or answer is substituted for an agent-produced patch.

The Phase 3.5 corrected three-run recovery series uses the 1200-second override above with the same model, max effort, 160 requests, four concurrent requests, and 2 GiB physical memory in every run. Official CLI request and stream retries are each capped at two; retries consume broker request budget. No model, effort, TLS or sandbox downgrade is used. Initial 900-second failures remain archived separately.
