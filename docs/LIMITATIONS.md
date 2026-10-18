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
  public verifier, never an independent private engineering grade or Native model.
- Production TrustedHost/Q07 verification requires private registered source and
  Outcome authorities. It is not silently replaced by the public synthetic seed.
- Historical public summaries do not allow third parties to re-run private Oracle
  assertions. Their hashes verify public bytes, not externally attest private facts.
- Rules/eligibility are decided by the organizer. Reused foundations and in-period
  changes are disclosed; a recent push date is not evidence of original creation.
