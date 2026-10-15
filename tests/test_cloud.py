import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import test_app
from app.store import Store, Problem, verify_password
from app.cloud_store import CloudStore, Connection, migrate, fingerprint, read_document, endpoint
from cloud_fixture import HranaFixture
from api.index import handler

class CloudRulesTests(test_app.AppTests):
    """Existing farm rule suite executed through simulated remote transactions."""
    def setUp(self):
        super().setUp()
        self.local=self.store;self.fixture=HranaFixture(Path(self.temp.name)/'remote.db')
        self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture)
        migrate(self.local,self.store)
    def tearDown(self):self.fixture.close();super().tearDown()
    def test_schema_upgrade_backs_up_and_preserves_users_records(self):
        # Local migrations are covered in AppTests; here verify exact cloud migration.
        db=self.local.connect()
        try:expected=read_document(db)
        finally:db.close()
        db=self.store.connect()
        try:actual=read_document(db)
        finally:db.close()
        self.assertEqual(fingerprint(expected),fingerprint(actual))
        self.assertTrue(list((Path(self.temp.name)/'backups').glob('before-vercel-migration-*')))
    def test_backup_import_repeat_preserves_tombstone(self):
        movement=self.move('death',1);document=self.store.export_backup()
        self.assertEqual(self.store.import_backup(self.admin,document)['added'],0)
        self.store.mutate(self.admin,'movements',movement,str(uuid.uuid4()),movement['id'],True)
        self.store.import_backup(self.admin,document)
        self.assertEqual(len(self.store.snapshot()['movements']),0)
        db=self.store.connect()
        try:self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM cloud_backups WHERE label='before-import'").fetchone()[0],2)
        finally:db.close()

class CloudDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.local=Store(self.path/'local.db')
        self.admin=self.local.create_initial_admin('farmadmin','synthetic-test-password')
        self.viewer=self.local.create_user('reader','synthetic-test-password','viewer')
        self.fixture=HranaFixture(self.path/'remote.db')
        self.cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture)
        migrate(self.local,self.cloud)
    def tearDown(self):self.fixture.close();self.temp.cleanup()
    def test_migration_works_when_provider_rejects_pragma(self):
        target=HranaFixture(self.path/'no-pragma.db')
        def no_pragma(url,payload):
            for request in payload['requests']:
                statements=[request['stmt']] if request['type']=='execute' else [step['stmt'] for step in request['batch']['steps']] if request['type']=='batch' else []
                if any(stmt['sql'].strip().upper().startswith('PRAGMA') for stmt in statements):
                    return {'baton':payload.get('baton'),'results':[{'type':'error','error':{'code':'SQL_PARSE_ERROR'}}]}
            return target(url,payload)
        cloud=CloudStore('libsql://test.turso.io','synthetic-token',no_pragma)
        try:
            result=migrate(self.local,cloud)
            self.assertFalse(result['already_migrated'])
            cloud.assert_ready()
            self.assertTrue(migrate(self.local,cloud)['already_migrated'])
            self.assertEqual(cloud.snapshot(),self.local.snapshot())
        finally:target.close()
    def test_legacy_cloud_version_stays_readable_without_schema_writes(self):
        db=sqlite3.connect(self.fixture.path)
        db.execute('DROP TABLE cloud_metadata');db.execute('PRAGMA user_version=4');db.commit();db.close()
        self.cloud.assert_ready()
        db=sqlite3.connect(self.fixture.path)
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='cloud_metadata'").fetchone());db.close()
        self.assertTrue(migrate(self.local,self.cloud)['already_migrated'])
        self.cloud.assert_ready()
    def test_newer_or_invalid_cloud_marker_cannot_be_overwritten(self):
        db=self.cloud.connect()
        db.execute("UPDATE cloud_metadata SET value='5' WHERE key='schema_version'");db.commit();db.close()
        with self.assertRaises(Problem):self.cloud.assert_ready()
        with self.assertRaises(Problem) as error:migrate(self.local,self.cloud)
        self.assertEqual(error.exception.code,'cloud_migration_conflict')
        db=self.cloud.connect()
        try:self.assertEqual(db.execute("SELECT value FROM cloud_metadata WHERE key='schema_version'").fetchone()[0],'5')
        finally:db.close()
    def test_migration_repeat_and_conflict_preserve_cloud_changes(self):
        self.assertTrue(migrate(self.local,self.cloud)['already_migrated'])
        self.cloud.mutate(self.admin,'barns',{'name':'9棟','group':''},str(uuid.uuid4()))
        with self.assertRaises(Problem) as e:migrate(self.local,self.cloud)
        self.assertEqual(e.exception.code,'cloud_migration_conflict')
        self.assertEqual(len(self.cloud.snapshot()['barns']),1)
    def test_cold_start_keeps_account_hash_roles_and_idempotency(self):
        key=str(uuid.uuid4());row=self.cloud.mutate(self.admin,'barns',{'name':'9棟','group':''},key)
        restarted=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture)
        self.assertEqual(restarted.identity,self.cloud.identity)
        self.assertEqual(restarted.mutate(self.admin,'barns',{'name':'9棟','group':''},key),row)
        db=restarted.connect()
        try:
            user=db.execute('SELECT * FROM users WHERE id=?',(self.admin['id'],)).fetchone()
            self.assertTrue(verify_password('synthetic-test-password',user['hash']))
            self.assertEqual(user['role'],'admin')
        finally:db.close()
    def test_batch_constraint_failure_never_commits_partial_changes(self):
        db=self.cloud.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT INTO users(id,username,hash,role) VALUES('new','new','test','viewer')")
            db.execute("INSERT INTO users(id,username,hash,role) VALUES('duplicate','farmadmin','test','admin')")
            with self.assertRaises(sqlite3.IntegrityError):db.commit()
        finally:db.close()
        db=self.cloud.connect()
        try:self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],2)
        finally:db.close()
    def test_lost_commit_response_retries_exactly_once(self):
        lost={'enabled':True}
        def transport(url,payload):
            response=self.fixture(url,payload)
            request=payload['requests'][0]
            if request['type']=='batch' and any(s['stmt']['sql']=='COMMIT' for s in request['batch']['steps']) and lost['enabled']:
                lost['enabled']=False;raise Problem('cloud_database_unavailable',503)
            return response
        cloud=CloudStore('libsql://test.turso.io','synthetic-token',transport)
        key=str(uuid.uuid4());payload={'name':'9棟','group':''}
        with self.assertRaises(Problem):cloud.mutate(self.admin,'barns',payload,key)
        row=cloud.mutate(self.admin,'barns',payload,key)
        self.assertEqual(len(cloud.snapshot()['barns']),1)
        self.assertEqual(cloud.snapshot()['barns'][0]['id'],row['id'])
    def test_login_limit_shared_across_function_instances(self):
        for i in range(10):
            CloudStore('libsql://test.turso.io','synthetic-token',self.fixture).reserve_login_attempt(('ip','user'))
        with self.assertRaises(Problem) as e:self.cloud.reserve_login_attempt(('ip','user'))
        self.assertEqual(e.exception.status,429)
        self.cloud.clear_login_attempts(('ip','user'));self.cloud.reserve_login_attempt(('ip','user'))
    def test_cloud_backup_persistent_and_schema_not_changed_by_requests(self):
        self.cloud.assert_ready();document=self.cloud.export_backup()
        self.assertEqual(len(document['users']),2)
        db=self.cloud.connect()
        try:self.assertGreaterEqual(db.execute('SELECT COUNT(*) FROM cloud_backups').fetchone()[0],2)
        finally:db.close()
    def test_unconfigured_cloud_does_not_fall_back_to_local_database(self):
        with patch.dict('os.environ',{'TURSO_DATABASE_URL':'','TURSO_AUTH_TOKEN':''}):
            with self.assertRaises(Problem) as e:CloudStore()
            self.assertEqual(e.exception.status,503)
    def test_unconfigured_vercel_health_returns_json_503(self):
        with patch.dict('os.environ',{'TURSO_DATABASE_URL':'','TURSO_AUTH_TOKEN':''}):
            server=ThreadingHTTPServer(('127.0.0.1',0),handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+'/api/health')
                self.assertEqual(e.exception.code,503)
                self.assertEqual(json.load(e.exception)['error'],'cloud_database_configuration')
                self.assertIn('max-age',e.exception.headers['Strict-Transport-Security'])
            finally:server.shutdown();server.server_close()
    def test_uninitialized_cloud_health_fails(self):
        empty=HranaFixture(self.path/'empty.db')
        try:
            with self.assertRaises(Problem) as e:CloudStore('https://empty.turso.io','synthetic-token',empty).assert_ready()
            self.assertEqual(e.exception.code,'cloud_database_uninitialized')
        finally:empty.close()
    def test_endpoint_rejects_insecure_urls_and_credentials(self):
        for url in ('http://db.turso.io','https://user:secret@db.turso.io','https://db.turso.io?secret=value','file:///tmp/db','https://db.turso.io:8080'):
            with self.assertRaises(Problem):endpoint(url)
    def test_untrusted_affinity_never_receives_token(self):
        def transport(url,payload):return {'baton':'x','base_url':'https://other.example/','results':[]}
        db=Connection('https://db.turso.io','synthetic-token',transport)
        with self.assertRaises(Problem) as e:db.execute('SELECT 1')
        self.assertEqual(e.exception.code,'cloud_database_redirect')
        self.assertEqual(db.url,'https://db.turso.io/v2/pipeline');db.close()
    def test_vercel_entry_routes_auth_cookie_roles_static_and_cold_start(self):
        with patch('api.index.CloudStore',side_effect=lambda:CloudStore('libsql://test.turso.io','synthetic-token',self.fixture)):
            server=ThreadingHTTPServer(('127.0.0.1',0),handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                with urllib.request.urlopen(base+'/') as r:self.assertIn(b'1.5.0',r.read())
                with urllib.request.urlopen(base+'/api/health') as r:self.assertTrue(json.load(r)['ok'])
                body=json.dumps({'username':'reader','password':'synthetic-test-password'}).encode()
                with urllib.request.urlopen(urllib.request.Request(base+'/api/login',data=body,headers={'Content-Type':'application/json'})) as r:
                    me=json.load(r);cookie=r.headers['Set-Cookie']
                    self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie)
                headers={'Cookie':cookie.split(';')[0],'X-CSRF-Token':me['csrf'],'Idempotency-Key':str(uuid.uuid4())}
                with urllib.request.urlopen(urllib.request.Request(base+'/api/me',headers=headers)) as r:self.assertEqual(json.load(r)['role'],'viewer')
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(urllib.request.Request(base+'/api/barns',data=b'{"name":"9"}',headers=headers))
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(base+'/api/backup',headers=headers))
                self.assertEqual(e.exception.code,403)
            finally:server.shutdown();server.server_close()
