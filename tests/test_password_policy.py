"""4–8 digit passwords for future writes; stored legacy hashes stay usable."""
import http.cookiejar,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from app.store import Store,Problem,password_hash,verify_password,validate_password
from app.accounts import change_password,issue_setup,activate,ensure_role_accounts
from app.server import Server

class PasswordPolicyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'db');self.admin=self.store.create_user('owner','0042');self.viewer=self.store.create_user('reader','00881234','viewer');self.server=Server(('127.0.0.1',0),self.store);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base=f'http://127.0.0.1:{self.server.server_port}'
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def request(self,op,path,body=None,method=None,csrf=None):
  headers={'Content-Type':'application/json'}
  if csrf:headers['X-CSRF-Token']=csrf
  r=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
  try:
   with op.open(r) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def login(self,op,name='owner',password='0042'):
  status,body=self.request(op,'/api/login',{'username':name,'password':password});self.assertEqual(status,200);return body
 def row(self,uid):
  db=self.store.connect()
  try:return dict(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
  finally:db.close()
 def test_boundaries_and_leading_zeroes(self):
  for value in ('0000','00001','000001','0000001','00000001','12345678'):
   with self.subTest(value=value):
    self.assertEqual(validate_password(value),value);u=self.store.create_user('u'+value,value);self.assertTrue(verify_password(value,self.row(u['id'])['hash']))
  self.assertFalse(verify_password('42',self.row(self.admin['id'])['hash']))
 def test_creation_and_bootstrap_reject_non_ascii_non_string_or_wrong_length(self):
  for value in ('','123','123456789','12a4','1234 ',' 1234','1234\n','１２３４','١٢٣٤','12.34','-1234',None,1234,True,[],{}):
   with self.subTest(value=value):
    for create in (lambda:self.store.create_user('invalid',value),lambda:Store(self.path/'initial').create_initial_admin('initial',value)):
     with self.assertRaises(Problem) as e:create()
     self.assertEqual(e.exception.code,'invalid_password_policy')
 def test_initial_admin_accepts_four_and_eight_digits(self):
  for index,value in enumerate(('0008','00000008')):
   store=Store(self.path/f'initial-{index}');u=store.create_initial_admin('initial',value);db=store.connect();row=db.execute('SELECT hash FROM users WHERE id=?',(u['id'],)).fetchone();db.close();self.assertTrue(verify_password(value,row[0]))
 def test_existing_legacy_login_and_current_password_remain_usable(self):
  legacy='pre-policy-alphanumeric-password';db=self.store.connect();db.execute('UPDATE users SET hash=? WHERE id=?',(password_hash(legacy),self.admin['id']));db.commit();db.close()
  op=self.client();user=self.login(op,password=legacy);before=self.row(self.admin['id']);status,body=self.request(op,'/api/password',{'current_password':legacy,'new_password':'123'},csrf=user['csrf']);self.assertEqual(status,400);self.assertEqual(body['error'],'invalid_password_policy');self.assertEqual(before,self.row(self.admin['id']))
  status,_=self.request(op,'/api/password',{'current_password':legacy,'new_password':'0066'},csrf=user['csrf']);self.assertEqual(status,200);self.assertEqual(self.request(op,'/api/me')[0],401);self.login(self.client(),password='0066');self.assertEqual(self.request(self.client(),'/api/login',{'username':'owner','password':legacy})[0],401)
 def test_server_create_requires_digits_and_first_login_change(self):
  op=self.client();user=self.login(op)
  for value in ('abcd','123',1234):
   status,body=self.request(op,'/api/users',{'username':'new-reader','password':value,'role':'viewer'},csrf=user['csrf']);self.assertEqual(status,400);self.assertEqual(body['error'],'invalid_password_policy')
  status,created=self.request(op,'/api/users',{'username':'new-reader','password':'0007','role':'viewer'},csrf=user['csrf']);self.assertEqual(status,201);reader=self.client();first=self.login(reader,'new-reader','0007');self.assertTrue(first['must_change']);self.assertEqual(self.request(reader,'/api/snapshot')[0],403)
  self.assertEqual(self.request(reader,'/api/password',{'current_password':'0007','new_password':'00080009'},csrf=first['csrf'])[0],200);self.assertFalse(self.login(self.client(),'new-reader','00080009')['must_change'])
 def test_all_roles_change_own_password_with_current_password(self):
  staff=self.store.create_user('writer','0022','staff')
  for user,current in ((self.admin,'0042'),(self.viewer,'00881234'),(staff,'0022')):
   with self.assertRaises(Problem) as e:change_password(self.store,user,'incorrect','0033')
   self.assertEqual(e.exception.code,'invalid_current_password');change_password(self.store,user,current,'0033');self.assertTrue(verify_password('0033',self.row(user['id'])['hash']))
 def test_admin_reset_is_validated_and_revokes_target_sessions(self):
  viewer=self.client();self.login(viewer,'reader','00881234');op=self.client();admin=self.login(op);target=self.row(self.viewer['id']);before={k:target[k] for k in ('role','active','revision')};before['active']=bool(before['active']);body={'role':'viewer','active':True,'before':before,'password':'abc4'}
  self.assertEqual(self.request(op,'/api/users/'+target['id'],body,'PUT',admin['csrf'])[0],400);self.assertEqual(target,self.row(target['id']));body['password']='0044';self.assertEqual(self.request(op,'/api/users/'+target['id'],body,'PUT',admin['csrf'])[0],200);self.assertEqual(self.request(viewer,'/api/me')[0],401);self.assertTrue(self.login(self.client(),'reader','0044')['must_change'])
 def test_staff_cannot_reset_and_admin_uses_own_current_password_form(self):
  staff=self.store.create_user('writer','0022','staff');op=self.client();s=self.login(op,'writer','0022');target=self.row(self.viewer['id']);body={'role':'viewer','active':True,'before':{k:target[k] for k in ('role','revision')}|{'active':True},'password':'0044'};self.assertEqual(self.request(op,'/api/users/'+target['id'],body,'PUT',s['csrf'])[0],403)
  owner=self.client();a=self.login(owner);body={'role':'admin','active':True,'before':{'role':'admin','active':True,'revision':1},'password':'0044'};status,result=self.request(owner,'/api/users/'+a['id'],body,'PUT',a['csrf']);self.assertEqual(status,400);self.assertEqual(result['error'],'use_own_password_form');self.assertTrue(verify_password('0042',self.row(a['id'])['hash']))
 def test_setup_rejects_bad_digits_without_consuming_token(self):
  link=issue_setup(self.store,self.admin,self.viewer['id'],1)
  with self.assertRaises(Problem):activate(self.store,'reader',link['token'],'abcd')
  activate(self.store,'reader',link['token'],'0000');self.assertTrue(verify_password('0000',self.row(self.viewer['id'])['hash']))
  with self.assertRaises(Problem):activate(self.store,'reader',link['token'],'0011')
 def test_role_temporary_passwords_are_distinct_numeric_and_not_reset(self):
  with patch('app.accounts.secrets.randbelow',side_effect=[1,1,2,3]):result=ensure_role_accounts(self.store,self.admin)
  for user,value in zip(result,('00000001','00000002','00000003')):self.assertTrue(verify_password(value,self.row(user['id'])['hash']))
  before=[self.row(u['id']) for u in result];self.assertTrue(all(not u['created'] for u in ensure_role_accounts(self.store,self.admin)));self.assertEqual(before,[self.row(u['id']) for u in result])
 def test_backup_keeps_legacy_hash_and_audit_has_no_password_fields(self):
  old='pre-policy-alphanumeric-password';db=self.store.connect();db.execute('UPDATE users SET hash=? WHERE id=?',(password_hash(old),self.admin['id']));db.commit();db.close();clone=Store(self.path/'restore');clone.import_backup(self.admin,self.store.export_backup());db=clone.connect();self.assertTrue(verify_password(old,db.execute('SELECT hash FROM users WHERE id=?',(self.admin['id'],)).fetchone()[0]));db.close()
  change_password(self.store,self.viewer,'00881234','0044');db=self.store.connect();row=db.execute("SELECT after_value FROM audit WHERE action='change-password'").fetchone();db.close();self.assertEqual(set(json.loads(row[0])),{'password_changed','revision'})
