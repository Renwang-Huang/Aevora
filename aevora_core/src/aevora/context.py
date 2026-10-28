"""Convert observed execution topology into public context facts."""


def public_context(topology: str | None, database="sqlite") -> dict:
    """Semantic public runtime facts; no Episode ID, hidden label or fix hint."""
    scope = {
        "single_process_multi_thread": "single_process_threads",
        "multi_process_shared_sqlite": "independent_processes",
    }.get(topology)
    return {
        "concurrency_scope": scope,
        "worker_count_known": True if scope else None,
        "shared_state_kind": "sqlite_file" if database == "sqlite" else None,
        "synchronization_scope": "shared_process_object"
        if scope == "single_process_threads"
        else "per_process"
        if scope == "independent_processes"
        else None,
        "transaction_guarantees": "sqlite_atomic_write_transactions"
        if database == "sqlite"
        else None,
        "observed_failure_mode": "inventory_ledger_inconsistency",
    }
