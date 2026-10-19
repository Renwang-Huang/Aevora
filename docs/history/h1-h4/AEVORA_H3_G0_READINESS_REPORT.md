# Aevora H3-G0 — readiness

**Verdict: PARTIAL.** Release boundary, clean deployment/query and Episode regression PASS. Original Native UDS compatibility remains PARTIAL with an executable equivalent business entry; no privilege expansion.

Source commit: `1f5f3d9d954191feef5eec88cc84ec1928a85286`. Archive: `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/`.

## Actual commands and evidence

| Execution | Exit | Evidence |
|---|---:|---|
| baseline collector, 195885 history hashes and331 H2 source hashes |0| baseline-capture/command.json; g0/BASELINE_RECEIPT.json |
| Docker Compose new H3 volume/loopback17689, authenticated health |0| h3-fresh-deployment/command.json; g0/compose.json |
| physical host/Outer/official Native command probes |0 controller| g0/native/*/command.json; RESULT.json |
| old-root wheel, current root denied, explicit maintainer wheel, public Core wheel/sdist |0 controller| g0/packages-v2/*/command.json; RESULT.json |
| clean Core venv install from real wheel, pip check, actual fresh graph query |0 each| g0/packages-v2/public-install, dependency-check, clean-real-graph-query |
| inherited CLI15 checks |0 controller| g0-episode-cli-regression/command.json; g0/cli/summary.json |
| D-v02 Buggy / Reference |1 /0| g0-dv02-buggy/reference; g0/dv02-runs/ |

The inherited CLI retains SMOKE8, A14, D28 positive/negative controls, legal flock alternative, B/C NOT_IMPLEMENTED, invalid submission ERROR, timeout TIMEOUT, archive/report/reset. D-v02 new Runs use the unchanged36-test suite: Buggy FAIL, Reference PASS. These are current H3 executions, not historical grades.

## Native compatibility

Identical reference/public input: host and Outer original6 assertions PASS; official Native original6 setup ERROR at AF_UNIX.bind (errno1). Actual namespaces/cgroup/CapEff/NoNewPrivs/Seccomp are recorded. Native CapEff=0, NoNewPrivs=1, Seccomp=2. `tests/public/dv02_inprocess_contract.py` runs the original suite unchanged with a local injected Clock and real SQLite:6/6 in all3 layers. It does not test UDS transport or independent process authority. Original tests remain unmodified and errors remain archived; no extra IPC/network/capabilities/mounts.

## Distribution and rebuild

Old root wheel actually contains private Evaluator assets. The root PEP517/660 backend now fails unless the trusted builder explicitly selects MAINTAINER_ONLY. Ordinary distribution is independent aevora-core; wheel and sdist have no evaluator/private_manifest/private_labels/reference/hidden members. Public install/query uses a fresh Git clone and new venv, no OrderFlow installation. Root maintainer artifacts must never enter Participant or public Lite.

First clean-package attempt exited1 because the runtime-mounted Git binary lacks git-upload-pack. The failed logs remain. A separate actual host `git clone --no-hardlinks` receipt and new package attempt succeeded. No assertion was weakened.

## Residual limits

H1/H2 services/volumes unchanged. H3 is a separate port/volume/credential directory. AOF139 is not fixed; RDB guarantees only completed SAVE. EOL runtime remains, planned upgrade requires fresh full sandbox qualification. Hostile shared-kernel and model injection proof remain PARTIAL/UNVERIFIED. No model call occurred at this Gate. G1 can proceed within these established boundaries.
