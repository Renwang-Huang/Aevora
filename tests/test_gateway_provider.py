"""SSE terminal-frame admission regressions, using local synthetic transport.

An upstream can keep its HTTP connection open after a complete Responses
terminal event. The terminal frame, rather than a later socket EOF, ends that
response. Incomplete terminal frames must retain their slot and cannot pass.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from test_gateway_broker import _broker, _payload, _request, _response, _sse, _wait_records


@contextmanager
def _held_terminal_upstream(*, partial_terminal=False):
    partial_sent = threading.Event()
    completed_sent = threading.Event()
    release_completion = threading.Event()
    release_eof = threading.Event()
    if not partial_terminal:
        release_completion.set()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def chunk(data):
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

            try:
                created = _sse({"type": "response.created", "response": _response(status="in_progress")})
                terminal = _sse({"type": "response.completed", "response": _response()})
                chunk(created + terminal[:-1] if partial_terminal else created + terminal)
                partial_sent.set()
                if partial_terminal:
                    if not release_completion.wait(4):
                        return
                    chunk(terminal[-1:])
                completed_sent.set()
                # Deliberately send no chunked EOF until test cleanup. This is
                # an owned listener, not an actual gateway or a real secret.
                if release_eof.wait(4):
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
            except (OSError, ValueError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{server.server_port}/v1", "partial_sent": partial_sent,
               "completed_sent": completed_sent, "release_completion": release_completion,
               "release_eof": release_eof}
    finally:
        release_completion.set()
        release_eof.set()
        server.shutdown()
        server.server_close()
        thread.join(2)


def _start_response(broker):
    finished = threading.Event()
    captured = {}

    def client():
        try:
            captured["response"] = _request(broker, method="POST", route="/v1/responses", body=_payload(stream=True))
        except Exception as error:
            captured["failure_type"] = type(error).__name__
        finally:
            finished.set()

    thread = threading.Thread(target=client, daemon=True)
    thread.start()
    return finished, captured, thread


def test_completed_sse_releases_admission_without_upstream_eof_for_successive_rounds():
    with _held_terminal_upstream() as upstream, _broker(upstream, max_concurrency=1,
                                                       request_budget=4, request_timeout=3) as broker:
        for round_number in range(3):
            finished, captured, thread = _start_response(broker)
            try:
                assert upstream["completed_sent"].wait(1)
                assert finished.wait(0.75), "Complete response still waits for upstream EOF and holds its admission slot"
                assert "failure_type" not in captured
                status, _, body = captured["response"]
                assert status == 200
                assert b"response.completed" in body
                assert b"event: error" not in body
                metadata = _wait_records(broker, round_number + 1)
                assert metadata["active_requests"] == 0
                assert metadata["request_records"][-1]["outcome"] == "COMPLETED"
                assert not upstream["release_eof"].is_set()
            finally:
                if not finished.is_set():
                    upstream["release_eof"].set()
                thread.join(4)
        assert broker.metadata["peak_concurrency"] == 1
        assert broker.metadata["upstream_requests"] == 3
        assert broker.metadata["error_counts"] == {}


def test_partial_completed_frame_retains_slot_until_full_frame_is_forwarded():
    with _held_terminal_upstream(partial_terminal=True) as upstream, _broker(
            upstream, max_concurrency=1, request_budget=4, request_timeout=3) as broker:
        finished, captured, thread = _start_response(broker)
        try:
            assert upstream["partial_sent"].wait(1)
            assert not finished.wait(0.05), "Unterminated response.completed frame passed prematurely"
            assert _request(broker)[0] == 429
            assert broker.metadata["active_requests"] == 1
            upstream["release_completion"].set()
            assert upstream["completed_sent"].wait(1)
            assert finished.wait(0.75), "Fully terminated completion still waits for upstream EOF"
            assert "failure_type" not in captured
            assert captured["response"][0] == 200
            assert b"response.completed" in captured["response"][2]
            metadata = _wait_records(broker, 2)
            assert metadata["active_requests"] == 0
            successful = [record for record in metadata["request_records"] if record["outcome"] == "COMPLETED"]
            assert len(successful) == 1
            assert successful[0]["response_completed"] is True
            assert metadata["error_counts"] == {"RUN_CONCURRENCY_LIMIT": 1}
            assert not upstream["release_eof"].is_set()
        finally:
            upstream["release_completion"].set()
            upstream["release_eof"].set()
            thread.join(4)
