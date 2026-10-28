"""Embed only the built public Console and independently pinned public replay.

Node and Python are build tools, never user runtime dependencies. No filesystem
path from the browser selects a file. Historical artifact bytes are preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path
from tools.public_evidence.hero_verify import verify

ROOT = Path(__file__).resolve().parents[1]
PIN = 'c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776'


def synchronize(check=False):
    verify(ROOT / 'demo', PIN)
    contract = json.loads((ROOT / 'demo/hero_scenario_contract.json').read_bytes())
    sources = {f'static/{p}': ROOT / 'console/src/aevora_observatory/static' / p
               for p in ['index.html', 'BUILD_MANIFEST.json', 'assets/app.js', 'assets/app.css']}
    sources['CYTOSCAPE_LICENSE'] = ROOT / 'console/third_party/CYTOSCAPE_LICENSE'
    for name in ['hero_scenario_contract.json', *[r['artifact_path'] for r in contract['artifacts'].values()]]:
        sources['replay/' + name] = ROOT / 'demo' / name
    manifest = {'schema_version': 'aevora.native-assets/1', 'replay_contract_sha256': PIN,
                'sources': {name: {'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                            for name,p in sorted(sources.items())}}
    target = ROOT / 'go-runtime/internal/observatory/assets'
    expected = {name:p.read_bytes() for name,p in sources.items()}
    expected['MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    existing = {str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()}
    if existing - set(expected):
        raise ValueError('Unexpected embedded assets; remove explicitly after review')
    for name,raw in expected.items():
        p = target / name
        if check:
            if not p.is_file() or p.is_symlink() or p.read_bytes() != raw:
                raise ValueError('Native asset differs: ' + name)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
    return {'status':'PASS', 'files':len(expected), 'replay_contract_sha256':PIN}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    print(json.dumps(synchronize(parser.parse_args().check), sort_keys=True))
