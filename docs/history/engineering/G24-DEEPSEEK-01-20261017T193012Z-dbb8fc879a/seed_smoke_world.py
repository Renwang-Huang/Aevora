"""Host-controlled trusted experience seed for the non-scored Adapter Smoke."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid
from datetime import datetime, timedelta, timezone

from audit import E, P, now, sha, write
from aevora.contracts import PROFILE, TenantBinding, TrustRegistry, digest, fact, schema
from aevora.graph_repository import GraphRepository
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora_maintainer.host_v2 import TrustedHost
from benchmark.episodes.episode_a import create_episode_a
from benchmark.runner import BenchmarkRunner
from integrations.aevora import public_runtime_context


CASES = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/"
    "G23-20261016T021142Z-1e5e8e1af0/02_source/cases/CASES.json"
)


def main() -> int:
    root = E / "02_calibration/smoke_world_v2"
    if root.exists():
        raise SystemExit("SMOKE_WORLD_ALREADY_EXISTS")
    root.mkdir(mode=0o700, parents=True)
    cases = json.loads(CASES.read_text())

    workspace = create_episode_a(root / "seed-rlock-workspace")
    service = workspace / "app/service.py"
    service.write_text(
        service.read_text()
        + '''
import threading
_create_lock = threading.RLock()
_unlocked_create = OrderFlow.create_order
def _serialized_create(self, *args, **kwargs):
    with _create_lock:
        return _unlocked_create(self, *args, **kwargs)
OrderFlow.create_order = _serialized_create
'''
    )
    report = BenchmarkRunner(root / "seed-runs").evaluate("A", workspace)
    if report["overall_status"] != "PASS":
        raise SystemExit("HOST_SEED_RUN_FAILED")
    run = root / "seed-runs" / report["run_id"]
    files = {
        str(path.relative_to(run)): sha(path)
        for path in run.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    write(run / "HOST_RUN_MANIFEST.json", {"files": files})
    anchor = TrustAnchor(
        run,
        sha(run / "HOST_RUN_MANIFEST.json"),
        {"evaluation_report.json": run.name},
        profile="current_live",
        manifest_relative_path="HOST_RUN_MANIFEST.json",
        source_snapshot_relative_path="frozen_source_snapshot",
        source_archive_root=Path(cases["source_root"]),
        source_manifest_sha256=cases["source_manifest_sha256"],
        source_manifest_relative_path="SOURCE_MANIFEST.json",
    )

    repository = GraphRepository.from_environment()
    repo = repository.v2(
        TenantBinding("tenant-g24-deepseek-smoke", repository.graph_name),
        TrustRegistry(),
    )
    try:
        repo.initialize()
        pins = root / "private_host_pins"
        grant = TrustedHost.bootstrap(
            repo,
            pins,
            principal="g24-deepseek-smoke-seed",
            allowed_scope={"task.shared_state_kind": ["sqlite_file"]},
        )
        host = TrustedHost(repo, pins, grant)
        verifier = host.register_orderflow(
            anchor,
            report["fingerprints"]["evaluator"]["sha256"],
            report["fingerprints"]["test_suite"]["sha256"],
        )
        proposal = {
            "candidate_key": "bounded-process-local-critical-section",
            "title": "Shared process-local critical section",
            "strategy": (
                "Serialize the complete stale-read and reservation path with the same "
                "process-local RLock when every participant shares that process and lock object."
            ),
            "public_summary": (
                "Host-controlled complete critical section passed a fresh independent "
                "threaded Oracle. It does not coordinate independent worker processes."
            ),
            "necessary_conditions": {
                "task.concurrency_scope": ["single_process_threads"],
                "task.synchronization_scope": ["shared_process_object"],
            },
            "inapplicable_conditions": {
                "task.concurrency_scope": ["independent_processes"],
            },
            "scope": {
                "task.shared_state_kind": ["sqlite_file"],
                "task.concurrency_scope": ["single_process_threads"],
            },
            "unknown_fields": [],
            "limitations": [
                "HOST_CONTROLLED_STRATEGY_SEED, not a new Agent result",
                "Not a cross-process coordination mechanism",
            ],
            "source_references": [],
        }
        candidate = host.propose(
            proposal,
            run_id=run.name,
            tree_sha=report["submission"]["evaluated_sha256"],
            patch_sha=None,
        )
        source = host.verify_source(
            candidate["id"],
            verifier.authority_id,
            "evaluation_report.json",
        )
        outcome = host.verify_outcome(candidate["id"], source["id"])
        review = host.review(
            candidate["id"],
            source["id"],
            outcome["id"],
            approved_scope=proposal["scope"],
            reason=(
                "Actual source critical section inspected; scope restricted to "
                "a shared process object; independent threaded Oracle passed"
            ),
        )
        if review["verification"] != "REVIEW_APPROVED":
            raise RuntimeError(review)
        head = host.transition(
            candidate["id"],
            "PUBLISHING",
            expected_head=digest(host.head(candidate["id"])),
            reason="Explicit controlled G24 smoke seed",
        )
        prepared = host.prepare(
            candidate["id"],
            review["id"],
            request_key="g24-deepseek-smoke-seed",
            expected_head=digest(head),
            expected_epoch=repo.state()["epoch"],
        )
        receipt = host.publish(prepared)

        manifest = json.loads((P / "benchmark/scenarios/SMOKE-001/public.json").read_text())
        public = root / "public_inputs/SMOKE-001/public.json"
        public.parent.mkdir(parents=True)
        public.write_bytes((P / "benchmark/scenarios/SMOKE-001/public.json").read_bytes())
        facts = {}
        authority = grant.capability_id
        first_line = public.read_bytes().splitlines(keepends=True)[0]
        for key, value in public_runtime_context(manifest).items():
            if "task." + key not in schema("fact")["properties"]["key"]["enum"]:
                continue
            known = value is not None
            value_fact = {
                "key": "task." + key,
                "phase": "task",
                "availability": "KNOWN" if known else "UNKNOWN",
                "value": value,
                "authority_class": "HOST_DECLARED_TASK" if known else None,
                "authority_ref": authority if known else None,
                "source_refs": [
                    {
                        "file": "public_inputs/SMOKE-001/public.json",
                        "file_sha256": sha(public),
                        "line": 1,
                        "line_sha256": hashlib.sha256(first_line).hexdigest(),
                        "byte_scope": "ARCHIVED_BYTES_INCLUDING_NEWLINE",
                    }
                ] if known else [],
                "observed_at": now() if known else None,
            }
            fact(value_fact)
            facts[value_fact["key"]] = value_fact
            if known:
                host.pins.put("fact_sources", digest(value_fact), authority)
        until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        bootstrap = {
            "binding": repo.binding.__dict__,
            "registry": {"pin_root": str(pins)},
            "facts": facts,
            "grant": {
                "tenant": repo.tenant,
                "session_id": "capability-session-" + uuid.uuid4().hex,
                "generation": uuid.uuid4().hex,
                "valid_until": until,
                "authz_epoch": repo.state()["authz_epoch"],
                "profile": PROFILE,
            },
        }
        bootstrap_path = root / "SMOKE_BOOTSTRAP.json"
        write(bootstrap_path, bootstrap)
        bootstrap_path.chmod(0o600)
        write(
            root / "SMOKE_WORLD_REGISTERED.json",
            {
                "seed_run": run.name,
                "seed_experience": receipt.get("experience_id"),
                "seed_origin": "HOST_CONTROLLED",
                "task": "SMOKE-001",
                "bootstrap_sha256": sha(bootstrap_path),
                "initial_experience_count": len(repository.experience_ids()),
                "causal_attribution": "NOT_APPLICABLE_SMOKE",
            },
        )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "seed_run": run.name,
                    "experience_id": receipt.get("experience_id"),
                    "bootstrap": str(bootstrap_path),
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
