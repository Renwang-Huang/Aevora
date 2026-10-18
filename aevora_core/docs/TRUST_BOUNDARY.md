# Aevora H1 trusted OrderFlow Outcome boundary

## Authority and scope

`aevora.orderflow_outcome_bridge` is a trusted host adapter. It has no model,
FalkorDB, MCP, Participant or network dependency. It reads existing OrderFlow
evaluation evidence and never imports or executes candidate business code. The
existing OrderFlow Evaluator and its private tests remain the engineering judge.

`verify_outcome(anchor, report_reference)` accepts no verdict, verified flag,
adoption claim or confidence parameter. A `TrustAnchor` is created by authorized
maintainer code, outside the Participant, with an exact report allowlist and a
previously approved SHA256 of an archive manifest. A caller-supplied self-seal
is not authority. The local trust root is the maintainer's source approval and
physical isolation; hashes alone do not authenticate a person or prove external
execution attestation.

The bridge admits complete `PASS` or business `FAIL` A/D evaluations. Runtime
ERROR/TIMEOUT, missing/errored/skipped suites and unavailable Oracle evidence
remain archived technical observations; they are not minted as complete
engineering VerifiedOutcomes. This distinction does not discard failures.

## Two trust profiles

| Profile | Evaluation anchor | Frozen evaluator source anchor |
|---|---|---|
| `historical_full` | Pre-pinned Full `EVIDENCE_MANIFEST.json` with exact report paths and Run IDs | Source snapshot in the same pinned archive |
| `current_live` | Trusted Runner's finished Run `run_evidence_manifest.json`, pinned after writers stop | Separately pre-pinned source archive, captured before the challenge |

The historical M1 profile defaults to `final_source_snapshot`. H1's current
profile overrides this with `frozen_source_snapshot`. Never replace a historical
fingerprint with today's source version. A current-live profile checks an
evidence format; it does not by itself establish that a Session is new or
Multi-Agent. Native Session/MCP evidence is checked separately.

Example for a freshly completed trusted Run:

```python
anchor = TrustAnchor(
    archive_root=run_directory,
    manifest_sha256=approved_run_seal_sha256,
    allowed_reports={"evaluation_report.json": authorized_run_id},
    profile="current_live",
    manifest_relative_path="run_evidence_manifest.json",
    source_archive_root=pre_run_source_archive,
    source_manifest_sha256=approved_source_manifest_sha256,
    source_snapshot_relative_path="frozen_source_snapshot",
)
outcome = verify_outcome(anchor, "evaluation_report.json")
```

These pins are supplied by the trusted Runner integration. None is taken from
Participant `record_decision` fields or tool arguments.

## Verification operations

1. Traverse every archive component using directory file descriptors and
   `O_NOFOLLOW`. Reject symlinks, hard-linked files, special files, noncanonical
   paths and cross-Run artifact references. Bounded nonblocking regular-file
   reads compare descriptor metadata before and after collection.
2. Check the configured manifest digest before using its file map. Every
   consumed report, XML, source, patch or Oracle file must be present in that
   pinned map and match its SHA256. JSON duplicate keys, nonfinite constants and
   excessive nesting are rejected.
3. Read required test identities from the pinned private manifest. The actual
   JUnit must contain every necessary identity exactly once. Declared counts,
   per-case outcomes, report counts and pytest exit status must agree. Reject
   skip, error, missing and duplicate tests. XML is UTF-8 and bounded; DTD and
   entity declarations are refused.
4. Recompute evaluator/suite composite source digests and require their exact
   complete file sets from the frozen source map. Compare every actual source
   file and the evaluator version literal, parsed with AST without execution.
   Removing a fingerprint file and recomputing a smaller digest is rejected.
5. Recompute the candidate source tree with OrderFlow's length-prefixed tree
   digest. Check the evaluated, expected and applied identities. For patch
   submissions, check patch bytes and the sealed public baseline, then reuse
   OrderFlow's non-executing strict diff interpreter. Its actual host source
   must match the pinned source version. The derived tree must exactly equal
   the evaluated candidate. Native extraction additionally requires the
   corresponding patch, baseline, final tree and per-file identities.
6. Independently reload sealed Oracle, Worker-topology and recovery records.
   They must equal their report copies and have unique source references. PASS
   cannot coexist with an inconsistent Oracle. D requires topology evidence;
   its crash-window coverage is recomputed from recorded pidfd-exited SIGKILL
   events. The common committed/response-loss recovery windows must be reached
   for PASS, preserving the existing Evaluator's legal-strategy boundary.

Finite budgets are 32 MiB per manifest, 64 MiB per embedded report, 8 MiB per
JUnit, 2 MiB per source tree and 256 MiB aggregate collection. The report limit
was adjusted after a preserved first invocation showed that actual unmodified
M1 D reports embed 201 topology observations and occupy 25–28 MB. Semantic
assertions were retained. This is bounded offline verification, not a streaming
or hostile multi-gigabyte evidence service.

