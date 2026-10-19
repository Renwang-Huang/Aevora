#!/usr/bin/env python3
"""One public live SSE request through the trusted completion-aware Broker.

No Participant task, private benchmark material, or credential bytes are logged.
Observed API model labels do not attest the remote model's internal weights.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from integrations.gateway_broker import SecureModelBroker
    from integrations.participant_bridge import UnixConnection
    from integrations.providers import ProviderConfig
    from scripts.m11_calibration import tls_probe
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.absolute()
    archive.mkdir(parents=True, exist_ok=False)
    url = "https://api.renwang-huang.top/v1"
    record = {"started_at": datetime.now(timezone.utc).isoformat(), "tls": tls_probe(url),
        "scope": "LIVE_PUBLIC_SYNTHETIC_CONNECTIVITY_NOT_EPISODE_CHALLENGE",
        "requested_model": "gpt-5.6-terra", "requested_effort": "max",
        "completion_policy": "completion-aware", "total_response_deadline_seconds": None}
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="of-m11-live-probe-") as temporary:
        token = secrets.token_urlsafe(32)
        broker = SecureModelBroker(ProviderConfig(base_url=url),
            Path(os.environ["ORDERFLOW_GATEWAY_SECRET_PATH"]), run_id=str(uuid.uuid4()),
            socket_path=Path(temporary) / "broker.sock", run_token=token,
            completion_policy="completion-aware", request_timeout=None, token_ttl_seconds=None,
            request_budget=4, max_concurrency=1, expected_model="gpt-5.6-terra", expected_effort="max",
            event_path=archive / "gateway_transport_events.jsonl")
        try:
            with broker:
                connection = UnixConnection(str(broker.socket_path), timeout=None)
                try:
                    connection.request("POST", "/v1/responses", body=json.dumps({
                        "model": "gpt-5.6-terra", "reasoning": {"effort": "max"},
                        "input": "Reply with exactly ORDERFLOW_CONNECTIVITY_OK.",
                        "max_output_tokens": 1024, "store": False, "stream": True}).encode(),
                        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
                    response = connection.getresponse()
                    record["http_status"] = response.status
                    events = []
                    terminal = None
                    # Parse actual provider SSE; never synthesize progress events.
                    for line in response:
                        if not line.startswith(b"data: ") or line.strip() == b"data: [DONE]":
                            continue
                        event = json.loads(line[6:])
                        events.append(event.get("type", "UNAVAILABLE"))
                        if event.get("type") == "response.completed":
                            value = event.get("response", {})
                            terminal = {"response_id": value.get("id"), "actual_model": value.get("model"),
                                "actual_effort": value.get("reasoning", {}).get("effort"),
                                "status": value.get("status"), "usage": value.get("usage")}
                    record.update(sse_event_types=events, terminal=terminal)
                finally:
                    connection.close()
        finally:
            record["broker"] = broker.metadata
            record["ended_at"] = datetime.now(timezone.utc).isoformat()
            record["elapsed_seconds"] = time.monotonic() - start
            terminal = record.get("terminal") or {}
            record["status"] = "PASS" if (record.get("http_status") == 200 and
                terminal.get("status") == "completed" and terminal.get("actual_model") == "gpt-5.6-terra" and
                terminal.get("actual_effort") == "max" and record["broker"].get("handler_cleanup_complete") is True) else "FAIL"
            (archive / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
