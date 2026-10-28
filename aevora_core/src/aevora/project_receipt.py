"""Package an independent verifier's outputs; this command grants no trust.

Run only in the separately controlled verifier job after it has stopped its
writers. The Host authorizes the printed receipt pin over that job's trusted
channel. Candidate-generated copies of this bundle remain untrusted.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from .models import parse_timestamp
from .project_source import ARTIFACT_LIMITS, RECEIPT_VERSION, load_policy
from .source_evidence import EvidenceFiles, _json, _require


def ordinary(path, limit):
    path = Path(path).absolute()
    files = EvidenceFiles(path.parent)
    try: return files.read(path.name, limit)
    finally: files.close()


def package_receipt(*, candidate_file, policy_file, artifacts, exit_code, started_at, ended_at, output):
    policy = load_policy(policy_file)
    candidate = _json(ordinary(candidate_file, 256*1024))['candidate']
    _require(type(exit_code) is int and 0 <= exit_code <= 255, 'Actual process exit code required')
    _require(parse_timestamp(ended_at) >= parse_timestamp(started_at), 'Invalid execution interval')
    data = {name:ordinary(artifacts[name], limit) for name,limit in ARTIFACT_LIMITS.items()}
    output = Path(output)
    _require(output.is_absolute(), 'Fresh absolute verifier output directory required')
    _require(not output.exists() and not output.is_symlink(), 'Verifier output already exists')
    files = EvidenceFiles(output.parent)
    try:
        _require(all(not (p/'EVIDENCE_MANIFEST.json').exists() for p in [output.parent,*output.parent.parents]),
                 'Sealed evidence cannot receive new output')
        # A single new directory; never update a prior verifier result.
        output.mkdir(mode=0o700)
    finally: files.close()
    references = {}
    for name,raw in data.items():
        member = name+'.bin' if name!='junit' else 'junit.xml'
        with (output/member).open('xb') as f: f.write(raw)
        references[name] = {'path':member, 'sha256':sha256(raw).hexdigest()}
    receipt = {
        'schema_version':RECEIPT_VERSION, 'candidate_id':candidate['id'],
        'candidate_body_sha256':candidate['body_sha256'], 'run_id':candidate['run_id'],
        'verifier_id':policy['verifier_id'], 'origin':policy['origin'], 'facts':policy['facts'],
        'started_at':started_at, 'ended_at':ended_at, 'exit_code':exit_code, 'artifacts':references,
    }
    raw = (json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with (output/'receipt.json').open('xb') as f: f.write(raw)
    return {'status':'PACKAGED_NOT_AUTHORIZED', 'receipt_sha256':sha256(raw).hexdigest(),
            'authority':'Host must authorize this pin through the independent verifier channel'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate-file', required=True); p.add_argument('--policy', required=True)
    for name in ARTIFACT_LIMITS: p.add_argument('--'+name, required=True)
    p.add_argument('--exit-code', required=True, type=int)
    p.add_argument('--started-at', required=True); p.add_argument('--ended-at', required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(argv)
    return package_receipt(candidate_file=a.candidate_file, policy_file=a.policy,
        artifacts={name:getattr(a,name) for name in ARTIFACT_LIMITS}, exit_code=a.exit_code,
        started_at=a.started_at, ended_at=a.ended_at, output=a.output)


if __name__ == '__main__':
    try: print(json.dumps(main(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'status':'ERROR','error_type':type(error).__name__}))
        raise SystemExit(2)
