"""Fixed-allowlist Host-only final Cypher compiler, one query per activation.

Never accepts Agent parameters; admission/governance prepare trusted canonical
records first. Database write serialization + the complete old-state CAS are
necessary. No claim that staging or network delivery is a global transaction.
"""
from collections import defaultdict
from aevora.contracts import *
from aevora.graph_queries import SEMANTIC_RELATIONS


def activate(repo, *, old_state, new_state, capability, pinned, documents,
             current_ids, prior_edges, create_nodes, create_edges, heads=(), current_verifier_ids=()):
    pinmap={v['id']:v for v in pinned}
    pinmap[capability['id']]=capability
    for old,new in heads:
        require(old['id']==new['id'] and old['kind']==new['kind']=='LifecycleHead')
        pinmap[old['id']]=old
    chunks=[]
    documents=list({r['id']:r for r in documents}.values())
    for root in documents:
        require(repo.node(root['id'])==root)
        repo.load_document(root);pinmap[root['id']]=root
        for ep,cp in repo.execute('Q09',document=root['id']):
            e,c=decode(ep,repo.tenant),decode(cp,repo.tenant)
            pinmap[c['id']]=c;chunks.append(e)
    for value in [*pinmap.values(),*create_nodes,*create_edges]:
        validate_record(value,repo.tenant)
    require(len(pinmap)<=16384 and len(create_edges)<=16384,'CAPACITY_EXCEEDED')
    require(new_state['id']==old_state['id']==repo.state_id
            and new_state['epoch']==old_state['epoch']+1
            and new_state['authz_epoch']>=old_state['authz_epoch'])
    endpoint_map={**pinmap,old_state['id']:old_state,**{v['id']:v for v in create_nodes}}
    require(len({v['id'] for v in create_nodes})==len(create_nodes))
    for e in create_edges:
        require(e['source_id'] in endpoint_map and e['target_id'] in endpoint_map)
        require(endpoint_map[e['source_id']]['kind']==e['source_kind']
                and endpoint_map[e['target_id']]['kind']==e['target_kind'])
    params=dict(state=repo.state_id,old_state=native(old_state),new_state=native(new_state),
                cap=capability['id'],cap_sha=digest(capability),now=datetime.now(timezone.utc).isoformat(),
                authz=old_state['authz_epoch'],pin_ids=sorted(pinmap),
                pins=[[i,native(pinmap[i])] for i in sorted(pinmap)],
                document_ids=sorted({r['id'] for r in documents}),
                chunk_pins=sorted([[e['id'],e['source_id'],e['target_id'],native(e)] for e in chunks],key=lambda x:x[0]),
                current_ids=sorted(current_ids),relations=SEMANTIC_RELATIONS,
                old_edges=[[i,prior_edges[i]['kind'],prior_edges[i]['source_id'],prior_edges[i]['target_id'],native(prior_edges[i])] for i in sorted(prior_edges)],
                verifier_ids=list(current_verifier_ids))
    query='''MATCH(s:TenantState {id:$state}),(cap:Authority {id:$cap})
WHERE properties(s)=$old_state AND cap.payload_sha256=$cap_sha
 AND cap.state='ACTIVE' AND cap.valid_until>$now AND s.authz_epoch=$authz
 AND size(labels(s))=2 AND 'V2Record' IN labels(s)
WITH s,cap MATCH(n:V2Record) WHERE n.id IN $pin_ids
 AND size(labels(n))=2 AND n.kind IN labels(n)
 AND (NOT n.id IN $verifier_ids OR (n.state='ACTIVE' AND n.valid_from<=$now AND n.valid_until>$now))
WITH s,cap,n ORDER BY n.id
WITH s,cap,collect([n.id,properties(n)]) AS pins WHERE pins=$pins
OPTIONAL MATCH (dr:V2Record)-[ce:HAS_CHUNK]->(cc:V2Record) WHERE dr.id IN $document_ids
WITH s,cap,dr,ce,cc ORDER BY ce.id
WITH s,cap,collect(CASE WHEN ce IS NULL THEN NULL ELSE [ce.id,dr.id,cc.id,properties(ce)] END) AS chunkpins
WHERE chunkpins=$chunk_pins
OPTIONAL MATCH (oa:V2Record)-[oe]->(ob:V2Record)
WHERE (oa.id IN $current_ids AND type(oe) IN $relations) OR (ob.id IN $current_ids AND type(oe)='GOVERNS')
WITH s,cap,oa,oe,ob ORDER BY oe.id
WITH s,cap,collect(CASE WHEN oe IS NULL THEN NULL ELSE [oe.id,type(oe),oa.id,ob.id,properties(oe)] END) AS oldpins
WHERE oldpins=$old_edges
'''
    common=','.join(k+':row.'+k for k in sorted(COMMON|{'payload_json','payload_sha256'}))
    groups=defaultdict(list)
    for n in create_nodes:
        require(n['kind'] in {'CandidateEvent','SourceVerification','GovernanceEvent'},'UNAUTHORIZED')
        groups[n['kind']].append(native(n))
    for i,(kind,rows) in enumerate(sorted(groups.items())):
        params['nodes'+str(i)]=rows
        query+=f'WITH s,cap UNWIND $nodes{i} AS row CREATE(x:V2Record:{kind} {{{common}}}) SET x += row WITH s,cap,count(x) AS created_nodes{i}\n'
    groups=defaultdict(list)
    for e in create_edges:
        require(e['kind'] in RELATIONS,'UNAUTHORIZED');groups[e['kind']].append(native(e))
    for i,(kind,rows) in enumerate(sorted(groups.items())):
        params['edges'+str(i)]=rows
        query+=f'''WITH s,cap UNWIND $edges{i} AS row
MATCH(a:V2Record {{id:row.source_id}}),(b:V2Record {{id:row.target_id}})
CREATE(a)-[rel:{kind} {{{common}}}]->(b) SET rel += row
WITH s,cap,count(rel) AS created_edges{i}
'''
    if heads:
        params['heads']=[native(new) for _,new in heads]
        query+='WITH s,cap UNWIND $heads AS row MATCH(hh:LifecycleHead {id:row.id}) SET hh=row WITH s,cap,count(hh) AS updated_heads\n'
    query+='SET s=$new_state RETURN s.payload_sha256'
    return repo.transport.query(query,params,read_only=False)
