import unittest,tempfile,threading,os,json,urllib.request,urllib.error,http.cookiejar,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from app.store import Store,Problem,verify_password,VERSION
from app.desktop import data_directory,profile_id,existing_instance,create_first_account
from app.server import Server

class DesktopTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.store=Store(self.folder/'data'/'pigledger.sqlite3')
    def tearDown(self):self.temp.cleanup()
    def test_windows_directory_is_stable_outside_version_folder(self):
        with patch('app.desktop.sys.platform','win32'),patch.dict(os.environ,{'LOCALAPPDATA':str(self.folder)},clear=False):
            self.assertEqual(data_directory(),self.folder/'PigLedger')
    def test_first_run_creates_real_admin_without_storing_plaintext(self):
        password='desktop-test-password';values=iter([password,password])
        self.assertTrue(create_first_account(self.store,lambda _: '',lambda _:next(values)))
        db=self.store.connect();row=db.execute('SELECT username,role,hash FROM users').fetchone();db.close()
        self.assertEqual(row['username'],'farmadmin');self.assertEqual(row['role'],'admin');self.assertNotEqual(row['hash'],password);self.assertTrue(verify_password(password,row['hash']))
    def test_repeat_launch_preserves_account_and_avoids_prompts(self):
        self.store.create_initial_admin('farmer','desktop-test-password')
        def should_not_prompt(_):raise AssertionError('Unexpected prompt')
        self.assertFalse(create_first_account(self.store,should_not_prompt,should_not_prompt))
    def test_invalid_password_retry(self):
        values=iter(['short','short','desktop-test-password','wrong-password','desktop-test-password','desktop-test-password'])
        self.assertTrue(create_first_account(self.store,lambda _:'farmer',lambda _:next(values)))
    def test_concurrent_initialization_can_create_only_one_admin(self):
        def go(i):
            try:return self.store.create_initial_admin('user'+str(i),'desktop-test-password')
            except Problem as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(go,range(2)))
        self.assertEqual(sum(isinstance(x,dict) for x in r),1);self.assertIn('already_initialized',r)
    def test_existing_any_role_never_creates_another_admin(self):
        self.store.create_user('viewer','desktop-test-password','viewer')
        with self.assertRaises(Problem):self.store.create_initial_admin('farmer','desktop-test-password')
    def test_profile_matching_does_not_open_another_farm(self):
        server=Server(('127.0.0.1',0),self.store);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            port=server.server_port;self.assertEqual(existing_instance(port,profile_id(self.store.path)),f'http://127.0.0.1:{port}/')
            self.assertIsNone(existing_instance(port,'another-profile'))
        finally:server.shutdown();server.server_close()
    def test_real_launcher_login_records_restart_and_preservation(self):
        self.store.create_initial_admin('farmer','desktop-test-password')
        # Choose an available fixed loopback port; the launcher may select the next one if raced.
        import socket
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        root=Path(__file__).resolve().parents[1]
        command=[sys.executable,'-u','-m','app.desktop','--data-dir',str(self.folder),'--port',str(port),'--no-browser']
        def start():
            log=open(self.folder/'launcher.log','a',encoding='utf-8');proc=subprocess.Popen(command,cwd=root,stdout=log,stderr=log)
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.2) as r:
                        if json.load(r)['profile_id']==profile_id(self.store.path):return proc,log
                except (OSError,ValueError):pass
                time.sleep(.1)
            proc.terminate();proc.wait(timeout=5);log.close();self.fail('Launcher did not become healthy')
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        proc,log=start()
        try:
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/login',data=json.dumps({'username':'farmer','password':'desktop-test-password'}).encode(),headers={'Content-Type':'application/json'})
            with op.open(req) as r:me=json.load(r)
            headers={'Content-Type':'application/json','X-CSRF-Token':me['csrf'],'Idempotency-Key':'desktop-test-request-0001'}
            body=json.dumps({'name':'Laptop barn','group':''}).encode()
            with op.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/barns',data=body,headers=headers)) as r:self.assertEqual(r.status,201)
            repeat=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=10)
            self.assertEqual(repeat.returncode,0);self.assertIn('already running',repeat.stdout)
        finally:proc.terminate();proc.wait(timeout=5);log.close()
        proc,log=start()
        try:
            with op.open(f'http://127.0.0.1:{port}/api/snapshot') as r:self.assertEqual(json.load(r)['barns'][0]['name'],'Laptop barn')
            db=self.store.connect();self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1);db.close()
        finally:proc.terminate();proc.wait(timeout=5);log.close()

if __name__=='__main__':unittest.main(verbosity=2)
