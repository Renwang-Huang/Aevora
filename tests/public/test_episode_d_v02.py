"""Public request-contract regressions using real SQLite and a local Clock.

Run `python tests/public/test_episode_d_v02.py` or the standard Participant
`python -m unittest discover -s tests/public -v` from the public workspace.
The suite is constructed by load_tests() because the maintainer's ordinary app
is a separate earlier API, while this file travels with the D-V02 public app.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest


class DiagnosticClock:
    """A real NOW-only query endpoint for this test's independent local time."""
    def __init__(self, path):
        self.path = str(path)
        self.tick = 0
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(self.path)
        self.listener.listen(8)
        self.listener.settimeout(0.1)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def advance(self, amount):
        if type(amount) is not int or amount < 0:
            raise ValueError("local ticks only advance by nonnegative integers")
        with self.lock:
            self.tick += amount

    def serve(self):
        while not self.closed.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                connection.settimeout(1)
                try:
                    with connection.makefile("rb") as stream:
                        request = stream.readline(64)
                    if request != b"NOW\n":
                        connection.sendall(b'{"error":"unsupported"}\n')
                        continue
                    with self.lock:
                        tick = self.tick
                    connection.sendall(json.dumps({"tick": str(tick)}).encode() + b"\n")
                except OSError:
                    continue

    def close(self):
        self.closed.set()
        self.listener.close()
        self.thread.join(timeout=2)
        Path(self.path).unlink(missing_ok=True)


@contextmanager
def diagnostic_environment(path):
    clock = DiagnosticClock(path)
    old = os.environ.get("ORDERFLOW_CLOCK_QUERY")
    os.environ["ORDERFLOW_CLOCK_QUERY"] = str(path)
    try:
        yield clock
    finally:
        clock.close()
        if old is None:
            os.environ.pop("ORDERFLOW_CLOCK_QUERY", None)
        else:
            os.environ["ORDERFLOW_CLOCK_QUERY"] = old


def contract_suite():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.service import OrderFlow
    from app.request_errors import RequestConflict

    class PublicRequestContract(unittest.TestCase):
        def setUp(self):
            self.directory = tempfile.TemporaryDirectory()
            self.addCleanup(self.directory.cleanup)
            self.root = Path(self.directory.name)
            self.environment = diagnostic_environment(self.root / "clock.sock")
            self.clock = self.environment.__enter__()
            self.addCleanup(self.environment.__exit__, None, None, None)
            self.database = self.root / "business.sqlite"
            self.flow = OrderFlow(self.database)
            self.flow.initialize({"SKU-1": 8}, reset=True)

        def claim(self, request="req", order="order", quantity=2, ttl=10):
            return self.flow.claim_request(request, order, "SKU-1", quantity, ttl)

        def test_claim_records_intent_without_stock_effect(self):
            granted = self.claim()
            self.assertEqual(granted["outcome"], "CLAIM_GRANTED")
            self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 8)
            self.assertNotIn("token", self.flow.get_request("req"))
            busy = self.claim()
            self.assertEqual(busy["outcome"], "CLAIM_BUSY")
            self.assertNotIn("handle", busy)

        def test_completion_retry_and_later_order_cancel(self):
            handle = self.claim()["handle"]
            receipt = self.flow.complete_request(handle)
            self.assertEqual(receipt["outcome"], "COMPLETE_RESERVED")
            self.assertEqual(self.flow.complete_request(handle), receipt)
            self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 6)
            self.flow.cancel_order("order")
            self.assertEqual(self.flow.complete_request(handle), receipt)
            self.assertEqual(self.flow.cancel_request("req")["outcome"], "ALREADY_COMPLETED")
            with self.assertRaises(RequestConflict):
                self.claim(order="different")

        def test_cancelled_intent_has_no_late_order_effect(self):
            handle = self.claim()["handle"]
            receipt = self.flow.cancel_request("req")
            self.assertEqual(receipt["outcome"], "REQUEST_CANCELLED")
            late = self.flow.complete_request(handle)
            self.assertIn(late["outcome"], {"STALE_HANDLE", "REQUEST_CANCELLED"})
            with sqlite3.connect(self.database) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
            self.assertEqual(self.flow.cancel_request("req"), receipt)

        def test_large_ttl_and_renewal_preserve_issuance_history(self):
            granted = self.claim(ttl=2**80)
            handle = granted["handle"]
            self.clock.advance(3)
            renewed = self.flow.renew_request(handle, 2**80)
            self.assertEqual(renewed["outcome"], "CLAIM_RENEWED")
            self.assertEqual(renewed["request"]["deadline"], 2**80 + 3)
            with sqlite3.connect(self.database) as connection:
                issued = connection.execute("SELECT issued_deadline FROM request_claims WHERE token=?",
                                            (handle["token"],)).fetchone()[0]
            self.assertEqual(issued, str(2**80))

        def test_legacy_order_insufficiency_does_not_remove_existing_order(self):
            self.flow.create_order("existing", "SKU-1", 9, reserve=False)
            handle = self.claim(order="existing", quantity=9)["handle"]
            refusal = self.flow.complete_request(handle)
            self.assertEqual(refusal["outcome"], "INSUFFICIENT_INVENTORY_RETRYABLE")
            self.assertEqual(self.flow.get_order("existing")["status"], "created")
            pending = self.flow.get_request("req")
            self.assertEqual(pending["status"], "PENDING")
            self.assertIsNone(pending["deadline"])

        def test_independent_intent_discovers_cancelled_order(self):
            first = self.claim()["handle"]
            self.flow.complete_request(first)
            self.flow.cancel_order("order")
            second = self.claim(request="other")["handle"]
            discovered = self.flow.complete_request(second)
            self.assertEqual(discovered["outcome"], "COMPLETE_DISCOVERED_CANCELLED")
            self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 8)

    return unittest.defaultTestLoader.loadTestsFromTestCase(PublicRequestContract)


def load_tests(loader, tests, pattern):
    """Standard unittest discovery hook; does not import the wrong host app."""
    return contract_suite()


def main():
    result = unittest.TextTestRunner(verbosity=2).run(contract_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
