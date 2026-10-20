"""One authoring source, byte-exact standalone public evidence consumers."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "tools/public_evidence/hero_verify.py": ["examples/observatory/verify_hero.py", "console/src/aevora_observatory/_hero_verify.py"],
    "tools/public_evidence/projection.py": ["examples/observatory/public_projection.py", "console/src/aevora_observatory/_public_projection.py"],
}
def synchronize(root=ROOT, *, check=False):
    rows=[]
    for source, destinations in PAIRS.items():
        raw=(root/source).read_bytes()
        for destination in destinations:
            p=root/destination
            if p.is_symlink():raise ValueError("Linked generated destination refused")
            if check:
                if not p.is_file() or p.read_bytes()!=raw:raise ValueError("Generated public evidence drift: "+destination)
            else:p.write_bytes(raw)
            rows.append({"source":source,"destination":destination,"sha256":sha256(raw).hexdigest(),"exact_copy":True})
    manifest=root/"console/src/aevora_observatory/EVIDENCE_TOOL_SOURCES.json"
    data=(json.dumps(rows,sort_keys=True,indent=2)+"\n").encode()
    if check:
        if manifest.read_bytes()!=data:raise ValueError("Generated public evidence manifest drift")
    else:manifest.write_bytes(data)
    return {"status":"PASS","generated_copies":len(rows),"business_decision_logic_copied":False,"canonical_owners":list(PAIRS)}
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true");args=parser.parse_args(argv)
    print(json.dumps(synchronize(check=args.check),sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
