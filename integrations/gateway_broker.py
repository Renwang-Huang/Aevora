"""Per-run, bounded Responses HTTP transport over a private Unix socket.

Only a trusted host reads the upstream secret. The participant receives a
short-lived run token and a dedicated model channel. A trusted bridge may map
this HTTP-over-UDS socket into an isolated participant's loopback namespace.
This transport does not execute tools, orchestrate agents, or expose arbitrary
authenticated destinations. Tests can explicitly nominate a synthetic HTTP
loopback upstream; production has validated TLS, no redirects, and no proxies.
"""
from contextlib import AbstractContextManager
import copy
import hmac
from http.client import HTTPException, HTTPConnection, HTTPSConnection
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import socket
from socketserver import ThreadingMixIn, UnixStreamServer
import ssl
import stat
import struct
import threading
import time
import weakref
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from integrations.model_broker import BrokerError
from integrations.providers import ProviderConfig


_MAX_BODY = 4 * 1024 * 1024
_MAX_OUTPUT = 16 * 1024 * 1024
_MAX_EVENT = 2 * 1024 * 1024
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._~-]{32,512}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _TransportFailure(Exception):
    def __init__(self, category, stage):
        self.category, self.stage = category, stage


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_):
    raise ValueError("Non-finite JSON value")


class _SecretFilter:
    """Prevent exact credential echoes, including echoes split across reads."""
    def __init__(self, values):
        self.values = tuple(value.encode() for value in values if value)
        self.pending = b""

    def feed(self, block=b"", *, final=False):
        data = self.pending + block
        for value in self.values:
            data = data.replace(value, b"[REDACTED]")
        keep = 0
        if not final:
            for value in self.values:
                start = max(0, len(data) - len(value) + 1)
                position = data.find(value[:1], start)
                while position != -1:
                    if value.startswith(data[position:]):
                        keep = max(keep, len(data) - position)
                    position = data.find(value[:1], position + 1)
        limit = len(data) - keep
        output, self.pending = data[:limit], data[limit:]
        return output


