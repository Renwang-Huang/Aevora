from pathlib import Path
import sys,sqlite3,json,importlib.metadata as md,hashlib,platform
E=Path(__file__).resolve().parent
v=dict(python=sys.version,sqlite=sqlite3.sqlite_version,platform=platform.platform(),packages={n:md.version(n) for n in ['mcp','falkordb','redis','pydantic','jsonschema','pytest']},live_model_calls=0,participant_agent_runs=0)
(E/'RUNTIME_VERSIONS.json').write_text(json.dumps(v,indent=2))
print(json.dumps(v))
