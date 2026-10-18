"""Official four-tool MCP over a clearly labelled synthetic Graph v2 example.

Launch only on a trusted host. The Agent never gets a publisher, verifier, secret
file or arbitrary Cypher tool. Local synthetic pins confer no production trust.
"""
from datetime import datetime, timedelta, timezone
import argparse
from pathlib import Path
import uuid
from .contracts import PROFILE, record
from .demo import connect, CONTEXTS
from .mcp_v2 import ReadGrant, V2Service, create_server


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--context',choices=list(CONTEXTS),default='threads');a=p.parse_args()
    transport,repo,body=connect(a.state_dir,'before')
    try:
        run='public-synthetic-'+uuid.uuid4().hex
        grant=ReadGrant(repo.tenant,run,'mcp-'+uuid.uuid4().hex,uuid.uuid4().hex,
                        (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),repo.state()['authz_epoch'])
        repo.put_node(record(repo.tenant,'Session',[grant.run_id,grant.session_id,grant.generation],
                             run_id=grant.run_id,session_id=grant.session_id,grant_generation=grant.generation,
                             profile=PROFILE,state='ACTIVE',valid_until=grant.valid_until))
        create_server(V2Service(repo,grant,body['contexts'][a.context],'connection-'+uuid.uuid4().hex)).run(transport='stdio')
    finally:transport.close()

if __name__=='__main__':main()
