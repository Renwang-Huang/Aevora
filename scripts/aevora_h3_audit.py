"""H3 receipts, releases and inherited byte/identity verification.

Reuses mature collectors without changing H1/H2 historical archives or root
Git index. Every new operation has an exclusive output directory.
"""
from pathlib import Path
from tools.history_paths import history_path
import argparse
import json
import os
import shutil
import subprocess
from scripts.aevora_h2_audit import ROOT, sources as inherited_sources, digest, write, now
from scripts.aevora_h1_audit import record
from scripts.aevora_h2_junit import check_junit


def archive():
    return Path((ROOT / 'aevora_validation/H3_CURRENT').read_text().strip())


def sources():
    rows = inherited_sources()
    for p in (ROOT / 'MANIFEST.in', ROOT / 'aevora_core/MANIFEST.in', history_path(ROOT, 'AEVORA_H3_TRACEABILITY_MATRIX.csv')):
        if p.exists(): rows[str(p.relative_to(ROOT))] = {'sha256': digest(p), 'mode': p.stat().st_mode & 0o777}
    return dict(sorted(rows.items()))


def launch(*args, live=False, graph=None):
    config = json.loads((archive() / 'CONFIG.json').read_text())
    return ['env', 'ORDERFLOW_ENABLE_CODEX=' + ('1' if live else '0'),
            'AEVORA_H2_RUNTIME=' + config['runtime'],
            'AEVORA_FALKORDB_PASSWORD_FILE=' + config['password_file'],
            'AEVORA_FALKORDB_PORT=' + str(config['port']),
            'AEVORA_FALKORDB_GRAPH=' + (graph or config['graph']),
            str(ROOT / 'scripts/aevora-h2-python'), *map(str, args)]


def release(label, output_root=None):
    A = archive(); target = Path(output_root).absolute() if output_root else A
    if output_root and (ROOT/'aevora_validation/audit_exports') not in target.parents:
        raise ValueError('Post-seal releases belong to the independent audit export directory')
    if target==A and (A/'EVIDENCE_MANIFEST.json').exists():
        raise ValueError('Do not append release evidence to a sealed Full')
    out = target / ('release-' + label); out.mkdir(mode=0o700)
    W = ROOT / 'aevora_validation/h3_worktrees' / A.name
    W.parent.mkdir(exist_ok=True)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(out), 'LANG': 'C.UTF-8',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}
    commands = []
    def git(*args):
        argv = ['git', '-c', 'core.hooksPath=/dev/null', *args]
        r = subprocess.run(argv, cwd=W, env=env, capture_output=True, text=True)
        commands.append({'argv': argv, 'cwd': str(W), 'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
        write(out / ('command-' + str(len(commands)) + '.json'), commands[-1])
        if r.returncode: raise RuntimeError('Release Git failed; receipt retained')
        return r.stdout.strip()
    if not W.exists():
        W.mkdir(mode=0o700); git('init', '-b', 'aevora-h3-releases')
    rows = sources()
    tracked = set(git('ls-files').splitlines())
    if tracked - set(rows): git('rm', '--force', '--', *sorted(tracked - set(rows)))
    for rel, entry in rows.items():
        p = W / rel; p.parent.mkdir(parents=True, exist_ok=True)
        if p.is_symlink(): raise ValueError('Linked release file')
        shutil.copyfile(ROOT / rel, p); p.chmod(entry['mode'])
    git('add', '--force', '--', *rows)
    git('-c', 'user.name=Aevora H3 Local Release', '-c', 'user.email=aevora-h3@invalid',
        'commit', '-m', 'Aevora H3 ' + label)
    result = {'commit': git('rev-parse', 'HEAD'), 'git_tree': git('rev-parse', 'HEAD^{tree}'),
              'source_files': rows, 'recorded_at': now(), 'root_index_staged': False}
    for rel, entry in rows.items():
        if digest(W / rel) != entry['sha256']: raise ValueError('Release bytes differ')
    write(out / 'SOURCE_MANIFEST.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_files'}))


def integrity(junit, output):
    A = archive(); checks = {}
    for name in ('PROTECTED_HISTORY', 'INHERITED_TEST_SOURCES', 'FROZEN_TASK_TRUTH'):
        rows = json.loads((A / 'g0' / (name + '.json')).read_text())
        bad = [p for p, sha in rows.items() if not (ROOT / p).is_file() or digest(ROOT / p) != sha]
        checks[name] = {'status': 'PASS' if not bad else 'FAIL', 'files': len(rows), 'mismatches': bad}
    required = json.loads((A / 'g0/INHERITED_TEST_IDENTITIES.json').read_text())['identities']
    checks['inherited_1655'] = check_junit(junit, required)
    result = {'status': 'PASS' if all(c['status'] == 'PASS' for c in checks.values()) else 'FAIL',
              'checks': checks, 'scope': 'Current local byte and actual JUnit consistency', 'recorded_at': now()}
    write(output, result); print(json.dumps(result)); return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='op', required=True)
    r = sub.add_parser('record'); r.add_argument('label'); r.add_argument('argv', nargs=argparse.REMAINDER)
    r = sub.add_parser('release'); r.add_argument('label')
    r = sub.add_parser('integrity'); r.add_argument('junit', type=Path); r.add_argument('output', type=Path)
    a = p.parse_args()
    if a.op == 'record': raise SystemExit(record(archive(), a.label, a.argv[1:] if a.argv[:1] == ['--'] else a.argv))
    elif a.op == 'release': release(a.label)
    else: raise SystemExit(integrity(a.junit, a.output))
