"""Official Vercel runtime locally; isolated simulated cloud, no public deployment."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from cloud_fixture import HranaFixture
from app.cloud_store import CloudStore,migrate
from app.store import Store,VERSION
results=[]
with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder);local=Store(folder/'local.db')
    local.create_initial_admin('tester','83000016')
    local.create_user('reader','83000016','viewer')
    fixture=HranaFixture(folder/'remote.db')
    cloud=CloudStore('libsql://test.turso.io','synthetic-token',fixture);migrate(local,cloud)
    os.environ.update({'__VC_HANDLER_ENTRYPOINT':'api/index.py','__VC_HANDLER_ENTRYPOINT_ABS':str(root/'api/index.py'),'__VC_HANDLER_MODULE_NAME':'api.index','__VC_HANDLER_VARIABLE_NAME':'handler','TURSO_DATABASE_URL':'libsql://test.turso.io','TURSO_AUTH_TOKEN':'synthetic-token'})
    with patch('app.cloud_store.Connection._http',new=lambda self,url,payload:fixture(url,payload)):
        import vercel_runtime.vc_init as runtime
        def invoke(path,method='GET',data=None,headers=None):
            return runtime.vc_handler({'body':json.dumps({'method':method,'path':path,'headers':{'Host':'farm.example',**(headers or {})},'body':json.dumps(data) if data is not None else ''})},None)
        def passed(name):results.append(name);print('PASS',name)
        response=invoke('/');assert response['statusCode']==200 and VERSION in response['body'];passed('official runtime discovers handler and renders App')
        response=invoke('/app.js?v='+VERSION);assert response['statusCode']==200 and VERSION in response['body'];passed('original static path and query preserved')
        response=invoke('/api/health');assert response['statusCode']==200 and json.loads(response['body'])['ok'];passed('initialized persistent backend health')
        response=invoke('/api/login','POST',{'username':'reader','password':'83000016'})
        assert response['statusCode']==200;me=json.loads(response['body'])
        headers={k.lower():v for k,v in response['headers'].items()}
        cookie=headers['set-cookie'];cookie=cookie[0] if isinstance(cookie,list) else cookie
        assert 'Secure' in cookie and 'HttpOnly' in cookie;passed('login and secure session cookie')
        auth={'Cookie':cookie.split(';')[0],'X-CSRF-Token':me['csrf']}
        response=invoke('/api/me',headers=auth);assert response['statusCode']==200 and json.loads(response['body'])['role']=='viewer';passed('session persists across invocations')
        assert invoke('/api/backup',headers=auth)['statusCode']==403;passed('administrator-only backup blocked for viewer')
        with patch.dict('os.environ',{'TURSO_AUTH_TOKEN':''}):
            response=invoke('/api/health');assert response['statusCode']==503 and json.loads(response['body'])['error']=='cloud_database_configuration';passed('missing cloud credential returns complete 503, not disconnect')
    runtime._finalize();fixture.close()
(root/'artifacts/vercel-runtime-results.json').write_text(json.dumps({'version':VERSION,'type':'official vercel-runtime locally, synthetic data and simulated Hrana; not production','passed':results},indent=2))
print('Completed',len(results),'official runtime checks')
