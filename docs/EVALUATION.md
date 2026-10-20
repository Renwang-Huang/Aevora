# Public historical evaluator

The actual supervisor/worker, Oracle, clock and recovery admission code is in `evaluator/`. Former `hidden_tests/`, `private_manifests/`, `private_labels/` and `reference_patches/` names are compatibility namespaces, not current secrecy claims. The original source byte pins and disclosure label are in `docs/history/evaluation/`.

The trusted evaluator launches a fresh isolated pytest process, checks exact registered test identities, derives counts from actual JUnit cases, reads durable SQLite records independently, and verifies recovery observations. Candidate source is never imported into the trusted pytest interpreter. Physical worker isolation, UDS peer/process identity, resource limits, fail-closed setup and exact source pin checks remain enforced. Making verifier source public does not confer Host authorization.

The Core strict diff interpreter is packaged separately so verifying a patch does not require installing the Benchmark. D-V02 Host admission additionally needs the matching optional public evaluator, whose actual bytes must match the sealed source snapshot. A version mismatch refuses admission; no recorded result is substituted for execution or verification.

Results belong to their pinned source and environment. Historical source versions are not retroactively credited with current test runs. Old phase reports retain old policy and known failures; the expanded owner scope supersedes their former non-publication rules. B/C remain unfinished, G24 formal causal evidence remains unestablished, and the historical FalkorDB SIGSEGV/139 root cause is unresolved. RDB durability is limited to the last completed explicit SAVE; AOF replay failures remain a documented risk.
