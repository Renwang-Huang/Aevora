"""Fail-closed H2 developer-regression identity gate, independent of pytest text."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def check_junit(path: Path, required: list[str]) -> dict:
    root = ET.parse(path).getroot()
    if root.tag not in {'testsuite', 'testsuites'}:
        raise ValueError('Unexpected JUnit root')
    if not required or len(required) != len(set(required)):
        raise ValueError('Nonempty unique inherited identity authority required')
    cases = list(root.iter('testcase'))
    ids = [c.get('classname', '') + '::' + c.get('name', '') for c in cases]
    duplicate = sorted(i for i, n in Counter(ids).items() if n != 1)
    missing = sorted(set(required) - set(ids))
    bad = [ids[n] for n, c in enumerate(cases)
           if any(c.find(t) is not None for t in ('failure', 'error', 'skipped'))]
    declared_bad = []
    for suite in root.iter('testsuite'):
        children = list(suite.iter('testcase'))
        actual = {'tests': len(children),
                  'failures': sum(c.find('failure') is not None for c in children),
                  'errors': sum(c.find('error') is not None for c in children),
                  'skipped': sum(c.find('skipped') is not None for c in children)}
        for key, number in actual.items():
            if key in suite.attrib and int(suite.attrib[key]) != number:
                declared_bad.append({'suite': suite.get('name'), 'field': key})
    return {'status': 'PASS' if cases and not (duplicate or missing or bad or declared_bad) else 'FAIL',
            'required': len(required), 'current': len(cases), 'missing': missing,
            'duplicates': duplicate, 'bad': bad, 'declared_count_errors': declared_bad,
            'junit_sha256': sha256(path.read_bytes()).hexdigest(),
            'identity_sha256': sha256(json.dumps(sorted(ids), separators=(',', ':')).encode()).hexdigest()}
