"""All-farm acknowledgements: review scope, atomicity, role, race and replay."""
import unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pathlib import Path
import test_daily_review as daily_tests
from app.store import Problem
from app.review import bulk_check_preview,save_bulk_checks,daily_review

class BulkPatrolTests(unittest.TestCase):
 setUp=daily_tests.DailyReviewTests.setUp
 tearDown=daily_tests.DailyReviewTests.tearDown
 add=daily_tests.DailyReviewTests.add
 def setUp(self):
  daily_tests.DailyReviewTests.setUp(self)
  barn=self.add('barns',name='21棟');self.second=self.add('batches',barn_id=barn['id'],name='TEST',entry_date='2026-01-02',entry_count=30,status='active')
 def preview(self,user=None,on='2026-01-03'):return bulk_check_preview(self.store.snapshot(),user or self.admin,on)
 def save(self,p=None,user=None,key=None):
  p=p or self.preview(user);return save_bulk_checks(self.store,user or self.admin,{'date':p['date'],'preview_token':p['preview_token']},key or str(uuid.uuid4()))
 def test_all_barns_saved_once_with_individual_audit_and_stock_unchanged(self):
  before=self.store.snapshot();p=self.preview();self.assertEqual(len(p['eligible']),2);result=self.save(p);self.assertEqual(result['confirmed_count'],2)
  after=self.store.snapshot();self.assertEqual(before['movements'],after['movements']);self.assertEqual(before['batches'],after['batches']);self.assertEqual(len(after['daily_checks']),2)
  self.assertEqual(daily_review(after,'2026-01-03')['counts']['no_deaths'],2)
  db=self.store.connect();self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE action='bulk-zero-create'").fetchone()[0],2);db.close()
 def test_dead_and_already_confirmed_are_skipped(self):
  self.add('movements',batch_id=self.batch['id'],date='2026-01-03',type='death',quantity=1)
  p=self.preview();self.assertEqual([i['batch_id'] for i in p['eligible']],[self.second['id']]);self.assertEqual(p['skipped'][0]['reason'],'death_recorded');self.save(p)
  p=self.preview();self.assertEqual(len(p['eligible']),0);self.assertEqual(len(p['skipped']),2);self.assertEqual(self.save(p)['confirmed_count'],0)
 def test_new_death_after_preview_prevents_all_writes(self):
  p=self.preview();self.add('movements',batch_id=self.batch['id'],date='2026-01-03',type='death',quantity=1)
  with self.assertRaises(Problem) as e:self.save(p)
  self.assertEqual(e.exception.code,'daily_preview_changed');self.assertEqual(len(self.store.snapshot()['daily_checks']),0)
 def test_new_batch_after_preview_requires_review(self):
  p=self.preview();barn=self.add('barns',name='3棟');self.add('batches',barn_id=barn['id'],name='NEW',entry_date='2026-01-01',entry_count=10,status='active')
  with self.assertRaises(Problem) as e:self.save(p)
  self.assertEqual(e.exception.code,'daily_preview_changed')
 def test_parallel_same_key_replay_is_exactly_once(self):
  p=self.preview();key=str(uuid.uuid4())
  with ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(lambda _:self.save(p,key=key),range(3)))
  self.assertTrue(all(x['ids']==r[0]['ids'] for x in r));self.assertEqual(len(self.store.snapshot()['daily_checks']),2)
  with self.assertRaises(Problem):save_bulk_checks(self.store,self.admin,{'date':p['date'],'preview_token':'different'},key)
 def test_different_requests_cannot_double_create_from_same_preview(self):
  p=self.preview();self.save(p)
  with self.assertRaises(Problem) as e:self.save(p)
  self.assertEqual(e.exception.code,'daily_preview_changed');self.assertEqual(len(self.store.snapshot()['daily_checks']),2)
 def test_failure_in_middle_rolls_back_every_record_and_audit(self):
  p=self.preview();original=self.store.audit;calls=[]
  def fail(*args):
   calls.append(1)
   if len(calls)==2:raise RuntimeError('synthetic atomic failure')
   return original(*args)
  with patch.object(self.store,'audit',side_effect=fail):
   with self.assertRaises(RuntimeError):self.save(p)
  self.assertEqual(len(self.store.snapshot()['daily_checks']),0)
  db=self.store.connect();self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE kind='daily_checks'").fetchone()[0],0);db.close()
 def test_viewer_rejected_and_another_editors_cancelled_check_is_skipped(self):
  with self.assertRaises(Problem) as e:self.save(user=self.viewer)
  self.assertEqual(e.exception.status,403)
  old=self.store.mutate(self.admin,'daily_checks',{'date':'2026-01-03','batch_id':self.batch['id'],'status':'cancelled','note':'需重查'},str(uuid.uuid4()))
  p=self.preview(self.staff);self.assertEqual(p['skipped'][0]['reason'],'other_owner');self.assertEqual(self.save(p,self.staff)['confirmed_count'],1)
  self.assertEqual(next(r for r in self.store.snapshot()['daily_checks'] if r['id']==old['id'])['status'],'cancelled')
 def test_own_cancelled_confirmation_is_reused_with_revision(self):
  r=self.store.mutate(self.staff,'daily_checks',{'date':'2026-01-03','batch_id':self.batch['id'],'status':'cancelled','note':'重新巡場'},str(uuid.uuid4()))
  self.save(user=self.staff);saved=next(x for x in self.store.snapshot()['daily_checks'] if x['id']==r['id']);self.assertEqual(saved['revision'],2);self.assertEqual(saved['created_by'],self.staff['id'])
 def test_future_and_ended_batches_are_not_confirmed(self):
  self.assertEqual(self.preview(on='2999-01-01')['eligible'],[])
  b=self.store.mutate(self.admin,'batches',self.second|{'status':'ended'},str(uuid.uuid4()),self.second['id']);self.assertEqual([r['batch_id'] for r in self.preview()['eligible']],[self.batch['id']])
 def test_source_uncertainty_not_marked_zero(self):
  data=self.store.snapshot();b=data['batches'][0]
  event={'id':'source-death','batch_id':None,'legacy_members':[b['id']],'type':'death','date':'2026-01-03','quantity':1}
  with patch('app.review.source_history',return_value=[event]):
   p=bulk_check_preview(data,self.admin,'2026-01-03');self.assertNotIn(b['id'],[r['batch_id'] for r in p['eligible']]);self.assertEqual(p['skipped'][0]['reason'],'unresolved')


class CloudBulkPatrolTests(BulkPatrolTests):
 def setUp(self):
  super().setUp()
  from cloud_fixture import HranaFixture
  from app.cloud_store import CloudStore,migrate
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote.db');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
