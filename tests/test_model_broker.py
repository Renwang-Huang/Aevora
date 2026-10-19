"""Synthetic in-memory HTTP contracts, not real model-service evidence.

Socket listeners are forbidden by the current tool environment. Protocol unit
tests replace only transport objects; a separate real listener probe verifies
that a denied startup is safely classified rather than silently bypassed.
"""
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

import integrations.model_broker as module
from integrations.model_broker import BrokerError, ModelBroker


def _auth(tmp_path: Path):
    source = tmp_path / "synthetic-auth.json"
    source.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {
        "access_token": "synthetic-test-access-token", "account_id": "synthetic-test-account",
        "refresh_token": "synthetic-test-refresh-not-forwarded", "id_token": "synthetic-test-id-not-forwarded"}}))
    return source


class _SyntheticResponse(BytesIO):
    status = 200

    def __init__(self, data, content_type):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}


@pytest.fixture
def memory_transport(monkeypatch):
    state = SimpleNamespace(handler=None, requests=[], failure=None, server_closed=False)

    class Server:
        server_port = 32123

        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            state.handler = handler

        def serve_forever(self):
            pass

        def shutdown(self):
            pass

        def server_close(self):
            state.server_closed = True

    class Opener:
        def open(self, request, timeout):
            assert timeout > 0
            state.requests.append(request)
            if state.failure:
                raise state.failure
            if request.method == "POST":
                return _SyntheticResponse(b'data: {"type":"synthetic.event"}\n\n', "text/event-stream")
            return _SyntheticResponse(b'{"models": []}', "application/json")

    def opener_factory(*handlers):
        assert any(isinstance(item, module._NoRedirect) for item in handlers)
        assert any(isinstance(item, module.ProxyHandler) and item.proxies == {} for item in handlers)
        return Opener()

    monkeypatch.setattr(module, "ThreadingHTTPServer", Server)
    monkeypatch.setattr(module, "build_opener", opener_factory)
    return state


def _request(state, route, *, method="GET", body=None, headers=None):
    handler = state.handler.__new__(state.handler)
    handler.command = method
    handler.path = route
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"{method} {route} HTTP/1.1"
    handler.close_connection = True
    handler.headers = Message()
    for name, value in (headers or {}).items():
        handler.headers[name] = value
    if body is not None and "Content-Length" not in handler.headers:
        handler.headers["Content-Length"] = str(len(body))
    handler.rfile = BytesIO(body or b"")
    handler.wfile = BytesIO()
    handler.connection = SimpleNamespace(settimeout=lambda _: None)
    getattr(handler, "do_" + method)()
    header_block, response_body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
    status = int(header_block.split(b" ", 2)[1])
    return status, header_block.decode(), response_body


def test_broker_fixed_routes_inject_only_required_host_credentials(tmp_path, memory_transport):
    broker = ModelBroker(_auth(tmp_path), test_upstream_base_url="http://127.0.0.1:32124/backend-api/codex")
    with broker:
        status, _, data = _request(memory_transport, "/v1/models?client_version=0.162.1")
        assert status == 200
        assert json.loads(data) == {"models": []}
        status, headers, data = _request(memory_transport, "/v1/responses", method="POST",
            body=b'{"model":"synthetic-model","input":"contract test"}',
            headers={"Authorization": "Bearer participant-input-must-be-ignored"})
        assert status == 200
        assert "text/event-stream" in headers
        assert b"synthetic.event" in data
        assert broker.secret_values == ("synthetic-test-access-token", "synthetic-test-account")
        metadata = broker.metadata
        assert metadata["transport"] == "TEST_TRANSPORT"
        assert metadata["upstream_requests"] == 2
        assert metadata["upstream_statuses"] == {"200": 2}
        assert "synthetic-test-access-token" not in json.dumps(metadata)
        assert "synthetic-test-refresh" not in json.dumps(metadata)
    assert broker.secret_values == ()
    assert broker.metadata["ended_at"] is not None
    assert memory_transport.server_closed
    with pytest.raises(BrokerError, match="not running"):
        _ = broker.base_url
    seen = memory_transport.requests
    assert seen[0].full_url == "http://127.0.0.1:32124/backend-api/codex/models?client_version=0.162.1"
    assert seen[1].full_url == "http://127.0.0.1:32124/backend-api/codex/responses"
    assert json.loads(seen[1].data)["store"] is False
    for request in seen:
        assert request.headers["Authorization"] == "Bearer synthetic-test-access-token"
        assert request.headers["Chatgpt-account-id"] == "synthetic-test-account"
        assert "refresh" not in json.dumps(request.headers)


