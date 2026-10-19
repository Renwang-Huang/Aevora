# OrderFlow Incident Lab

Optional package: `orderflow-incident-lab==0.3.1`. Core and Console remain separately installable; neither depends on this package.

Use Linux, Python 3.12, Git and bubblewrap. Multi-worker D/D-V02 and strict native contracts require a real delegated cgroup v2 parent with memory and pids controls. Never disable those controls to obtain a result. From a fresh checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e './aevora_core' -e './console' -e '.[dev,benchmark]'
pip check
orderflow list
orderflow validate --episode A
python scripts/reproduce_public_benchmark.py --output /absolute/fresh/path/orderflow-reproduction
```

The reproduction runs the actual Runner, candidate bubblewrap isolation, independent pytest evaluator and SQLite Oracle for defective and reference-patched SMOKE-001, A, D and D-V02. It emits every real report, JUnit and source/runtime fingerprint. Expected defective FAILs are distinct from a failed reproduction gate. B and C remain PLANNED/NOT_IMPLEMENTED.

D-V02 is registered through `python -m benchmark.h2_cli`, retaining the original explicit profile. Default `orderflow` preserves its original registration semantics. Example:

```sh
python -m benchmark.h2_cli --runs-root /absolute/fresh/path/runs prepare --episode D-V02
```

All formerly hidden tests and reference answers are now public historical materials. These commands make no networked Agent/model calls and establish neither native multi-agent success nor statistical causal improvement. Real model experiments are optional, require separately configured explicit credentials and supported official runtime, and are never a fallback for offline evaluation.
