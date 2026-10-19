"""Phase 3.5 bounded, owned probes; no model requests or real secret reads."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import pytest

from benchmark.participant_sandbox import participant_command
from benchmark.resources import (CANDIDATE_LIMITS, PARTICIPANT_LIMITS, CgroupScope,
    ResourceLimits, ResourceWatchdog, SecurityGateError)
from benchmark.sandbox import runtime_python, sandbox_command


def _participant(tmp_path):
    workspace, state = tmp_path / "public", tmp_path / "state"
    workspace.mkdir()
    state.mkdir()
    return workspace, state, Path(shutil.which("git"))


def _run(command, timeout=15):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


@pytest.mark.parametrize("layer", ["outer", "candidate"])
def test_strict_sandboxes_deny_21_private_file_paths(tmp_path, layer):
    workspace, state, binary = _participant(tmp_path)
    (workspace / "visible.txt").write_text("public")
    private = tmp_path / "private"
    private.mkdir()
    labels = ["hidden_tests", "reference_patch", "private_manifest", "host_source",
              "other_run", "host_auth", "host_home", "maintainer_archive",
              "evidence", "seed_experience"]
    paths = []
    for label in labels:
        canary = private / label
        canary.write_text("synthetic private canary")
        paths.extend([str(canary), "/proc/1/root" + str(canary)])
    paths.append(str(workspace / ".." / "private" / "host_source"))
    code = """
import json,os
paths = json.loads(%r)
results=[]
for p in paths:
    try:
        fd=os.open(p,os.O_RDONLY); os.close(fd); results.append('READABLE')
    except OSError: results.append('DENIED')
print(json.dumps({'probes':results,'public':open('/workspace/visible.txt').read()}))
""" % json.dumps(paths)
    if layer == "outer":
        command = participant_command(workspace, state, binary,
            ["/usr/bin/python3.12", "-c", code], network_isolated=True)
    else:
        command = sandbox_command(workspace, [runtime_python(), "-c", code])
    result = _run(command)
    assert result.returncode == 0, result.stderr
    observation = json.loads(result.stdout)
    assert observation["probes"] == ["DENIED"] * 21
    assert observation["public"] == "public"
    assert "--unshare-net" in command
    assert "/sys/fs/cgroup" not in command


@pytest.mark.parametrize("layer", ["outer", "candidate"])
def test_strict_sandboxes_cannot_connect_owned_host_listener(tmp_path, layer):
    workspace, state, binary = _participant(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        # A positive host-side control makes absence of a listener distinguishable.
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            accepted, _ = listener.accept()
            accepted.close()
        code = f"""
import socket,json
try:
    s=socket.create_connection(('127.0.0.1',{port}),timeout=0.5);s.close();r={{'connected':True}}
except OSError as e:r={{'connected':False,'errno':e.errno,'kind':type(e).__name__}}
print(json.dumps(r))
"""
        command = (participant_command(workspace, state, binary,
            ["/usr/bin/python3.12", "-c", code], network_isolated=True)
            if layer == "outer" else sandbox_command(workspace, [runtime_python(), "-c", code]))
        result = _run(command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["connected"] is False


def test_outer_only_exposes_selected_unix_model_channel(tmp_path):
    workspace, state, binary = _participant(tmp_path)
    # AF_UNIX has a 108-byte kernel path limit; pytest basetemp may be longer.
    # This is a dedicated owned endpoint, not a directory mounted wholesale.
    with tempfile.TemporaryDirectory(prefix="of-channel-") as endpoint, socket.socket(socket.AF_UNIX) as listener:
        channel = Path(endpoint) / "model.sock"
        listener.bind(str(channel))
        listener.listen(1)
        os.chmod(channel, 0o600)
        received = []
        def serve():
            connection, _ = listener.accept()
            with connection:
                received.append(connection.recv(32))
                connection.sendall(b"model-channel-test")
        server = threading.Thread(target=serve, daemon=True)
        server.start()
        code = "import socket; s=socket.socket(socket.AF_UNIX);s.connect('/model-channel/broker.sock');s.sendall(b'owned-probe');print(s.recv(32).decode());s.close()"
        command = participant_command(workspace, state, binary,
            ["/usr/bin/python3.12", "-c", code], broker_socket=channel)
        result = _run(command)
        server.join(timeout=2)
    assert "--unshare-net" in command
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "model-channel-test"
    assert received == [b"owned-probe"]
    assert str(tmp_path) not in command  # Only workspace/state/socket paths are mounted, no parent.


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_non_socket_model_channel_fails_closed(tmp_path, kind):
    workspace, state, binary = _participant(tmp_path)
    bad = tmp_path / "not-socket"
    bad.write_text("not a channel")
    if kind == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(bad)
        bad = alias
    with pytest.raises(ValueError, match="Unix-domain socket"):
        participant_command(workspace, state, binary, ["/tools/git", "--version"], broker_socket=bad)


@pytest.mark.parametrize("setting,value", [
    ("wall_seconds", 0), ("wall_seconds", float("nan")), ("wall_seconds", 7201),
    ("cpu_seconds", True), ("cpu_seconds", -1), ("max_tasks", 2049),
    ("open_files", 0), ("poll_seconds", 2), ("memory_bytes", 100 * 1024**3),
])
def test_resource_limits_reject_unbounded_or_invalid_budgets(setting, value):
    with pytest.raises(ValueError):
        replace(PARTICIPANT_LIMITS, **{setting: value})


def test_candidate_rlimits_and_200_thread_capacity_are_real(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    code = """
import json,resource,threading
barrier=threading.Barrier(201)
ids=[]
def f():
    ids.append(threading.get_native_id());barrier.wait(timeout=10)
