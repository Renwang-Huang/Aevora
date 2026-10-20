# Separate Native Live and maintenance deployments

Live and regression graphs must use separate owned **server instances and
volumes**, not only different graph names. Each has authenticated loopback access,
an external mode0600 credential/config, explicit owner label and finite CPU,
memory/PID limits. Participant receives neither credential nor admin endpoint.

G23 exposed a real signal11/exit139 failure in the pinned C-module engine during
mixed retained maintenance/growth and Live activity. Docker reports OOMKilled=false;
the stack reaches moduleTimerHandler. The exact engine root cause is UNVERIFIED.
Changing a memory limit is not evidence that this defect is repaired. The actual
failed deployment and last saved RDB are retained. A clean independent Live server
is restored and checked against the saved graph SHA before a new Session starts;
unsaved Query/Decision/Session loss is not synthesized or claimed durable.

Keep the original RDB last-SAVE recovery scope, AOF limitation and shared-kernel
isolation limits. Maintenance/profiling/copy tests do not run on the active Native
server. A separate Recovery server is stopped after exact restore verification.
No old H1–G22 database or evidence is changed. A future engine fix/upgrade requires
its own compatibility evidence; G23 does not certify an untested upstream fix.

## Existing maintainer CLI (trusted launcher namespace)

Set host-only toolchain and per-instance `AEVORA_FALKORDB_*` configuration using the
existing protected launcher, then execute:

```sh
python -m benchmark.h2_cli --runs-root /owned/fresh/runs run-codex \
  --episode D --variant v01 --provider gateway \
  --model gpt-5.6-terra --reasoning-effort max \
  --completion-policy completion-aware --agent-timeout none --request-budget none \
  --agent-mode multi --stream-idle-timeout-ms 3600000 \
  --experience aevora --experience-profile aevora.mcp/2.0.0-rc2 \
  --experience-v2-bootstrap /host/private/bootstrap.json \
  --enable-experience-proposals
```

The command is a format reference. External G23 per-command receipts contain
actual executed argv, configuration SHA and exits. Do not run it against frozen
roots or old database defaults. The default Native request concurrency is4 and
native thread bound4; reducing transport capacity below active native demand
caused genuine 429 rejections in an earlier G23 attempt. Those failures remain.
Financial/token/cumulative request caps are None. Authorization expiry, finite
transport retries, per-operation bounds, resource limits and trusted stop remain.
