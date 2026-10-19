"""Inherited cancellation race reproduction, no live model or test weakening."""
import json
import threading
from uuid import uuid4

from integrations.runtime_control import RuntimeControl, cancel_run


def test_cancel_is_published_only_after_complete_json(tmp_path, monkeypatch):
    """Block JSON serialization while the actual controller reads cancellation."""
    archive = tmp_path / str(uuid4())
    archive.mkdir()
    control = RuntimeControl(archive, archive.name, completion_policy="completion-aware", agent_mode="multi")
    entered, release = threading.Event(), threading.Event()
    real_dump = json.dump
    errors = []

    def blocked(value, output, *args, **kwargs):
        if isinstance(value, dict) and value.get("classification") == "CANCELLED_BY_OPERATOR":
            entered.set()
            assert release.wait(5)
        return real_dump(value, output, *args, **kwargs)

    monkeypatch.setattr("integrations.runtime_control.json.dump", blocked)

    def operator():
        try:
            cancel_run(archive, "publication boundary regression")
        except Exception as error:
            errors.append(error)

    writer = threading.Thread(target=operator)
    writer.start()
    try:
        assert entered.wait(5)
        # Controller must see no request yet, rather than parse an empty file.
        assert control.cancellation() is None
    finally:
        release.set()
        writer.join(5)
    assert not errors and not writer.is_alive()
    assert control.cancellation()["classification"] == "CANCELLED_BY_OPERATOR"
    control.finish("CANCELLED", "CANCELLED_BY_OPERATOR")
