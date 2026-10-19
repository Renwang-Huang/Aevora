#!/usr/bin/env python3
"""Execute real Aevora graph deployment/import/path gates, without mock advice."""
import argparse
import json
from pathlib import Path

from aevora.graph_repository import GraphRepository
from aevora.historical_import import ATOMIC_ID, LOCK_ID, import_verified_history


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=("import", "snapshot"))
    p.add_argument("output",type=Path)
    p.add_argument("--historical-archive",type=Path)
    args=p.parse_args()
    repo=GraphRepository.from_environment()
    try:
        schema=repo.initialize()
        imported=import_verified_history(repo,args.historical_archive) if args.operation=="import" else None
        before=repo.state_fingerprint()
        if args.operation=="import":
            import_verified_history(repo,args.historical_archive)
            assert repo.state_fingerprint()==before, "Repeated import changed immutable state"
        paths={identifier:{"premises":repo.premise_paths(identifier),"evidence":repo.snapshot_public_paths(identifier)} for identifier in (ATOMIC_ID,LOCK_ID)}
        if args.operation=="import":
            assert len(paths[ATOMIC_ID]["evidence"])==2 and len(paths[LOCK_ID]["evidence"])==2
            assert {row['relation'] for row in paths[LOCK_ID]['evidence']}=={'SUPPORTED_BY','COUNTEREXAMPLE'}
        result={"status":"PASS","schema":schema,"state":repo.state_fingerprint(),"import":imported,"actual_parameterized_paths":paths}
        with args.output.open("x") as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps({"status":"PASS","state":result['state'],"output":str(args.output)}))
    finally:repo.close()
    return 0


if __name__=="__main__":raise SystemExit(main())
