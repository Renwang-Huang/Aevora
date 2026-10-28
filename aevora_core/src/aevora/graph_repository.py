"""Real FalkorDB repository. Database failures are explicit; records never overwrite history."""
from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any

from .models import (LABELS, RELATIONSHIPS, QUERY_VERSION, SCHEMA_VERSION, GraphError,
                     GraphUnavailable, ImmutableConflict, InvalidRecord, canonical_json,
                     digest, normalize_context, public_record, utc_now, validate_id,
                     validate_record, validate_scope, parse_timestamp, PUBLIC_CONTEXT_FACTS)
from .models import LIFECYCLE_LABELS, LIFECYCLE_RELATIONSHIPS, schema_catalog


class GraphRepository:
    def __init__(self, *, host: str = "127.0.0.1", port: int = 17692,
                 graph_name: str = "aevora", password: str,
                 socket_timeout: float = 10.0, query_timeout_ms: int = 5000):
        validate_id(graph_name)
        if not password:
            raise InvalidRecord("FalkorDB password is required")
        if not 1 <= port <= 65535 or not 1 <= query_timeout_ms <= 30000:
            raise InvalidRecord("Invalid bounded connection parameters")
        try:
            from falkordb import FalkorDB
            from redis.backoff import NoBackoff
            from redis.retry import Retry
            self._client = FalkorDB(host=host, port=port, password=password,
                                    socket_connect_timeout=3.0, socket_timeout=socket_timeout,
                                    max_connections=8, retry=Retry(NoBackoff(), 0))
            self._graph = self._client.select_graph(graph_name)
        except ImportError as exc:
            raise GraphUnavailable("Official FalkorDB SDK is unavailable") from None
        except Exception as exc:
            # The official constructor performs discovery/authentication I/O.
            # Its errors must be classified here, without printing connection data.
            raise GraphUnavailable(f"FalkorDB connection unavailable ({type(exc).__name__})") from None
        self.graph_name = graph_name
        self.query_timeout_ms = query_timeout_ms
        from .backend_guard import BackendGuard
        self._backend_guard = BackendGuard(host, port, graph_name)

    @classmethod
    def from_environment(cls) -> "GraphRepository":
        password_path = os.environ.get("AEVORA_FALKORDB_PASSWORD_FILE")
        if not password_path:
            from .startup import StartupError
            raise StartupError('HOST_CONFIG_REQUIRED', 'No database credential file is configured on this Host.',
                'Run aevora configure --port PORT --graph GRAPH --password-file ABSOLUTE_PATH, or use --config PATH in this terminal. Explicit deployments may set AEVORA_FALKORDB_PASSWORD_FILE.')
        path = Path(password_path)
        try: fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        except OSError:
            from .startup import StartupError
            raise StartupError('DB_CREDENTIAL_FILE_UNAVAILABLE', 'The configured database credential file could not be opened safely.',
                'Check the Host profile password_file reference and the owned mode-0600 file; recreate missing project secrets with the documented bootstrap, without printing them.') from None
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_uid != os.getuid():
                raise InvalidRecord("DB password must be an ordinary unlinked secret file")
            if metadata.st_mode & 0o077:
                raise InvalidRecord("DB password file must not be group/world accessible")
            if not 1 <= metadata.st_size <= 4096:
                raise InvalidRecord("DB password file has invalid size")
            secret = os.read(fd, 4097)
            if not secret or len(secret) != metadata.st_size or len(secret) > 4096:
                raise InvalidRecord("DB password file has invalid size")
            after = os.fstat(fd)
            if (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise InvalidRecord("DB password file changed during bounded read")
        finally:
            os.close(fd)
        try:
            password = secret.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise InvalidRecord("DB password must be UTF-8") from None
        if not password:
            raise InvalidRecord("DB password must not be empty")
        return cls(host=os.environ.get("AEVORA_FALKORDB_HOST", "127.0.0.1"),
                   port=int(os.environ.get("AEVORA_FALKORDB_PORT", "17692")),
                   graph_name=os.environ.get("AEVORA_FALKORDB_GRAPH", "aevora"), password=password)

    def query(self, statement: str, params: dict[str, Any] | None = None,
              *, read_only: bool = True) -> list[list[Any]]:
        """Trusted-host only: the Participant never receives this object or a Cypher tool."""
        if not read_only:
            with self._write_guard():
                return self._execute_query(statement, params, read_only=False)
        return self._execute_query(statement, params, read_only=True)

    def _write_guard(self):
        return self._backend_guard.write()

    def _execute_query(self, statement, params, *, read_only):
        try:
            method = self._graph.ro_query if read_only else self._graph.query
            return method(statement, params=params or {}, timeout=self.query_timeout_ms).result_set
        except Exception as exc:
            # Do not include SDK exception text: it may echo parameters or connection secrets.
            raise GraphUnavailable(f"FalkorDB operation unavailable ({type(exc).__name__})") from None

    def initialize(self, *, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
        with self._write_guard():
            return self._initialize(schema_version=schema_version)

    def _initialize(self, *, schema_version):
        """Build and verify actual async constraints before accepting graph records."""
        # db.constraints() is a read-only procedure and FalkorDB rejects it on
        # a nonexistent graph key. A real immutable schema node bootstraps it.
        labels = schema_catalog(schema_version)["labels"]
        self.put_node("Schema", {"id": schema_version, "version": schema_version})
        try:
            for label in sorted(labels):
                existing = self._graph.list_constraints()
                for constraint_type, properties in (("UNIQUE", ["id"]),
                                                     ("MANDATORY", ["id", "payload_json", "payload_sha256"])):
                    if any(c.get("entitytype") == "NODE" and c["label"] == label and c["type"] == constraint_type
                           and sorted(c["properties"]) == sorted(properties) for c in existing):
                        continue
                    if constraint_type == "UNIQUE":
                        self._graph.create_node_unique_constraint(label, *properties)
                    else:
                        self._graph.create_node_mandatory_constraint(label, *properties)
            deadline = time.monotonic() + 10.0
            while True:
                constraints = self._graph.list_constraints()
                expected = len(labels) * 2
                owned = constraints
                identities = [(c.get("entitytype"), c["label"], c["type"], tuple(sorted(c["properties"]))) for c in owned]
                required = {("NODE", label, kind, tuple(sorted(properties))) for label in labels
                    for kind, properties in (("UNIQUE", ["id"]), ("MANDATORY", ["id", "payload_json", "payload_sha256"]))}
                if len(owned) != expected or len(set(identities)) != len(identities) or set(identities) != required:
                    raise GraphError("Schema constraint set is incomplete")
                if any(c["status"] == "FAILED" for c in owned):
                    raise GraphError("Schema constraint construction failed")
                if all(c["status"] == "OPERATIONAL" for c in owned):
                    break
                if time.monotonic() >= deadline:
                    raise GraphError("Schema constraint construction exceeded deadline")
                time.sleep(0.02)
        except GraphError:
            raise
        except Exception as exc:
            raise GraphUnavailable(f"FalkorDB schema unavailable ({type(exc).__name__})") from None
        self.put_node("Schema", {"id": schema_version, "version": schema_version})
        return {"schema_version": schema_version, "graph_name": self.graph_name,
                "constraints": owned, "status": "READY"}

    def _audit_conflict(self, *, label: str, record_id: str, expected: str, received: str) -> None:
        audit = {"id": "conflict:" + digest([label, record_id, expected, received]),
                 "event": "immutable_conflict", "record_label": label, "record_id": record_id,
                 "existing_digest": expected, "attempted_digest": received}
        # Audit IDs are deterministic, allowing retries without modifying their first fact.
        self.put_node("AuditEvent", audit)

    def put_node(self, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = validate_record(label, payload)
        encoded, fingerprint = canonical_json(payload), digest(payload)
        try:
            # FalkorDB validates mandatory properties at node creation, before
            # ON CREATE SET. Include the complete immutable value in MERGE.
            # UNIQUE(id) rejects a same-id different-value creation atomically.
            rows = self.query(f"MERGE (n:{label} {{id:$id,payload_json:$payload,payload_sha256:$sha}}) "
                              "ON CREATE SET n.run_id=$run_id RETURN n.payload_sha256",
                              {"id": payload["id"], "payload": encoded, "sha": fingerprint,
                               "run_id": payload.get("run_id")}, read_only=False)
        except GraphUnavailable:
            existing = self.get_node(label, payload["id"])
            if existing is not None and digest(existing) != fingerprint:
                self._audit_conflict(label=label, record_id=payload["id"],
                                     expected=digest(existing), received=fingerprint)
                raise ImmutableConflict(f"Conflicting immutable {label} id: {payload['id']}") from None
            raise
        if not rows or len(rows) != 1:
            raise GraphError("Immutable node write did not return exactly one record")
        if rows[0][0] != fingerprint:
            self._audit_conflict(label=label, record_id=payload["id"], expected=rows[0][0], received=fingerprint)
            raise ImmutableConflict(f"Conflicting immutable {label} id: {payload['id']}")
        return {"id": payload["id"], "payload_sha256": fingerprint}

    def get_node(self, label: str, record_id: str, *, public: bool = False) -> dict[str, Any] | None:
        if label not in LIFECYCLE_LABELS:
            raise InvalidRecord("Unknown graph label")
        validate_id(record_id)
        rows = self.query(f"MATCH (n:{label} {{id:$id}}) RETURN n.payload_json,n.payload_sha256", {"id": record_id})
        if not rows:
            return None
        if len(rows) != 1:
            raise GraphError("Duplicate graph identity")
        payload = self._decode(label, rows[0][0], rows[0][1])
        if payload["id"] != record_id:
            raise GraphError("Stored payload identity differs from the actual node")
        return public_record(label, payload) if public else payload

    @staticmethod
    def _decode(label: str, raw: str, fingerprint: str) -> dict:
        try:
            record = json.loads(raw)
            if digest(record) != fingerprint:
                raise InvalidRecord("Stored payload digest mismatch")
            return validate_record(label, record)
        except (ValueError, TypeError, KeyError):
            raise GraphError("Graph record is malformed or its digest is inconsistent") from None

    def put_edge(self, edge_type: str, source_label: str, source_id: str,
                 target_label: str, target_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if edge_type not in LIFECYCLE_RELATIONSHIPS or source_label not in LIFECYCLE_LABELS or target_label not in LIFECYCLE_LABELS:
            raise InvalidRecord("Unknown graph edge schema")
        validate_id(source_id); validate_id(target_id)
        if edge_type in {"IN_CONTEXT", "FOR_TASK"}:
            existing = self.query(f"MATCH (s:{source_label} {{id:$source}})-[:{edge_type}]->(t) RETURN t.id",
                                  {"source": source_id})
            if any(row[0] != target_id for row in existing):
                raise ImmutableConflict("A recorded outcome context/task cannot be reinterpreted")
        value = dict(payload or {})
        edge_id = "edge:" + digest([edge_type, source_label, source_id, target_label, target_id])
        if "id" in value and value["id"] != edge_id:
            raise InvalidRecord("Edge id is derived from immutable endpoints")
        value["id"] = edge_id
        fingerprint = digest(value)
        guard = ""
        if edge_type in {"IN_CONTEXT", "FOR_TASK"}:
            # FalkorDB serializes write queries. Enforce cardinality in the same
            # query as insertion, including concurrent trusted ingestion attempts.
            guard = (f"OPTIONAL MATCH (s)-[:{edge_type}]->(old) "
                     "WITH s,t,collect(old.id) AS previous "
                     "WHERE size(previous)=0 OR (size(previous)=1 AND previous[0]=$target) ")
        rows = self.query(f"MATCH (s:{source_label} {{id:$source}}), (t:{target_label} {{id:$target}}) "
                          + guard + f"MERGE (s)-[r:{edge_type} {{id:$id}}]->(t) ON CREATE SET "
                          "r.payload_json=$payload, r.payload_sha256=$sha RETURN r.payload_sha256",
                          {"source": source_id, "target": target_id, "id": edge_id,
                           "payload": canonical_json(value), "sha": fingerprint}, read_only=False)
        if not rows or len(rows) != 1:
            raise GraphError("Edge endpoints are absent or duplicated")
        if rows[0][0] != fingerprint:
            self._audit_conflict(label=edge_type, record_id=edge_id, expected=rows[0][0], received=fingerprint)
            raise ImmutableConflict(f"Conflicting immutable edge id: {edge_id}")
        return {"id": edge_id, "payload_sha256": fingerprint}

    def import_experience(self, experience: dict[str, Any], rule: dict[str, Any],
                          revision_id: str | None = None) -> dict[str, Any]:
        validate_record("Experience", experience)
        premises = rule.get("premises", [])
        if not isinstance(premises, list) or not premises:
            raise InvalidRecord("Rule requires graph premises")
        rule_record = {k: v for k, v in rule.items() if k != "premises"}
        validate_record("Rule", rule_record)
        for premise in premises:
            validate_record("Premise", premise)
        premise_ids = sorted(p["id"] for p in premises)
        if len(set(premise_ids)) != len(premise_ids):
            raise InvalidRecord("Rule contains duplicate premise identities")
        # The immutable declaration lets the resolver detect a deleted or
        # incomplete REQUIRES edge without restoring its missing condition.
        rule_record["premise_ids"] = premise_ids
        rule_record["premise_count"] = len(premise_ids)
        revision_id = revision_id or experience["id"] + "/revision/initial"
        self.put_node("Experience", experience)
        revision = {"id": revision_id, "experience_id": experience["id"],
                    "created_at": experience.get("created_at", "UNAVAILABLE"),
                    "revision_reason": "initial_verified_history_import", "attribution": "UNKNOWN"}
        self.put_node("ExperienceRevision", revision)
        self.put_node("Rule", rule_record)
        self.put_edge("HAS_REVISION", "Experience", experience["id"], "ExperienceRevision", revision_id)
        self.put_edge("USES_RULE", "ExperienceRevision", revision_id, "Rule", rule_record["id"])
        for premise in premises:
            self.put_node("Premise", premise)
            self.put_edge("REQUIRES", "Rule", rule_record["id"], "Premise", premise["id"])
        return {"experience_id": experience["id"], "revision_id": revision_id,
                "rule_id": rule_record["id"], "premise_count": len(premises)}

    def attach_evidence(self, experience_id: str, evidence: dict[str, Any], outcome: dict[str, Any],
                        context: dict[str, Any], task: dict[str, Any], *, relation: str = "SUPPORTED_BY",
                        revision_id: str | None = None) -> dict[str, Any]:
        if relation not in {"SUPPORTED_BY", "COUNTEREXAMPLE", "OBSERVED_OUTCOME"}:
            raise InvalidRecord("Invalid experience evidence relation")
        if self.get_node("Experience", experience_id) is None:
            raise InvalidRecord("Experience is absent")
        revision_id = revision_id or experience_id + "/revision/initial"
        revision = self.get_node("ExperienceRevision", revision_id)
        if revision is None:
            raise InvalidRecord("Revision is absent")
        if revision.get("experience_id") != experience_id or not self.query(
            "MATCH (:Experience {id:$e})-[:HAS_REVISION]->(:ExperienceRevision {id:$r}) RETURN count(*)",
            {"e": experience_id, "r": revision_id})[0][0]:
            raise InvalidRecord("Revision is not associated with this Experience")
        context = dict(context)
        context["facts"] = normalize_context(context.get("facts", {}))
        for label, record in (("Evidence", evidence), ("VerifiedOutcome", outcome),
                              ("Context", context), ("Task", task)):
            validate_record(label, record)
        if relation == "SUPPORTED_BY" and outcome["verdict"] != "PASS":
            raise InvalidRecord("A non-PASS outcome cannot be a positive support chain")
        if relation == "COUNTEREXAMPLE" and outcome["verdict"] != "FAIL":
            raise InvalidRecord("Only business FAIL can be a counterexample, not infrastructure error")
        if evidence.get("source_run_id", outcome["run_id"]) != outcome["run_id"]:
            raise InvalidRecord("Evidence source run does not match Outcome")
        # Fully validate before writing. Every operation is independently idempotent;
        # interrupted imports are safely retried and incomplete paths are not recommendations.
        for label, record in (("Evidence", evidence), ("VerifiedOutcome", outcome),
                              ("Context", context), ("Task", task)):
            self.put_node(label, record)
        self.put_edge(relation, "ExperienceRevision", revision_id, "Evidence", evidence["id"])
        self.put_edge("VERIFIES", "Evidence", evidence["id"], "VerifiedOutcome", outcome["id"])
        self.put_edge("IN_CONTEXT", "VerifiedOutcome", outcome["id"], "Context", context["id"])
        self.put_edge("FOR_TASK", "Context", context["id"], "Task", task["id"])
        return {"experience_id": experience_id, "revision_id": revision_id, "evidence_id": evidence["id"],
                "outcome_id": outcome["id"], "relation": relation}

    def experience_ids(self) -> list[str]:
        ids = [row[0] for row in self.query("MATCH (e:Experience) RETURN e.id ORDER BY e.id")]
        result = []
        for identifier in ids:
            value = self.get_node("Experience", identifier)
            candidate = value.get("publication_candidate_id")
            if candidate:
                from .candidate import CandidateLifecycle
                if not CandidateLifecycle(self).publication_allowed(candidate, identifier):
                    continue
            result.append(identifier)
        return result

    def experience_was_resolved(self, run_id: str, experience_id: str) -> bool:
        validate_id(run_id); validate_id(experience_id)
        rows = self.query("MATCH (q:Query)-[:CONSIDERED]->(e:Experience {id:$experience}) "
                          "WHERE q.run_id=$run RETURN q.id",
                          {"experience": experience_id, "run": run_id})
        for row in rows:
            self.require_edge("CONSIDERED","Query",row[0],"Experience",experience_id)
        return bool(rows)

    def premise_paths(self, experience_id: str) -> list[dict[str, Any]]:
        validate_id(experience_id)
        rows = self.query("MATCH (e:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)"
                          "-[:USES_RULE]->(rule:Rule)-[:REQUIRES]->(p:Premise) "
                          "RETURN r.payload_json,r.payload_sha256,rule.payload_json,rule.payload_sha256,"
                          "p.payload_json,p.payload_sha256 ORDER BY r.id,rule.id,p.id",
                          {"id": experience_id})
        result = []
        for row in rows:
            records = [self._decode(label, row[i * 2], row[i * 2 + 1])
                       for i, label in enumerate(("ExperienceRevision", "Rule", "Premise"))]
            result.append({"revision": public_record("ExperienceRevision", records[0]),
                           "rule": public_record("Rule", records[1]), "premise": public_record("Premise", records[2]),
                           "path": [experience_id] + [record["id"] for record in records]})
        return result

    def snapshot_public_paths(self, experience_id: str) -> list[dict[str, Any]]:
        validate_id(experience_id)
        rows = self.query("MATCH (e:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)"
                          "-[link]->(ev:Evidence)-[:VERIFIES]->(o:VerifiedOutcome)"
                          "-[:IN_CONTEXT]->(c:Context)-[:FOR_TASK]->(t:Task) "
                          "WHERE type(link) IN $relations "
                          "RETURN type(link),r.payload_json,r.payload_sha256,ev.payload_json,ev.payload_sha256,"
                          "o.payload_json,o.payload_sha256,c.payload_json,c.payload_sha256,t.payload_json,t.payload_sha256 "
                          "ORDER BY r.id,ev.id,o.id,c.id,t.id,type(link)",
                          {"id": experience_id, "relations": ["SUPPORTED_BY", "COUNTEREXAMPLE", "OBSERVED_OUTCOME"]})
        labels = ("ExperienceRevision", "Evidence", "VerifiedOutcome", "Context", "Task")
        result = []
        for row in rows:
            records = {label: public_record(label, self._decode(label, row[1 + 2*i], row[2 + 2*i]))
                       for i, label in enumerate(labels)}
            result.append({"relation": row[0], "records": records,
                           "path": [experience_id] + [records[label]["id"] for label in labels],
                           "edge_types": ["HAS_REVISION", row[0], "VERIFIES", "IN_CONTEXT", "FOR_TASK"]})
        return result

    def migrate_governance(self) -> dict:
        """Add exact current constraints/schema without rewriting any old record."""
        before = self.state_fingerprint()
        result = self.initialize()
        # Stable completion identity does not include mutable query bookkeeping.
        record = {"id": "migration:" + SCHEMA_VERSION, "event": "append_only_schema_migration_complete",
                  "schema_version": SCHEMA_VERSION, "query_version": QUERY_VERSION,
                  "policy": "OLD_NODE_AND_EDGE_PAYLOADS_NOT_REWRITTEN"}
        self.put_node("AuditEvent", record)
        after = self.state_fingerprint()
        return {"status": "MIGRATED", "before": before, "after": after,
                "schema": result, "completion_audit_id": record["id"]}

    def append_rule_revision(self, experience_id: str, rule: dict, *, revision_id: str,
                             supersedes_ids: list[str], source_type: str, scope: dict | None = None,
                             valid_from: str, valid_until: str | None = None,
                             public_reason: str = "Explicit scoped rule revision") -> dict:
        """Trusted host only. No public MCP writer can publish or supersede rules."""
        validate_id(experience_id); validate_id(revision_id)
        if self.get_node("Experience", experience_id) is None:
            raise InvalidRecord("Experience is absent")
        premises = rule.get("premises")
        if not isinstance(premises, list) or not premises:
            raise InvalidRecord("Rule requires premises")
        for premise in premises:
            validate_record("Premise", premise)
            if premise["fact_key"] not in PUBLIC_CONTEXT_FACTS:
                raise InvalidRecord("New rule publications require public semantic facts")
        identifiers = sorted(p["id"] for p in premises)
        if len(set(identifiers)) != len(identifiers):
            raise InvalidRecord("Duplicate premise declaration")
        rule_record = {k: v for k, v in rule.items() if k != "premises"}
        rule_record.update(premise_ids=identifiers, premise_count=len(identifiers))
        validate_record("Rule", rule_record)
        audit_id = "publication:" + digest(revision_id)
        revision = {"id": revision_id, "experience_id": experience_id, "revision_kind": "rule_publication",
                    "declared_rule_id": rule_record["id"], "supersedes_ids": sorted(supersedes_ids),
                    "source_type": source_type, "scope": scope or {}, "valid_from": valid_from,
                    "valid_until": valid_until, "created_at": valid_from, "publication_audit_id": audit_id,
                    "revision_reason": public_reason, "attribution": "UNKNOWN"}
        validate_record("ExperienceRevision", revision)
        for identifier in supersedes_ids:
            if identifier == revision_id:
                raise InvalidRecord("A revision cannot supersede itself")
            predecessor = self.get_node("ExperienceRevision", identifier)
            if not predecessor or predecessor.get("experience_id") != experience_id:
                raise InvalidRecord("Revision predecessor is absent or from another Experience")
        # Same-ID conflicts are refused before activating any new rule path.
        self.put_node("ExperienceRevision", revision)
        self.put_node("Rule", rule_record)
        self.put_edge("HAS_REVISION", "Experience", experience_id, "ExperienceRevision", revision_id)
        self.put_edge("USES_RULE", "ExperienceRevision", revision_id, "Rule", rule_record["id"])
        for premise in premises:
            self.put_node("Premise", premise)
            self.put_edge("REQUIRES", "Rule", rule_record["id"], "Premise", premise["id"])
        for predecessor in supersedes_ids:
            self.put_edge("SUPERSEDES", "ExperienceRevision", revision_id, "ExperienceRevision", predecessor)
        self.put_node("AuditEvent", {"id": audit_id, "event": "rule_publication_complete",
                                    "revision_id": revision_id, "revision_sha256": digest(revision)})
        return {"status": "PUBLISHED", "revision_id": revision_id, "rule_id": rule_record["id"],
                "completion_audit_id": audit_id}

    def append_governance_event(self, *, event_id: str, target_label: str, target_id: str,
                                event_type: str, source_type: str, public_reason: str,
                                effective_at: str, scope: dict | None = None,
                                material_fact_keys: list[str] | None = None) -> dict:
        audit_id = "governance-complete:" + digest(event_id)
        record = {"id": event_id, "target_label": target_label, "target_id": target_id,
                  "event_type": event_type, "source_type": source_type, "public_reason": public_reason,
                  "effective_at": effective_at, "created_at": effective_at, "scope": scope or {},
                  "material_fact_keys": sorted(material_fact_keys or []), "completion_audit_id": audit_id,
                  "authority": "TRUSTED_HOST_GOVERNANCE"}
        validate_record("GovernanceEvent", record)
        if self.get_node(target_label, target_id) is None:
            raise InvalidRecord("Governance target is absent")
        self.put_node("GovernanceEvent", record)
        self.put_edge("GOVERNS", "GovernanceEvent", event_id, target_label, target_id)
        self.put_node("AuditEvent", {"id": audit_id, "event": "governance_event_complete",
                                    "governance_event_id": event_id, "record_sha256": digest(record)})
        return {"status": "APPENDED", "event_id": event_id, "completion_audit_id": audit_id}

    def governance_view(self, experience_id: str) -> dict:
        rows = self.query("MATCH (:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision) "
                          "OPTIONAL MATCH (r)-[:USES_RULE]->(rule:Rule) "
                          "RETURN r.payload_json AS record,r.payload_sha256 AS sha,collect(rule.id) AS rules ORDER BY record", {"id": experience_id})
        revisions = []
        for raw, fingerprint, rules in rows:
            record = self._decode("ExperienceRevision", raw, fingerprint)
            complete = True
            if record.get("publication_audit_id"):
                audit = self.get_node("AuditEvent", record["publication_audit_id"])
                complete = bool(audit and audit.get("event") == "rule_publication_complete"
                                and audit.get("revision_id") == record["id"] and audit.get("revision_sha256") == digest(record))
            revisions.append({"record": public_record("ExperienceRevision", record),
                              "rule_ids": sorted(set(rules)), "complete": complete})
        successors = self.query("MATCH (:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)"
            "-[s:SUPERSEDES]->(old:ExperienceRevision) RETURN r.id,old.id,s.payload_json,s.payload_sha256 ORDER BY r.id,old.id", {"id": experience_id})
        supersedes = []
        for new, old, raw, fingerprint in successors:
            payload = json.loads(raw)
            expected = "edge:" + digest(["SUPERSEDES", "ExperienceRevision", new, "ExperienceRevision", old])
            if digest(payload) != fingerprint or payload.get("id") != expected:
                raise GraphError("SUPERSEDES edge digest mismatch")
            supersedes.append({"new_id": new, "old_id": old, "edge_payload_sha256": fingerprint})
        targets = {("ExperienceRevision",row["record"]["id"]) for row in revisions} | {
            ("Evidence",row[0]) for row in self.query("MATCH (:Experience {id:$id})-[:HAS_REVISION]->(:ExperienceRevision)"
                "-[link]->(ev:Evidence) WHERE type(link) IN $relations RETURN DISTINCT ev.id",
                {"id": experience_id, "relations": ["SUPPORTED_BY", "COUNTEREXAMPLE", "OBSERVED_OUTCOME"]})}
        events = []
        event_rows = self.query("MATCH (g:GovernanceEvent) OPTIONAL MATCH (g)-[:GOVERNS]->(target) "
                               "RETURN g.payload_json AS record,g.payload_sha256 AS sha,collect([labels(target),target.id]) AS targets ORDER BY record")
        if len(event_rows) > 1024:
            raise GraphError("Governance event scan bound exceeded")
        for raw, fingerprint, reached in event_rows:
            record = self._decode("GovernanceEvent", raw, fingerprint)
            if (record["target_label"],record["target_id"]) not in targets:
                continue
            audit = self.get_node("AuditEvent", record["completion_audit_id"])
            complete = bool(audit and audit.get("event") == "governance_event_complete"
                            and audit.get("governance_event_id") == record["id"] and audit.get("record_sha256") == digest(record))
            events.append({"record": public_record("GovernanceEvent", record), "complete": complete,
                           "edge_present": reached == [[[record["target_label"]],record["target_id"]]]})
        if len(revisions) > 256 or len(events) > 256 or len(supersedes) > 1024:
            raise GraphError("Governance retrieval bound exceeded")
        return {"revisions": revisions, "supersedes": supersedes, "events": events,
                "query_version": QUERY_VERSION, "consistency": "ACTUAL_MULTI_QUERY_RETRIEVAL; NOT_ATOMIC"}

    def capture_query_snapshot(self, content: dict) -> dict:
        fingerprint = digest(content)
        record = {"id": "snapshot:" + fingerprint, "content": content, "content_sha256": fingerprint}
        self.put_node("QuerySnapshot", record)
        return {"snapshot_id": record["id"], "snapshot_sha256": fingerprint}

    def load_query_snapshot(self, snapshot_id: str) -> dict:
        record = self.get_node("QuerySnapshot", snapshot_id)
        if record is None:
            raise InvalidRecord("Snapshot is absent")
        return record["content"]

    def require_query_snapshot_edge(self, query_id: str, snapshot_id: str) -> None:
        """Require the actual immutable Query -> snapshot association, not a map alone."""
        self.require_edge("AT_SNAPSHOT","Query",query_id,"QuerySnapshot",snapshot_id)

    def require_edge(self, edge_type: str, source_label: str, source_id: str,
                     target_label: str, target_id: str) -> None:
        """Validate one actual typed association and its canonical endpoint identity."""
        if edge_type not in LIFECYCLE_RELATIONSHIPS or source_label not in LIFECYCLE_LABELS or target_label not in LIFECYCLE_LABELS:
            raise InvalidRecord("Unknown graph association schema")
        validate_id(source_id); validate_id(target_id)
        rows = self.query(f"MATCH (:{source_label} {{id:$source}})-[r:{edge_type}]->(:{target_label} {{id:$target}}) "
                          "RETURN r.id,r.payload_json,r.payload_sha256", {"source":source_id,"target":target_id})
        expected = "edge:" + digest([edge_type,source_label,source_id,target_label,target_id])
        if len(rows) != 1:
            raise GraphError("Actual typed graph association is absent or ambiguous")
        identity, raw, fingerprint = rows[0]
        try:
            payload = json.loads(raw)
            valid = identity == expected and payload.get("id") == expected and digest(payload) == fingerprint
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise GraphError("Graph association identity or digest is inconsistent")

    def state_fingerprint(self) -> dict[str, Any]:
        nodes = self.query("MATCH (n) RETURN labels(n),n.id,n.payload_sha256 ORDER BY n.id")
        edges = self.query("MATCH (s)-[r]->(t) RETURN s.id,type(r),r.id,r.payload_sha256,t.id "
                           "ORDER BY s.id,type(r),r.id,t.id")
        return {"graph_name": self.graph_name, "node_count": len(nodes), "edge_count": len(edges),
                "graph_sha256": digest({"nodes": nodes, "edges": edges}), "query_version": QUERY_VERSION}

    def close(self) -> None:
        try:
            self._client.close()
        finally:
            self._backend_guard.close()
