"""Real local TLS/HTTP/SQLite tests with a simulated public proxy/connector.

These tests do NOT claim that Cloudflare provisioning, native Windows, or a
physical phone's cellular connection has been verified.
"""
import contextlib,http.client,http.server,json,os,ssl,subprocess,sys,tempfile,threading,time,unittest,uuid
from pathlib import Path
from app.phone import QuickTunnel,URL_PATTERN,phone_lock,remote_health
from app.desktop import profile_id
from app.server import Server
from app.store import Store
from app.tunnel_binary import verify_binary

class PhoneLifecycleTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.children=[]
    def tearDown(self):
        for child in self.children:child.close()
        self.tmp.cleanup()
    def connector(self,lines,exit_immediately=False):
        code='import time\n'
        for line in lines:code+='print('+repr(line)+',flush=True)\n'
        if not exit_immediately:code+='time.sleep(60)\n'
        def factory(command,**options):
            self.command=command
            return subprocess.Popen([sys.executable,'-u','-c',code],**options)
        child=QuickTunnel('simulated-connector','http://127.0.0.1:9999',self.folder/'empty.yml',factory)
        self.children.append(child);return child
    def test_accepts_only_cloudflare_https_hostnames(self):
        self.assertEqual(URL_PATTERN.search('| https://farm-test.trycloudflare.com |').group(),'https://farm-test.trycloudflare.com')
        for bad in ['http://farm-test.trycloudflare.com','https://farm.trycloudflare.com.evil.test','https://farm.trycloudflare.com:1234','https://evil.test']:
            self.assertIsNone(URL_PATTERN.search(bad))
    def test_address_announcement_without_registration_is_not_ready(self):
        child=self.connector(['https://farm-test.trycloudflare.com'])
        with self.assertRaisesRegex(RuntimeError,'could not be verified'):child.wait_ready('profile',timeout=.4,check=lambda *_:True)
    def test_registered_connection_without_matching_health_is_not_ready(self):
        child=self.connector(['https://farm-test.trycloudflare.com','Registered tunnel connection'])
        with self.assertRaisesRegex(RuntimeError,'could not be verified'):child.wait_ready('profile',timeout=.4,check=lambda *_:False)
    def test_waits_for_matching_health_and_preserves_secure_options(self):
        child=self.connector(['https://farm-test.trycloudflare.com','Registered tunnel connection'])
        calls=[]
        def check(url,profile):calls.append((url,profile));return len(calls)>=2
        self.assertEqual(child.wait_ready('my-profile',timeout=3,check=check),'https://farm-test.trycloudflare.com')
        self.assertEqual(calls[-1][1],'my-profile');self.assertIn('--no-autoupdate',self.command);self.assertIn('http2',self.command)
        self.assertNotIn('--no-tls-verify',self.command)
    def test_failed_child_never_announces_success(self):
        child=self.connector(['connector failure'],exit_immediately=True);child.process.wait(timeout=3)
        with self.assertRaisesRegex(RuntimeError,'stopped before connecting'):child.wait_ready('profile',timeout=1,check=lambda *_:True)
    def test_close_terminates_only_owned_connector(self):
        other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
        child=self.connector(['https://farm-test.trycloudflare.com'])
        try:
            child.close();self.assertIsNotNone(child.process.poll());self.assertIsNone(other.poll())
        finally:other.terminate();other.wait(timeout=3)
    def test_lock_blocks_duplicate_start_and_releases(self):
        with phone_lock(self.folder):
            with self.assertRaisesRegex(RuntimeError,'already running'):
                with phone_lock(self.folder):pass
        with phone_lock(self.folder):pass
    def test_tampered_connector_cannot_be_executed(self):
        bad=self.folder/'connector.exe';bad.write_bytes(b'not official')
        with self.assertRaisesRegex(RuntimeError,'checksum mismatch'):verify_binary(bad,'windows-amd64')
        with self.assertRaisesRegex(RuntimeError,'missing'):verify_binary(self.folder/'missing','windows-amd64')
    def test_older_desktop_blocks_phone_before_database_migration(self):
        from unittest.mock import patch
        from app.phone import run
        store=Store(self.folder/'data'/'pigledger.sqlite3');store.create_initial_admin('farmer','83000007')
        db=store.connect();db.execute('PRAGMA user_version=2');db.commit();db.close()
        with patch('app.phone.verify_binary',return_value=Path(sys.executable)),patch('app.phone.existing_instance',side_effect=RuntimeError('Close older version')):
            with self.assertRaisesRegex(RuntimeError,'older version'):run(self.folder,Path(sys.executable),True)
        db=store.connect();self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2);db.close()
    def test_remote_health_network_error_remains_unverified(self):
        from unittest.mock import patch
        with patch('app.phone.urllib.request.urlopen',side_effect=OSError('offline')):self.assertFalse(remote_health('https://farm-test.trycloudflare.com','profile'))
    def test_real_launcher_duplicate_launch_stop_and_same_database(self):
        store=Store(self.folder/'data'/'pigledger.sqlite3');admin=store.create_initial_admin('farmer','83000007')
        barn=store.mutate(admin,'barns',{'name':'Existing barn','group':''},str(uuid.uuid4()))
        # Only connector provisioning is simulated. The launcher, loopback HTTP,
        # locks, child lifecycle and original SQLite database are real processes.
        script=self.folder/'run_simulated_phone.py'
        script.write_text('''import json,subprocess,sys,urllib.request
from pathlib import Path
import app.phone as m
from app.desktop import profile_id
from app.store import VERSION
folder=Path(sys.argv[1]);origin_file=folder/'origin.json'
real_tunnel=m.QuickTunnel
def factory(command,**options):
    code="import time;print('https://farm-test.trycloudflare.com',flush=True);print('Registered tunnel connection',flush=True);time.sleep(60)"
    child=subprocess.Popen([sys.executable,'-u','-c',code],**options)
    origin_file.write_text(json.dumps({'url':command[-1],'pid':child.pid}))
    return child
def tunnel(binary,url,config):return real_tunnel(binary,url,config,process_factory=factory)
def check(url,expected):
    origin=json.loads(origin_file.read_text())['url']
    req=urllib.request.Request(origin+'/api/health',headers={'Host':'farm-test.trycloudflare.com'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=2) as response:info=json.load(response)
    return info['version']==VERSION and info['profile_id']==expected
m.verify_binary=lambda path,platform:Path(sys.executable)
m.QuickTunnel=tunnel;m.remote_health=check
raise SystemExit(m.main(['--data-dir',str(folder),'--no-browser','--connector',sys.executable,'--startup-timeout','5']))
''')
        root=Path(__file__).resolve().parents[1];env=dict(os.environ,PYTHONPATH=str(root))
        command=[sys.executable,'-u',str(script),str(self.folder)]
        log=open(self.folder/'phone.log','w',encoding='utf-8');process=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=log)
        child_pid=None
        try:
            deadline=time.monotonic()+8
            while not (self.folder/'PHONE_URL.txt').exists() and time.monotonic()<deadline:
                if process.poll() is not None:self.fail('Launcher exited: '+(self.folder/'phone.log').read_text())
                time.sleep(.05)
            self.assertEqual((self.folder/'PHONE_URL.txt').read_text().strip(),'https://farm-test.trycloudflare.com/')
            child_pid=json.loads((self.folder/'origin.json').read_text())['pid']
            second=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(second.returncode,1);self.assertIn('already running',second.stdout)
            self.assertEqual(store.snapshot()['barns'][0]['id'],barn['id'])
        finally:process.terminate();process.wait(timeout=8);log.close()
        self.assertEqual(process.returncode,0);self.assertFalse((self.folder/'PHONE_URL.txt').exists())
        self.assertEqual(store.snapshot()['barns'][0]['id'],barn['id']);self.assertTrue(list((self.folder/'data'/'backups').glob('before-phone-*.sqlite3')))
        if sys.platform!='win32' and child_pid:
            with self.assertRaises(ProcessLookupError):os.kill(child_pid,0)

class PhoneHttpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_tmp=tempfile.TemporaryDirectory();cls.cert_folder=Path(cls.cert_tmp.name)
        cls.cert=cls.cert_folder/'cert.pem';cls.key=cls.cert_folder/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost','-keyout',str(cls.key),'-out',str(cls.cert)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.cert_tmp.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'data'/'pigledger.sqlite3')
        self.admin=self.store.create_initial_admin('farmer','83000007')
        self.store.create_user('reader','83000007','viewer')
        self.backend=Server(('127.0.0.1',0),self.store,secure=True);self.host='farm-test.trycloudflare.com';self.backend.public_host=self.host
        self.worker=threading.Thread(target=self.backend.serve_forever,daemon=True);self.worker.start()
        port=self.backend.server_port
        class Proxy(http.server.BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def forward(self):
                conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
                try:
                    data=self.rfile.read(int(self.headers.get('Content-Length','0')))
                    conn.request(self.command,self.path,body=data,headers=dict(self.headers))
                    response=conn.getresponse();raw=response.read();self.send_response(response.status)
                    for key,value in response.getheaders():
                        if key.lower() not in ('connection','server','date'):self.send_header(key,value)
                    self.end_headers();self.wfile.write(raw)
                finally:conn.close()
            do_GET=do_POST=do_PUT=do_DELETE=forward
        self.proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(self.cert,self.key)
        self.proxy.socket=tls.wrap_socket(self.proxy.socket,server_side=True)
        self.proxy_worker=threading.Thread(target=self.proxy.serve_forever,daemon=True);self.proxy_worker.start()
        self.context=ssl.create_default_context(cafile=str(self.cert));self.cookie=None;self.csrf=None
    def tearDown(self):
        self.proxy.shutdown();self.proxy.server_close();self.backend.shutdown();self.backend.server_close()
        self.proxy_worker.join(timeout=2);self.worker.join(timeout=2);self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        h={'Host':self.host,'Origin':'https://'+self.host,'Content-Type':'application/json'}
        if self.cookie:h['Cookie']=self.cookie
        if self.csrf:h['X-CSRF-Token']=self.csrf
        h.update(headers or {})
        conn=http.client.HTTPSConnection('localhost',self.proxy.server_port,context=self.context,timeout=5)
        try:
            conn.request(method,path,json.dumps(body).encode() if body is not None else None,h)
            r=conn.getresponse();status=r.status;rh=dict(r.getheaders());data=json.loads(r.read());return status,data,rh
        finally:conn.close()
    def login(self,username='farmer'):
        status,me,headers=self.request('POST','/api/login',{'username':username,'password':'83000007'})
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=me['csrf'];return headers
    def test_verified_tls_login_sets_secure_cookie_and_hsts(self):
        headers=self.login()
        self.assertIn('Secure',headers['Set-Cookie']);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertIn('max-age=',headers['Strict-Transport-Security'])
        self.assertEqual(self.context.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(self.context.check_hostname)
        self.assertEqual(self.request('GET','/api/me')[1]['username'],'farmer')
    def test_phone_and_laptop_use_same_records_accounts_and_idempotency(self):
        self.login();key=str(uuid.uuid4());headers={'Idempotency-Key':key}
        first=self.request('POST','/api/barns',{'name':'手機9棟','group':''},headers)
        repeat=self.request('POST','/api/barns',{'name':'手機9棟','group':''},headers)
        self.assertEqual(first[0],201);self.assertEqual(repeat[0],201)
        sync=first[1].pop('sync');self.assertEqual(sync['barns'][0]['id'],first[1]['id'])
        self.assertEqual(first[1],repeat[1])
        laptop=Store(self.store.path);self.assertEqual(len(laptop.snapshot()['barns']),1)
        backup=laptop.backup_sqlite(label='phone-test');self.assertTrue(backup.exists())
        self.assertEqual(self.request('GET','/api/snapshot')[1]['barns'][0]['id'],first[1]['id'])
        db=laptop.connect();self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],2);db.close()
    def test_unauthenticated_and_readonly_writes_rejected_by_server(self):
        self.assertEqual(self.request('GET','/api/snapshot')[0],401)
        self.login('reader');self.assertEqual(self.request('POST','/api/barns',{'name':'not allowed','group':''},{'Idempotency-Key':str(uuid.uuid4())})[0],403)
    def test_wrong_host_origin_http_origin_and_csrf_rejected(self):
        self.assertEqual(self.request('POST','/api/login',{'username':'farmer','password':'83000007'},{'Host':'evil.test'})[0],403)
        self.assertEqual(self.request('POST','/api/login',{'username':'farmer','password':'83000007'},{'Origin':'http://'+self.host})[0],403)
        self.login()
        for extra in [{'Host':'evil.test'},{'Origin':'https://evil.test'},{'Origin':'http://'+self.host},{'X-CSRF-Token':'wrong'}]:
            extra['Idempotency-Key']=str(uuid.uuid4())
            self.assertEqual(self.request('POST','/api/barns',{'name':'not allowed','group':''},extra)[0],403)

if __name__=='__main__':unittest.main(verbosity=2)
