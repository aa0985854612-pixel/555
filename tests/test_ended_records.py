"""Status-scoped paper queries preserve original ledgers and older API behavior."""
import copy,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store
from app.domain import Invalid
from app.weekly import weekly_report

class EndedRecordScopeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1','FEED_AUTO_ALLOCATION':'equal'});self.env.start();self.store=Store(Path(self.tmp.name)/'db');self.user=self.store.create_user('owner','83000111')
  self.barns=[self.add('barns',name=f'{n}棟') for n in (1,2)]
  self.a=self.add('batches',name='SAME',barn_id=self.barns[0]['id'],entry_date='2026-07-17',entry_count=100,status='active',entry_age_days=70)
  self.b=self.add('batches',name='SAME',barn_id=self.barns[1]['id'],entry_date='2026-07-17',entry_count=200,status='ended',entry_age_days=70,same_batch_as=self.a['id'])
  self.add('movements',date='2026-10-20',batch_id=self.a['id'],type='death',quantity=2);self.add('movements',date='2026-10-21',batch_id=self.b['id'],type='death',quantity=3)
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.user,kind,body,str(uuid.uuid4()))
 def report(self,**query):return weekly_report(self.store.snapshot(),{'cohort':['SAME|2026-07-17'],'all_records':['1']}|{k:[v] for k,v in query.items()},today='2026-11-02')
 def test_current_and_ended_members_never_mix_in_status_scoped_paper(self):
  active=self.report(batch_status='active');ended=self.report(batch_status='ended')
  self.assertEqual(active['batch_ids'],[self.a['id']]);self.assertEqual(active['totals']['death'],2);self.assertEqual(active['barns'],['1棟'])
  self.assertEqual(ended['batch_ids'],[self.b['id']]);self.assertEqual(ended['totals']['death'],3);self.assertEqual(ended['barns'],['2棟'])
 def test_old_api_without_status_still_prints_whole_original_cohort(self):
  result=self.report();self.assertEqual(set(result['batch_ids']),{self.a['id'],self.b['id']});self.assertEqual(result['totals']['death'],5)
 def test_shared_bin_equal_portions_are_not_duplicated_when_one_barn_ends(self):
  bin=self.add('feed_bins',name='1、2',barn_ids=[b['id'] for b in self.barns],vendor='養全',active=True)
  self.add('feed_orders',date='2026-10-26',kg=2000,display_unit='ton',feed_bin_id=bin['id'],target_batch_ids=[self.a['id'],self.b['id']])
  self.assertEqual(self.report(batch_status='active')['totals']['feed_orders'],1000);self.assertEqual(self.report(batch_status='ended')['totals']['feed_orders'],1000);self.assertEqual(self.report()['totals']['feed_orders'],2000)
  self.assertEqual(len(self.store.snapshot()['feed_orders']),1)
 def test_other_status_future_feed_does_not_extend_current_report_or_leak_details(self):
  self.add('feed_orders',date='2026-12-30',kg=1500,display_unit='ton',vendor='新農科',allocations=[{'batch_id':self.b['id'],'kg':1500}])
  current=self.report(batch_status='active');old=self.report(batch_status='ended')
  self.assertEqual(current['to'],'2026-11-02');self.assertEqual(current['totals']['feed_orders'],0);self.assertEqual(old['to'],'2026-12-30');self.assertEqual(old['totals']['feed_orders'],1500)
 def test_wrong_status_and_incompatible_barn_are_rejected(self):
  with self.assertRaises(Invalid):self.report(batch_status='typo')
  with self.assertRaises(Invalid):self.report(batch_status='active',barn_id=self.barns[1]['id'])
  with self.assertRaises(Invalid):self.report(batch_status='ended',batch_id=self.a['id'])
 def test_reads_do_not_change_status_heads_users_or_original_rows(self):
  before=copy.deepcopy(self.store.snapshot());self.report(batch_status='active');self.report(batch_status='ended');self.report();self.assertEqual(self.store.snapshot(),before)
