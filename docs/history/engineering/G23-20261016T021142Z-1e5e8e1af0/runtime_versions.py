from audit import *
import sys,sqlite3,ssl,platform,importlib.metadata,subprocess
mods=['aevora-core','aevora-console','falkordb','redis','mcp','pydantic','pytest','jsonschema']
write(E/'RUNTIME_VERSIONS.json',{'at':now(),'python':sys.version,'sqlite':sqlite3.sqlite_version,'ssl':ssl.OPENSSL_VERSION,'kernel':platform.release(),'packages':{n:importlib.metadata.version(n) for n in mods},'python_binary_sha256':sha('/usr/bin/python3.12'),'codex_binary_sha256':sha(E/'owned_runtime/native/codex'),'helper_sha256':sha(E/'owned_runtime/native/codex-code-mode-host'),'codex_version':subprocess.check_output([str(E/'owned_runtime/native/codex'),'--version'],text=True).strip(),'upstream_model_weights':'UNVERIFIED'})
