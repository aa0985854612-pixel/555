"""Shared physical receipts auto-attribute once; confirmed quantities stay intact."""
import copy,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store,Problem
from app.feed_allocation import automatic_allocation
from app.feed import order_scope
from app.feed_review import preview_feed_order,save_reviewed_feed
from app.weekly import weekly_report
from app.server import statistics,filter_rows,client_snapshot
from app.feed_receipts import receipts
from app.bin_stock import stock
from app.domain import consumption
from app.operations import token

class AutoFeedAllocationTests(unittest.TestCase):
 cloud=False
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'headcount','FEED_ORDERS_ARE_ARRIVALS':'1'});self.env.start();self.s=Store(Path(self.tmp.name)/'db');self.u=self.s.create_user('owner','83000011');self.reader=self.s.create_user('reader','83000012','viewer')
  self.barns={n:self.add('barns',name=f'{n}棟') for n in (1,2,18)};self.batches={n:self.add('batches',barn_id=b['id'],name='A' if n in (1,18) else 'B',entry_date='2026-10-01',entry_count=300 if n==2 else 100,entry_age_days=70,status='active') for n,b in self.barns.items()};self.bin=self.add('feed_bins',name='1、2',vendor='養全',barn_ids=[self.barns[n]['id'] for n in (1,2)],active=True,inventory_enabled=True,capacity_kg=10000,safe_fill_percent=85,inventory_date='2026-10-01',inventory_opening_kg=0);self.remote=None
  if self.cloud:
   from cloud_fixture import HranaFixture
   from app.cloud_store import CloudStore,migrate
   self.remote=HranaFixture(Path(self.tmp.name)/'remote');target=CloudStore('libsql://test.turso.io','synthetic-token',self.remote);migrate(self.s,target);self.s=target
 def tearDown(self):
  if self.remote:self.remote.close()
  self.env.stop();self.tmp.cleanup()
 def add(self,kind,**d):return self.s.mutate(self.u,kind,d,str(uuid.uuid4()))
 def body(self,**d):return dict(date='2026-10-27',kg=4000,display_unit='ton',vendor='養全',item='哺乳二期料',feed_bin_id=self.bin['id'],target_batch_ids=[self.batches[n]['id'] for n in (1,2)],bin_allocations=[],allocations=[])|d
 def order(self,**d):return self.add('feed_orders',**self.body(**d))
 def report(self,key='A',**q):return weekly_report(self.s.snapshot(),{'cohort':[key+'|2026-10-01'],'all_records':['1']}|{k:[v] for k,v in q.items()},today='2026-10-25')
 def test_unallocated_original_shared_order_immediately_appears_in_each_proper_paper(self):
  o=self.order();d=self.s.snapshot();before=copy.deepcopy(d)
  for key,kg in [('A',1000),('B',3000)]:
   r=self.report(key);self.assertEqual(r['totals']['feed_orders'],kg);rows=[e for w in r['weeks'] for e in w['feed_details']];self.assertEqual(len(rows),1);self.assertEqual((rows[0]['id'],rows[0]['kg'],rows[0]['bin'],rows[0]['allocation_basis']),(o['id'],kg,'1','auto_headcount'));self.assertFalse(any(w['feed_shared_details'] for w in r['weeks']))
  self.assertEqual(self.s.snapshot(),before)
 def test_original_total_one_id_and_physical_stock_are_not_doubled(self):
  o=self.order();d=self.s.snapshot();self.assertEqual(len(d['feed_orders']),1);self.assertEqual(statistics(d,{'to':['2026-10-27']})['delivery_kg'],4000);self.assertEqual(stock(d,self.bin,'2026-10-27')['kg'],4000);self.assertEqual(stock(d,self.bin,'2026-10-26')['kg'],0);self.assertEqual(o['bin_allocations'],[]);self.assertEqual(statistics(d,{'to':['2026-10-27']})['unallocated_kg'],0);whole=copy.deepcopy(d);next(b for b in whole['batches'] if b['id']==self.batches[2]['id'])['name']='A';r=weekly_report(whole,{'cohort':['A|2026-10-01'],'all_records':['1']},today='2026-10-25');self.assertEqual(len([e for w in r['weeks'] for e in w['feed_details']]),1);self.assertEqual(r['totals']['feed_orders'],4000)
 def test_dated_headcounts_include_deaths_and_exclude_later_changes(self):
  self.add('movements',date='2026-10-27',batch_id=self.batches[1]['id'],type='death',quantity=20);self.add('movements',date='2026-10-28',batch_id=self.batches[2]['id'],type='sale',quantity=100)
  o=self.order();p=automatic_allocation(o,self.s.snapshot());self.assertEqual(p['heads'],{self.batches[1]['id']:80,self.batches[2]['id']:300});self.assertEqual([a['kg'] for a in p['allocations']],[842,3158]);self.assertEqual(sum(a['kg'] for a in p['allocations']),4000)
 def test_later_correction_of_heads_recalculates_old_unconfirmed_portions(self):
  self.order();self.assertEqual(self.report()['totals']['feed_orders'],1000);self.add('movements',date='2026-10-26',batch_id=self.batches[1]['id'],type='death',quantity=20);self.assertEqual(self.report()['totals']['feed_orders'],842)
 def test_confirmed_manual_parts_always_override_auto(self):
  o=self.order(bin_allocations=[{'batch_id':self.batches[n]['id'],'kg':2000} for n in (1,2)]);self.assertIsNone(automatic_allocation(o,self.s.snapshot()));self.add('movements',date='2026-10-26',batch_id=self.batches[1]['id'],type='death',quantity=20);self.assertEqual(self.report()['totals']['feed_orders'],2000)
 def test_unique_dated_batches_can_be_found_when_old_record_targets_are_missing(self):
  o=self.order(target_batch_ids=[]);p=automatic_allocation(o,self.s.snapshot());self.assertEqual([a['kg'] for a in p['allocations']],[1000,3000]);self.assertEqual(self.report()['totals']['feed_orders'],1000)
 def test_ambiguous_or_unknown_heads_are_not_invented(self):
  o=self.order();d=self.s.snapshot();next(b for b in d['batches'] if b['id']==self.batches[1]['id'])['entry_count']=None;self.assertIsNone(automatic_allocation(o,d))
  self.add('batches',barn_id=self.barns[1]['id'],name='OVERLAP',entry_date='2026-10-01',entry_count=30,status='active');o=self.order(target_batch_ids=[]);self.assertIsNone(automatic_allocation(o,self.s.snapshot()))
 def test_zero_head_barn_receives_zero_and_small_quantities_conserve_exact_total(self):
  self.add('movements',date='2026-10-26',batch_id=self.batches[1]['id'],type='sale',quantity=100);o=self.order(kg=.000002);p=automatic_allocation(o,self.s.snapshot());self.assertEqual(p['allocations'],[{'batch_id':self.batches[2]['id'],'kg':.000002}])
 def test_equal_mode_and_off_mode_are_explicit(self):
  o=self.order();d=self.s.snapshot()
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):self.assertEqual([a['kg'] for a in automatic_allocation(o,d)['allocations']],[2000,2000])
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':''}):self.assertIsNone(automatic_allocation(o,d));self.assertIsNone(order_scope(o,d,{self.batches[1]['id']})['kg'])
 def test_equal_mode_divides_odd_kg_in_half_without_headcount_rounding(self):
  o=self.order(kg=2001);d=self.s.snapshot()
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):
   p=automatic_allocation(o,d);self.assertEqual([a['kg'] for a in p['allocations']],[1000.5,1000.5]);self.assertEqual(self.report()['totals']['feed_orders'],1000.5)
 def test_equal_mode_ignores_zero_or_unknown_heads_for_explicit_targets(self):
  o=self.order(kg=2000);d=self.s.snapshot();next(b for b in d['batches'] if b['id']==self.batches[1]['id'])['entry_count']=0
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):self.assertEqual([a['kg'] for a in automatic_allocation(o,d)['allocations']],[1000,1000])
  next(b for b in d['batches'] if b['id']==self.batches[1]['id'])['entry_count']=None
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):self.assertEqual([a['kg'] for a in automatic_allocation(o,d)['allocations']],[1000,1000])
 def test_equal_mode_retains_manually_confirmed_portions(self):
  o=self.order(bin_allocations=[{'batch_id':self.batches[1]['id'],'kg':1000},{'batch_id':self.batches[2]['id'],'kg':3000}])
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):self.assertIsNone(automatic_allocation(o,self.s.snapshot()));self.assertEqual(self.report()['totals']['feed_orders'],1000)
 def test_preentry_uses_explicit_upcoming_entry_counts_in_a_separate_section(self):
  self.order(date='2026-09-30');r=self.report();self.assertEqual(r['preentry_feed']['total_kg'],1000);self.assertEqual(r['totals']['feed_orders'],0)
 def test_original_review_shows_auto_parts_and_retry_creates_one_order(self):
  body={'record':self.body()};p=preview_feed_order(self.s,self.u,body);self.assertEqual([r['kg'] for r in p['automatic_allocation']['allocations']],[1000,3000]);request=body|{'preview_token':p['preview_token'],'decision':'create'};key=str(uuid.uuid4());first=save_reviewed_feed(self.s,self.u,request,key);again=save_reviewed_feed(self.s,self.u,request,key);self.assertEqual(first['id'],again['id']);self.assertEqual(len(self.s.snapshot()['feed_orders']),1)
 def test_preview_rejects_changed_heads_or_mode(self):
  body={'record':self.body()};p=preview_feed_order(self.s,self.u,body);self.add('movements',date='2026-10-26',batch_id=self.batches[1]['id'],type='death',quantity=20)
  with self.assertRaises(Problem):save_reviewed_feed(self.s,self.u,body|{'preview_token':p['preview_token'],'decision':'create'},str(uuid.uuid4()))
  p=preview_feed_order(self.s,self.u,body)
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}),self.assertRaises(Problem):save_reviewed_feed(self.s,self.u,body|{'preview_token':p['preview_token'],'decision':'create'},str(uuid.uuid4()))
 def test_estimated_receipt_split_does_not_become_measured_inventory_consumption(self):
  self.order();d=self.s.snapshot();u=dict(method='inventory',batch_id=self.batches[1]['id'],feed_bin_id=self.bin['id'],start='2026-10-27',end='2026-10-28',opening=0,closing=0,transfer_in=0,transfer_out=0,loss=0);self.assertIsNone(consumption(u,receipts(d)));u.update(method='direct',kg=123);self.assertEqual(consumption(u,receipts(d)),123)
 def test_scope_snapshot_and_token_expose_policy_without_changing_original_records(self):
  o=self.order(target_batch_ids=[]);d=self.s.snapshot();rows=filter_rows('feed_orders',d,{'batch_id':[self.batches[1]['id']]});self.assertEqual(rows[0]['scope_attribution']['kg'],1000);self.assertEqual(rows[0]['automatic_allocation']['basis'],'auto_headcount');self.assertEqual(client_snapshot(d,'test')['feed_auto_allocation'],'headcount');self.assertNotIn('order:'+o['id'],[i['id'] for i in client_snapshot(d,'test')['data_quality']['items']]);original=token(d)
  with patch.dict(os.environ,{'FEED_AUTO_ALLOCATION':'equal'}):self.assertNotEqual(token(d),original)
 def test_edit_and_void_recalculate_without_adding_receipt_copies(self):
  old=self.order();updated=self.s.mutate(self.u,'feed_orders',self.body(kg=2000,revision=old['revision']),str(uuid.uuid4()),old['id']);self.assertEqual(self.report()['totals']['feed_orders'],500);self.s.mutate(self.u,'feed_orders',{'revision':updated['revision']},str(uuid.uuid4()),old['id'],delete=True);self.assertEqual(self.report()['totals']['feed_orders'],0)
 def test_viewer_cannot_create_or_change_split(self):
  with self.assertRaises(Problem) as e:self.s.mutate(self.reader,'feed_orders',self.body(),str(uuid.uuid4()))
  self.assertEqual(e.exception.status,403)

class CloudAutoFeedAllocationTests(AutoFeedAllocationTests):cloud=True
