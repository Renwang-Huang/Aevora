"""Real OS-socket transport contracts using exclusively synthetic credentials.

No model call, true API secret, inherited identity, or auth file is used here.
Successful tests establish bounded UDS/HTTP behavior, not gateway compatibility.
"""
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
from urllib.request import HTTPSHandler, ProxyHandler

import pytest

import integrations.gateway_broker as module
from integrations.gateway_broker import SecureModelBroker
from integrations.model_broker import BrokerError
from integrations.providers import ProviderConfig, gateway_provider


_KEY = "synthetic-gateway-upstream-key-not-a-real-secret"
_TOKEN_A = "synthetic-run-a-authorized-token-0123456789"
_TOKEN_B = "synthetic-run-b-authorized-token-0123456789"


class _UnixHTTPConnection(HTTPConnection):
    def __init__(self, path, timeout=4):
        super().__init__("localhost", timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def _payload(**extra):
    return {"model": "gpt-5.6-terra", "reasoning": {"effort": "max"},
            "input": "synthetic public task", **extra}


def _request(broker, *, method="GET", route="/v1/models", body=None,
             token=_TOKEN_A, headers=None):
    connection = _UnixHTTPConnection(broker.socket_path)
    request_headers = {}
    if token is not None:
        request_headers["Authorization"] = "Bearer " + token
    if isinstance(body, dict):
        body = json.dumps(body).encode()
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    connection.request(method, route, body=body, headers=request_headers)
    response = connection.getresponse()
    result = (response.status, dict(response.headers), response.read())
    connection.close()
    return result


def _response(**extra):
    return {"id": "resp_synthetic", "object": "response", "status": "completed",
            "model": "gpt-5.6-terra", "reasoning": {"effort": "max"},
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "synthetic response"}]}],
            "usage": {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10,
                      "output_tokens_details": {"reasoning_tokens": 2}}, **extra}


def _sse(event):
    return b"data: " + json.dumps(event).encode() + b"\n\n"


