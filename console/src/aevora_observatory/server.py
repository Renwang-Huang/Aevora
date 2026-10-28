"""Loopback, read-only PUBLIC Observatory API. No browser write/Cypher/filesystem authority."""
import argparse
import asyncio
import errno
import json
import os
from pathlib import Path
import re
import socket
import sys
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route,Mount
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from .projection import ReplayReader,LiveReader

RESOURCES={'overview','sessions','decisions','experiences','graph','timeline','outcomes','health'}


def bounded_live_response(data):
    """Stop repeated snapshot references from amplifying the JSON response."""
    from .live_graph import MAX_PAYLOAD_BYTES
    encoder=json.JSONEncoder(ensure_ascii=False,allow_nan=False,separators=(',',':'))
    size=0
    for chunk in encoder.iterencode(data):
        size+=len(chunk.encode('utf-8'))
        if size>MAX_PAYLOAD_BYTES:raise OverflowError('Public response exceeds read budget')
    return JSONResponse(data)


def create_app(*,replay_root=None,replay_sha256=None,activity_root=None,mcp_events=None,session_root=None):
    if (replay_root is None)!=(replay_sha256 is None):raise ValueError('Replay root and independent pin must be configured together')
    replay=ReplayReader(replay_root,replay_sha256) if replay_root is not None else None
    if mcp_events is not None and session_root is not None:raise ValueError('Choose explicit events or managed session root')
    live=LiveReader(activity_root,mcp_events,session_root);slots=asyncio.Semaphore(4)
    async def api(request):
        if request.method!='GET':return JSONResponse({'status':'FORBIDDEN','error':'READ_ONLY_VIEWER'},status_code=403)
        allowed={'mode','case','experience','run','context','stage','limit','offset','cursor'}
        if set(request.query_params)-allowed or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
            return JSONResponse({'status':'ERROR','error':'INVALID_QUERY'},status_code=400)
        mode=request.query_params.get('mode','LIVE');case=request.query_params.get('case','case-a');context=request.query_params.get('context','workers');stage=request.query_params.get('stage','before')
        if mode not in {'LIVE','REPLAY'} or case not in {'case-a','case-b','case-c'} or context not in {'threads','workers','unknown'} or stage not in {'before','after','restored'}:
            return JSONResponse({'status':'ERROR','error':'INVALID_SELECTOR'},status_code=400)
        if mode=='REPLAY' and replay is None:
            return JSONResponse({'mode':mode,'status':'UNAVAILABLE','error':'REPLAY_NOT_CONFIGURED','fallback':False},status_code=404)
        try:
            limit=int(request.query_params.get('limit','20'));offset=int(request.query_params.get('offset','0'))
            if not 1<=limit<=100 or not 0<=offset<=1000:raise ValueError()
        except ValueError:return JSONResponse({'status':'ERROR','error':'PAGE_BOUND_EXCEEDED'},status_code=400)
        experience=request.query_params.get('experience');run=request.query_params.get('run')
        for identity in [experience,run]:
            if identity is not None and (not identity or len(identity)>240 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-]*',identity)):
                return JSONResponse({'status':'ERROR','error':'INVALID_ID'},status_code=400)
        resource=request.path_params.get('resource','overview')
        if resource not in RESOURCES:return JSONResponse({'status':'FORBIDDEN','error':'RESOURCE_NOT_PUBLIC'},status_code=403)
        cursor=request.query_params.get('cursor')
        try:
            from .live_graph import decode_cursor
            if cursor is not None and (mode!='LIVE' or offset):raise ValueError()
            after=decode_cursor(cursor,run,experience)
        except ValueError:return JSONResponse({'status':'ERROR','error':'INVALID_CURSOR'},status_code=400)
        try:
            await asyncio.wait_for(slots.acquire(),timeout=.2)
        except TimeoutError:return JSONResponse({'status':'UNAVAILABLE','error':'READ_CONCURRENCY_BOUND'},status_code=503)
        try:
            data=await run_in_threadpool(replay.overview,case,experience,stage) if mode=='REPLAY' else await run_in_threadpool(live.overview,case,experience,context,run,resource=resource,limit=limit,offset=offset,after=after)
            if mode=='REPLAY' and resource!='overview':
                key=resource;value=data[key]
                if isinstance(value,list):value=value[offset:offset+limit]
                data={k:data.get(k) for k in ['mode','visibility','status','captured_at','observed_at','archive','contract_sha256']}
                data.update(resource=resource,data=value,offset=offset,limit=limit)
            return await run_in_threadpool(bounded_live_response,data) if mode=='LIVE' else JSONResponse(data)
        except OverflowError:return JSONResponse({'mode':mode,'status':'PARTIAL','error':'GRAPH_READ_BUDGET_EXCEEDED','fallback':False},status_code=413)
        except Exception as e:
            from aevora.models import GraphUnavailable
            from aevora.startup import StartupError
            status=503 if isinstance(e,GraphUnavailable) else 422
            if isinstance(e,StartupError):return JSONResponse({**e.public(),'mode':mode,'status':'UNAVAILABLE','fallback':False},status_code=422)
            return JSONResponse({'mode':mode,'status':'UNAVAILABLE','error':type(e).__name__,'fallback':False},status_code=status)
        finally:slots.release()
    async def proof(request):
        if request.method!='GET':return JSONResponse({'status':'FORBIDDEN','error':'READ_ONLY_VIEWER'},status_code=403)
        if set(request.query_params)-{'mode','candidate'} or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
            return JSONResponse({'status':'ERROR','error':'INVALID_QUERY'},status_code=400)
        mode=request.query_params.get('mode','REPLAY');candidate=request.query_params.get('candidate');name=request.path_params['name']
        def failure(error,status):return JSONResponse({'mode':mode,'status':'UNAVAILABLE','error':error,'fallback':False},status_code=status)
        if mode not in {'LIVE','REPLAY'}:return failure('INVALID_SELECTOR',400)
        if mode=='REPLAY' and replay is None:return failure('REPLAY_NOT_CONFIGURED',404)
        if candidate is not None and (not candidate or len(candidate)>240 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-]*',candidate)):
            return failure('INVALID_ID',400)
        if candidate is not None and name!='lifecycle':return failure('INVALID_SELECTOR',400)
        if mode=='LIVE':
            if name!='lifecycle':return failure('LIVE_PROOF_NOT_AVAILABLE',404)
            if not candidate:return failure('CANDIDATE_REQUIRED',400)
        try:await asyncio.wait_for(slots.acquire(),timeout=.2)
        except TimeoutError:return failure('READ_CONCURRENCY_BOUND',503)
        try:
            if mode=='LIVE':
                body=await run_in_threadpool(live.proof,candidate)
                return failure('CANDIDATE_NOT_FOUND',404) if body is None else await run_in_threadpool(bounded_live_response,body)
            body=await run_in_threadpool(replay.proof,name)
            if candidate is not None and body['data']['candidate']['id']!=candidate:return failure('PROOF_OBJECT_MISMATCH',404)
            return JSONResponse(body)
        except OverflowError:return failure('GRAPH_READ_BUDGET_EXCEEDED',413)
        except KeyError:return failure('KeyError',422) if mode=='LIVE' else failure('ARTIFACT_NOT_PUBLIC',403)
        except Exception as e:
            from aevora.models import GraphUnavailable
            return failure(type(e).__name__ if mode=='LIVE' else 'REPLAY_VERIFICATION_FAILED',503 if isinstance(e,GraphUnavailable) else 422)
        finally:slots.release()
    async def root(_):return JSONResponse({'product':'Aevora','status':'API_READY','console':'NOT_IMPLEMENTED_G2','read_only':True})
    routes=[Route('/api/proof/{name}',proof,methods=['GET','POST','PUT','DELETE']),Route('/api/{resource}',api,methods=['GET','POST','PUT','DELETE']),Route('/',root)]
    static=Path(__file__).parent/'static'
    if (static/'index.html').is_file():routes[-1]=Mount('/',StaticFiles(directory=static,html=True,follow_symlink=False))
    app=Starlette(routes=routes)
    async def boundary(request,call_next):
        host=request.headers.get('host','')
        if re.fullmatch(r'(127\.0\.0\.1|localhost)(:[0-9]{1,5})?',host) is None:
            return JSONResponse({'status':'FORBIDDEN','error':'LOOPBACK_HOST_REQUIRED'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin!='http://'+host:return JSONResponse({'status':'FORBIDDEN','error':'CROSS_ORIGIN_VIEWER_DENIED'},status_code=403)
        size=request.headers.get('content-length','0')
        if not size.isdecimal() or len(size)>8 or len(str(request.url))>4096 or len(request.headers)>64 or int(size)>8192:
            return JSONResponse({'status':'ERROR','error':'REQUEST_BOUND_EXCEEDED'},status_code=413)
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response
    app.add_middleware(BaseHTTPMiddleware,dispatch=boundary)
    return app


def bind_console(host,port):
    from aevora.startup import StartupError
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind((host,port));listener.listen(128);return listener
    except OSError as e:
        listener.close()
        if e.errno==errno.EADDRINUSE:
            raise StartupError('CONSOLE_PORT_IN_USE', 'Console port '+str(port)+' is already in use.',
                'Keep the existing service if it is the intended Console, or choose --port FREE_PORT. Demo defaults to 17804; project LIVE defaults to 17805. No existing process was stopped.') from None
        raise StartupError('CONSOLE_BIND_FAILED','Console could not bind the selected loopback port.','Choose an available nonprivileged --port and check local networking permissions.') from None


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--replay-root',type=Path);p.add_argument('--replay-sha256')
    p.add_argument('--config',type=Path);p.add_argument('--activity-root',type=Path)
    channel=p.add_mutually_exclusive_group();channel.add_argument('--mcp-events',type=Path);channel.add_argument('--session-root',type=Path)
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int);args=p.parse_args()
    from aevora.host_config import prepare_environment
    from aevora.startup import StartupError
    try:
        profile=prepare_environment(args.config,use_default=args.replay_root is None)
        port=args.port if args.port is not None else profile['console']['port'] if profile else 17804 if args.replay_root else 17805
        if args.host!='127.0.0.1' or not 1024<=port<=65535:
            raise StartupError('CONSOLE_ADDRESS_INVALID','Console requires a nonprivileged loopback listener.','Use --host 127.0.0.1 and --port 1024..65535.')
        if args.replay_root is None and not os.environ.get('AEVORA_FALKORDB_PASSWORD_FILE'):
            raise StartupError('HOST_CONFIG_REQUIRED','No database settings were loaded for LIVE.','Run aevora configure, or start this Console with --config PATH. For the demo use the documented replay flags.')
        root=args.session_root or (profile['session']['root'] if profile and not args.mcp_events else None)
        app=create_app(replay_root=args.replay_root,replay_sha256=args.replay_sha256,activity_root=args.activity_root,mcp_events=args.mcp_events,session_root=root)
        import uvicorn
        with bind_console(args.host,port) as listener:
            url='http://127.0.0.1:'+str(port)
            if args.replay_root and not profile:url+='/?mode=REPLAY'
            print(json.dumps({'status':'LISTENING','url':url,'session_root':str(root) if root else None}),flush=True)
            server=uvicorn.Server(uvicorn.Config(app,host=args.host,port=port,log_level='warning',access_log=False,limit_concurrency=16,timeout_keep_alive=5))
            server.run(sockets=[listener])
        return 0
    except StartupError as e:
        print(json.dumps(e.public(),sort_keys=True),file=sys.stderr);return 2
    except Exception as e:
        print(json.dumps({'status':'ERROR','error_type':type(e).__name__,'next_step':'Check the selected Host configuration and replay pin; no existing service was changed.'}),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
