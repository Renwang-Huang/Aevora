"""HOST_CONTROLLED_SYNTHETIC_FIXTURE. Never a real Agent or independent engineering grade.

G21 read-side acceptance only. This is NOT a G22 production publication API.
"""

from collections import defaultdict
from aevora.contracts import *
from aevora.models import utc_now
from aevora.graph_queries import SEMANTIC_RELATIONS

SOURCE = "HOST_CONTROLLED_SYNTHETIC_FIXTURE"


def facts(registry, **values):
    out = {}
    for key, value in values.items():
        key = key.replace("__", ".")
        f = dict(
            key=key,
            phase=key.split(".")[0],
            availability="KNOWN" if value is not None else "UNKNOWN",
            value=value,
            authority_class="HOST_DECLARED_TASK" if value is not None else None,
            authority_ref="fixture-host" if value is not None else None,
            source_refs=[
                dict(
                    file="synthetic/facts.jsonl",
                    file_sha256=digest([key, value]),
                    line=1,
                    line_sha256=digest([key, value]),
                    byte_scope="ARCHIVED_BYTES_INCLUDING_NEWLINE",
                )
            ]
            if value is not None
            else [],
            observed_at="2026-10-15T00:00:00Z" if value is not None else None,
        )
        fact(f)
        if value is not None:
            registry.fact_sources[digest(f)] = "fixture-host"
        out[key] = f
    return out


def bulk(repo, nodes, edges):
    # Synthetic trusted writer: immutable MERGE, no silent overwrite or publication API.
    groups = defaultdict(list)
    for n in nodes:
        validate_record(n, repo.tenant)
        groups[n["kind"]].append(native(n))
    common = ",".join(
        k + ":row." + k for k in sorted(COMMON | {"payload_json", "payload_sha256"})
    )
    for kind, rows in groups.items():
        for i in range(0, len(rows), 64):
            repo.transport.query(
                f"UNWIND $rows AS row MERGE(n:V2Record:{kind} {{{common}}}) ON CREATE SET n += row RETURN n.id",
                dict(rows=rows[i : i + 64]),
                read_only=False,
            )
    groups = defaultdict(list)
    for e in edges:
        validate_record(e, repo.tenant)
        groups[e["kind"]].append(native(e))
    for kind, rows in groups.items():
        for i in range(0, len(rows), 64):
            repo.transport.query(
                f"UNWIND $rows AS row MATCH(a:V2Record {{id:row.source_id}}),(b:V2Record {{id:row.target_id}}) MERGE(a)-[r:{kind} {{{common}}}]->(b) ON CREATE SET r += row RETURN r.id",
                dict(rows=rows[i : i + 64]),
                read_only=False,
            )


def update_state(repo, **changes):
    state = repo.state()
    state.update(changes)
    repo.transport.query(
        "MATCH(s:TenantState {id:$id}) SET s=$properties RETURN s.id",
        dict(id=repo.state_id, properties=native(state)),
        read_only=False,
    )
    return state


