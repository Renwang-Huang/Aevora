"""Host-only source verification; Participant self-reports never enter this API."""

import json
from .models import InvalidRecord, digest, utc_now
from .candidate import CandidateLifecycle


def _source_epoch(manifest_sha256):
    """Identify the already verified source manifest without inferring a phase."""
    if (
        not isinstance(manifest_sha256, str)
        or len(manifest_sha256) != 64
        or any(value not in "0123456789abcdef" for value in manifest_sha256)
    ):
        raise InvalidRecord("A pinned source manifest SHA256 is required")
    return "sealed-run-manifest:sha256:" + manifest_sha256


def verify_orderflow_candidate(repo, candidate_id, anchor, report_reference):
    from .orderflow_outcome_bridge import verify_outcome, _Archive, _manifest, _json
    from .feedback import ingest_outcome, _report, _environment

    outcome = verify_outcome(anchor, report_reference)
    view = CandidateLifecycle(repo).inspect(candidate_id)
    if (
        outcome["run_id"] != view["candidate"]["run_id"]
        or anchor.profile != "current_live"
    ):
        raise InvalidRecord(
            "Candidate needs the independently pinned same-run current-live source"
        )
    report = _report(anchor, report_reference, outcome)
    with_archive = _Archive(anchor.archive_root)
    try:
        files = _manifest(
            with_archive, anchor.manifest_relative_path, anchor.manifest_sha256
        )

        def read(name, maximum):
            if name not in files:
                raise InvalidRecord("Required native source is not sealed")
            return with_archive.read(name, maximum, files[name])

        metadata = _json(read("runtime_metadata.json", 4 * 1024 * 1024))
        if (
            metadata.get("run_id") != outcome["run_id"]
            or metadata.get("fresh_session") is not True
        ):
            raise InvalidRecord("Fresh native Run source required")
        if (
            metadata.get("thread_id") in (None, "UNAVAILABLE")
            or metadata.get("exit_code") != 0
        ):
            raise InvalidRecord("Completed official native Runtime source required")
        events = [
            json.loads(line)
            for line in read("aevora_mcp_events.jsonl", 8 * 1024 * 1024).splitlines()
        ]
        requests = {}
        replies = []
        matched = []
        for event in events:
            if event.get("category") != "JSONRPC":
                continue
            msg = json.loads(event["raw_json"])
            key = (event.get("connection_id"), msg.get("id"))
            if (
                event.get("direction") == "PARTICIPANT_TO_OFFICIAL_SDK"
                and msg.get("method") == "tools/call"
            ):
                requests[key] = msg
            if event.get("direction") == "OFFICIAL_SDK_TO_PARTICIPANT":
                result = (msg.get("result") or {}).get("structuredContent") or {}
                if result.get("candidate_id") == candidate_id:
                    replies.append((key, result))
        for key, result in replies:
            req = requests.get(key, {}).get("params", {})
            if (
                req.get("name") == "propose_experience"
                and digest(req.get("arguments", {}).get("proposal"))
                == view["candidate"]["body_sha256"]
            ):
                matched.append(
                    {
                        "connection_id": key[0],
                        "request_id": key[1],
                        "candidate_id": candidate_id,
                    }
                )
        if not matched:
            raise InvalidRecord("Actual sealed scoped proposal request/reply missing")
        # Raw official events are separately retained. Native identity derives
        # from the completed runtime receipt, not caller-written proposal data.
        raw_native = read("codex_events.jsonl", 32 * 1024 * 1024)
        native_lines = raw_native.splitlines(keepends=True)
        native = [json.loads(line) for line in native_lines]
        starts = [e for e in native if e.get("type") == "thread.started"]
        if len(starts) != 1 or starts[0].get("thread_id") != metadata["thread_id"]:
            raise InvalidRecord("Official native thread-start source missing")

        def native_candidate(e):
            result = e.get("item", {}).get("result") or {}
            value = result.get("structuredContent", result.get("structured_content"))
            if isinstance(value, dict):
                return value.get("candidate_id")
            for block in result.get("content", []):
                if block.get("type") == "text":
                    try:
                        value = json.loads(block.get("text", ""))
                    except (ValueError, TypeError):
                        continue
                    if isinstance(value, dict):
                        return value.get("candidate_id")
            return None

        proposal_events = [
            e
            for e in native
            if e.get("item", {}).get("type") == "mcp_tool_call"
            and e["item"].get("server") == "aevora"
            and e["item"].get("tool") == "propose_experience"
            and e["item"].get("status") == "completed"
            and native_candidate(e) == candidate_id
            and digest(e["item"].get("arguments", {}).get("proposal"))
            == view["candidate"]["body_sha256"]
        ]
        if not proposal_events:
            raise InvalidRecord("Official typed native proposal completion missing")
    finally:
        with_archive.close()
    receipt = ingest_outcome(repo, anchor, report_reference)
    context, _ = _environment(report, None)
    patch = report.get("agent", {}).get("submission_sha256")
    if not patch:
        raise InvalidRecord("Actual native patch reference required")
    source = {
        "id": "source-verification:" + digest([candidate_id, anchor.manifest_sha256]),
        "candidate_id": candidate_id,
        "run_id": outcome["run_id"],
        "authority": "TRUSTED_HOST_SOURCE_VERIFIER",
        "origin": "natural_agent_run",
        "source_epoch": _source_epoch(anchor.manifest_sha256),
        "source_sha256": anchor.manifest_sha256,
        "submission_sha256": patch,
        "outcome_id": outcome["id"],
        "facts": context["facts"],
        "native_thread_id": metadata["thread_id"],
        "proposal_call_references": matched,
        "official_native_proposal_event_sha256": [digest(e) for e in proposal_events],
        "proposal_event_references": [
            {
                "file": "codex_events.jsonl",
                "line": i + 1,
                "sha256": __import__("hashlib").sha256(native_lines[i]).hexdigest(),
                "sha256_scope": "ARCHIVED_BYTES_INCLUDING_NEWLINE",
            }
            for i, e in enumerate(native)
            if e in proposal_events
        ],
        "causal_benefit": "UNKNOWN",
    }
    repo.put_node("SourceVerification", source)
    repo.put_edge(
        "HAS_SOURCE_VERIFICATION",
        "Candidate",
        candidate_id,
        "SourceVerification",
        source["id"],
    )
    return {
        "source": source,
        "trusted_feedback": receipt,
        "outcome_verdict": outcome["verdict"],
    }


def record_external_observation(repo, run_id, *, source_sha256, summary):
    from .candidate import public_text
    from .models import validate_id

    validate_id(run_id)
    public_text(summary)
    value = {
        "id": "external-observation:" + digest([run_id, source_sha256, summary]),
        "run_id": run_id,
        "source_sha256": source_sha256,
        "public_summary": summary,
        "authority": "EXTERNAL_UNVERIFIED",
        "trusted_outcome": "NOT_CREATED",
        "attribution": "UNKNOWN",
    }
    repo.put_node("ExternalObservation", value)
    return value
