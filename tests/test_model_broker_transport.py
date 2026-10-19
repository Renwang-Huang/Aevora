"""Actual loopback HTTP tests with explicitly synthetic TEST_TRANSPORT identity.

These tests exercise OS sockets, HTTP forwarding and physical filesystem
boundaries. They do not call a model or establish native Agent execution.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from benchmark.participant_sandbox import participant_command
from integrations.model_broker import ModelBroker


_ACCESS = "synthetic-loopback-access-token"
_ACCOUNT = "synthetic-loopback-account"
_REFRESH = "synthetic-loopback-refresh-token"
_IDENTITY = "synthetic-loopback-id-token"
_API_KEY = "synthetic-loopback-api-key"
_SECRET_VALUES = (_ACCESS, _ACCOUNT, _REFRESH, _IDENTITY, _API_KEY)


def _auth(tmp_path):
    directory = tmp_path / "trusted-maintainer"
    directory.mkdir()
    path = directory / "auth.json"
    path.write_text(json.dumps({"auth_mode": "chatgpt", "OPENAI_API_KEY": _API_KEY,
        "tokens": {"access_token": _ACCESS, "account_id": _ACCOUNT,
                   "refresh_token": _REFRESH, "id_token": _IDENTITY}}))
    return path


@contextmanager
def _upstream(*, redirect=False, controlled_stream=False):
    seen = []
    lock = threading.Lock()
    first_sent = threading.Event()
    release_second = threading.Event()
    if not controlled_stream:
        release_second.set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _capture(self, data=None):
            record = {"path": self.path, "method": self.command,
                      "headers": {name.lower(): value for name, value in self.headers.items()}}
            if data is not None:
                record["body"] = json.loads(data)
            with lock:
                seen.append(record)

        def do_GET(self):
            self._capture()
            if redirect:
                payload = ("untrusted upstream error echo: " + _ACCESS).encode()
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/credential-leak")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            payload = b'{"models":[],"test_transport":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            self._capture(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b'data: {"type":"synthetic.first"}\n\n')
            self.wfile.flush()
            first_sent.set()
            if not release_second.wait(timeout=10):
                return
            self.wfile.write(b'data: {"type":"synthetic.second"}\n\n')
            self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{server.server_port}/backend-api/codex",
               "seen": seen, "first_sent": first_sent, "release_second": release_second}
    finally:
        release_second.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _assert_no_secrets(contents):
    encoded = contents if isinstance(contents, str) else json.dumps(contents)
    assert all(secret not in encoded for secret in _SECRET_VALUES)


def test_real_http_transport_injects_only_required_credentials_and_redacts_metadata(tmp_path):
    auth = _auth(tmp_path)
    original = auth.read_bytes()
    with _upstream() as upstream:
        broker = ModelBroker(auth, test_upstream_base_url=upstream["url"])
        with broker:
            request = Request(broker.base_url + "/models?client_version=0.162.1",
                              headers={"Authorization": "Bearer participant-supplied-ignored"})
            with urlopen(request, timeout=5) as response:
                assert response.status == 200
                body = response.read().decode()
                assert json.loads(body)["test_transport"] is True
                _assert_no_secrets(body)
                _assert_no_secrets(dict(response.headers))
            metadata = broker.metadata
            assert metadata["transport"] == "TEST_TRANSPORT"
            assert metadata["upstream_requests"] == 1
            assert metadata["upstream_statuses"] == {"200": 1}
            _assert_no_secrets(metadata)
        assert broker.secret_values == ()
    assert auth.read_bytes() == original
    record = upstream["seen"][0]
    assert record["path"] == "/backend-api/codex/models?client_version=0.162.1"
    assert record["headers"]["authorization"] == "Bearer " + _ACCESS
    assert record["headers"]["chatgpt-account-id"] == _ACCOUNT
    for secret in (_REFRESH, _IDENTITY, _API_KEY):
        assert secret not in json.dumps(record)


def test_real_sse_is_incremental_with_event_controlled_delivery(tmp_path):
    """First event must reach the client before upstream releases the second."""
    with _upstream(controlled_stream=True) as upstream:
        with ModelBroker(_auth(tmp_path), test_upstream_base_url=upstream["url"]) as broker:
            received_first = threading.Event()
            finished = threading.Event()
            captured = {}

            def client():
                try:
                    request = Request(broker.base_url + "/responses",
                        data=b'{"model":"synthetic-transport-model","input":"test","stream":true}')
                    with urlopen(request, timeout=5) as response:
                        captured["headers"] = dict(response.headers)
                        captured["first"] = response.readline()
                        received_first.set()
                        captured["remaining"] = response.read()
                except Exception as error:
                    captured["error"] = type(error).__name__
                finally:
                    finished.set()

            thread = threading.Thread(target=client, daemon=True)
            thread.start()
            try:
                assert upstream["first_sent"].wait(timeout=3)
                assert received_first.wait(timeout=3), captured
                assert captured["first"] == b'data: {"type":"synthetic.first"}\n'
                assert not finished.is_set(), "Complete response arrived before upstream released it"
            finally:
                upstream["release_second"].set()
                thread.join(timeout=5)
            assert finished.is_set()
            assert "error" not in captured
            assert b"synthetic.second" in captured["remaining"]
            assert captured["headers"]["Content-Type"] == "text/event-stream"
            _assert_no_secrets(captured["first"].decode() + captured["remaining"].decode())
            _assert_no_secrets(captured["headers"])
            assert broker.metadata["errors"] == []
    record = upstream["seen"][0]
    assert record["method"] == "POST"
    assert record["path"] == "/backend-api/codex/responses"
    assert record["body"]["store"] is False


def test_real_http_redirect_does_not_forward_credentials_or_expose_error_echo(tmp_path):
    with _upstream(redirect=True) as upstream:
        with ModelBroker(_auth(tmp_path), test_upstream_base_url=upstream["url"]) as broker:
            with pytest.raises(HTTPError) as result:
                urlopen(broker.base_url + "/models", timeout=5)
            assert result.value.code == 502
            _assert_no_secrets(result.value.read().decode())
            assert "Location" not in result.value.headers
            assert broker.metadata["upstream_statuses"] == {"302": 1}
    assert len(upstream["seen"]) == 1
    assert upstream["seen"][0]["path"] == "/backend-api/codex/models"


@pytest.mark.parametrize("route,method,status", [
    ("/auth", "GET", 404), ("/credentials", "GET", 404),
    ("/../../trusted-maintainer/auth.json", "GET", 404),
    ("/models?target=http://127.0.0.1/private", "GET", 400),
    ("/responses?client_version=0.162.1", "POST", 400),
    ("/models", "POST", 405), ("/responses", "GET", 405),
])
def test_real_http_forbidden_routes_cannot_reach_authenticated_upstream(tmp_path, route, method, status):
    with _upstream() as upstream:
        with ModelBroker(_auth(tmp_path), test_upstream_base_url=upstream["url"]) as broker:
            request = Request(broker.base_url + route, data=b"{}" if method == "POST" else None, method=method)
            with pytest.raises(HTTPError) as result:
                urlopen(request, timeout=5)
            assert result.value.code == status
            _assert_no_secrets(result.value.read().decode())
            assert upstream["seen"] == []
            assert broker.metadata["upstream_requests"] == 0


def test_actual_participant_boundary_can_use_broker_without_reading_identity_source(tmp_path):
    """Real bwrap + HTTP probe, using Python as a boundary probe executable."""
    auth = _auth(tmp_path)
    workspace = tmp_path / "public-participant"
    state = tmp_path / "new-codex-state"
    workspace.mkdir()
    state.mkdir()
    (workspace / "public.txt").write_text("public canary")
    with _upstream() as upstream:
        with ModelBroker(auth, test_upstream_base_url=upstream["url"]) as broker:
            probe_input = json.dumps({"url": broker.base_url + "/models",
                "paths": [str(auth), "/proc/1/root" + str(auth), "/maintainer/auth.json",
                          "/home/private-user/.codex/auth.json", "/codex-state/auth.json"]})
            program = """
import json, pathlib, sys, urllib.request
request = json.loads(sys.argv[1])
result = {'identity': {}}
with urllib.request.urlopen(request['url'], timeout=5) as response:
    result['models'] = json.loads(response.read())
for path in request['paths']:
    try:
        pathlib.Path(path).read_bytes()
        result['identity'][path] = 'READABLE'
    except OSError:
        result['identity'][path] = 'DENIED'
result['public'] = pathlib.Path('/workspace/public.txt').read_text()
print(json.dumps(result))
"""
            command = participant_command(workspace, state, Path(shutil.which("git")),
                ["/usr/bin/python3.12", "-c", program, probe_input])
            completed = subprocess.run(command, text=True, capture_output=True, timeout=15)
            assert completed.returncode == 0, completed.stderr
            result = json.loads(completed.stdout)
            assert result["models"]["test_transport"] is True
            assert result["public"] == "public canary"
            assert all(status == "DENIED" for status in result["identity"].values())
            _assert_no_secrets(completed.stdout + completed.stderr)
            assert broker.metadata["upstream_requests"] == 1
    assert not (workspace / "auth.json").exists()
    assert not (state / "auth.json").exists()
