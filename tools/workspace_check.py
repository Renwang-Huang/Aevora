"""Check the two local developer views without opening or changing an editor.

View filters are navigation preferences, never filesystem or release security.
Uses VS Code's documented multi-root JSON shape and Git's real parent discovery.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ("Aevora.Product.code-workspace", "Aevora.Maintainer.code-workspace")
PRODUCT_ROOTS = {
    "aevora_core/src", "aevora_core/docs", "aevora_core/examples/receipt_store",
    "console/src", "console/web", "h4", "docs/current", "tools/public_evidence",
}
MAINTAINER_ROOTS = PRODUCT_ROOTS | {
    "app", "benchmark", "evaluator", "integrations", "aevora_maintainer",
    "tests", "aevora_core/tests", "tools", "scripts", "evidence", "docs/history",
}
CACHE_FILTERS = {
    "**/.venv", "**/.pytest_cache", "**/__pycache__", "**/node_modules",
    "**/build", "**/dist", "**/*.egg-info",
}


def resolve_cwd(value, folders):
    """Expand the documented named workspaceFolder variable, with no shell."""
    match = re.fullmatch(r"\$\{workspaceFolder:([^}]+)\}(/[^$]*)?", value)
    if not match or match[1] not in folders:
        raise ValueError("Named workspaceFolder required for command cwd")
    return (folders[match[1]] / (match[2] or "/").lstrip("/")).resolve()


def validate_view(root, filename, *, check_git=True):
    root = Path(root).resolve()
    doc = json.loads((root / filename).read_text())
    expected = PRODUCT_ROOTS if filename == VIEWS[0] else MAINTAINER_ROOTS
    folders = {}
    paths = set()
    for item in doc["folders"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) not in expected:
            raise ValueError("Unexpected, absolute or traversing workspace folder")
        path = root / relative
        if not path.is_dir() or path.resolve() != path or item["name"] in folders:
            raise ValueError("Missing, linked or duplicate workspace folder")
        if str(relative) in paths:
            raise ValueError("Duplicate workspace folder path")
        paths.add(str(relative))
        folders[item["name"]] = path
    if paths != expected:
        raise ValueError("Incomplete active folder coverage")
    settings = doc["settings"]
    for setting in ("files.exclude", "search.exclude", "files.watcherExclude"):
        rules = settings[setting]
        if set(rules) != CACHE_FILTERS or any(v is not True for v in rules.values()):
            raise ValueError("Only confirmed regenerable cache filters are permitted")
    if settings["git.openRepositoryInParentFolders"] != "always":
        raise ValueError("Parent repository discovery must be explicit")
    if resolve_cwd(settings["terminal.integrated.cwd"], folders) != root:
        raise ValueError("Terminal cwd must be the real repository root")
    tasks = doc["tasks"]
    if tasks["version"] != "2.0.0" or not tasks["tasks"]:
        raise ValueError("Documented workspace process tasks required")
    allowed = {
        ("python3", ("tools/sync_public_evidence.py", "--check")),
        ("python3", ("tools/workspace_check.py",)),
        ("python3", ("tools/dev.py", "--help")),
        ("npm", ("--prefix", "console", "run", "build")),
        ("npm", ("--prefix", "console", "test")),
    }
    for task in tasks["tasks"]:
        if task["type"] != "process" or (task["command"], tuple(task["args"])) not in allowed:
            raise ValueError("Unexpected task; no shell, model or database startup tasks")
        if resolve_cwd(task["options"]["cwd"], folders) != root:
            raise ValueError("Task cwd must be the real repository root")
    repositories = {}
    if check_git:
        for name, path in folders.items():
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                check=True, capture_output=True, text=True,
            )
            if Path(result.stdout.strip()).resolve() != root:
                raise ValueError("Folder belongs to a different Git repository")
            repositories[name] = result.stdout.strip()
    return {"view": filename, "folders": {n: str(p.relative_to(root)) for n, p in folders.items()},
            "git_parent_discovery": repositories, "tasks": len(tasks["tasks"]),
            "filter_authority": "VIEW_ONLY", "visual_status": "VISUAL_UNVERIFIED"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = [validate_view(args.root, filename) for filename in VIEWS]
    print(json.dumps({"status": "PASS", "checks": result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
