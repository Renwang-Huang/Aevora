from audit import *
import subprocess,uuid
from datetime import datetime,timezone,timedelta
j=E/'10_regression_final/host58-new46/JUNIT.xml';import xml.etree.ElementTree as X
rows=X.parse(j).findall('.//testcase');assert len(rows)==104 and all(not list(t) for t in rows)
assert subprocess.check_output(['git','status','--porcelain'],cwd=P)==b''
old=json.loads((E/'G23_LIVE_GATE_V3.json').read_text());source={p:sha(P/p) for p in subprocess.check_output(['git','ls-files'],cwd=P,text=True).splitlines()}
old.update(at=now(),source_files=source,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=P,text=True).strip(),new_g23_tests=46,junit_sha256=sha(j),prior_gate_sha256=sha(E/'G23_LIVE_GATE_V3.json'),public_contract_revision='exact typed Host declaration matching; unknown genuine premises remain PENDING; no strategy/experience hints')
write(E/'G23_LIVE_GATE_V4.json',old);(E/'G23_LIVE_GATE_V4.json').chmod(0o400)
s=(E/'challenge.py').read_text();(E/'source_history_challenge-v3.py').write_text(s);s=s.replace('G23_LIVE_GATE_V3.json','G23_LIVE_GATE_V4.json');(E/'challenge.py').write_text(s)
s=(E/'publish_native.py').read_text().replace('G23_LIVE_GATE_V3.json','G23_LIVE_GATE_V4.json');(E/'publish_native.py').write_text(s)
b=json.loads((E/'03_world_accepted/S1_04_BOOTSTRAP.json').read_text());b['grant'].update(session_id='capability-session-'+uuid.uuid4().hex,generation=uuid.uuid4().hex,valid_until=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat());write(E/'03_world_accepted/S1_05_BOOTSTRAP.json',b);(E/'03_world_accepted/S1_05_BOOTSTRAP.json').chmod(0o600)
print(old['source_commit'])
