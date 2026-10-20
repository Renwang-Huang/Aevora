from pathlib import Path
import json,sys,hashlib
from aevora.graph_repository import GraphRepository
E=Path(__file__).parent;label=sys.argv[1]
r=GraphRepository.from_environment();c=r._client.connection
value=dict(label=label,persistence_before=c.info('persistence'),memory=c.info('memory'),graphs=[x.decode() if isinstance(x,bytes) else x for x in c.execute_command('GRAPH.LIST')],save=c.save(),persistence_after=c.info('persistence'))
(E/'reports'/('RESOURCE_SAVE_'+label+'.json')).write_text(json.dumps(value,indent=2,default=str));assert value['save'] is True;r.close();print(label,'SAVE true',len(value['graphs']))