## Immutable identity and public/private separation

The Outcome ID is `orderflow:<run_id>`. Its `immutable_digest` is SHA256 of
canonical facts before that digest field is added. It includes the actual
verifier source SHA256, source-report and manifest identities, candidate/patch,
JUnit, evaluator and suite fingerprints. The returned dictionary is a transport
copy. Trusted graph ingestion must reject a same-ID content conflict and append
an audit fact; it must not let a Participant recalculate a digest and submit an
Outcome as a trusted actor.

`public_outcome_summary()` is an allowlist projection. It excludes absolute
report paths, private Manifest identities, hidden testcase names, frozen source
maps and raw Oracle contents. `private_verification` stays on the trusted host
and must be omitted as a whole by the graph's public Evidence projection.

Verified engineering results, experience queries, adoption claims, observable
actions and causal attribution are different facts. The bridge sets attribution
`UNKNOWN`. PASS does not prove that an experience caused a successful repair.
Feedback may append `outcome_observed_no_attribution` and a new revision without
changing reliability. An exact same-strategy A/D controlled replay supports
only the corresponding environment boundary; it does not measure Aevora's
effect on Agent capability.

## Historical seed provenance

The fixed H1 seed helper verifies four actual M1 reports against old Full
manifest `a914e4fbacd1c96bc382686e6c38981a5041a7345d16eb9679f62ece29ca94ce`:

| Strategy/source | A Run | D Run | Results |
|---|---|---|---|
| Maintainer RLock | `6a312f02-3e28-406a-81f7-86b2636e836f` | `c39773d4-33fe-408b-81af-2b3dcd19fa84` | 14 PASS → 14 PASS / 14 FAIL |
| Historical natural atomic strategy replay | `4943e873-6e9d-4905-a281-dfb621b56748` | `cf083714-0a91-4392-81ed-1070f2cdef71` | 14 PASS → 28 PASS |

Each pair has exactly identical candidate source. RLock's tree is `85127c...`;
the natural strategy's tree is `5011b8...` (complete values in verification
JSON). The natural experience's origin is the distinct real Phase 3 Session
`339f7d73-29df-4242-8920-9e566bce8a9c`, original patch `0525c965...`. The frozen
producer applies that historical patch; the original native runtime proof is
a separate historical audit. These four verified outcomes are maintainer
replays, never four fresh natural Sessions. Experience source types remain
`maintainer_seed` and `natural_agent_run`; Outcome profile provenance remains
`historical_replay`.

Offline helper (writes only a fresh output outside historical evidence):

```sh
scripts/python312 -m aevora.orderflow_outcome_bridge \
  --historical-archive m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e \
  --output <new-H1-archive>/historical_seed_review/VERIFIED_SEEDS_FINAL.json
```

This command rechecks historical bytes, not the hidden tests themselves.
Current-profile compatibility was also dynamically verified on the already
sealed M1.1 natural D Run `64377ef0-3998-434c-936c-8011886b9cd2`, including real
patch-derived tree and extraction identities. Its probe explicitly records
`new_session_launched=false`, `formal_h1_outcome=false` and does not change the
old Run or turn it into an H1 challenge.

## Tests and limits

Trust tests use explicitly synthetic small archives and perform no real model
or business execution. Their malformed/equivocating fields are resealed under
test-only authority to exercise semantic checks beyond simple hash mismatch.
Actual history verification is separate. New H1 command receipts, failures,
JUnit and verification JSON are under the fresh `aevora_validation/` archive;
old protected tests and archives have not been edited.

Residual assurance limits: a compromised trusted maintainer can authorize false
evidence; host SQLite observer limitations remain; local hashes are not external
attestation; source matching cannot prove private model reasoning. This module
does not independently rerun the raw database Oracle or cryptographically attest
the original process. It cross-checks the independent Oracle's sealed host
observations. Only actual H1 dynamic gates can establish the new deployment,
MCP boundary and cross-Session feedback loop.

