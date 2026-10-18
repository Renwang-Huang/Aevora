# Aevora Full Archive and Audit-Lite

## Authority and preservation

Full Archive is the complete new H1 maintainer evidence collection. Historical
archives, scores, Run IDs and raw bytes are protected inputs. New commands,
failed attempts, source freezes, actual database/MCP responses, native traces,
submissions and independent evaluations go into the new `aevora_validation/`
collection. Stop all writers before its final manifest/seal. A snapshot made
after changes is not a pristine pre-run source freeze.

Audit-Lite is **MAINTAINER_AUDIT**, never Participant input. The existing
`benchmark.evidence_export.export_archive()` and stdlib
`benchmark.evidence_verify` remain unchanged. They already provide bounded
regular-file reads, source/index cross-checks, content-addressed ZIP objects,
portable paths, credential redaction, line provenance, no-overwrite publication
and offline Run/JUnit/Oracle/submission/native-reference consistency checks.

Its existing selection includes collection `PROTOCOL.json`, but not arbitrary
new design documents or `aevora_mcp_events.jsonl`. A new Aevora audit capsule
therefore explicitly carries these required bytes through that supported entry.
The old selector and historical archives are not monkeypatched or rewritten.

## Capsule collection API

`aevora.audit_capsule.build_capsule(archive, public_assets, secret_values=())`
is read-only. `public_assets` is an explicit finite mapping from safe paths
relative to the new archive to a category or descriptor. The caller first
copies authorized public source/design into ordinary single-link archived
files; absolute paths and traversal cannot import unrelated host data.

```python
from aevora.audit_capsule import build_capsule

capsule = build_capsule(new_full_archive, {
    "public_design/ARCHITECTURE.md": "DESIGN",
    "public_design/GRAPH_SCHEMA.md": "GRAPH_SCHEMA",
    "public_design/QUERY_COOKBOOK.md": "QUERY_COOKBOOK",
    "G0_GATE.json": "GATE",
    "G1_RELEASE_GATE.json": "GATE",
    "G2_GATE.json": "GATE",
    "G3_GATE.json": "GATE",
    "G4_GATE.json": "GATE",
    "G5_GATE.json": "GATE",
    "final-tests.junit.xml": "JUNIT",
    "runs/<run-id>/aevora_mcp_events.jsonl": "MCP_TRACE",
    "feedback/trusted_outcome_receipt.json": "OUTCOME",
    "SOURCE_CHANGE_MANIFEST.json": "SOURCE_CHANGE",
    "public_source/aevora/models.py": {"category": "SOURCE_CHANGE", "representation": "base64"},
}, secret_values=trusted_in_memory_secret_values)
# Trusted collector writes a NEW protocol, then seals the finished archive:
# protocol = {"suite_expectations": approved_suite_metadata,
#             "aevora_capsule": capsule, ...}
```

This example is a selection template, not a claim that every named file already
exists or every Gate passed. The collector must use exact real paths, retain all
attempts and list every required Gate. A missing Gate remains UNVERIFIED in the
final report; it must not be replaced by a fabricated receipt. The helper never
writes `PROTOCOL.json`, seals an archive or chooses a Benchmark score.

All eight categories are mandatory: DESIGN, GRAPH_SCHEMA, QUERY_COOKBOOK, GATE,
JUNIT, MCP_TRACE, OUTCOME, SOURCE_CHANGE. The final inventory must include design
**bodies**, complete actual Gate reports, test JUnit, anonymized original MCP
JSON-RPC evidence, key independent Outcome and the exact source change list.
Category coverage is a machine-checkable minimum, not proof that a design is
good or all six Gate requirements were achieved.

## Bytes, transformation and line maps

Every entry records original relative path, source length/SHA256, exported
length/SHA256, category, representation and transformation. Text assets default
to readable `utf8_text`; source `.py`/config/script assets default to base64 of
their **exported bytes**. Either representation can be requested explicitly.
Base64 is not encryption and cannot exempt content from credential scanning.
The existing portable transformation is reused, then caller-supplied arbitrary
secret values are redacted. Pattern detection cannot discover every arbitrary
secret; the collector must supply known in-memory project keys/tokens, and the
Runtime must keep credentials out of evidence at the source.

