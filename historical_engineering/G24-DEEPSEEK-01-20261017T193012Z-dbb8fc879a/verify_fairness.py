"""Verify the raw text is a faithful serialization of the graph witness."""
from __future__ import annotations

import hashlib
import json
import re

from audit import E, write


def main() -> int:
    graph = json.loads((E / "01_protocol/memory/GRAPH_MEMORY_SNAPSHOT.json").read_text())
    raw = (E / "01_protocol/memory/RAW_MEMORY.md").read_text()
    match = re.search(r"```json\n(.*)\n```", raw, re.S)
    if not match:
        raise SystemExit("RAW_JSON_BLOCK_MISSING")
    text_witness = json.loads(match.group(1))
    graph_witness = graph["witness"]
    text_sha = hashlib.sha256(
        json.dumps(text_witness, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result = {
        "status": "PASS" if text_sha == graph["witness_sha256"] else "FAIL",
        "witness_sha256": graph["witness_sha256"],
        "raw_text_witness_sha256": text_sha,
        "same_experience_id": text_witness.get("experience_id") == graph_witness.get("experience_id"),
        "same_scope": text_witness.get("scope") == graph_witness.get("scope"),
        "same_limitations": text_witness.get("limitations") == graph_witness.get("limitations"),
        "same_evidence_nodes": text_witness.get("evidence_nodes") == graph_witness.get("evidence_nodes"),
        # This is authority metadata only. The hidden test implementation,
        # private expectations, and reference patch are not witness content.
        "trusted_oracle_authority_metadata_visible": bool(
            graph.get("hidden_oracle_content") == "NOT_INCLUDED"
        ),
        "hidden_oracle_test_content_exposed": not (
            graph.get("hidden_oracle_content") == "NOT_INCLUDED"
        ),
        "hidden_oracle_content_marker": graph.get("hidden_oracle_content"),
    }
    if not all(result[key] for key in (
        "same_experience_id", "same_scope", "same_limitations",
        "same_evidence_nodes", "trusted_oracle_authority_metadata_visible",
    )):
        result["status"] = "FAIL"
    if result["hidden_oracle_test_content_exposed"]:
        result["status"] = "FAIL"
    write(E / "01_protocol/memory/FAIRNESS_VERIFICATION.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
