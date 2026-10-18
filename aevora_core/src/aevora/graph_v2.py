"""Explicit v2 extension of the existing official FalkorDB transport.

Only trusted host constructs this repository. Synthetic test publishers live in
maintainer validation code, not in the four-tool service.
"""

from __future__ import annotations
import hashlib
import time
import os
import json
from .contracts import *
from .graph_queries import QUERIES, SEMANTIC_RELATIONS
from .graph_repository import GraphRepository
from .models import GraphUnavailable


class GraphV2Repository:
    def __init__(
        self,
        transport: GraphRepository,
        binding: TenantBinding,
        registry: TrustRegistry,
    ):
        require(transport.graph_name == binding.graph_name, "UNAUTHORIZED")
        self.transport, self.binding, self.registry = transport, binding, registry
        self.tenant = binding.tenant_id
        self.state_id = identity(self.tenant, "TenantState", "state")
        self.query_receipts = []
        self.read_bytes = 0
        self._recall = {}
        self._recall_state_sha = None

    def execute(self, name, **params):
        require(name in QUERIES, "UNAUTHORIZED")
        started = time.monotonic()
        try:
            rows = self.transport.query(QUERIES[name], params)
        except GraphUnavailable:
            raise V2Error("GRAPH_UNAVAILABLE") from None
        size = len(canonical_json(rows).encode())
        require(size <= 20 * 1024 * 1024, "CAPACITY_EXCEEDED")
        self.read_bytes += size
        self.query_receipts.append(
            dict(
                query=name,
                elapsed=time.monotonic() - started,
                rows=len(rows),
                bytes=size,
                result_sha256=digest(rows),
            )
        )
        self.query_receipts = self.query_receipts[-2048:]
        audit_path = os.environ.get("AEVORA_V2_QUERY_AUDIT")
        if audit_path:
            fd = os.open(
                audit_path,
                os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                0o600,
            )
            try:
                require(os.fstat(fd).st_size < 256 * 1024 * 1024, "CAPACITY_EXCEEDED")
                data = (
                    canonical_json(
                        dict(
                            query=name,
                            statement=QUERIES[name],
                            params=params,
                            rows=rows,
                            elapsed=time.monotonic() - started,
                        )
                    )
                    + "\n"
                ).encode()
                require(os.write(fd, data) == len(data))
            finally:
                os.close(fd)
        return rows

    def initialize(self):
        # Refuse even an otherwise valid legacy graph; never alter its schema.
        known = self.transport._client.connection.execute_command("GRAPH.LIST")
        existing = (
            self.transport.query("MATCH(n) RETURN labels(n),properties(n) LIMIT 2")
            if self.binding.graph_name.encode() in known
            or self.binding.graph_name in known
            else []
        )
        if existing:
            for labels, properties in existing:
                require("V2Record" in labels)
                decode(properties, self.tenant)
            self.state()
            return self.schema_dump()
        state = record(
            self.tenant,
            "TenantState",
            "state",
            epoch=0,
            authz_epoch=0,
            generation="1",
            discovery_heads={},
            policy_version=POLICY,
        )
        self.put_node(state)
        graph = self.transport._graph
        for label in sorted(LABELS | {"V2Record"}):
            graph.create_node_unique_constraint(label, "id")
            graph.create_node_mandatory_constraint(
                label, *sorted(COMMON | {"payload_json", "payload_sha256"})
            )
        self.transport.query(
            "CREATE INDEX FOR(n:Experience) ON(n.scope_token)", read_only=False
        )
        deadline = time.monotonic() + 15
        while True:
            cs = graph.list_constraints()
            require(not any(c["status"] == "FAILED" for c in cs))
            if len(cs) == 2 * (len(LABELS) + 1) and all(
                c["status"] == "OPERATIONAL" for c in cs
            ):
                break
            require(time.monotonic() < deadline, "GRAPH_UNAVAILABLE")
            time.sleep(0.02)
        return self.schema_dump()

    def schema_dump(self):
        return dict(
            version=GRAPH_VERSION,
            graph=self.binding.graph_name,
            tenant=self.tenant,
            constraints=self.transport._graph.list_constraints(),
            indexes=self.transport.query("CALL db.indexes()"),
        )

    def put_node(self, value):
        validate_record(value, self.tenant)
        kind = value["kind"]
        require(kind in LABELS)
        props = native(value)
        common = ",".join(
            k + ":$row." + k
            for k in sorted(COMMON | {"payload_json", "payload_sha256"})
        )
        self.transport.query(
            f"MERGE(n:V2Record:{kind} {{{common}}}) ON CREATE SET n += $row RETURN n.id",
            {"row": props},
            read_only=False,
        )
        return value

    def put_edge(self, value):
        validate_record(value, self.tenant)
        kind = value["kind"]
        require(kind in RELATIONS)
        a = self.node(value["source_id"])
        b = self.node(value["target_id"])
        require(a["kind"] == value["source_kind"] and b["kind"] == value["target_kind"])
        props = native(value)
        common = ",".join(
            k + ":$row." + k
            for k in sorted(COMMON | {"payload_json", "payload_sha256"})
        )
        rows = self.transport.query(
            f"MATCH(a:V2Record {{id:$a}}),(b:V2Record {{id:$b}}) MERGE(a)-[r:{kind} {{{common}}}]->(b) ON CREATE SET r += $row RETURN r.id",
            dict(a=a["id"], b=b["id"], row=props),
            read_only=False,
        )
        require(len(rows) == 1)
        return value

    def node(self, identifier):
        rows = self.execute("Q13", id=identifier)
        require(len(rows) == 1)
        labels, props = rows[0]
        value = decode(props, self.tenant)
        require(set(labels) == {"V2Record", value["kind"]})
        return value

    def state(self):
        rows = self.execute("Q00", state=self.state_id)
        require(len(rows) == 1)
        value = decode(rows[0][0], self.tenant)
        require(value["kind"] == "TenantState" and value["policy_version"] == POLICY)
        return value

    def chunks(self, kind, key, document):
        raw = canonical_json(document).encode()
        require(len(raw) <= MAX_DOCUMENT, "CAPACITY_EXCEEDED")
        texts = []
        part = []
        size = 0
        for char in raw.decode():
            n = len(char.encode())
            if size + n > MAX_CHUNK:
                texts.append("".join(part))
                part = []
                size = 0
            part.append(char)
            size += n
        texts.append("".join(part))
        require(len(texts) <= MAX_CHUNKS, "CAPACITY_EXCEEDED")
        root_id = identity(self.tenant, kind, key)
        chunks = [
            record(
                self.tenant,
                "SnapshotChunk",
                [root_id, i],
                document_id=root_id,
                chunk_index=i,
                text=t,
                chunk_sha256=hashlib.sha256(t.encode()).hexdigest(),
            )
            for i, t in enumerate(texts)
        ]
        manifest = dict(
            document_sha256=hashlib.sha256(raw).hexdigest(),
            document_utf8_bytes=len(raw),
            chunks=[
                {"id": c["id"], "index": c["chunk_index"], "sha256": c["chunk_sha256"]}
                for c in chunks
            ],
        )
        return manifest, chunks

    def put_document(self, kind, key, document, **metadata):
        manifest, chunks = self.chunks(kind, key, document)
        root = record(self.tenant, kind, key, document=manifest, **metadata)
        self.put_node(root)
        for c in chunks:
            self.put_node(c)
            self.put_edge(edge(self.tenant, "HAS_CHUNK", root, c))
        return root

    def load_document(self, root):
        manifest = root["document"]
        expected = manifest["chunks"]
        require(1 <= len(expected) <= MAX_CHUNKS, "CAPACITY_EXCEEDED")
        rows = self.execute("Q09", document=root["id"])
        require(len(rows) <= MAX_CHUNKS, "CAPACITY_EXCEEDED")
        require(len(rows) == len(expected))
        texts = []
        for index, (h, c) in enumerate(rows):
            link, value = decode(h, self.tenant), decode(c, self.tenant)
            require(
                link
                == edge(
                    self.tenant, "HAS_CHUNK", root, value, created=link["created_at"]
                )
            )
            require(
                value["document_id"] == root["id"] and value["chunk_index"] == index
            )
            require(
                expected[index]
                == dict(id=value["id"], index=index, sha256=value["chunk_sha256"])
            )
            texts.append(value["text"])
        raw = "".join(texts).encode()
        require(len(raw) <= MAX_DOCUMENT, "CAPACITY_EXCEEDED")
        require(
            len(raw) == manifest["document_utf8_bytes"]
            and hashlib.sha256(raw).hexdigest() == manifest["document_sha256"]
        )
        value = decode_json(raw)
        require(canonical_json(value).encode() == raw)
        return value

    def discover(self, facts, state):
        f = facts.get("task.shared_state_kind")
        heads = state.get("discovery_heads")
        require(isinstance(heads, dict) and len(heads) <= 1024, "GRAPH_INTEGRITY_ERROR")
        tokens = (
            ["*", digest(["task.shared_state_kind", f["value"]])]
            if f and f["availability"] == "KNOWN"
            else sorted(heads)
        )
        return self.discover_partitions(tokens, state)

    def discover_partitions(self, tokens, state):
        """Trusted Host selector; no public tool accepts tokens or candidate IDs.

        Shares exact catalogue authentication, native recall equality and bounds
        with the public fact-derived selector. Useful for bounded governance in
        a tenant with many unrelated partitions.
        """
        heads=state.get('discovery_heads')
        require(isinstance(heads,dict) and len(heads)<=1024)
        require(isinstance(tokens,list) and len(tokens)<=1024
                and len(tokens)==len(set(tokens)) and all(isinstance(t,str) for t in tokens))
        expected = {}
        for token in tokens: 
            if token not in heads:
                continue
            pin = heads[token]
            root = self.node(pin["id"])
            require(
                digest(root) == pin["sha256"]
                and root["kind"] == "QuerySnapshot"
                and root.get("document_kind") == "DISCOVERY_CATALOGUE"
                and root.get("scope_token") == token
                and root["epoch"] <= state["epoch"]
            )
            listing = self.load_document(root)
            require(isinstance(listing, dict))
            for eid, entry in listing.items():
                require(
                    eid not in expected
                    and set(entry) == {"manifest_id", "manifest_sha256"}
                )
                expected[eid] = {
                    **entry,
                    "catalogue_id": root["id"],
                    "catalogue_sha256": digest(root),
                    "catalogue_document_sha256": root["document"]["document_sha256"],
                    "scope_token": token,
                }
        require(len(expected) <= 256, "CAPACITY_EXCEEDED")
        result = []
        after = ""
        while True:
            rows = self.execute(
                "Q01",
                tokens=tokens,
                state=self.state_id,
                epoch=state["epoch"],
                after=after,
            )
            ids = [r[0] for r in rows]
            require(ids == sorted(set(ids)) and all(i > after for i in ids))
            result.extend(ids[:64])
            require(len(result) <= 256, "CAPACITY_EXCEEDED")
            if len(ids) <= 64:
                break
            after = ids[63]
        require(result == sorted(expected))
        self._recall = expected
        self._recall_state_sha = digest(state)
        return result

    def read_witness(self, experience_id, state):
        rows = self.execute(
            "Q12", state=self.state_id, experience=experience_id, epoch=state["epoch"]
        )
        require(
            rows and len(rows) <= 256,
            "CAPACITY_EXCEEDED" if len(rows) > 256 else "GRAPH_INTEGRITY_ERROR",
        )
        commits = []
        for cp, mp in rows:
            c, m = decode(cp, self.tenant), decode(mp, self.tenant)
            require(
                c
                == edge(
                    self.tenant,
                    "COMMITS",
                    state,
                    m,
                    manifest_sha256=digest(m),
                    created=c["created_at"],
                )
            )
            require(
                m["kind"] == "PublicationManifest"
                and m["experience_id"] == experience_id
                and m["epoch"] <= state["epoch"]
            )
            require(self.registry.publications.get(m["id"]) == digest(m))
            commits.append((c, m))
        require(len({m["epoch"] for _, m in commits}) == len(commits))
        manifest = commits[0][1]
        require(
            self._recall_state_sha == digest(state) and experience_id in self._recall
        )
        discovery = self._recall[experience_id]
        require(
            discovery["manifest_id"] == manifest["id"]
            and discovery["manifest_sha256"] == digest(manifest)
        )
        require(self.registry.publications.get(manifest["id"]) == digest(manifest))
        declared = self.load_document(manifest)
        require(
            set(declared) == {"nodes", "edges"}
            and isinstance(declared["nodes"], dict)
            and isinstance(declared["edges"], dict)
        )
        require(
            len(declared["nodes"]) <= 8192 and len(declared["edges"]) <= 8192,
            "CAPACITY_EXCEEDED",
        )
        ids = sorted(declared["nodes"])
        require(experience_id in ids)
        actual = self.execute("Q10", ids=ids)
        require(len(actual) == len(ids))
        nodes = {}
        for labels, props in actual:
            value = decode(props, self.tenant)
            require(set(labels) == {"V2Record", value["kind"]})
            require(
                value["id"] in declared["nodes"]
                and declared["nodes"][value["id"]] == digest(value)
            )
            nodes[value["id"]] = value
        require(set(nodes) == set(ids))
        require(
            all(v["visibility"] == "PUBLIC" for v in nodes.values()), "UNAUTHORIZED"
        )
        actual = self.execute("Q11", ids=ids, relations=SEMANTIC_RELATIONS)
        require(len(actual) <= 8192, "CAPACITY_EXCEEDED")
        edges = {}
        for al, a, rel, props, bl, b in actual:
            # Ignore only external staged revision/governance endpoints proved uncommitted.
            external = a if a not in nodes else b if b not in nodes else None
            if external and (
                (
                    rel == "HAS_REVISION"
                    and a == experience_id
                    and "ExperienceRevision" in bl
                )
                or (rel == "GOVERNS" and "GovernanceEvent" in al)
            ):
                committed = self.execute(
                    "Q16", id=external, state=self.state_id, epoch=state["epoch"]
                )
                if not committed:
                    continue
            value = decode(props, self.tenant)
            require(
                value["kind"] == rel
                and value["source_id"] == a
                and value["target_id"] == b
            )
            require(value["source_kind"] in al and value["target_kind"] in bl)
            require(
                a in nodes
                and b in nodes
                and value["source_kind"] == nodes[a]["kind"]
                and value["target_kind"] == nodes[b]["kind"]
            )
            require(value["id"] not in edges)
            edges[value["id"]] = value
        require({k: digest(v) for k, v in edges.items()} == declared["edges"])
        revision_ids = sorted(
            n["id"] for n in nodes.values() if n["kind"] == "ExperienceRevision"
        )
        require(len(revision_ids) <= 16, "CAPACITY_EXCEEDED")
        # These independent native joins prove actual full traversal, not merely a JSON listing.
        premises = self.execute("Q02", experience=experience_id)
        require(len(premises) <= 1024, "CAPACITY_EXCEEDED")
        supersedes = self.execute("Q03", ids=revision_ids)
        require(len(supersedes) <= 256, "CAPACITY_EXCEEDED")
        paths = self.execute("Q04", ids=revision_ids)
        require(len(paths) <= 512, "CAPACITY_EXCEEDED")
        governance = self.execute("Q05", ids=ids)
        require(len(governance) <= 256, "CAPACITY_EXCEEDED")
        publications = self.execute("Q14", manifest=manifest["id"])
        for rid, props in publications:
            require(rid in nodes)
            require(
                decode(props, self.tenant)
                == edge(
                    self.tenant,
                    "PUBLISHED_BY",
                    nodes[rid],
                    manifest,
                    created=decode(props, self.tenant)["created_at"],
                )
            )
        required_pub = {
            n["id"]
            for n in nodes.values()
            if n["kind"] in {"ExperienceRevision", "GovernanceEvent"}
        }
        require({r[0] for r in publications} == required_pub)
        witness = dict(
            experience_id=experience_id,
            manifest=manifest,
            commit=commits[0][0],
            nodes=nodes,
            edges=edges,
            paths=paths,
            epoch=state["epoch"],
            authz_epoch=state["authz_epoch"],
            generation=state["generation"],
            completeness="COMPLETE",
            discovery_ref=discovery,
        )
        validate_witness(witness, self.registry, self.tenant)
        return witness

    def resolve_witnesses(self, facts):
        for v in facts.values():
            self.registry.verify_fact(v)
        start_bytes = self.read_bytes
        started = time.monotonic()
        for attempt in range(2):
            start = self.state()
            ids = self.discover(facts, start)
            witnesses = []
            try:
                for i in ids:
                    witnesses.append(self.read_witness(i, start))
                    require(
                        self.read_bytes - start_bytes <= 20 * 1024 * 1024
                        and time.monotonic() - started <= 30,
                        "CAPACITY_EXCEEDED",
                    )
            except V2Error:
                if self.state() != start:
                    continue
                raise
            if self.state() == start:
                return start, witnesses
        raise V2Error("GRAPH_CHANGED")

    def authorize(self, grant, state=None):
        grant.check()
        rows = self.execute(
            "Q08", state=self.state_id, session=grant.session_record_id(self.tenant)
        )
        require(len(rows) == 1, "UNAUTHORIZED")
        current, session = [decode(v, self.tenant) for v in rows[0]]
        require(
            type(grant.authz_epoch) is int
            and current["authz_epoch"] == grant.authz_epoch,
            "UNAUTHORIZED",
        )
        require(
            session["state"] == "ACTIVE"
            and session["run_id"] == grant.run_id
            and session["session_id"] == grant.session_id
            and session["profile"] == PROFILE
            and session["grant_generation"] == grant.generation,
            "UNAUTHORIZED",
        )
        require(
            timestamp(session["valid_until"]) > datetime.now(timezone.utc),
            "UNAUTHORIZED",
        )
        if state is not None:
            require(current == state, "STALE_SNAPSHOT")
        return current


