"""Loopback, read-only PUBLIC Observatory API. No browser write/Cypher/filesystem authority."""
import argparse
import asyncio
from pathlib import Path
import re
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route,Mount
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from .projection import ReplayReader,LiveReader

RESOURCES={'overview','sessions','decisions','experiences','graph','timeline','outcomes','health'}


def create_app(*,replay_root,replay_sha256,activity_root=None,mcp_events=None,demo_state=None):
    replay=ReplayReader(replay_root,replay_sha256);live=LiveReader(activity_root,mcp_events);slots=asyncio.Semaphore(4)
    async def api(request):
        if request.method!='GET':return JSONResponse({'status':'FORBIDDEN','error':'READ_ONLY_VIEWER'},status_code=403)
        allowed={'mode','case','experience','context','stage','limit','offset'}
        if set(request.query_params)-allowed or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
            return JSONResponse({'status':'ERROR','error':'INVALID_QUERY'},status_code=400)
        mode=request.query_params.get('mode','REPLAY');case=request.query_params.get('case','case-a');context=request.query_params.get('context','workers');stage=request.query_params.get('stage','before')
        if mode not in {'LIVE','REPLAY'} or case not in {'case-a','case-b','case-c'} or context not in {'threads','workers','unknown'} or stage not in {'before','after','restored'}:
            return JSONResponse({'status':'ERROR','error':'INVALID_SELECTOR'},status_code=400)
        try:
            limit=int(request.query_params.get('limit','50'));offset=int(request.query_params.get('offset','0'))
            if not 1<=limit<=100 or not 0<=offset<=1000:raise ValueError()
        except ValueError:return JSONResponse({'status':'ERROR','error':'PAGE_BOUND_EXCEEDED'},status_code=400)
        experience=request.query_params.get('experience')
        if experience and (len(experience)>240 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-]*',experience)):
            return JSONResponse({'status':'ERROR','error':'INVALID_ID'},status_code=400)
        resource=request.path_params.get('resource','overview')
        if resource not in RESOURCES:return JSONResponse({'status':'FORBIDDEN','error':'RESOURCE_NOT_PUBLIC'},status_code=403)
        try:
            await asyncio.wait_for(slots.acquire(),timeout=.2)
        except TimeoutError:return JSONResponse({'status':'UNAVAILABLE','error':'READ_CONCURRENCY_BOUND'},status_code=503)
        try:
            data=await run_in_threadpool(replay.overview,case,experience,stage) if mode=='REPLAY' else await run_in_threadpool(live.overview,case,experience,context)
            if resource!='overview':
                key=resource;value=data[key]
                if isinstance(value,list):value=value[offset:offset+limit]
                data={k:data.get(k) for k in ['mode','visibility','status','captured_at','observed_at','archive','contract_sha256']}
                data.update(resource=resource,data=value,offset=offset,limit=limit)
            return JSONResponse(data)
        except OverflowError:return JSONResponse({'mode':mode,'status':'PARTIAL','error':'GRAPH_READ_BUDGET_EXCEEDED','fallback':False},status_code=413)
        except Exception as e:
            from aevora.models import GraphUnavailable
            status=503 if isinstance(e,GraphUnavailable) else 422
            return JSONResponse({'mode':mode,'status':'UNAVAILABLE','error':type(e).__name__,'fallback':False},status_code=status)
        finally:slots.release()
    async def proof(request):
        if request.method!='GET':return JSONResponse({'status':'FORBIDDEN','error':'READ_ONLY_VIEWER'},status_code=403)
        if request.query_params:return JSONResponse({'status':'ERROR','error':'PROOF_SELECTOR_NOT_ALLOWED'},status_code=400)
        try:return JSONResponse(await run_in_threadpool(replay.proof,request.path_params['name']))
        except KeyError:return JSONResponse({'status':'FORBIDDEN','error':'ARTIFACT_NOT_PUBLIC'},status_code=403)
        except Exception:return JSONResponse({'status':'UNAVAILABLE','error':'REPLAY_VERIFICATION_FAILED'},status_code=422)
    async def root(_):return JSONResponse({'product':'Aevora','status':'API_READY','console':'NOT_IMPLEMENTED_G2','read_only':True})
    routes=[Route('/api/proof/{name}',proof,methods=['GET','POST','PUT','DELETE']),Route('/api/{resource}',api,methods=['GET','POST','PUT','DELETE']),Route('/',root)]
    if demo_state is not None:
        async def journey(request):
            if request.method!='GET':return JSONResponse({'status':'FORBIDDEN','error':'READ_ONLY_VIEWER'},status_code=403)
            if set(request.query_params)-{'context','stage'} or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):
                return JSONResponse({'status':'ERROR','error':'INVALID_SELECTOR'},status_code=400)
            context=request.query_params.get('context','threads');stage=request.query_params.get('stage','before')
            if context not in {'threads','workers','unknown'} or stage not in {'before','after'}:
                return JSONResponse({'status':'ERROR','error':'INVALID_SELECTOR'},status_code=400)
            try:
                await asyncio.wait_for(slots.acquire(),timeout=.2)
            except TimeoutError:return JSONResponse({'status':'UNAVAILABLE','error':'READ_CONCURRENCY_BOUND'},status_code=503)
            try:
                from aevora.demo import observe
                return JSONResponse(await run_in_threadpool(observe,demo_state,context,stage))
            except Exception:
                # No private path, credential or exception body crosses HTTP.
                return JSONResponse({'status':'UNAVAILABLE','error':'LIVE_GRAPH_READ_FAILED','fallback':False},status_code=503)
            finally:slots.release()
        async def landing(_):
            from starlette.responses import RedirectResponse
            return RedirectResponse('/journey.html',status_code=303)
        routes.insert(0,Route('/api/journey',journey,methods=['GET','POST','PUT','PATCH','DELETE']))
        routes[-1]=Route('/',landing)
    static=Path(__file__).parent/'static'
    if (static/'index.html').is_file():
        if demo_state is None:routes[-1]=Mount('/',StaticFiles(directory=static,html=True,follow_symlink=False))
        else:routes.append(Mount('/',StaticFiles(directory=static,html=True,follow_symlink=False)))
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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--replay-root',type=Path,required=True);p.add_argument('--replay-sha256',required=True)
    p.add_argument('--demo-state',type=Path);p.add_argument('--activity-root',type=Path);p.add_argument('--mcp-events',type=Path);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=17804);args=p.parse_args()
    if args.host!='127.0.0.1' or not 1024<=args.port<=65535:raise SystemExit('Only explicit loopback nonprivileged listener is supported')
    app=create_app(replay_root=args.replay_root,replay_sha256=args.replay_sha256,activity_root=args.activity_root,mcp_events=args.mcp_events,demo_state=args.demo_state)
    import uvicorn
    uvicorn.run(app,host=args.host,port=args.port,log_level='warning',access_log=False,limit_concurrency=16,timeout_keep_alive=5)


if __name__=='__main__':main()
