import hashlib
import pytest
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from tools.validation.g21_fixture import seed, facts


@pytest.mark.parametrize("size", [65535, 65536, 65537, 8388608, 8388609])
def test_document_exact_utf8_bound(v2, size):
    document = "a" * (size - 2)  # canonical JSON includes exactly two quotes
    if size > MAX_DOCUMENT:
        with pytest.raises(V2Error, match="CAPACITY_EXCEEDED"):
            v2.put_document("QuerySnapshot", ["boundary", size], document)
    else:
        root = v2.put_document("QuerySnapshot", ["boundary", size], document)
        assert len(root["document"]["chunks"]) == (size + 65535) // 65536
        assert v2.load_document(root) == document


@pytest.mark.parametrize("size", [65535, 65536, 65537])
def test_chunk_plus_minus_one(v2, size):
    text = "a" * size
    if size > 65536:
        with pytest.raises(V2Error, match="CAPACITY_EXCEEDED"):
            record(
                v2.tenant,
                "SnapshotChunk",
                "oversized",
                document_id="doc:x",
                chunk_index=0,
                text=text,
                chunk_sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
    else:
        assert record(
            v2.tenant,
            "SnapshotChunk",
            ["size", size],
            document_id="doc:x",
            chunk_index=0,
            text=text,
            chunk_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )


@pytest.mark.parametrize(
    "attack", ["missing", "sha", "index", "tenant", "duplicate", "129"]
)
def test_document_corruption_cannot_reconstruct(v2, attack):
    root = v2.put_document("QuerySnapshot", attack, "汉😀" * 30000)
    first = root["document"]["chunks"][0]["id"]
    if attack == "missing":
        v2.transport.query(
            "MATCH(m {id:$m})-[r:HAS_CHUNK]->(c {id:$c}) DELETE r",
            dict(m=root["id"], c=first),
            read_only=False,
        )
    elif attack == "129":
        root["document"]["chunks"] *= 130
    elif attack == "duplicate":
        v2.transport.query(
            "MATCH(m {id:$m})-[r:HAS_CHUNK]->(c {id:$c}) CREATE(m)-[x:HAS_CHUNK]->(c) SET x=properties(r)",
            dict(m=root["id"], c=first),
            read_only=False,
        )
    else:
        n = v2.node(first)
        if attack == "sha":
            n["chunk_sha256"] = "0" * 64
        elif attack == "index":
            n["chunk_index"] = 1
        else:
            n["tenant_id"] = "other-tenant"
        v2.transport.query(
            "MATCH(n {id:$id}) SET n=$p", dict(id=first, p=native(n)), read_only=False
        )
    with pytest.raises(V2Error):
        v2.load_document(root)


@pytest.mark.parametrize("count", [512, 513])
def test_evidence_path_limit_preserves_negative(v2, count):
    seed(v2, outcomes=("PASS",) * (count - 1) + ("FAIL",))
    fs = facts(v2.registry, task__shared_state_kind="sqlite_file")
    if count > 512:
        with pytest.raises(V2Error, match="CAPACITY_EXCEEDED"):
            v2.resolve_witnesses(fs)
    else:
        state, w = v2.resolve_witnesses(fs)
        assert len(w[0]["paths"]) == 512
        # Observe the counter, never ignore the last path at the boundary.
        assert (
            any(p[1]["kind"] == "COUNTEREXAMPLE" for p in w[0]["paths"])
            if False
            else any(
                decode(p[1], v2.tenant)["kind"] == "COUNTEREXAMPLE"
                for p in w[0]["paths"]
            )
        )


def test_257_unrelated_candidates_do_not_exhaust_current_scope(v2):
    for i in range(257):
        seed(v2, "foreign-" + str(i), scope_value="other_engine", outcomes=())
    chosen = seed(v2, "related")
    fs = facts(v2.registry, task__shared_state_kind="sqlite_file")
    state = v2.state()
    result = v2.discover(fs, state)
    # Independent full enumeration oracle uses raw canonical properties, not product scope query.
    raw = v2.transport.query(
        "MATCH(s:TenantState)-[:COMMITS]->(m:PublicationManifest),(e:Experience) WHERE m.experience_id=e.id RETURN DISTINCT e.payload_json"
    )
    expected = sorted(
        decode_json(row[0])["id"]
        for row in raw
        if decode_json(row[0])["scope_token"]
        in {"*", digest(["task.shared_state_kind", "sqlite_file"])}
    )
    assert len(raw) == 258 and result == expected == [chosen["experience"]["id"]]
    assert len(resolve_v2(v2, fs, "query:scope", utc_now())[1]) == 1


def test_current_scope_257_refuses_without_favorable_truncation(v2):
    for i in range(257):
        seed(v2, "related-" + str(i), outcomes=())
    fs = facts(v2.registry, task__shared_state_kind="sqlite_file")
    with pytest.raises(V2Error, match="CAPACITY_EXCEEDED"):
        v2.discover(fs, v2.state())


def test_seek_pages_complete_identity_set(v2):
    expected = []
    for i in range(66):
        expected.append(seed(v2, "page-" + str(i), outcomes=())["experience"]["id"])
    assert v2.discover(
        facts(v2.registry, task__shared_state_kind="sqlite_file"), v2.state()
    ) == sorted(expected)
