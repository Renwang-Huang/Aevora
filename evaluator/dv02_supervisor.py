"""Additive request topology: original RPC/resource lifecycle plus query Clock."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import time

from evaluator.control import process_identity
from evaluator.dv02_clock import ClockAuthority, extend_candidate_command
from evaluator.rpc import RemoteExecutionError
from evaluator.supervisor import WorkerSupervisor

REQUEST_WRITES = frozenset({"claim_request", "renew_request", "complete_request", "cancel_request"})


class DV02WorkerSupervisor(WorkerSupervisor):
    def __init__(self, *args, clock_tick=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.clock = ClockAuthority(clock_tick)
        self._paused = {}

    def start(self):
        self.clock.start()
        return super().start()

    def _start_worker(self, index):
        rpc = self.workers[index]
        # Keep the cgroup wrapper outside the bubblewrap command. Refresh on
        # every generation rather than stacking transforms after a restart.
        def wrap(command):
            extended = extend_candidate_command(command, self.clock.path)
            return self.cgroup.wrap_command(extended) if self.cgroup else extended
        rpc.command_wrapper = wrap
        return super()._start_worker(index)

    def _observe_control_event(self, event):
        super()._observe_control_event(event)
        method = event.get("metadata", {}).get("method")
        if event["event"] != "before_commit" or method not in REQUEST_WRITES:
            return
        key = (event["worker_index"], event["host_pid"], method)
        with self._record_lock:
            if key in self._fd_observed_generations:
                return
            self._fd_observed_generations.add(key)
        proof = self.database_fds(event["worker_index"])
        proof.update(event_reference={"event": event["event"], "host_observed_ns": event["host_observed_ns"]},
                     worker_index=event["worker_index"], method=method, host_observed_ns=time.monotonic_ns())
        with self._record_lock:
            self._fd_witnesses.append(proof)

    def _owned_signal(self, index, kind):
        self._index(index)
        identity = self.control.wait_ready(index)
        with self.control._lock:
            fd = os.dup(self.control._pidfds[index])
        try:
            now = process_identity(identity["host_pid"])
            if now["start_ticks"] != identity["start_ticks"]:
                raise RemoteExecutionError("Owned worker generation identity changed")
            signal.pidfd_send_signal(fd, kind)
            deadline = time.monotonic() + 2
            stopped = kind == signal.SIGSTOP
            while True:
                raw = (Path("/proc") / str(identity["host_pid"]) / "stat").read_text()
                state = raw[raw.rindex(")") + 2:].split()[0]
                if (state in {"T", "t"}) == stopped:
                    break
                if time.monotonic() >= deadline:
                    raise RemoteExecutionError("Kernel worker signal was not observed within its bound")
                time.sleep(0.002)
            row = self._record("worker.signal", worker_index=index, identity=identity,
                               signal=signal.Signals(kind).name, kernel_state=state,
                               authority="OWNED_KERNEL_PIDFD; PUBLIC_CALLS_BETWEEN_PHASES")
            return row
        finally:
            os.close(fd)

    def pause(self, index):
        row = self._owned_signal(index, signal.SIGSTOP)
        self._paused[index] = row["identity"]["start_ticks"]
        self.save("paused")
        return row

    def resume(self, index):
        if index not in self._paused:
            raise ValueError("Worker has no owned pause")
        identity = self.control.wait_ready(index)
        if identity["start_ticks"] != self._paused[index]:
            raise RemoteExecutionError("Cannot resume a different worker generation")
        row = self._owned_signal(index, signal.SIGCONT)
        del self._paused[index]
        self.save("resumed")
        return row

    def kill(self, index):
        result = super().kill(index)
        self._paused.pop(index, None)
        return result

    def stop_all(self):
        for index in list(self._paused):
            try:
                self.resume(index)
            except (OSError, ValueError, RemoteExecutionError):
                self._paused.pop(index, None)
        return super().stop_all()

    def evidence(self):
        result = super().evidence()
        result.update(request_supervisor_version="1.0.0", clock=self.clock.evidence(),
                      paused_worker_indices=sorted(self._paused))
        return result

    def close(self):
        try:
            super().close()
        finally:
            self.clock.close()
        self.save("clock-cleanup")
        return self.evidence()