def seed(
    repo,
    key="principle",
    *,
    scope_value="sqlite_file",
    required=None,
    outcomes=("PASS",),
    withdraw=False,
    authority_class="ENGINEERING_VERIFIER",
    evidence_facts=None,
    staging=False,
):
    tenant = repo.tenant
    nodes = []
    edges = []

    def n(kind, k, **body):
        v = record(
            tenant,
            kind,
            [key, k],
            source=SOURCE,
            created="2026-10-15T00:00:00Z",
            **body,
        )
        nodes.append(v)
        return v

    def link(kind, a, b, **body):
        v = (
            edge(tenant, kind, a, b, source_type=SOURCE, **body)
            if False
            else edge(tenant, kind, a, b, **body)
        )
        edges.append(v)
        return v

    scope_ = {"task.shared_state_kind": [scope_value]}
    token = digest(["task.shared_state_kind", scope_value])
    e = n(
        "Experience",
        "experience",
        scope_token=token,
        title="Synthetic conditional engineering principle",
        strategy="test principle",
    )
    required = (
        required
        if required is not None
        else {"task.shared_state_kind": ["sqlite_file"]}
    )
    pre = [
        n(
            "Premise",
            ["pre", k],
            fact_key=k,
            phase=k.split(".")[0],
            mode="necessary",
            allowed_values=vs,
        )
        for k, vs in required.items()
    ]
    rule = n(
        "Rule",
        "rule",
        scope_token=token,
        scope=scope_,
        premise_ids=[v["id"] for v in pre],
        strategy_sha256=digest(["principle", key]),
    )
    r = n(
        "ExperienceRevision",
        "revision",
        experience_id=e["id"],
        revision_kind="rule_publication",
        declared_rule_id=rule["id"],
        supersedes_ids=[],
        scope=scope_,
        valid_from="2026-10-15T00:00:00Z",
    )
    link("HAS_REVISION", e, r)
    link("USES_RULE", r, rule)
    for v in pre:
        link("REQUIRES", rule, v)
    observed = evidence_facts or facts(
        repo.registry,
        task__shared_state_kind=scope_value,
        **{
            k.replace(".", "__"): vs[0]
            for k, vs in required.items()
            if k != "task.shared_state_kind"
        },
    )
    for i, verdict in enumerate(outcomes):
        a = n(
            "Authority",
            ["authority", i],
            authority_class=authority_class,
            independence="INDEPENDENT",
            state="ACTIVE",
            verifier_version="synthetic-1",
            source_sha256=digest(["synthetic-verifier", i]),
        )
        t = n("Task", ["task", i], facts=observed)
        c = n("Context", ["context", i], facts=observed, task_id=t["id"])
        o = n(
            "VerifiedOutcome",
            ["outcome", i],
            authority=a["id"],
            task_id=t["id"],
            verdict=verdict,
            result_sha256=digest(["synthetic-result", key, i]),
            artifact_sha256=digest(["synthetic-artifact", key, i]),
            failure_class="BUSINESS"
            if verdict == "FAIL"
            else "INFRASTRUCTURE"
            if verdict in {"ERROR", "TIMEOUT", "NOT_RUN"}
            else None,
        )
        ev = n(
            "Evidence",
            ["evidence", i],
            revision_id=r["id"],
            outcome_id=o["id"],
            artifact_sha256=o["artifact_sha256"],
            strategy_sha256=rule["strategy_sha256"],
        )
        repo.registry.authorities[a["id"]] = digest(a)
        repo.registry.outcomes[o["id"]] = digest(o)
        for kind, x, y in [
            (
                "SUPPORTED_BY"
                if verdict == "PASS"
                else "COUNTEREXAMPLE"
                if verdict == "FAIL"
                else "OBSERVED_OUTCOME",
                r,
                ev,
            ),
            ("VERIFIES", ev, o),
            ("IN_CONTEXT", o, c),
            ("FOR_TASK", c, t),
            ("ATTESTED_BY", o, a),
        ]:
            link(kind, x, y)
    if withdraw:
        g = n(
            "GovernanceEvent",
            "withdraw",
            event_type="withdraw",
            effective_at="2026-10-15T00:00:00Z",
            scope=scope_,
            target_id=r["id"],
            target_label="ExperienceRevision",
        )
        link("GOVERNS", g, r)
    state = repo.state()
    epoch = state["epoch"] + 1
    manifest_id = identity(tenant, "PublicationManifest", [key, "manifest"])
    # Root is outside its own listing; activation links are verified separately.
    listing = {
        "nodes": {v["id"]: digest(v) for v in nodes},
        "edges": {v["id"]: digest(v) for v in edges},
    }
    bulk(repo, nodes, edges)
    manifest = repo.put_document(
        "PublicationManifest",
        [key, "manifest"],
        listing,
        experience_id=e["id"],
        epoch=epoch,
        source_namespace=SOURCE,
    )
    repo.registry.publications[manifest["id"]] = digest(manifest)
    for v in nodes:
        if v["kind"] in {"ExperienceRevision", "GovernanceEvent"}:
            repo.put_edge(edge(tenant, "PUBLISHED_BY", v, manifest))
    if not staging:
        repo.put_edge(
            edge(tenant, "COMMITS", state, manifest, manifest_sha256=digest(manifest))
        )
        update_state(
            repo,
            epoch=epoch,
            discovery_heads=prepare_catalogue(repo, state, e, manifest, epoch),
        )
    return dict(
        experience=e, revision=r, rule=rule, nodes=nodes, edges=edges, manifest=manifest
    )


def seal_closure(repo, key, experience, nodes, edges):
    """Synthetic cumulative manifest refresh; NOT a production publisher/CAS."""
    bulk(repo, nodes, edges)
    state = repo.state()
    manifest = repo.put_document(
        "PublicationManifest",
        key,
        {
            "nodes": {n["id"]: digest(n) for n in nodes},
            "edges": {e["id"]: digest(e) for e in edges},
        },
        experience_id=experience["id"],
        epoch=state["epoch"] + 1,
        source_namespace=SOURCE,
    )
    repo.registry.publications[manifest["id"]] = digest(manifest)
    for n in nodes:
        if n["kind"] in {"ExperienceRevision", "GovernanceEvent"}:
            repo.put_edge(edge(repo.tenant, "PUBLISHED_BY", n, manifest))
    repo.put_edge(
        edge(repo.tenant, "COMMITS", state, manifest, manifest_sha256=digest(manifest))
    )
    update_state(
        repo,
        epoch=state["epoch"] + 1,
        discovery_heads=prepare_catalogue(
            repo, state, experience, manifest, state["epoch"] + 1
        ),
    )
    return manifest


def prepare_catalogue(repo, state, experience, manifest, epoch):
    """Synthetic publisher only: authenticated graph-native recall set, not a static ID allowlist."""
    token = experience["scope_token"]
    heads = dict(state["discovery_heads"])
    listing = {}
    if token in heads:
        old = repo.node(heads[token]["id"])
        assert digest(old) == heads[token]["sha256"]
        listing = repo.load_document(old)
    listing[experience["id"]] = {
        "manifest_id": manifest["id"],
        "manifest_sha256": digest(manifest),
    }
    root = repo.put_document(
        "QuerySnapshot",
        ["discovery", token, epoch],
        listing,
        document_kind="DISCOVERY_CATALOGUE",
        scope_token=token,
        epoch=epoch,
    )
    heads[token] = {"id": root["id"], "sha256": digest(root)}
    return heads
