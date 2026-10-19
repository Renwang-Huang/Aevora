"""Small trusted, host-side credential boundary for a participant model client.

This is an HTTP transport, not an Agent orchestrator. Only two fixed Codex
backend routes are exposed. The participant never receives host access tokens,
refresh tokens, identity files or a general authenticated proxy.

The ChatGPT backend/custom-provider combination must be verified by a real
Codex invocation; contract tests do not establish model-service compatibility.
"""
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


_UPSTREAM = "https://chatgpt.com/backend-api/codex"
_MAX_BODY = 4 * 1024 * 1024
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class BrokerError(RuntimeError):
    """A safe error whose message contains no credential contents."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ModelBroker(AbstractContextManager):
    """Run a loopback broker whose secrets remain in the trusted host process.

    A test upstream is allowed only through the explicit test-only keyword and
    only for an HTTP loopback endpoint. Production always uses the fixed TLS
    backend; environment proxies and redirects cannot redirect credentials.
    """

    def __init__(self, auth_path: Path, *, request_timeout: float = 20,
                 test_upstream_base_url: str | None = None):
        if not 0 < request_timeout <= 120:
            raise ValueError("Broker timeout must be in (0, 120] seconds")
        self.auth_path = Path(auth_path)
        self.request_timeout = float(request_timeout)
        self._upstream = _UPSTREAM
        if test_upstream_base_url is not None:
            parsed = urlsplit(test_upstream_base_url)
            if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
                    or parsed.username or parsed.password or parsed.query or parsed.fragment):
                raise ValueError("Test upstream must be an HTTP loopback URL")
            self._upstream = test_upstream_base_url.rstrip("/")
        self._test_transport = test_upstream_base_url is not None
        self._server = None
        self._thread = None
        self._access_token = None
        self._account_id = None
        self._lock = threading.Lock()
        self._active = set()
        self._stats = {"requests": 0, "upstream_requests": 0, "upstream_statuses": {},
                       "errors": [], "started_at": None, "ended_at": None}

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise BrokerError("Model broker is not running")
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    @property
    def metadata(self) -> dict:
        with self._lock:
            snapshot = json.loads(json.dumps(self._stats))
        return {"transport": "TEST_TRANSPORT" if self._test_transport else "HOST_CREDENTIAL_BROKER",
                "upstream": "LOOPBACK_TEST_SERVER" if self._test_transport else _UPSTREAM,
                "credential_source": "HOST_CHATGPT_ACCESS_TOKEN",
                "credential_values": "UNAVAILABLE", "refresh": "DISABLED",
                "allowed_routes": ["GET /v1/models", "POST /v1/responses"],
                "request_timeout_seconds": self.request_timeout, **snapshot}

    @property
    def secret_values(self) -> tuple[str, ...]:
        """In-memory host redaction inputs; never archive or send to participants."""
        return tuple(value for value in (self._access_token, self._account_id) if value)

    def _error(self, kind: str):
        with self._lock:
            self._stats["errors"].append({"category": kind, "timestamp": time.time()})

    def __enter__(self):
        if self._server is not None:
            raise BrokerError("Model broker is already running")
        try:
            if self.auth_path.is_symlink() or not self.auth_path.is_file() or self.auth_path.stat().st_size > _MAX_BODY:
                raise ValueError()
            contents = json.loads(self.auth_path.read_text(encoding="utf-8"))
            tokens = contents.get("tokens", {})
            access_token = tokens.get("access_token")
            account_id = tokens.get("account_id")
            if contents.get("auth_mode") != "chatgpt" or not all(
                    isinstance(value, str) and value and "\r" not in value and "\n" not in value
                    for value in (access_token, account_id)):
                raise ValueError()
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
            raise BrokerError("Valid host ChatGPT authentication is unavailable") from None
        # Retain only fields necessary for fixed model requests. Never retain or
        # forward refresh/id tokens, API keys, user config or the complete file.
        self._access_token, self._account_id = access_token, account_id
        del contents, tokens
        owner = self
        opener = build_opener(ProxyHandler({}), _NoRedirect())

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"  # streaming delimited by connection close

            def log_message(self, format, *args):
                pass  # Never log headers, URLs, prompt bodies or upstream errors.

            def _reject(self, status: int, category: str):
                owner._error(category)
                body = json.dumps({"error": {"type": category, "message": category}}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._forward()

            def do_POST(self):
                self._forward()

            def do_PUT(self):
                self._reject(405, "METHOD_NOT_ALLOWED")

            do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_CONNECT = do_PUT

            def _forward(self):
                with owner._lock:
                    owner._stats["requests"] += 1
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    return self._reject(400, "INVALID_REQUEST_TARGET")
                if parsed.path not in ("/v1/models", "/v1/responses"):
                    return self._reject(404, "ROUTE_NOT_ALLOWED")
                if ((parsed.path == "/v1/models" and self.command != "GET")
                        or (parsed.path == "/v1/responses" and self.command != "POST")):
                    return self._reject(405, "METHOD_NOT_ALLOWED")
                query = ""
                if parsed.query:
                    pairs = parse_qsl(parsed.query, keep_blank_values=True)
                    if (parsed.path != "/v1/models" or len(pairs) != 1
                            or pairs[0][0] != "client_version" or not _SAFE_VERSION.fullmatch(pairs[0][1])):
                        return self._reject(400, "QUERY_NOT_ALLOWED")
                    query = "?" + urlencode(pairs)
                if self.headers.get("Transfer-Encoding"):
                    return self._reject(400, "TRANSFER_ENCODING_NOT_ALLOWED")
                data = None
                if self.command == "POST":
                    try:
                        length = int(self.headers.get("Content-Length", ""))
                    except ValueError:
                        return self._reject(411, "CONTENT_LENGTH_REQUIRED")
                    if not 0 < length <= _MAX_BODY:
                        return self._reject(413, "REQUEST_TOO_LARGE")
                    self.connection.settimeout(owner.request_timeout)
                    try:
                        data = self.rfile.read(length)
                        if len(data) != length:
                            raise ValueError()
                        body = json.loads(data)
                        if not isinstance(body, dict):
                            raise ValueError()
                        if body.get("store") is True:
                            return self._reject(400, "PERSISTENCE_NOT_ALLOWED")
                        body["store"] = False
                        data = json.dumps(body, separators=(",", ":")).encode()
                    except (ValueError, UnicodeError, OSError):
                        return self._reject(400, "INVALID_JSON_BODY")
                elif self.headers.get("Content-Length") not in (None, "0"):
                    return self._reject(400, "GET_BODY_NOT_ALLOWED")
                target = owner._upstream + parsed.path.removeprefix("/v1") + query
                headers = {"Authorization": "Bearer " + owner._access_token,
                           "ChatGPT-Account-ID": owner._account_id,
                           "Accept": "text/event-stream" if data else "application/json",
                           "Content-Type": "application/json", "User-Agent": "orderflow-model-broker/1.0",
                           "originator": "codex_cli_rs"}
                request = Request(target, data=data, headers=headers, method=self.command)
                with owner._lock:
                    owner._stats["upstream_requests"] += 1
                try:
                    upstream = opener.open(request, timeout=owner.request_timeout)
                except HTTPError as error:
                    # Do not expose an upstream body, redirect Location or request
                    # echo: those may include authentication or personal data.
                    with owner._lock:
                        key = str(error.code)
                        owner._stats["upstream_statuses"][key] = owner._stats["upstream_statuses"].get(key, 0) + 1
                    error.close()
                    return self._reject(502, "UPSTREAM_HTTP_ERROR")
                except (URLError, OSError, ValueError):
                    return self._reject(502, "UPSTREAM_CONNECTION_ERROR")
                with owner._lock:
                    owner._active.add(upstream)
                    key = str(upstream.status)
                    owner._stats["upstream_statuses"][key] = owner._stats["upstream_statuses"].get(key, 0) + 1
                try:
                    self.send_response(upstream.status)
                    content_type = upstream.headers.get("Content-Type", "application/octet-stream")
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    # read1 returns available socket data, preserving incremental
                    # SSE delivery rather than waiting for a complete response.
                    while block := upstream.read1(65536):
                        self.wfile.write(block)
                        self.wfile.flush()
                except (OSError, ValueError):
                    owner._error("UPSTREAM_STREAM_INTERRUPTED")
                finally:
                    with owner._lock:
                        owner._active.discard(upstream)
                    upstream.close()

        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except OSError:
            self._access_token = self._account_id = None
            self._error("BROKER_LISTEN_UNAVAILABLE")
            raise BrokerError("Trusted model broker listener is unavailable; refusing credential exposure") from None
        server.daemon_threads = True
        self._server = server
        self._stats["started_at"] = time.time()
        self._thread = threading.Thread(target=server.serve_forever, name="orderflow-model-broker", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._server is not None:
            self._server.shutdown()
            with self._lock:
                active = list(self._active)
            for upstream in active:
                try:
                    upstream.close()
                except OSError:
                    pass
            self._server.server_close()
            if self._thread is not None:
                self._thread.join(timeout=2)
            self._server = None
            self._stats["ended_at"] = time.time()
        self._access_token = self._account_id = None
        return False
