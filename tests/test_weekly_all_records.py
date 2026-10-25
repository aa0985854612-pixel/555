"""Complete saved paper ledger, future dates and the one-entry feed policy."""
import copy,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store
from app.weekly import weekly_report
from app.server import statistics
from app.bin_stock import stock

class WeeklyAllRecordsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'});self.env.start()
  self.s=Store(Path(self.tmp.name)/'db');self.u=self.s.create_user('owner','83000011')
  self.barns=[self.add('barns',name=f'{n}棟') for n in (13,22)]
  self.batches=[self.add('batches',name='SAVED',barn_id=b['id'],entry_date='2026-07-17',entry_age_days=71,entry_count=100,status='active') for b in self.barns]
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def add(self,kind,**fields):return self.s.mutate(self.u,kind,fields,str(uuid.uuid4()))
 def order(self,on='2026-10-26',kg=2000,index=0):return self.add('feed_orders',date=on,kg=kg,display_unit='ton',allocations=[{'batch_id':self.batches[index]['id'],'kg':kg}],vendor='新農科',item='大豬料')
 def report(self,**q):return weekly_report(self.s.snapshot(),{'cohort':['SAVED|2026-07-17'],'all_records':['1']}|{k:[v] for k,v in q.items()},today='2026-10-25')
 def test_latest_saved_october_26_and_27_orders_appear_even_after_today(self):
  rows=[self.order('2026-10-22',2000),self.order('2026-10-24',4000),self.order('2026-10-26',4000),self.order('2026-10-27',8000)]
  r=self.report();self.assertEqual(r['to'],'2026-10-27');self.assertTrue(r['all_records']);self.assertTrue(r['feed_orders_are_arrivals'])
  self.assertEqual({d['id'] for w in r['weeks'] for d in w['feed_details']},{o['id'] for o in rows});self.assertEqual(r['totals']['feed_orders'],18000)
 def test_entire_future_week_with_saved_data_is_not_blank_and_no_fake_zero(self):
  o=self.order('2026-11-03',1500);r=self.report();w=r['weeks'][-1]
  self.assertTrue(w['future']);self.assertTrue(w['has_records']);self.assertEqual(w['feed_details'][0]['id'],o['id']);self.assertEqual(w['values']['feed_orders'],1500);self.assertIsNone(w['values']['death']);self.assertEqual(r['known_totals']['feed_orders'],1500)
 def test_all_mode_ignores_stats_date_filters_and_weekly_start_but_old_api_keeps_them(self):
  self.order('2026-07-18',1000);self.order('2026-10-26',2000);d=self.s.snapshot();d['batches'][0]['weekly_start_date']='2026-10-01'
  r=weekly_report(d,{'batch_id':[self.batches[0]['id']],'all_records':['1'],'from':['2026-10-01'],'to':['2026-10-02']},today='2026-10-25');self.assertEqual(r['from'],'2026-07-17');self.assertEqual(r['totals']['feed_orders'],3000)
  bounded=weekly_report(d,{'batch_id':[self.batches[0]['id']],'from':['2026-10-01'],'to':['2026-10-27']},today='2026-10-25');self.assertEqual(bounded['totals']['feed_orders'],0)
 def test_current_stock_survival_and_asof_stats_do_not_include_future_records(self):
  bin=self.add('feed_bins',name='13',barn_ids=[self.barns[0]['id']],vendor='新農科',active=True,inventory_enabled=True,capacity_kg=10000,safe_fill_percent=85,inventory_date='2026-10-01',inventory_opening_kg=0)
  self.add('feed_orders',date='2026-11-03',kg=2000,display_unit='ton',vendor='新農科',item='大豬料',feed_bin_id=bin['id'],target_batch_ids=[self.batches[0]['id']])
  self.add('movements',date='2026-11-03',type='death',quantity=3,batch_id=self.batches[0]['id'])
  d=self.s.snapshot();before=copy.deepcopy(d);r=weekly_report(d,{'batch_id':[self.batches[0]['id']],'all_records':['1']},today='2026-10-25')
  self.assertEqual(r['totals']['death'],3);self.assertEqual(r['cumulative']['dead'],0);self.assertEqual(r['cumulative']['remaining'],100);self.assertEqual(r['observed_to'],'2026-10-25');self.assertEqual(stock(d,bin,'2026-10-25')['kg'],0);self.assertEqual(statistics(d,{'to':['2026-10-25']})['delivery_kg'],0);self.assertEqual(d,before)
 def test_same_physical_shared_bin_prints_reference_once_without_guessing_allocation(self):
  bin=self.add('feed_bins',name='13、22',barn_ids=[b['id'] for b in self.barns],vendor='新農科',active=True)
  o=self.add('feed_orders',date='2026-11-03',kg=4000,display_unit='ton',vendor='新農科',item='大豬料',feed_bin_id=bin['id'],target_batch_ids=[b['id'] for b in self.batches])
  whole=self.report();self.assertEqual(whole['totals']['feed_orders'],4000);self.assertEqual(len(whole['weeks'][-1]['feed_details']),1)
  one=self.report(barn_id=self.barns[0]['id']);self.assertIsNone(one['totals']['feed_orders']);self.assertEqual(one['known_totals']['feed_orders'],0);self.assertEqual(one['weeks'][-1]['feed_shared_details'][0]['id'],o['id']);self.assertEqual(one['weeks'][-1]['feed_shared_details'][0]['kg'],4000)
 def test_legacy_arrival_and_original_order_both_appear_without_stored_copies(self):
  self.order('2026-10-26',2000);self.add('deliveries',vendor='',date='2026-10-27',kg=1500,display_unit='ton',allocations=[{'batch_id':self.batches[0]['id'],'kg':1500}])
  before=self.s.export_backup()['records'];r=self.report();self.assertEqual(r['totals']['feed_orders'],3500);self.assertEqual(len([d for w in r['weeks'] for d in w['feed_details']]),2);self.assertEqual(self.s.export_backup()['records'],before)
 def test_original_edit_and_void_are_reflected_on_next_report(self):
  o=self.order(kg=2000);self.s.mutate(self.u,'feed_orders',{'date':o['date'],'kg':1500,'display_unit':'ton','vendor':'新農科','item':'大豬料','allocations':[{'batch_id':self.batches[0]['id'],'kg':1500}],'revision':o['revision']},str(uuid.uuid4()),o['id'])
  self.assertEqual(self.report()['totals']['feed_orders'],1500);now=self.s.snapshot()['feed_orders'][0];self.s.mutate(self.u,'feed_orders',{'revision':now['revision']},str(uuid.uuid4()),o['id'],delete=True);self.assertEqual(self.report()['totals']['feed_orders'],0)
 def test_future_other_batch_does_not_extend_selected_barn_report(self):
  self.order('2026-11-03',2000,1);r=self.report(barn_id=self.barns[0]['id']);self.assertEqual(r['to'],'2026-10-25');self.assertEqual(r['totals']['feed_orders'],0)
 def test_preentry_feed_survives_all_mode_even_if_stats_filter_started_later(self):
  o=self.order('2026-07-16',2000);r=self.report(**{'from':'2026-10-01'});self.assertEqual(r['preentry_feed']['known_kg'],2000);self.assertEqual(r['preentry_feed']['details'][0]['id'],o['id']);self.assertEqual(r['totals']['feed_orders'],0)
 def test_ledger_mode_off_still_has_order_rows_without_double_arrivals(self):
  self.order();self.add('deliveries',vendor='',date='2026-10-26',kg=1500,display_unit='ton',allocations=[{'batch_id':self.batches[0]['id'],'kg':1500}])
  with patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':''}):r=self.report()
  self.assertEqual(r['totals']['feed_orders'],2000);self.assertFalse(r['feed_orders_are_arrivals'])
