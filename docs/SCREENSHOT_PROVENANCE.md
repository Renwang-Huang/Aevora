# README screenshot provenance

All three images are **byte-for-byte copies of sealed browser screenshots**
captured on 2026-10-18 UTC during actual Chromium/HTTP/FalkorDB validation.
No pixels were generated, retouched, composited or cropped; README thumbnails
only scale the full images. Their original Live/synthetic and historical Replay
labels, timestamps, verdicts and limitations remain visible.

| Public image | Archived capture | Interpretation |
|---|---|---|
| [Activity & Decisions](assets/activity-decisions.png) | `01-live-apply.png` | Shared-thread APPLY; public verifier; separate historical REPLAY section. |
| [Experience Explorer](assets/experience-explorer.png) | `04-graph-witness.png` | Actual bounded Graph v2 relationships and the LIVE synthetic label. |
| [Governance Timeline](assets/governance-timeline.png) | `06-withdrawal.png` | Withdrawn revision ABSTAIN; original historical Core APPLY / Agent VERIFY distinction. |

The [machine-readable provenance](assets/SCREENSHOT_PROVENANCE.json) records exact
SHA256, sizes, dimensions and source-tree identity. The validated capture's public
source tree is the same tree published at the RC1 baseline. Images depict that
recorded state, not a new run or a continuous uptime claim.

Hashes verify file identity; they are not third-party attestation of private
Oracle results. No private audit logs, authentication files, hidden tests or
reference patches have been added to these public assets.
