"""Extract bounded actual read queries for maintainer audit, never a task input."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def extract(archive):
    source = "g3/historical-corpus-readonly-review-v1/trusted_graph_commands.jsonl"
    path = archive / source
    data = path.read_bytes()
    if len(data) > 128 * 1024**2 or path.is_symlink():
        raise ValueError("Bounded ordinary raw SDK evidence is required")
    rows, seen = [], set()
    for line, raw in enumerate(data.splitlines(keepends=True), 1):
        value = json.loads(raw)
        command = value.get("command", [])
        if len(command) < 3 or command[0] != "GRAPH.RO_QUERY":
            continue
        query = command[2]
        if not isinstance(query, str) or len(query) > 5000 or query in seen:
            continue
        seen.add(query)
        rows.append({"actual_command": command, "options": value.get("options", {}),
            "raw_source_reference": {"path": source, "line": line,
                "line_sha256": sha256(raw).hexdigest(), "file_sha256": sha256(data).hexdigest()},
            "actual_response_sha256": sha256(json.dumps(value["actual_response"], ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "response_disclosure": "NOT_INCLUDED; full raw host response remains in Full Archive"})
        if len(rows) == 20:
            break
    if not rows:
        raise ValueError("No actual SDK read query found")
    output = archive / "AUDIT_KEY_CYPHER.json"
    with output.open("x") as stream:
        json.dump({"classification": "ACTUAL_SDK_READ_QUERY_EXTRACTION",
            "scope": "Maintainer Audit-Lite, never Participant input; no graph mutation or model call",
            "rows": rows, "source_report": "g3/historical-corpus-readonly-review-v1/CORPUS_REVIEW_GATE.json"},
            stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"path": str(output), "queries": len(rows), "sha256": sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    extract(parser.parse_args().archive.absolute())
