"""Create an explicit Gate source commit in the isolated H2 release repository.

Never stages the user's original working tree. Ordinary allowlisted source
only; runtime caches, environment files, archives and credentials are excluded.
"""
from datetime import datetime,timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from scripts.aevora_h2_audit import ROOT,sources,digest,write


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('label');p.add_argument('release_repository',type=Path);a=p.parse_args()
 A=a.archive.resolve(strict=True); W=a.release_repository.resolve(strict=True)
 if W==ROOT or not (W/'.git').is_dir() or ROOT/'aevora_validation/h2_worktrees' not in W.parents:
  raise ValueError('Only the dedicated H2 release repository is permitted')
 if not a.label.replace('-','').replace('_','').isalnum():raise ValueError('Simple unique gate label required')
 d=A/('release-'+a.label);d.mkdir();rows=sources()
 for rel,row in rows.items():
  target=W/rel
  if target.is_symlink():raise ValueError('Release source symlink refused')
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target);target.chmod(row['mode'])
 env={'PATH':'/usr/bin:/bin','HOME':str(d),'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','LANG':'C.UTF-8'}
 cmds=[]
 def run(argv):
  r=subprocess.run(['git','-c','core.hooksPath=/dev/null',*argv],cwd=W,env=env,capture_output=True,text=True)
  cmds.append({'argv':['git','-c','core.hooksPath=/dev/null',*argv],'cwd':str(W),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  write(d/('command-'+str(len(cmds))+'.json'),cmds[-1])
  if r.returncode:raise ValueError('Source commit failed; preserve receipt')
  return r.stdout.strip()
 # Existing generic ignore patterns also cover requirements.lock.txt and some
 # maintainer evidence docs. Only these independently selected source paths are
 # explicitly added; never force-add a runtime or archive directory.
 tracked=set(run(['ls-files']).splitlines())
 stale=sorted(tracked-set(rows))
 # The dedicated release repository contains only earlier selected source.
 # Explicitly remove paths that this new allowlist no longer admits; earlier
 # release commits and the original user checkout remain intact.
 if stale:run(['rm','--force','--',*stale])
 run(['add','--force','--',*rows])
 run(['-c','user.name=Aevora H2 Local Release','-c','user.email=aevora-h2@invalid','commit','-m','Aevora H2 '+a.label+' source release'])
 commit=run(['rev-parse','HEAD']);tree=run(['rev-parse','HEAD^{tree}'])
 import hashlib
 source_sha=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 for rel,row in rows.items():
  if digest(W/rel)!=row['sha256']:raise ValueError('Release copy mismatch')
 write(d/'SOURCE_MANIFEST.json',{'source_files':rows,'source_tree_sha256':source_sha,'commit':commit,'git_tree':tree,'recorded_at':datetime.now(timezone.utc).isoformat(),'qualification':'New local release commit of current source; not fabricated historical H1 commit'})
 write(d/'COMMIT_RECEIPT.json',{'commit':commit,'git_tree':tree,'source_tree_sha256':source_sha,'command_results':cmds,'original_git_index_staged':False})
 print(json.dumps({'commit':commit,'git_tree':tree,'source_tree_sha256':source_sha,'source_files':len(rows)}))
if __name__=='__main__':main()
