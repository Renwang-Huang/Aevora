# Reproduction profiles

Product only: follow the main README and public `scripts/aevora_public_demo.py`; install `aevora_core` and `console` only. Runtime tables show LIVE SYNTHETIC demo data separately from HISTORICAL REPLAY. Graph failures return UNAVAILABLE without replay fallback.

Optional engineering/Benchmark: install all three distributions using docs/BENCHMARK.md, then run `scripts/reproduce_public_benchmark.py`. Register fresh synthetic Host authority through `tools/validation/g22_host_cases.py`; run Core/Host/adapter tests against a new owned FalkorDB volume. Package files include actual public tests so a wheel install can prepare episodes outside the source checkout.

Python developer tests: `python -m pytest -q tests aevora_core/tests`. Supply graph/Host settings from docs/DEBUGGING.md. Three legacy G1 suites require the exact authenticated historical import and explicitly skip without `AEVORA_VERIFIED_G1_HISTORY_READY`; a synthetic replacement must not be called historical evidence. Strict native and multi-worker tests require delegated cgroup memory/pids controls. No cgroup fallback is allowed.

Console: `npm --prefix console ci`, `npm --prefix console run build`, `npm --prefix console test`. Browser tooling remains in `console/web`; the real Chromium recorder accepts its existing URL/output environment variables. Runtime/Node dependencies are installed from pinned manifests; no global upgrade is required.

Build the explicit reviewed source and three wheel/sdist pairs with `python tools/public_release.py --output /absolute/fresh/path/build`. Source selection validates path traversal, links, file types and credential filenames before copying. Inspect the release security scan and artifact SHA256 manifest as well as build/test output. Test failures, environmental skips and expected negative evaluations are distinct statuses; none may be changed by editing a receipt.
