# Pinned Observatory replay example

This example supplies the optional read-only Console replay, its public context, an independent verifier and a standalone deployment template. The main live synthetic product demo is documented in [Quickstart](../../docs/QUICKSTART.md).

```sh
python3 examples/observatory/demo.py \
  --sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776
```

The verifier checks the externally pinned contract and each projected artifact. Replay identities and outcomes remain historical; they are not current Agent execution or proof of causal benefit. [Replay cases](../../docs/REPLAY_SCENARIO.md) explains the evidence, and [Observatory API](../../docs/OBSERVATORY_API.md) describes the read-only interface. LIVE failures never substitute this replay.

For the optional standalone image and owned database template see [deployment](deploy/README.md). No Benchmark installation, model API key or production Host authority is granted by this example.
