CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
CREATE TABLE nodes(
 label TEXT NOT NULL,
 id TEXT NOT NULL UNIQUE,
 payload BLOB NOT NULL CHECK(length(payload)<=262144),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 PRIMARY KEY(label,id)
) STRICT;
CREATE TABLE edges(
 id TEXT PRIMARY KEY,
 relation TEXT NOT NULL,
 source_label TEXT NOT NULL, source_id TEXT NOT NULL,
 target_label TEXT NOT NULL, target_id TEXT NOT NULL,
 payload BLOB NOT NULL CHECK(length(payload)<=262144),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 FOREIGN KEY(source_label,source_id) REFERENCES nodes(label,id),
 FOREIGN KEY(target_label,target_id) REFERENCES nodes(label,id)
) STRICT;
CREATE INDEX edge_out ON edges(source_label,source_id,relation,target_id);
CREATE INDEX edge_in ON edges(target_label,target_id,relation,source_id);
CREATE UNIQUE INDEX outcome_context ON edges(source_label,source_id,relation)
 WHERE relation IN ('IN_CONTEXT','FOR_TASK');
CREATE INDEX node_label_id ON nodes(label,id);
CREATE INDEX node_run ON nodes(label,json_extract(payload,'$.run_id'),id);
CREATE INDEX node_candidate ON nodes(label,json_extract(payload,'$.candidate_id'),id);
CREATE INDEX node_experience ON nodes(label,json_extract(payload,'$.experience_id'),id);
CREATE TRIGGER immutable_node BEFORE UPDATE ON nodes WHEN old.label!='LifecycleHead'
 BEGIN SELECT RAISE(ABORT,'immutable node'); END;
CREATE TRIGGER immutable_edge BEFORE UPDATE ON edges BEGIN SELECT RAISE(ABORT,'immutable edge'); END;
CREATE TRIGGER append_only_node BEFORE DELETE ON nodes BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER append_only_edge BEFORE DELETE ON edges BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TABLE run_contexts(run_id TEXT PRIMARY KEY, context_sha256 TEXT NOT NULL, facts BLOB NOT NULL) STRICT;
CREATE TABLE operation_results(
 operation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 request_sha256 TEXT NOT NULL, result BLOB NOT NULL,
 FOREIGN KEY(run_id) REFERENCES run_contexts(run_id)
) STRICT;
