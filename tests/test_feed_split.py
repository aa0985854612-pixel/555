"""A physical bin may supply two cohorts; explicit portions conserve its total."""
import copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.feed import order_scope,bin_label
from app.history import cohort_key
from app.server import statistics,filter_rows
from app.weekly import weekly_report
from app.feed_review import preview_feed_order,save_reviewed_feed

class FeedSplitTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=Store(Path(self.temp.name)/'local');self.u=self.s.create_user('owner','83000011');self.staff=self.s.create_user('worker','83000012','staff');self.viewer=self.s.create_user('reader','83000013','viewer')
  self.barns={n:self.add('barns',name=f'{n}棟') for n in (1,2,3,4,18)}
  self.batches={n:self.add('batches',name='A' if n in (1,18) else 'B',entry_date='2026-10-01',entry_age_days=70,entry_count=100,status='active',barn_id=b['id']) for n,b in self.barns.items()}
  self.bin=self.add('feed_bins',name='1、2',barn_ids=[self.barns[n]['id'] for n in (1,2)],vendor='養全',active=True)
 def tearDown(self):self.temp.cleanup()
 def add(self,kind,**row):return self.s.mutate(self.u,kind,row,str(uuid.uuid4()))
 def body(self,**patch):return dict(date='2026-10-12',kg=4000,display_unit='ton',vendor='養全',item='大豬料',feed_bin_id=self.bin['id'],target_batch_ids=[self.batches[n]['id'] for n in (1,2)],allocations=[],bin_allocations=[{'batch_id':self.batches[n]['id'],'kg':2000} for n in (1,2)])|patch
 def order(self,**patch):return self.s.mutate(self.staff,'feed_orders',self.body(**patch),str(uuid.uuid4()))
 def report(self,n,**patch):return weekly_report(self.s.snapshot(),{'cohort':[cohort_key(self.batches[n])],'to':['2026-10-18']}|patch,today='2026-10-18')
 def test_two_cohort_sheets_show_two_tonnes_each_and_one_four_tonne_farm_order(self):
  original=self.order();data=self.s.snapshot()
  for n,barns in ((1,{'1棟','18棟'}),(2,{'2棟','3棟','4棟'})):
   report=self.report(n);self.assertEqual(set(report['barns']),barns);self.assertEqual(report['totals']['feed_orders'],2000)
   detail=[r for w in report['weeks'] for r in w['feed_details']];self.assertEqual(len(detail),1);self.assertEqual((detail[0]['kg'],detail[0]['bin_label'],detail[0]['bin_total_kg']),(2000,'1',4000))
   query={'cohort':[cohort_key(self.batches[n])]};self.assertEqual(statistics(data,query)['feed_order_kg'],2000);row=filter_rows('feed_orders',data,query)[0];self.assertEqual(row['kg'],4000);self.assertEqual(row['scope_attribution']['kg'],2000)
  self.assertEqual(statistics(data,{})['feed_order_kg'],4000);self.assertEqual(len(data['feed_orders']),1);self.assertEqual(original['feed_bin_snapshot']['name'],'1、2');self.assertFalse(data['usages'])
 def test_unconfirmed_old_order_remains_unknown_and_never_auto_splits(self):
  self.order(bin_allocations=[]);self.assertIsNone(self.report(1)['totals']['feed_orders']);self.assertIsNone(self.report(2)['totals']['feed_orders']);self.assertEqual(statistics(self.s.snapshot(),{})['feed_order_kg'],4000)
 def test_unrelated_barns_and_new_batches_get_no_portion(self):
  self.order();data=self.s.snapshot()
  for n in (3,4,18):self.assertEqual(filter_rows('feed_orders',data,{'barn_id':[self.barns[n]['id']]}),[])
  new=self.add('batches',name='NEW',entry_date='2026-10-15',entry_count=20,status='active',barn_id=self.barns[1]['id']);self.assertFalse(filter_rows('feed_orders',self.s.snapshot(),{'batch_id':[new['id']]}))
 def test_bad_totals_duplicate_foreign_and_forged_portions_rejected(self):
  rows=self.body()['bin_allocations']
  for invalid in (None,{},[rows[0]],[rows[0],rows[0]],[rows[0],{'batch_id':self.batches[18]['id'],'kg':2000}],[rows[0],{'batch_id':self.batches[2]['id'],'kg':-2000}],[rows[0],{'batch_id':self.batches[2]['id'],'kg':True}],[rows[0],rows[1]|{'invented':1}]):
   with self.subTest(invalid=invalid),self.assertRaises(Problem):self.order(bin_allocations=invalid)
  self.assertFalse(self.s.snapshot()['feed_orders'])
 def test_same_cohort_mixed_arrival_dates_split_preentry_portion_correctly(self):
  later=self.s.mutate(self.u,'batches',self.batches[2]|{'name':'A','entry_date':'2026-10-16','same_batch_as':self.batches[1]['id']},str(uuid.uuid4()),self.batches[2]['id']);self.batches[2]=later;self.order(date='2026-10-10')
  report=self.report(1);self.assertEqual(report['totals']['feed_orders'],2000);self.assertEqual(report['preentry_feed']['total_kg'],2000);self.assertEqual(report['preentry_feed']['details'][0]['batch_id'],later['id'])
 def test_same_cohort_portions_sum_without_becoming_two_physical_orders(self):
  self.s.mutate(self.u,'batches',self.batches[2]|{'name':'A'},str(uuid.uuid4()),self.batches[2]['id']);self.order();self.assertEqual(self.report(1)['totals']['feed_orders'],4000);self.assertEqual(statistics(self.s.snapshot(),{})['feed_order_kg'],4000)
 def test_repeated_review_update_preserves_id_and_original_snapshot_with_audit(self):
  body={'record':self.body()};p=preview_feed_order(self.s,self.staff,body);req=body|{'preview_token':p['preview_token'],'decision':'create'};key=str(uuid.uuid4());saved=save_reviewed_feed(self.s,self.staff,req,key);self.assertEqual(save_reviewed_feed(self.s,self.staff,req,key)['id'],saved['id']);original=self.s.snapshot()['feed_orders'][0]
  rows=[{'batch_id':self.batches[1]['id'],'kg':1000},{'batch_id':self.batches[2]['id'],'kg':3000}];body={'rid':saved['id'],'record':self.body(bin_allocations=rows,revision=1)};p=preview_feed_order(self.s,self.staff,body);save_reviewed_feed(self.s,self.staff,body|{'preview_token':p['preview_token'],'decision':'update','existing_id':saved['id']},str(uuid.uuid4()))
  now=self.s.snapshot()['feed_orders'][0];self.assertEqual(now['id'],original['id']);self.assertEqual(now['revision'],2);self.assertEqual(now['feed_bin_snapshot'],original['feed_bin_snapshot']);self.assertEqual(self.report(1)['totals']['feed_orders'],1000);self.assertEqual(self.report(2)['totals']['feed_orders'],3000)
 def test_old_client_omission_preserves_portions_and_backup_roundtrip(self):
  old=self.order();body=self.body(revision=1);body.pop('bin_allocations');updated=self.s.mutate(self.staff,'feed_orders',body,str(uuid.uuid4()),old['id']);self.assertEqual(updated['bin_allocations'],old['bin_allocations'])
  body['revision']=2;body['kg']=5000
  with self.assertRaises(Problem):self.s.mutate(self.staff,'feed_orders',body,str(uuid.uuid4()),old['id'])
  clone=Store(Path(self.temp.name)/'restore');clone.import_backup(self.u,self.s.export_backup());self.assertEqual(clone.snapshot()['feed_orders'],self.s.snapshot()['feed_orders'])
 def test_permissions_and_void_remove_each_portion_once(self):
  with self.assertRaises(Problem) as e:self.s.mutate(self.viewer,'feed_orders',self.body(),str(uuid.uuid4()))
  self.assertEqual(e.exception.status,403);r=self.order();self.s.mutate(self.u,'feed_orders',{'revision':1},str(uuid.uuid4()),r['id'],delete=True);self.assertEqual(self.report(1)['totals']['feed_orders'],0);self.assertEqual(self.report(2)['totals']['feed_orders'],0);self.assertEqual(statistics(self.s.snapshot(),{})['feed_order_kg'],0)
 def test_only_confirmed_short_names_change_display(self):
  for original,short in [('1、2','1'),('16、17','16'),('3、4','3'),('5、6','5'),('15-1','15-1'),('自訂桶','自訂桶')]:self.assertEqual(bin_label({'name':original}),short)

class CloudFeedSplitTests(FeedSplitTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.temp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.s,cloud);self.s=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
