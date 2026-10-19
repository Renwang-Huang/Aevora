"""Strict v2 source admission from pinned official own-turn/MCP evidence.

Local Host collection is the trust root, not independent runtime attestation.
No timestamps, prose, supplied actor IDs or model verdicts create identity.
"""
from pathlib import Path
import hashlib
import json
from aevora.contracts import PROFILE, digest, require
from aevora.orderflow_outcome_bridge import _Archive, _manifest, _json
from integrations.native_rollout_trace import analyze_native_rollouts


def structured(result):
    if not isinstance(result, dict):
        return None
    if result.get("isError") or result.get("is_error"):
        return None
    value = result.get("structuredContent", result.get("structured_content"))
    if isinstance(value, dict):
        return value
    values = []
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                value = json.loads(block.get("text", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                values.append(value)
    return values[0] if len(values) == 1 else None


def join_proposal(native_events, broker_events, *, run_id, candidate_id, body_sha256,
                  eligible_actors, expected_tenant):
    """Pure deterministic join; all inputs must first be Host-pinned and parsed.

    Official result's connection/session/profile and full structured reply join
    the Broker request/reply. Repeating one actor's idempotent call is allowed;
    two actors claiming the same candidate are ambiguous and rejected.
    """
    requests, replies = {}, []
    for line, event in enumerate(broker_events, 1):
        if event.get("category") != "JSONRPC":
            continue
        msg = json.loads(event["raw_json"])
        key = (event.get("connection_id"), msg.get("id"))
        if event.get("direction") == "PARTICIPANT_TO_OFFICIAL_SDK" and msg.get("method") == "tools/call":
            require(key not in requests, "SOURCE_MISMATCH")
            requests[key] = (msg, line)
        elif event.get("direction") == "OFFICIAL_SDK_TO_PARTICIPANT":
            value = structured(msg.get("result"))
            if value and value.get("candidate_id") == candidate_id:
                replies.append((key, value, line))
    matches = []
    for event in native_events:
        if event.get("event_type") != "native.McpToolCall":
            continue
        payload = event["payload"]; actor = payload["thread_id"]; item = payload["event"]
        if not (item.get("server") == "aevora" and item.get("tool") == "propose_experience"
                and item.get("status") == "completed" and item.get("error") is None):
            continue
        if digest(item.get("arguments", {}).get("proposal")) != body_sha256:
            continue
        value = structured(item.get("result"))
        if not value or value.get("candidate_id") != candidate_id:
            continue
        require(actor in eligible_actors and value.get("body_sha256") == body_sha256, "SOURCE_MISMATCH")
        scope = value.get("read_scope", {})
        require(scope.get("protocol_profile") == PROFILE and scope.get("run_id") == run_id
                and scope.get("tenant_id") == expected_tenant
                and isinstance(scope.get("connection_id"), str)
                and isinstance(scope.get("session_id"), str), "SOURCE_MISMATCH")
        joined = []
        for key, reply, line in replies:
            request, request_line = requests.get(key, ({}, 0))
            params = request.get("params", {})
            if (key[0] == scope["connection_id"] and reply == value
                    and params.get("name") == "propose_experience"
                    and params.get("arguments") == item.get("arguments")):
                joined.append(dict(connection_id=key[0], request_id=key[1],
                                   request_line=request_line, reply_line=line))
        require(len(joined) >= 1, "SOURCE_MISMATCH")
        matches.append(dict(actor_thread_id=actor, own_turn_id=item["own_turn_id"],
                            official_call_id=item["id"],
                            raw_reference=payload["raw_reference"],
                            result_sha256=digest(value), calls=joined,
                            capability_session_id=scope["session_id"]))
    require(matches and len({m["actor_thread_id"] for m in matches}) == 1, "SOURCE_MISMATCH")
    return matches


def verify_native_v2(anchor, outcome, candidate_id, body_sha256, *, expected_tenant):
    arc = _Archive(anchor.archive_root)
    try:
        pins = _manifest(arc, anchor.manifest_relative_path, anchor.manifest_sha256)
        def read(name, maximum):
            require(name in pins, "SOURCE_MISMATCH")
            return arc.read(name, maximum, pins[name])
        metadata = _json(read("runtime_metadata.json", 8 * 1024**2))
        run = outcome["run_id"]
        require(metadata.get("run_id") == run and metadata.get("fresh_session") is True
                and metadata.get("exit_code") == 0 and metadata.get("runtime_result") == "PASS", "SOURCE_MISMATCH")
        require(metadata.get("experience", {}).get("protocol_profile") == PROFILE, "SOURCE_MISMATCH")
        native = metadata.get("native_rollouts", {})
        require(native.get("availability") == "AVAILABLE", "SOURCE_MISMATCH")
        for f in native.get("files", []):
            try:
                relative = str(Path(f["path"]).relative_to(anchor.archive_root))
            except (KeyError, ValueError):
                require(False, "SOURCE_MISMATCH")
            require(relative.startswith("artifacts/native_rollouts/") and pins.get(relative) == f["sha256"], "SOURCE_MISMATCH")
            require(hashlib.sha256(read(relative, 64 * 1024**2)).hexdigest() == f["sha256"], "SOURCE_MISMATCH")
        parsed = analyze_native_rollouts(run, anchor.archive_root, native,
                                        expected_parent_thread_id=metadata.get("thread_id"))
        summary = parsed["summary"]
        require(summary["integrity"]["status"] == "COMPLETE" and
                summary["session_id"] == metadata.get("session_id") == metadata.get("thread_id"), "SOURCE_MISMATCH")
        require(summary.get("root_terminal", {}).get("completed") is True, "SOURCE_MISMATCH")
        # Official exec start is separate from the own rollout metadata.
        starts = [json.loads(l) for l in read("codex_events.jsonl", 32 * 1024**2).splitlines()
                  if json.loads(l).get("type") == "thread.started"]
        require(len(starts) == 1 and starts[0].get("thread_id") == summary["thread_id"], "SOURCE_MISMATCH")
        actors = {summary["thread_id"]} | {a["agent_id"] for a in summary["subagents"]["agents"] if a["verified"]}
        gateway = read("gateway_transport_events.jsonl", 64 * 1024**2).splitlines(keepends=True)
        provider = []
        for i, raw in enumerate(gateway, 1):
            e = json.loads(raw); d = e.get("detail", {})
            if (e.get("source") == "trusted_gateway_transport" and e.get("event_type") == "REQUEST_FINISHED"
                    and e.get("run_id") == run and d.get("run_id") == run
                    and d.get("route") == "/v1/responses" and d.get("outcome") == "COMPLETED"
                    and d.get("http_status") == 200 and d.get("response_completed") is True
                    and d.get("actual_model") == metadata.get("model") and d.get("response_id")):
                provider.append(dict(line=i, sha256=hashlib.sha256(raw).hexdigest(), response_id=d["response_id"]))
        require(provider, "SOURCE_MISMATCH")
        broker = [json.loads(l) for l in read("aevora_mcp_events.jsonl", 32 * 1024**2).splitlines()]
        matches = join_proposal(parsed["events"], broker, run_id=run, candidate_id=candidate_id,
                                body_sha256=body_sha256, eligible_actors=actors,
                                expected_tenant=expected_tenant)
        actor = matches[0]["actor_thread_id"]
        actor_responses = {r["response_id"] for r in summary["usage"]["records"]
                           if r["thread_id"] == actor}
        actor_provider = [p for p in provider if p["response_id"] in actor_responses]
        require(actor_provider, "SOURCE_MISMATCH")
        return dict(version="aevora.native-source/2.3", native_thread_id=summary["thread_id"],
                    native_tenant_id=expected_tenant,
                    native_session_id=summary["session_id"],
                    proposal_actor_thread_id=matches[0]["actor_thread_id"],
                    proposal_call_references=matches, provider_completion_references=actor_provider,
                    native_subagents=summary["subagents"]["verified_count"],
                    source_assurance="HOST_PINNED_OFFICIAL_EVENTS_NOT_EXTERNAL_ATTESTATION")
    finally:
        arc.close()
