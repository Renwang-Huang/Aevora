"""Owned trusted-maintainer namespace. Never used as Participant permissions."""
from audit import *
W=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/aevora')
T=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch')
R=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/orderflow_incident_lab')
RA=T/'orderflow_incident_lab';P=E/'worktree'
def runtime(*args,base=False,history=False,native=False,live=False,graph=None):
 cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());venv=cfg['venv']
 cmd=['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',cfg['runtime'],'/usr','--ro-bind','/usr/bin/bwrap','/tools/bwrap','--ro-bind','/usr/bin/git','/tools/git','--ro-bind','/usr/bin/make','/tools/make','--ro-bind','/etc/resolv.conf','/etc/resolv.conf','--ro-bind','/etc/ssl/certs','/etc/ssl/certs','--bind','/sys/fs/cgroup','/sys/fs/cgroup','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',cfg['runtime'],cfg['runtime'],'--bind',str(E),str(E)]
 if history:
  cmd+=['--ro-bind',str(T),str(T)]
  for n in ['orderflow_incident_lab','aevora_gen1_5','aevora_gen1_5_1','aevora_gen1_5_evidence','aevora_gen1_5_1_evidence','aevora_gen1_5_2_evidence']:cmd+=['--ro-bind',str(T/n),str(W.parent/n)]
  for n in ['aevora_validation','m1_validation','m1_1_validation','phase3_5_validation','runs','evidence_review']:cmd+=['--ro-bind',str(RA/n),str(P/n)]
 if live:cmd+=['--ro-bind','/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key','/maintainer/gateway.key']
 cmd+=['--ro-bind',cfg['password_file'],'/maintainer/aevora-db.password','--chdir',str(P),'--clearenv','--setenv','HOME','/tmp','--setenv','PATH',venv+'/bin:/tools:/usr/bin','--setenv','SSL_CERT_FILE','/etc/ssl/certs/ca-certificates.crt','--setenv','ORDERFLOW_BUILD_PROFILE','MAINTAINER_ONLY','--setenv','ORDERFLOW_CGROUP_PARENT',cfg['cgroup'],'--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','PYTHONPATH',str(P/'aevora_core/src')+':'+str(P/'console/src')+':'+str(P),'--setenv','GIT_OPTIONAL_LOCKS','0','--setenv','AEVORA_FALKORDB_PASSWORD_FILE','/maintainer/aevora-db.password','--setenv','AEVORA_FALKORDB_PORT',str(cfg['port']),'--setenv','AEVORA_FALKORDB_GRAPH',graph or cfg['graph'],'--setenv','AEVORA_FALKORDB_HOST','127.0.0.1']
 if native or live:cmd+=['--setenv','ORDERFLOW_CODEX_BINARY',str(E/'owned_runtime/native/codex')]
 if live:cmd+=['--setenv','ORDERFLOW_GATEWAY_SECRET_PATH','/maintainer/gateway.key','--setenv','ORDERFLOW_GATEWAY_URL','https://api.renwang-huang.top/v1','--setenv','ORDERFLOW_ENABLE_CODEX','1']
 return cmd+['/usr/bin/python3.12' if base else venv+'/bin/python',*map(str,args)]
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--history',action='store_true');p.add_argument('--base',action='store_true');p.add_argument('label');p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args();args=a.args[1:] if a.args[:1]==['--'] else a.args;raise SystemExit(record(a.label,runtime(*args,base=a.base,history=a.history)))
