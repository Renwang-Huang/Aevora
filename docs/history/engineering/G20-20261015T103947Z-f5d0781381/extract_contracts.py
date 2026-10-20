from pathlib import Path
import asyncio,json,platform,sqlite3,importlib.metadata,sys,ast
E=Path(__file__).resolve().parent
from aevora.mcp_server import create_server,ExperienceService
from aevora.models import schema_catalog
async def main():
 service=ExperienceService(run_id='g20-schema-observation',public_context={},repository=None,enable_proposals=True)
 tools=await create_server(service).list_tools()
 (E/'source_audit/V5C1_ACTUAL_MCP_SCHEMAS.json').write_text(json.dumps({'status':'SCHEMA_EXTRACTION_ONLY_NO_TOOL_EXECUTION','source_commit':'fc539c8524250b53af5353bfce13f1ee857b3695','tools':[t.model_dump(mode='json') for t in tools]},indent=2)+'\n')
 print('OFFICIAL_SCHEMA_EXTRACTION',len(tools))
 for v in ['aevora.graph/1.0','aevora.graph/1.1','aevora.graph/1.2']:
  d=schema_catalog(v);d={k:sorted(x) if isinstance(x,(set,frozenset)) else x for k,x in d.items()};(E/'source_audit'/('AS_IS_'+v.replace('/','_')+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 versions={n:importlib.metadata.version(n) for n in ['mcp','falkordb','redis','pydantic','jsonschema','pytest','aevora-core','aevora-console']}
 (E/'source_audit/ACTUAL_READONLY_RUNTIME.json').write_text(json.dumps({'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'packages':versions,'executable':sys.executable,'new_live_agent_test':'NOT_RUN','graph_connect':'NOT_RUN'},indent=2)+'\n')
asyncio.run(main())
