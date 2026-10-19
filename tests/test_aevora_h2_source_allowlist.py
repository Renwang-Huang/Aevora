"""Source selection contracts; runtime caches are not release source assets."""
import importlib.util
from pathlib import Path
import pytest

_path=Path(__file__).resolve().parents[1]/"scripts/aevora_h2_audit.py"
_spec=importlib.util.spec_from_file_location("h2_source_allowlist",_path)
audit=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

@pytest.mark.parametrize("path",["aevora_core/.pytest_cache/README.md","aevora_core/.venv/lib/site-packages/library.py",
 "aevora_core/build/generated.py","tests/__pycache__/generated.py","integrations/pkg.egg-info/requires.txt",
 "scripts/node_modules/vendor/test.py","aevora_core/.ruff_cache/README.md"])
def test_runtime_and_generated_directories_are_not_release_source(path):
 assert audit.source_path_allowed(path) is False

@pytest.mark.parametrize("path",["scripts/aevora-h2-python","aevora_core/src/aevora/feedback.py",
 "aevora_core/requirements.lock.txt","docs/ARCHITECTURE.md","evaluator/private_manifests/D-V02.json"])
def test_authorized_maintainer_source_includes_required_assets(path):
 assert audit.source_path_allowed(path) is True

def test_actual_source_inventory_contains_launcher_but_no_cache():
 rows=audit.sources()
 assert "scripts/aevora-h2-python" in rows
 assert "aevora_core/src/aevora/feedback.py" in rows
 assert all(audit.source_path_allowed(path) for path in rows if path not in {".gitignore"})
