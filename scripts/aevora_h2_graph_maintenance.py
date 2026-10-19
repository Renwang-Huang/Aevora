"""Trusted H2-only temporary RDB scheduling window, with unconditional restore.

This pauses automatic SAVE scheduling while preserved copy tests run; it neither
retries GRAPH.COPY nor changes a test verdict. No H1 endpoint is permitted.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


@contextmanager
def paused_auto_save(output: Path):
    if os.environ.get("AEVORA_FALKORDB_PORT") != "17679":
        raise RuntimeError("Maintenance is restricted to the dedicated H2 endpoint")
    from aevora.graph_repository import GraphRepository
    repository = GraphRepository.from_environment()
    connection = repository._client.connection
    original = connection.config_get("save")
    if not isinstance(original, dict) or set(original) != {"save"} or not isinstance(original["save"], str):
        repository.close(); raise RuntimeError("Unexpected original SAVE configuration")
    receipt = {"started_at":datetime.now(timezone.utc).isoformat(),"endpoint_port":17679,
        "graph_name":repository.graph_name,"original_save":original,"classification":"TEMPORARY_TEST_MAINTENANCE; NOT_DEPLOYMENT_CONFIG",
        "original_persistence":connection.info("persistence"),"original_stats":connection.info("stats")}
    paused = False
    def drain_existing_fork():
        deadline=time.monotonic()+5
        while True:
            state=connection.info("persistence")
            if not any(state.get(key,0) for key in ("rdb_bgsave_in_progress","aof_rewrite_in_progress","module_fork_in_progress")):
                return state
            if time.monotonic()>=deadline:
                raise RuntimeError("Existing database fork did not finish within maintenance bound")
            time.sleep(.02)
    try:
        paused = connection.config_set("save", "") is True
        receipt["pause_result"] = paused
        if not paused or connection.config_get("save") != {"save":""}:
            raise RuntimeError("Automatic SAVE schedule was not paused")
        receipt["before_yield_persistence"]=drain_existing_fork()
        yield receipt
    finally:
        # Restore is attempted even if pytest, SDK or SAVE fails. A restoration
        # failure is a new maintenance ERROR, never disguised as a test PASS.
        try:
            if paused:
                receipt["before_explicit_save_persistence"]=drain_existing_fork()
                receipt["explicit_save_result"] = connection.save()
                if receipt["explicit_save_result"] is not True:
                    raise RuntimeError("Explicit RDB SAVE failed")
        except Exception as error:
            receipt["save_error_type"] = type(error).__name__
            raise
        finally:
            try:
                receipt["restore_result"] = connection.config_set("save",original["save"])
                receipt["restored_save"] = connection.config_get("save")
                receipt["final_persistence"] = connection.info("persistence")
                if receipt["restore_result"] is not True or receipt["restored_save"] != original:
                    raise RuntimeError("Original SAVE configuration was not restored")
            finally:
                receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
                with (Path(output)/"RDB_MAINTENANCE_RECEIPT.json").open("x") as stream:
                    json.dump(receipt,stream,sort_keys=True,indent=2);stream.write("\n")
                repository.close()
