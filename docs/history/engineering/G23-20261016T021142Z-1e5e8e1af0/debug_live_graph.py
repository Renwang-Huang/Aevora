from audit import *
from aevora.graph_repository import GraphRepository
r=GraphRepository.from_environment();print('GRAPH',r.graph_name);print('graphs',r._client.connection.execute_command('GRAPH.LIST'));print(r.query('MATCH(c:Candidate) RETURN c.id,c.run_id,c.source,c.origin'))
r.close()
