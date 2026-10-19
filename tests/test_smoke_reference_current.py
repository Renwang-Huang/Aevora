from benchmark.manifest import ROOT
from benchmark.runner import apply_patch
from benchmark.templates import create_template, reference_patch


def test_current_smoke_patch_matches_factory_and_strict_submission(tmp_path):
    patch=ROOT/"evaluator/reference_patches/SMOKE-001-current.diff"
    assert patch.read_text()==reference_patch()
    workspace=create_template(tmp_path/"candidate")
    apply_patch(workspace,patch)
    for source in (ROOT/"app").rglob("*.py"):
        assert (workspace/"app"/source.relative_to(ROOT/"app")).read_bytes()==source.read_bytes()
