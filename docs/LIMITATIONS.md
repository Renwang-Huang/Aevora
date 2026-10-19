# Known limits and claim boundaries

- G23: FUNCTIONAL ACCEPTED / RELIABILITY CONDITIONAL. The pinned owned FalkorDB
  experienced a real SIGSEGV/139; root cause remains UNVERIFIED. No engine fix is
  claimed by this productization release. Historical AOF-reload139 is separate.
- Demo AOF and automatic snapshots are disabled. Container restart durability is
  limited to explicitly saved graph state; unsaved crash tails can be lost. A
  fresh demo is reproducible; that is not a production recovery guarantee.
- Historical Native isolation shares a Linux kernel/UID and is PARTIAL. Local
  protection is not third-party attestation. Public Compose is not a Participant
  sandbox or an authenticated cloud deployment.
- Cross-network revocation has an in-flight operation window. Epoch checks and
  completeness are enforced; arbitrary distributed linearizability is not claimed.
- Agent record_decision is an untrusted claim. Querying is not adoption; a passing
  patch plus a viewed experience does not prove causal improvement.
- G24 DeepSeek Single-Agent pre-registration is separate and unchanged. Pilot and
  formal three-arm comparisons have NOT RUN. Comparative causal benefit UNKNOWN.
- Live synthetic examples, historical sanitized G23 evidence and legacy Replay
  are different sources. Synthetic VerifiedOutcome records describe only an owned
  public verifier, never an independent Benchmark engineering grade or Native model.
- TrustedHost/Q07 and Oracle implementation source is included in the full
  engineering release. Production verification still requires explicitly
  registered source/Outcome authorities and protected credentials; the synthetic
  demo seed does not provide them.
- Historical Oracle tests and reference answers are public and support new
  reproductions. They are no longer future blind tests. Original private model
  conversations and some historical run evidence remain unpublished; a new
  reproduction or summary hash does not re-certify every original session.
- The approved full-source baseline retains 51 SKIP results for legacy G1 tests
  requiring an authenticated historical import. Episodes B/C remain
  PLANNED / NOT_IMPLEMENTED; no historical skip or unfinished experiment is
  converted into PASS by this documentation update.
- Rules/eligibility are decided by the organizer. Reused foundations and in-period
  changes are disclosed; a recent push date is not evidence of original creation.