class _SSEObserver:
    """Observe response termination and public metadata without saving bodies."""
    def __init__(self, owner, record):
        self.owner, self.record = owner, record
        self.pending = b""
        self.completed = False

    def feed(self, block):
        self.pending += block
        # SSE permits both CRLF and LF. Preserve wire bytes when forwarding.
        normalized = self.pending.replace(b"\r\n", b"\n")
        while b"\n\n" in normalized:
            event, normalized = normalized.split(b"\n\n", 1)
            if len(event) > _MAX_EVENT:
                raise _TransportFailure("UPSTREAM_EVENT_TOO_LARGE", "upstream_read")
            self._event(event)
        self.pending = normalized
        if len(self.pending) > _MAX_EVENT:
            raise _TransportFailure("UPSTREAM_EVENT_TOO_LARGE", "upstream_read")

    def _event(self, event):
        data = b"\n".join(line[5:].lstrip(b" ") for line in event.split(b"\n")
                          if line.startswith(b"data:"))
        if not data or data == b"[DONE]":
            return
        try:
            item = json.loads(data, object_pairs_hook=_unique_json, parse_constant=_invalid_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise _TransportFailure("UPSTREAM_INVALID_SSE", "upstream_read") from None
        if not isinstance(item, dict):
            raise _TransportFailure("UPSTREAM_INVALID_SSE", "upstream_read")
        kind = item.get("type")
        if kind in ("response.created", "response.in_progress", "response.completed"):
            self.owner._observe_response(item.get("response"), self.record)
        if kind == "response.completed":
            response = item.get("response")
            if not isinstance(response, dict) or response.get("status") != "completed":
                raise _TransportFailure("UPSTREAM_INVALID_COMPLETION", "upstream_read")
            self.completed = True
            self.record["response_completed"] = True
        if kind in ("error", "response.failed", "response.incomplete"):
            raise _TransportFailure("UPSTREAM_RESPONSE_ERROR", "upstream_read")

    def finish(self):
        # An unterminated SSE frame is incomplete, even if it contains the text
        # response.completed. [DONE] alone cannot establish Responses success.
        if self.pending.strip() or not self.completed:
            raise _TransportFailure("UPSTREAM_STREAM_INCOMPLETE", "upstream_read")


class SecureModelBroker(AbstractContextManager):
    def __init__(self, provider: ProviderConfig, secret_path: Path, *, run_id: str,
                 socket_path: Path, run_token: str, request_budget: int | None = 160,
                 max_concurrency: int = 4, request_timeout: float = 120,
                 expected_model: str | None = None, expected_effort: str | None = None,
                 allowed_peer_uid: int | None = None, token_ttl_seconds: float = 1800,
                 max_body_bytes: int = _MAX_BODY, max_output_bytes: int = _MAX_OUTPUT,
                 test_upstream_base_url: str | None = None,
                 completion_policy: str = "bounded", connect_timeout_seconds: float = 30,
                 event_path: Path | None = None):
        if completion_policy not in ("bounded", "completion-aware"):
            raise ValueError("Unknown completion policy")
        if not isinstance(provider, ProviderConfig):
            raise ValueError("A validated provider configuration is required")
        if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
            raise ValueError("A bounded run ID is required")
        if not isinstance(run_token, str) or not _TOKEN.fullmatch(run_token):
            raise ValueError("A dedicated run token of at least 32 safe characters is required")
        if not (completion_policy == "completion-aware" and request_budget is None) and (
                not isinstance(request_budget, int) or isinstance(request_budget, bool) or not 1 <= request_budget <= 10000):
            raise ValueError("Request budget must be in [1, 10000]")
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or not 1 <= max_concurrency <= 32:
            raise ValueError("Concurrency must be in [1, 32]")
        if completion_policy == "bounded" and (request_timeout is None or token_ttl_seconds is None):
            raise ValueError("Bounded broker requires finite timeout and identity lifetime")
        if (request_timeout is not None and not 0 < request_timeout <= 120) or (
                token_ttl_seconds is not None and not 0 < token_ttl_seconds <= 86400):
            raise ValueError("Request timeout and token lifetime must be bounded")
        if not isinstance(connect_timeout_seconds, (int, float)) or isinstance(connect_timeout_seconds, bool) or not 0 < connect_timeout_seconds <= 120:
            raise ValueError("Socket/TLS connection timeout must be finite and bounded")
        if not 1 <= max_body_bytes <= _MAX_BODY or not 1 <= max_output_bytes <= _MAX_OUTPUT:
            raise ValueError("Body and output limits exceed the transport policy")
        if expected_model is not None and expected_model != provider.model:
            raise ValueError("Expected model must agree with the nominated provider")
        if expected_effort is not None and expected_effort != provider.effort:
            raise ValueError("Expected effort must agree with the nominated provider")
        self.provider, self.secret_path = provider, Path(secret_path)
        self.run_id, self.socket_path = run_id, Path(socket_path)
        self.expected_model, self.expected_effort = provider.model, provider.effort
        self.request_budget, self.max_concurrency = request_budget, max_concurrency
        self.request_timeout = float(request_timeout) if request_timeout is not None else None
        self.token_ttl_seconds = float(token_ttl_seconds) if token_ttl_seconds is not None else None
        self.completion_policy, self.connect_timeout_seconds = completion_policy, connect_timeout_seconds
        self.event_path, self._event_output = Path(event_path) if event_path else None, None
        self.max_body_bytes, self.max_output_bytes = max_body_bytes, max_output_bytes
        self.allowed_peer_uid = os.getuid() if allowed_peer_uid is None else allowed_peer_uid
        if not isinstance(self.allowed_peer_uid, int) or self.allowed_peer_uid < 0:
            raise ValueError("Peer UID must be a valid nonnegative UID")
        self._token, self._api_key = run_token, None
        self._upstream = provider.base_url
        self._test_transport = test_upstream_base_url is not None
        if self._test_transport:
            parsed = urlsplit(test_upstream_base_url)
            try:
                port = parsed.port
            except ValueError:
                raise ValueError("Invalid synthetic upstream") from None
            if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
                    or not port or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in ("", "/", "/v1", "/v1/")):
                raise ValueError("Synthetic upstream must be an explicit HTTP loopback API root")
            self._upstream = test_upstream_base_url.rstrip("/")
        self._lock = threading.Lock()
        self._server = self._thread = None
        self._entered = False
        self._active_upstreams, self._connections = set(), set()
        self._transport_sockets, self._active_records = weakref.WeakSet(), {}
        self._handler_threads = set()
        self._last_rate_limit = None
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._socket_identity = None
        self._start_mono = None
        self._stats = {"requests": 0, "upstream_requests": 0, "active_requests": 0,
                       "peak_concurrency": 0, "upstream_statuses": {}, "error_counts": {},
                       "errors": [], "request_records": [], "started_at": None, "ended_at": None}

    @property
    def base_url(self):
        """Bridge-side HTTP root; no host TCP listener is created by this broker."""
        if self._server is None:
            raise BrokerError("Secure model broker is not running")
        return "http://localhost/v1"

    @property
    def secret_values(self):
        """Trusted in-memory redaction inputs. Never serialize this property."""
        return tuple(value for value in (self._api_key, self._token) if value)

    @property
    def metadata(self):
        with self._lock:
            snapshot = copy.deepcopy(self._stats)
        models = sorted({item["actual_model"] for item in snapshot["request_records"] if item.get("actual_model")})
        efforts = sorted({item["actual_effort"] for item in snapshot["request_records"] if item.get("actual_effort")})
        completed_models = sorted({item["actual_model"] for item in snapshot["request_records"]
                                   if item.get("actual_model") and item.get("outcome") == "COMPLETED"})
        completed_efforts = sorted({item["actual_effort"] for item in snapshot["request_records"]
                                    if item.get("actual_effort") and item.get("outcome") == "COMPLETED"})
        return {**self.provider.metadata,
                "effective_model": completed_models[0] if len(completed_models) == 1 else "UNAVAILABLE",
                "effective_effort": completed_efforts[0] if len(completed_efforts) == 1 else "UNAVAILABLE",
                "observed_models": models, "observed_efforts": efforts,
                "transport": "SYNTHETIC_LOOPBACK_UDS" if self._test_transport else "HOST_GATEWAY_UDS",
                "run_id": self.run_id, "credential_source": "TRUSTED_HOST_SECRET_FILE",
                "credential_values": "UNAVAILABLE", "caller_authentication": "PER_RUN_BEARER",
                "allowed_routes": ["GET /v1/models", "POST /v1/responses"],
                "peer_uid_binding": self.allowed_peer_uid, "request_budget": self.request_budget,
                "max_concurrency": self.max_concurrency, "request_timeout_seconds": self.request_timeout,
                "completion_policy": self.completion_policy, "connect_timeout_seconds": self.connect_timeout_seconds,
                "first_response_timeout_seconds": self.request_timeout,
                "stream_idle_timeout_seconds": self.request_timeout,
                "total_response_timeout_seconds": self.request_timeout,
                "request_history": {"availability": "AVAILABLE" if self.event_path else "UNAVAILABLE",
                                    "path": str(self.event_path) if self.event_path else None,
                                    "metadata_records_are_bounded_window": True},
                "token_revocation": "BROKER_OWNER_LIFETIME" if self.token_ttl_seconds is None else "FIXED_TTL_AND_OWNER_LIFETIME",
                "token_lifetime_seconds": self.token_ttl_seconds,
                "max_body_bytes": self.max_body_bytes, "max_output_bytes": self.max_output_bytes,
                "tls_verification": "NOT_APPLICABLE_SYNTHETIC" if self._test_transport else "REQUIRED",
                "redirects": "DENIED", "environment_proxies": "DISABLED", **snapshot}

    def _safe_id(self, value):
        if (isinstance(value, str) and _SAFE_ID.fullmatch(value)
                and all(secret not in value for secret in self.secret_values)):
            return value
        return None

    def _observe_response(self, response, record):
        if not isinstance(response, dict):
            return
        for name, value in (("actual_model", response.get("model")),
                            ("response_id", response.get("id"))):
            safe = self._safe_id(value)
            if safe:
                record[name] = safe
        reasoning = response.get("reasoning")
        if isinstance(reasoning, dict) and reasoning.get("effort") in (
                "none", "minimal", "low", "medium", "high", "xhigh", "max"):
            record["actual_effort"] = reasoning["effort"]
        usage = response.get("usage")
        if isinstance(usage, dict):
            observed = {}
            for name in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(name)
                if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10**12:
                    observed[name] = value
            for name in ("input_tokens_details", "output_tokens_details"):
                details = usage.get(name)
                if isinstance(details, dict):
                    safe_details = {key: value for key, value in details.items()
                                    if key in ("cached_tokens", "reasoning_tokens")
                                    and isinstance(value, int) and not isinstance(value, bool)
                                    and 0 <= value <= 10**12}
                    if safe_details:
                        observed[name] = safe_details
            if observed:
                record["usage"] = observed

    def _error(self, category, stage):
        with self._lock:
            counts = self._stats["error_counts"]
            counts[category] = counts.get(category, 0) + 1
            self._stats["errors"].append({"category": category, "stage": stage, "timestamp": time.time()})
            del self._stats["errors"][:-256]
        self._event("UPSTREAM_ERROR", {"category": category, "stage": stage})

    def _event(self, kind, detail):
        with self._lock:
            if self._event_output is not None:
                self._event_output.write(json.dumps({"run_id": self.run_id, "timestamp": time.time(),
                    "source": "trusted_gateway_transport", "event_type": kind, "detail": detail}, sort_keys=True) + "\n")
                self._event_output.flush()

    def _activity(self, record, activity):
        record["activity"] = activity
        record["activity_at"] = time.time()
        with self._lock:
            self._active_records[id(record)] = dict(record)

    def activity_snapshot(self):
        with self._lock:
            usage = {}
            for record in self._stats["request_records"]:
                if record.get("response_id") and record.get("outcome") == "COMPLETED" and record.get("usage"):
                    usage[record["response_id"]] = copy.deepcopy(record["usage"])
            active = [dict(item) for item in self._active_records.values()]
            for item in active:
                if item.get("last_body_byte_at"):
                    item["stream_idle_observed_seconds"] = max(0, time.time() - item["last_body_byte_at"])
                    if item["stream_idle_observed_seconds"] > 30:
                        item["activity"] = "ACTIVE_MODEL_REQUEST"
            return {"upstream_requests": self._stats["upstream_requests"], "request_budget": self.request_budget,
                    "active_requests": active,
                    "last_errors": copy.deepcopy(self._stats["errors"][-8:]),
                    "error_counts": dict(self._stats["error_counts"]),
                    "rate_limit_advice": copy.deepcopy(self._last_rate_limit),
                    "response_usage": {"availability": "AVAILABLE" if usage else "UNAVAILABLE",
                        "coverage": "RECENT_METADATA_WINDOW_ONLY; FULL_REQUEST_LOG_IS_AUTHORITATIVE",
                        "by_response_id": usage}}

    def _record(self, record):
        record["ended_at"] = time.time()
        if record.get("request_sent_at"):
            record["complete_request_seconds"] = record["ended_at"] - record["request_sent_at"]
        if record.get("first_body_byte_at") and record.get("last_body_byte_at"):
            record["observed_stream_seconds"] = record["last_body_byte_at"] - record["first_body_byte_at"]
        with self._lock:
            self._stats["request_records"].append(copy.deepcopy(record))
            del self._stats["request_records"][:-min(2048, (self.request_budget or 1920) + 128)]
            self._active_records.pop(id(record), None)
        self._event("REQUEST_FINISHED", record)

    def _read_secret(self):
        descriptor = None
        try:
            descriptor = os.open(self.secret_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_nlink != 1 or not 0 < info.st_size <= 8192):
                raise ValueError()
            raw = os.read(descriptor, 8193)
            key = raw.decode("ascii").strip()
            if not key or len(key) > 8192 or any(ord(char) < 33 or ord(char) > 126 for char in key):
                raise ValueError()
            return key
        except (OSError, ValueError, UnicodeError):
            raise BrokerError("A private, owner-only host gateway secret is required") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def __enter__(self):
        if self._entered:
            raise BrokerError("A secure broker instance cannot be reused across runs")
        self._entered = True
        try:
            self._api_key = self._read_secret()
        except BrokerError:
            self._token = None
            self._error("HOST_SECRET_UNAVAILABLE", "startup")
            raise
        try:
            parent = self.socket_path.parent
            info = parent.stat()
            if (not self.socket_path.is_absolute() or parent.resolve() != parent
                    or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or self.socket_path.exists() or self.socket_path.is_symlink()
                    or len(os.fsencode(self.socket_path)) > 107):
                raise ValueError()
            if not hasattr(socket, "SO_PEERCRED"):
                raise ValueError()
            owner = self
            tls = ssl.create_default_context()
            if self.completion_policy == "completion-aware":
                # urllib's timeout normally includes HTTP first-response wait.
                # Set it only while connecting/TLS, then clear it. Register the
                # live socket before waiting for headers so cancellation can
                # interrupt even an upstream that has sent no response yet.
                class ConnectionMixin:
                    def connect(self):
                        self.timeout = owner.connect_timeout_seconds
                        super().connect()
                        self.sock.settimeout(None)
                        with owner._lock:
                            owner._transport_sockets.add(self.sock)

                class PlainConnection(ConnectionMixin, HTTPConnection):
                    pass

                class TLSConnection(ConnectionMixin, HTTPSConnection):
                    pass

                class PlainHandler(HTTPHandler):
                    def http_open(self, request):
                        return self.do_open(PlainConnection, request)

                class TLSHandler(HTTPSHandler):
                    def https_open(self, request):
                        return self.do_open(TLSConnection, request, context=self._context)

                opener = build_opener(ProxyHandler({}), _NoRedirect(), PlainHandler(), TLSHandler(context=tls))
            else:
                opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=tls))
            if self.event_path:
                self._event_output = self.event_path.open("x")

            class Server(ThreadingMixIn, UnixStreamServer):
                daemon_threads = True
                block_on_close = False
                request_queue_size = max(4, owner.max_concurrency * 2)

                def __init__(self, *args):
                    self.thread_slots = threading.BoundedSemaphore(owner.max_concurrency * 2 + 4)
                    super().__init__(*args)

                def get_request(self):
                    connection, address = super().get_request()
                    connection.settimeout(min(5, owner.request_timeout or 5))
                    with owner._lock:
                        owner._connections.add(connection)
                    return connection, address

                def process_request(self, request, client_address):
                    if not self.thread_slots.acquire(blocking=False):
                        owner._error("BROKER_CONNECTION_LIMIT", "admission")
                        payload = b'{"error":{"type":"BROKER_CONNECTION_LIMIT"}}'
                        try:
                            request.sendall(b"HTTP/1.0 429 Too Many Requests\r\nContent-Type: application/json\r\n"
                                            + b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload)
                        except OSError:
                            pass
                        self.shutdown_request(request)
                        return
                    try:
                        super().process_request(request, client_address)
                    except BaseException:
                        self.thread_slots.release()
                        raise

                def process_request_thread(self, request, client_address):
                    with owner._lock:
                        owner._handler_threads.add(threading.current_thread())
                    try:
                        super().process_request_thread(request, client_address)
                    finally:
                        with owner._lock:
                            owner._handler_threads.discard(threading.current_thread())
                        self.thread_slots.release()

                def shutdown_request(self, request):
                    with owner._lock:
                        owner._connections.discard(request)
                    super().shutdown_request(request)

                def handle_error(self, request, client_address):
                    owner._error("BROKER_HANDLER_ERROR", "handler")

            class Handler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.0"
                server_version = "OrderFlowSecureBroker/1.0"
                sys_version = ""

                def setup(self):
                    super().setup()
                    self.deadline = time.monotonic() + owner.request_timeout if owner.request_timeout is not None else None
                    self.deadline_expired = False

                    def expire():
                        self.deadline_expired = True
                        owner._error("REQUEST_WALL_TIMEOUT", "timeout")
                        try:
                            self.connection.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

                    # Socket timeouts alone are per recv; a slow header/body
                    # producer could otherwise extend a run without limit.
                    self.deadline_timer = threading.Timer(owner.request_timeout or 10, expire)
                    self.deadline_timer.daemon = True
                    self.deadline_timer.start()  # New mode bounds only untrusted ingress framing.

                def finish(self):
                    try:
                        super().finish()
                    finally:
                        self.deadline_timer.cancel()

                def address_string(self):
                    return "unix-peer"

                def log_message(self, *_):
                    pass

                def send_error(self, code, message=None, explain=None):
                    # BaseHTTPRequestHandler's defaults may echo request text.
                    self._reject(code, "INVALID_HTTP_REQUEST", "downstream_read")

                def _reject(self, status, category, stage="validation", retry_after=None):
                    owner._error(category, stage)
                    record = getattr(self, "record", None)
                    if record is not None:
                        record.update(outcome="REJECTED", category=category, stage=stage, http_status=status)
                    body = json.dumps({"error": {"type": category, "message": category}}).encode()
                    try:
                        self.send_response(status)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Cache-Control", "no-store")
                        if retry_after is not None:
                            self.send_header("Retry-After", retry_after)
                        self.end_headers()
                        self.wfile.write(body)
                    except (OSError, ValueError):
                        owner._error("CLIENT_DISCONNECTED", "downstream_write")

                def do_GET(self):
                    self._dispatch()

                do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_CONNECT = do_TRACE = do_GET

                def _dispatch(self):
                    self.record = {"run_id": owner.run_id, "started_at": time.time(), "outcome": "ERROR"}
                    with owner._lock:
                        owner._stats["requests"] += 1
                    try:
                        self._forward()
                    finally:
                        owner._record(self.record)

                def _forward(self):
                    try:
                        _, peer_uid, _ = struct.unpack("3i", self.connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
                    except OSError:
                        return self._reject(401, "CALLER_IDENTITY_UNAVAILABLE", "authentication")
                    authorization = self.headers.get_all("Authorization", [])
                    if (peer_uid != owner.allowed_peer_uid or len(authorization) != 1 or not owner._token
                            or not hmac.compare_digest(authorization[0].encode(), ("Bearer " + owner._token).encode())
                            or (owner.token_ttl_seconds is not None and time.monotonic() - owner._start_mono >= owner.token_ttl_seconds)):
                        return self._reject(401, "RUN_AUTHENTICATION_REQUIRED", "authentication")
                    parsed = urlsplit(self.path)
                    if parsed.scheme or parsed.netloc or parsed.fragment:
                        return self._reject(400, "INVALID_REQUEST_TARGET")
                    if parsed.path not in ("/v1/models", "/v1/responses"):
                        return self._reject(404, "ROUTE_NOT_ALLOWED")
                    self.record["route"] = parsed.path
                    if self.command != ("GET" if parsed.path == "/v1/models" else "POST"):
                        return self._reject(405, "METHOD_NOT_ALLOWED")
                    query = ""
                    if parsed.query:
                        pairs = parse_qsl(parsed.query, keep_blank_values=True)
                        if (parsed.path != "/v1/models" or len(pairs) != 1
                                or pairs[0][0] != "client_version" or not _SAFE_VERSION.fullmatch(pairs[0][1])):
                            return self._reject(400, "QUERY_NOT_ALLOWED")
                        query = "?" + urlencode(pairs)
                    if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) > 1:
                        return self._reject(400, "AMBIGUOUS_REQUEST_FRAMING")
                    if not owner._slots.acquire(blocking=False):
                        return self._reject(429, "RUN_CONCURRENCY_LIMIT", "admission")
                    try:
                        with owner._lock:
                            exhausted = owner.request_budget is not None and owner._stats["upstream_requests"] >= owner.request_budget
                            if not exhausted:
                                owner._stats["active_requests"] += 1
                                owner._stats["peak_concurrency"] = max(owner._stats["peak_concurrency"],
                                                                       owner._stats["active_requests"])
                        if exhausted:
                            return self._reject(429, "RUN_REQUEST_BUDGET_EXHAUSTED", "admission")
                        try:
                            self._authorized_request(parsed, query)
                        finally:
                            with owner._lock:
                                owner._stats["active_requests"] -= 1
                    finally:
                        owner._slots.release()

                def _authorized_request(self, parsed, query):
                    deadline = self.deadline
                    self.connection.settimeout(owner.request_timeout)
                    data = None
                    streaming = False
                    if self.command == "POST":
                        length_text = self.headers.get("Content-Length", "")
                        if not length_text.isascii() or not length_text.isdecimal():
                            return self._reject(411, "CONTENT_LENGTH_REQUIRED")
                        length = int(length_text)
                        if not 0 < length <= owner.max_body_bytes:
                            return self._reject(413, "REQUEST_TOO_LARGE")
                        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        if content_type != "application/json":
                            return self._reject(415, "JSON_CONTENT_TYPE_REQUIRED")
                        try:
                            raw = self.rfile.read(length)
                            if len(raw) != length:
                                if self.deadline_expired:
                                    return self._reject(408, "CLIENT_REQUEST_TIMEOUT", "timeout")
                                return self._reject(400, "CLIENT_REQUEST_INCOMPLETE", "downstream_read")
                            body = json.loads(raw, object_pairs_hook=_unique_json, parse_constant=_invalid_constant)
                            if not isinstance(body, dict):
                                raise ValueError()
                        except TimeoutError:
                            return self._reject(408, "CLIENT_REQUEST_TIMEOUT", "timeout")
                        except (ValueError, UnicodeError, RecursionError):
                            return self._reject(400, "INVALID_JSON_BODY")
                        except OSError:
                            return self._reject(400, "CLIENT_DISCONNECTED", "downstream_read")
                        if body.get("model") != owner.expected_model:
                            return self._reject(400, "MODEL_NOT_ALLOWED")
                        reasoning = body.get("reasoning")
                        if not isinstance(reasoning, dict) or reasoning.get("effort") != owner.expected_effort:
                            return self._reject(400, "EFFORT_NOT_ALLOWED")
                        if body.get("store") is True or body.get("background") is True:
                            return self._reject(400, "PERSISTENCE_NOT_ALLOWED")
                        if "stream" in body and not isinstance(body["stream"], bool):
                            return self._reject(400, "INVALID_STREAM_FLAG")
                        body["store"] = False
                        streaming = body.get("stream", False)
                        data = json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
                        if len(data) > owner.max_body_bytes:
                            return self._reject(413, "REQUEST_TOO_LARGE")
                        self.record.update(model=owner.expected_model, effort=owner.expected_effort)
                    elif self.headers.get("Content-Length") not in (None, "0"):
                        return self._reject(400, "GET_BODY_NOT_ALLOWED")
                    if owner.completion_policy == "completion-aware":
                        # Authentication and bounded body/framing have finished.
                        # Do not impose a whole response deadline on the model.
                        self.deadline_timer.cancel()
                        self.connection.settimeout(None)
                    # Reserve the global budget atomically after validation.
                    with owner._lock:
                        exhausted = owner.request_budget is not None and owner._stats["upstream_requests"] >= owner.request_budget
                        if not exhausted:
                            owner._stats["upstream_requests"] += 1
                    if exhausted:
                        return self._reject(429, "RUN_REQUEST_BUDGET_EXHAUSTED", "admission")
                    target = owner._upstream + parsed.path.removeprefix("/v1") + query
                    headers = {"Authorization": "Bearer " + owner._api_key,
                               "Accept": "text/event-stream" if streaming else "application/json",
                               "Content-Type": "application/json", "Accept-Encoding": "identity",
                               "User-Agent": "orderflow-secure-gateway/1.0"}
                    request = Request(target, data=data, headers=headers, method=self.command)
                    self.record["request_sent_at"] = time.time()
                    owner._activity(self.record, "ACTIVE_MODEL_REQUEST")
                    owner._event("ACTIVE_MODEL_REQUEST", self.record)
                    try:
                        remaining = deadline - time.monotonic() if deadline is not None else None
                        if remaining is not None and remaining <= 0:
                            raise TimeoutError()
                        upstream = opener.open(request, timeout=remaining)
                    except HTTPError as error:
                        self._upstream_status(error.code)
                        self.record["upstream_request_id"] = owner._safe_id(error.headers.get("x-request-id"))
                        retry_after = None
                        candidate = error.headers.get("Retry-After", "")
                        if error.code == 429 and len(candidate) <= 128:
                            try:
                                delay = int(candidate) if candidate.isascii() and candidate.isdecimal() else max(0, int(parsedate_to_datetime(candidate).timestamp() - time.time()))
                                if 0 <= delay <= 86400:
                                    retry_after = str(delay)
                                    self.record.update(retry_after_seconds=delay, retry_after_source="UPSTREAM_HEADER")
                                    owner._last_rate_limit = {"observed_at": time.time(), "retry_after_seconds": delay,
                                                             "backoff_until": time.time() + delay, "actual_client_wait": "UNAVAILABLE"}
                            except (ValueError, TypeError, OverflowError):
                                pass
                        error.close()
                        if error.code in (401, 403):
                            status, category = error.code, "UPSTREAM_AUTHENTICATION_ERROR"
                        elif error.code == 429:
                            status, category = 429, "UPSTREAM_RATE_LIMITED"
                        elif 300 <= error.code < 400:
                            status, category = 502, "UPSTREAM_REDIRECT_REJECTED"
                        elif error.code >= 500:
                            status, category = 502, "UPSTREAM_SERVER_ERROR"
                        else:
                            status, category = error.code if 400 <= error.code < 500 else 502, "UPSTREAM_REQUEST_REJECTED"
                        return self._reject(status, category, "upstream_connect", retry_after=retry_after)
                    except (URLError, OSError, ValueError) as error:
                        reason = error.reason if isinstance(error, URLError) else error
                        if isinstance(reason, (TimeoutError, socket.timeout)):
                            return self._reject(504, "UPSTREAM_TIMEOUT", "timeout")
                        if isinstance(reason, ssl.SSLError):
                            return self._reject(502, "UPSTREAM_TLS_ERROR", "upstream_connect")
                        return self._reject(502, "UPSTREAM_CONNECTION_ERROR", "upstream_connect")
                    self._upstream_status(upstream.status)
                    self.record["http_first_response_at"] = time.time()
                    self.record["http_first_response_seconds"] = self.record["http_first_response_at"] - self.record["request_sent_at"]
                    owner._activity(self.record, "ACTIVE_MODEL_REQUEST")
                    self.record["upstream_request_id"] = owner._safe_id(upstream.headers.get("x-request-id"))
                    with owner._lock:
                        owner._active_upstreams.add(upstream)
                    try:
                        self._relay(upstream, deadline, streaming, parsed.path)
                    finally:
                        with owner._lock:
                            owner._active_upstreams.discard(upstream)
                        upstream.close()

                def _upstream_status(self, status):
                    self.record["upstream_http_status"] = status
                    with owner._lock:
                        key = str(status)
                        owner._stats["upstream_statuses"][key] = owner._stats["upstream_statuses"].get(key, 0) + 1

                def _read_block(self, upstream, deadline):
                    remaining = deadline - time.monotonic() if deadline is not None else None
                    if remaining is not None and remaining <= 0:
                        raise _TransportFailure("UPSTREAM_TIMEOUT", "timeout")
                    try:
                        # urllib's standard HTTPResponse owns the live socket.
                        # Update its read timeout to the remaining wall budget.
                        raw = getattr(getattr(upstream, "fp", None), "raw", None)
                        upstream_socket = getattr(raw, "_sock", None)
                        if upstream_socket is not None:
                            upstream_socket.settimeout(remaining)
                        return upstream.read1(65536)
                    except TimeoutError:
                        raise _TransportFailure("UPSTREAM_TIMEOUT", "timeout") from None
                    except (OSError, ValueError, HTTPException):
                        raise _TransportFailure("UPSTREAM_STREAM_INTERRUPTED", "upstream_read") from None

                def _write(self, data, deadline):
                    remaining = deadline - time.monotonic() if deadline is not None else None
                    if remaining is not None and remaining <= 0:
                        raise _TransportFailure("DOWNSTREAM_TIMEOUT", "timeout")
                    try:
                        self.connection.settimeout(remaining)
                        self.wfile.write(data)
                        self.wfile.flush()
                    except TimeoutError:
                        raise _TransportFailure("DOWNSTREAM_TIMEOUT", "timeout") from None
                    except (BrokenPipeError, ConnectionResetError):
                        raise _TransportFailure("CLIENT_DISCONNECTED", "downstream_write") from None
                    except (OSError, ValueError):
                        raise _TransportFailure("DOWNSTREAM_WRITE_ERROR", "downstream_write") from None

                def _relay(self, upstream, deadline, streaming, route):
                    sent_headers = False
                    content_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    response_filter = _SecretFilter(owner.secret_values)
                    observer = _SSEObserver(owner, self.record) if streaming else None
                    size = 0
                    try:
                        expected_type = "text/event-stream" if streaming else "application/json"
                        if content_type != expected_type or upstream.headers.get("Content-Encoding", "identity") != "identity":
                            raise _TransportFailure("UPSTREAM_PROTOCOL_MISMATCH", "upstream_read")
                        length_text = upstream.headers.get("Content-Length")
                        if length_text is not None:
                            if not length_text.isdecimal() or int(length_text) > owner.max_output_bytes:
                                raise _TransportFailure("UPSTREAM_OUTPUT_TOO_LARGE", "upstream_read")
                        if streaming:
                            self.send_response(upstream.status)
                            self.send_header("Content-Type", "text/event-stream")
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            sent_headers = True
                        chunks = []
                        while block := self._read_block(upstream, deadline):
                            arrived = time.time()
                            if "first_body_byte_at" not in self.record:
                                self.record["first_body_byte_at"] = arrived
                            if "last_body_byte_at" in self.record:
                                self.record["max_body_gap_seconds"] = max(self.record.get("max_body_gap_seconds", 0), arrived - self.record["last_body_byte_at"])
                            self.record["last_body_byte_at"] = arrived
                            size += len(block)
                            self.record["observed_body_bytes"] = size
                            owner._activity(self.record, "SSE_STREAMING" if streaming else "ACTIVE_MODEL_REQUEST")
                            if size > owner.max_output_bytes:
                                raise _TransportFailure("UPSTREAM_OUTPUT_TOO_LARGE", "upstream_read")
                            if observer:
                                observer.feed(block)
                                self._write(response_filter.feed(block), deadline)
                                if observer.completed:
                                    # A fully parsed and forwarded Responses
                                    # terminal frame ends this response. Some
                                    # gateways keep their chunked connection
                                    # open afterward; waiting for socket EOF
                                    # would retain a completed request's slot.
                                    self.record["transport_completion_boundary"] = "RESPONSES_COMPLETED_EVENT"
                                    break
                            else:
                                chunks.append(block)
                        if length_text is not None and size != int(length_text):
                            raise _TransportFailure("UPSTREAM_STREAM_INTERRUPTED", "upstream_read")
                        if observer:
                            observer.finish()
                            self._write(response_filter.feed(final=True), deadline)
                        else:
                            data = b"".join(chunks)
                            try:
                                response = json.loads(data, object_pairs_hook=_unique_json, parse_constant=_invalid_constant)
                            except (ValueError, UnicodeError, RecursionError):
                                raise _TransportFailure("UPSTREAM_INVALID_JSON", "upstream_read") from None
                            if not isinstance(response, dict):
                                raise _TransportFailure("UPSTREAM_INVALID_JSON", "upstream_read")
                            if route == "/v1/responses":
                                owner._observe_response(response, self.record)
                                if response.get("status") != "completed":
                                    raise _TransportFailure("UPSTREAM_RESPONSE_ERROR", "upstream_read")
                                self.record["response_completed"] = True
                            data = response_filter.feed(data, final=True)
                            self.send_response(upstream.status)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Content-Length", str(len(data)))
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            sent_headers = True
                            self._write(data, deadline)
                        self.record.update(outcome="COMPLETED", http_status=upstream.status, output_bytes=size)
                    except _TransportFailure as failure:
                        self.record.update(outcome="ERROR", category=failure.category, stage=failure.stage,
                                           http_status=upstream.status if sent_headers else 502, output_bytes=size)
                        if sent_headers:
                            owner._error(failure.category, failure.stage)
                            if failure.stage == "upstream_read":
                                try:
                                    self._write(b'\n\nevent: error\ndata: ' + json.dumps({"type": "error", "error": {
                                        "type": failure.category, "message": failure.category}}).encode() + b"\n\n", deadline)
                                except _TransportFailure:
                                    pass
                        else:
                            self._reject(504 if failure.stage == "timeout" else 502,
                                         failure.category, failure.stage)
                    except (OSError, ValueError):
                        owner._error("DOWNSTREAM_WRITE_ERROR", "downstream_write")
                        self.record.update(outcome="ERROR", category="DOWNSTREAM_WRITE_ERROR", stage="downstream_write")

            self._server = Server(str(self.socket_path), Handler)
            info = self.socket_path.stat()
            self._socket_identity = (info.st_dev, info.st_ino)
            os.chmod(self.socket_path, 0o600)
            self._start_mono = time.monotonic()
            self._stats["started_at"] = time.time()
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            kwargs={"poll_interval": 0.05},
                                            name="orderflow-secure-broker", daemon=True)
            self._thread.start()
            return self
        except (OSError, ValueError):
            if self._server is not None:
                self._server.server_close()
                self._server = None
                try:
                    info = self.socket_path.lstat()
                    if (info.st_dev, info.st_ino) == self._socket_identity and stat.S_ISSOCK(info.st_mode):
                        self.socket_path.unlink()
                except FileNotFoundError:
                    pass
            self._api_key = self._token = None
            self._error("BROKER_LISTEN_UNAVAILABLE", "startup")
            raise BrokerError("Private Unix broker unavailable; refusing unsafe transport fallback") from None

    def __exit__(self, exc_type, exc_value, traceback):
        if self._server is not None:
            self._server.shutdown()
            with self._lock:
                connections, upstreams, transport_sockets = list(self._connections), list(self._active_upstreams), list(self._transport_sockets)
            for transport in transport_sockets:
                try:
                    transport.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                transport.close()
            for connection in connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
            for upstream in upstreams:
                raw = getattr(getattr(upstream, "fp", None), "raw", None)
                upstream_socket = getattr(raw, "_sock", None)
                if upstream_socket is not None:
                    try:
                        upstream_socket.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                upstream.close()
            with self._lock:
                handlers = list(self._handler_threads)
            stop_deadline = time.monotonic() + 2
            for handler in handlers:
                handler.join(timeout=max(0, stop_deadline - time.monotonic()))
            self._stats["handler_cleanup_complete"] = not any(handler.is_alive() for handler in handlers)
            self._server.server_close()
            self._thread.join(timeout=2)
            self._stats["server_thread_stopped"] = not self._thread.is_alive()
            self._server = None
            try:
                info = self.socket_path.lstat()
                if (info.st_dev, info.st_ino) == self._socket_identity and stat.S_ISSOCK(info.st_mode):
                    self.socket_path.unlink()
            except FileNotFoundError:
                pass
            self._stats["ended_at"] = time.time()
        self._api_key = self._token = None
        self._stats["token_revoked"] = self._token is None
        self._stats["socket_unlinked"] = not self.socket_path.exists() and not self.socket_path.is_symlink()
        with self._lock:
            if self._event_output is not None:
                self._event_output.flush()
                self._event_output.close()
                self._event_output = None
        return False
