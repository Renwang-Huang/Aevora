# Demo recording and sharing

The local RC1 delivery includes a **138.48-second real Playwright browser recording**
and separate captions. It is not a new model run. No hosted video URL is available
in this repository, and a narrated competition submission is not verified.
The [walkthrough](DEMO_WALKTHROUGH.md) also supports a new two-minute recording.

1. Start the [owned local demo](QUICKSTART.md). Use actual browser actions and actual graph responses.
2. Record Activity & Decisions, Experience Explorer and Governance Timeline.
3. Keep LIVE synthetic and historical REPLAY labels, timestamps and verdicts visible.
4. Preserve **S2 Core APPLY / Agent VERIFY** and the Host-approved follow-up distinction.
5. Explain the graph's decision mechanism; do not claim statistical improvement from the historical examples.
6. Do not show real API keys, database passwords, production grant/capability files, private model conversations or personal account UI. Oracle/test/reference source is included as public historical evaluation material; label it accurately and do not present disclosed answers as future blind tests.
7. Review every frame before sharing. Only add a video link after its actual upload is verified.

For a new recording from the repository root, after installing browser dependencies
and starting the demo:

```sh
AEVORA_BROWSER_URL=http://127.0.0.1:19064 \
AEVORA_BROWSER_OUTPUT=/absolute/new/external-evidence-directory \
AEVORA_RECORD_VIDEO=1 \
npm --prefix console run demo:record
```

The output directory holds the real browser video, screenshots, trace and RESULT.json.
Review their contents before publication. Run without AEVORA_RECORD_VIDEO to
validate without narration pauses. See [browser setup](REPRODUCIBILITY.md#browser-source).
Official competition submission and eligibility remain owner/organizer actions.
