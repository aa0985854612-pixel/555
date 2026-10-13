"""Run after `FARM_DOMAIN=localhost docker compose -p pigledger-smoke up -d --build`.
Only uses that disposable project. TLS verified against Caddy's local public root.
"""
import subprocess, os, ssl, urllib.request, http.cookiejar, json, uuid, time
from pathlib import Path
os.environ['DOCKER_CONFIG']='/tmp/pigledger-docker'
os.environ['FARM_DOMAIN']='localhost'
root=Path(__file__).resolve().parents[1]
subprocess.run(['docker','exec','-i','pigledger-smoke-app-1','python','-'],input=b"from app.store import Store\ns=Store('/data/pigledger.sqlite3');s.create_user('docker-test','docker-fixture-password')\n",check=True)
ctx=ssl.create_default_context(cafile='/tmp/pigledger-smoke-root.crt')
op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
me={}
def call(path,body=None):
    headers={'Content-Type':'application/json','Idempotency-Key':str(uuid.uuid4())}
    if me:headers['X-CSRF-Token']=me['csrf']
    req=urllib.request.Request('https://localhost'+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    with op.open(req,timeout=10) as response:
        if path=='/api/login':assert 'Secure' in response.headers['Set-Cookie'] and 'HttpOnly' in response.headers['Set-Cookie']
        assert 'max-age=' in response.headers.get('Strict-Transport-Security','')
        return json.load(response)
assert call('/api/health')['version']=='1.1.0'
me=call('/api/login',{'username':'docker-test','password':'docker-fixture-password'})
barn=call('/api/barns',{'name':'Docker fixture','group':''})
batch=call('/api/batches',{'barn_id':barn['id'],'name':'100-head fixture','entry_date':'2026-01-01','entry_count':100,'entry_age_days':70,'status':'active'})
for date,mean in [('2026-01-01',50),('2026-01-15',60)]:call('/api/weights',{'date':date,'batch_id':batch['id'],'count':2,'total_kg':2*mean,'representative':True})
call('/api/usages',{'start':'2026-01-01','end':'2026-01-15','batch_id':batch['id'],'method':'direct','kg':2500})
assert call('/api/statistics?batch_id='+batch['id'])['aggregate_fcr']==2.5
backup=call('/api/backup');assert backup['schema']==2 and len(backup['records'])==5
subprocess.run(['docker','compose','-p','pigledger-smoke','restart','app'],cwd=root,check=True)
for attempt in range(20):
    try:
        snapshot=call('/api/snapshot');break
    except Exception:
        if attempt==19:raise
        time.sleep(.25)
assert len(snapshot['batches'])==1 and len(snapshot['weights'])==2
assert call('/api/statistics?batch_id='+batch['id'])['aggregate_fcr']==2.5
(root/'artifacts/docker-results.json').write_text(json.dumps({'version':'1.1.0','tests':['Docker build','Compose healthy application','Caddy HTTPS with trusted root; TLS verification enabled','Secure HttpOnly cookie and HSTS','real HTTPS login and writes','HTTPS FCR 2.5','backup with schema 2','restart preserves records and calculations']},indent=2))
print('PASS 8 Docker/HTTPS scenarios')
