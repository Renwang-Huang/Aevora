# Public project source walkthrough

Run `walkthrough.py --output <fresh external absolute directory>` with installed
public Core, pytest 9.1.1, and an initialized dedicated `aevora_demo_` graph.
See [the complete public guide](../../../docs/PROJECT_SOURCES.md).

This explicit synthetic fixture uses a separately owned fixed pytest verifier to
check a tiny file contract. It submits through the public Python service, imports
the verified source with the real CLI, reviews, publishes, and queries in a new
Run. It executes no candidate code and makes no model/native Agent, industrial
benefit, adoption, or causal claim. Ordinary projects must supply their own
independently controlled verifier; packaging alone grants no trust.
