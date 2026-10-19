"""Equivalent six business assertions for network-denied Native commands.

The original UDS suite is unchanged and must still be reported independently.
This entry verifies real SQLite business semantics with an injected local Clock;
it does NOT validate Clock sockets, transport or cross-process authority.
Run: python tests/public/dv02_inprocess_contract.py
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import threading


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app import request_clock
    spec = importlib.util.spec_from_file_location("original_public_contract", Path(__file__).with_name("test_episode_d_v02.py"))
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)

    class LocalClock:
        def __init__(self):
            self.tick = 0
            self.lock = threading.Lock()

        def now(self):
            with self.lock:
                return self.tick

        def advance(self, amount):
            if type(amount) is not int or amount < 0:
                raise ValueError("nonnegative local ticks required")
            with self.lock:
                self.tick += amount

    @contextmanager
    def environment(path):
        clock = LocalClock()
        before = request_clock.now
        request_clock.now = clock.now
        try:
            yield clock
        finally:
            request_clock.now = before

    original.diagnostic_environment = environment
    return original.main()


if __name__ == "__main__":
    raise SystemExit(main())