@contextmanager
def _upstream(*, status=200, stream=False, incomplete=False, invalid_completion=False,
              controlled=False, timeout=False, output=None, redirect=False,
              declared_length=None, content_type=None, tool_round=False):
    seen = []
    lock = threading.Lock()
    first_sent = threading.Event()
    release = threading.Event()
    if not controlled:
        release.set()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *_):
            pass

        def handle_request(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.loads(raw) if raw else None
            with lock:
                seen.append({"path": self.path, "method": self.command, "body": body,
                             "headers": {key.lower(): value for key, value in self.headers.items()}})
            self.send_response(302 if redirect else status)
            self.send_header("x-request-id", "req_synthetic_123")
            if redirect:
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leak")
            if status != 200 or redirect:
                data = (_KEY + " echoed error body " + _TOKEN_A).encode()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            is_models = self.command == "GET"
            if not is_models and stream:
                self.send_header("Content-Type", content_type or "text/event-stream")
                if declared_length:
                    self.send_header("Content-Length", str(declared_length))
                self.end_headers()
                try:
                    first = _sse({"type": "response.created", "response": _response(status="in_progress")})
                    self.wfile.write(first)
                    self.wfile.flush()
                    first_sent.set()
                    if timeout:
                        release.wait(1)
                        return
                    if not release.wait(4):
                        return
                    if not incomplete:
                        response = _response(status="in_progress" if invalid_completion else "completed")
                        self.wfile.write(_sse({"type": "response.completed", "response": response}))
                        self.wfile.flush()
                    return
                except (BrokenPipeError, ConnectionResetError):
                    return
            if timeout:
                first_sent.set()
                release.wait(1)
            if is_models:
                data = b'{"object":"list","data":[{"id":"gpt-5.6-terra","object":"model"}]}'
            elif output is not None:
                data = output
            elif tool_round and body.get("tools"):
                data = json.dumps(_response(output=[{"type": "function_call", "name": "public_tool",
                    "call_id": "call_synthetic", "arguments": '{"value":1}'}])).encode()
            else:
                data = json.dumps(_response()).encode()
            self.send_header("Content-Type", content_type or "application/json")
            self.send_header("Content-Length", str(declared_length or len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = do_POST = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{server.server_port}/v1", "seen": seen,
               "first_sent": first_sent, "release": release}
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)


@contextmanager
def _broker(upstream=None, *, token=_TOKEN_A, run_id="synthetic-run-a", **options):
    # A short, owner-only directory also meets Linux's 108-byte UDS path limit.
    with tempfile.TemporaryDirectory(prefix="ofb-") as directory:
        root = Path(directory)
        secret = root / "synthetic-secret"
        secret.write_text(_KEY + "\n")
        secret.chmod(0o600)
        config = ProviderConfig(base_url="https://api.renwang-huang.top/v1")
        broker = SecureModelBroker(config, secret, run_id=run_id, socket_path=root / "model.sock",
            run_token=token, test_upstream_base_url=upstream["url"] if upstream else None, **options)
        with broker:
            yield broker


def _wait_records(broker, count=1):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        metadata = broker.metadata
        if len(metadata["request_records"]) >= count:
            return metadata
        time.sleep(0.005)
    raise AssertionError("Broker request did not finish")


def _no_secrets(value):
    data = json.dumps(value) if not isinstance(value, str) else value
    assert all(secret not in data for secret in (_KEY, _TOKEN_A, _TOKEN_B))


def test_provider_is_explicit_nonsecret_and_does_not_guess_v1():
    provider = gateway_provider()
    assert provider.base_url == "https://api.renwang-huang.top"
    assert provider.metadata["api_root"] == "/"
    assert provider.metadata["effective_model"] == "UNVERIFIED"
    assert ProviderConfig(base_url=provider.base_url + "/v1/").base_url.endswith("/v1")
    explicit = ProviderConfig(effort="xhigh", requested_effort="max")
    assert explicit.metadata["requested_effort"] == "max"
    assert explicit.metadata["selected_effort"] == "xhigh"


@pytest.mark.parametrize("url", ["http://api.renwang-huang.top", "https://other.example/v1",
    "https://api.renwang-huang.top/v1/v1", "https://api.renwang-huang.top/v1?secret=x",
    "https://name:password@api.renwang-huang.top/v1", "https://api.renwang-huang.top:444/v1"])
def test_provider_rejects_unapproved_or_ambiguous_roots(url):
    with pytest.raises(ValueError):
        ProviderConfig(base_url=url)


def test_real_uds_http_forwards_only_host_auth_and_actual_public_metadata():
    with _upstream() as upstream, _broker(upstream) as broker:
        assert broker.socket_path.stat().st_mode & 0o777 == 0o600
        status, headers, body = _request(broker, method="POST", route="/v1/responses", body=_payload())
        assert status == 200
        assert json.loads(body)["status"] == "completed"
        _no_secrets(headers)
        _no_secrets(body.decode())
        metadata = _wait_records(broker)
        _no_secrets(metadata)
        assert metadata["effective_model"] == "gpt-5.6-terra"
        assert metadata["effective_effort"] == "max"
        assert metadata["request_records"][0]["upstream_request_id"] == "req_synthetic_123"
        assert metadata["request_records"][0]["usage"]["total_tokens"] == 10
        assert metadata["request_records"][0]["response_completed"] is True
        assert broker.secret_values == (_KEY, _TOKEN_A)
        seen = upstream["seen"][0]
        assert seen["path"] == "/v1/responses"
        assert seen["headers"]["authorization"] == "Bearer " + _KEY
        assert _TOKEN_A not in json.dumps(seen)
        assert seen["body"]["store"] is False
        path = broker.socket_path
    assert not path.exists()
    assert broker.secret_values == ()
    assert broker.metadata["ended_at"] is not None


@pytest.mark.parametrize("token", [None, "wrong-synthetic-token", _TOKEN_B, "nonascii-è"])
def test_missing_wrong_and_cross_run_tokens_are_401_without_upstream(token):
    with _upstream() as upstream, _broker(upstream) as broker:
        status, _, body = _request(broker, token=token)
        assert status == 401
        assert json.loads(body)["error"]["type"] == "RUN_AUTHENTICATION_REQUIRED"
        assert upstream["seen"] == []
        _no_secrets(_wait_records(broker))


def test_two_real_run_sockets_accept_own_token_and_reject_other_run():
    with _upstream() as upstream, _broker(upstream) as first, _broker(
            upstream, token=_TOKEN_B, run_id="synthetic-run-b") as second:
        assert _request(first)[0] == 200
        assert _request(second, token=_TOKEN_B)[0] == 200
        assert _request(first, token=_TOKEN_B)[0] == 401
        assert _request(second, token=_TOKEN_A)[0] == 401
        assert len(upstream["seen"]) == 2


def test_peer_uid_and_expired_token_are_rejected():
    with _upstream() as upstream, _broker(upstream, allowed_peer_uid=os.getuid() + 1) as broker:
        assert _request(broker)[0] == 401
        assert upstream["seen"] == []
    with _upstream() as upstream, _broker(upstream, token_ttl_seconds=0.02) as broker:
        time.sleep(0.03)
        assert _request(broker)[0] == 401
        assert upstream["seen"] == []


@pytest.mark.parametrize("route,method,body,status", [
    ("/auth", "GET", None, 404), ("/v1/responses", "GET", None, 405),
    ("/v1/models", "POST", {}, 405), ("/v1/responses", "PUT", {}, 405),
    ("http://other.example/v1/models", "GET", None, 400),
    ("/v1/models?target=http://localhost", "GET", None, 400),
    ("/v1/responses?client_version=1.0", "POST", _payload(), 400),
    ("/v1/responses", "POST", _payload(model="other-model"), 400),
    ("/v1/responses", "POST", _payload(reasoning={"effort": "xhigh"}), 400),
    ("/v1/responses", "POST", _payload(reasoning={}), 400),
    ("/v1/responses", "POST", _payload(store=True), 400),
    ("/v1/responses", "POST", _payload(background=True), 400),
    ("/v1/responses", "POST", _payload(stream="yes"), 400),
    ("/v1/responses", "POST", b'{"model":"a","model":"b"}', 400),
    ("/v1/responses", "POST", b'{"bad":NaN}', 400),
    ("/v1/responses", "POST", b"[]", 400),
])
def test_route_model_effort_and_request_contracts_fail_closed(route, method, body, status):
    with _upstream() as upstream, _broker(upstream) as broker:
        actual, _, response = _request(broker, route=route, method=method, body=body)
        assert actual == status
        _no_secrets(response.decode())
        assert upstream["seen"] == []
        assert _wait_records(broker)["upstream_requests"] == 0


def test_request_budget_is_exact_includes_models_and_not_unauthorized_requests():
    with _upstream() as upstream, _broker(upstream, request_budget=2) as broker:
        assert _request(broker, token=None)[0] == 401
        assert _request(broker)[0] == 200
        assert _request(broker, route="/v1/models?client_version=0.162.1")[0] == 200
        assert _request(broker)[0] == 429
        metadata = _wait_records(broker, 4)
        assert metadata["upstream_requests"] == 2
        assert metadata["error_counts"]["RUN_REQUEST_BUDGET_EXHAUSTED"] == 1
        assert len(upstream["seen"]) == 2


def test_sse_is_incremental_and_concurrency_limit_is_strong():
    with _upstream(stream=True, controlled=True) as upstream, _broker(upstream, max_concurrency=1) as broker:
        connection = _UnixHTTPConnection(broker.socket_path)
        connection.request("POST", "/v1/responses", body=json.dumps(_payload(stream=True)).encode(),
                           headers={"Authorization": "Bearer " + _TOKEN_A, "Content-Type": "application/json"})
        response = connection.getresponse()
        assert upstream["first_sent"].wait(2)
        first = response.readline()
        assert b"response.created" in first
        assert _request(broker)[0] == 429
        upstream["release"].set()
        remainder = response.read()
        connection.close()
        assert b"response.completed" in remainder
        metadata = _wait_records(broker, 2)
        assert metadata["peak_concurrency"] == 1
        assert metadata["upstream_requests"] == 1
        assert metadata["error_counts"]["RUN_CONCURRENCY_LIMIT"] == 1
        success = [record for record in metadata["request_records"] if record["outcome"] == "COMPLETED"]
        assert success[0]["response_completed"] is True


@pytest.mark.parametrize("status,category", [(401, "UPSTREAM_AUTHENTICATION_ERROR"),
    (403, "UPSTREAM_AUTHENTICATION_ERROR"), (429, "UPSTREAM_RATE_LIMITED"),
    (500, "UPSTREAM_SERVER_ERROR"), (503, "UPSTREAM_SERVER_ERROR")])
def test_upstream_status_is_classified_without_echoing_error_body(status, category):
    with _upstream(status=status) as upstream, _broker(upstream) as broker:
        actual, headers, body = _request(broker)
        assert actual == (status if status < 500 else 502)
        assert json.loads(body)["error"]["type"] == category
        _no_secrets(headers)
        _no_secrets(body.decode())
        metadata = _wait_records(broker)
        assert metadata["upstream_statuses"] == {str(status): 1}
        assert metadata["errors"][0]["stage"] == "upstream_connect"
        _no_secrets(metadata)


def test_redirect_is_denied_without_credentials_reaching_other_route():
    with _upstream(redirect=True) as upstream, _broker(upstream) as broker:
        status, headers, body = _request(broker)
        assert status == 502
        assert json.loads(body)["error"]["type"] == "UPSTREAM_REDIRECT_REJECTED"
        assert "Location" not in headers
        _no_secrets(body.decode())
        assert len(upstream["seen"]) == 1


@pytest.mark.parametrize("options,category", [({"incomplete": True}, "UPSTREAM_STREAM_INCOMPLETE"),
    ({"invalid_completion": True}, "UPSTREAM_INVALID_COMPLETION"),
    ({"declared_length": 10000}, "UPSTREAM_STREAM_INTERRUPTED")])
def test_sse_integrity_failure_records_upstream_stage(options, category):
    with _upstream(stream=True, **options) as upstream, _broker(upstream) as broker:
        status, _, body = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        assert status == 200  # HTTP headers precede detection of SSE failure.
        assert category.encode() in body
        metadata = _wait_records(broker)
        assert metadata["request_records"][0]["category"] == category
        assert metadata["request_records"][0]["stage"] == "upstream_read"
        assert metadata["request_records"][0]["outcome"] == "ERROR"
        assert metadata["effective_model"] == "UNAVAILABLE"
        _no_secrets(metadata)


def test_real_upstream_read_timeout_is_bounded_and_classified():
    with _upstream(stream=True, controlled=True, timeout=True) as upstream, _broker(
            upstream, request_timeout=0.08) as broker:
        started = time.monotonic()
        status, _, _ = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        assert status == 200
        metadata = _wait_records(broker)
        assert time.monotonic() - started < 1
        assert metadata["request_records"][0]["category"] == "UPSTREAM_TIMEOUT"
        assert metadata["request_records"][0]["stage"] == "timeout"


def test_real_client_disconnect_is_distinguished_from_upstream_read():
    with _upstream(stream=True, controlled=True) as upstream, _broker(upstream) as broker:
        connection = _UnixHTTPConnection(broker.socket_path)
        connection.request("POST", "/v1/responses", body=json.dumps(_payload(stream=True)).encode(),
                           headers={"Authorization": "Bearer " + _TOKEN_A, "Content-Type": "application/json"})
        response = connection.getresponse()
        assert b"response.created" in response.readline()
        response.close()
        connection.close()
        upstream["release"].set()
        metadata = _wait_records(broker)
        record = metadata["request_records"][0]
        assert record["category"] == "CLIENT_DISCONNECTED"
        assert record["stage"] == "downstream_write"
        assert record["outcome"] == "ERROR"


def test_incomplete_slow_client_body_cannot_extend_wall_deadline():
    with _upstream() as upstream, _broker(upstream, request_timeout=0.08) as broker:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(1)
        client.connect(str(broker.socket_path))
        client.sendall(b"POST /v1/responses HTTP/1.0\r\nAuthorization: Bearer " + _TOKEN_A.encode()
            + b"\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{")
        started = time.monotonic()
        client.recv(4096)
        client.close()
        metadata = _wait_records(broker)
        assert time.monotonic() - started < 1
        assert metadata["request_records"][0]["category"] == "CLIENT_REQUEST_TIMEOUT"
        assert metadata["request_records"][0]["stage"] == "timeout"
        assert upstream["seen"] == []


def test_effective_fields_come_from_upstream_not_client_configuration():
    response = _response(model="synthetic-actual-model-alias", reasoning={})
    with _upstream(output=json.dumps(response).encode()) as upstream, _broker(upstream) as broker:
        assert _request(broker, method="POST", route="/v1/responses", body=_payload())[0] == 200
        metadata = _wait_records(broker)
        assert metadata["requested_model"] == "gpt-5.6-terra"
        assert metadata["effective_model"] == "synthetic-actual-model-alias"
        assert metadata["requested_effort"] == "max"
        assert metadata["effective_effort"] == "UNAVAILABLE"


def test_output_limit_and_request_limit_are_enforced_before_forwarding():
    with _upstream() as upstream, _broker(upstream, max_body_bytes=32) as broker:
        assert _request(broker, method="POST", route="/v1/responses", body=_payload())[0] == 413
        assert upstream["seen"] == []
    with _upstream() as upstream, _broker(upstream, max_output_bytes=20) as broker:
        status, _, body = _request(broker)
        assert status == 502
        assert b"UPSTREAM_OUTPUT_TOO_LARGE" in body


def test_actual_responses_tool_call_round_trip_is_preserved():
    with _upstream(tool_round=True) as upstream, _broker(upstream) as broker:
        tools = [{"type": "function", "name": "public_tool", "parameters": {"type": "object"}}]
        first = _request(broker, method="POST", route="/v1/responses", body=_payload(tools=tools))
        item = json.loads(first[2])["output"][0]
        assert item["type"] == "function_call"
        tool_output = {"type": "function_call_output", "call_id": item["call_id"], "output": "1"}
        second = _request(broker, method="POST", route="/v1/responses", body=_payload(input=[tool_output]))
        assert json.loads(second[2])["status"] == "completed"
        assert upstream["seen"][0]["body"]["tools"] == tools
        assert upstream["seen"][1]["body"]["input"] == [tool_output]
        assert all(record["path"] == "/v1/responses" for record in upstream["seen"])
        _no_secrets(_wait_records(broker, 2))


def test_success_echoes_are_redacted_in_json_and_across_stream_chunks():
    data = json.dumps(_response(output=[{"type": "message", "content": [{"type": "output_text",
        "text": _KEY + " " + _TOKEN_A}]}])).encode()
    with _upstream(output=data) as upstream, _broker(upstream) as broker:
        result = _request(broker, method="POST", route="/v1/responses", body=_payload())
        assert result[0] == 200
        _no_secrets(result[2].decode())
        assert b"[REDACTED]" in result[2]
    filtered = module._SecretFilter((_KEY, _TOKEN_A))
    chunks = [_KEY[:20].encode(), _KEY[20:].encode() + b" public ", _TOKEN_A[:15].encode(), _TOKEN_A[15:].encode()]
    output = b"".join(filtered.feed(chunk) for chunk in chunks) + filtered.feed(final=True)
    assert output == b"[REDACTED] public [REDACTED]"


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o666])
def test_secret_file_permissions_are_fail_closed(tmp_path, mode):
    secret = tmp_path / "synthetic-secret"
    secret.write_text(_KEY)
    secret.chmod(mode)
    broker = SecureModelBroker(ProviderConfig(), secret, run_id="synthetic-run", socket_path=tmp_path / "s.sock",
                               run_token=_TOKEN_A)
    with pytest.raises(BrokerError, match="owner-only"):
        with broker:
            pass
    assert not (tmp_path / "s.sock").exists()