If bytes were unchanged, included bytes directly match the original source SHA.
After redaction/path normalization, the original source SHA is a Full Archive
pointer and original transformed bytes are UNVERIFIED from Lite alone. Exported
bytes have their own digest. JSONL files include every original line, ending
and ordinal with separate source/export line hashes. Malformed lines remain
malformed and are counted in verification; they are not converted into new
official tool events. No trace slicing is performed.

Sources are bounded to 256 entries, 8 MiB per file, 48 MiB aggregate content and
80 MiB serialized capsule. Ordinary UTF-8 public evidence only is accepted.
Linked directories, symlinks, hardlinks, FIFOs, changing reads, credential files,
hidden/reference/private-manifest source, Participant workspaces, state
directories, executable binaries and business databases are refused.

## Export and independent verification

After the new Full manifest indexes the capsule's real source paths and new
`PROTOCOL.json`, use the unchanged exporter with explicit real Run IDs and a new
destination outside Full:

```python
from benchmark.evidence_export import export_archive
receipt = export_archive(full_archive, new_output_zip, run_ids=finished_run_ids,
                         created_at="<fixed-ISO-time-with-timezone>")
```

The ordinary exporter maps capsule source files that its selector does not
include to `NOT_INCLUDED.json`. Their bytes are available as capsule content;
the source-file selection remains honestly reported as omitted. The capsule
verifier cross-checks each original source SHA against the outer included or
omitted Full index. It does not silently upgrade transformed original pointers.

Use trusted verifier source obtained through a separate channel and compare an
externally supplied bundle SHA256. Then:

```python
from benchmark.evidence_verify import verify_bundle
from aevora.audit_capsule import verify_exported_capsule
benchmark_review = verify_bundle(audit_zip)
aevora_review = verify_exported_capsule(audit_zip)
```

The Aevora verifier first executes the unchanged Benchmark consistency verifier,
then reads the capsule inside exported `PROTOCOL.json`. It verifies the capsule
digest, exact included content bytes, required category policy, unique paths,
JSONL hashes/order/completeness, nonempty structurally correct JUnit and source
index agreement. A missing/malformed/tampered capsule or source pointer fails.
It never follows a source path, extracts ZIP files, executes bundled code,
imports a Participant patch, calls a model or contacts the database/network.

This verifier needs trusted installed project source because it reuses the
Benchmark implementation. The bundled old stdlib verifier alone checks
Benchmark consistency and does not implement Aevora capsule semantics. A package
and its own checksums/verifier can all be replaced by an adversary; self-checking
does not authenticate origin.

## Claims the lightweight verifier does not establish

Verification PASS means included byte/metadata consistency, explicit category
coverage and structural cross-checks. It does not mean every Gate PASS, every
JUnit test PASS, an authentic model origin, genuine subagents, causal adoption
or success-rate improvement. FAIL/TIMEOUT/ERROR and malformed lines are retained.
Native model/subagent claims require cross-review against official raw rollout
and parent completion evidence; MCP broker JSON-RPC alone cannot establish them.

`runtime_origin_attestation`, `semantic_gate_claims` and transformed original
bytes remain UNVERIFIED. Omitted files remain Full-only hash pointers. External
auditors can inspect actual readable designs, Cypher, patches, Gate failures,
JUnit and raw MCP messages in the capsule, but must state which conclusions are
manual analysis, local dynamic evidence or still unverifiable.

## Validation evidence

The new `test_audit_capsule.py` uses explicitly synthetic files/Run metadata.
Its actual initial execution was 59/59 PASS (exit 0), archived under
`aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/audit-capsule-tests`.
It exercises the unchanged exporter's real roundtrip, retained failure/timeout,
source preservation, complete CRLF/malformed JSONL provenance, content/line/index
tampering, base64 secret scanning, all required categories, path/file boundaries
and finite budgets. This is export-contract evidence, not a native Agent Session.
The final actual H1 package export/verification needs its own separate receipt.
