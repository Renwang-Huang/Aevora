from audit import *
import urllib.request
urls={
'official_rules':'https://www.wemakedevs.org/hackathons/falkordb/rules',
'official_faq':'https://www.wemakedevs.org/hackathons/falkordb',
'codex_subagents':'https://developers.openai.com/codex/subagents/',
'codex_noninteractive':'https://developers.openai.com/codex/noninteractive/',
'falkordb_constraint':'https://docs.falkordb.com/commands/graph.constraint-create.html',
'falkordb_indexes':'https://docs.falkordb.com/cypher/indexing.html',
'official_python_sdk':'https://raw.githubusercontent.com/FalkorDB/falkordb-py/main/falkordb/graph.py',
'mcp_sdk_126':'https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v1.26.0/src/mcp/server/fastmcp/tools/base.py',
'codex_pinned_protocol':'https://raw.githubusercontent.com/openai/codex/rust-v0.162.1/codex-rs/protocol/src/protocol.rs'}
rows=[]
for name,url in urls.items():
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Aevora-G20-source-audit/1.0'}),timeout=25) as r:
   raw=r.read(3*1024*1024+1);assert len(raw)<=3*1024*1024
   p=E/'research'/(name+'.raw');p.write_bytes(raw);rows.append({'id':name,'url':url,'resolved_url':r.url,'http_status':r.status,'retrieved_at':now(),'path':str(p.relative_to(E)),'sha256':sha(p),'bytes':len(raw),'use':'Primary source research; branch main is observed, NOT pinned installed version'})
 except Exception as e:rows.append({'id':name,'url':url,'retrieved_at':now(),'status':'UNAVAILABLE','error_type':type(e).__name__})
write(E/'research/PRIMARY_SOURCE_RECEIPTS.json',rows);print(json.dumps(rows))
