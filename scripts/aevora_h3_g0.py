"""Actual G0 Native vs outer public-test/permission comparison, no model calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from scripts.aevora_h2_audit import write, digest, now
from benchmark.episodes.episode_d_v02 import build_episode_d_v02
from benchmark.participant_sandbox import participant_command


def main(output):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace = build_episode_d_v02(output / 'workspace', implementation='reference')
    root = Path(__file__).resolve().parents[1]
    (workspace / 'tests/public').mkdir(parents=True)
    for name in ('test_episode_d_v02.py', 'dv02_inprocess_contract.py'):
        shutil.copyfile(root / 'tests/public' / name, workspace / 'tests/public' / name)
    results = []
    for layer in ('host', 'outer', 'native'):
        for entry in ('permission', 'original-uds', 'equivalent-inprocess'):
            state = output / (layer + '-' + entry + '-state'); state.mkdir(mode=0o700)
            prefix = str(workspace) if layer == 'host' else '/workspace'
            if entry == 'permission':
                code = """import json,os,socket,tempfile
status={k:v.strip() for k,v in (line.split(':',1) for line in open('/proc/self/status') if ':' in line) if k in ['CapEff','NoNewPrivs','Seccomp']}
status['namespaces']={k:os.readlink('/proc/self/ns/'+k) for k in ['user','pid','net','ipc','mnt']}
status['cgroup']=open('/proc/self/cgroup').read()
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
try:
 s.bind(tempfile.gettempdir()+'/g0-public-clock.sock');status['bind']='SUCCESS'
except OSError as e:status['bind']='DENIED';status['bind_errno']=e.errno
finally:s.close()
print(json.dumps(status))
"""
                command = ['/usr/bin/python3.12', '-I', '-B', '-c', code]
            else:
                name = 'test_episode_d_v02.py' if entry == 'original-uds' else 'dv02_inprocess_contract.py'
                command = ['/usr/bin/python3.12', '-B', prefix + '/tests/public/' + name]
            if layer == 'host':
                argv = command
            else:
                if layer == 'native':
                    command = ['/opt/codex/codex', 'sandbox', '-c', 'sandbox_mode="workspace-write"',
                               '-c', 'approval_policy="never"', '--', *command]
                argv = participant_command(workspace, state, Path(os.environ['ORDERFLOW_CODEX_BINARY']), command,
                                           network_isolated=True)
            start = now()
            r = subprocess.run(argv, cwd=workspace, capture_output=True, timeout=90)
            d = output / (layer + '-' + entry); d.mkdir()
            (d / 'stdout.log').write_bytes(r.stdout); (d / 'stderr.log').write_bytes(r.stderr)
            receipt = {'argv': argv, 'exit_code': r.returncode, 'layer': layer, 'entry': entry,
                       'started_at': start, 'ended_at': now(), 'stdout_sha256': digest(d / 'stdout.log'),
                       'stderr_sha256': digest(d / 'stderr.log'), 'model_calls': 0}
            write(d / 'command.json', receipt); results.append(receipt)
    expected = {(r['layer'],r['entry']):r['exit_code'] for r in results}
    ok = all(expected[(layer,entry)] == (1 if layer == 'native' and entry == 'original-uds' else 0)
             for layer in ('host','outer','native') for entry in ('permission','original-uds','equivalent-inprocess'))
    write(output / 'RESULT.json', {'gate': 'PARTIAL', 'probe_status': 'PASS' if ok else 'FAIL', 'commands': results,
        'scope': 'Equivalent business assertions; original UDS EPERM preserved; no permissions expanded',
        'private_evaluation': 'NOT_RUN', 'model_calls': 0})
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[1]).absolute()))
