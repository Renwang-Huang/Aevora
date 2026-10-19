#!/usr/bin/env python3
"""Bounded, owned-only FalkorDB reliability probes; never a production migrator.

Uses Redis RESP directly, stores secret-safe receipts, and stops at the first
unexpected server exit. Historical crash logs are AES-GCM encrypted; the key
remains outside the evidence archive. No reproduction means NOT_REPRODUCED.
"""
from __future__ import annotations
import argparse, base64, concurrent.futures as cf, csv, hashlib, json, os, pathlib
import platform, re, secrets, socket, subprocess, time, urllib.request
from datetime import datetime, timezone

IMAGE='falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
OLD=None
NAME=None
PORT=None

def sha(b): return hashlib.sha256(b).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()

class RedisError(Exception): pass
class RESP:
    def __init__(self,password,port=None): self.password=password; self.port=PORT if port is None else port
    def _read(self,f):
        line=f.readline()
        if not line: raise ConnectionError('RESP EOF')
        prefix=line[:1]; v=line[1:-2]
        if prefix==b'+': return v.decode()
        if prefix==b'-': raise RedisError(v.decode())
        if prefix==b':': return int(v)
        if prefix==b'$':
            n=int(v)
            if n<0:return None
            b=f.read(n); assert f.read(2)==b'\r\n'; return b.decode(errors='replace')
        if prefix==b'*': return [self._read(f) for _ in range(int(v))]
        raise ValueError('Unknown RESP type')
    def cmd(self,*args):
        with socket.create_connection(('127.0.0.1',self.port),timeout=15) as s:
            s.settimeout(20); f=s.makefile('rb')
            def send(parts):
                a=[str(x).encode() if not isinstance(x,bytes) else x for x in parts]
                s.sendall(b'*'+str(len(a)).encode()+b'\r\n'+b''.join(b'$'+str(len(x)).encode()+b'\r\n'+x+b'\r\n' for x in a))
                return self._read(f)
            send(('AUTH',self.password)); return send(args)
    def q(self,query,graph='g24_probe_v3'): return self.cmd('GRAPH.QUERY',graph,query)

