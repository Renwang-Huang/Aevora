from audit import *
B=BASE.parents[0]
def runtime(*args):
 return ['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',B/'usr','/usr','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',B/'venv',B/'venv','--ro-bind',B/'native','/native','--ro-bind',B/'node','/node','--bind',E,E,'--chdir',P,'--clearenv','--setenv','HOME','/tmp','--setenv','CODEX_HOME','/tmp','--setenv','PATH',str(B/'venv/bin')+':/usr/bin','--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','PYTHONPATH',str(P/'aevora_core/src')+':'+str(P/'console/src')+':'+str(P),'--',*args]
if __name__=='__main__':
 import sys
 raise SystemExit(record(sys.argv[1],runtime(*sys.argv[2:])))
