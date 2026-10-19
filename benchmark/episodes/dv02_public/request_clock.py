"""Public authoritative time: monotonic millisecond integer ticks.

ORDERFLOW_CLOCK_QUERY selects the controlled Unix-domain query endpoint. Its
only request is exactly NOW followed by a newline. The response is one bounded
JSON line containing only tick, a canonical nonnegative decimal string. This
client has no time-setting operation. Local diagnosis may own its own separate
time server; the service's shared authority is controlled by its deployment.
Clock/transport errors remain infrastructure errors, never stock exhaustion.
"""
import json
import os
import re
import socket
import time

from app.request_errors import ClockUnavailable

MAX_CLOCK_LINE_BYTES = 16384
CLOCK_TIMEOUT_SECONDS = 2.0
DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")


def now() -> int:
    endpoint = os.environ.get("ORDERFLOW_CLOCK_QUERY")
    if endpoint is None:
        return time.monotonic_ns() // 1_000_000
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(CLOCK_TIMEOUT_SECONDS)
            connection.connect(endpoint)
            connection.sendall(b"NOW\n")
            with connection.makefile("rb") as stream:
                raw = stream.readline(MAX_CLOCK_LINE_BYTES + 1)
        if len(raw) > MAX_CLOCK_LINE_BYTES or not raw.endswith(b"\n"):
            raise ValueError("Clock reply exceeds its protocol bound")

        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate Clock field")
                value[key] = item
            return value

        value = json.loads(raw, object_pairs_hook=unique)
        if (not isinstance(value, dict) or set(value) != {"tick"}
                or not isinstance(value["tick"], str) or not DECIMAL.fullmatch(value["tick"])):
            raise ValueError("Clock reply violates the public protocol")
        return int(value["tick"])
    except (OSError, ValueError, TypeError, RecursionError):
        raise ClockUnavailable("Authoritative Clock query unavailable or invalid") from None
