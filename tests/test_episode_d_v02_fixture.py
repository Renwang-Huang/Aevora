"""Maintainer fixture tests; original app/old task truth stay unchanged."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from benchmark.episodes.episode_d_v02 import (ROOT, IMPLEMENTATIONS, build_episode_d_v02,
                                             episode_d_v02_patch, implementation_sources)
from benchmark.submission import apply_verified_patch, snapshot_source_tree


def _run(workspace, source):
    program = workspace / "fixture_probe.py"
    program.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).parent))\n" + source)
    result = subprocess.run([sys.executable, "-I", "-B", str(program)], cwd=workspace,
                            capture_output=True, text=True, timeout=20)
    (workspace / "probe.stdout").write_text(result.stdout)
    (workspace / "probe.stderr").write_text(result.stderr)
    (workspace / "probe_receipt.json").write_text(json.dumps({"argv": [sys.executable, "-I", "-B", str(program)],
        "exit_code": result.returncode, "program_sha256": hashlib.sha256(program.read_bytes()).hexdigest()}, indent=2))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _with_public_clock(workspace):
    shutil.copy(ROOT / "tests/public/test_episode_d_v02.py", workspace / "diagnostic_clock.py")
    return '''import json,sqlite3
from diagnostic_clock import diagnostic_environment
from app.service import OrderFlow
flow=OrderFlow(Path(__file__).parent/'business.sqlite')
flow.initialize({'SKU':10},reset=True)
'''


@pytest.mark.parametrize("implementation", IMPLEMENTATIONS)
def test_new_fixture_has_real_python_and_preserves_old_business_source(tmp_path, implementation):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    for name in ("orders.py", "inventory.py", "persistence.py", "errors.py"):
        assert (workspace / "app" / name).read_bytes() == (ROOT / "app" / name).read_bytes()
    assert (workspace / "app/legacy_service.py").read_bytes() == (ROOT / "app/service.py").read_bytes()
    for source in (workspace / "app").rglob("*.py"):
        ast.parse(source.read_text())
    assert list(workspace.iterdir()) == [workspace / "app"]


@pytest.mark.parametrize("implementation", ["reference", "flock", "local_lock", "blind_cleanup"])
def test_patch_fidelity_matches_exact_new_implementation(tmp_path, implementation):
    base = build_episode_d_v02(tmp_path / "baseline")
    target = build_episode_d_v02(tmp_path / "target", implementation=implementation)
    patch = tmp_path / "submission.diff"
    patch.write_text(episode_d_v02_patch(implementation))
    assert patch.stat().st_size > 0
    applied = apply_verified_patch(base, patch)
    assert applied["status"] == "PASS"
    assert snapshot_source_tree(base) == snapshot_source_tree(target)


def test_inventory_only_control_is_honestly_the_same_capacity_safe_artifact():
    assert implementation_sources("inventory_only") == implementation_sources("buggy")
    with pytest.raises(ValueError):
        episode_d_v02_patch("inventory_only")


@pytest.mark.parametrize("implementation", IMPLEMENTATIONS)
def test_all_strategies_execute_normal_claim_complete_on_real_database(tmp_path, implementation):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    result = _run(workspace, '''import json,sqlite3
from app.service import OrderFlow
flow=OrderFlow(Path(__file__).parent/'business.sqlite')
flow.initialize({'SKU':10},reset=True)
c=flow.claim_request('req','order','SKU',3,100000)
r=flow.complete_request(c['handle'])
again=flow.complete_request(c['handle'])
print(json.dumps({'claim':c,'receipt':r,'again':again,'inventory':flow.get_inventory('SKU')}))
''')
    assert result["claim"]["outcome"] == "CLAIM_GRANTED"
    assert result["receipt"]["outcome"] == "COMPLETE_RESERVED"
    assert result["receipt"] == result["again"]
    assert result["inventory"]["available"] == 7
    assert result["inventory"]["reserved"] == 3


@pytest.mark.parametrize("implementation", ["reference", "flock"])
@pytest.mark.parametrize("entrypoint", ["script", "discovery"])
def test_public_real_clock_sqlite_regressions_are_executed(tmp_path, implementation, entrypoint):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    target = workspace / "tests/public"
    target.mkdir(parents=True)
    shutil.copy(ROOT / "tests/public/test_episode_d_v02.py", target)
    command = ([sys.executable, "-I", "-B", str(target / "test_episode_d_v02.py")]
               if entrypoint == "script" else
               [sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", "tests/public", "-v"])
    result = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=20)
    (workspace / "public.stdout").write_text(result.stdout)
    (workspace / "public.stderr").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert "Ran 6 tests" in result.stderr and result.stderr.endswith("OK\n")


@pytest.mark.parametrize("implementation,expected", [("buggy", "COMPLETED"), ("local_lock", "COMPLETED"),
                                                      ("reference", "CANCELLED"), ("flock", "CANCELLED")])
def test_actual_cancellation_then_late_complete_distinguishes_strategies(tmp_path, implementation, expected):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    result = _run(workspace, '''import json,sqlite3
from app.service import OrderFlow
flow=OrderFlow(Path(__file__).parent/'business.sqlite')
flow.initialize({'SKU':10},reset=True)
c=flow.claim_request('req','order','SKU',2,100000)
cancel=flow.cancel_request('req')
late=flow.complete_request(c['handle'])
with sqlite3.connect(flow.persistence.db_path) as db:
    request=db.execute('SELECT status,current_token,deadline FROM requests').fetchone()
    orders=db.execute('SELECT order_id,status FROM orders').fetchall()
    ledger=db.execute('SELECT action,quantity FROM inventory_ledger').fetchall()
print(json.dumps({'cancel':cancel,'late':late,'request':request,'orders':orders,'ledger':ledger}))
''')
    assert result["cancel"]["outcome"] == "REQUEST_CANCELLED"
    assert result["request"][0] == expected
    if expected == "COMPLETED":
        assert result["late"]["outcome"] == "COMPLETE_RESERVED"
        assert result["orders"] == [["order", "reserved"]]
        assert result["ledger"] == [["reserve", 2]]
    else:
        assert result["late"]["outcome"] in ("REQUEST_CANCELLED", "STALE_HANDLE")
        assert result["orders"] == [] and result["ledger"] == []


def test_flock_is_actual_cross_worker_guard_and_deferred_request_transactions():
    source = implementation_sources("flock")
    assert 'connection.execute("BEGIN")' in source["requests.py"]
    assert "self._request_transaction()" in source["requests.py"]
    assert "fcntl.flock(lock.fileno(), fcntl.LOCK_EX)" in source["service.py"]
    assert '.requests.lock", "a+b"' in source["service.py"]
    assert ".unlink(" not in source["service.py"]


def test_new_fixture_refuses_unknown_strategy_or_existing_tree(tmp_path):
    with pytest.raises(ValueError):
        build_episode_d_v02(tmp_path / "bad", variant="v01")
    with pytest.raises(ValueError):
        build_episode_d_v02(tmp_path / "bad", implementation="invented")
    assert not (tmp_path / "bad").exists()
    workspace = build_episode_d_v02(tmp_path / "existing")
    with pytest.raises(ValueError):
        build_episode_d_v02(workspace)


@pytest.mark.parametrize("implementation", IMPLEMENTATIONS)
def test_real_clock_expiry_takeover_and_old_completion_raw_records(tmp_path, implementation):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    result = _run(workspace, _with_public_clock(workspace) + '''
with diagnostic_environment(Path('/tmp') / ('dv02-fixture-'+__import__('uuid').uuid4().hex+'.sock')) as clock:
    a=flow.claim_request('req','order','SKU',2,5)
    clock.advance(5)
    b=flow.claim_request('req','order','SKU',2,20)
    with sqlite3.connect(flow.persistence.db_path) as db:
        before=db.execute('SELECT current_token,deadline,status FROM requests').fetchone()
    late=flow.complete_request(a['handle'])
    with sqlite3.connect(flow.persistence.db_path) as db:
        after=db.execute('SELECT current_token,deadline,status FROM requests').fetchone()
        claims=db.execute('SELECT token,issued_tick,issued_deadline FROM request_claims ORDER BY issued_tick').fetchall()
        effects=db.execute('SELECT count(*) FROM inventory_ledger').fetchone()[0]
    renewed=flow.renew_request(b['handle'],30)
print(json.dumps({'a':a,'b':b,'before':before,'after':after,'claims':claims,'late':late,
                 'renewed':renewed,'effects':effects}))
''')
    assert result["a"]["handle"]["token"] != result["b"]["handle"]["token"]
    assert result["before"] == [result["b"]["handle"]["token"], "25", "PENDING"]
    assert result["claims"] == [[result["a"]["handle"]["token"], "0", "5"],
                                 [result["b"]["handle"]["token"], "5", "25"]]
    if implementation in ("buggy", "inventory_only", "local_lock"):
        assert result["late"]["outcome"] == "COMPLETE_RESERVED"
        assert result["after"] == [None, None, "COMPLETED"] and result["effects"] == 1
    elif implementation == "blind_cleanup":
        assert result["late"]["outcome"] == "STALE_HANDLE"
        assert result["after"] == [None, None, "PENDING"] and result["effects"] == 0
        assert result["renewed"]["outcome"] == "STALE_HANDLE"
    else:
        assert result["late"]["outcome"] == "STALE_HANDLE"
        assert result["after"] == result["before"] and result["effects"] == 0
        assert result["renewed"]["outcome"] == "CLAIM_RENEWED"


@pytest.mark.parametrize("implementation", ["reference", "flock"])
def test_reset_terminal_conflict_clock_failure_and_invalid_inputs_are_real(tmp_path, implementation):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    result = _run(workspace, _with_public_clock(workspace) + '''
import os
from app.request_errors import RequestConflict,RequestNotFound,ClockUnavailable
from app.errors import InvalidInput
errors=[]
with diagnostic_environment(Path('/tmp') / ('dv02-fixture-'+__import__('uuid').uuid4().hex+'.sock')) as clock:
    handle=flow.claim_request('req','order','SKU',1,10)['handle']
    original=flow.cancel_request('req')
    try: flow.claim_request('req','other','SKU',1,10)
    except RequestConflict: errors.append('terminal_conflict')
    for value in (0,-1,True,1.5,'1'):
        try: flow.claim_request('invalid','invalid','SKU',1,value)
        except InvalidInput: errors.append('invalid_ttl')
    try: flow.get_request('missing')
    except RequestNotFound: errors.append('missing')
    os.environ['ORDERFLOW_CLOCK_QUERY']=str(Path(__file__).parent/'missing-clock.sock')
    try: flow.claim_request('clock-failure','clock-order','SKU',1,10)
    except ClockUnavailable: errors.append('clock')
    with sqlite3.connect(flow.persistence.db_path) as db:
        clock_rows=db.execute('SELECT count(*) FROM requests WHERE request_id=?',('clock-failure',)).fetchone()[0]
    flow.initialize({'SKU':4},reset=True)
    with sqlite3.connect(flow.persistence.db_path) as db:
        rows=[db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('requests','request_claims','orders','inventory_ledger')]
print(json.dumps({'errors':errors,'clock_rows':clock_rows,'rows':rows,'inventory':flow.get_inventory('SKU')}))
''')
    assert result["errors"] == ["terminal_conflict", *( ["invalid_ttl"] * 5), "missing", "clock"]
    assert result["clock_rows"] == 0 and result["rows"] == [0, 0, 0, 0]
    assert result["inventory"]["initial_stock"] == result["inventory"]["available"] == 4


@pytest.mark.parametrize("implementation", ["reference", "flock"])
def test_new_insufficient_order_rolls_back_and_independent_intents_share_order(tmp_path, implementation):
    workspace = build_episode_d_v02(tmp_path / implementation, implementation=implementation)
    result = _run(workspace, _with_public_clock(workspace) + '''
with diagnostic_environment(Path('/tmp') / ('dv02-fixture-'+__import__('uuid').uuid4().hex+'.sock')) as clock:
    too_large=flow.claim_request('too-large','too-large','SKU',11,10)
    failed=flow.complete_request(too_large['handle'])
    with sqlite3.connect(flow.persistence.db_path) as db:
        empty=db.execute('SELECT count(*) FROM orders').fetchone()[0]
    first=flow.claim_request('first','shared-order','SKU',3,10)
    one=flow.complete_request(first['handle'])
    second=flow.claim_request('second','shared-order','SKU',3,10)
    two=flow.complete_request(second['handle'])
    with sqlite3.connect(flow.persistence.db_path) as db:
        counts=[db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('orders','inventory_ledger')]
print(json.dumps({'failed':failed,'empty':empty,'one':one,'two':two,'counts':counts,'inventory':flow.get_inventory('SKU')}))
''')
    assert result["failed"]["outcome"] == "INSUFFICIENT_INVENTORY_RETRYABLE"
    assert result["empty"] == 0
    assert result["one"]["outcome"] == result["two"]["outcome"] == "COMPLETE_RESERVED"
    assert result["counts"] == [1, 1] and result["inventory"]["reserved"] == 3


@pytest.mark.parametrize("implementation", ["buggy", "reference", "flock", "local_lock", "blind_cleanup"])
def test_four_real_isolated_os_workers_preserve_or_violate_current_authority(tmp_path, implementation):
    """Supplement the trusted suite with actual four-worker strategy evidence."""
    from evaluator.dv02_supervisor import DV02WorkerSupervisor
    workspace = build_episode_d_v02(tmp_path / "candidate", implementation=implementation)
    supervisor = DV02WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts",
                                     worker_count=4).start()
    try:
        supervisor.initialize({"SKU": 30})
        for index in range(4):
            claim = supervisor.call(index, "claim_request", request_id=f"witness-{index}",
                                    order_id=f"witness-{index}", sku="SKU", quantity=1, ttl=100)
            assert supervisor.call(index, "complete_request", handle=claim["handle"])["outcome"] == "COMPLETE_RESERVED"
        identities = supervisor.evidence()["identity_generations"]
        assert len({row["host_pid"] for row in identities}) == 4
        db_path = tmp_path / "data/business.sqlite"
        inode = db_path.stat().st_ino
        a = supervisor.call(0, "claim_request", request_id="handoff", order_id="handoff",
                            sku="SKU", quantity=2, ttl=5)
        stopped = supervisor.pause(0)
        assert stopped["kernel_state"] in {"T", "t"}
        supervisor.clock.advance(5)
        b = supervisor.call(1, "claim_request", request_id="handoff", order_id="handoff",
                            sku="SKU", quantity=2, ttl=20)
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as connection:
            before = connection.execute("SELECT current_token,deadline,status FROM requests WHERE request_id='handoff'").fetchone()
        supervisor.resume(0)
        late = supervisor.call(0, "complete_request", handle=a["handle"])
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as connection:
            after = connection.execute("SELECT current_token,deadline,status FROM requests WHERE request_id='handoff'").fetchone()
            created = connection.execute("SELECT count(*) FROM orders WHERE order_id='handoff'").fetchone()[0]
        if implementation in {"buggy", "local_lock"}:
            assert late["outcome"] == "COMPLETE_RESERVED" and after == (None, None, "COMPLETED")
            assert created == 1
        elif implementation == "blind_cleanup":
            assert late["outcome"] == "STALE_HANDLE" and after == (None, None, "PENDING")
            assert created == 0
            assert supervisor.call(1, "renew_request", handle=b["handle"], ttl=30)["outcome"] == "STALE_HANDLE"
        else:
            assert late["outcome"] == "STALE_HANDLE" and after == before and created == 0
            assert supervisor.call(1, "renew_request", handle=b["handle"], ttl=30)["outcome"] == "CLAIM_RENEWED"
            assert supervisor.call(1, "complete_request", handle=b["handle"])["outcome"] == "COMPLETE_RESERVED"
        witnesses = supervisor.evidence()["database_fd_witnesses"]
        assert {row["worker_index"] for row in witnesses if row.get("matching_fds")} == set(range(4))
        assert {row["database"]["inode"] for row in witnesses} == {inode}
        (tmp_path / "artifacts/STRATEGY_OBSERVATION.json").write_text(json.dumps({
            "implementation": implementation, "before": before, "after": after,
            "a": a, "b": b, "late": late, "created": created,
            "source": "four actual sandboxed OS workers; host read-only raw SQLite; owned pidfd pause"}, indent=2))
    finally:
        supervisor.close()
    evidence = supervisor.evidence()
    assert evidence["cleanup"]["complete"] is True
    assert evidence["pool_cgroup"]["cleanup_complete"] is True
    assert evidence["clock"]["cleanup"]["complete"] is True
