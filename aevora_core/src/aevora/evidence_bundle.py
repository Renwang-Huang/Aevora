"""WHY is a public projection of actual relationship paths, not a stored answer."""
from __future__ import annotations

from .models import QUERY_VERSION, SCHEMA_VERSION, LIFECYCLE_SCHEMA_VERSION, digest, validate_id


def build_evidence_bundle(repo, experience_id: str) -> dict:
    validate_id(experience_id)
    experience = repo.get_node("Experience", experience_id, public=True)
    if experience is None:
        return {"status": "NOT_FOUND", "experience_id": experience_id,
                "query_version": QUERY_VERSION, "paths": [], "premise_paths": []}
    premises = repo.premise_paths(experience_id)
    paths = repo.snapshot_public_paths(experience_id)
    snapshot = {"experience": experience, "premise_paths": premises, "paths": paths}
    governance = repo.governance_view(experience_id)
    lifecycle = {}
    if experience.get('publication_candidate_id'):
        from .candidate import CandidateLifecycle
        view = CandidateLifecycle(repo).inspect(experience['publication_candidate_id'])
        lifecycle = {'publication_lifecycle': {'candidate_id': view['candidate']['id'],
            'state': view['head']['state'], 'body_sha256': view['candidate']['body_sha256'],
            'head_sha256': view['head_sha256'], 'events': [{k: e[k] for k in
                ('id','from_state','to_state','created_at','reason','authority') if k in e} for e in view['events']],
            **{k:view['candidate']['body'][k] for k in ('necessary_conditions','inapplicable_conditions','scope','unknown_fields')},
            'causal_benefit': 'UNKNOWN'}}
    return {"status": "AVAILABLE", "experience_id": experience_id, **snapshot, **lifecycle,
            "query_version": QUERY_VERSION, "schema_version": LIFECYCLE_SCHEMA_VERSION if lifecycle else SCHEMA_VERSION,
            "revision_ids": sorted({p["records"]["ExperienceRevision"]["id"] for p in paths}
                                   | {p["revision"]["id"] for p in premises}),
            "support_paths": [p for p in paths if p["relation"] == "SUPPORTED_BY"],
            "counterexample_paths": [p for p in paths if p["relation"] == "COUNTEREXAMPLE"],
            "observed_outcome_paths": [p for p in paths if p["relation"] == "OBSERVED_OUTCOME"],
            "retrieval_snapshot_sha256": digest(snapshot),
            "governance": governance,
            "governance_evidence_sha256": digest({"legacy_evidence": snapshot, "governance": governance, **lifecycle}),
            "snapshot_assurance": "Actual bounded Cypher path retrieval; no distributed transaction assertion",
            "attribution": "UNKNOWN",
            "disclosure": "PUBLIC_ALLOWLIST_PROJECTION; no private report, suite identities or patch"}
