"""Thin request-API transport over the unchanged generic SQLite observer.

Contains no assertions, expected outcomes, repair hints or private task logic.
Mounted alone with the old transport and the current query-only Clock socket.
"""
import argparse
import contextlib
import importlib.util
import json
import os
import sys

REQUEST_METHODS = ("claim_request", "renew_request", "complete_request",
                   "cancel_request", "get_request")
BASE_METHODS = ("initialize", "create_order", "cancel_order", "reserve_inventory",
                "release_inventory", "get_order", "get_inventory", "audit")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-socket")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("orderflow_generic_endpoint", "/worker_base.py")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    control = base.WorkerControlClient(args.control_socket) if args.control_socket else None
    observer = base.SQLiteObserver(control.notify, "/data/business.sqlite").install() if control else None
    # Public dependency configuration precedes candidate import. Implementations
    # may consume this channel through the public abstraction or equivalently.
    os.environ["ORDERFLOW_CLOCK_QUERY"] = "/clock-query.sock"
    sys.path.insert(0, "/workspace")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from app.service import OrderFlow
            flow = OrderFlow("/data/business.sqlite")
            if control:
                flow._schedule_checkpoint = control.checkpoint
            methods = {name: getattr(flow, name) for name in (*BASE_METHODS, *REQUEST_METHODS)}
    except Exception as error:
        base.write_message({"ready": False, "error": base.error_message(error)})
        if control:
            control.close()
        return 2
    base.write_message({"ready": True, "protocol_version": 1, "clock_query_protocol": 1,
                        "request_methods": list(REQUEST_METHODS)})
    try:
        while True:
            line = sys.stdin.readline(8 * 1024**2 + 1)
            if not line:
                break
            request_id = None
            try:
                if len(line.encode()) > 8 * 1024**2 or not line.endswith("\n"):
                    raise ValueError("RPC request exceeds its bounded message size")
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("RPC request must be an object")
                request_id = request.get("id")
                method, params = request["method"], request.get("params", {})
                if (method not in methods and method != "batch") or not isinstance(params, dict):
                    raise ValueError("Unknown RPC method or invalid parameters")
                if not isinstance(request.get("execution", {}), dict) or request.get("execution", {}):
                    raise ValueError("Unknown worker execution options")
                if control:
                    control.method = method
                with contextlib.redirect_stdout(sys.stderr):
                    result = (base.execute_batch(flow, methods, **params) if method == "batch"
                              else methods[method](**params))
                if control:
                    control.notify("before_response", ok=True, transaction_observer=observer is not None,
                                   sqlite_observer=observer.observation())
                base.write_message({"id": request_id, "ok": True, "result": result})
            except Exception as error:
                if control:
                    control.notify("before_response", ok=False, transaction_observer=observer is not None,
                                   sqlite_observer=observer.observation())
                base.write_message({"id": request_id, "ok": False, "error": base.error_message(error)})
    finally:
        if control:
            control.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