The design reuses mature principles from [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts)
and bounded parsing precautions in [Python XML security guidance](https://docs.python.org/3/library/xml.html).

## Trusted observed feedback

`aevora.feedback.ingest_outcome(repo, anchor, report_reference, ...)` invokes the
bridge itself. It accepts no already-minted caller Outcome and is not exposed
through MCP. Optional Experience IDs require actual same-Run
`Query → CONSIDERED → Experience` relationships. Query authority and immutable
candidate IDs must agree. Optional context facts must equal the authorized
report's public runtime facts. Persisted Decision records require the same Run,
the corresponding Query relationship and the actual Experience relationship;
they retain `UNTRUSTED_PARTICIPANT_CLAIM` authority.

The ingestor appends a VerifiedOutcome, its public Context and Task, an
ObservedAction containing verified patch/candidate identities, Feedback, Evidence
and a new ExperienceRevision. An existing historical Outcome keeps its original
Context/Task identity. The new revision retains links to the original Rule and
revision; neither old evidence nor rule bytes change. Its Evidence relationship
is always `OBSERVED_OUTCOME`. A PASS is not automatically support, and a FAIL
without proved strategy use is not automatically a strategy counterexample.
The new bundle and retrieval fingerprint can change while the support count
and applicability decision remain unchanged.

Feedback status is `outcome_observed_no_attribution`; attribution is `UNKNOWN`,
adoption and strategy association are `UNVERIFIED`. Actual submission bytes do
not prove model reasoning or experience influence. Decision claims and actual
Query exposure are linked separately. No observed exposure produces only the
Outcome/Context/Task/action records, without an invented experience revision.

Identities derive from the immutable Run and Experience IDs. The same ingestion
is idempotent. Changed Outcome bytes, new exposure after completed ingestion or
new Decision claims that reinterpret existing Feedback are refused and audited.
Operations are individually append-only; H1 does not provide a multi-statement
database transaction. An interrupted ingestion may leave partial append records.
Its completion AuditEvent is written only after all required edges succeed; an
identical retry completes the chain. A competing claim requires explicit future
versioning rather than rewriting the old ingestion. H1 copies the initial Rule
to observed revisions; it does not implement a general active-rule selection or
experience reliability evolution algorithm.

The feedback contract tests use a real FalkorDB connection with separate,
test-owned graph namespaces and explicitly synthetic small evidence archives.
The synthetic Query/Decision records are not native MCP execution proof. Tests
cover both PASS and FAIL, actual edge requirements, no-exposure behavior,
immutable conflicts, public projection, evidence/applicability separation,
historical Context reuse, connection persistence and a deliberate interruption
after real appends. They delete only their own graph namespace. Historical
source verification and formal current Session evidence remain separate gates.

During G1 development, an initial prototype graph imported an earlier verifier
payload. Its immutable nodes and receipt are retained. Accepted release imports
use the final bridge in a separate release namespace, rather than weakening the
conflict check. A future verifier upgrade needs an explicit VerificationRevision
contract separate from stable Run identity; H1 does not silently mutate already
stored Outcomes when the verifier source hash changes.

## Maintainer ingestion CLI

After the trusted Runner finishes and all Run writers stop, the maintainer
approves the actual Run seal SHA256. The source manifest SHA256 was approved
before the challenge. The CLI accepts exact Run/source pins and no verdict flag:

```sh
scripts/aevora-python aevora_core/scripts/ingest_orderflow_outcome.py \
  --run-dir <finished-runs-directory>/<run-id> \
  --run-id <authorized-run-id> \
  --run-seal-sha256 <approved-run-evidence-manifest-sha256> \
  --source-archive <pre-run-source-archive> \
  --source-manifest-sha256 <approved-evidence-manifest-sha256> \
  --source-snapshot-relative-path frozen_source_snapshot \
  --output <new-H1-archive>/feedback/<new-receipt>.json
```

The output's existing parent must be trusted. The CLI refuses symlink parents,
an existing receipt, or an output under the sealed Run/frozen source snapshot.
It uses a new mode-0600 file and stores the real before/after graph fingerprint,
ingestion identities, identical-repeat result and actual new conflict AuditEvent
IDs. It invokes ingestion twice without changing the pins; idempotence requires
identical semantic receipts and graph fingerprints. Run/Query writers must stay
stopped during this check; concurrent authorized graph writes may make a whole-
graph fingerprint differ and are not silently called idempotent.

Exit 0 means a verified engineering Outcome was ingested idempotently; its real
PASS/FAIL remains in the nested ingestion result. Exit 2 means pin, evidence or
trust-contract rejection; exit 3 an immutable conflict; exit 4 database
unavailability/error; exit 5 internal, receipt or idempotence failure. A failed
invocation is not a successful Outcome. Conflicts preserve the original Outcome
and append the repository's real conflict audit. Precondition rejection before
receipt creation is reported on stdout without overwriting an existing file.
Raw database credentials and private Outcome dictionaries are not written to
receipts. The pins establish the configured maintainer authority, not an
external signature or proof of a fresh native Session.

A minimal frozen source manifest is `{"files": {"frozen_source_snapshot/<path>":
"<sha256>", ...}}`; `ordinary_files_sha256` is also accepted. Copy ordinary
single-link files for every `evaluator/**/*.py`, `benchmark/sandbox.py`,
`benchmark/submission.py` and A/D private manifests. Preserve the full evaluator
source set including other hidden suites. The report's evaluator composite
fingerprint is independently checked against that complete frozen set. A suite
fingerprint additionally uses its own hidden directory, global hidden conftest
and database Oracle. Extra app, core and integration source entries are allowed.
