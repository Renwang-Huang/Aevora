"""Trusted append-only observed-outcome feedback, with causal attribution UNKNOWN.

No public MCP route calls this module. Outcome facts are minted inside ingestion
from the authorized OrderFlow archive; Agent claims cannot provide a verdict.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .models import InvalidRecord, digest, normalize_context, validate_id
from .historical_import import public_context
from .orderflow_outcome_bridge import TrustAnchor, verify_outcome, _Archive, _MAX_REPORT, _json


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidRecord(message)


def _report(anchor: TrustAnchor, report_reference, outcome: Mapping[str, Any]) -> dict:
    archive = _Archive(anchor.archive_root)
    try:
        reference = archive.reference(str(report_reference))
        return _json(archive.read(reference, _MAX_REPORT, outcome["source_report_sha256"]))
    finally:
        archive.close()


def _exposures(repo, run_id: str) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Actual persisted edges and same-run identities, never caller claims."""
    queries: dict[str, list[dict]] = {}
    rows = repo.query("MATCH (q:Query {run_id:$run})-[:CONSIDERED]->(e:Experience) "
                      "RETURN q.payload_json,q.payload_sha256,e.id ORDER BY q.id,e.id", {"run": run_id})
    for raw, fingerprint, experience_id in rows:
        record = repo._decode("Query", raw, fingerprint)
        validate_id(record["id"])
        _check(record.get("run_id") == run_id and record.get("authority") == "scoped_broker_run"
               and experience_id in record.get("candidate_experience_ids", []),
               "Query authority or candidate edge is inconsistent")
        repo.require_edge("CONSIDERED","Query",record["id"],"Experience",experience_id)
        queries.setdefault(experience_id, []).append(record)
    decisions: dict[str, list[dict]] = {}
    rows = repo.query("MATCH (d:Decision {run_id:$run})-[:DECIDED]->(e:Experience), "
                      "(d)-[:RESPONDS_TO]->(q:Query {run_id:$run})-[:CONSIDERED]->(e) "
                      "RETURN d.payload_json,d.payload_sha256,q.id,e.id ORDER BY d.id,e.id", {"run": run_id})
    for raw, fingerprint, query_id, experience_id in rows:
        record = repo._decode("Decision", raw, fingerprint)
        valid_queries = {row["id"] for row in queries.get(experience_id, [])}
        _check(record.get("run_id") == run_id and record.get("query_id") == query_id
               and query_id in valid_queries and record.get("experience_id") == experience_id
               and record.get("authority") == "UNTRUSTED_PARTICIPANT_CLAIM"
               and record.get("adoption") == "CLAIM_ONLY" and record.get("attribution") == "UNKNOWN",
               "Decision does not have an actual same-run Query/Experience chain")
        repo.require_edge("DECIDED","Decision",record["id"],"Experience",experience_id)
        repo.require_edge("RESPONDS_TO","Decision",record["id"],"Query",query_id)
        query = next(row for row in queries[experience_id] if row["id"] == query_id)
        snapshot_id = query.get("query_snapshot_ids", {}).get(experience_id)
        _check(record.get("query_snapshot_id") == snapshot_id,
               "Decision snapshot claim differs from its actual Query epoch")
        if snapshot_id:
            repo.require_query_snapshot_edge(query_id, snapshot_id)
        decisions.setdefault(experience_id, []).append(record)
    return queries, decisions


def _environment(report: Mapping[str, Any], run_context: dict | None) -> tuple[dict, dict]:
    scenario = report.get("scenario_metadata")
    _check(isinstance(scenario, dict) and isinstance(scenario.get("runtime"), dict),
           "Trusted report has no public scenario environment")
    runtime = scenario["runtime"]
    facts = public_context(runtime.get("topology"), runtime.get("database"))
    extension = runtime.get("governance_context", {})
    _check(isinstance(extension, dict), "Trusted report governance context must be an object")
    # The same six public semantic facts accepted by Participant projection;
    # no private Oracle configuration or Episode identifier is a premise.
    keys = {"operation_semantics", "authority_model", "authority_validation", "clock_domain",
            "supported_operation_set", "observed_failure_mode"}
    facts.update({key: value for key, value in extension.items() if key in keys})
    if run_context is not None:
        supplied = normalize_context(run_context)
        _check(all(key in facts and facts[key] == value for key, value in supplied.items()),
               "Provided context differs from authorized public environment")
    facts = normalize_context(facts)
    run_id = report["run_id"]
    context = {"id": "context:outcome:" + run_id, "facts": facts,
               "source_type": "trusted_report_public_environment"}
    title = scenario.get("metadata", {}).get("title")
    _check(isinstance(title, str) and 0 < len(title) <= 2000, "Missing bounded public Task title")
    task = {"id": "task:outcome:" + run_id, "public_title": title,
            "scenario_version": report.get("scenario_version", "UNAVAILABLE")}
    return context, task


