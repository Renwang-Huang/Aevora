"""Public package defaults and source identity require no database or model."""

import inspect

import pytest

from aevora.admission import _source_epoch
from aevora.graph_repository import GraphRepository
from aevora.models import InvalidRecord


def test_graph_defaults_name_a_current_local_instance():
    parameters = inspect.signature(GraphRepository).parameters
    assert parameters["host"].default == "127.0.0.1"
    assert parameters["port"].default == 17692
    assert parameters["graph_name"].default == "aevora"


def test_source_epoch_uses_the_verified_manifest_identity():
    assert _source_epoch("a" * 64) == "sealed-run-manifest:sha256:" + "a" * 64
    assert _source_epoch("b" * 64) != _source_epoch("a" * 64)


@pytest.mark.parametrize(
    "value", [None, "", "H3_NEW_NATIVE_SESSION", "a" * 63, "z" * 64, "A" * 64]
)
def test_source_epoch_refuses_unpinned_or_noncanonical_inputs(value):
    with pytest.raises(InvalidRecord):
        _source_epoch(value)
