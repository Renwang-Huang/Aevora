"""Current public source selection + setuptools distributions; fresh output only.

Uses an explicit public allowlist and deterministic ZIP contract, with no
sealed-archive dependency, no maintainer import and no blanket Git staging.
"""

import argparse, hashlib, json, os, shutil, stat, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    "node_modules",
    ".venv",
    "build",
    "dist",
}
DOCS = [
	"PRODUCT_DIRECTION.md",
	"TASK_MEMORY.md",
	"CODEX_CAPTURE.md",
	"RETRIEVAL.md",
	"RETRIEVAL_QUALITY.md",
	"UPGRADING.md",
	"LOCAL_WORKFLOW.md",
    "RUNTIME.md",
    "QUICKSTART.md",
    "PROJECT_SOURCES.md",
    "ARCHITECTURE.md",
    "MCP.md",
    "CONSOLE.md",
    "DEMO.md",
    "LIMITATIONS.md",
    "NOTICES.md",
]


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def emit(p, v):
    with p.open("x") as f:
        json.dump(v, f, indent=2, sort_keys=True)
        f.write("\n")


def chosen(root=ROOT):
    paths = set()
    for base in [
        "go-runtime",
        "aevora_core/src",
        "aevora_core/docs",
        "aevora_core/examples/receipt_store",
        "aevora_core/examples/project_source",
        "aevora_core/tests/unit",
        "console/src",
        "console/web",
        "console/third_party",
        "demo",
        "deploy",
        "tools/public_evidence",
    ]:
        for p in (root / base).rglob("*"):
            native_asset = p.is_relative_to(root / 'go-runtime/internal/observatory/assets') and (
                p.suffix in {'.html', '.css', '.js'} or p.name == 'CYTOSCAPE_LICENSE')
            if base == 'go-runtime' and not native_asset and p.suffix not in {'.go', '.json', '.sql'} and p.name not in {'go.mod', 'go.sum', '.goreleaser.yaml'}:
                continue
            if (
                p.is_file()
                and not p.is_symlink()
                and not set(p.relative_to(root).parts) & SKIP
                and not any(x.endswith(".egg-info") for x in p.parts)
            ):
                paths.add(p)
    for folder, names in [
        ("aevora_core", ["README.md", "pyproject.toml", "MANIFEST.in", "LICENSE"]),
        (
            "console",
            [
                "README.md",
                "pyproject.toml",
                "MANIFEST.in",
                "LICENSE",
                "package.json",
                "package-lock.json",
                "build.mjs",
                "sync_evidence_tools.py",
                ".nvmrc",
            ],
        ),
    ]:
        paths.update(root / folder / n for n in names)
    paths.update(root / "docs" / n for n in DOCS)
    paths.update(
        root / p
        for p in [
            "deploy/bootstrap.py",
            "tools/sync_public_evidence.py",
            "tools/runtime_contracts.py",
            "tools/native_reference.py",
            "tools/native_assets.py",
            "tools/export_native.py",
            "tools/native_release.py",
			"tools/public_release.py",
            "tools/paths.py",
            "CONTRIBUTING.md",
            ".github/workflows/ci.yml",
            ".github/workflows/native.yml",
        ]
    )
    return sorted(paths)


def build(output, root=ROOT):
    sys.path.insert(0, str(root))
    from tools.sync_public_evidence import synchronize

    synchronize(root, check=True)
    from tools.paths import fresh_external_output

    output = fresh_external_output(output, root)
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    rows = {}
    for p in chosen(root):
        if p.is_symlink() or not p.is_file():
            raise ValueError("Public ordinary input required")
        rel = str(p.relative_to(root))
        q = source / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        q.chmod(p.stat().st_mode & 0o777)
        rows[rel] = {
            "sha256": digest(q),
            "source_sha256": digest(p),
            "visibility": "PUBLIC",
        }
    for src, dst in [
        ("README.md", "README.md"),
        ("aevora_core/LICENSE", "LICENSE"),
        ("docs/NOTICES.md", "THIRD_PARTY_NOTICES.md"),
    ]:
        shutil.copyfile(root / src, source / dst)
        rows[dst] = {
            "sha256": digest(source / dst),
            "source_sha256": digest(root / src),
            "visibility": "PUBLIC",
        }
    ignore = ".git\n**/__pycache__\n**/node_modules\n**/build\n**/dist\n**/*.egg-info\n**/*.key\n**/*.password\ngrant.json\n"
    for name in [".gitignore", ".dockerignore"]:
        (source / name).write_text(ignore)
        rows[name] = {"sha256": digest(source / name), "visibility": "PUBLIC_GENERATED"}
    emit(
        output / "PUBLIC_SELECTION.json",
        {
            "files": rows,
            "excluded": "All OrderFlow/maintainer/Oracle/Reference/private labels/root AGENTS/private tests/history/model logs/credentials (public Core unit tests included)",
            "maintainer_git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "local_only": True,
        },
    )
    dist = output / "dist"
    dist.mkdir()
    commands = []
    for package in ["aevora_core", "console"]:
        # Existing pinned setuptools backend, not a new build system.
        code = (
            "from setuptools.build_meta import build_wheel,build_sdist;print(build_wheel("
            + repr(str(dist))
            + "));print(build_sdist("
            + repr(str(dist))
            + "))"
        )
        argv = [sys.executable, "-c", code]
        r = subprocess.run(argv, cwd=source / package, capture_output=True)
        (output / (package + "-build.stdout.log")).write_bytes(r.stdout)
        (output / (package + "-build.stderr.log")).write_bytes(r.stderr)
        commands.append(
            {
                "argv": argv,
                "cwd": str(source / package),
                "exit_code": r.returncode,
                "stdout_sha256": digest(output / (package + "-build.stdout.log")),
                "stderr_sha256": digest(output / (package + "-build.stderr.log")),
            }
        )
        emit(output / (package + "-command.json"), commands[-1])
        if r.returncode:
            raise ValueError("Real package build failed; original output retained")
    emit(output / "BUILD_COMMANDS.json", {"commands": commands})

    def export(p):
        with zipfile.ZipFile(
            p, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as z:
            for rel, row in sorted(rows.items()):
                q = source / rel
                if digest(q) != row["sha256"]:
                    raise ValueError("Public source changed during build")
                info = zipfile.ZipInfo("aevora/" + rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                z.writestr(
                    info,
                    q.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )

    archive = output / "aevora-public-source.zip"
    repeat = output / "aevora-public-source-repeat.zip"
    export(archive)
    export(repeat)
    assert digest(archive) == digest(repeat)
    result = {
        "status": "PASS",
        "source_files": len(rows),
        "source_zip_sha256": digest(archive),
        "source_zip_bytes": archive.stat().st_size,
        "deterministic_zip_equal": True,
        "artifacts": {p.name: digest(p) for p in dist.iterdir()},
        "local_only": True,
    }
    emit(output / "RESULT.json", result)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    raise SystemExit(build(a.output))