@pytest.mark.parametrize("route,method,data,status", [
    ("/private", "GET", None, 404),
    ("/v1/models", "POST", b"{}", 405),
    ("/v1/responses", "GET", None, 405),
    ("/v1/responses?target=http://127.0.0.1/secret", "POST", b"{}", 400),
    ("/v1/models?token=secret", "GET", None, 400),
    ("/v1/responses", "POST", b'{"store":true}', 400),
    ("/v1/responses", "POST", b"[]", 400),
    ("/v1/responses", "POST", b"invalid-json", 400),
    ("/v1/responses", "PUT", b"{}", 405),
    ("http://other-host/v1/models", "GET", None, 400),
])
def test_broker_rejects_other_routes_methods_and_invalid_bodies(tmp_path, memory_transport, route, method, data, status):
    with ModelBroker(_auth(tmp_path)) as broker:
        actual, _, _ = _request(memory_transport, route, method=method, body=data)
        assert actual == status
        assert memory_transport.requests == []
        assert broker.metadata["upstream_requests"] == 0


def test_redirect_is_not_followed_and_upstream_body_is_not_exposed(tmp_path, memory_transport):
    memory_transport.failure = HTTPError("http://127.0.0.1/", 302, "Redirect", {"Location": "http://other-host/"},
                                        BytesIO(b"synthetic-test-access-token"))
    with ModelBroker(_auth(tmp_path)) as broker:
        status, _, data = _request(memory_transport, "/v1/models")
        assert status == 502
        assert b"UPSTREAM_HTTP_ERROR" in data
        assert b"synthetic-test" not in data
        assert len(memory_transport.requests) == 1
        assert broker.metadata["upstream_statuses"] == {"302": 1}
    assert module._NoRedirect().redirect_request(None, None, 302, "Redirect", {}, "https://other-host/") is None


def test_connection_failure_is_classified_without_fallback_or_credentials(tmp_path, memory_transport):
    memory_transport.failure = URLError("synthetic connection refusal")
    with ModelBroker(_auth(tmp_path), request_timeout=1) as broker:
        status, _, data = _request(memory_transport, "/v1/models")
        assert status == 502
        assert json.loads(data)["error"]["type"] == "UPSTREAM_CONNECTION_ERROR"
        assert broker.metadata["errors"][-1]["category"] == "UPSTREAM_CONNECTION_ERROR"


def test_real_listener_probe_denial_is_safe_or_actual_start_is_clean(tmp_path):
    """Actual OS socket capability probe; no model is called and no skip used."""
    broker = ModelBroker(_auth(tmp_path), request_timeout=1)
    try:
        broker.__enter__()
    except BrokerError as error:
        assert "listener is unavailable" in str(error)
        assert broker.metadata["errors"][-1]["category"] == "BROKER_LISTEN_UNAVAILABLE"
        assert broker.metadata["started_at"] is None
        assert broker.secret_values == ()
    else:
        assert broker.base_url.startswith("http://127.0.0.1:")
        broker.__exit__(None, None, None)
        assert broker.secret_values == ()


def test_forced_listener_failure_is_classified_and_clears_secrets(tmp_path, monkeypatch):
    def denied(*_):
        raise PermissionError("synthetic bind denial")
    monkeypatch.setattr(module, "ThreadingHTTPServer", denied)
    broker = ModelBroker(_auth(tmp_path))
    with pytest.raises(BrokerError, match="refusing credential exposure"):
        broker.__enter__()
    assert broker.secret_values == ()
    assert broker.metadata["errors"][-1]["category"] == "BROKER_LISTEN_UNAVAILABLE"


@pytest.mark.parametrize("contents", ["not json", "{}", '{"auth_mode":"apikey"}',
    '{"auth_mode":"chatgpt","tokens":{"access_token":"unsafe\\nheader","account_id":"synthetic"}}'])
def test_invalid_auth_is_safe_and_never_starts_broker(tmp_path, contents):
    source = tmp_path / "auth.json"
    source.write_text(contents)
    broker = ModelBroker(source)
    with pytest.raises(BrokerError, match="authentication is unavailable"):
        broker.__enter__()
    assert broker.secret_values == ()
    assert broker.metadata["started_at"] is None


@pytest.mark.parametrize("url", ["https://example.com", "http://192.0.2.1", "http://user:pass@127.0.0.1", "http://127.0.0.1/?secret=x"])
def test_test_transport_cannot_become_arbitrary_authenticated_proxy(tmp_path, url):
    with pytest.raises(ValueError, match="loopback"):
        ModelBroker(_auth(tmp_path), test_upstream_base_url=url)
