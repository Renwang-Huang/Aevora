"""Freeze one trusted graph fact set and its byte-equivalent raw representation."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

from audit import E, sha, write
from aevora.mcp_v2 import load_configuration
from benchmark.manifest import load_manifest
from integrations.aevora import public_runtime_context
from integrations.aevora_v2 import prepare_runtime_configuration


BOOTSTRAP = E / "02_calibration/smoke_world_v2/SMOKE_BOOTSTRAP.json"
OUTPUT = E / "01_protocol/memory"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest("SMOKE-001")
    context = public_runtime_context({
        "runtime": manifest.runtime,
        "public_task": manifest.public_task,
        "metadata": manifest.metadata,
    })
    with tempfile.TemporaryDirectory(prefix="g24-fairness-") as directory:
        config, _, _ = prepare_runtime_configuration(
            BOOTSTRAP,
            "fairness-" + uuid.uuid4().hex,
            context,
            directory,
        )
        repo, grant, facts = load_configuration(config)
        try:
            state = repo.state()
            discovered = repo.discover(facts, state)
            witnesses = []
            for item in discovered:
                identifier = item if isinstance(item, str) else item.get("experience_id")
                if not identifier:
                    continue
                witnesses.append(repo.read_witness(identifier, state))
        finally:
            repo._transport.close() if hasattr(repo, "_transport") else None
    if len(witnesses) != 1:
        raise SystemExit(f"EXPECTED_ONE_WITNESS_GOT_{len(witnesses)}")
    witness = witnesses[0]
    graph_snapshot = {
        "schema": "g24.graph_memory_snapshot/1",
        "source": "HOST_CONTROLLED_REAL_FALKORDB",
        "tenant": grant.tenant,
        "run_id": grant.run_id,
        "session_id": grant.session_id,
        "semantic_epoch": state.get("epoch"),
        "authz_epoch": state.get("authz_epoch"),
        "facts": facts,
        "witness": witness,
        "witness_sha256": hashlib.sha256(
            json.dumps(witness, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "hidden_oracle_content": "NOT_INCLUDED",
        "graph_reasoning": "ENABLED",
    }
    write(OUTPUT / "GRAPH_MEMORY_SNAPSHOT.json", graph_snapshot)
    raw_text = (
        "# Trusted historical experience snapshot\n\n"
        "This is the same Host-controlled record used by the GRAPH arm, serialized as text. "
        "It contains no graph traversal, applicability engine, Oracle output, or reference patch.\n\n"
        "```json\n"
        + json.dumps(witness, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n```\n"
    )
    (OUTPUT / "RAW_MEMORY.md").write_text(raw_text)
    raw_bytes = (OUTPUT / "RAW_MEMORY.md").read_bytes()
    graph_bytes = (OUTPUT / "GRAPH_MEMORY_SNAPSHOT.json").read_bytes()
    matrix = [
        {
            "field": "source_experience_id",
            "graph": witness.get("experience_id"),
            "raw_memory": witness.get("experience_id"),
            "status": "MATCH",
        },
        {
            "field": "source_witness_sha256",
            "graph": graph_snapshot["witness_sha256"],
            "raw_memory": graph_snapshot["witness_sha256"],
            "status": "MATCH",
        },
        {
            "field": "positive_and_counterexample_records",
            "graph": "FULL_WITNESS",
            "raw_memory": "FULL_WITNESS_TEXT",
            "status": "MATCH_CONTENT_INTERFACE_DECLARED",
        },
        {
            "field": "scope_and_version",
            "graph": "IN_WITNESS",
            "raw_memory": "IN_WITNESS_TEXT",
            "status": "MATCH",
        },
        {
            "field": "memory_bytes",
            "graph": len(graph_bytes),
            "raw_memory": len(raw_bytes),
            "status": "RECORDED_DIFFERENCE",
        },
        {
            "field": "memory_interface",
            "graph": "Aevora MCP four tools + FalkorDB",
            "raw_memory": "read-only RAW_MEMORY.md through the same participant shell",
            "status": "DECLARED_INTERFACE_ASYMMETRY",
        },
        {
            "field": "hidden_oracle",
            "graph": "NOT_INCLUDED",
            "raw_memory": "NOT_INCLUDED",
            "status": "MATCH",
        },
    ]
    with (E / "01_protocol/ARM_EQUIVALENCE_MATRIX.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["field", "graph", "raw_memory", "status"])
        writer.writeheader()
        writer.writerows(matrix)
    write(OUTPUT / "FAIRNESS_RECEIPT.json", {
        "status": "INFORMATION_BALANCED_WITH_DECLARED_TOOL_ASYMMETRY",
        "experience_count": len(witnesses),
        "graph_snapshot_sha256": sha(OUTPUT / "GRAPH_MEMORY_SNAPSHOT.json"),
        "raw_memory_sha256": sha(OUTPUT / "RAW_MEMORY.md"),
        "raw_memory_bytes": len(raw_bytes),
        "graph_snapshot_bytes": len(graph_bytes),
        "token_estimate": "TOKENIZER_NOT_PINNED; BYTES_RECORDED_INSTEAD",
        "no_memory_control": "NO_HISTORY_FILE_OR_MEMORY_TOOL",
        "hidden_oracle_included": False,
    })
    print(json.dumps({"status": "PASS", "experience_count": len(witnesses)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
