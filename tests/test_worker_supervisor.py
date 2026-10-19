"""Real independent-process topology, scheduling, crash and control boundaries."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import pytest

from benchmark.episodes.episode_a import create_episode_a
from benchmark.sandbox import runtime_python, sandbox_command
from benchmark.templates import create_template
from benchmark.resources import CgroupScope, SecurityGateError
from evaluator.control import BoundedGate, WorkerControl
from evaluator.oracle import inspect_database
from evaluator.rpc import RemoteBusinessError
from evaluator.supervisor import WorkerSupervisor


def requests(count, prefix="worker"):
    return [{"method": "create_order", "params": {
        "order_id": f"{prefix}-{index}", "sku": "widget", "quantity": 1}}
        for index in range(count)]


@pytest.mark.parametrize("worker_count", [2, 4])
def test_real_process_pool_shares_database_and_all_workers_write(tmp_path, worker_count):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts",
                                  worker_count=worker_count).start()
    try:
        supervisor.initialize({"widget": 12})
        witnessed = [supervisor.call(index, "create_order", order_id=f"witness-{index}",
                                    sku="widget", quantity=1) for index in range(worker_count)]
        batch = supervisor.batch(requests(30), checkpoint={"label": "inventory_read", "timeout_seconds": 0.1})
        assert len({row["host_pid"] for row in batch["execution"]["worker_identities"]}) == worker_count
        assert {row["worker_index"] for row in batch["results"]} == set(range(worker_count))
        assert sum(row["ok"] for row in batch["results"]) == 12 - worker_count
        assert all(row["error"]["type"] == "InsufficientInventory"
                   for row in batch["results"] if not row["ok"])
        first = [next(row for row in batch["results"] if row["worker_index"] == index)
                 for index in range(worker_count)]
        assert max(row["start_ns"] for row in first) < min(row["end_ns"] for row in first)
        assert batch["execution"]["shared_database"]["inode"] == (tmp_path / "data/business.sqlite").stat().st_ino
        assert batch["execution"]["checkpoint"]["arrivals"] == 0
        witnesses = supervisor.evidence()["database_fd_witnesses"]
        assert {row["worker_index"] for row in witnesses if row.get("matching_fds")} == set(range(worker_count))
        assert {row["database"]["inode"] for row in witnesses} == {(tmp_path / "data/business.sqlite").stat().st_ino}
        supervisor.stop_all()
        oracle = inspect_database(tmp_path / "data/business.sqlite", expected_stock={"widget": 12})
        assert oracle["consistent"], oracle["violations"]
        assert {order["order_id"] for order in witnessed} <= {order["order_id"] for order in oracle["orders"]}
        assert len(oracle["orders"]) == len(oracle["ledger"]) == 12
        supervisor.start()
        assert supervisor.call(1, "get_inventory", sku="widget")["reserved"] == 12
    finally:
        supervisor.close()
    assert supervisor.evidence()["cleanup"]["complete"] is True
    assert supervisor.evidence()["pool_cgroup"]["cleanup_complete"] is True
    resource_record = json.loads(supervisor.resource_record_path.read_text())
    assert resource_record["cleanup_complete"] is True
    assert not Path(resource_record["cgroup_path"]).exists()
    assert not Path(resource_record["control_directory"]).exists()


@pytest.mark.parametrize("worker_count", [2, 4])
def test_cross_process_checkpoint_causes_actual_stale_snapshot_loss(tmp_path, worker_count):
    workspace = create_episode_a(tmp_path / "candidate", buggy=True)
    # The local lock fixes this actual code in one process, but does not create
    # a shared Python object among independently launched Worker processes.
    source = workspace / "app/service.py"
    source.write_text(source.read_text() + """
import threading
_worker_lock = threading.RLock()
_original_create = OrderFlow.create_order
def _worker_create(self, *args, **kwargs):
    with _worker_lock:
        return _original_create(self, *args, **kwargs)