def validate_witness(witness, registry, tenant):
    """Independent structural verifier, separate from arbitration and native query assembly."""
    nodes = witness["nodes"]
    edges = witness["edges"]
    eid = witness["experience_id"]

    def targets(node, kind, label=None):
        result = [
            nodes[e["target_id"]]
            for e in edges.values()
            if e["source_id"] == node and e["kind"] == kind
        ]
        if label:
            require(all(n["kind"] == label for n in result))
        return result

    def one(node, kind, label):
        values = targets(node, kind, label)
        require(len(values) == 1)
        return values[0]

    e = nodes[eid]
    require(e["kind"] == "Experience" and e["visibility"] == "PUBLIC")
    revisions = targets(eid, "HAS_REVISION", "ExperienceRevision")
    require(revisions)
    reachable = {eid}
    expected_paths = []
    for r in revisions:
        require(r["experience_id"] == eid)
        scope(r["scope"])
        timestamp(r["valid_from"])
        if r.get("valid_until"):
            timestamp(r["valid_until"])
        rule = one(r["id"], "USES_RULE", "Rule")
        scope(rule["scope"])
        require(r.get("declared_rule_id") == rule["id"])
        require(
            sorted(
                n["id"] for n in targets(r["id"], "SUPERSEDES", "ExperienceRevision")
            )
            == sorted(r["supersedes_ids"])
        )
        token = (
            digest(
                ["task.shared_state_kind", rule["scope"]["task.shared_state_kind"][0]]
            )
            if "task.shared_state_kind" in rule["scope"]
            and len(rule["scope"]["task.shared_state_kind"]) == 1
            else "*"
        )
        require(e["scope_token"] == token and rule["scope_token"] == token)
        premises = targets(rule["id"], "REQUIRES", "Premise")
        require(len(premises) <= 64, "CAPACITY_EXCEEDED")
        require(sorted(p["id"] for p in premises) == sorted(rule["premise_ids"]))
        # Necessary membership and exclusion are different predicates on one
        # fact. Their conjunction is already evaluated independently by WHEN.
        # Duplicate predicates of the same mode remain an integrity error.
        require(len({(p["mode"], p["fact_key"]) for p in premises}) == len(premises))
        reachable.update([r["id"], rule["id"], *(p["id"] for p in premises)])
        for relation in ["SUPPORTED_BY", "COUNTEREXAMPLE", "OBSERVED_OUTCOME"]:
            for ev in targets(r["id"], relation, "Evidence"):
                o = one(ev["id"], "VERIFIES", "VerifiedOutcome")
                c = one(o["id"], "IN_CONTEXT", "Context")
                t = one(c["id"], "FOR_TASK", "Task")
                a = one(o["id"], "ATTESTED_BY", "Authority")
                registry.verify_outcome(o, a)
                require(
                    o["task_id"] == t["id"]
                    and c["task_id"] == t["id"]
                    and c["facts"] == t["facts"]
                )
                require(
                    ev["revision_id"] == r["id"]
                    and ev["outcome_id"] == o["id"]
                    and ev["artifact_sha256"] == o["artifact_sha256"]
                )
                require(ev["strategy_sha256"] == rule["strategy_sha256"])
                for f in c["facts"].values():
                    registry.verify_fact(f)
                require(relation != "SUPPORTED_BY" or o["verdict"] == "PASS")
                require(
                    relation != "COUNTEREXAMPLE"
                    or o["verdict"] == "FAIL"
                    and o["failure_class"] == "BUSINESS"
                )
                reachable.update([ev["id"], o["id"], c["id"], t["id"], a["id"]])
                expected_paths.append(
                    (r["id"], ev["id"], o["id"], c["id"], t["id"], a["id"])
                )
    actual_paths = []
    for path in witness["paths"]:
        require(len(path) == 11)
        decoded = [decode(x, tenant) for x in path]
        for value in decoded:
            if value["kind"] in RELATIONS:
                require(edges.get(value["id"]) == value)
            else:
                require(nodes.get(value["id"]) == value)
        actual_paths.append(tuple(decoded[i]["id"] for i in (0, 2, 4, 6, 8, 10)))
    require(sorted(actual_paths) == sorted(expected_paths))
    for n in nodes.values():
        if n["kind"] == "GovernanceEvent":
            require(n["event_type"] in {"withdraw", "expire", "restrict_scope"})
            timestamp(n["effective_at"])
            scope(n["scope"])
            ts = targets(n["id"], "GOVERNS")
            require(len(ts) == 1 and ts[0]["id"] == n["target_id"])
            require(ts[0]["kind"] in {"ExperienceRevision", "Evidence"})
            reachable.add(n["id"])
    require(reachable == set(nodes))
    adjacency = {
        r["id"]: [n["id"] for n in targets(r["id"], "SUPERSEDES", "ExperienceRevision")]
        for r in revisions
    }

    def visit(key, seen):
        require(key not in seen and len(seen) <= 8)
        for child in adjacency[key]:
            require(child in adjacency)
            visit(child, seen | {key})

    for key in adjacency:
        visit(key, set())
    return witness
