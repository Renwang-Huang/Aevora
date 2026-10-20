from pathlib import Path
import json
from aevora.graph_repository import GraphRepository
E=Path(__file__).resolve().parent;r=GraphRepository.from_environment();c=r._client.connection
before=c.info('memory');result=c.save();after=c.info('persistence')
(E/'reports/MAIN_DB_FINAL_SAVE.json').write_text(json.dumps(dict(saved=result,memory_before=before,persistence_after=after,graph_count=len(c.execute_command('GRAPH.LIST')),scope='CURRENT_OWNED_DB_ONLY; preserving all failed and accepted synthetic graphs'),indent=2));print('OWNED_MAIN_SAVE',result);r.close()