OrderFlow.create_order = _worker_create
""")
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts",
                                  worker_count=worker_count).start()
    try:
        supervisor.initialize({"widget": worker_count})
        batch = supervisor.batch(requests(worker_count),
                                 checkpoint={"label": "inventory_read", "timeout_seconds": 0.3})
        assert all(row["ok"] for row in batch["results"])
        assert batch["execution"]["checkpoint"]["arrivals"] == worker_count
        assert batch["execution"]["checkpoint"]["released_by"] == "all_arrived"
        supervisor.stop_all()
        oracle = inspect_database(tmp_path / "data/business.sqlite", expected_stock={"widget": worker_count})
        assert not oracle["consistent"]
        assert len(oracle["orders"]) == len(oracle["ledger"]) == worker_count
        assert oracle["inventory"][0]["reserved"] == 1
        assert any("ledger_matches" in item for item in oracle["violations"])
    finally:
        supervisor.close()


@pytest.mark.parametrize("label", ["before_commit", "transaction_committed", "before_response"])
def test_supervisor_real_pidfd_crash_restart_and_idempotent_retry(tmp_path, label):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts").start()
    try:
        supervisor.initialize({"widget": 5})
        prior = supervisor.evidence()["identity_generations"][0]
        crash = supervisor.crash_call(0, "create_order", label, order_id="retry", sku="widget", quantity=2)
        assert crash["availability"] == "AVAILABLE"
        assert crash["kill"]["mechanism"] == "pidfd_send_signal"
        assert crash["kill"]["worker_pidfd_exited"] is True
        assert crash["kill"]["launcher_exit_code"] == 137
        assert crash["request_outcome"]["response_available"] is False
        assert crash["request_outcome"]["error"]["type"] == "RemoteExecutionError"
        fresh = supervisor.restart(0)
        assert fresh["host_pid"] != prior["host_pid"]
        # Opening the database recovers any genuine hot rollback journal before
        # the host read-only oracle. There is no fabricated post-crash state.
        state = supervisor.call(0, "get_inventory", sku="widget")
        assert state["reserved"] == (0 if label == "before_commit" else 2)
        supervisor.call(1, "create_order", order_id="retry", sku="widget", quantity=2)
        supervisor.call(0, "create_order", order_id="retry", sku="widget", quantity=2)
        supervisor.stop_all()
        oracle = inspect_database(tmp_path / "data/business.sqlite", expected_stock={"widget": 5})
        assert oracle["consistent"], oracle["violations"]
        assert len(oracle["orders"]) == len(oracle["ledger"]) == 1
        assert oracle["inventory"][0]["reserved"] == 2
    finally:
        supervisor.close()
    assert supervisor.evidence()["cleanup"]["complete"]


def test_optional_transaction_observation_absence_is_not_a_business_failure(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts").start()
    try:
        supervisor.initialize({"widget": 5})
        started = time.monotonic()
        result = supervisor.crash_call(0, "get_inventory", "before_commit", sku="widget")
        assert result["availability"] == "UNAVAILABLE"
        assert result["kill"] is None
        assert result["request_outcome"]["ok"] is True
        assert time.monotonic() - started < 1
        assert supervisor.call(0, "create_order", order_id="normal", sku="widget", quantity=1)["status"] == "reserved"
    finally:
        supervisor.close()


def test_open_database_fd_identity_is_trusted_host_observation(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts").start()
    try:
        supervisor.initialize({"widget": 5})
        supervisor.arm_stop(0, "before_commit")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(supervisor.call, 0, "create_order", order_id="fd-proof", sku="widget", quantity=1)
            assert supervisor.wait_stop(0)["availability"] == "AVAILABLE"
            proof = supervisor.database_fds(0)
            assert proof["availability"] == "AVAILABLE"
            assert proof["matching_fds"], proof
            assert {row["inode"] for row in proof["matching_fds"]} == {(tmp_path / "data/business.sqlite").stat().st_ino}
            supervisor.release(0)
            assert future.result(timeout=5)["status"] == "reserved"
    finally:
        supervisor.close()


def test_bounded_gate_permanently_releases_a_serialized_strategy():
    gate = BoundedGate("read", 4, 0.05)
    started = time.monotonic()
    for index in range(4):
        gate.arrive(index, "read")
    assert time.monotonic() - started < 0.2
    assert gate.observation()["released_by"] == "timeout"
    assert gate.observation()["arrivals"] == 4


@pytest.mark.parametrize("checkpoint", [{"label": ""}, {"label": "read", "timeout_seconds": 1},
                                        {"label": "read", "timeout_seconds": float("nan")}])
def test_control_gate_rejects_unbounded_configuration(checkpoint):
    with pytest.raises(ValueError):
        BoundedGate(checkpoint["label"], 2, checkpoint.get("timeout_seconds", 0.3))


@pytest.mark.parametrize("kind", ["regular", "symlink", "public_directory"])
def test_candidate_control_mount_rejects_non_private_socket(tmp_path, kind):
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir(mode=0o700)
    channel = channel_dir / "control.sock"
    with socket.socket(socket.AF_UNIX) as listener:
        if kind == "regular":
            channel.write_text("not a control endpoint")
        else:
            listener.bind(str(channel))
            if kind == "symlink":
                alias = channel_dir / "alias"
                alias.symlink_to(channel)
                channel = alias
            else:
                channel_dir.chmod(0o755)
        with pytest.raises(ValueError):
            sandbox_command(workspace, ["/usr/bin/python3.12", "-c", "pass"], control_socket=channel)


def test_control_protocol_rejects_arbitrary_host_services():
    control = WorkerControl(2)
    try:
        control.prepare_restart(0)
        with socket.socket(socket.AF_UNIX) as connection:
            connection.connect(str(control.paths[0]))
            connection.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\n')
            assert connection.recv(100) == b'{"command":"continue"}\n'
            connection.sendall(b'{"event":"read_host_file","metadata":{"path":"/hidden"}}\n')
            assert connection.recv(100) == b""
        assert control.errors and "Unknown control event" in control.errors[-1]["message"]
    finally:
        control.close()


def test_control_reconnection_requires_explicit_restart_authorization():
    control = WorkerControl(2)
    try:
        control.prepare_restart(0)
        with socket.socket(socket.AF_UNIX) as connection:
            connection.connect(str(control.paths[0]))
            connection.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\n')
            assert connection.recv(100) == b'{"command":"continue"}\n'
        original = control.wait_ready(0)
        with socket.socket(socket.AF_UNIX) as second:
            second.connect(str(control.paths[0]))
            second.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\n')
            # Linux resets a stream closed with unread request bytes. Both EOF
            # and this specific reset mean the denied peer got no handshake.
            try:
                denied_response = second.recv(100)
            except ConnectionResetError as error:
                assert error.errno == 104
                denied_response = b""
            assert denied_response == b""
        assert control.wait_ready(0) == original
        assert any("authorized new generation" in row["message"] for row in control.errors)
        control.prepare_restart(0)
        with socket.socket(socket.AF_UNIX) as third:
            third.connect(str(control.paths[0]))
            third.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\n')
            assert third.recv(100) == b'{"command":"continue"}\n'
        assert control.wait_ready(0)["host_pid"] == os.getpid()
    finally:
        control.close()


def test_selected_control_socket_does_not_expose_parent_files_or_host_network(tmp_path):
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    (workspace / "public.txt").write_text("public marker")
    private = tmp_path / "private"
    private.mkdir()
    canary = private / "hidden-test-canary"
    canary.write_text("synthetic private marker")
    control = WorkerControl(2)
    listener = socket.socket()
    try:
        control.prepare_restart(0)
        sibling = control.directory / "private-control-canary"
        sibling.write_text("synthetic sibling marker")
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            peer, _ = listener.accept()
            peer.close()
        code = """
