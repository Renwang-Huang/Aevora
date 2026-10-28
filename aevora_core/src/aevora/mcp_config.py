"""Generate a scoped ordinary Codex MCP stanza; does not read secrets or grants."""
import argparse
import json
from pathlib import Path


def stanza(python,capability=None,*,session_root=None):
    target = capability if capability is not None else session_root
    if (capability is None)==(session_root is None) or not Path(python).is_absolute() or not Path(target).is_absolute():
        raise ValueError('Explicit absolute interpreter and grant file paths required')
    # JSON strings are valid TOML basic string literals for these plain paths.
    return '[mcp_servers.aevora]\ncommand = '+json.dumps(str(python))+'\nargs = '+json.dumps(['-I','-m','aevora.mcp_connect','--capability-file' if capability is not None else '--session-root',str(target)])+'\nstartup_timeout_sec = 20\ntool_timeout_sec = 90\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--capability-file',type=Path);group.add_argument('--session-root',type=Path);a=p.parse_args()
    print(stanza(a.python,a.capability_file,session_root=a.session_root),end='')


if __name__=='__main__':main()
