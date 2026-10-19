"""Additive developer-view contracts; all inherited tests remain unchanged."""
import json
from pathlib import Path

import pytest
from tools.workspace_check import ROOT, VIEWS, validate_view


@pytest.mark.parametrize("view", VIEWS)
def test_real_relative_views_find_parent_repository(view):
    result = validate_view(ROOT, view)
    assert result["filter_authority"] == "VIEW_ONLY"
    assert result["git_parent_discovery"]
    assert result["visual_status"] == "VISUAL_UNVERIFIED"


@pytest.fixture
def copied_view(tmp_path):
    doc = json.loads((ROOT / VIEWS[0]).read_text())
    for item in doc["folders"]:
        (tmp_path / item["path"]).mkdir(parents=True, exist_ok=True)
    def check(changed):
        (tmp_path / VIEWS[0]).write_text(json.dumps(changed))
        return validate_view(tmp_path, VIEWS[0], check_git=False)
    return doc, check


@pytest.mark.parametrize("path", ["/tmp", "../outside", "evaluator", "integrations", "tests"])
def test_product_view_rejects_private_or_traversing_roots(copied_view, path):
    doc, check = copied_view
    doc["folders"][0]["path"] = path
    with pytest.raises(ValueError, match="Unexpected"):
        check(doc)


def test_missing_active_folder_is_not_silently_hidden(copied_view):
    doc, check = copied_view
    doc["folders"].pop()
    with pytest.raises(ValueError, match="Incomplete"):
        check(doc)


@pytest.mark.parametrize("setting", ["files.exclude", "search.exclude", "files.watcherExclude"])
def test_active_source_cannot_be_filtered(copied_view, setting):
    doc, check = copied_view
    doc["settings"][setting]["**/src"] = True
    with pytest.raises(ValueError, match="cache filters"):
        check(doc)


def test_linked_folder_is_rejected(copied_view, tmp_path):
    doc, check = copied_view
    path = tmp_path / doc["folders"][0]["path"]
    path.rmdir()
    path.symlink_to(ROOT / doc["folders"][0]["path"], target_is_directory=True)
    with pytest.raises(ValueError, match="linked"):
        check(doc)


def test_implicit_terminal_directory_is_rejected(copied_view):
    doc, check = copied_view
    doc["settings"]["terminal.integrated.cwd"] = "${workspaceFolder}"
    with pytest.raises(ValueError, match="Named workspaceFolder"):
        check(doc)


def test_wrong_task_directory_is_rejected(copied_view):
    doc, check = copied_view
    doc["tasks"]["tasks"][0]["options"]["cwd"] = "${workspaceFolder:Core}"
    with pytest.raises(ValueError, match="Task cwd"):
        check(doc)


def test_unreviewed_shell_task_is_rejected(copied_view):
    doc, check = copied_view
    doc["tasks"]["tasks"][0]["type"] = "shell"
    with pytest.raises(ValueError, match="Unexpected task"):
        check(doc)


def test_full_release_selects_portable_developer_views():
    from tools.public_release import chosen
    selected = {str(p.relative_to(ROOT)) for p in chosen()}
    assert set(VIEWS) <= selected
    assert "tools/workspace_check.py" in selected
    assert "docs/current/WORKSPACE.md" in selected
