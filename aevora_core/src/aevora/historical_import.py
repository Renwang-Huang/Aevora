"""Maintainer-only import of exact, authorized historical strategy controls.

These are verified historical replays. The natural strategy's original Session
is a separate origin; no replay is advertised as a fresh Agent Session.
"""
from pathlib import Path

from .orderflow_outcome_bridge import verify_historical_seeds
from .models import utc_now

ATOMIC_ID = "experience:sqlite-atomic-reservation"
LOCK_ID = "experience:process-local-reservation-lock"


def public_context(topology: str | None, database="sqlite") -> dict:
    """Semantic public runtime facts; no Episode ID, hidden label or fix hint."""
    scope = {"single_process_multi_thread": "single_process_threads",
             "multi_process_shared_sqlite": "independent_processes"}.get(topology)
    return {"concurrency_scope": scope, "worker_count_known": True if scope else None,
        "shared_state_kind": "sqlite_file" if database == "sqlite" else None,
        "synchronization_scope": "shared_process_object" if scope == "single_process_threads" else "per_process" if scope == "independent_processes" else None,
        "transaction_guarantees": "sqlite_atomic_write_transactions" if database == "sqlite" else None,
        "observed_failure_mode": "inventory_ledger_inconsistency"}


def import_verified_history(repo, archive: Path) -> dict:
    verified = verify_historical_seeds(archive)
    created = utc_now()
    experiences = [
        {"id": ATOMIC_ID, "strategy": "sqlite_conditional_update_in_transaction",
         "title": "Conditional inventory writes with coherent durable records",
         "source_type": "natural_agent_run", "created_at": created,
         "origin_run_id": "339f7d73-29df-4242-8920-9e566bce8a9c",
         "origin_patch_sha256": "0525c9650546d438589bd26e7bafd46cd0b1e51b6e469fd67bcb8458138d9f0f",
         "public_summary": "An actual historical Agent used a capacity-conditioned relative SQL update inside a write transaction. The exact resulting source tree was separately evaluated in threaded and independent-worker SQLite environments.",
         "limitations": ["Evidence concerns SQLite with a shared persistent database and the recorded API semantics.",
             "Investigate the complete order, inventory and ledger unit of work and retry/recovery behavior; this is a principle, not a patch to copy.",
             "The A/D support records are maintainer replays of one actual Agent artifact, not two new Agent Sessions or causal governance evidence."]},
        {"id": LOCK_ID, "strategy": "complete_process_local_rlock",
         "title": "Complete critical section under a shared process-local lock",
         "source_type": "maintainer_seed", "created_at": created,
         "public_summary": "A maintainer-created complete RLock critical section passed a real single-process threaded evaluation. The exact same source tree failed with independent OS workers sharing SQLite.",
         "limitations": ["All relevant operations must share the same synchronization object in the same process.",
             "An ordinary process-local lock provides no coordination between independent OS workers.",
             "This is a controlled maintainer strategy and counterexample, not an Agent-invented strategy."]}]
    rules = {
        ATOMIC_ID: {"id": "rule:sqlite-atomic-reservation:1", "version": "1.0.0",
            "public_description": "Use the recorded database principle only within the verified SQLite durability and shared-state capabilities.",
            "premises": [{"id": "premise:atomic:state", "fact_key": "shared_state_kind", "allowed_values": ["sqlite_file"]},
                         {"id": "premise:atomic:transactions", "fact_key": "transaction_guarantees", "allowed_values": ["sqlite_atomic_write_transactions"]}]},
        LOCK_ID: {"id": "rule:process-local-lock:1", "version": "1.0.0",
            "public_description": "A process lock is supported only for a shared synchronization object in one process.",
            "premises": [{"id": "premise:lock:topology", "fact_key": "concurrency_scope", "allowed_values": ["single_process_threads"]},
                         {"id": "premise:lock:object", "fact_key": "synchronization_scope", "allowed_values": ["shared_process_object"]}]}}
    before = repo.state_fingerprint()
    rows = []
    for exp in experiences:
        existing = repo.get_node("Experience", exp["id"])
        if existing:
            exp["created_at"] = existing["created_at"]
        repo.import_experience(exp, rules[exp["id"]])
        kind = "atomic" if exp["id"] == ATOMIC_ID else "rlock"
        for label, topology, relation in ((kind+"_a", "single_process_multi_thread", "SUPPORTED_BY"),
             (kind+"_d", "multi_process_shared_sqlite", "SUPPORTED_BY" if kind=="atomic" else "COUNTEREXAMPLE")):
            outcome = verified["outcomes"][label]
            run = outcome["run_id"]
            evidence = {"id": "evidence:history:"+run, "source_type": exp["source_type"], "created_at": outcome["evaluated_at"],
                "source_run_id": run, "public_summary": f"Historical maintainer replay of the exact strategy source tree: {outcome['verdict']}, {outcome['test_count']} necessary cases, independently checked durable records.",
                "historical_replay": True, "source_manifest_sha256": outcome["source_manifest_sha256"], "attribution": "CONTROLLED_STRATEGY_APPLICABILITY_ONLY"}
            context = {"id": "context:history:"+run, "source_type": "maintainer_verified_public_runtime", "facts": public_context(topology)}
            task = {"id": "task:history:"+run, "public_title": "Independent workers sharing SQLite" if topology.startswith("multi_process") else "Single process threaded inventory", "scenario_version": "2.0.0" if topology.startswith("multi_process") else "1.0.0"}
            rows.append(repo.attach_evidence(exp["id"], evidence, outcome, context, task, relation=relation))
    return {"status":"IMPORTED", "before":before, "after":repo.state_fingerprint(), "chains":rows,
        "provenance":verified["provenance_observations"], "assurance":"Four distinct historically executed outcomes, currently byte-verified; no new hidden-suite execution in this import"}
