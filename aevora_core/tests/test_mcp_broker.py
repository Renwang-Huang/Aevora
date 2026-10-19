"""Real official SDK transport tests using explicitly synthetic service data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

import pytest

from aevora.mcp_broker import MCPBroker, PROTOCOL, _message


SYNTHETIC_SERVER = r'''
import json,sys,time
from aevora.mcp_server import create_server
authority=json.loads(sys.stdin.buffer.readline())
class SyntheticService:
    def resolve_experience(self, context):
        if context.get("observed_failure_mode")=="synthetic-slow":time.sleep(0.5)
        if context.get("observed_failure_mode")=="synthetic-disconnected":
            from aevora.models import GraphUnavailable
            raise GraphUnavailable("Synthetic disconnected fixture, not a live database event")
        return {"status":"SYNTHETIC_TRANSPORT_ONLY","context":context,"run_id":authority["run_id"]}
    def build_evidence_bundle(self, experience_id):
        return {"source":"synthetic_transport_only","experience_id":experience_id}
    def record_decision(self, decision):
        return {"status":"SYNTHETIC_TRANSPORT_ONLY","decision":decision}
create_server(SyntheticService()).run(transport="stdio")
'''


def wait_for(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


@pytest.fixture
def broker_factory(tmp_path):
    brokers = []

    def create(**options):
        folder = tmp_path / ("channel-" + str(len(brokers)))
        folder.mkdir(mode=0o700)
        token = "test_run_" + secrets.token_hex(32)
        instance = MCPBroker(run_id="run-test", public_context={"concurrency_scope": "single_process_threads"},
                             socket_path=folder / "mcp.sock", run_token=token,
                             event_path=folder / "mcp_events.jsonl",
                             server_command=[sys.executable, "-u", "-c", SYNTHETIC_SERVER], **options)
        instance.__enter__()
        brokers.append(instance)
        return instance, token

    yield create
    for instance in brokers:
        instance.close()


def connection(instance, token, *, run_id="run-test", nonce=None):
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    channel.settimeout(4)
    channel.connect(str(instance.socket_path))
    reader = channel.makefile("rb")
    auth = {"protocol": PROTOCOL, "run_id": run_id, "token": token,
            "nonce": nonce or secrets.token_hex(32)}
    channel.sendall(json.dumps(auth).encode() + b"\n")
    answer = json.loads(reader.readline())
    return channel, reader, answer


def send(channel, reader, value):
    channel.sendall(json.dumps(value, separators=(",", ":")).encode() + b"\n")
    return json.loads(reader.readline())


def initialize(channel, reader):
    result = send(channel, reader, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                              "clientInfo": {"name": "Aevora synthetic transport test", "version": "1"}}})
    assert result["result"]["serverInfo"]["name"] == "Aevora"
    channel.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')


def test_official_sdk_initialize_list_and_call_are_real_transport(broker_factory):
    instance, token = broker_factory()
    channel, reader, ack = connection(instance, token)
    try:
        assert ack == {"aevora_transport": "READY"}
        initialize(channel, reader)
        catalog = send(channel, reader, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert {tool["name"] for tool in catalog["result"]["tools"]} == {"resolve_experience", "build_evidence_bundle", "record_decision"}
        answer = send(channel, reader, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                      "params": {"name": "resolve_experience", "arguments": {"task_context": {"worker_count_known": False}}}})
        assert answer["result"]["structuredContent"]["status"] == "SYNTHETIC_TRANSPORT_ONLY"
        assert answer["result"]["structuredContent"]["run_id"] == "run-test"
        assert not answer["result"].get("isError")
    finally:
        reader.close(); channel.close()
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)
    instance.close()
    assert instance.metadata["token_revoked"] is True
    assert instance.metadata["socket_unlinked"] is True
    assert instance.metadata["handler_cleanup_complete"] is True
    assert instance.metadata["server_thread_stopped"] is True
    rows = [json.loads(line) for line in instance.event_path.read_text().splitlines()]
    assert token not in instance.event_path.read_text()
    messages = [row for row in rows if row["category"] == "JSONRPC"]
    assert len(messages) >= 7
    assert {row["direction"] for row in messages} == {"PARTICIPANT_TO_OFFICIAL_SDK", "OFFICIAL_SDK_TO_PARTICIPANT"}
    for row in messages:
        assert hashlib.sha256(row["raw_json"].encode()).hexdigest() == row["archived_message_sha256"]


@pytest.mark.parametrize("token_override,run_id", [("", "run-test"), ("wrong" * 8, "run-test"),
                                                  (None, "foreign-run"), ("非ASCII" * 10, "run-test")])
def test_wrong_or_foreign_authority_rejected_before_sdk_start(broker_factory, token_override, run_id):
    instance, token = broker_factory()
    channel, reader, ack = connection(instance, token if token_override is None else token_override, run_id=run_id)
    assert ack["aevora_transport"] == "REJECTED"
    reader.close(); channel.close()
    assert instance.metadata["sdk_children_started"] == 0


def test_wrong_kernel_peer_uid_rejected(broker_factory):
    instance, token = broker_factory(allowed_peer_uid=os.getuid() + 1)
    channel, reader, ack = connection(instance, token)
    assert ack["aevora_transport"] == "REJECTED"
    reader.close(); channel.close()
    assert instance.metadata["sdk_children_started"] == 0


def test_connection_nonce_replay_rejected(broker_factory):
    instance, token = broker_factory()
    nonce = secrets.token_hex(32)
    first, reader, ack = connection(instance, token, nonce=nonce)
    assert ack["aevora_transport"] == "READY"
    reader.close(); first.close()
    second, reader, ack = connection(instance, token, nonce=nonce)
    assert ack["aevora_transport"] == "REJECTED"
    reader.close(); second.close()
    assert instance.metadata["accepted_connections"] == 1


@pytest.mark.parametrize("rpc_request,expected", [
    ({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "submit_outcome", "arguments": {"verdict": "PASS"}}}, "TOOL_NOT_ALLOWED"),
    ({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "cypher", "arguments": {}}}, "TOOL_NOT_ALLOWED"),
    ({"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "file:///secret"}}, "METHOD_NOT_ALLOWED"),
    ({"jsonrpc": "2.0", "id": 1, "method": "ping"}, "REQUEST_ID_REPLAY"),
    ({"jsonrpc": "2.0", "id": 2, "method": "initialize"}, "DUPLICATE_INITIALIZE"),
    ({"jsonrpc": "2.0", "id": True, "method": "ping"}, "INVALID_REQUEST_ID"),
])
def test_forbidden_methods_tools_and_request_replay_disconnect(broker_factory, rpc_request, expected):
    instance, token = broker_factory()
    channel, reader, ack = connection(instance, token)
    assert ack["aevora_transport"] == "READY"
    initialize(channel, reader)
    channel.sendall(json.dumps(rpc_request).encode() + b"\n")
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get(expected, 0) == 1)
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


def test_active_call_timeout_is_bounded_without_idle_wall_timeout(broker_factory):
    instance, token = broker_factory(request_timeout=2)
    channel, reader, _ = connection(instance, token)
    initialize(channel, reader)
    # Bootstrap imports and an active business call are different phases.
    instance.request_timeout = 0.2
    time.sleep(0.25)
    assert send(channel, reader, {"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    channel.sendall(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": "resolve_experience", "arguments": {"task_context": {"observed_failure_mode": "synthetic-slow"}}}}).encode() + b"\n")
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("MCP_REQUEST_TIMEOUT", 0) == 1)


def test_finite_request_budget_is_enforced(broker_factory):
    instance, token = broker_factory(request_budget=2)
    channel, reader, acknowledgement = connection(instance, token)
    assert acknowledgement == {"aevora_transport": "READY"}
    initialize(channel, reader)
    channel.sendall(b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("REQUEST_BUDGET_EXCEEDED", 0) == 1)


def test_owner_close_reaps_live_sdk_and_revokes_channel(broker_factory):
    instance, token = broker_factory()
    channel, reader, _ = connection(instance, token)
    initialize(channel, reader)
    instance.close()
    assert reader.readline() == b""
    reader.close(); channel.close()
    metadata = instance.metadata
    assert metadata["active_sdk_children"] == metadata["active_connections"] == 0
    assert metadata["sdk_children_started"] == metadata["sdk_children_closed"] == 1
    assert metadata["handler_cleanup_complete"] and metadata["socket_unlinked"] and metadata["token_revoked"]


def test_official_sdk_disconnected_service_returns_explicit_error(broker_factory):
    instance, token = broker_factory()
    channel, reader, _ = connection(instance, token)
    initialize(channel, reader)
    answer = send(channel, reader, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                   "params": {"name": "resolve_experience", "arguments": {
                                       "task_context": {"observed_failure_mode": "synthetic-disconnected"}}}})
    assert answer["result"]["isError"] is True
    assert "AEVORA_GRAPH_UNAVAILABLE" in json.dumps(answer)
    assert "AVAILABLE" not in answer["result"].get("structuredContent", {}).get("status", "")
    reader.close(); channel.close()


def test_official_sdk_discovery_catalogs_are_empty_and_read_routes_stay_denied(broker_factory):
    instance, token = broker_factory()
    channel, reader, _ = connection(instance, token)
    initialize(channel, reader)
    for identifier, (method, field) in enumerate((("resources/list", "resources"),
                                                 ("resources/templates/list", "resourceTemplates"),
                                                 ("prompts/list", "prompts")), 2):
        result = send(channel, reader, {"jsonrpc": "2.0", "id": identifier, "method": method})
        assert result["result"][field] == []
    channel.sendall(b'{"jsonrpc":"2.0","id":5,"method":"resources/read","params":{"uri":"file:///private"}}\n')
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("METHOD_NOT_ALLOWED", 0) == 1)


def test_stdlib_proxy_process_reaches_official_sdk_and_exits_on_stdin_eof(broker_factory):
    instance, token = broker_factory()
    # This synthetic transport test changes the module constant inside its own
    # trusted test process. Production mounts the original immutable fixed path.
    command = [sys.executable, "-u", "-c",
               "import os;from aevora import mcp_proxy as p;p.SOCKET_PATH=os.environ.pop('AEVORA_TEST_SOCKET');raise SystemExit(p.main())"]
    env = {**os.environ, "AEVORA_RUN_TOKEN": token, "AEVORA_RUN_ID": "run-test",
           "AEVORA_TEST_SOCKET": str(instance.socket_path)}
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                        "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                                   "clientInfo": {"name": "Aevora stdlib proxy test", "version": "1"}}}).encode() + b"\n")
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
        assert response["result"]["serverInfo"]["name"] == "Aevora"
        process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        process.stdin.write(b'{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'); process.stdin.flush()
        catalog = json.loads(process.stdout.readline())
        assert len(catalog["result"]["tools"]) == 3
        process.stdin.close()
        assert process.wait(timeout=4) == 0
        assert token.encode() not in process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close()
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


@pytest.mark.parametrize("env_changes", [{"AEVORA_RUN_TOKEN": ""}, {"AEVORA_RUN_ID": "foreign-run"}])
def test_stdlib_proxy_invalid_authority_fails_without_secret_echo(broker_factory, env_changes):
    instance, token = broker_factory()
    command = [sys.executable, "-u", "-c",
               "import os;from aevora import mcp_proxy as p;p.SOCKET_PATH=os.environ.pop('AEVORA_TEST_SOCKET');raise SystemExit(p.main())"]
    env = {**os.environ, "AEVORA_RUN_TOKEN": token, "AEVORA_RUN_ID": "run-test",
           "AEVORA_TEST_SOCKET": str(instance.socket_path), **env_changes}
    result = subprocess.run(command, input=b"", capture_output=True, env=env, timeout=3)
    assert result.returncode == 1
    assert result.stdout == b""
    assert token.encode() not in result.stderr
    assert instance.metadata["sdk_children_started"] == 0


def test_server_start_failure_is_archived_as_failure(broker_factory):
    # Replace the command before any participant can connect; trusted test injection.
    instance, token = broker_factory()
    instance._command = ["/nonexistent/aevora-test-sdk"]
    channel, reader, acknowledgement = connection(instance, token)
    assert acknowledgement == {"aevora_transport": "REJECTED", "reason": "SDK_STARTUP_FAILED"}
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("FILENOTFOUNDERROR", 0) == 1)


def test_hung_sdk_pipe_write_is_bounded_and_child_reaped(broker_factory):
    instance, token = broker_factory(request_timeout=0.2)
    instance._command = [sys.executable, "-u", "-c", "import sys,time;sys.stdin.buffer.readline();time.sleep(100)"]
    channel, reader, acknowledgement = connection(instance, token)
    assert acknowledgement["aevora_transport"] == "READY"
    request_value = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                "clientInfo": {"name": "x" * 200_000, "version": "synthetic-hung-pipe"}}}
    started = time.monotonic()
    channel.sendall(json.dumps(request_value).encode() + b"\n")
    assert reader.readline() == b""
    assert time.monotonic() - started < 3
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("SDK_PIPE_WRITE_TIMEOUT_OR_CANCELLED", 0) == 1)
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


def test_malformed_sdk_stdout_is_archived_as_protocol_failure(broker_factory):
    instance, token = broker_factory()
    instance._command = [sys.executable, "-u", "-c", "import sys,time;sys.stdin.buffer.readline();print('not-json',flush=True);time.sleep(100)"]
    channel, reader, acknowledgement = connection(instance, token)
    assert acknowledgement["aevora_transport"] == "READY"
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("JSONDECODEERROR", 0) == 1)
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


def test_valid_json_malformed_sdk_response_is_classified(broker_factory):
    instance, token = broker_factory()
    instance._command = [sys.executable, "-u", "-c", "import sys,json,time;sys.stdin.buffer.readline();sys.stdin.buffer.readline();print(json.dumps({'jsonrpc':'2.0','id':1,'result':['malformed']}),flush=True);time.sleep(100)"]
    channel, reader, _ = connection(instance, token)
    channel.sendall(b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
    assert reader.readline() == b""
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["rejections"].get("SDK_PROTOCOL_ERROR", 0) == 1)
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


def test_sdk_stderr_is_bounded_redacted_and_preserved(broker_factory):
    instance, token = broker_factory()
    fake_secret = "sk-test_mcp_fixture_abcdefghijklmnop"
    instance._command = [sys.executable, "-u", "-c",
                         "import sys,time;sys.stdin.buffer.readline();sys.stderr.write(" + repr(fake_secret + "\n" + "x" * 70_000) + ");sys.stderr.flush();time.sleep(100)"]
    channel, reader, acknowledgement = connection(instance, token)
    assert acknowledgement["aevora_transport"] == "READY"
    wait_for(lambda: "SDK_STDERR" in instance.event_path.read_text())
    time.sleep(0.05)
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)
    content = instance.event_path.read_text()
    assert fake_secret not in content
    rows = [json.loads(line) for line in content.splitlines()]
    stderr_rows = [row for row in rows if row["category"] == "SDK_STDERR"]
    assert sum(len(row["archived_text"].encode()) for row in stderr_rows) <= 65536
    assert any(row["redaction"] == "APPLIED" for row in stderr_rows)
    assert any(row.get("stderr_truncated") is True for row in rows)


def test_four_connection_limit_does_not_start_a_fifth_sdk(broker_factory):
    instance, token = broker_factory()
    active = [connection(instance, token) for _ in range(4)]
    assert all(answer["aevora_transport"] == "READY" for _, _, answer in active)
    fifth = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    fifth.settimeout(2); fifth.connect(str(instance.socket_path))
    assert fifth.recv(1) == b""
    fifth.close()
    assert instance.metadata["sdk_children_started"] == 4
    wait_for(lambda: instance.metadata["rejections"].get("CONCURRENCY_LIMIT", 0) == 1)
    for channel, reader, _ in active:
        reader.close(); channel.close()
    wait_for(lambda: instance.metadata["active_sdk_children"] == 0)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}\n', b'[]\n', b'{"x":NaN}\n',
                                 b'{}', b'{"x":"' + b'x' * 262_144 + b'"}\n',
                                 json.dumps({"nested": [[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]]]}).encode() + b'\n'])
def test_message_structure_limits(raw):
    with pytest.raises(ValueError):
        _message(raw)


def test_revocation_discard_after_shutdown_preserves_eof_and_denies_peer_writes():
    from aevora.mcp_broker import _discard_revoked_input
    owner, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        payload = b'pending-notification\n'
        peer.sendall(payload)
        discarded, reads, reached = _discard_revoked_input(owner)
        assert discarded == len(payload) and 1 <= reads <= 4 and reached is False
        with pytest.raises(BrokenPipeError):
            peer.sendall(b'no-new-request-after-shutdown\n')
        owner.close()
        assert peer.recv(1024) == b''
    finally:
        owner.close(); peer.close()


def test_revocation_discard_never_parses_or_forwards_untrusted_bytes(monkeypatch):
    import aevora.mcp_broker as module
    def forbidden(*_args, **_kwargs):
        pytest.fail('Revoked input must never be parsed or sent to the SDK')
    monkeypatch.setattr(module, '_message', forbidden)
    monkeypatch.setattr(module.MCPBroker, '_write_input', forbidden)
    class QueuedSocket:
        def __init__(self):
            self.calls = []; self.pending = b'not-json: no privileged outcome action\n'
        def shutdown(self, how): self.calls.append(('shutdown', how))
        def setblocking(self, mode): self.calls.append(('blocking', mode))
        def recv(self, count):
            self.calls.append(('recv', count))
            result, self.pending = self.pending[:count], self.pending[count:]
            return result
    channel = QueuedSocket()
    expected = len(channel.pending)
    assert module._discard_revoked_input(channel) == (expected, 2, False)
    assert channel.calls[:2] == [('shutdown', socket.SHUT_RDWR), ('blocking', False)]


def test_revocation_discard_is_bounded_for_an_adversarial_queue():
    import aevora.mcp_broker as module
    class LargeQueue:
        def __init__(self):
            self.pending = module.MAX_MESSAGE_BYTES + 65_536; self.counts = []
        def shutdown(self, how): assert how == socket.SHUT_RDWR
        def setblocking(self, mode): assert mode is False
        def recv(self, count):
            self.counts.append(count); self.pending -= count; return b'x' * count
    channel = LargeQueue()
    assert module._discard_revoked_input(channel) == (module.MAX_MESSAGE_BYTES, 4, True)
    assert len(channel.counts) == 4 and max(channel.counts) <= 65_536
    assert channel.pending == 65_536


def test_revocation_discard_returns_immediately_on_would_block():
    from aevora.mcp_broker import _discard_revoked_input
    class WouldBlock:
        def __init__(self): self.reads = 0; self.nonblocking = False
        def shutdown(self, how): assert how == socket.SHUT_RDWR
        def setblocking(self, mode): self.nonblocking = mode is False
        def recv(self, count):
            assert self.nonblocking and count <= 65_536
            self.reads += 1
            raise BlockingIOError()
    channel = WouldBlock()
    assert _discard_revoked_input(channel) == (0, 1, False)
    assert channel.reads == 1


def test_discard_only_occurs_after_owner_revocation(broker_factory):
    instance, token = broker_factory()
    channel, reader, _ = connection(instance, token)
    initialize(channel, reader)
    reader.close(); channel.close()
    wait_for(lambda: instance.metadata['active_connections'] == 0)
    assert not instance._stopped.is_set()
    assert instance.metadata['owner_revocation_discarded_bytes'] == 0
    assert instance.metadata['owner_revocation_discard_read_calls'] == 0


def test_owner_close_discards_pending_frames_without_forwarding_and_reaps_resources(broker_factory):
    """Events hold the handler after a real SDK reply, leaving input unread."""
    import threading
    instance, token = broker_factory()
    original_handle = instance._handle
    response_sent, resume = threading.Event(), threading.Event()
    class HeldResponseSocket:
        def __init__(self, actual): self.actual = actual
        def __getattr__(self, name): return getattr(self.actual, name)
        def sendall(self, raw):
            self.actual.sendall(raw)
            value = json.loads(raw)
            if 'protocolVersion' in value.get('result', {}):
                response_sent.set()
                assert resume.wait(4)
    def controlled_handle(actual):
        wrapped = HeldResponseSocket(actual)
        with instance._lock:
            instance._connections.remove(actual)
            instance._connections.add(wrapped)
        return original_handle(wrapped)
    instance._handle = controlled_handle
    channel, reader, _ = connection(instance, token)
    closing = None
    try:
        initialize(channel, reader)
        assert response_sent.wait(2)
        pending_ping = b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        channel.sendall(pending_ping)
        closing = threading.Thread(target=instance.close)
        closing.start()
        assert instance._stopped.wait(2)
        resume.set()
        closing.join(timeout=5)
        assert not closing.is_alive()
        assert reader.readline() == b''
        with pytest.raises(BrokenPipeError): channel.sendall(pending_ping)
        metadata = instance.metadata
        assert metadata['owner_revocation_discarded_bytes'] >= len(pending_ping)
        assert metadata['owner_revocation_discard_read_calls'] <= 4
        assert metadata['owner_revocation_discard_budget_reached'] == 0
        assert metadata['active_sdk_children'] == metadata['active_connections'] == 0
        assert metadata['sdk_children_started'] == metadata['sdk_children_closed'] == 1
        assert metadata['handler_cleanup_complete'] and metadata['socket_unlinked'] and metadata['token_revoked']
        fresh = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with pytest.raises(FileNotFoundError): fresh.connect(str(instance.socket_path))
        finally: fresh.close()
        requests = [json.loads(row['raw_json'])['method']
                    for row in map(json.loads, instance.event_path.read_text().splitlines())
                    if row.get('category') == 'JSONRPC' and row.get('direction') == 'PARTICIPANT_TO_OFFICIAL_SDK']
        assert requests == ['initialize']
        assert token not in instance.event_path.read_text()
    finally:
        resume.set()
        if closing is not None: closing.join(timeout=5)
        reader.close(); channel.close()
