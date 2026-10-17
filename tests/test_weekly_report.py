"""Synthetic weekly sheets: shared source history, no changes to stock or accounts."""
import base64,copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store
from app.weekly import weekly_report
from app.domain import Invalid,herd
from legacy_fixture import workbook_fixture
class WeeklyReportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011')
  self.barns=[self.add('barns',name=f'{n}棟',group='') for n in (1,2)]
  self.batches=[self.add('batches',name='SYNTHETIC',barn_id=b['id'],entry_date='2026-10-09',entry_count=100,entry_age_days=71,status='active') for b in self.barns]
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**fields):return self.store.mutate(self.admin,kind,fields,str(uuid.uuid4()))
 def report(self,**query):
  return weekly_report(self.store.snapshot(),{'cohort':['SYNTHETIC|2026-10-09'],'to':['2026-10-22']}|{k:[v] for k,v in query.items()},today='2026-10-22')
 def movement(self,on,typ,n,batch=0):return self.add('movements',date=on,type=typ,quantity=n,batch_id=self.batches[batch]['id'])
 def test_seven_day_boundaries_and_ordinal_week_do_not_use_calendar_week(self):
  self.movement('2026-10-09','death',1);self.movement('2026-10-15','death',2);self.movement('2026-10-16','death',4)
  r=self.report();self.assertEqual([w['anchor'] for w in r['weeks']],['2026-10-09','2026-10-16']);self.assertEqual([w['age_week'] for w in r['weeks']],[11,12]);self.assertEqual([w['values']['death'] for w in r['weeks']],[3,4])
 def test_normal_sale_cull_death_are_separate_and_survival_death_only(self):
  self.movement('2026-10-10','sale',15);self.movement('2026-10-10','death',1);self.movement('2026-10-12','cull',2)
  r=self.report();self.assertEqual(r['totals'],{'death':1,'sale':15,'cull':2,'feed_orders':0});self.assertEqual(r['cumulative']['survival'],99.5);self.assertEqual(r['cumulative']['remaining'],182)
 def test_scope_and_weighted_feed_allocations_exclude_other_barn(self):
  self.movement('2026-10-10','death',1);self.movement('2026-10-11','death',2,1)
  for b,kg in zip(self.batches,(1000,2000)):self.add('feed_orders',date='2026-10-12',kg=kg,display_unit='ton',vendor='',allocations=[{'batch_id':b['id'],'kg':kg}])
  self.assertEqual(self.report()['totals']['feed_orders'],3000)
  one=self.report(barn_id=self.barns[0]['id']);self.assertEqual(one['totals']['feed_orders'],1000);self.assertEqual(one['totals']['death'],1)
 def test_common_order_is_pending_never_divided_or_counted_as_consumption(self):
  self.add('feed_orders',date='2026-10-10',kg=2000,display_unit='ton',vendor='',allocations=[])
  before=self.store.export_backup();r=self.report();self.assertIsNone(r['weeks'][0]['values']['feed_orders']);self.assertEqual(r['weeks'][0]['known']['feed_orders'],0);self.assertEqual(r['weeks'][1]['values']['feed_orders'],0);self.assertEqual(r['pending'][0]['reason'],'unassigned_order');self.assertEqual(before,self.store.export_backup() | {'exported_at':before['exported_at']})
 def test_partial_period_is_clipped_without_changing_anchor_or_cumulative(self):
  self.movement('2026-10-09','death',2);self.movement('2026-10-15','death',1);r=self.report(**{'from':'2026-10-13','to':'2026-10-16'});self.assertEqual(r['totals']['death'],1);self.assertEqual(r['cumulative']['dead'],3);self.assertEqual(r['weeks'][0]['anchor'],'2026-10-09');self.assertTrue(r['weeks'][0]['partial'])
 def test_unknown_age_remains_unknown_and_future_weeks_are_not_zero(self):
  d=self.store.snapshot();d['batches'][0]['entry_age_days']=None;r=weekly_report(d,{'cohort':['SYNTHETIC|2026-10-09'],'to':['2026-11-05']},today='2026-10-16');self.assertTrue(all(w['age_week'] is None for w in r['weeks']));self.assertTrue(r['weeks'][-1]['future']);self.assertTrue(all(v is None for v in r['weeks'][-1]['values'].values()))
 def test_voided_record_is_excluded_and_report_is_read_only(self):
  m=self.movement('2026-10-10','death',1);self.store.mutate(self.admin,'movements',{'revision':m['revision']},str(uuid.uuid4()),m['id'],delete=True);d=self.store.snapshot();old=copy.deepcopy(d);r=weekly_report(d,{'cohort':['SYNTHETIC|2026-10-09']},today='2026-10-16');self.assertEqual(r['totals']['death'],0);self.assertEqual(d,old)
 def test_ambiguous_all_farm_and_overlong_range_rejected(self):
  with self.assertRaises(Invalid):weekly_report(self.store.snapshot(),{},today='2026-10-16')
  with self.assertRaises(Invalid):self.report(to='2030-01-01')
 def legacy(self):
  self.store.import_workbook(self.admin,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()));return self.store.snapshot()
 def test_legacy_source_history_included_once_without_reapplying_baseline(self):
  d=self.legacy();before=herd(d['batches'],d['movements'],'2026-10-15');r=weekly_report(d,{'cohort':['JD-TEST|2026-09-09'],'from':['2026-10-09'],'to':['2026-10-15']},today='2026-10-15');self.assertEqual(r['totals']['death'],4);self.assertEqual(r['totals']['sale'],5);self.assertEqual(r['totals']['cull'],1);self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15'),before)
 def test_unassigned_source_sale_single_barn_unknown_but_known_deaths_retained(self):
  d=self.legacy();r=weekly_report(d,{'cohort':['JD-TEST|2026-09-09'],'barn_id':[self.barns[0]['id']],'from':['2026-10-09'],'to':['2026-10-15']},today='2026-10-15');self.assertIsNone(r['totals']['sale']);self.assertEqual(r['known_totals']['sale'],2);self.assertEqual(r['totals']['death'],1)
 def test_undated_source_does_not_poison_new_weeks_after_source_cutoff(self):
  d=self.legacy();book=d['workbooks'][0];row=book['report']['rows'][0];row['unresolved_cells'].append({'cell':'AG6','quantity':2,'unresolved_quantity':2,'type':'death','comment':'missing date'});r=weekly_report(d,{'cohort':['JD-TEST|2026-09-09'],'from':['2026-10-09'],'to':['2026-10-28']},today='2026-10-28');self.assertIsNone(r['weeks'][0]['values']['death']);self.assertEqual(r['weeks'][-1]['values']['death'],0)
 def test_feed_details_keep_each_order_date_quantity_and_barn_in_the_correct_week(self):
  records=[]
  for on,kg,b in [('2026-10-15',2000,0),('2026-10-15',500,0),('2026-10-16',2500,1)]:records.append(self.add('feed_orders',date=on,kg=kg,display_unit='ton',vendor='',allocations=[{'batch_id':self.batches[b]['id'],'kg':kg}]))
  r=self.report();self.assertEqual([e['kg'] for e in r['weeks'][0]['feed_details']],[2000,500]);self.assertEqual([sum(e['kg'] for e in w['feed_details']) for w in r['weeks']],[2500,2500]);self.assertEqual({e['id'] for w in r['weeks'] for e in w['feed_details']},{o['id'] for o in records});self.assertEqual(r['weeks'][1]['feed_details'][0]['barn'],'2棟');self.assertEqual(len(self.report(barn_id=self.barns[0]['id'])['weeks'][0]['feed_details']),2)
 def test_unassigned_and_voided_orders_never_become_fake_feed_entries(self):
  order=self.add('feed_orders',date='2026-10-10',kg=2000,display_unit='ton',vendor='',allocations=[{'batch_id':self.batches[0]['id'],'kg':2000}]);self.store.mutate(self.admin,'feed_orders',{'revision':order['revision']},str(uuid.uuid4()),order['id'],delete=True);self.add('feed_orders',date='2026-10-10',kg=3000,display_unit='ton',vendor='',allocations=[]);r=self.report();self.assertEqual(r['weeks'][0]['feed_details'],[]);self.assertIsNone(r['weeks'][0]['values']['feed_orders'])

 def test_linked_barns_preserve_separate_entry_dates_counts_and_means(self):
  d=self.store.snapshot();a,b=d['batches'];b.update(_cohort_key='SYNTHETIC|2026-10-09',entry_date='2026-10-16',entry_count=318,entry_mean_kg=21.58,entry_mean_date='2026-10-17',cohort_id=a['id']);a.update(entry_count=1052,entry_mean_kg=21.36,entry_mean_date='2026-10-09',cohort_id=a['id'])
  from app.history import cohort_key
  r=weekly_report(d,{'cohort':[cohort_key(a)],'to':['2026-10-22']},today='2026-10-22')
  self.assertEqual(r['cumulative']['entry'],1370);self.assertEqual([(x['date'],x['count'],x['mean_kg']) for x in r['entry_details']],[('2026-10-09',1052,21.36),('2026-10-16',318,21.58)]);self.assertEqual(r['entry_details'][1]['mean_date'],'2026-10-17');self.assertIsNone(r['entry_mean_kg'])
 def test_combined_legacy_entry_never_becomes_invented_barn_entry(self):
  d=self.legacy();r=weekly_report(d,{'cohort':['JD-TEST|2026-09-09'],'to':['2026-10-15']},today='2026-10-15')
  for item in r['entry_details']:
   self.assertEqual(item['count'],herd(d['batches'],d['movements'],'2026-10-15',[item['batch_id']])['entry'])
  self.assertTrue(any(x['count'] is None for x in r['entry_details']))
