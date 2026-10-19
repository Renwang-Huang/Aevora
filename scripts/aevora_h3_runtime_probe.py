"""Actual installed official CLI fields and TLS, with no model/secret output."""
import json
import os
from pathlib import Path
import subprocess
from scripts.aevora_h3_audit import archive, write
from scripts.m11_calibration import tls_probe


def main():
    out=archive()/'g1/runtime-probe';out.mkdir(mode=0o700)
    binary=os.environ['ORDERFLOW_CODEX_BINARY'];rows=[]
    for args in [('--version',),('exec','--help'),('features','list'),('sandbox','--help'),('mcp','add','--help')]:
        result=subprocess.run([binary,*args],capture_output=True,text=True,timeout=30)
        row={'argv':[binary,*args],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        rows.append(row);write(out/('command-'+str(len(rows))+'.json'),row)
    if any(r['exit_code'] for r in rows):raise ValueError('Official CLI probe failed')
    tls=tls_probe('https://api.renwang-huang.top/v1');write(out/'TLS.json',tls)
    write(out/'RESULT.json',{'status':'PASS','actual_codex_version':rows[0]['stdout'].strip(),'model_calls':0,
        'model_service_completion':'UNVERIFIED_UNTIL_FRESH_NATIVE_SESSION','tls':tls})
    print(json.dumps({'status':'PASS','actual_codex_version':rows[0]['stdout'].strip(),'model_calls':0}))


if __name__=='__main__':main()
