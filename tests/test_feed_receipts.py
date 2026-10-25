"""Single-ledger farm policy, including calendar stock and atomic corrections."""
import copy,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store,Problem
from app.cloud_store import CloudStore,migrate
from app.bin_stock import stock
from app.feed_receipts import receipts
from app.quick_record import preview,save
from app.feed_review import preview_feed_order,save_reviewed_feed,preview_feed_bulk,save_feed_bulk
from app.server import statistics,client_snapshot
from app.domain import consumption
from cloud_fixture import HranaFixture

class FeedReceiptTests(unittest.TestCase):
 cloud=False
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.env=patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'});self.env.start();self.day=patch('app.quick_record.today',return_value='2026-10-25');self.day.start();self.farm=patch('app.review.farm_today',return_value='2026-10-25');self.farm.start()
  self.s=Store(p/'local');self.u=self.s.create_user('owner','83000011');self.barn=self.add('barns',name='13棟');self.batch=self.add('batches',name='TEST',barn_id=self.barn['id'],entry_date='2026-01-01',entry_count=100,entry_age_days=70,status='active');self.bin=self.add('feed_bins',name='13',barn_ids=[self.barn['id']],vendor='新農科',active=True,inventory_enabled=True,capacity_kg=10000,safe_fill_percent=85,inventory_date='2026-10-01',inventory_opening_kg=0);self.remote=None
  if self.cloud:
   self.remote=HranaFixture(p/'remote');target=CloudStore('libsql://test.turso.io','synthetic-token',self.remote);migrate(self.s,target);self.s=target
 def tearDown(self):
  if self.remote:self.remote.close()
  self.env.stop();self.day.stop();self.farm.stop();self.tmp.cleanup()
 def add(self,kind,**d):return self.s.mutate(self.u,kind,d,str(uuid.uuid4()))
 def order(self,**d):return {'date':'2026-10-25','kg':2000,'display_unit':'ton','vendor':'新農科','item':'仔豬料','note':'','feed_bin_id':self.bin['id'],'target_batch_ids':[self.batch['id']]}|d
 def request(self,text='13棟叫料2噸',**d):return {'text':text,'operation_id':str(uuid.uuid4())}|d
 def write(self,request):
  p=preview(self.s,self.u,request);body={'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']};return save(self.s,self.u,body,str(uuid.uuid4()))
 def inventory(self,on='2026-10-25'):return stock(self.s.snapshot(),self.bin,on)
 def test_arrival_and_order_phrases_use_one_original_order(self):
  out=self.write(self.request('13棟到料2噸'));d=self.s.snapshot();self.assertEqual(out['kind'],'feed_orders');self.assertEqual(len(d['feed_orders']),1);self.assertFalse(d['deliveries']);self.assertEqual(self.inventory()['kg'],2000);self.assertEqual(receipts(d)[0]['id'],out['id']);snap=client_snapshot(d,'test:1');self.assertTrue(snap['feed_orders_are_arrivals']);self.assertEqual(len(snap['feed_receipts']),1)
 def test_statistics_count_received_once_but_never_invent_consumption(self):
  self.write(self.request());d=self.s.snapshot();s=statistics(d,{'to':['2026-10-25']});self.assertEqual(s['delivery_kg'],2000);self.assertEqual(s['feed_order_kg'],2000);self.assertIsNone(s['consumption_kg']);self.assertFalse(d['usages'])
 def test_modify_delete_and_retries_recalculate_original_stock(self):
  r=self.write(self.request());old=r['record'];request=self.request('13棟叫料1.5噸',action='update',kind='feed_orders',id=r['id'],revision=old['revision']);out=self.write(request);self.assertEqual(out['id'],r['id']);self.assertEqual(self.inventory()['kg'],1500)
  request={'action':'delete','kind':'feed_orders','id':r['id'],'revision':out['revision']};p=preview(self.s,self.u,request);body={'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']};key=str(uuid.uuid4());save(self.s,self.u,body,key);save(self.s,self.u,body,key);self.assertEqual(self.inventory()['kg'],0);self.assertFalse(self.s.snapshot()['feed_orders'])
 def test_future_date_only_enters_stock_on_its_calendar_day(self):
  r=self.write(self.request('2026-10-26 13棟到料2噸'));self.assertEqual(r['kind'],'feed_orders');self.assertEqual(self.inventory()['kg'],0);self.assertEqual(self.inventory('2026-10-26')['kg'],2000);s=statistics(self.s.snapshot(),{'to':['2026-10-25']});self.assertEqual(s['delivery_kg'],0)
 def test_projection_does_not_mutate_original_allocation_or_duplicate_ids(self):
  self.write(self.request());d=self.s.snapshot();before=copy.deepcopy(d);a=receipts(d);self.assertEqual(a[0]['allocations'],[{'batch_id':self.batch['id'],'kg':2000}]);self.assertEqual(d,before);self.assertEqual(len(receipts(d|{'deliveries':a})),1)
 def test_inventory_usage_uses_received_orders_but_direct_usage_stays_direct(self):
  self.write(self.request());d=self.s.snapshot();u={'method':'inventory','batch_id':self.batch['id'],'start':'2026-10-25','end':'2026-10-26','opening':100,'closing':300,'transfer_in':0,'transfer_out':0,'loss':0};self.assertEqual(consumption(u,receipts(d)),1800);u.update(method='direct',kg=123);self.assertEqual(consumption(u,receipts(d)),123)
 def test_shared_bin_receives_once_and_unallocated_consumption_is_unknown(self):
  b=self.add('barns',name='12棟');batch=self.add('batches',name='TEST-12',barn_id=b['id'],entry_date='2026-01-01',entry_count=100,status='active');bin=self.add('feed_bins',name='12、13',barn_ids=[b['id'],self.barn['id']],vendor='新農科',active=True,inventory_enabled=True,capacity_kg=10000,safe_fill_percent=85,inventory_date='2026-10-01',inventory_opening_kg=0)
  self.add('feed_orders',**self.order(feed_bin_id=bin['id'],target_batch_ids=[self.batch['id'],batch['id']]));d=self.s.snapshot();self.assertEqual(stock(d,bin,'2026-10-25')['kg'],2000);u={'method':'inventory','batch_id':self.batch['id'],'start':'2026-10-25','end':'2026-10-26','opening':0,'closing':0,'transfer_in':0,'transfer_out':0,'loss':0};self.assertIsNone(consumption(u,receipts(d)))
 def test_quick_capacity_warning_is_required_for_canonical_order(self):
  request=self.request('13棟叫料9噸');p=preview(self.s,self.u,request);self.assertIn('quick_capacity_exceeded',p['warnings']);self.assertEqual(p['inventories'][0]['after']['kg'],9000)
  with self.assertRaises(Problem):save(self.s,self.u,{'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':[]},str(uuid.uuid4()))
  self.assertFalse(self.s.snapshot()['feed_orders'])
 def test_original_review_and_bulk_writes_update_stock_without_delivery_copies(self):
  request={'record':self.order()};p=preview_feed_order(self.s,self.u,request);save_reviewed_feed(self.s,self.u,request|{'preview_token':p['preview_token'],'decision':'create','new_entry_confirmed':True},str(uuid.uuid4()));self.assertEqual(self.inventory()['kg'],2000)
  body={'date':'2026-10-25','rows':[{'record':self.order(kg=9000)}]};p=preview_feed_bulk(self.s,self.u,body);self.assertIn('quick_capacity_exceeded',p['receipt_warnings']);self.assertFalse(self.s.snapshot()['deliveries'])
 def test_concurrent_stock_change_invalidates_review(self):
  request={'record':self.order()};p=preview_feed_order(self.s,self.u,request);self.add('feed_orders',**self.order(kg=7000));body=request|{'preview_token':p['preview_token'],'decision':'create','new_entry_confirmed':True}
  with self.assertRaises(Problem) as error:save_reviewed_feed(self.s,self.u,body,str(uuid.uuid4()))
  self.assertEqual(error.exception.code,'revision_conflict');self.assertEqual(len(self.s.snapshot()['feed_orders']),1)
 def test_picking_another_entry_cannot_hide_capacity_warning(self):
  old=self.add('feed_orders',**self.order(kg=5000));p=preview_feed_order(self.s,self.u,{'record':self.order(kg=5000)})
  self.assertIn('feed_receipt_possible_capacity',p['receipt_warnings'])
  p=preview_feed_order(self.s,self.u,{'rid':old['id'],'record':self.order(kg=5000,revision=old['revision'])})
  self.assertNotIn('feed_receipt_possible_capacity',p['receipt_warnings'])
 def test_original_separate_mode_is_preserved_when_policy_is_off(self):
  self.add('feed_orders',**self.order())
  with patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':''}):self.assertEqual(self.inventory()['kg'],0);self.assertFalse(receipts(self.s.snapshot()))

class CloudFeedReceiptTests(FeedReceiptTests):cloud=True
