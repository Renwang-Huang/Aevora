"""Draft only; not installed into a running source epoch."""
from pathlib import Path
import os
from aevora.contracts import PROFILE,schema,canonical_json,require,digest

def write_public_contract(workspace,public_manifest):
    from integrations.aevora import public_runtime_context
    names=['resolve_experience','build_evidence_bundle','record_decision','propose_experience']
    context=public_runtime_context(public_manifest)
    allowed=schema('resolve_experience.arguments')['properties']['task_context']['properties']
    body=dict(protocol_profile=PROFILE,provenance='INITIAL_HOST_DECLARED_PUBLIC_TASK; NOT_KERNEL_OBSERVATION_OR_OUTCOME',public_declared_facts=context,optional_claim_context={k:v for k,v in context.items() if k in allowed},tools={n:schema(n+'.arguments') for n in names},notes=['Use exact argument schema if you choose to use a tool; empty task_context is valid and uses Host-bound facts.','Claims do not establish trusted premises. Contradictory known values are rejected.','Query/Recommendation/Decision source references must come from successful calls on the same MCP connection; never invent IDs.','This file supplies no experience ID, recommendation, engineering solution, Outcome or Host approval.'])
    raw=(canonical_json(body)+'\n').encode();require(len(raw)<=100000,'CAPACITY_EXCEEDED')
    p=Path(workspace)/'AEVORA_MCP_CONTRACT.json';fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
    try:require(os.write(fd,raw)==len(raw));os.fsync(fd)
    finally:os.close(fd)
    return {'file':p.name,'sha256':__import__('hashlib').sha256(raw).hexdigest(),'source':'HOST_GENERATED_PUBLIC_INPUT_NOT_AGENT_CODE_ACTION'}
