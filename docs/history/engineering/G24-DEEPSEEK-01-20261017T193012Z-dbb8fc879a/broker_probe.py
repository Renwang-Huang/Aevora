"""Authenticated DeepSeek /models probe through the production secure broker."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import ssl
import stat
import uuid

from audit import E, write
from integrations.gateway_broker import SecureModelBroker
from integrations.providers import deepseek_provider


def main() -> int:
    provider = deepseek_provider(model="deepseek-flash", effort="max")
    token = "probe-" + uuid.uuid4().hex + uuid.uuid4().hex
    channel = Path("/tmp") / ("g24ds-" + uuid.uuid4().hex[:12])
    channel.mkdir(mode=0o700, parents=True, exist_ok=True)
    event_path = E / "09_evidence" / ("broker_models_transport-" + uuid.uuid4().hex + ".jsonl")
    channel.chmod(0o700)
    broker = SecureModelBroker(
        provider,
        Path("/maintainer/deepseek.token"),
        run_id="models-" + uuid.uuid4().hex,
        socket_path=channel / f"probe-{uuid.uuid4().hex}.sock",
        run_token=token,
        request_budget=4,
        request_timeout=30,
        token_ttl_seconds=300,
        completion_policy="bounded",
        event_path=event_path,
    )
    secret_info = os.stat("/maintainer/deepseek.token")
    parent_info = channel.stat()
    diagnostics = {
        "secret_uid": secret_info.st_uid,
        "secret_mode": oct(secret_info.st_mode & 0o777),
        "secret_nlink": secret_info.st_nlink,
        "secret_regular": stat.S_ISREG(secret_info.st_mode),
        "socket_parent_uid": parent_info.st_uid,
        "socket_parent_mode": oct(parent_info.st_mode & 0o777),
        "socket_path_bytes": len(os.fsencode(broker.socket_path)),
        "peercred": hasattr(socket, "SO_PEERCRED"),
    }
    ssl.create_default_context()
    print(json.dumps({"broker_diagnostics": diagnostics}, sort_keys=True), flush=True)
    result = {"status": "ERROR"}
    with broker:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(30)
            sock.connect(str(broker.socket_path))
            request = (
                "GET /v1/models?client_version=0.163.0 HTTP/1.0\r\n"
                f"Authorization: Bearer {token}\r\n"
                "Accept: application/json\r\n\r\n"
            ).encode()
            sock.sendall(request)
            response = b""
            while block := sock.recv(65536):
                response += block
        head, body = response.split(b"\r\n\r\n", 1)
        status_line = head.splitlines()[0].decode("ascii")
        status_code = int(status_line.split()[1])
        data = json.loads(body)
        ids = sorted(
            item["id"] for item in data.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
        result = {
            "status": "PASS" if "deepseek-flash" in ids else "BLOCKED_MODEL_UNAVAILABLE",
            "http_status": status_code,
            "model_ids": ids,
            "provider": provider.metadata,
        }
    result["broker_diagnostics"] = diagnostics
    result["event_path"] = str(event_path)
    result["broker"] = broker.metadata
    write(E / "09_evidence/BROKER_MODELS_PROBE.json", result)
    print(json.dumps({"status": result["status"], "model_ids": result.get("model_ids", [])}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
