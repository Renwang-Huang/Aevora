# See Aevora in about two minutes

[Start the local demo](QUICKSTART.md), then open
**http://127.0.0.1:19064/journey.html**. No model API key is required.
The live panels use real FalkorDB with controlled synthetic task facts. The
historical Native section is labelled REPLAY. [Watch the public demo on YouTube](https://youtu.be/g5KCv_stZhg).

| Time | Screen and action | What to look for |
|---|---|---|
| 0:00–0:20 | **Activity & Decisions → Shared threads** | APPLY: the known process premise matches complete applicable support. The LIVE synthetic label is visible; no agent is executing here. |
| 0:20–0:40 | Select **Independent workers**, then **Unknown premise** | The same experience yields ABSTAIN for a false premise and VERIFY for a missing premise. Familiar advice is not enough. |
| 0:40–1:05 | **Experience Explorer** | Follow Revision → Rule → Premise and Evidence → Outcome → Authority. Expand the visible records to inspect real IDs and relationships. |
| 1:05–1:25 | **Governance Timeline → After withdrawal** | A real GovernanceEvent in the second controlled graph state changes the answer to ABSTAIN. The browser cannot publish or mint an Outcome. |
| 1:25–1:50 | Inspect the historical Native section | Two historical sessions produced patches and original 28/28 independent Oracle results. **S2 Core APPLY / Agent VERIFY** remain separate. S2 feedback was a Host-approved follow-up. |
| 1:50–2:00 | Return to live view | WHEN / WHY / ACCOUNTABILITY / FEEDBACK form a checkable chain. They do not establish a statistical causal advantage. |

## Screens you can inspect without installation

- [Activity & Decisions](assets/activity-decisions.png)
- [Experience Explorer](assets/experience-explorer.png)
- [Governance Timeline](assets/governance-timeline.png)

These are unmodified archived screenshots. See [image provenance](SCREENSHOT_PROVENANCE.md)
and [Native transfer](NATIVE_TRANSFER.md) for the source and limits.

## Recording and verification

Use the existing real-browser [validation command](REPRODUCIBILITY.md#browser-source)
with a running owned demo. It clicks the actual UI; it does not intercept API
responses. `demo:record` optionally records those same actions with narration
pauses. Keep all source/mode labels visible and preserve failures.

A sealed 138.48-second browser recording exists in the local release delivery,
with separate captions. See the [recording guide](DEMO_RECORDING_GUIDE.md).

Never record credentials, private Oracle assertions, Host pins, personal account
UI or raw private model conversations. Public controls are demonstration inputs,
not new Agent behavior. G2-4's bundled formal comparison status remains NOT_RUN;
causal benefit is UNKNOWN.
