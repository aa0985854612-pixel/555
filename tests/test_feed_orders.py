"""Order quantities never become receipts or consumption; preserve role and retry rules."""
import json,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.domain import Invalid,performance,herd
from app.server import statistics,filter_rows
from app.operations import void_preview,void_record
from app.cloud_store import CloudStore,migrate
from cloud_fixture import HranaFixture

class FeedOrderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('editor','83000012','staff');self.other=self.store.create_user('other','83000013','staff');self.viewer=self.store.create_user('reader','83000014','viewer')
  self.barn=self.add('barns',name='19棟',group='A');self.batch=self.add('batches',barn_id=self.barn['id'],name='JD-ORDER',entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active')
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))
 def body(self,**patch):return dict(date='2026-10-02',kg=1500,display_unit='ton',vendor='',item='',note='',allocations=[])|patch
 def order(self,user=None,**patch):return self.store.mutate(user or self.staff,'feed_orders',self.body(**patch),str(uuid.uuid4()))
 def perf(self):
  d=self.store.snapshot();return performance(d['batches'][0],d['batches'],d['movements'],d['weights'],d['usages'],d['deliveries'],'2026-10-11')
 def weights(self):
  for on,w in [('2026-10-01',50),('2026-10-11',60)]:self.add('weights',batch_id=self.batch['id'],date=on,count=10,total_kg=w*10,representative=True)
 def test_order_independent_from_receipts_and_consumption(self):
  self.order();d=self.store.snapshot();self.assertEqual(len(d['feed_orders']),1);self.assertEqual(d['deliveries'],[]);self.assertEqual(d['usages'],[])
  s=statistics(d,{'from':['2026-10-01'],'to':['2026-10-11']});self.assertEqual(s['feed_order_kg'],1500);self.assertEqual(s['delivery_kg'],0);self.assertIsNone(s['consumption_kg']);self.assertEqual(s['cumulative']['remaining'],100)
 def test_orders_cannot_supply_missing_fcr_feed(self):
  self.weights();self.order();self.assertIsNone(self.perf()['fcr']);self.assertIsNone(self.perf()['feed'])
 def test_order_create_edit_and_void_do_not_change_actual_fcr(self):
  self.weights();self.add('usages',batch_id=self.batch['id'],start='2026-10-01',end='2026-10-11',method='direct',kg=2000,active=True);self.assertEqual(self.perf()['fcr'],2)
  o=self.order();self.assertEqual(self.perf()['fcr'],2)
  o=self.store.mutate(self.staff,'feed_orders',self.body(kg=9000,revision=o['revision']),str(uuid.uuid4()),o['id']);self.assertEqual(self.perf()['fcr'],2)
  p=void_preview(self.store,self.admin,self.store.snapshot(),'feed_orders',o['id']);self.assertEqual(p['impact']['farm_before'],p['impact']['farm_after']);self.assertEqual(p['impact']['feed_order_kg_removed'],9000)
  void_record(self.store,self.admin,{'kind':'feed_orders','id':o['id'],'preview_token':p['preview_token'],'reason':'synthetic correction'},str(uuid.uuid4()));self.assertEqual(self.perf()['fcr'],2);self.assertEqual(self.store.snapshot()['feed_orders'],[])
  db=self.store.connect();raw=db.execute('SELECT deleted,data FROM records WHERE id=?',(o['id'],)).fetchone();self.assertEqual(raw['deleted'],1);self.assertEqual(json.loads(raw['data'])['void_reason'],'synthetic correction');db.close()
 def test_retries_do_not_duplicate_and_stale_edits_are_rejected(self):
  key=str(uuid.uuid4());body=self.body();a=self.store.mutate(self.staff,'feed_orders',body,key);b=self.store.mutate(self.staff,'feed_orders',body,key);self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.store.snapshot()['feed_orders']),1)
  with self.assertRaises(Problem):self.store.mutate(self.staff,'feed_orders',body|{'kg':1},key)
  self.store.mutate(self.staff,'feed_orders',body|{'revision':1,'kg':1600},str(uuid.uuid4()),a['id'])
  with self.assertRaises(Problem):self.store.mutate(self.staff,'feed_orders',body|{'revision':1,'kg':1700},str(uuid.uuid4()),a['id'])
  self.assertEqual(self.store.snapshot()['feed_orders'][0]['kg'],1600)
 def test_viewer_and_unrelated_editor_cannot_write_or_void(self):
  with self.assertRaises(Problem):self.order(user=self.viewer)
  o=self.order()
  with self.assertRaises(Problem):self.store.mutate(self.other,'feed_orders',self.body(revision=1),str(uuid.uuid4()),o['id'])
  for user in (self.staff,self.viewer):
   with self.assertRaises(Problem):void_preview(self.store,user,self.store.snapshot(),'feed_orders',o['id'])
   with self.assertRaises(Problem):self.store.mutate(user,'feed_orders',{'revision':1},str(uuid.uuid4()),o['id'],delete=True)
 def test_invalid_quantity_unit_and_allocation_roll_back(self):
  for patch in ({'kg':0},{'kg':-1},{'kg':True},{'display_unit':'bag'},{'allocations':[{'batch_id':'missing','kg':1500}]},{'allocations':[{'batch_id':self.batch['id'],'kg':1000}]}):
   with self.subTest(patch=patch):
    with self.assertRaises((Invalid,Problem)):self.order(**patch)
  self.assertEqual(self.store.snapshot()['feed_orders'],[])
 def test_date_barn_cohort_and_vendor_filters_match_order_totals(self):
  self.order(allocations=[{'batch_id':self.batch['id'],'kg':1500}],vendor='養全');self.order(date='2026-10-03',kg=500);d=self.store.snapshot()
  for q,n in [({'from':['2026-10-02'],'to':['2026-10-02']},1500),({'barn_id':[self.barn['id']]},1500),({'cohort':['JD-ORDER|2026-10-01']},1500),({'vendor':['新農科']},0)]:
   self.assertEqual(sum(o['kg'] for o in filter_rows('feed_orders',d,q)),n)
  self.assertEqual(statistics(d,{'from':['2026-10-02'],'to':['2026-10-03']})['feed_order_kg'],2000)
 def test_can_record_order_before_entry_without_creating_receipt(self):
  self.order(date='2026-09-30',allocations=[{'batch_id':self.batch['id'],'kg':1500}]);self.store.validate_global(self.store.snapshot());self.assertEqual(self.store.snapshot()['deliveries'],[])
 def test_backup_retains_new_orders_and_old_records(self):
  self.add('deliveries',**self.body());self.order();doc=self.store.export_backup();clone=Store(Path(self.tmp.name)/'restore');clone.import_backup(self.admin,doc);self.assertEqual(len(clone.snapshot()['feed_orders']),1);self.assertEqual(len(clone.snapshot()['deliveries']),1);self.assertEqual(clone.import_backup(self.admin,doc)['added'],0)

class CloudFeedOrderTests(FeedOrderTests):
 def setUp(self):
  super().setUp();self.local=self.store;self.fixture=HranaFixture(Path(self.tmp.name)/'remote');self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.local,self.store)
 def tearDown(self):self.fixture.close();super().tearDown()