import json,os,socket
paths = %r
out = []
for path in paths:
    try:
        with open(path): pass
        out.append('READABLE')
    except OSError:
        out.append('DENIED')
try:
    network=socket.create_connection(('127.0.0.1',%d),timeout=0.3)
    connected=True; network.close()
except OSError:
    connected=False
channel=socket.socket(socket.AF_UNIX)
channel.connect('/control.sock')
channel.sendall(b'{"event":"hello","metadata":{"protocol_version":1}}\\n')
handshake=channel.recv(100).decode()
print(json.dumps({'denials':out,'host_connected':connected,'handshake':handshake,
                  'public':open('/workspace/public.txt').read()}))
""" % ([str(canary), "/proc/1/root" + str(canary), str(sibling),
          "/control.sock/../private-control-canary", str(Path(__file__).resolve())], port)
        command = sandbox_command(workspace, [runtime_python(), "-I", "-c", code],
                                  control_socket=control.paths[0])
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["denials"] == ["DENIED"] * 5
        assert result["host_connected"] is False
        assert result["public"] == "public marker"
        assert result["handshake"] == '{"command":"continue"}\n'
        assert "--unshare-net" in command
        assert str(control.directory) not in command
        assert str(control.paths[0]) in command
        assert "/sys/fs/cgroup" not in command
    finally:
        listener.close()
        control.close()


def test_worker_startup_failure_closes_control_and_pool_scope(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    (workspace / "app/service.py").write_text("raise RuntimeError('owned import failure')\n")
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts")
    with pytest.raises(Exception, match="Worker startup failed"):
        supervisor.start()
    evidence = supervisor.evidence()
    assert evidence["cleanup"]["complete"] is True
    assert evidence["cleanup"]["control_directory_removed"] is True
    assert evidence["pool_cgroup"]["cleanup_complete"] is True
    receipt = json.loads(supervisor.resource_record_path.read_text())
    assert receipt["cleanup_complete"] is True
    assert not Path(receipt["cgroup_path"]).exists()


def test_required_pool_resource_gate_does_not_fall_back_to_plain_workers(tmp_path, monkeypatch):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    def unavailable(_limits):
        raise SecurityGateError("owned missing cgroup gate")
    monkeypatch.setattr(CgroupScope, "create", unavailable)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts")
    with pytest.raises(SecurityGateError, match="missing cgroup gate"):
        supervisor.start()
    assert not supervisor.workers
    assert supervisor.control is None
    assert not supervisor.evidence()["identity_generations"]
    assert supervisor.evidence()["pool_cgroup"]["availability"] == "UNAVAILABLE_SECURITY_GATE"


@pytest.mark.parametrize("count", [0, 1, 3, 5, True])
def test_worker_supervisor_rejects_unregistered_topologies(tmp_path, count):
    with pytest.raises(ValueError):
        WorkerSupervisor(tmp_path, tmp_path / "data", tmp_path / "artifacts", worker_count=count)
