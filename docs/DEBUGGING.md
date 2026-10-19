# Debugging and validation

Current entries require fresh outputs outside the checkout:

```sh
python tools/dev.py --help
python scripts/reproduce_public_benchmark.py --output /absolute/fresh/path/benchmark
python tools/validation/g22_host_cases.py --output /absolute/fresh/path/host-cases
python tools/validation/g22_tests.py --output /absolute/fresh/path/graph-tests --owned-port 19163 -- -q tests aevora_core/tests -p no:cacheprovider
python tools/workspace_check.py
python tools/sync_public_evidence.py --check
```

Before graph tests set an explicitly owned loopback `AEVORA_FALKORDB_PORT`, external mode-0600 `AEVORA_FALKORDB_PASSWORD_FILE`, isolated `AEVORA_FALKORDB_GRAPH`, and `AEVORA_G22_CASES` to the newly generated `CASES.json`. These cases execute the real public Oracle and synthesize registered test authority; they are not owner production authority or Agent outcomes.

`tools/experiments/g24/instances.py` constructs explicit experimental task variants; `pagination_audit.py` verifies actual bounded pages. `reliability.py --help` describes opt-in probes using a fresh owned Docker container, explicit port and external secret directory. Its deliberate SIGKILL/resource/AOF probes must run only on that owned instance. Optional historical log collection stays local and requires an explicit stopped source container; no historical container is restarted or removed.

The H2/H3/H4, validate_phase*, m1_* and phase35_* scripts remain inspectable historical engineering utilities. Many require their original sealed archive/configuration, model runtime or phase-specific graph; they are not all generic one-command acceptance entries. Some write newly generated phase reports. Use a disposable clone and explicit archive roots; do not run them over immutable history. Current replacements and per-file reasons are recorded in the release source matrix. No new paid/native model trial is asserted by shipping these scripts.

For a system without Python 3.12, `scripts/python312` accepts an explicit verified `ORDERFLOW_PYTHON_RUNTIME` directory and uses bubblewrap. Normal Python 3.12 installations use the active project virtual environment or `AEVORA_PYTHON`. No personal runtime path or real credential is embedded. Native strict tests retain their real cgroup prerequisites.
