"""Describe reached crash windows separately from business test outcomes."""


def recovery_coverage(records, *, required_points=()):
    observations = {}
    for point in required_points:
        rows = [row for row in records if isinstance(row, dict) and row.get("label") == point]
        reached = [row for row in rows if row.get("availability") == "AVAILABLE"
                   and isinstance(row.get("kill"), dict)
                   and row["kill"].get("signal") == "SIGKILL"
                   and row["kill"].get("worker_pidfd_exited") is True]
        observations[point] = {
            "availability": "AVAILABLE" if reached else "UNVERIFIED",
            "recorded_attempts": len(rows), "verified_interruptions": len(reached),
            "host_pids": [row["kill"]["identity"]["host_pid"] for row in reached],
        }
    return {
        "status": ("NOT_APPLICABLE" if not required_points else
                   "COMPLETE" if all(row["availability"] == "AVAILABLE" for row in observations.values())
                   else "PARTIAL"),
        "points": observations,
        "engineering_outcome_independent": True,
        "limits": "A missing observer is UNVERIFIED, not proof of recovery or a business failure. "
                  "In-process observations are scheduling evidence; the host database Oracle determines business truth.",
    }


def missing_required_recovery(coverage):
    """Missing common commit/ack windows are evaluator incompleteness, not a bad repair."""
    if coverage.get("status") == "NOT_APPLICABLE":
        return []
    return [point for point in ("transaction_committed", "before_response")
            if coverage.get("points", {}).get(point, {}).get("availability") != "AVAILABLE"]