threads=[threading.Thread(target=f) for _ in range(200)]
for t in threads:t.start()
barrier.wait(timeout=10)
for t in threads:t.join()
print(json.dumps({'threads':len(set(ids)),'as':resource.getrlimit(resource.RLIMIT_AS),
'cpu':resource.getrlimit(resource.RLIMIT_CPU),'files':resource.getrlimit(resource.RLIMIT_NOFILE)}))
"""
    result = _run(sandbox_command(workspace, [runtime_python(), "-c", code]), timeout=20)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["threads"] == 200
    assert value["as"] == [CANDIDATE_LIMITS.address_space_bytes] * 2
    assert value["cpu"] == [CANDIDATE_LIMITS.cpu_seconds] * 2
    assert value["files"] == [CANDIDATE_LIMITS.open_files] * 2


def test_candidate_wall_budget_kills_and_reaps_child(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    limits = replace(CANDIDATE_LIMITS, wall_seconds=0.3, poll_seconds=0.01)
    result = _run(sandbox_command(workspace,
        [runtime_python(), "-c", "import time;time.sleep(60)"], resources=limits))
    assert result.returncode == 124
    observation = json.loads(result.stderr.strip().splitlines()[-1])
    assert observation["violation"]["resource"] == "wall_seconds"
    assert observation["remaining_pids"] == []


def test_candidate_file_budget_is_enforced(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    limits = replace(CANDIDATE_LIMITS, file_bytes=4096)
    code = "import os; f=open('/workspace/output','wb');f.write(b'x'*8192);f.flush()"
    result = _run(sandbox_command(workspace, [runtime_python(), "-c", code],
                                 writable=True, resources=limits))
    assert result.returncode != 0
    assert (workspace / "output").stat().st_size <= 4096


@pytest.mark.parametrize("budget", ["bytes", "files", "directories"])
def test_candidate_aggregate_output_budget_kills_and_reaps(tmp_path, budget):
    workspace, _, _ = _participant(tmp_path)
    limits = replace(CANDIDATE_LIMITS, output_bytes=16384, max_files=8,
                     poll_seconds=0.01)
    program = ("from pathlib import Path;import time;"
               + ("[Path('/workspace/'+str(i)).write_bytes(b'x'*8192) for i in range(4)];"
                  if budget == "bytes" else
                  "[Path('/workspace/'+str(i)).mkdir() for i in range(20)];"
                  if budget == "directories" else
                  "[Path('/workspace/'+str(i)).write_text('x') for i in range(20)];")
               + "time.sleep(60)")
    result = _run(sandbox_command(workspace, [runtime_python(), "-c", program],
                                 writable=True, resources=limits))
    assert result.returncode == 137
    observation = json.loads(result.stderr.strip().splitlines()[-1])
    assert observation["violation"]["resource"] == ("output_bytes" if budget == "bytes" else "files")
    assert observation["remaining_pids"] == []


def test_candidate_cannot_disable_output_monitor_with_permissions(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    code = "import os,time; os.chmod('/workspace',0);time.sleep(60)"
    try:
        result = _run(sandbox_command(workspace, [runtime_python(), "-c", code], writable=True))
    finally:
        workspace.chmod(0o700)
    assert result.returncode == 137
    observation = json.loads(result.stderr.strip().splitlines()[-1])
    assert observation["violation"]["kind"] == "RESOURCE_MONITOR_FAILED"
    assert observation["remaining_pids"] == []


def test_candidate_cpu_budget_is_enforced(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    limits = replace(CANDIDATE_LIMITS, cpu_seconds=1, wall_seconds=10)
    result = _run(sandbox_command(workspace,
        [runtime_python(), "-c", "while True: pass"], resources=limits))
    assert result.returncode != 0
    assert "wall_seconds" not in result.stderr


def test_candidate_cannot_modify_resource_launcher(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    code = "open('/resource_launcher.py','w').write('unbounded')"
    result = _run(sandbox_command(workspace, [runtime_python(), "-c", code]))
    assert result.returncode != 0
    assert "Read-only file system" in result.stderr


def test_candidate_memory_budget_is_enforced(tmp_path):
    workspace, _, _ = _participant(tmp_path)
    limits = replace(CANDIDATE_LIMITS, address_space_bytes=128 * 1024**2,
                     memory_bytes=96 * 1024**2)
    code = "blocks=[bytearray(32*1024**2) for _ in range(10)]"
    result = _run(sandbox_command(workspace, [runtime_python(), "-c", code], resources=limits))
    assert result.returncode != 0
    assert "MemoryError" in result.stderr or "RESOURCE_LIMIT_EXCEEDED" in result.stderr


def test_watchdog_aggregates_tasks_and_cleans_up(tmp_path):
    program = """
import threading,time
threads=[threading.Thread(target=lambda:time.sleep(60)) for _ in range(6)]
for t in threads:t.start()
time.sleep(60)
"""
    process = subprocess.Popen([sys.executable, "-c", program], start_new_session=True)
    watchdog = ResourceWatchdog(process.pid, replace(PARTICIPANT_LIMITS,
        max_tasks=3, poll_seconds=0.01)).start()
    try:
        process.wait(timeout=5)
    finally:
        observation = watchdog.close()
        if process.poll() is None:
            process.kill(); process.wait()
    assert observation["violation"]["resource"] == "tasks"
    assert observation["peak_tasks"] > 3
    assert observation["remaining_pids"] == []


def test_missing_cgroup_delegation_fails_closed(tmp_path):
    with pytest.raises(SecurityGateError, match="BLOCKED_SECURITY_GATE"):
        CgroupScope.create(PARTICIPANT_LIMITS, parent=tmp_path)
    assert list(tmp_path.iterdir()) == []