def test_secret_links_and_existing_socket_path_are_rejected(tmp_path):
    secret = tmp_path / "synthetic-secret"
    secret.write_text(_KEY)
    secret.chmod(0o600)
    link = tmp_path / "linked-secret"
    link.symlink_to(secret)
    broker = SecureModelBroker(ProviderConfig(), link, run_id="synthetic-run", socket_path=tmp_path / "s.sock",
                               run_token=_TOKEN_A)
    with pytest.raises(BrokerError, match="owner-only"):
        with broker:
            pass
    occupied = tmp_path / "s.sock"
    occupied.write_text("preserve-existing")
    broker = SecureModelBroker(ProviderConfig(), secret, run_id="synthetic-run", socket_path=occupied,
                               run_token=_TOKEN_A)
    with pytest.raises(BrokerError, match="unsafe transport fallback"):
        with broker:
            pass
    assert occupied.read_text() == "preserve-existing"


def test_hardlinked_secret_is_rejected_without_reading_contents(tmp_path):
    secret = tmp_path / "synthetic-secret"
    secret.write_text(_KEY)
    secret.chmod(0o600)
    os.link(secret, tmp_path / "second-name")
    broker = SecureModelBroker(ProviderConfig(), secret, run_id="synthetic-run", socket_path=tmp_path / "s.sock",
                               run_token=_TOKEN_A)
    with pytest.raises(BrokerError, match="owner-only"):
        with broker:
            pass
    assert broker.secret_values == ()


