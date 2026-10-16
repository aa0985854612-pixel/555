"""Daily patrol records preserve stock, ownership, concurrency and source uncertainty."""
import copy, tempfile, unittest, uuid, base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.store import Store, Problem
from app.domain import herd
from app.review import daily_review, data_quality, check_coverage
from app.server import client_snapshot, statistics
from legacy_fixture import workbook_fixture

class DailyReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('worker','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.barn=self.add('barns',name='15棟');self.batch=self.add('batches',barn_id=self.barn['id'],name='TEST',entry_date='2026-01-01',entry_count=100,entry_mean_kg=20,entry_age_days=70,status='active')
 def tearDown(self):self.tmp.cleanup()
 def reopen(self):return Store(self.store.path)
 def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))
 def check(self,user=None,**extra):return self.store.mutate(user or self.staff,'daily_checks',{'batch_id':self.batch['id'],'date':'2026-01-02','status':'no_deaths'}|extra,str(uuid.uuid4()))
 def report(self):return daily_review(self.store.snapshot(),'2026-01-02')
 def test_no_record_not_zero_and_sales_do_not_confirm_patrol(self):
  self.assertEqual(self.report()['rows'][0]['status'],'not_reported')
  self.add('movements',batch_id=self.batch['id'],date='2026-01-02',type='sale',quantity=5)
  r=self.report();self.assertEqual(r['rows'][0]['status'],'not_reported');self.assertEqual(r['totals']['sale'],5);self.assertEqual(len(r['events']),1)
 def test_confirmation_preserves_stock_and_works_after_restart(self):
  before=self.store.snapshot();self.check();after=self.store.snapshot()
  self.assertEqual(herd(before['batches'],before['movements'],'2026-01-02'),herd(after['batches'],after['movements'],'2026-01-02'))
  fresh=self.reopen();self.assertEqual(daily_review(fresh.snapshot(),'2026-01-02')['rows'][0]['status'],'no_deaths')
  c=check_coverage(after,[self.batch['id']],'2026-01-01','2026-01-03');self.assertEqual(c['expected_batch_days'],3);self.assertEqual(c['confirmed_zero_batch_days'],1);self.assertEqual(c['awaiting_batch_days'],2)
 def test_death_rejects_zero_and_later_death_supersedes_confirmation(self):
  self.check();self.add('movements',batch_id=self.batch['id'],date='2026-01-02',type='death',quantity=1)
  r=self.report()['rows'][0];self.assertEqual(r['status'],'death_recorded');self.assertTrue(r['check_superseded'])
  c=check_coverage(self.store.snapshot(),[self.batch['id']],'2026-01-02','2026-01-02');self.assertEqual(c['confirmed_zero_batch_days'],0);self.assertEqual(c['death_recorded_batch_days'],1)
  with self.assertRaises(Problem) as e:self.check()
  self.assertEqual(e.exception.code,'daily_death_conflict')
 def test_parallel_retries_do_not_duplicate_even_with_different_keys(self):
  payload={'batch_id':self.batch['id'],'date':'2026-01-02','status':'no_deaths'};key=str(uuid.uuid4())
  with ThreadPoolExecutor(max_workers=4) as p:results=list(p.map(lambda _:self.store.mutate(self.staff,'daily_checks',payload,key),range(4)))
  self.assertEqual(len({r['id'] for r in results}),1)
  with self.assertRaises(Problem) as e:self.check()
  self.assertEqual(e.exception.code,'daily_check_exists');self.assertEqual(len(self.store.snapshot()['daily_checks']),1)
 def test_roles_cancellation_revision_and_audit(self):
  with self.assertRaises(Problem) as e:self.check(self.viewer)
  self.assertEqual(e.exception.status,403)
  r=self.check();body=r|{'status':'cancelled','note':'登記錯誤'}
  with self.assertRaises(Problem):self.store.mutate(self.viewer,'daily_checks',body,str(uuid.uuid4()),r['id'])
  cancelled=self.store.mutate(self.staff,'daily_checks',body,str(uuid.uuid4()),r['id']);self.assertEqual(self.report()['rows'][0]['status'],'not_reported')
  with self.assertRaises(Problem) as e:self.store.mutate(self.admin,'daily_checks',r,str(uuid.uuid4()),r['id'])
  self.assertEqual(e.exception.code,'revision_conflict')
  confirmed=self.store.mutate(self.staff,'daily_checks',cancelled|{'status':'no_deaths','note':''},str(uuid.uuid4()),r['id'])
  self.assertEqual(confirmed['revision'],3)
  db=self.store.connect();self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE kind='daily_checks'").fetchone()[0],3);db.close()
 def test_another_editor_cannot_override_check(self):
  r=self.check(self.admin)
  with self.assertRaises(Problem) as e:self.store.mutate(self.staff,'daily_checks',r|{'status':'cancelled','note':'test'},str(uuid.uuid4()),r['id'])
  self.assertEqual(e.exception.status,403)
 def test_no_future_before_entry_or_moving_identity(self):
  for date in ('2025-12-31','2999-01-01'):
   with self.assertRaises(Problem):self.check(date=date)
  r=self.check()
  with self.assertRaises(Problem) as e:self.store.mutate(self.admin,'daily_checks',r|{'date':'2026-01-03'},str(uuid.uuid4()),r['id'])
  self.assertEqual(e.exception.code,'daily_check_identity_locked')
  with self.assertRaises(Problem):self.store.mutate(self.admin,'daily_checks',r,str(uuid.uuid4()),r['id'],delete=True)
  with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',self.batch,str(uuid.uuid4()),self.batch['id'],delete=True)
 def test_new_old_batches_and_linked_barns_keep_separate_checks(self):
  barn=self.add('barns',name='21棟');other=self.add('batches',barn_id=barn['id'],name='TEST',entry_date='2026-01-02',entry_count=30,status='active',same_batch_as=self.batch['id'])
  self.check();r=self.report();self.assertEqual({x['batch_id']:x['status'] for x in r['rows']},{self.batch['id']:'no_deaths',other['id']:'not_reported'})
  old=self.add('batches',barn_id=barn['id'],name='OLD',entry_date='2025-01-01',entry_count=0,status='ended');self.assertNotIn(old['id'],[x['batch_id'] for x in self.report()['rows']])
 def test_quality_missing_fields_and_stock_conflict_never_modify_data(self):
  data=self.store.snapshot();b=data['batches'][0];b.update(entry_mean_kg=None,entry_age_days=None);data['movements']=[{'id':'m','batch_id':b['id'],'date':'2026-01-02','type':'adjustment','quantity':5}]
  before=copy.deepcopy(data);q=data_quality(data,'2026-01-02');self.assertEqual(q['items'][0]['fields'],['missing_entry_mean','missing_age']);self.assertEqual(data,before)
  data['movements']=[];b['legacy_group']={'id':'G','members':[b['id']],'expected_members':1,'as_of':'2026-01-02','snapshots':{'2026-01-02':{'entry':100,'dead':0,'sold':0,'culled':0,'remaining':110}}};b['legacy_heads']={'2026-01-02':110};b['legacy_values']={'2026-01-02':{'entry':100,'dead':0,'sold':0,'culled':0}}
  self.assertIn('stock_exceeds_entry',data_quality(data,'2026-01-02')['items'][0]['fields'])
 def test_source_baseline_is_not_retroactively_confirmed(self):
  self.store.import_workbook(self.admin,{'filename':'source.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
  data=self.store.snapshot();b=next(b for b in data['batches'] if b.get('legacy_barn')==1)
  with self.assertRaises(Problem) as e:self.check(batch_id=b['id'],date='2026-10-13')
  self.assertEqual(e.exception.code,'check_legacy_period')
  q=data_quality(data,'2026-10-15');self.assertTrue(any('missing_entry_count' in i['fields'] for i in q['items']))
  c=check_coverage(data,[b['id']],'2026-10-01','2026-10-14');self.assertEqual(c['expected_batch_days'],0)
 def test_backup_restore_preserves_acknowledgements(self):
  self.check();backup=self.store.export_backup();fresh=Store(Path(self.tmp.name)/'restore');fresh.import_backup(self.admin,backup);fresh.import_backup(self.admin,backup)
  self.assertEqual(len(fresh.snapshot()['daily_checks']),1);self.assertEqual(daily_review(fresh.snapshot(),'2026-01-02')['rows'][0]['status'],'no_deaths')
 def test_snapshot_and_statistics_share_check_status(self):
  self.check();d=self.store.snapshot(include_source=False);client=client_snapshot(d,'test')
  self.assertIn('data_quality',client);self.assertIn('daily_review',client)
  s=statistics(d,{'from':['2026-01-02'],'to':['2026-01-02']});self.assertEqual(s['death_check_coverage']['confirmed_zero_batch_days'],1);self.assertEqual(s['cumulative']['remaining'],100)
 def test_voiding_later_death_does_not_revive_old_zero_statement(self):
  self.check();m=self.add('movements',batch_id=self.batch['id'],date='2026-01-02',type='death',quantity=1)
  self.store.mutate(self.admin,'movements',m,str(uuid.uuid4()),m['id'],delete=True)
  self.assertEqual(self.report()['rows'][0]['status'],'not_reported');self.assertEqual(self.store.snapshot()['daily_checks'][0]['status'],'cancelled')

class CloudDailyReviewTests(DailyReviewTests):
 """The same patrol rules through simulated Turso HTTP transactions."""
 def setUp(self):
  super().setUp()
  from cloud_fixture import HranaFixture
  from app.cloud_store import CloudStore, migrate
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote.db');remote=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,remote);self.store=remote
 def reopen(self):
  from app.cloud_store import CloudStore
  return CloudStore('libsql://test.turso.io','synthetic-token',self.fixture)
 def tearDown(self):self.fixture.close();super().tearDown()
