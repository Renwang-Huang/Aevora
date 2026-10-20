from audit import *
ACTIVE=W
import shutil
p=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/aevora_gen1_5_2_evidence/Gen1.5.2-20261014T065322Z-01fb65a2-eac4-4ce4-a468-9fe5de1a8567-prearchive-review');h=E/'05_product/vscode-api-harness';h.mkdir()
for n in ['package.json','extension.js','test.cjs']:shutil.copyfile(p/'g2/vscode-api-harness'/n,h/n)
views=E/'05_product/editor-views';views.mkdir()
for view in ['Product','Maintainer']:
 fn='Aevora.'+view+'.code-workspace';v=json.loads((ACTIVE/fn).read_text())
 for f in v['folders']:f['path']=os.path.relpath(ACTIVE/f['path'],views)
 (views/fn).write_text(json.dumps(v,indent=2)+'\n')
 profile=E/'05_product'/('vscode-'+view.lower());profile.mkdir();(profile/'User').mkdir()
 (profile/'User/settings.json').write_text(json.dumps({'security.workspace.trust.enabled':False,'update.mode':'none','telemetry.telemetryLevel':'off','terminal.integrated.defaultProfile.linux':'Audit Bash','terminal.integrated.profiles.linux':{'Audit Bash':{'path':'/bin/bash','args':['--noprofile','--norc']}}}))
 argv=['env','-u','VSCODE_IPC_HOOK_CLI','timeout','180','code','--new-window','--disable-extensions','--skip-welcome','--skip-release-notes','--user-data-dir',str(profile),'--extensions-dir',str(profile/'extensions'),'--extensionDevelopmentPath='+str(h),'--extensionTestsPath='+str(h/'test.cjs'),str(views/fn)]
 assert record('v4-native-vscode-'+view.lower(),argv)==0
 result=E/'05_product'/('api-ui-terminal-'+fn)/'RESULT.json';fail=result.with_name('FAILURE.json');end=time.monotonic()+120
 while not result.exists() and not fail.exists() and time.monotonic()<end:time.sleep(.2)
 assert result.exists() and json.loads(result.read_text())['status']=='PASS',str(fail)
write(E/'05_product/EDITOR_RESULT.json',{'status':'PASS','native_views':2,'checks_per_view':6,'canonical_config_sha_unchanged':True,'mode':'Equivalent temporary workspace copies; fresh isolated profiles; actual newaevora folders','visual_status':'VISUAL_UNVERIFIED','model_calls':0})
print('V4_NATIVE_EDITOR_PASS')
