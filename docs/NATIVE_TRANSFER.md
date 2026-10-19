# Native agents, independent sessions, accountable transfer

The Decision Journey includes a **historical, sanitized G2-3 summary** of actual
Codex Native Multi-Agent work. It is separate from the public live synthetic
graph and is not a new model execution by the demo.

## What crossed the session boundary

1. **S1 engineering action.** Native agents investigated and modified an actual
   Episode D-v01 instance. The archived S1_05 run has three verified native children,
   a patch hash and an original independent Oracle result of 28/28 PASS.
2. **Trusted publication.** S1's natural proposal passed source/Outcome review by
   the Trusted Host and was committed through Q07. A proposal alone is not trust.
3. **Fresh S2.** A new model session retrieved that published experience and its
   Witness, made a decision and produced another patch. Its archived independent
   Oracle result is also 28/28 PASS, with three verified native children.
4. **Feedback with a source.** S2 support was a Host-approved follow-up. It was
   **not direct publication of S2's natural proposal**.

## Recommendation is not adoption

**S2 Core: APPLY. S2 agent's recorded decision: VERIFY.** Both are preserved.
The recommendation, the recorded claim, the actual patch and the independent
Outcome are different records. A viewed experience plus a passing patch does not
by itself establish that the experience caused the success.

The public [historical summary](../console/web/gen2_history.json) contains the
original run IDs, patch/report hashes, Witness reference and these distinctions.
The [Console implementation](../console/web/journey.js) displays it as
**HISTORICAL · SANITIZED · REPLAY**. It never substitutes for failed live reads.

## What this does not prove

- This is transfer to a new instance of the same D-v01 family, not an unseen task family.
- No statistical causal benefit is established. This public snapshot carries
  G2-4 Pilot/formal comparison status NOT_RUN and causal benefit UNKNOWN.
- The full source release includes the [historical Oracle tests, manifests and
  reference answers](../historical_public_evaluation/README.md), with original
  code pins and an explicit disclosure label. These are public engineering
  materials and are no longer future blind tests.
- Original private model conversations and some original per-run native/evaluation
  records remain unpublished. Public code supports new [model-free reproductions](BENCHMARK.md);
  it does not supply every original run seal, session byte record or authority
  record needed to independently re-certify the historical 28/28 outcomes.
  Public summary hashes identify public bytes, not external attestation of
  unpublished evidence.
- Historical shared-kernel isolation is PARTIAL, and database reliability remains
  conditional. See [limitations](LIMITATIONS.md).

The demo's synthetic publisher is separate from the included
[Trusted Host implementation](../aevora_maintainer/host_v2.py). Production use still
requires owner-granted authority and protected keys; publishing its source does
not grant that authority. The [MCP interface](CODEX_MCP_SETUP.md) exposes untrusted
decisions/proposals, not Host approval, Oracle registration or Q07 publication.
