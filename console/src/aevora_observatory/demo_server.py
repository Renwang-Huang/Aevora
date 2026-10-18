"""Container entry for a local, synthetic, read-only Gen2 demo.

Compose publishes only127.0.0.1. The existing HTTP Host/origin checks still apply.
This is a local demonstration, not an authenticated multi-user deployment.
"""
from pathlib import Path
from aevora.demo import seed
from .server import create_app


def main():
    directory=Path('/state')
    if not (directory/'baseline.json').exists():seed(directory)
    app=create_app(replay_root='/opt/aevora/h4',
                   replay_sha256='c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776',
                   demo_state=directory)
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8080,access_log=False,log_level='warning',limit_concurrency=16,timeout_keep_alive=5)

if __name__=='__main__':main()
