"""Mixed-entry cohorts use a named grid reference without changing actual ages."""
import copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store
from app.weekly import weekly_report

class WeeklyReferenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=Store(Path(self.temp.name)/'db');self.u=self.s.create_user('owner','83000011')
  self.barns=[self.add('barns',name=f'{n}棟') for n in (15,21)]
  self.first=self.add('batches',name='LINKED',barn_id=self.barns[0]['id'],entry_date='2026-10-09',entry_age_days=71,entry_count=1052,status='active')
  self.second=self.add('batches',name='LINKED',barn_id=self.barns[1]['id'],same_batch_as=self.first['id'],entry_date='2026-10-16',entry_age_days=71,entry_count=318,status='active')
 def tearDown(self):self.temp.cleanup()
 def add(self,kind,**row):return self.s.mutate(self.u,kind,row,str(uuid.uuid4()))
 def report(self,data=None,**q):return weekly_report(data or self.s.snapshot(),{'cohort':['LINKED|2026-10-09'],'to':['2026-10-18']}|q,today='2026-10-18')
 def test_named_reference_does_not_become_a_common_cohort_age(self):
  before=self.s.snapshot();r=self.report();self.assertTrue(r['age_mixed']);self.assertIsNone(r['entry_age_days']);self.assertEqual(r['week_reference']['barn'],'15棟');self.assertEqual(r['week_reference']['start_week'],11);self.assertEqual(r['week_reference']['basis'],'named_earliest_entry_barn_only');self.assertTrue(all(w['age_week'] is None for w in r['weeks']))
  self.assertEqual([(e['date'],e['age_days']) for e in r['entry_details']],[('2026-10-09',71),('2026-10-16',71)]);self.assertEqual([b['age_days'] for b in r['barn_ages']],[80,73]);self.assertEqual(before,self.s.snapshot())
 def test_each_single_barn_keeps_its_own_entry_anchored_weeks(self):
  a=self.report(batch_id=[self.first['id']]);b=self.report(batch_id=[self.second['id']]);self.assertIsNone(a['week_reference']);self.assertIsNone(b['week_reference']);self.assertEqual([w['age_week'] for w in a['weeks']],[11,12]);self.assertEqual([w['age_week'] for w in b['weeks']],[11]);self.assertEqual(b['weeks'][0]['anchor'],'2026-10-16')
 def test_reference_is_stable_when_input_order_is_reversed_or_interval_changes(self):
  data=self.s.snapshot();data['batches'].reverse();r=self.report(data,**{'from':['2026-10-16']});self.assertEqual(r['week_reference']['batch_id'],self.first['id']);self.assertEqual(r['weeks'][0]['index'],2);self.assertEqual(r['weeks'][0]['anchor'],'2026-10-16')
 def test_unknown_earliest_entry_age_is_not_borrowed_from_a_later_barn(self):
  data=self.s.snapshot();data['batches'][0]['entry_age_days']=None;r=self.report(data);self.assertIsNone(r['week_reference']);self.assertTrue(all(w['age_week'] is None for w in r['weeks']))
 def test_reference_does_not_fill_missing_age_for_another_barn(self):
  data=self.s.snapshot();data['batches'][1]['entry_age_days']=None;r=self.report(data);self.assertEqual(r['week_reference']['barn'],'15棟');self.assertIsNone(r['entry_details'][1]['age_days']);self.assertIsNone(r['barn_ages'][1]['age_days']);self.assertIsNone(r['entry_age_days'])
 def test_period_totals_preentry_and_herd_stay_independent_of_grid_reference(self):
  self.add('movements',date='2026-10-17',batch_id=self.second['id'],type='death',quantity=1)
  self.add('feed_orders',date='2026-10-08',kg=8000,display_unit='ton',vendor='',allocations=[{'batch_id':self.first['id'],'kg':8000}]);self.add('feed_orders',date='2026-10-16',kg=2000,display_unit='ton',vendor='',allocations=[{'batch_id':self.second['id'],'kg':2000}]);r=self.report();self.assertEqual(r['preentry_feed']['total_kg'],8000);self.assertEqual(r['totals']['feed_orders'],2000);self.assertEqual(r['totals']['death'],1);self.assertEqual(r['cumulative']['remaining'],1369);self.assertEqual(len(r['weeks']),2)

class CloudWeeklyReferenceTests(WeeklyReferenceTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.temp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.s,cloud);self.s=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
