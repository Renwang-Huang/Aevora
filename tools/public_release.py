"""Build the explicitly reviewed full-source release; never collect run stores.

The owner's 2026-10-19 authorization includes historical Benchmark/Oracle code.
Credentials, linked files, live run stores and private raw evidence remain out.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache',
                   'runs', 'owned_secrets', 'codex_home'}
FORBIDDEN_NAMES = {'auth.json', 'grant.json', '.runtime.env'}


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def chosen(root=ROOT):
    root = Path(root).resolve()
    result = []
    seen = set()
    for line in (root / 'PUBLIC_SOURCE_FILES.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        rel = PurePosixPath(line)
        if (rel.is_absolute() or '..' in rel.parts or str(rel) != line or '\\' in line
                or line in seen or set(rel.parts) & FORBIDDEN_PARTS
                or rel.name in FORBIDDEN_NAMES or rel.name.startswith('.env') and rel.name != '.env.example'
                or rel.suffix in {'.key', '.password', '.pem', '.p12', '.pfx'}):
            raise ValueError('Unsafe or duplicate publication path: ' + line)
        p = root / line
        if any(parent.is_symlink() for parent in [p, *p.parents] if parent.is_relative_to(root)):
            raise ValueError('Linked publication path: ' + line)
        info = p.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Ordinary single-link publication input required: ' + line)
        seen.add(line)
        result.append(p)
    if not result:
        raise ValueError('Empty publication selection')
    return sorted(result)


def build(output, root=ROOT):
    sys.path.insert(0, str(root))
    from tools.paths import fresh_external_output
    from tools.sync_public_evidence import synchronize
    synchronize(root, check=True)
    output = fresh_external_output(output, root)
    output.mkdir(parents=True)
    source = output / 'source'
    rows = {}
    for p in chosen(root):
        rel = p.relative_to(root).as_posix()
        q = source / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        q.chmod(p.stat().st_mode & 0o777)
        rows[rel] = {'sha256': digest(q), 'bytes': q.stat().st_size}
    dist = output / 'dist'
    dist.mkdir()
    commands = []
    for label in ('aevora_core', 'console', '.'):
        argv = [sys.executable, '-m', 'build', '--no-isolation', '--outdir', str(dist)]
        r = subprocess.run(argv, cwd=source / label, capture_output=True)
        name = 'benchmark' if label == '.' else label
        (output / (name + '.stdout.log')).write_bytes(r.stdout)
        (output / (name + '.stderr.log')).write_bytes(r.stderr)
        commands.append({'argv': argv, 'package': label, 'exit_code': r.returncode})
        (output / 'BUILD_COMMANDS.json').write_text(json.dumps(commands, indent=2) + '\n')
        if r.returncode:
            raise RuntimeError('Package build failed; original receipts retained: ' + label)
    archive = output / 'aevora-full-project-source.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(rows):
            q = source / rel
            if digest(q) != rows[rel]['sha256']:
                raise ValueError('Source changed during export')
            info = zipfile.ZipInfo('aevora/' + rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | (q.stat().st_mode & 0o777)) << 16
            z.writestr(info, q.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    result = {'status': 'PASS', 'source_files': rows,
              'artifacts': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                            for p in [archive, *sorted(dist.iterdir())]}}
    (output / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'files': len(rows), 'artifacts': list(result['artifacts'])}))
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    raise SystemExit(build(p.parse_args().output))
