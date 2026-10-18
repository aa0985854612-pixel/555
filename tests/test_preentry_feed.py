"""Explicit pre-entry orders remain dated and outside ordinary period totals."""
import tempfile,unittest,uuid
from pathlib import Path
from app.store import Store
from app.weekly import weekly_report
from app.history import cohort_key

class PreentryFeedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'db');self.u=self.s.create_user('owner','83000011');self.barn=self.add('barns',name='15棟');self.batch=self.add('batches',name='JD-NEW',barn_id=self.barn['id'],entry_date='2026-10-09',entry_count=100,status='active');self.bin=self.add('feed_bins',name='15-1',barn_ids=[self.barn['id']],vendor='新農科',active=True)
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**d):return self.s.mutate(self.u,kind,d,str(uuid.uuid4()))
 def order(self,on,kg=8000,**patch):return self.add('feed_orders',**(dict(date=on,kg=kg,display_unit='ton',vendor='新農科',item='哺乳二期料',feed_bin_id=self.bin['id'],target_batch_ids=[self.batch['id']])|patch))
 def report(self,**q):return weekly_report(self.s.snapshot(),{'batch_id':[self.batch['id']],'to':['2026-10-18']}|q,today='2026-10-18')
 def test_preentry_kept_separate_and_not_counted_twice(self):
  before=self.order('2026-10-08');self.order('2026-10-10',2000);d=self.report();self.assertEqual(d['preentry_feed']['total_kg'],8000);self.assertEqual(d['preentry_feed']['details'][0]['date'],'2026-10-08');self.assertEqual(d['totals']['feed_orders'],2000);self.assertFalse(any(x['id']==before['id'] for w in d['weeks'] for x in w['feed_details']));self.assertEqual(d['preentry_feed']['details'][0]['bin_label'],'15-1')
 def test_period_start_after_entry_excludes_older_preentry_context(self):
  self.order('2026-10-08');self.assertEqual(self.report(**{'from':['2026-10-10']})['preentry_feed']['count'],0)
 def test_unassigned_bin_is_not_guessed_to_an_upcoming_batch(self):
  self.order('2026-10-08',target_batch_ids=[]);self.assertEqual(self.report()['preentry_feed']['count'],0)
 def test_linked_barns_keep_their_own_arrival_dates(self):
  b=self.add('barns',name='21棟');second=self.add('batches',name='JD-NEW',barn_id=b['id'],entry_date='2026-10-16',entry_count=30,same_batch_as=self.batch['id'],status='active');bin=self.add('feed_bins',name='21',barn_ids=[b['id']],vendor='養全',active=True);self.order('2026-10-15',2000,feed_bin_id=bin['id'],target_batch_ids=[second['id']]);r=self.report(cohort=[cohort_key(self.s.snapshot()['batches'][0])],batch_id=['']);self.assertEqual(r['preentry_feed']['total_kg'],2000);self.assertEqual(r['totals']['feed_orders'],0)
 def test_cross_cohort_shared_preentry_never_becomes_a_single_batch_total(self):
  b=self.add('barns',name='16棟');other=self.add('batches',name='OTHER',barn_id=b['id'],entry_date='2026-10-09',entry_count=20,status='active');bin=self.add('feed_bins',name='15、16',barn_ids=[self.barn['id'],b['id']],vendor='新農科',active=True);self.order('2026-10-08',feed_bin_id=bin['id'],target_batch_ids=[self.batch['id'],other['id']]);r=self.report()['preentry_feed'];self.assertIsNone(r['total_kg']);self.assertEqual(r['known_kg'],0);self.assertEqual(r['shared_details'][0]['kg'],8000)
 def test_void_is_excluded_and_orders_never_add_consumption_or_heads(self):
  o=self.order('2026-10-08');self.s.mutate(self.u,'feed_orders',{'revision':1},str(uuid.uuid4()),o['id'],delete=True);r=self.report();self.assertEqual(r['preentry_feed']['count'],0);self.assertEqual(r['cumulative']['remaining'],100);self.assertFalse(self.s.snapshot()['usages'])
