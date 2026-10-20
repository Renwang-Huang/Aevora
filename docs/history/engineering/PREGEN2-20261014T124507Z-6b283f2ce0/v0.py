from audit import *
import stat,xml.etree.ElementTree as ET,collections,shutil,socket
os.umask(0o077)
for label,args in [('status',['status','--porcelain=v1']),('branch',['branch','--show-current']),('head',['rev-parse','HEAD']),('tree',['rev-parse','HEAD^{tree}']),('remote',['remote','-v']),('objects',['count-objects','-v']),('worktrees',['worktree','list','--porcelain']),('ls-files',['ls-files','-z']),('fsck',['fsck','--full'])]:
 assert record('v0-git-'+label,['git','-C',W,*args])==0
raw=lambda n:(E/'commands'/('v0-git-'+n)/'stdout.log').read_bytes()
assert raw('head').strip().decode()==C['head'] and raw('tree').strip().decode()==C['tree'] and raw('branch').strip()==b'aevora-gen2-baseline' and raw('status')==b''
prior=json.loads((G5/'g5/ACTIVE_SOURCE_IDENTITY.json').read_text())['source547_sha256']
current={p:sha(W/p) for p in prior};delta=[p for p in prior if prior[p]!=current[p]]
tracked=[x.decode() for x in raw('ls-files').split(b'\0') if x]
assert len(prior)==547 and not delta and set(prior)==set(tracked)
objects=[p for p in (W/'.git/objects').rglob('*') if p.is_file()]
integrity={'at':now(),'status':'PASS','head':C['head'],'tree':C['tree'],'branch':'aevora-gen2-baseline','clean':True,'ordinary_git':(W/'.git').is_dir() and not (W/'.git').is_symlink(),'alternates':(W/'.git/objects/info/alternates').exists(),'git_file_nlink_max':max(p.stat().st_nlink for p in objects),'source_definition':'exact path->SHA mapping g5/ACTIVE_SOURCE_IDENTITY.json source547_sha256; includes documentation/configs, not only executable code','source_count':len(current),'prior_receipt_sha256':sha(G5/'g5/ACTIVE_SOURCE_IDENTITY.json'),'deltas':delta,'source547_sha256':current}
assert integrity['ordinary_git'] and not integrity['alternates'] and integrity['git_file_nlink_max']==1
write(E/'00_environment/repo_integrity.json',integrity)
(E/'00_environment/git_baseline.txt').write_text('\n'.join(n+'\n'+raw(n).decode(errors='replace') for n in ['status','branch','head','tree','remote','objects','worktrees']))
x=ET.parse(G5/'g5/full-regression/JUNIT.xml')
ids=[c.get('classname','')+'::'+c.get('name','') for c in x.iter('testcase')]
assert len(ids)==1836 and len(set(ids))==1836
(E/'02_regression/expected_test_ids.txt').write_text('\n'.join(sorted(ids))+'\n')
write(E/'02_regression/EXPECTED_RECEIPT.json',{'source':str(G5/'g5/full-regression/JUNIT.xml'),'sha256':sha(G5/'g5/full-regression/JUNIT.xml'),'identity_convention':'JUnit classname::name; established G5 comparison','count':len(ids),'unique':len(set(ids)),'expected_ids_sha256':sha(E/'02_regression/expected_test_ids.txt')})
commands=[('os',['uname','-a']),('uid',['id']),('clock',['date','-u','--iso-8601=seconds']),('disk',['df','-B1',str(E),str(W)]),('filesystem',['findmnt','-T',str(E)]),('docker-version',['docker','version','--format','{{json .}}']),('docker-owned-inventory',['docker','ps','-a','--format','{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}']),('ports',['ss','-ltn']),('node',['node','--version']),('npm',['npm','--version']),('codex',['codex','--version']),('codex-help',['codex','exec','--help']),('codex-features',['codex','features','list']),('bwrap',['bwrap','--version']),('workspace',['python3',str(W/'tools/workspace_check.py')]),('dev-help',['python3',str(W/'tools/dev.py'),'--help'])]
for label,cmd in commands:record('v0-'+label,cmd,cwd=W)
write(E/'00_environment/resource_budget.json',{'at':now(),'new_codex_sessions_cap':4,'model_request_cap':40,'unit':'Gateway authenticated admitted response POSTs; actual implementation to be verified before online call','session_concurrency':1,'provider_concurrency_cap':2,'soft_usd_budget':20,'hard_usd_cap':'UNAVAILABLE until actual provider capability verified','completion_policy':'completion-aware','fixed_task_timeout':None,'max_supervision_window':'PAUSED_PENDING_REVIEW if activity persists; not task TIMEOUT','budget_status':'NO_MODEL_REQUESTS_YET; guard must pass V5 protocol freeze'})
print('V0 baseline547 and expected1836 identity PASS',flush=True)
