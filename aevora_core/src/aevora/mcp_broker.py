"""Authenticated per-run transport to the official trusted MCP SDK server.

This is a bounded transport and authority boundary, not an agent orchestrator.
Only the trusted host can configure its subprocess or database environment.
No upstream credential or authorization header is written to its event log.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid


PROTOCOL = "aevora-mcp-uds-v1"
TOOLS = frozenset({"resolve_experience", "build_evidence_bundle", "record_decision"})
MAX_MESSAGE_BYTES = 262_144
_REVOCATION_DISCARD_CHUNK_BYTES = 65_536
_REVOCATION_DISCARD_MAX_READS = 4
_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
_TOKEN = re.compile(r"[A-Za-z0-9._~-]{32,256}")
_NONCE = re.compile(r"[0-9a-f]{64}")
_SECRET_KEY = re.compile(r"(?i)^(?:authorization|proxy_authorization|token|run_token|aevora_run_token|"
                         r"secret|password|api_key|credentials|credential|access_token|refresh_token|client_secret)$")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _message(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
        raise ValueError("Frame size or terminator")
    value = json.loads(raw, object_pairs_hook=_no_duplicates,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if not isinstance(value, dict):
        raise ValueError("Object required")
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 16 or nodes > 20_000:
            raise ValueError("JSON shape bound")
        if isinstance(item, dict):
            pending.extend((part, depth + 1) for part in item.values())
        elif isinstance(item, list):
            pending.extend((part, depth + 1) for part in item)
    return value


def _redact(value, token):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.search(key) else _redact(part, token)
                for key, part in value.items()}
    if isinstance(value, list):
        return [_redact(part, token) for part in value]
    if isinstance(value, str):
        result = value.replace(token, "[REDACTED]") if token else value
        result = re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b", "[REDACTED]", result)
        result = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", result)
        return re.sub(r"(?i)(\b(?:password|api_key|access_token|refresh_token|client_secret)\s*[:=]\s*)"
                      r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;}]+)", r"\1[REDACTED]", result)
    return value


def _discard_revoked_input(connection) -> tuple[int, int, bool]:
    """After owner revocation, discard a finite unread kernel queue.

    SHUT_RDWR prevents new peer writes. Reads are nonblocking, at most four
    64 KiB chunks and MAX_MESSAGE_BYTES total. Bytes are never parsed, logged
    or forwarded. Linux may still report reset if an adversarial queue exceeds
    these bounds; revocation and bounded cleanup take precedence over EOF.
    """
    discarded, reads = 0, 0
    try:
        connection.shutdown(socket.SHUT_RDWR)
        connection.setblocking(False)
    except OSError:
        return discarded, reads, False
    while discarded < MAX_MESSAGE_BYTES and reads < _REVOCATION_DISCARD_MAX_READS:
        reads += 1
        try:
            chunk = connection.recv(min(_REVOCATION_DISCARD_CHUNK_BYTES,
                                        MAX_MESSAGE_BYTES - discarded))
        except OSError:
            break
        if not chunk:
            break
        discarded += len(chunk)
    return discarded, reads, (discarded == MAX_MESSAGE_BYTES or
                              reads == _REVOCATION_DISCARD_MAX_READS)


class MCPBroker:
    """Owner-lifetime scoped UDS authority, with finite per-call bounds.

    ``server_command`` is a trusted-host test injection. Participants cannot
    select executables, environment, socket paths or authority context.
    """

    def __init__(self, *, run_id: str, public_context: dict, socket_path: Path,
                 run_token: str, event_path: Path, max_connections: int = 4,
                 request_budget: int = 4096, request_timeout: float = 60,
                 allowed_peer_uid: int | None = None, server_command: list[str] | None = None,
                 server_environment: dict[str, str] | None = None, enable_proposals: bool = False,
                 protocol_profile: str = "aevora.mcp/1.2", v2_config_path: str | None = None):
        if not isinstance(run_id, str) or not _ID.fullmatch(run_id):
            raise ValueError("A stable bounded run ID is required")
        if not isinstance(run_token, str) or not _TOKEN.fullmatch(run_token):
            raise ValueError("Dedicated scoped token required")
        if not isinstance(public_context, dict) or len(json.dumps(public_context, allow_nan=False).encode()) > 8192:
            raise ValueError("Bounded public context required")
        if type(max_connections) is not int or not 1 <= max_connections <= 4:
            raise ValueError("Connection concurrency must be 1 through 4")
        if type(request_budget) is not int or not 1 <= request_budget <= 10_000:
            raise ValueError("A finite bounded request budget is required")
        if isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float)) or not 0 < request_timeout <= 120:
            raise ValueError("Each active request must have a finite timeout")
        self.run_id, self.public_context = run_id, json.loads(json.dumps(public_context))
        if type(enable_proposals) is not bool:
            raise ValueError('Explicit trusted proposal capability required')
        if protocol_profile not in {"aevora.mcp/1.2", "aevora.mcp/2.0.0-rc2"}:
            raise ValueError("Explicit supported MCP profile required")
        if (protocol_profile == "aevora.mcp/2.0.0-rc2") != (v2_config_path is not None):
            raise ValueError("Explicit v2 trusted configuration required")
        if protocol_profile != "aevora.mcp/1.2" and not enable_proposals:
            raise ValueError("v2 requires the four-tool catalog")
        self.protocol_profile, self.v2_config_path = protocol_profile, v2_config_path
        self._v2_guard = None
        self.enable_proposals = enable_proposals
        self.tools = TOOLS | {'propose_experience'} if enable_proposals else TOOLS
        self.socket_path, self.event_path = Path(socket_path), Path(event_path)
        self.max_connections, self.request_budget = max_connections, request_budget
        self.request_timeout = float(request_timeout)
        self.allowed_peer_uid = os.getuid() if allowed_peer_uid is None else allowed_peer_uid
        self._token = run_token
        self._command = server_command or [sys.executable, "-u", "-m", "aevora.mcp_server"]
        if not all(isinstance(part, str) and part and "\0" not in part for part in self._command):
            raise ValueError("Trusted server argv must be nonempty strings")
        # The model key and host Codex identity never enter this environment.
        self._environment = {key: value for key, value in os.environ.items()
                             if key in {"PATH", "LANG", "SSL_CERT_FILE", "PYTHONPATH"}
                             or key.startswith("AEVORA_FALKORDB_")}
        if server_environment is not None:
            self._environment.update(server_environment)
        self._lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(max_connections)
        self._stopped = threading.Event()
        self._nonces, self._connections, self._handlers, self._children = set(), set(), set(), set()
        self._requests = 0
        self._sequence = 0
        self._events = None
        self._listener = self._thread = self._socket_identity = None
        self._stats = {"run_id": run_id, "status": "NOT_STARTED", "source": "aevora.authenticated_mcp_broker",
                       "authority": "PER_RUN_BEARER_AND_KERNEL_PEER_UID", "agent_thread_id": "UNAVAILABLE",
                       "started_at": None, "ended_at": None, "accepted_connections": 0,
                       "sdk_children_started": 0, "sdk_children_closed": 0,
                       "owner_revocation_discarded_bytes": 0,
                       "owner_revocation_discard_read_calls": 0,
                       "owner_revocation_discard_budget_reached": 0,
                       "rejections": Counter(), "tools": sorted(self.tools),
                       "token_lifetime": "BROKER_OWNER_LIFETIME", "request_timeout_seconds": self.request_timeout,
                       "max_connections": max_connections, "request_budget": request_budget}
        self._stats.update(pinned_public_context=self.public_context,
                           pinned_public_context_sha256=hashlib.sha256(json.dumps(self.public_context, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
                           context_origin="TRUSTED_CALLER_PINNED_PUBLIC_FACTS")

    @property
    def metadata(self) -> dict:
        with self._lock:
            result = dict(self._stats)
            result["rejections"] = dict(self._stats["rejections"])
            result.update(active_connections=len(self._connections), active_sdk_children=len(self._children),
                          requests=self._requests, event_count=self._sequence,
                          token_revoked=self._token is None,
                          socket_unlinked=not self.socket_path.exists() and not self.socket_path.is_symlink())
            return result

    def _event(self, category: str, connection_id: str | None = None, *, raw: bytes | None = None,
               direction: str | None = None, **facts) -> None:
        with self._lock:
            self._sequence += 1
            event = {"sequence": self._sequence, "timestamp": _timestamp(), "run_id": self.run_id,
                     "source": "aevora.authenticated_mcp_broker", "category": category,
                     "connection_id": connection_id, **_redact(facts, self._token)}
            if raw is not None:
                safe = _redact(_message(raw), self._token)
                # Store exact raw bytes when no redaction is needed; otherwise
                # explicitly identify the sanitized representation and its SHA.
                if safe == _message(raw):
                    archived = raw
                    redaction = "NONE"
                else:
                    archived = json.dumps(safe, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
                    redaction = "APPLIED"
                event.update(direction=direction, raw_json=archived.decode("utf-8"),
                             archived_message_sha256=hashlib.sha256(archived).hexdigest(),
                             redaction=redaction, sha256_scope="ARCHIVED_MESSAGE_BYTES")
            if self._events is not None:
                self._events.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                self._events.flush()

    def _reject(self, category: str, connection_id: str | None = None) -> None:
        with self._lock:
            self._stats["rejections"][category] += 1
        self._event("REJECTED", connection_id, reason=category)

    def __enter__(self):
        if self._listener is not None or self._stopped.is_set():
            raise RuntimeError("MCP broker is single use")
        parent = self.socket_path.parent
        info = parent.lstat()
        if (not self.socket_path.is_absolute() or parent.resolve() != parent or
                not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or
                self.socket_path.exists() or self.socket_path.is_symlink() or len(os.fsencode(self.socket_path)) > 107):
            raise ValueError("MCP channel requires a private owned directory and fresh UDS path")
        if not hasattr(socket, "SO_PEERCRED"):
            raise RuntimeError("Kernel peer credentials are required")
        self.event_path.parent.mkdir(parents=True, exist_ok=True)
        if self.event_path.is_symlink() or self.event_path.exists():
            raise ValueError("MCP raw evidence must be exclusively created")
        fd = os.open(self.event_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self._events = os.fdopen(fd, "w", encoding="utf-8")
        try:
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            info = self.socket_path.lstat()
            self._socket_identity = (info.st_dev, info.st_ino)
            self._listener.listen(self.max_connections)
            self._listener.settimeout(0.2)
            self._stats.update(status="STARTED", started_at=_timestamp())
            self._thread = threading.Thread(target=self._accept, name="aevora-mcp-accept", daemon=True)
            self._thread.start()
            self._event("BROKER_STARTED")
            return self
        except BaseException:
            self.close()
            raise

    def _accept(self):
        while not self._stopped.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self._slots.acquire(blocking=False):
                self._reject("CONCURRENCY_LIMIT")
                connection.close()
                continue
            with self._lock:
                self._connections.add(connection)
                handler = threading.Thread(target=self._handle, args=(connection,), name="aevora-mcp-connection", daemon=True)
                self._handlers.add(handler)
            handler.start()

    def _valid_request(self, value: dict, seen: set) -> str | int | None:
        if value.get("jsonrpc") != "2.0" or not isinstance(value.get("method"), str):
            raise ValueError("INVALID_JSONRPC")
        if set(value) - {"jsonrpc", "id", "method", "params"}:
            raise ValueError("INVALID_ENVELOPE")
        method = value["method"]
        if method not in {"initialize", "notifications/initialized", "notifications/cancelled", "ping", "tools/list", "tools/call",
                          "resources/list", "resources/templates/list", "prompts/list"}:
            raise ValueError("METHOD_NOT_ALLOWED")
        identifier = value.get("id")
        if method.startswith("notifications/"):
            if "id" in value:
                raise ValueError("NOTIFICATION_ID")
        else:
            if not (type(identifier) is int and 0 <= identifier <= 2**63 - 1 or
                    isinstance(identifier, str) and 0 < len(identifier) <= 128):
                raise ValueError("INVALID_REQUEST_ID")
            key = (type(identifier).__name__, identifier)
            if key in seen:
                raise ValueError("REQUEST_ID_REPLAY")
            seen.add(key)
        params = value.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("INVALID_PARAMS")
        if method == "tools/call":
            if set(params) - {"name", "arguments", "_meta"} or params.get("name") not in self.tools or not isinstance(params.get("arguments", {}), dict):
                raise ValueError("TOOL_NOT_ALLOWED")
        return identifier

    def _handle(self, connection):
        connection_id = str(uuid.uuid4())
        process = None
        selector = None
        ready = False
        stderr_bytes = 0
        try:
            connection.settimeout(10)
            peer_pid, peer_uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            reader = connection.makefile("rb")
            raw = reader.readline(4097)
            try:
                auth = _message(raw)
            except (ValueError, UnicodeDecodeError, RecursionError):
                auth = {}
            with self._lock:
                accepted = (len(raw) <= 4096 and set(auth) == {"protocol", "run_id", "token", "nonce"}
                            and auth.get("protocol") == PROTOCOL and auth.get("run_id") == self.run_id
                            and isinstance(auth.get("token"), str) and self._token is not None
                            and _TOKEN.fullmatch(auth["token"])
                            and hmac.compare_digest(auth["token"], self._token) and peer_uid == self.allowed_peer_uid
                            and isinstance(auth.get("nonce"), str) and _NONCE.fullmatch(auth["nonce"])
                            and auth["nonce"] not in self._nonces and len(self._nonces) < self.request_budget)
                if accepted:
                    self._nonces.add(auth["nonce"])
                    self._stats["accepted_connections"] += 1
            del auth, raw
            if not accepted:
                self._reject("AUTHENTICATION_OR_NONCE_REPLAY", connection_id)
                connection.sendall(b'{"aevora_transport":"REJECTED"}\n')
                return
            self._event("AUTHENTICATED", connection_id, peer_pid=peer_pid, peer_uid=peer_uid,
                        peer_identity_source="KERNEL_SO_PEERCRED", agent_thread_id="UNAVAILABLE")
            process = subprocess.Popen(self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=self._environment, start_new_session=True, bufsize=0)
            with self._lock:
                self._children.add(process)
                self._stats["sdk_children_started"] += 1
            os.set_blocking(process.stdin.fileno(), False)
            authority = {"protocol": PROTOCOL, "run_id": self.run_id,
                         "public_context": self.public_context, "connection_id": connection_id}
            if self.enable_proposals:
                authority['enable_proposals'] = True
            if self.v2_config_path is not None:
                authority.update(protocol_profile=self.protocol_profile, v2_config_path=self.v2_config_path)
            self._write_input(process, json.dumps(authority, separators=(",", ":")).encode() + b"\n")
            connection.sendall(b'{"aevora_transport":"READY"}\n')
            ready = True
            # reader has consumed only the authority header. A proxy waits for
            # READY before sending initialize, so no buffered client bytes exist.
            reader.close()
            connection.settimeout(None)
            selector = selectors.DefaultSelector()
            selector.register(connection, selectors.EVENT_READ, "client")
            selector.register(process.stdout, selectors.EVENT_READ, "server")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            buffers = {"client": bytearray(), "server": bytearray()}
            seen = set()
            pending = {}
            request_methods = {}
            initialized = False
            while not self._stopped.is_set():
                if any(time.monotonic() > deadline for deadline in pending.values()):
                    self._reject("MCP_REQUEST_TIMEOUT", connection_id)
                    break
                events = selector.select(0.2)
                for key, _ in events:
                    source = key.data
                    if source == "stderr":
                        chunk = os.read(process.stderr.fileno(), 65536)
                        if not chunk:
                            selector.unregister(process.stderr)
                            continue
                        remaining = max(0, 65536 - stderr_bytes)
                        stderr_bytes += len(chunk)
                        if remaining:
                            text = chunk[:remaining].decode("utf-8", errors="replace")
                            safe = _redact(text, self._token)
                            self._event("SDK_STDERR", connection_id, archived_text=safe,
                                        archived_text_sha256=hashlib.sha256(safe.encode()).hexdigest(),
                                        redaction="APPLIED" if safe != text else "NONE",
                                        sha256_scope="ARCHIVED_UTF8_TEXT", decoding="UTF8_ERRORS_REPLACE",
                                        capture_limit_bytes=65536)
                        continue
                    chunk = connection.recv(65536) if source == "client" else os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        return
                    buffer = buffers[source]
                    buffer.extend(chunk)
                    if len(buffer) > MAX_MESSAGE_BYTES and b"\n" not in buffer[:MAX_MESSAGE_BYTES]:
                        raise ValueError("MESSAGE_SIZE_LIMIT")
                    while b"\n" in buffer:
                        index = buffer.index(b"\n") + 1
                        raw = bytes(buffer[:index]); del buffer[:index]
                        value = _message(raw)
                        if source == "client":
                            identifier = self._valid_request(value, seen)
                            method = value["method"]
                            if not initialized and method != "initialize":
                                raise ValueError("INITIALIZE_REQUIRED")
                            if initialized and method == "initialize":
                                raise ValueError("DUPLICATE_INITIALIZE")
                            with self._lock:
                                if self._requests >= self.request_budget:
                                    raise ValueError("REQUEST_BUDGET_EXCEEDED")
                                self._requests += 1
                            self._event("JSONRPC", connection_id, raw=raw, direction="PARTICIPANT_TO_OFFICIAL_SDK")
                            if identifier is not None:
                                request_key = (type(identifier).__name__, identifier)
                                pending[request_key] = time.monotonic() + self.request_timeout
                                request_methods[request_key] = method
                            self._write_input(process, raw)
                        else:
                            if value.get("jsonrpc") != "2.0" or set(value) - {"jsonrpc", "id", "result", "error", "method", "params"}:
                                raise ValueError("SDK_PROTOCOL_ERROR")
                            identifier = value.get("id")
                            if identifier is not None:
                                if ("method" in value or ("result" in value) == ("error" in value)
                                        or "result" in value and not isinstance(value["result"], dict)
                                        or "error" in value and not isinstance(value["error"], dict)):
                                    raise ValueError("SDK_PROTOCOL_ERROR")
                                response_key = (type(identifier).__name__, identifier)
                                if response_key not in pending:
                                    raise ValueError("UNMATCHED_SDK_RESPONSE")
                                pending.pop(response_key)
                                method = request_methods.pop(response_key)
                                result = value.get("result")
                                if isinstance(result, dict):
                                    empty_catalogs = {"resources/list": "resources", "resources/templates/list": "resourceTemplates", "prompts/list": "prompts"}
                                    if method in empty_catalogs and result.get(empty_catalogs[method]) != []:
                                        raise ValueError("SDK_UNAUTHORIZED_RESOURCE_OR_PROMPT_CATALOG")
                                    if method == "tools/list":
                                        entries = result.get("tools")
                                        if not isinstance(entries, list) or len(entries) != len(self.tools) or not all(isinstance(entry, dict) for entry in entries) or {entry.get("name") for entry in entries} != self.tools:
                                            raise ValueError("SDK_UNAUTHORIZED_TOOL_CATALOG")
                                if isinstance(value.get("result"), dict) and "protocolVersion" in value["result"]:
                                    initialized = True
                            elif value.get("method") not in {"notifications/progress", "notifications/message", "notifications/tools/list_changed"} or "result" in value or "error" in value:
                                raise ValueError("SDK_PROTOCOL_ERROR")
                            self._event("JSONRPC", connection_id, raw=raw, direction="OFFICIAL_SDK_TO_PARTICIPANT")
                            # A participant that stops consuming responses must
                            # not hold the trusted transport in sendall forever.
                            connection.settimeout(self.request_timeout)
                            try:
                                if self.v2_config_path is None:
                                    connection.sendall(raw)
                                else:
                                    # Owner revocation and send are serialized locally.
                                    # The DB check/network interval is explicitly not a distributed transaction.
                                    with self._lock:
                                        if self._stopped.is_set() or self._token is None:
                                            raise ValueError("REVOKED")
                                        if self._v2_guard is None:
                                            from .mcp_v2 import OutputGuard
                                            self._v2_guard = OutputGuard(self.v2_config_path, self._environment)
                                        checked = time.monotonic()
                                        authorization = self._v2_guard.check(value)
                                        connection.sendall(raw)
                                        self._event("V2_RESPONSE_DELIVERED", connection_id,
                                                    read_scope=authorization,
                                                    check_to_send_seconds=time.monotonic()-checked,
                                                    delivered_bytes=len(raw),
                                                    delivered_sha256=hashlib.sha256(raw).hexdigest())
                            finally:
                                connection.settimeout(None)
                if process.poll() is not None:
                    break
        except (OSError, ValueError, TypeError, UnicodeDecodeError, RecursionError, subprocess.SubprocessError) as error:
            category = str(error) if isinstance(error, ValueError) and str(error).isupper() and len(str(error)) < 80 else type(error).__name__.upper()
            self._reject(category, connection_id)
            if not ready:
                try:
                    connection.sendall(b'{"aevora_transport":"REJECTED","reason":"SDK_STARTUP_FAILED"}\n')
                except OSError:
                    pass
        finally:
            if selector is not None:
                selector.close()
            if process is not None:
                self._stop_child(process)
                with self._lock:
                    if process in self._children:
                        self._children.remove(process)
                        self._stats["sdk_children_closed"] += 1
                self._event("SDK_CHILD_CLOSED", connection_id, exit_code=process.returncode,
                            stderr_observed_bytes=stderr_bytes,
                            stderr_truncated=stderr_bytes > 65536)
            if self._stopped.is_set():
                discarded, reads, reached = _discard_revoked_input(connection)
                with self._lock:
                    self._stats["owner_revocation_discarded_bytes"] += discarded
                    self._stats["owner_revocation_discard_read_calls"] += reads
                    self._stats["owner_revocation_discard_budget_reached"] += int(reached)
            connection.close()
            with self._lock:
                self._connections.discard(connection)
                self._handlers.discard(threading.current_thread())
            self._slots.release()

    def _write_input(self, process, raw: bytes) -> None:
        """Bound pipe backpressure, including a broken or unresponsive SDK."""
        deadline = time.monotonic() + self.request_timeout
        view = memoryview(raw)
        with selectors.DefaultSelector() as writable:
            writable.register(process.stdin, selectors.EVENT_WRITE)
            while view:
                if self._stopped.is_set() or time.monotonic() > deadline:
                    raise ValueError("SDK_PIPE_WRITE_TIMEOUT_OR_CANCELLED")
                if not writable.select(0.2):
                    continue
                try:
                    written = os.write(process.stdin.fileno(), view)
                except BlockingIOError:
                    continue
                if written <= 0:
                    raise ValueError("SDK_PIPE_WRITE_FAILED")
                view = view[written:]

    @staticmethod
    def _stop_child(process):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
        # A trusted SDK extension may have created helpers. Reap the dedicated
        # group even if its direct parent has already exited after SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()

    def close(self):
        self._stopped.set()
        if self._listener is not None:
            self._listener.close()
        with self._lock:
            connections, children = list(self._connections), list(self._children)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for child in children:
            self._stop_child(child)
        if self._thread is not None:
            self._thread.join(timeout=3)
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            handler.join(timeout=3)
        if self._socket_identity is not None:
            try:
                info = self.socket_path.lstat()
                if (info.st_dev, info.st_ino) == self._socket_identity and stat.S_ISSOCK(info.st_mode):
                    self.socket_path.unlink()
            except FileNotFoundError:
                pass
        with self._lock:
            if self._v2_guard is not None and not self._handlers and not self._children:
                self._v2_guard.repo.transport.close()
                self._stats["v2_repository_closed"] = True
            self._token = None
            self._stats.update(status="CLOSED", ended_at=_timestamp(),
                               server_thread_stopped=self._thread is None or not self._thread.is_alive(),
                               handler_cleanup_complete=not self._handlers and not self._children)
            if self._events is not None:
                self._event("BROKER_CLOSED", cleanup=self.metadata)
                self._events.close()
                self._events = None

    def __exit__(self, *_):
        self.close()


# Descriptive compatibility alias for callers that prefer the longer name.
AevoraMCPBroker = MCPBroker
