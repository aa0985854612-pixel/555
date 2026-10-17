"""Accepting historical gaps removes reminders, never records or uncertainty."""
import base64,copy,json,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.review import data_quality,farm_today,daily_review
from app.history import source_history
from app.domain import herd
from app.server import client_snapshot,statistics
from legacy_fixture import workbook_fixture

class QualityCompletionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('worker','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.import_body={'filename':'source.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'};self.store.import_workbook(self.admin,self.import_body,str(uuid.uuid4()));data=self.store.snapshot();self.target=next(b for b in data['batches'] if b.get('legacy_barn')==1)
  eligible={'batch:'+self.target['id']}
  for kind in ('movements','weights'):
   eligible.update('source:'+r['id'] for r in source_history(data,kind) if self.target['id'] in r.get('legacy_members',[]) or r.get('batch_id')==self.target['id'])
  self.items=[{'id':i['id'],'fields':i['fields']} for i in data_quality(data,farm_today())['items'] if i['id'] in eligible];assert self.items
  self.review={'status':'completed_skipped','reason':'舊批次即將結束，使用者決定略過剩餘核對','items':self.items}
 def tearDown(self):self.tmp.cleanup()
 def complete(self,user=None,review=None,key=None):return self.store.mutate(user or self.admin,'batches',self.target|{'quality_review':self.review if review is None else review},key or str(uuid.uuid4()),self.target['id'])
 def test_scope_count_and_farm_data_are_preserved(self):
  before=self.store.snapshot();q0=data_quality(before,farm_today());history={k:source_history(before,k) for k in ('movements','weights')};daily=daily_review(before,farm_today());total=herd(before['batches'],before['movements'],farm_today());self.complete();after=self.store.snapshot();q=data_quality(after,farm_today());ids={r['id'] for r in self.items}
  self.assertFalse(ids & {i['id'] for i in q['items']});self.assertEqual(q['count'],q0['count']-len(ids));self.assertEqual(q['count'],len(q['items']));self.assertEqual(q['completed_skipped_count'],len(ids));self.assertEqual(q['active_batches_with_gaps'],sum(i['kind']=='batches' for i in q['items']))
  self.assertEqual({k:source_history(after,k) for k in history},history);self.assertEqual(total,herd(after['batches'],after['movements'],farm_today()));self.assertEqual(daily,daily_review(after,farm_today()));self.assertEqual(after['workbooks'],before['workbooks']);self.assertEqual(next(b for b in after['batches'] if b['id']==self.target['id'])['status'],'active')
  self.assertEqual(client_snapshot(after,'test')['data_quality'],q)
 def test_other_batch_stays_pending(self):
  self.complete();q=data_quality(self.store.snapshot(),farm_today());self.assertTrue(any(i['kind']=='batches' and i['batch_id']!=self.target['id'] for i in q['items']))
 def test_viewer_staff_and_stale_writes_are_rejected(self):
  for user in (self.viewer,self.staff):
   with self.assertRaises(Problem) as e:self.complete(user)
   self.assertEqual(e.exception.status,403)
  self.complete()
  with self.assertRaises(Problem) as e:self.complete()
  self.assertEqual(e.exception.status,409)
 def test_retry_is_idempotent_and_audited(self):
  key=str(uuid.uuid4());first=self.complete(key=key);self.assertEqual(first,self.complete(key=key));db=self.store.connect()
  try:
   row=db.execute("SELECT * FROM audit WHERE kind='batches' AND record_id=? ORDER BY seq DESC LIMIT 1",(self.target['id'],)).fetchone();self.assertEqual(json.loads(row['after_value'])['quality_review'],self.review)
  finally:db.close()
 def test_old_client_edits_and_same_excel_reimport_preserve_completion(self):
  saved=self.complete();payload={k:v for k,v in saved.items() if k!='quality_review'};saved=self.store.mutate(self.admin,'batches',payload,str(uuid.uuid4()),saved['id']);self.assertEqual(saved['quality_review'],self.review);q=data_quality(self.store.snapshot(),farm_today());self.store.import_workbook(self.admin,self.import_body,str(uuid.uuid4()));self.assertEqual(q,data_quality(self.store.snapshot(),farm_today()))
 def test_backup_restore_keeps_completion(self):
  self.complete();clone=Store(Path(self.tmp.name)/'restore');backup=self.store.export_backup();clone.import_backup(self.admin,backup);clone.import_backup(self.admin,backup);self.assertEqual(data_quality(clone.snapshot(),farm_today()),data_quality(self.store.snapshot(),farm_today()))
 def test_unrelated_issue_and_forged_fields_are_rejected(self):
  data=self.store.snapshot();other=next(b for b in data['batches'] if b['id']!=self.target['id']);forged=copy.deepcopy(self.review);forged['items']=[{'id':'batch:'+other['id'],'fields':['missing_entry_count']}]
  with self.assertRaises(Problem):self.complete(review=forged)
  for patch in ({'fields':['invented_field']},{'fields':[]},{'fields':[False]}):
   bad=copy.deepcopy(self.review);bad['items'][0].update(patch)
   with self.assertRaises(Problem):self.complete(review=bad)
  for patch in ({'status':'done'},{'reason':''},{'items':[]},{'items':[self.items[0],self.items[0]]}):
   with self.assertRaises(Problem):self.complete(review=self.review|patch)
 def test_new_gap_and_new_batch_are_not_automatically_completed(self):
  barn=self.store.mutate(self.admin,'barns',{'name':'NEW'},str(uuid.uuid4()));body={'barn_id':barn['id'],'name':'OLD','entry_date':'2026-01-01','entry_count':100,'entry_mean_kg':20,'status':'active'};batch=self.store.mutate(self.admin,'batches',body,str(uuid.uuid4()));item=next(i for i in data_quality(self.store.snapshot(),farm_today())['items'] if i.get('batch_id')==batch['id']);review={'status':'completed_skipped','reason':'accepted old age gap','items':[{'id':item['id'],'fields':item['fields']}]};saved=self.store.mutate(self.admin,'batches',batch|{'quality_review':review},str(uuid.uuid4()),batch['id']);self.assertNotIn(item['id'],[i['id'] for i in data_quality(self.store.snapshot(),farm_today())['items']]);saved=self.store.mutate(self.admin,'batches',saved|{'entry_mean_kg':None},str(uuid.uuid4()),saved['id']);self.assertIn(item['id'],[i['id'] for i in data_quality(self.store.snapshot(),farm_today())['items']]);new=self.store.mutate(self.admin,'batches',body|{'name':'NEXT'},str(uuid.uuid4()));self.assertIn('batch:'+new['id'],[i['id'] for i in data_quality(self.store.snapshot(),farm_today())['items']])
 def test_admin_can_reopen_and_unknown_deaths_stay_unknown(self):
  before=self.store.snapshot();old=herd(before['batches'],before['movements'],farm_today(),[self.target['id']]);saved=self.complete();after=self.store.snapshot();self.assertEqual(old,herd(after['batches'],after['movements'],farm_today(),[self.target['id']]));self.store.mutate(self.admin,'batches',saved|{'quality_review':None},str(uuid.uuid4()),saved['id']);self.assertEqual(data_quality(before,farm_today()),data_quality(self.store.snapshot(),farm_today()))

class CloudQualityCompletionTests(QualityCompletionTests):
 def setUp(self):
  super().setUp()
  from cloud_fixture import HranaFixture
  from app.cloud_store import CloudStore,migrate
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