def test_production_uses_validated_tls_no_environment_proxy_or_redirect(monkeypatch):
    captured = []
    original = module.build_opener

    def factory(*handlers):
        captured.extend(handlers)
        return original(*handlers)

    monkeypatch.setattr(module, "build_opener", factory)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    with _broker() as broker:
        assert broker.metadata["tls_verification"] == "REQUIRED"
        # Listener startup does not contact a real model or read a real secret.
    assert any(isinstance(handler, ProxyHandler) and handler.proxies == {} for handler in captured)
    assert any(isinstance(handler, module._NoRedirect) for handler in captured)
    tls = next(handler for handler in captured if isinstance(handler, HTTPSHandler))._context
    assert tls.check_hostname is True
    assert tls.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize("options", [{"request_budget": 0}, {"max_concurrency": 0},
    {"request_timeout": 121}, {"expected_model": "other-model"}, {"expected_effort": "xhigh"},
    {"test_upstream_base_url": "http://other.example/v1"},
    {"test_upstream_base_url": "https://127.0.0.1:443/v1"}])
def test_unsafe_broker_options_are_rejected(tmp_path, options):
    with pytest.raises(ValueError):
        SecureModelBroker(ProviderConfig(), tmp_path / "unread-synthetic-secret", run_id="synthetic-run",
                          socket_path=tmp_path / "s.sock", run_token=_TOKEN_A, **options)
