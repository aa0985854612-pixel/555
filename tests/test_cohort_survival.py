"""Dashboard totals use reliable whole-cohort stock, including ended barns."""
import base64,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store
from app.server import statistics,client_snapshot
from legacy_fixture import workbook_fixture

class CohortSurvivalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011')
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))
 def batch(self,number,count,**extra):
  barn=self.add('barns',name=f'{number}棟',group='')
  return self.add('batches',**({'barn_id':barn['id'],'name':'JD-SAME','entry_date':'2026-01-01','entry_count':count,'status':'active'}|extra))
 def move(self,batch,kind,quantity,**extra):return self.add('movements',**({'batch_id':batch['id'],'date':'2026-01-02','type':kind,'quantity':quantity}|extra))
 def summary(self,**query):return statistics(self.store.snapshot(),{'to':['2026-10-16'],'summary':['1']}|{k:[v] for k,v in query.items()})
 def source(self):
  self.store.import_workbook(self.admin,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
  return self.store.snapshot()['batches']
 def test_combined_denominator_not_average_of_barn_percentages(self):
  a=self.batch(1,100);b=self.batch(2,900,status='ended');self.move(a,'death',10);self.move(b,'death',9)
  result=self.summary();cohort=result['cohorts'][0];self.assertCountEqual(cohort['ids'],[a['id'],b['id']]);self.assertEqual(cohort['herd']['denominator'],1000);self.assertEqual(cohort['herd']['dead'],19);self.assertAlmostEqual(cohort['herd']['survival'],98.1)
  self.assertNotEqual(cohort['herd']['survival'],sum(x['herd']['survival'] for x in result['batches'])/2)
 def test_same_name_different_entry_dates_remains_separate(self):
  self.batch(1,100);self.batch(2,900,entry_date='2025-01-01');result=self.summary();self.assertEqual(len(result['cohorts']),2);self.assertEqual({c['cohort'] for c in result['cohorts']},{'JD-SAME|2026-01-01','JD-SAME|2025-01-01'})
 def test_whole_source_known_even_when_barn_entry_counts_unknown(self):
  self.source();result=self.summary();self.assertTrue(all(b['herd']['survival'] is None for b in result['batches']));h=result['cohorts'][0]['herd'];self.assertEqual(h['denominator'],100);self.assertEqual(h['dead'],4);self.assertEqual(h['survival'],96)
 def test_finished_source_barn_deaths_remain_in_total(self):
  a,b=self.source();self.move(b,'sale',45,date='2026-10-15');self.store.mutate(self.admin,'batches',b|{'status':'ended'},str(uuid.uuid4()),b['id']);result=self.summary();h=result['cohorts'][0]['herd'];self.assertEqual(h['remaining'],45);self.assertEqual(h['dead'],4);self.assertEqual(h['survival'],96);self.assertEqual(len(result['cohorts'][0]['ids']),2)
 def test_internal_transfer_does_not_duplicate_cohort_entry(self):
  a=self.batch(1,100);b=self.batch(2,0,cohort_id=a['id']);self.move(a,'transfer',25,target_batch_id=b['id']);self.move(b,'death',3,date='2026-01-03');h=self.summary()['cohorts'][0]['herd'];self.assertEqual(h['denominator'],100);self.assertEqual(h['transfer_in'],0);self.assertEqual(h['survival'],97)
 def test_arrival_increases_denominator_but_cull_and_adjustment_do_not(self):
  b=self.batch(1,100);self.move(b,'arrival',10);self.move(b,'death',11);self.move(b,'cull',20);self.move(b,'adjustment',5);h=self.summary()['cohorts'][0]['herd'];self.assertEqual(h['denominator'],110);self.assertEqual(h['survival'],90);self.assertEqual(h['remaining'],84)
 def test_zero_or_incomplete_source_denominator_has_no_percentage(self):
  self.batch(3,0);self.assertIsNone(self.summary()['cohorts'][0]['herd']['survival']);self.source();d=self.store.snapshot();d['batches']=[b for b in d['batches'] if b.get('legacy_barn')!=2];result=statistics(d,{'summary':['1'],'to':['2026-10-16']});cohort=next(c for c in result['cohorts'] if c['name']=='JD-TEST');self.assertIsNone(cohort['herd']['denominator']);self.assertIsNone(cohort['herd']['survival'])
 def test_snapshot_totals_respect_date_and_do_not_run_heavy_performance(self):
  a=self.batch(1,100);self.move(a,'death',2)
  with patch('app.server.performance',side_effect=AssertionError('dashboard must stay lean')):
   self.assertEqual(self.summary(to='2026-01-01')['cohorts'][0]['herd']['survival'],100)
   result=client_snapshot(self.store.snapshot(),'test-cursor');self.assertEqual(result['dashboard']['cohorts'][0]['herd']['survival'],98)
