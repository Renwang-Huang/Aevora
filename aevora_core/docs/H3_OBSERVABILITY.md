# H3 read-only observation and independent verification

The public scripts in `aevora_core/scripts/` run against an installed Core.
They do not import the Benchmark Runner, Registry or private Evaluator. The
current package intentionally ships only the Core executable and source; take
these scripts from the separately trusted H3 source release or Audit-Lite.

The actual H3 deployment was replayed from a new authenticated RDB checkpoint
into a separate owned FalkorDB Volume on loopback port 17691. Its image digest,
SAVE/copy/checkpoint receipts, restored graph hash and last-SAVE RPO are in
Full `g4/demo-deployment/`. Existing primary and control instances are untouched.

With Host-only graph environment already set, the validated command shape is:

```sh
python aevora_core/scripts/h3_demo.py --output <new-output-directory> \
  --candidate <published-candidate-id> --external-run <actual-external-run-id>
python -I aevora_core/scripts/h3_verify.py <new-output-directory> \
  --manifest-sha256 <manifest-sha-from-a-separately-trusted-channel>
```

The demo produces actual CandidateLifecycle, WHEN/WHY, ExternalObservation,
PUBLIC_GRAPH, TIMELINE and their manifest. Missing source/observation or an
unexpected external VerifiedOutcome is an error. No model calls, writes or
fixed recommendations are part of this read path. Nodes have explicit public
allowlists; edge IDs/endpoints/types come from actual graph queries.

The independent verifier uses only the standard library, bounded ordinary
no-follow file reads and strict finite, unique-key JSON. It checks byte hashes,
candidate body/head, event ordering/transitions, real source and event edges,
independent PASS source, external authority and displayed positive graph paths.
It never executes any project code from the observation directory. Use a
separately trusted verifier and externally pinned manifest: changing both data
and an untrusted checksum file does not establish historical authenticity.

Actual repeated observations preserve four data files byte-for-byte. WHEN/WHY
contains real `governance_projection.as_of` clocks; only those enumerated
timestamps are excluded from the qualified semantic comparison. Original bytes
and manifests remain intact. A changed timeline byte is rejected.

The supplemental native timeline keeps original source-file line order and
complete-line SHA256. It uses typed official events and verified child metadata,
never natural-language claims to infer Agent identities. Missing timestamps
remain UNAVAILABLE; multiple files do not define one total causal order. MCP
per-run identity cannot establish which child authored an individual call.

The local Full index, Audit-Lite CAS/redaction and separate standard-library
verifier are reused from the existing evidence infrastructure. Lite is
MAINTAINER_AUDIT, not Participant input; private Oracle/Reference/raw topology
remain excluded with source hash pointers. External Sessions are supporting
evidence, not entries in the scored Run index. All actual failures and unknown
attribution survive export. Local checksums do not constitute third-party
attestation, model-weight proof or evidence of causal benefit.
