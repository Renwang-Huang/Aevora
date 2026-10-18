"""Portable readonly Hero walkthrough. Pinned public Replay; optional real loopback LIVE."""
import argparse,json,urllib.request
from pathlib import Path
from verify_hero import verify,read,strict_json

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).parent);p.add_argument('--sha256',required=True);p.add_argument('--live-url',choices=['http://127.0.0.1:17804']);args=p.parse_args()
    checked=verify(args.root,args.sha256);c=strict_json(read(args.root,'hero_scenario_contract.json'));art={k:strict_json(read(args.root,v['artifact_path'])) for k,v in c['artifacts'].items()}
    result={'product':'Aevora','mode':'REPLAY','verification':checked,'cases':c['acts'],'experience_lifecycle':{'run_id':art['origin']['run_id'],'native_children':len(art['origin']['children']),'necessary_test_counts':art['origin']['test_counts'],'publication':art['lifecycle']['head']},'evolution':{k:art['evolution'][k] for k in ['before','after','restored','classification','selected_edge','historical_replay']},'ordinary_pilot':art['pilot'],'agent_adoption':'UNKNOWN','causal_benefit':'UNKNOWN'}
    if args.live_url:
        views={}
        for context in ['threads','workers','unknown']:
            try:
                with urllib.request.urlopen(args.live_url+'/api/overview?mode=LIVE&case=case-b&context='+context,timeout=20) as r:v=json.loads(r.read(2*1024*1024))
                views[context]={'mode':v['mode'],'observed_at':v['observed_at'],'decisions':v['decisions'],'context_authority':v['context_authority']}
            except Exception as e:views[context]={'status':'UNAVAILABLE','error_type':type(e).__name__,'fallback':False}
        result['actual_live_public_views']=views
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
