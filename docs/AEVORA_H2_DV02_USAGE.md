# D-v02 execution and evidence boundary

D-v02 is an independently registered D-family lease/authority challenge. Its public ID is `D-V02`; its variant is `v02`. Existing `D / v01`, A and SMOKE-001 keep their earlier task contracts, fixtures and required tests. B/C remain planned.

## Trusted runtime

Use `scripts/aevora-h2-python` with explicit `AEVORA_H2_RUNTIME`, `AEVORA_FALKORDB_PORT`, `AEVORA_FALKORDB_GRAPH` and an external owner-only `AEVORA_FALKORDB_PASSWORD_FILE`. The H2 runtime contains independently obtained Python 3.12 and the verified SQLite 3.51.3 library; see `aevora_core/docs/H2_SQLITE_RUNTIME.md`. Do not put credentials in arguments, task inputs or archives.

The launcher is for the trusted maintainer. Its filesystem view is not the Participant view. Candidate RPC and native Agent execution use the existing narrower bubblewrap environments.

## Additive CLI

After setting the trusted runtime variables, run:

```sh
scripts/aevora-h2-python -m benchmark.h2_cli list
scripts/aevora-h2-python -m benchmark.h2_cli validate --episode D-V02 --variant v02
scripts/aevora-h2-python -m benchmark.h2_cli --runs-root /absolute/new/runs prepare --episode D-V02
scripts/aevora-h2-python -m benchmark.h2_cli --runs-root /absolute/new/runs evaluate --episode D-V02 --submission evaluator/reference_patches/D-V02-reference.diff
scripts/aevora-h2-python -m benchmark.h2_cli --runs-root /absolute/new/runs report --run-id ACTUAL_RUN_UUID
scripts/aevora-h2-python -m benchmark.h2_cli --runs-root /absolute/new/runs reset --episode D-V02
```

`benchmark.h2_cli` installs an idempotent Episode/Suite registration and a D-v02-only recovery admission check, then calls the original CLI/Runner lifecycle. The original entry point does not install the new registration; validation of D-V02 through it fails closed. Always use the H2 entry point for this challenge. Existing old commands and task truth are preserved.

Without `--submission`, evaluation uses the newly prepared defective workspace. The maintainer-only reference, flock, local-lock and blind-cleanup patches are controls; they are never mounted in a Participant workspace. The inventory-only control is explicitly byte-identical to the existing capacity-safe defect, not an independent invented repair.

## Candidate Clock and process topology

The five public request operations use a shared authoritative integer Clock. Candidate workers receive one read-only mounted Unix socket with a query-only `NOW` protocol. The host can advance ticks through its in-process Clock owner. The endpoint rejects time changes, SQL, file reads and network forwarding.

The additive worker transport reuses the original resource supervisor, RPC/control protocol, namespaces and SQLite observer. The host proves actual worker identity through kernel peer credentials, stable pidfds and target database FDs. Handoffs pause an acknowledged old holder between ordinary API calls; they do not hold a required transaction across a barrier.

Suite 1.1.1 has thirty-six required hidden tests covering public behavior, capacity, authority handoffs, terminal receipts, independent SQLite records and interruption/retry. Eight mandatory method/phase observations include claim and completion at three write/response boundaries, stale-cleanup response loss, and completion of an existing unreserved order at an observed commit boundary. The public scenario and fixture remain 1.0.0. The earlier suite 1.0.0 and its thirty-five-test runs remain separate historical evidence.

The publication Oracle compares trusted before/after records. In the sole completion-writer window, a previously acknowledged unreserved order must remain present with its typed payload and permitted lifecycle intact; deleting and recreating it after an intermediate commit is invalid. Suite 1.1.0 results remain separate historical evidence and do not receive this new check retrospectively. An additional authorization or audit transaction can leave an intent pending when it has no new business effect; a new reservation and its completion receipt must share the recovered publication state. An unsupported native SQLite observation path is infrastructure `ERROR`, not an engineering `FAIL` or `PASS`. Observing the targeted first commit does not exhaust every possible transaction schedule. The controlled Clock does not prove power-loss, arbitrary clock skew or hostile-kernel behavior.

## Public regressions

Inside the actual prepared public workspace:

```sh
python -m unittest discover -s tests/public -v
python tests/public/test_episode_d_v02.py
```

Both commands execute the six real public SQLite/Clock checks. Hidden assertions, expected test identities, authoritative host snapshots and reference patches stay on the maintainer side.

## Repeated and native execution

`scripts/aevora_h2_dv02_validation.py` creates fresh Run IDs, candidates and independently initialized databases for serial repetitions. It retains every attempt and reset receipt. Raw JUnit, Oracle, process, FD and recovery records remain under each Run.

`scripts/aevora_h2_native.py` binds the actual G0/G1/G2 gates, D-v02 isolation result, successful current regression and reviewed corpus to an exact local release commit and source file manifest before a fresh completion-aware native multi-agent challenge. It reuses the official Codex adapter, Gateway and MCP boundary. Its separate read-only observation Session intentionally produces `NO_PATCH / NOT_EXECUTED`; this is preserved independently of whether it can read the new trusted Outcome. Solving, runtime integration, feedback visibility and causal benefit are separate conclusions.
