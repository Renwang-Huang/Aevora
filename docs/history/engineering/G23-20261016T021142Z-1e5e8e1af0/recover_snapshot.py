from audit import *
from aevora.graph_repository import GraphRepository
import time
r=GraphRepository.from_environment();conn=r._client.connection
end=time.monotonic()+30
while conn.info('persistence').get('loading'):
 assert time.monotonic()<end;time.sleep(.1)
nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id');edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id')
write(E/'05_security/db-crash-139/RECOVERED_LAST_SAVE_GRAPH.json',{'nodes':nodes,'edges':edges,'sha256':__import__('aevora.contracts',fromlist=['digest']).digest([nodes,edges]),'profile':'RECOVERY_LAST_SAVED_RDB_NOT_UNSAVED_TAIL','rdb_sha256':sha(E/'05_security/db-crash-139/dump.rdb'),'source_graph':r.graph_name,'port':17754})
expected=['ad74338f-e940-490e-bcb4-f52806acf6b5']
write(E/'05_security/db-crash-139/LIVE_RUN_RPO_CHECK.json',{'expected_runs':expected,'rows':r.query('MATCH(n) WHERE n.run_id IN $runs RETURN labels(n),n.id,n.run_id',{'runs':expected}),'interpretation':'Missing original Query/Decision/Session nodes are not synthesized; raw successful tool evidence retained separately'})
print('recovered',len(nodes),len(edges));r.close()
