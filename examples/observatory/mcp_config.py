"""Generate a scoped ordinary Codex MCP stanza; does not read secrets or grants."""
import argparse
import json
from pathlib import Path


def stanza(python,capability):
    if not Path(python).is_absolute() or not Path(capability).is_absolute():
        raise ValueError('Explicit absolute interpreter and grant file paths required')
    # JSON strings are valid TOML basic string literals for these plain paths.
    return '[mcp_servers.aevora]\ncommand = '+json.dumps(str(python))+'\nargs = '+json.dumps(['-I','-m','aevora.mcp_connect','--capability-file',str(capability)])+'\nstartup_timeout_sec = 20\ntool_timeout_sec = 90\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',type=Path,required=True);p.add_argument('--capability-file',type=Path,required=True);a=p.parse_args()
    print(stanza(a.python,a.capability_file),end='')


if __name__=='__main__':main()