class Audit:
    def __init__(self,evidence,secret_dir,resume=False,redact_files=()):
        self.resume=resume
        self.e=pathlib.Path(evidence).resolve(); self.out=self.e/'07_reliability'; self.out.mkdir(parents=True,exist_ok=True)
        self.secret_dir=pathlib.Path(secret_dir).absolute()
        if self.secret_dir.is_relative_to(self.e) or self.secret_dir.is_symlink():
            raise ValueError('Secret directory must be external and unlinked')
        self.secret_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.secret_dir.stat().st_mode & 0o077:
            raise ValueError('Secret directory must be owner-only')
        self.password_file=self.secret_dir/'reliability.password'
        if not self.password_file.exists():
            with self.password_file.open('x') as f: f.write(secrets.token_hex(32))
            self.password_file.chmod(0o600)
        info=self.password_file.lstat()
        if self.password_file.is_symlink() or info.st_nlink!=1 or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ValueError('Credential file rejected')
        self.password=self.password_file.read_text().strip(); self.patterns=[self.password.encode()]
        for file in redact_files:
            p=pathlib.Path(file)
            if p.is_symlink() or not p.is_file():raise ValueError('Invalid explicit redaction input')
            self.patterns.append(p.read_bytes().strip())
        self.patterns=[z for p in self.patterns if len(p)>=16 for z in (p,sha(p).encode(),base64.b64encode(p))]
        self.records=[]; self.rows=[]; self.r=RESP(self.password)
    def redact(self,b):
        for v in self.patterns:b=b.replace(v,b'[REDACTED_SECRET]')
        return re.sub(rb'(requirepass|masterauth)([\s:=]+)[^\s\"\']+',rb'\1\2[REDACTED]',b,flags=re.I)
    def put(self,name,obj):
        p=self.out/name;p.parent.mkdir(parents=True,exist_ok=True)
        b=json.dumps(obj,indent=2,sort_keys=True,default=str).encode()+b'\n';p.write_bytes(self.redact(b));return p
    def command(self,args,label,timeout=120):
        start=utc(); p=subprocess.run(args,capture_output=True,timeout=timeout)
        raw=p.stdout+p.stderr; safe=self.redact(raw)
        path=self.out/'commands'/f'{len(self.records):03}-{label}.log';path.parent.mkdir(exist_ok=True);path.write_bytes(safe)
        self.records.append(dict(command=args,start=start,end=utc(),exit_code=p.returncode,redacted_sha256=sha(safe),output=str(path.relative_to(self.out))))
        self.put('COMMANDS.json',self.records)
        if p.returncode: raise RuntimeError(f'{label}: command exit {p.returncode}')
        return p.stdout
    def safe_inspect(self,name):
        p=subprocess.run(['docker','inspect',name],capture_output=True,check=True)
        x=json.loads(p.stdout)[0]
        return {k:x.get(k) for k in ('Id','Created','Image','State','Mounts')} | {'Name':x['Name'],'HostConfig':{k:x['HostConfig'].get(k) for k in ('Memory','MemorySwap','NanoCpus','PidsLimit','RestartPolicy','SecurityOpt','Ulimits','ReadonlyRootfs')},'Config':{'Image':x['Config']['Image'],'User':x['Config']['User'],'Labels':x['Config'].get('Labels',{})}}
    def require_owned(self,state):
        if state['Config']['Labels'].get('aevora.owner') != NAME:
            raise RuntimeError('Container ownership label mismatch; refusing mutation')
    def alive(self):
        x=self.safe_inspect(NAME)
        self.require_owned(x)
        if not x['State']['Running']: self.put('UNEXPECTED_EXIT.json',x); raise RuntimeError(f'Owned reliability DB exited {x["State"]["ExitCode"]}; stop probes')
        return x
    def wait(self):
        for _ in range(60):
            try:
                if self.r.cmd('PING')=='PONG':return
            except (OSError,RedisError,ConnectionError):pass
            time.sleep(.25)
        raise RuntimeError('Owned DB not ready')
    def query(self,q,label):
        start=utc(); result=self.r.q(q)
        self.put('queries/'+label+'.json',dict(query=q,start=start,end=utc(),result=result));return result
    def snapshot(self,label):
        nodes=self.query('MATCH (n) RETURN labels(n), n.id, n.epoch, n.value ORDER BY n.id',label+'-nodes')
        edges=self.query('MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id ORDER BY a.id, b.id',label+'-edges')
        # Timing/cached-query metadata are not graph contents.
        content={'nodes':nodes[:2],'edges':edges[:2]}
        self.put('snapshots/'+label+'.json',content);return sha(json.dumps(content,sort_keys=True).encode())
    def probe(self,name,fn,hypothesis):
        t=time.monotonic(); before=self.alive()
        try:
            result=fn(); after=self.alive(); status='NOT_REPRODUCED'
            row=dict(probe=name,hypothesis=hypothesis,status=status,elapsed_seconds=round(time.monotonic()-t,3),result=result,before_started_at=before['State']['StartedAt'],after_started_at=after['State']['StartedAt'])
        except Exception as ex:
            row=dict(probe=name,hypothesis=hypothesis,status='PROBE_ERROR',elapsed_seconds=round(time.monotonic()-t,3),error=self.redact(str(ex).encode()).decode())
            self.rows.append(row);self.put('PROBE_RESULTS.json',self.rows);raise
        self.rows.append(row);self.put('PROBE_RESULTS.json',self.rows)
        return row
    def preserve(self):
        old=self.safe_inspect(OLD); assert old['State']['ExitCode']==139 and not old['State']['Running']
        self.put('HISTORICAL_CONTAINER.json',old)
        raw=subprocess.run(['docker','logs',OLD],capture_output=True,check=True).stdout
        # docker logs can use stderr for diagnostics. Preserve both streams exactly.
        p=subprocess.run(['docker','logs',OLD],capture_output=True,check=True);raw=p.stdout+p.stderr
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        keyfile=self.secret_dir/'reliability-raw-aes.key'
        if not keyfile.exists():keyfile.write_bytes(AESGCM.generate_key(bit_length=256));keyfile.chmod(0o600)
        nonce=os.urandom(12);encrypted=nonce+AESGCM(keyfile.read_bytes()).encrypt(nonce,raw,b'G24 historical docker logs')
        (self.out/'historical-crash.raw.aesgcm').write_bytes(encrypted)
        assert AESGCM(keyfile.read_bytes()).decrypt(encrypted[:12],encrypted[12:],b'G24 historical docker logs')==raw
        safe=self.redact(raw);(self.out/'historical-crash.redacted.log').write_bytes(safe)
        self.put('HISTORICAL_LOG_RECEIPT.json',dict(source_command=['docker','logs',OLD],exit_code=p.returncode,raw_sha256=sha(raw),redacted_sha256=sha(safe),encrypted_sha256=sha(encrypted),encrypted_bytes=len(encrypted),key_location='HOST_ONLY_OUTSIDE_ARCHIVE',decrypt_roundtrip='PASS',core_dump='UNAVAILABLE_NOT_CAPTURED',captured_at=utc()))
        image=json.loads(subprocess.run(['docker','image','inspect',old['Image']],capture_output=True,check=True).stdout)[0]
        self.put('IMAGE.json',{k:image[k] for k in ('Id','RepoTags','RepoDigests','Architecture','Os','Created','Size')})
        binaries={}
        for label,path in [('redis-server','/usr/local/bin/redis-server'),('falkordb.so','/var/lib/falkordb/bin/falkordb.so')]:
            dest=self.out/'binaries'/label;dest.parent.mkdir(exist_ok=True)
            self.command(['docker','cp',OLD+':'+path,str(dest)],'preserve-'+label)
            binaries[label]={'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'source':OLD+':'+path}
        self.put('ENGINE_ENV_AND_DIGESTS.json',dict(historical=old,image=json.loads((self.out/'IMAGE.json').read_text()),binaries=binaries,host={'uname':platform.uname()._asdict(),'core_pattern':pathlib.Path('/proc/sys/kernel/core_pattern').read_text().strip(),'meminfo':pathlib.Path('/proc/meminfo').read_text()},historical_cgroup_events='UNAVAILABLE_STOPPED_CGROUP_REMOVED',current_cgroup_events='captured_for_new_owned_instance',pinned_image=IMAGE,captured_at=utc()))
    def official(self):
        urls=[('issue-2201','https://api.github.com/repos/FalkorDB/FalkorDB/issues/2201'),('issue-238','https://api.github.com/repos/FalkorDB/FalkorDB/issues/238'),('issue-2880','https://api.github.com/repos/FalkorDB/FalkorDB/issues/2880'),('release-4.20.4','https://api.github.com/repos/FalkorDB/FalkorDB/releases/tags/v4.20.4'),('release-4.20.7','https://api.github.com/repos/FalkorDB/FalkorDB/releases/tags/v4.20.7')]
        receipts=[]
        for label,url in urls:
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'Aevora-G24-reliability-audit','Accept':'application/vnd.github+json'})
                with urllib.request.urlopen(req,timeout=30) as r:b=r.read();code=r.status
                (self.out/'official').mkdir(exist_ok=True);(self.out/'official'/f'{label}.json').write_bytes(b)
                receipts.append(dict(url=url,retrieved_at=utc(),http_status=code,sha256=sha(b),bytes=len(b),file='official/'+label+'.json'))
            except Exception as ex:receipts.append(dict(url=url,retrieved_at=utc(),error=str(ex),status='UNAVAILABLE'))
        self.put('OFFICIAL_SOURCE_RECEIPTS.json',receipts)
    def start(self):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',PORT))==0:raise RuntimeError('Reserved port in use')
        exists=subprocess.run(['docker','inspect',NAME],capture_output=True).returncode==0
        if exists:
            if not self.resume:raise RuntimeError('Owned name already exists; explicit resume required')
            state=self.safe_inspect(NAME)
            self.require_owned(state)
            if state['State']['Running'] or state['State']['ExitCode']!=0:raise RuntimeError('Resume allowed only after clean owned stop')
            self.command(['docker','start',NAME],'explicit-owned-resume');self.wait();self.put('OWNED_INITIAL.json',self.alive());return
        data=self.e/'reliability-db-data';data.mkdir(mode=0o700)
        config=self.secret_dir/'reliability.redis.conf'
        config.write_text(f'bind 0.0.0.0\nprotected-mode yes\nport 6379\nrequirepass {self.password}\nloadmodule /var/lib/falkordb/bin/falkordb.so THREAD_COUNT 2\ndir /data\nsave ""\nappendonly no\nmaxmemory 768mb\nmaxmemory-policy noeviction\nlogfile ""\n')
        config.chmod(0o600)
        self.command(['docker','run','-d','--name',NAME,'--label','aevora.owner='+NAME,'--memory','1g','--memory-swap','1g','--cpus','1','--pids-limit','256','--ulimit','core=0','--restart','no','-p',f'127.0.0.1:{PORT}:6379','-v',str(data)+':/data','-v',str(config)+':/run/aevora/redis.conf:ro','--entrypoint','/usr/local/bin/redis-server',IMAGE,'/run/aevora/redis.conf'],'start-owned')
        self.wait();self.put('OWNED_INITIAL.json',self.alive())
        self.put('OWNED_RUNTIME_INFO.json',{'server_info':self.r.cmd('INFO','server'),'memory_info':self.r.cmd('INFO','memory'),'module_list':self.r.cmd('MODULE','LIST')})
    def cgroup(self,label):
        self.command(['docker','exec',NAME,'sh','-c','cat /sys/fs/cgroup/memory.events; cat /sys/fs/cgroup/memory.peak; cat /sys/fs/cgroup/pids.events; cat /sys/fs/cgroup/cpu.stat'],label)
    def restart(self,label):
        self.command(['docker','restart','-t','20',NAME],label);self.wait();self.alive()
    def probes(self):
        self.cgroup('cgroup-before')
        self.query('UNWIND range(0,127) AS i CREATE (:Probe {id:i, epoch:0, value:"synthetic"})','init-nodes')
        self.query('MATCH (a:Probe),(b:Probe) WHERE a.id < 127 AND b.id = a.id + 1 CREATE (a)-[:NEXT]->(b)','init-edges')
        baseline=self.snapshot('baseline')
        def copy_decode():
            for i in range(40):
                target=f'g24_v3_copy_{i}';self.r.cmd('GRAPH.COPY','g24_probe_v3',target)
                x=self.r.q('MATCH (n) RETURN count(n)',target);assert x[1]==[[128]],x
                self.r.cmd('GRAPH.DELETE',target)
            assert self.snapshot('copy-final')==baseline
            return {'copy_decode_delete_cycles':40,'nodes_per_copy':128,'content_sha256':baseline}
        self.probe('COPY_DECODE_DELETE',copy_decode,'H_COPY_OR_DECODE')
        def rdb():
            snapshots=[]
            for i in range(3):
                assert self.r.cmd('SAVE')=='OK';self.restart(f'rdb-restart-{i}')
                snapshots.append(self.snapshot(f'rdb-reload-{i}'));assert snapshots[-1]==baseline
            return {'save_restart_cycles':3,'snapshot_sha256':snapshots,'saved_state_exact':True}
        self.probe('RDB_SAVE_RELOAD',rdb,'H_RDB_RELOAD')
        def aof():
            self.r.cmd('CONFIG','SET','appendonly','yes');self.r.cmd('CONFIG','SET','appendfsync','always')
            for i in range(32): self.r.q(f'MATCH (n:Probe) WHERE n.id={i} SET n.epoch=1')
            expected=self.snapshot('aof-before');self.r.cmd('BGREWRITEAOF')
            for _ in range(100):
                info=self.r.cmd('INFO','persistence')
                if 'aof_rewrite_in_progress:0' in info:break
                time.sleep(.1)
            assert 'aof_rewrite_in_progress:0' in self.r.cmd('INFO','persistence')
            # Runtime CONFIG SET is not written back into the host-only config.
            # Persist enablement in that config for the deliberate replay probes.
            cfg=self.secret_dir/'reliability.redis.conf';cfg.write_text(cfg.read_text().replace('appendonly no','appendonly yes').replace('logfile ""','appendfsync always\nlogfile ""'));cfg.chmod(0o600)
            hashes=[]
            for i in range(3): self.restart(f'aof-restart-{i}');hashes.append(self.snapshot(f'aof-reload-{i}'));assert hashes[-1]==expected
            self.r.cmd('CONFIG','SET','appendonly','no');cfg.write_text(cfg.read_text().replace('appendonly yes','appendonly no'));cfg.chmod(0o600)
            self.r.cmd('SAVE')
            return {'normal_aof_replay_cycles':3,'snapshot_sha256':hashes,'external_load_csv_failure_not_exercised':True}
        self.probe('AOF_NORMAL_RELOAD',aof,'H_AOF_REPLAY')
        def concurrent():
            events=[]
            def worker(k):
                for i in range(100):
                    if k%2:self.r.q('MATCH (n:Probe) WHERE n.id < 64 SET n.epoch=n.epoch+1 RETURN count(n)')
                    else:self.r.q('MATCH (a:Probe)-[:NEXT]->(b:Probe) RETURN count(b),sum(b.epoch)')
                return {'worker':k,'operations':100,'mode':'write' if k%2 else 'read'}
            with cf.ThreadPoolExecutor(max_workers=4) as pool:events=list(pool.map(worker,range(4)))
            result=self.query('MATCH (n:Probe) RETURN count(n),sum(n.epoch)','concurrent-final')
            assert result[1]==[[128,12832]],result
            return {'threads':4,'operations':400,'operation_breakdown':events,'accounting_exact':True,'not_full_Q07_publication':True}
        self.probe('CONCURRENT_QUERY_UPDATES',concurrent,'H_CONCURRENT_PUBLISH_QUERY')
        def timer():
            start=time.monotonic();pings=0
            while time.monotonic()-start<30:
                assert self.r.cmd('PING')=='PONG';self.alive();pings+=1;time.sleep(.5)
            return {'observed_seconds':round(time.monotonic()-start,3),'pings':pings,'no_timer_fault_injection':True}
        self.probe('TIMER_OBSERVATION',timer,'H_MODULE_TIMER')
        def resource():
            used=int(re.search(r'^used_memory:(\d+)',self.r.cmd('INFO','memory'),re.M)[1])
            self.r.cmd('CONFIG','SET','maxmemory',max(1,used-1024))
            message=''
            try:self.r.cmd('SET','g24_large_synthetic',b'x'*(4*1024*1024))
            except RedisError as ex:message=str(ex)
            assert 'OOM' in message,message
            self.r.cmd('CONFIG','SET','maxmemory','768mb');assert self.r.cmd('PING')=='PONG'
            self.cgroup('cgroup-after-resource')
            return {'redis_maxmemory_refusal':'OOM','cgroup_oom_injection':False,'payload_bytes':4*1024*1024,'redis_memory_used_before':used,'graph_operable':self.r.q('MATCH (n) RETURN count(n)')[1]==[[128]]}
        self.probe('RESOURCE_REFUSAL',resource,'H_RESOURCE_EXHAUSTION')
        def crash_tail():
            before=self.snapshot('rpo-saved');self.r.cmd('SAVE')
            self.r.q('CREATE (:UnsavedTail {id:1000, epoch:1, value:"not_saved"})')
            self.command(['docker','kill','--signal','KILL',NAME],'controlled-sigkill')
            state=self.safe_inspect(NAME);assert state['State']['ExitCode']==137 and not state['State']['OOMKilled'],state
            self.put('CONTROLLED_SIGKILL.json',state)
            self.command(['docker','start',NAME],'restart-after-sigkill');self.wait()
            after=self.snapshot('rpo-restored');assert after==before
            absent=self.r.q('MATCH (n:UnsavedTail) RETURN count(n)')[1]==[[0]];assert absent
            return {'controlled_exit':137,'same_as_original_139':False,'saved_sha256':before,'restored_sha256':after,'unsaved_tail_lost':True,'durability_claim':'ONLY_LAST_EXPLICIT_SAVE','aof_enabled':False}
        self.probe('RDB_SAVED_STATE_AND_UNSAVED_TAIL',crash_tail,'H_RECOVERY_RPO')
        self.cgroup('cgroup-final');self.r.cmd('SAVE')
        self.put('FINAL_SAVED_SNAPSHOT.json',{'sha256':self.snapshot('final'),'lastsave':self.r.cmd('LASTSAVE')})
    def finish(self):
        self.require_owned(self.safe_inspect(NAME))
        self.command(['docker','stop','-t','20',NAME],'final-graceful-stop')
        self.put('OWNED_FINAL.json',self.safe_inspect(NAME));self.put('HISTORICAL_CONTAINER_AFTER.json',self.safe_inspect(OLD)) if OLD else None
        p=subprocess.run(['docker','logs',NAME],capture_output=True,check=True);raw=p.stdout+p.stderr;safe=self.redact(raw)
        (self.out/'owned-db.redacted.log').write_bytes(safe)
        self.put('OWNED_LOG_RECEIPT.json',{'raw_sha256':sha(raw),'redacted_sha256':sha(safe),'bytes':len(raw),'no_secret_value_recorded':True})
        with (self.out/'CRASH_REPRO_MATRIX.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['probe','hypothesis','status','elapsed_seconds','result']);w.writeheader()
            for r in self.rows:w.writerow({k:json.dumps(r.get(k),sort_keys=True) if isinstance(r.get(k),dict) else r.get(k,'') for k in w.fieldnames})
        index=[]
        for p in sorted(self.out.rglob('*')):
            if p.is_file() and p.name not in {'CRASH_RAW_INDEX.csv'}:index.append({'path':str(p.relative_to(self.out)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size,'classification':'PRIVATE_ENCRYPTED_RAW' if p.suffix=='.aesgcm' else 'PRIVATE_BINARY' if p.parent.name=='binaries' else 'SANITIZED_EVIDENCE'})
        with (self.out/'CRASH_RAW_INDEX.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(index[0]));w.writeheader();w.writerows(index)
        self.put('RESULT.json',{'status':'MITIGATED_WITH_RISK','original_root_cause':'UNVERIFIED','synthetic_probes':len(self.rows),'not_reproduced':sum(x['status']=='NOT_REPRODUCED' for x in self.rows),'fixed_claim':False,'owned_final_exit':self.safe_inspect(NAME)['State']['ExitCode'],'old_container_unchanged_stopped_139':self.safe_inspect(OLD)['State']['ExitCode']==139 if OLD else 'NOT_REQUESTED','ended_at':utc()})

def main():
    global OLD,NAME,PORT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--secret-dir',required=True,help='External owner-only directory, never exported')
    parser.add_argument('--owned-name',required=True,help='Fresh aevora-reliability-* Docker container')
    parser.add_argument('--port',required=True,type=int)
    parser.add_argument('--historical-container',help='Optional read-only historical stopped exit139 source')
    parser.add_argument('--redact-file',action='append',default=[],help='Explicit local redaction input, never exported')
    parser.add_argument('--fetch-official',action='store_true',help='Fetch external public issue metadata')
    parser.add_argument('--execute',action='store_true',help='Run destructive probes only inside this owned container')
    parser.add_argument('--resume-owned',action='store_true')
    a=parser.parse_args()
    if not a.execute:parser.error('--execute is required; no default DB operations')
    if not re.fullmatch(r'aevora-reliability-[a-z0-9-]{1,48}',a.owned_name):parser.error('Owned name must use aevora-reliability-*')
    if not 1024 <= a.port <= 65535:parser.error('Explicit unprivileged port required')
    NAME=a.owned_name;PORT=a.port;OLD=a.historical_container
    audit=Audit(a.evidence,a.secret_dir,a.resume_owned,a.redact_file)
    if OLD:audit.preserve()
    if a.fetch_official:audit.official()
    audit.start()
    try:audit.probes()
    finally:
        try:
            if audit.safe_inspect(NAME)['State']['Running']:audit.finish()
        except Exception as ex:
            audit.put('FINALIZE_ERROR.json',{'error':audit.redact(str(ex).encode()).decode()});raise
    print(json.dumps(json.loads((audit.out/'RESULT.json').read_text())))

if __name__=='__main__':main()
