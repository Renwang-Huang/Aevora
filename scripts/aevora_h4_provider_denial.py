"""Actual nominated HTTPS Gateway denial through the existing trusted broker.

An intentionally invalid ephemeral credential tests failure classification;
no real model key or generated model answer is used, and no response is forged.
"""
import json,tempfile,uuid
from pathlib import Path
from integrations.gateway_broker import SecureModelBroker
from integrations.providers import ProviderConfig
from tests.test_gateway_broker import _request
from scripts.aevora_h4_audit import archive,write,now

def main():
    out=archive()/'g5/provider-auth-denial';out.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='aevora-h4-provider-denial-') as directory:
        private=Path(directory);private.chmod(0o700);key=private/'invalid.key';key.write_text('intentionally-invalid-h4-'+uuid.uuid4().hex);key.chmod(0o600)
        token='temporary-h4-channel-'+uuid.uuid4().hex
        with SecureModelBroker(ProviderConfig(base_url='https://api.renwang-huang.top/v1'),key,run_id='h4-provider-denial',socket_path=private/'gateway.sock',run_token=token,request_budget=1,max_concurrency=1,request_timeout=30,connect_timeout_seconds=10,event_path=out/'actual_transport_events.jsonl') as broker:
            status,headers,body=_request(broker,method='POST',route='/v1/responses',body={'model':'gpt-5.6-terra','reasoning':{'effort':'max'},'input':'Credential denial protocol check; no generation expected.'},token=token)
            data=json.loads(body);write(out/'SANITIZED_RESPONSE.json',{'status':status,'body':data})
        meta=broker.metadata
        ok=status in {401,403} and meta['error_counts'].get('UPSTREAM_AUTHENTICATION_ERROR',0)==1 and meta['upstream_requests']==1 and meta['token_revoked'] is True
        write(out/'RESULT.json',{'status':'PASS' if ok else 'FAIL','http_status':status,'metadata':meta,'credential':'INTENTIONALLY_INVALID_EPHEMERAL; value NOT_INCLUDED','model_completion':'NOT_GENERATED','at':now()})
    print(json.dumps({'status':'PASS' if ok else 'FAIL','actual_http_status':status,'model_completion':'NOT_GENERATED'}));return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
