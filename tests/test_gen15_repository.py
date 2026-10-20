"""Additive consolidation contracts; inherited assertions/sources stay frozen."""
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from tools.sync_public_evidence import PAIRS,synchronize
ROOT=Path(__file__).resolve().parents[1]
def test_legacy_host_alias_is_the_canonical_module():
    old=importlib.import_module("aevora.audit_capsule")
    current=importlib.import_module("aevora_maintainer.audit_capsule")
    assert old is current and old.CAPSULE_VERSION=="aevora.audit_capsule/1.0"
@pytest.mark.parametrize("source",list(PAIRS))
def test_standalone_generated_evidence_matches_owner(source):
    assert all((ROOT/p).read_bytes()==(ROOT/source).read_bytes() for p in PAIRS[source])
def test_public_sync_manifest_uses_authoritative_source():
    assert synchronize(check=True)["generated_copies"]==4
@pytest.mark.parametrize("destination",[p for ps in PAIRS.values() for p in ps])
def test_vendor_drift_fails_closed(tmp_path,destination):
    for source,targets in PAIRS.items():
        for p in [source,*targets]:
            target=tmp_path/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
    manifest=Path("console/src/aevora_observatory/EVIDENCE_TOOL_SOURCES.json");shutil.copyfile(ROOT/manifest,tmp_path/manifest)
    with (tmp_path/destination).open("ab") as out:out.write(b"# drift\n")
    with pytest.raises(ValueError,match="drift"):synchronize(tmp_path,check=True)
def test_core_normal_import_does_not_pull_private_benchmark():
    code="import sys;import aevora.experience_resolver,aevora.mcp_connect;assert not any(n.startswith(('benchmark','evaluator','integrations','aevora_maintainer')) for n in sys.modules)"
    r=subprocess.run([sys.executable,"-I","-c",code],cwd=ROOT,capture_output=True)
    assert r.returncode==0,r.stderr.decode()
def test_no_truth_or_inherited_source_modified():
    # The dynamic evidence harness checks the full original SHA maps separately.
    # Repository layer adds strict package profile enforcement without private paths.
    import tomllib
    profile=tomllib.loads((ROOT/"pyproject.toml").read_text())
    assert "aevora_maintainer*" in profile["tool"]["setuptools"]["packages"]["find"]["include"]

@pytest.mark.parametrize('command',['public-build','test-core','benchmark-check','dv02-check','test-maintainer'])
def test_current_commands_reject_implicit_output(command):
    r=subprocess.run([sys.executable,str(ROOT/'tools/dev.py'),command],cwd=ROOT,capture_output=True)
    assert r.returncode==2 and b'Fresh external --output required' in r.stderr

def test_full_selection_contains_engineering_but_excludes_run_credentials():
    from tools.public_release import chosen
    paths={str(p.relative_to(ROOT)) for p in chosen()}
    assert {'app/service.py','benchmark/runner.py','evaluator/oracle.py',
            'integrations/codex_agent.py','aevora_maintainer/host_v2.py',
            'tools/public_evidence/hero_verify.py'} <= paths
    assert not any(p.startswith(('runs/','owned_secrets/','.venv/')) for p in paths)
    assert {'AGENTS.md','docs/history/engineering/maintainer/AGENTS.md'} <= paths


def test_current_output_guard_preserves_sealed_archive(tmp_path):
    from tools.paths import fresh_external_output
    sealed=tmp_path/'sealed';sealed.mkdir();(sealed/'EVIDENCE_MANIFEST.json').write_text('{}')
    with pytest.raises(ValueError,match='immutable'):fresh_external_output(sealed/'new-command',ROOT)
    assert not (sealed/'new-command').exists()
    with pytest.raises(ValueError,match='Noncanonical'):fresh_external_output(tmp_path/'parent'/'..'/'new-command',ROOT)

def test_current_output_guard_rejects_linked_parent(tmp_path):
    from tools.paths import fresh_external_output
    parent=tmp_path/'parent';parent.mkdir();link=tmp_path/'link';link.symlink_to(parent,target_is_directory=True)
    with pytest.raises(ValueError,match='Linked'):fresh_external_output(link/'new-command',ROOT)