def _reuse_environment(repo, outcome: dict, context: dict, task: dict) -> tuple[dict, dict]:
    rows = repo.query("MATCH (o:VerifiedOutcome {id:$id})-[:IN_CONTEXT]->(c:Context)"
                      "-[:FOR_TASK]->(t:Task) RETURN c.payload_json,t.payload_json", {"id": outcome["id"]})
    _check(len(rows) <= 1, "VerifiedOutcome has ambiguous environment")
    if rows:
        old_context, old_task = (json.loads(value) for value in rows[0])
        _check(old_context.get("facts") == context["facts"]
               and old_task.get("scenario_version") == task["scenario_version"],
               "Existing Outcome environment cannot be reinterpreted")
        return old_context, old_task
    return context, task


def ingest_outcome(repo, anchor: TrustAnchor, report_reference, *,
                   experience_ids: Sequence[str] | None = None,
                   run_context: dict | None = None) -> dict:
    """Verify real evidence, then append observed feedback without adoption inference.

    Explicit experience IDs must have actual same-run Query edges. Omitting them
    selects those persisted exposures. With no exposure the verified Outcome is
    still stored; no experience-specific revision is invented.

    Operations are individually append-only/idempotent, not a multi-statement DB
    transaction. A completion AuditEvent is added only after all required edges
    succeed. Interrupted ingestion can be retried with identical facts.
    """
    outcome = verify_outcome(anchor, report_reference)
    report = _report(anchor, report_reference, outcome)
    context, task = _environment(report, run_context)
    context, task = _reuse_environment(repo, outcome, context, task)
    queries, decisions = _exposures(repo, outcome["run_id"])
    if experience_ids is None:
        selected = sorted(queries)
    else:
        _check(not isinstance(experience_ids, (str, bytes)) and isinstance(experience_ids, Sequence)
               and 0 < len(experience_ids) <= 256, "Experience selection must be a bounded sequence")
        selected = sorted(validate_id(value) for value in experience_ids)
        _check(len(set(selected)) == len(selected), "Experience selection contains duplicates")
        _check(all(experience_id in queries for experience_id in selected),
               "Experience was not queried in this authorized Run")
    plans = []
    for experience_id in selected:
        experience = repo.get_node("Experience", experience_id)
        _check(experience is not None, "Queried Experience is unavailable")
        base_revision_id = experience_id + "/revision/initial"
        base = repo.get_node("ExperienceRevision", base_revision_id)
        _check(base is not None and base.get("experience_id") == experience_id,
               "Initial Experience revision is unavailable")
        rule_rows = repo.query("MATCH (e:Experience {id:$experience})-[:HAS_REVISION]->"
            "(r:ExperienceRevision {id:$revision})-[:USES_RULE]->(rule:Rule) RETURN rule.id ORDER BY rule.id",
            {"experience": experience_id, "revision": base_revision_id})
        rule_ids = [row[0] for row in rule_rows]
        _check(bool(rule_ids) and len(set(rule_ids)) == len(rule_ids), "Recorded revision has no unique Rule chain")
        suffix = digest([outcome["id"], experience_id])
        revision_id = experience_id + "/revision/observed-" + suffix
        query_records = sorted(queries[experience_id], key=lambda value: value["id"])
        decision_records = sorted(decisions.get(experience_id, []), key=lambda value: value["id"])
        snapshot_ids, snapshot_rule_ids, snapshot_revision_ids = set(), set(), set()
        for query_record in query_records:
            snapshot_id = query_record.get("query_snapshot_ids", {}).get(experience_id)
            if snapshot_id is None:
                continue  # Explicit legacy Queries retain their original initial-rule association.
            repo.require_query_snapshot_edge(query_record["id"], snapshot_id)
            content = repo.load_query_snapshot(snapshot_id)
            candidate = content.get("candidate", {})
            _check(candidate.get("experience_id") == experience_id
                   and content.get("context") == query_record.get("task_context"),
                   "Query snapshot association is inconsistent")
            snapshot_ids.add(snapshot_id)
            snapshot_rule_ids.update(candidate.get("rule_ids", []))
            snapshot_revision_ids.update(candidate.get("governance_projection", {}).get("selected_revision_ids", []))
        if snapshot_ids:
            rule_ids = sorted(snapshot_rule_ids)
        feedback = {"id": "feedback:" + suffix, "run_id": outcome["run_id"], "experience_id": experience_id,
            "outcome_id": outcome["id"], "outcome_digest": outcome["immutable_digest"],
            "status": "outcome_observed_no_attribution", "attribution": "UNKNOWN",
            "adoption": "UNVERIFIED", "strategy_association": "UNVERIFIED",
            "query_records": [{"id": row["id"], "payload_sha256": digest(row)} for row in query_records],
            "untrusted_decision_claims": [{"id": row["id"], "payload_sha256": digest(row)} for row in decision_records],
            "created_at": outcome["evaluated_at"], "revision_id": revision_id,
            "authority": "TRUSTED_OUTCOME_OBSERVATION_ONLY"}
        revision = {"id": revision_id, "experience_id": experience_id, "created_at": outcome["evaluated_at"],
            "revision_reason": "outcome_observed_no_attribution", "attribution": "UNKNOWN",
            "base_revision_id": base_revision_id, "feedback_id": feedback["id"]}
        if snapshot_ids:
            revision.update(revision_kind="outcome_observation", query_snapshot_ids=sorted(snapshot_ids),
                            base_revision_ids=sorted(snapshot_revision_ids))
            feedback.update(query_snapshot_ids=sorted(snapshot_ids), rule_ids=rule_ids,
                            rule_association="ACTUAL_QUERY_SNAPSHOT_EPOCH")
        source_type = "natural_agent_run" if (outcome["source_type"] == "current_live"
            and report.get("agent", {}).get("adapter") == "codex_exec") else "maintainer_seed"
        evidence = {"id": "evidence:observed:" + suffix, "source_type": source_type,
            "source_run_id": outcome["run_id"], "created_at": outcome["evaluated_at"],
            "public_summary": "An independently verified engineering outcome was observed in a Run that queried this experience. Exposure and decision claims do not establish adoption or causal benefit.",
            "attribution": "UNKNOWN", "feedback_id": feedback["id"]}
        plans.append((feedback, revision, evidence, rule_ids, query_records, decision_records))
    completion = {"id": "ingestion:orderflow:" + outcome["run_id"], "run_id": outcome["run_id"],
        "event": "trusted_outcome_ingestion_complete", "outcome_id": outcome["id"],
        "outcome_digest": outcome["immutable_digest"], "experience_ids": selected,
        "feedback_ids": [plan[0]["id"] for plan in plans], "created_at": outcome["evaluated_at"]}
    existing_completion = repo.get_node("AuditEvent", completion["id"])
    if existing_completion is not None and existing_completion != completion:
        # Use the repository's actual same-ID refusal/audit before adding chains.
        repo.put_node("AuditEvent", completion)
        raise InvalidRecord("Completed ingestion cannot acquire new exposure facts")
    # Existing conflicts are refused before any new result-specific relations.
    repo.put_node("VerifiedOutcome", outcome)
    repo.put_node("Context", context)
    repo.put_node("Task", task)
    repo.put_edge("IN_CONTEXT", "VerifiedOutcome", outcome["id"], "Context", context["id"])
    repo.put_edge("FOR_TASK", "Context", context["id"], "Task", task["id"])
    action = {"id": "action:orderflow:" + outcome["run_id"], "run_id": outcome["run_id"],
        "kind": "verified_submission_bytes", "submission_digest": outcome["submission_digest"],
        "patch_sha256": outcome["patch_sha256"], "created_at": outcome["evaluated_at"],
        "strategy_association": "UNVERIFIED", "mental_influence": "UNVERIFIED",
        "authority": "TRUSTED_REPORT_PATCH_AND_CANDIDATE_IDENTITIES"}
    repo.put_node("ObservedAction", action)
    repo.put_edge("OBSERVED_ACTION", "VerifiedOutcome", outcome["id"], "ObservedAction", action["id"])
    receipts = []
    for feedback, revision, evidence, rule_ids, query_records, decision_records in plans:
        repo.put_node("Feedback", feedback)
        repo.put_node("ExperienceRevision", revision)
        experience_id = feedback["experience_id"]
        repo.put_edge("HAS_FEEDBACK", "Experience", experience_id, "Feedback", feedback["id"])
        repo.put_edge("FROM_OUTCOME", "Feedback", feedback["id"], "VerifiedOutcome", outcome["id"])
        repo.put_edge("REVISES", "Feedback", feedback["id"], "ExperienceRevision", revision["id"])
        repo.put_edge("HAS_REVISION", "Experience", experience_id, "ExperienceRevision", revision["id"])
        repo.put_edge("REVISES", "ExperienceRevision", revision["id"], "ExperienceRevision", revision["base_revision_id"])
        for rule_id in rule_ids:
            repo.put_edge("USES_RULE", "ExperienceRevision", revision["id"], "Rule", rule_id)
        receipt = repo.attach_evidence(experience_id, evidence, outcome, context, task,
                                       relation="OBSERVED_OUTCOME", revision_id=revision["id"])
        repo.put_edge("OBSERVED_ACTION", "Evidence", evidence["id"], "ObservedAction", action["id"])
        for query in query_records:
            repo.put_edge("DERIVED_FROM", "Feedback", feedback["id"], "Query", query["id"])
        for decision in decision_records:
            repo.put_edge("RESPONDS_TO", "Feedback", feedback["id"], "Decision", decision["id"])
        receipts.append({**receipt, "feedback_id": feedback["id"], "attribution": "UNKNOWN"})
    repo.put_node("AuditEvent", completion)
    return {"status": "INGESTED", "outcome_id": outcome["id"], "run_id": outcome["run_id"],
        "verdict": outcome["verdict"], "feedback_status": "outcome_observed_no_attribution" if receipts else "no_exposure_observed",
        "attribution": "UNKNOWN", "receipts": receipts, "completion_audit_id": completion["id"],
        "observed_action_id": action["id"], "graph": repo.state_fingerprint()}
