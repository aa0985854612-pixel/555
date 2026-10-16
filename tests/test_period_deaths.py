"""Period queries share history scope; missing allocations are never invented."""
import base64,copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store
from app.server import statistics,filter_rows
from legacy_fixture import workbook_fixture

class PeriodDeathTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.user=self.store.create_user('owner','83000011')
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.user,kind,body,str(uuid.uuid4()))
 def batch(self,name='JD-SAME',number=11,group='A',entry_date='2026-01-01',age=70,status='active'):
  barn=self.add('barns',name=f'{number}棟',group=group)
  return self.add('batches',barn_id=barn['id'],name=name,entry_date=entry_date,entry_count=100,entry_age_days=age,status=status)
 def death(self,b,quantity,date='2026-01-03'):
  return self.add('movements',batch_id=b['id'],type='death',quantity=quantity,date=date)
 def query(self,**q):return {'from':['2026-01-03'],'to':['2026-01-03']}|{k:[v] for k,v in q.items()}
 def check_consistent(self,data,q):
  s=statistics(data,q);rows=filter_rows('movements',data,q|{'type':['death'],'from':[s['death_summary']['from']],'to':[s['death_summary']['to']]})
  self.assertEqual(s['death_summary']['known'],sum(r['quantity'] for r in rows))
  self.assertEqual(sum(c['known_period_deaths'] for c in s['death_groups']),s['death_summary']['known'])
  return s
 def source(self):
  self.store.import_workbook(self.user,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
  return self.store.snapshot()
 def test_group_filter_limits_same_cohort_deaths(self):
  a=self.batch();b=self.batch(number=21,group='B');self.death(a,4);self.death(b,7)
  for q,n in [(self.query(),11),(self.query(group='A'),4),(self.query(group='B'),7),(self.query(barn_id=a['barn_id']),4),(self.query(batch_id=b['id']),7),(self.query(cohort='JD-SAME|2026-01-01',group='A'),4)]:
   with self.subTest(q=q):
    s=self.check_consistent(self.store.snapshot(),q);self.assertEqual(s['death_summary']['total'],n);self.assertEqual(s['cohorts'][0]['period_deaths'],n)
 def test_zero_and_ended_barns_stay_visible_without_cumulative_mixing(self):
  a=self.batch();b=self.batch(number=21,status='ended');z=self.batch(name='ZERO',number=9)
  self.death(a,2,date='2026-01-02');self.death(b,3)
  s=self.check_consistent(self.store.snapshot(),self.query());self.assertEqual(s['cumulative']['dead'],5);self.assertEqual(s['death_summary']['total'],3)
  same=next(c for c in s['death_groups'] if c['name']=='JD-SAME');self.assertEqual([x['period_deaths'] for x in same['barns']],[0,3]);self.assertEqual(next(c for c in s['death_groups'] if c['name']=='ZERO')['period_deaths'],0)
 def test_same_name_different_entry_dates_not_merged_and_age_uses_cutoff(self):
  self.batch();self.batch(number=21,entry_date='2025-12-01');s=statistics(self.store.snapshot(),self.query())
  self.assertEqual(len(s['death_groups']),2);self.assertEqual({c['age_days'] for c in s['death_groups']},{72,103});self.assertEqual({c['entry_date'] for c in s['death_groups']},{'2025-12-01','2026-01-01'})
 def test_future_entry_not_shown_as_zero_or_negative_age(self):
  self.batch();self.batch(number=21,name='FUTURE',entry_date='2026-02-01');s=statistics(self.store.snapshot(),self.query());self.assertEqual([c['name'] for c in s['death_groups']],['JD-SAME'])
 def test_date_only_query_is_one_day_including_zero(self):
  b=self.batch();self.death(b,8,date='2026-01-02');s=self.check_consistent(self.store.snapshot(),{'to':['2026-01-03']});self.assertEqual(s['death_summary']['from'],'2026-01-03');self.assertEqual(s['death_groups'][0]['period_deaths'],0)
 def test_source_death_allocations_match_history(self):
  d=self.source();s=self.check_consistent(d,{'from':['2026-10-13'],'to':['2026-10-14']});self.assertEqual(s['death_groups'][0]['period_deaths'],3);self.assertEqual([b['period_deaths'] for b in s['death_groups'][0]['barns']],[0,3])
 def test_unknown_barn_split_keeps_cohort_total_but_never_fake_barn_zero(self):
  d=self.source();r=d['workbooks'][0]['report']['rows'][0];r['events'][0]['allocations']=[]
  s=statistics(d,{'from':['2026-10-11'],'to':['2026-10-14']});c=s['death_groups'][0];self.assertEqual(c['period_deaths'],4);self.assertTrue(all(b['period_deaths'] is None for b in c['barns']))
 def test_undated_death_is_unknown_not_zero(self):
  d=self.source();r=d['workbooks'][0]['report']['rows'][0];r['events'][0]['date']=None
  s=statistics(d,{'from':['2026-10-11'],'to':['2026-10-14']});self.assertIsNone(s['death_summary']['total']);self.assertIsNone(s['death_groups'][0]['period_deaths']);self.assertEqual(s['death_groups'][0]['known_period_deaths'],3)
 def test_known_barn_not_marked_unknown_by_other_barn_undated_death(self):
  d=self.source();d['workbooks'][0]['report']['rows'][0]['events'][0]['date']=None
  b=next(b for b in d['batches'] if b['legacy_barn']==2)
  s=statistics(d,{'from':['2026-10-11'],'to':['2026-10-14'],'cohort':['JD-TEST|2026-09-09'],'barn_id':[b['barn_id']]})
  self.assertEqual(s['death_summary']['total'],3);self.assertEqual(s['death_groups'][0]['period_deaths'],3)
  self.assertEqual(s['death_summary']['scope'],{'cohort':'JD-TEST|2026-09-09','barn_id':b['barn_id']})
 def test_archive_in_history_appears_in_period_list_without_creating_stock(self):
  d=self.source();original=copy.deepcopy(d);r=copy.deepcopy(d['workbooks'][0]['report']['rows'][0]);r['name']='ARCHIVE';r['entry_date']='2025-12-01';d['workbooks'][0]['report']['archive_rows']=[r]
  s=self.check_consistent(d,{'from':['2026-10-13'],'to':['2026-10-14']});self.assertEqual(s['death_summary']['total'],6);arch=next(c for c in s['death_groups'] if c.get('archive'));self.assertEqual(arch['period_deaths'],3);self.assertIsNone(arch['age_days']);self.assertEqual(d['batches'],original['batches'])
