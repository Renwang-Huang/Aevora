# Run the Aevora Decision Journey

This starts a local, owned **LIVE synthetic demo** backed by real FalkorDB and
the existing WHEN/WHY policy. No model API key or Benchmark installation is required.
For a fresh, unseeded ordinary project instead, see [standalone Core](STANDALONE_CORE.md).

## Requirements

- Docker Engine and Docker Compose v2.
- Python 3.10+ for the launcher; the application image uses Python 3.12.14.
- Linux, at least 4 GB available RAM, free loopback ports 19062 and 19064.
- A checkout of this repository. The first build needs network access for images
  and pinned dependencies; browser assets are included, with no runtime CDN.

## Start

From the repository root:

```sh
python3 scripts/aevora_public_demo.py start \
  --project aevora-gen2-demo \
  --secret-dir "$HOME/.config/aevora/public-demo"
```

Open **http://127.0.0.1:19064/journey.html**.

The launcher builds Core and Console, creates new owned volumes, runs the public
SQLite verifier in a separate process, and seeds baseline and withdrawn example
graphs. Secrets are generated outside the checkout and are never printed.
The synthetic trust registry grants no production publication authority.

## Inspect three decisions

1. **Shared threads → APPLY.** Inspect the known process premise and support.
2. **Independent workers → ABSTAIN.** A process-local lock does not span workers.
3. **Unknown premise → VERIFY.** Missing topology is not inferred as a match.
4. Open **Experience Explorer** for the actual graph and Witness.
5. Open **Governance Timeline** and choose **After withdrawal → ABSTAIN**.

The [walkthrough](DEMO_WALKTHROUGH.md) explains the screens and the separate
historical Native evidence. Live panels are synthetic graph observations, not
new model runs; the historical section is labelled REPLAY.

## Status, stop and repeat

```sh
python3 scripts/aevora_public_demo.py status \
  --project aevora-gen2-demo \
  --secret-dir "$HOME/.config/aevora/public-demo"

python3 scripts/aevora_public_demo.py stop \
  --project aevora-gen2-demo \
  --secret-dir "$HOME/.config/aevora/public-demo"
```

Stop explicitly saves the owned graph before stopping and retains the volumes.
For a fresh initialization, choose a **new project name and secret directory**.
Do not reuse historical volumes as proof of a clean install.
Use `--db-port` and `--console-port` if the defaults are occupied.

## Next steps

- [Connect an MCP client](CODEX_MCP_SETUP.md); keep authority and secrets on the trusted host.
- [Install standalone Core](STANDALONE_CORE.md) for your own unseeded project.
- [Build and run public tests](REPRODUCIBILITY.md), including real browser checks.
- [Troubleshoot](TROUBLESHOOTING.md) and review [security](../SECURITY.md) and
  [durability limits](LIMITATIONS.md) before adapting this local deployment.
