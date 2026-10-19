# Reviewed full-source publication inputs

The owner-expanded 2026-10-19 scope includes product, Agent integration, Trusted Host, Benchmark, evaluator/Oracle, public historical answers, tests and engineering tools. The earlier non-Benchmark exclusion is superseded. See FULL_PROJECT_SCOPE_AND_LICENSE.md and docs/FULL_PUBLIC_SOURCE_MAP.md.

`PUBLIC_SOURCE_FILES.txt` is the explicit reviewed source selection used by `tools/public_release.py`. It includes executable engineering code and deliberately labelled historical source. It excludes credentials, signing private keys, private raw model sessions, generated Host registries/grants, databases, build caches and installed third-party dependencies. Path traversal, symlinks, hard links and nonordinary files fail selection. Wheels/sdists and Git history receive a separate release safety scan.

The product Docker image still installs only Core/Console and public replay assets. Root optional Benchmark packaging does not enter ordinary Core imports or grant participants host/evaluation filesystem access. Public historical test and answer disclosure invalidates future blind-test claims, while trusted execution and publication boundaries remain enforced.
