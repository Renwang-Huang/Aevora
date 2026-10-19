"""Trusted subprocess client for the generic, sandboxed business worker."""

import json
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time

from benchmark.sandbox import sandbox_command


class RemoteExecutionError(RuntimeError):
    """The worker failed to start or broke the RPC protocol."""


class RemoteBusinessError(RuntimeError):
    """An application operation raised an exception in the sandbox."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(f"{kind}: {message}")


class BusinessRPC:
    """One client owns one worker, while its database survives restarts.

    Workers inherit the trusted pytest process group, so an evaluator timeout
    terminates pytest and every worker together. Only candidate code and the
    generic endpoint are mounted into that worker's filesystem.
    """

    def __init__(self, workspace: Path, data_dir: Path, log_path: Path, *,
                 control_socket: Path | None = None, command_wrapper=None,
                 response_timeout: float | None = None):
        self.workspace = workspace.resolve()
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_path
        self.process: subprocess.Popen | None = None
        self._log = None
        self._next_id = 0
        self.control_socket = control_socket
        self.command_wrapper = command_wrapper
        if response_timeout is not None and (type(response_timeout) not in (int, float)
                or not math.isfinite(response_timeout) or not 0 < response_timeout <= 120):
            raise ValueError("RPC response timeout must be finite and in (0, 120]")
        self.response_timeout = response_timeout
        self._request_lock = threading.Lock()
        self._read_buffer = b""
        self.startup_response = None
        self.last_exit_code = None

    def start(self) -> "BusinessRPC":
        # A terminated generation's reader must finish before its descriptors
        # can be replaced by a restarted worker on the same client object.
        with self._request_lock:
            return self._start()

    def _start(self) -> "BusinessRPC":
        if self.process is not None:
            raise RemoteExecutionError("Worker is already running")
        python = Path(sys.base_prefix) / "bin" / "python3.12"
        worker_command = [str(python), "-I", "-B", "/worker.py"]
        if self.control_socket is not None:
            worker_command += ["--control-socket", "/control.sock"]
        command = sandbox_command(
            self.workspace,
            worker_command,
            data_dir=self.data_dir,
            worker=Path(__file__).with_name("worker.py"),
            control_socket=self.control_socket,
        )
        if self.command_wrapper is not None:
            command = self.command_wrapper(command)
        self._read_buffer = b""
        self.last_exit_code = None
        self._log = self.log_path.open("ab")
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self._log, text=True, encoding="utf-8", bufsize=1,
            )
            response = self._read()
            if response.get("ready") is not True or response.get("protocol_version") != 1:
                raise RemoteExecutionError(f"Worker startup failed: {response}")
            self.startup_response = response
        except Exception:
            self.close()
            raise
        return self

    def _read(self, process=None) -> dict:
        # close()/kill() may clear self.process while another thread is waiting
        # for its outstanding response. Keep this invocation's identity stable.
        process = self.process if process is None else process
        if process is None or process.stdout is None:
            raise RemoteExecutionError("Worker is unavailable")
        stdout = process.stdout
        deadline = None if self.response_timeout is None else time.monotonic() + self.response_timeout
        while b"\n" not in self._read_buffer:
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            try:
                descriptor = stdout.fileno()
                readable, _, _ = select.select([descriptor], [], [], remaining)
                chunk = os.read(descriptor, 65536) if readable else None
            except (OSError, ValueError) as error:
                raise RemoteExecutionError("Worker response stream closed during process termination") from error
            if not readable:
                raise RemoteExecutionError("Worker response exceeded the bounded request deadline")
            if not chunk:
                raise RemoteExecutionError(
                    f"Worker exited before responding (exit={process.poll()}); "
                    f"see {self.log_path.name}"
                )
            self._read_buffer += chunk
            if len(self._read_buffer) > 8 * 1024**2:
                raise RemoteExecutionError("Worker response exceeds the bounded RPC message size")
        line, self._read_buffer = self._read_buffer.split(b"\n", 1)
        try:
            result = json.loads(line)
        except (ValueError, UnicodeError) as error:
            raise RemoteExecutionError("Worker emitted invalid JSON") from error
        if not isinstance(result, dict):
            raise RemoteExecutionError("Worker response must be an object")
        return result

    def call(self, method: str, **parameters):
        return self.call_with_options(method, parameters)

    def call_with_options(self, method: str, parameters: dict, execution_options: dict | None = None):
        # One input/output stream has exactly one in-flight request. A pool
        # achieves process concurrency through different clients, never through
        # interleaving requests on this client's pipe.
        with self._request_lock:
            return self._call(method, parameters, execution_options)

    def _call(self, method: str, parameters: dict, execution_options: dict | None = None):
        process = self.process
        if process is None or process.stdin is None:
            raise RemoteExecutionError("Worker is unavailable")
        stdin = process.stdin
        self._next_id += 1
        request = {"id": self._next_id, "method": method, "params": parameters}
        if execution_options is not None:
            request["execution"] = execution_options
        try:
            stdin.write(json.dumps(request) + "\n")
            stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as error:
            raise RemoteExecutionError("Worker closed its request stream") from error
        response = self._read(process)
        if response.get("id") != self._next_id:
            raise RemoteExecutionError("Worker response ID does not match the request")
        if response.get("ok") is True:
            if "result" not in response:
                raise RemoteExecutionError("Worker response has no result")
            return response["result"]
        if response.get("ok") is not False or not isinstance(response.get("error"), dict):
            raise RemoteExecutionError("Worker emitted an invalid response envelope")
        remote = response["error"]
        raise RemoteBusinessError(str(remote.get("type")), str(remote.get("message")))

    def batch(self, operations: list[dict], *, max_workers: int = 32,
              synchronize_start: bool = True, checkpoint: dict | None = None) -> dict:
        """Execute operations concurrently inside the one sandbox worker.

        Business errors remain individual result envelopes, so an insufficient
        inventory response cannot discard the remaining requests. The client
        sends one RPC request; host threads are not used to simulate concurrency.
        """
        return self.call("batch", operations=operations, max_workers=max_workers,
                         synchronize_start=synchronize_start, checkpoint=checkpoint)

    def restart(self) -> None:
        self.close()
        self.start()

    def close(self) -> None:
        process, self.process = self.process, None
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            self.last_exit_code = process.returncode
            if process.stdout is not None:
                process.stdout.close()
        if self._log is not None:
            self._log.close()
            self._log = None
