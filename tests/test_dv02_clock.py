"""Real sockets and immutable command boundaries; no task outcome is simulated."""
import json
from pathlib import Path
import socket
import pytest

from evaluator.dv02_clock import ClockAuthority, extend_candidate_command


def query(clock, request=b"NOW\n"):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(clock.path))
        client.sendall(request)
        return json.loads(client.recv(1024))


def test_real_query_clock_monotonic_owner_and_cleanup():
    clock = ClockAuthority(100).start()
    try:
        assert query(clock) == {"tick": "100"}
        assert clock.advance(3) == 103
        assert query(clock) == {"tick": "103"}
        assert clock.advance_to(2**80) == 2**80
        assert query(clock) == {"tick": str(2**80)}
        with pytest.raises(ValueError):
            clock.advance_to(99)
        events = clock.evidence()["events"]
        assert [row["sequence"] for row in events] == list(range(1, len(events) + 1))
        peers = [row["peer"] for row in events if row["event"] == "clock.now"]
        assert len(peers) == 3 and all(peer["host_pid"] > 0 for peer in peers)
    finally:
        evidence = clock.close()
    assert evidence["cleanup"]["complete"]
    assert not clock.path.exists() and not clock.directory.exists()
    assert clock.close()["cleanup"]["complete"]
    with pytest.raises(RuntimeError):
        clock.start()


@pytest.mark.parametrize("payload", [b"ADVANCE 10\n", b"SET 0\n", b"SQL SELECT 1\n",
    b"READ /etc/passwd\n", b"GET https://example.org\n", b"NOW\nSET 1\n", b"x" * 65])
def test_real_socket_denies_every_non_query_operation(payload):
    with ClockAuthority(100) as clock:
        assert query(clock, payload) == {"error": "CLOCK_QUERY_ONLY"}
        assert query(clock) == {"tick": "100"}
        denied = [row for row in clock.evidence()["events"] if row["event"] == "clock.request_denied"]
        assert len(denied) == 1 and denied[0]["request_length"] == len(payload)


@pytest.mark.parametrize("value", [True, False, -1, 1.0, "1", None])
def test_clock_rejects_non_integer_and_negative_ticks(value):
    with pytest.raises(ValueError):
        ClockAuthority(value)


def command():
    worker = Path(__file__).resolve().parents[1] / "evaluator/worker.py"
    return ["bwrap", "--unshare-all", "--cap-drop", "ALL", "--ro-bind", str(worker),
            "/worker.py", "--clearenv", "--setenv", "HOME", "/workspace", "--", "/usr/bin/python3", "/worker.py"]


def test_extension_preserves_namespace_and_clears_before_clock_environment():
    with ClockAuthority() as clock:
        original = command()
        result = extend_candidate_command(original, clock.path)
        assert original == command()
        assert result[:4] == original[:4]
        assert result[result.index("--"):] == original[original.index("--"):]
        assert result.index("ORDERFLOW_CLOCK_QUERY") > result.index("--clearenv")
        assert result.count(str(clock.path)) == 1
        assert str(clock.directory) not in result
        mounts = [result[index + 2] for index in range(len(result) - 2) if result[index] == "--ro-bind"]
        assert mounts == ["/worker_base.py", "/clock-query.sock", "/worker.py"]


def test_extension_rejects_regular_file_symlink_and_extra_clearenv(tmp_path):
    ordinary = tmp_path / "clock"
    ordinary.write_text("not a socket")
    with pytest.raises(ValueError):
        extend_candidate_command(command(), ordinary)
    with ClockAuthority() as clock:
        link = tmp_path / "linked"
        link.symlink_to(clock.path)
        with pytest.raises(ValueError):
            extend_candidate_command(command(), link)
        with pytest.raises(ValueError):
            extend_candidate_command(command() + ["--clearenv"], clock.path)


def test_extension_rejects_different_worker_source(tmp_path):
    fake = tmp_path / "worker.py"
    fake.write_text("raise RuntimeError('not the trusted generic worker')")
    with ClockAuthority() as clock:
        wrong = command()
        wrong[wrong.index("--ro-bind") + 1] = str(fake)
        with pytest.raises(ValueError):
            extend_candidate_command(wrong, clock.path)
