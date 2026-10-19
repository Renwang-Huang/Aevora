"""H4 evidence receipts and isolated source releases. Historical archives are read-only."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

from scripts.aevora_h1_audit import ROOT, digest, write, now, record


def archive():
    return Path((ROOT / 'aevora_validation/H4_CURRENT').read_text().strip())


def init():
    h3 = Path((ROOT / 'aevora_validation/H3_CURRENT').read_text().strip())
    export = ROOT / 'aevora_validation/audit_exports' / h3.name
    receipt = json.loads((export / 'FINAL_DELIVERY_RECEIPT.json').read_text())
    prior = json.loads((export / 'release-h3-final-delivery-closure/SOURCE_MANIFEST.json').read_text())
    mismatch = [p for p, v in prior['source_files'].items()
                if not (ROOT/p).is_file() or digest(ROOT/p) != v['sha256']]
    if mismatch: raise ValueError('H3 delivery source mismatch: ' + repr(mismatch))
    name = 'H4-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + str(uuid.uuid4())
    a = ROOT / 'aevora_validation' / name
    (a/'g0').mkdir(parents=True, mode=0o700)
    write(a/'g0/H3_SOURCE_MANIFEST.json', prior)
    write(a/'g0/H3_DELIVERY_RECEIPT.json', receipt)
    manifest = json.loads((h3/'EVIDENCE_MANIFEST.json').read_text())
    history = json.loads((h3/'g0/PROTECTED_HISTORY.json').read_text())
    history.update({str((h3/p).relative_to(ROOT)): sha for p, sha in manifest['ordinary_files_sha256'].items()})
    for p in (h3/'EVIDENCE_MANIFEST.json', h3/'SHA256SUMS'):
        history[str(p.relative_to(ROOT))] = digest(p)
    # H3 export contains the post-seal closure. Do not traverse linked paths.
    for base, dirs, names in os.walk(export, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(base)/d).is_symlink())
        for n in sorted(names):
            p = Path(base)/n
            if p.is_file() and not p.is_symlink(): history[str(p.relative_to(ROOT))] = digest(p)
    write(a/'g0/PROTECTED_HISTORY.json', history)
    old_tests = {str(p.relative_to(ROOT)): digest(p)
                 for d in (ROOT/'tests', ROOT/'aevora_core/tests')
                 for p in d.rglob('*.py') if not p.is_symlink()}
    write(a/'g0/INHERITED_TEST_SOURCES.json', old_tests)
    write(a/'g0/FROZEN_TASK_TRUTH.json', json.loads((h3/'g0/FROZEN_TASK_TRUTH.json').read_text()))
    cases = list(ET.parse(export/'post-seal-full-regression/JUNIT.xml').getroot().iter('testcase'))
    ids = [c.get('classname','')+'::'+c.get('name','') for c in cases]
    if len(ids)!=1714 or len(ids)!=len(set(ids)): raise ValueError('Invalid H3 inherited JUnit identities')
    write(a/'g0/INHERITED_TEST_IDENTITIES.json', {'identities': ids, 'source_junit_sha256': digest(export/'post-seal-full-regression/JUNIT.xml')})
    status = subprocess.check_output(['git','status','--short','--branch'], cwd=ROOT, text=True)
    (a/'g0/GIT_STATUS.txt').write_text(status)
    write(a/'g0/BASELINE.json', {'at':now(), 'h3_archive':str(h3.relative_to(ROOT)),
          'h3_source_commit':prior['commit'], 'h3_source_tree':prior['git_tree'],
          'h3_source_files':len(prior['source_files']), 'source_mismatches':mismatch,
          'h3_lite_sha256':digest(export/'aevora-h3-audit-lite-v2.zip'),
          'root_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'root_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),
          'protected_files':len(history), 'inherited_tests':len(ids), 'new_model_calls':0,
          'trust':'Local byte verification; historical tests are not current H4 results.'})
    (ROOT/'aevora_validation/H4_CURRENT').write_text(str(a)+'\n')
    print(json.dumps({'archive':str(a),'source_files':len(prior['source_files']), 'history_files':len(history),'tests':len(ids)}))


def sources():
    prior = json.loads((archive()/'g0/H3_SOURCE_MANIFEST.json').read_text())['source_files']
    paths = {ROOT/p for p in prior}
    paths.update(ROOT.glob('AEVORA_H4_*'))
    paths.update(ROOT.glob('scripts/aevora_h4_*'))
    paths.update(ROOT.glob('tests/test_aevora_h4*'))
    paths.update((ROOT/'aevora_core/src/aevora').glob('*.py'))
    paths.update((ROOT/'aevora_core/tests').glob('test_h4*'))
    paths.add(ROOT/'aevora_core/LICENSE')
    for folder in ('h4','console'):
        if (ROOT/folder).exists():
            paths.update(p for p in (ROOT/folder).rglob('*') if not set(p.parts)&{'node_modules','__pycache__','.venv','dist','build'} and not any(part.endswith('.egg-info') for part in p.parts))
    paths.update((ROOT/'docs').glob('*.md'))
    paths.update((ROOT/'docs').glob('*.csv'))
    paths.add(ROOT/'Aevora_H4_Competition_Product_Experience_Delivery_Codex_Task_v1.0.md')
    return {str(p.relative_to(ROOT)):{'sha256':digest(p),'mode':p.stat().st_mode&0o777}
            for p in sorted(paths) if p.is_file() and not p.is_symlink()}


def release(label,receipt_parent=None):
    a=archive(); parent=Path(receipt_parent) if receipt_parent is not None else a
    if (a/'EVIDENCE_MANIFEST.json').exists() and (parent==a or parent.is_relative_to(a)):
        raise ValueError('Sealed Full is read-only; use outside-Full release receipts')
    out=parent/('release-'+label); out.mkdir(mode=0o700)
    w=ROOT/'aevora_validation/h4_worktrees'/a.name; w.mkdir(parents=True,exist_ok=True)
    env={'PATH':'/usr/bin:/bin','HOME':str(out),'LANG':'C.UTF-8',
         'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_NOSYSTEM':'1'}
    count=0
    def git(*args):
        nonlocal count
        argv=['git','-c','core.hooksPath=/dev/null',*args]
        r=subprocess.run(argv,cwd=w,env=env,capture_output=True,text=True);count+=1
        write(out/('command-'+str(count)+'.json'), {'argv':argv,'cwd':str(w),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'at':now()})
        if r.returncode: raise ValueError('Source release failed; receipt retained')
        return r.stdout.strip()
    if not (w/'.git').exists(): git('init','-b','aevora-h4-releases')
    rows=sources(); stale=set(git('ls-files').splitlines())-set(rows)
    if stale:git('rm','--force','--',*sorted(stale))
    for p,v in rows.items():
        target=w/p; target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_symlink(): raise ValueError('Linked release destination')
        shutil.copyfile(ROOT/p,target);target.chmod(v['mode'])
    git('add','--force','--',*rows)
    git('-c','user.name=Aevora H4 Local Release','-c','user.email=aevora-h4@invalid','commit','-m','Aevora H4 '+label)
    result={'commit':git('rev-parse','HEAD'),'git_tree':git('rev-parse','HEAD^{tree}'),
            'source_files':rows,'at':now(),'root_index_staged':False}
    write(out/'SOURCE_MANIFEST.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='source_files'}))


def launch(*args, live=False, port=None, graph=None, password_file=None):
    h3=Path((ROOT/'aevora_validation/H3_CURRENT').read_text().strip())
    cfg=json.loads((h3/'CONFIG.json').read_text())
    if (archive()/'CONFIG.json').exists():cfg=json.loads((archive()/'CONFIG.json').read_text())
    return ['env','ORDERFLOW_ENABLE_CODEX='+('1' if live else '0'),'AEVORA_H2_RUNTIME='+cfg['runtime'],
            'AEVORA_FALKORDB_PASSWORD_FILE='+str(password_file or cfg['password_file']),
            'AEVORA_FALKORDB_PORT='+str(port or cfg.get('port',17691)),'AEVORA_FALKORDB_GRAPH='+(graph or cfg['graph']),
            str(ROOT/'scripts/aevora-h2-python'),*map(str,args)]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
    s.add_parser('init');q=s.add_parser('release');q.add_argument('label')
    q=s.add_parser('record');q.add_argument('label');q.add_argument('argv',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if a.op=='init':init()
    elif a.op=='release':release(a.label)
    else:raise SystemExit(record(archive(),a.label,a.argv[1:] if a.argv[:1]==['--'] else a.argv))
