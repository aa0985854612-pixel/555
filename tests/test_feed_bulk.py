"""Feed lists validate together, review duplicates and commit all rows exactly once."""
import copy,unittest,tempfile,uuid
from pathlib import Path
from app.store import Store,Problem
from app.domain import Invalid
from app.feed_review import preview_feed_bulk,save_feed_bulk
import test_feed_review as feed_cases

class FeedBulkTests(unittest.TestCase):
 setUp=feed_cases.FeedReviewTests.setUp
 tearDown=feed_cases.FeedReviewTests.tearDown
 add=feed_cases.FeedReviewTests.add
 record=feed_cases.FeedReviewTests.record
 document=feed_cases.FeedReviewTests.document
 def body(self,records=None):return {'date':'2026-10-08','draft_id':str(uuid.uuid4()),'rows':[{'record':r} for r in (records or [self.record()])]}
 def preview(self,body,user=None):return preview_feed_bulk(self.store,user or self.admin,body)
 def reviewed(self,body,choices=None):
  p=self.preview(body);r=copy.deepcopy(body);r['preview_token']=p['preview_token']
  for i,row in enumerate(r['rows']):row.update((choices or [{}]*len(r['rows']))[i] or {'decision':'create'})
  return r
 def save(self,body,key=None,user=None):return save_feed_bulk(self.store,user or self.admin,body,key or str(uuid.uuid4()))
 def second(self):
  barn=self.add('barns',name='19棟');batch=self.add('batches',name='NEXT',barn_id=barn['id'],entry_date='2026-10-09',entry_count=350,status='active');bin=self.add('feed_bins',name='19',barn_ids=[barn['id']],vendor='新農科',active=True);return self.record(feed_bin_id=bin['id'],target_batch_ids=[batch['id']],kg=2000,item='',vendor='')
 def test_preview_then_atomic_multiple_bins_preserves_preentry_and_blank_type(self):
  b=self.body([self.record(),self.second()]);before=self.document();p=self.preview(b);self.assertEqual(before,self.document());self.assertEqual((p['count'],p['total_kg']),(2,10000));r=self.save(self.reviewed(b));d=self.store.snapshot();self.assertEqual(len(r['ids']),2);self.assertEqual([x['date'] for x in d['feed_orders']],['2026-10-08']*2);self.assertEqual([x['kg'] for x in d['feed_orders']],[8000,2000]);self.assertEqual(d['feed_orders'][1]['item'],'');self.assertEqual(d['feed_orders'][1]['vendor'],'');self.assertEqual(d['deliveries'],[]);self.assertEqual(d['usages'],[])
 def test_existing_record_update_and_new_order_keep_id_creator_notes(self):
  old=self.add('feed_orders',**self.record(kg=1000,note='old source'));b=self.body([self.record(kg=2000),self.second()]);choices=[{'decision':'update','existing_id':old['id']},{'decision':'create'}];r=self.save(self.reviewed(b,choices));orders=self.store.snapshot()['feed_orders'];self.assertEqual(len(orders),2);self.assertEqual(r['ids'][0],old['id']);self.assertEqual(orders[0]['created_by'],old['created_by']);self.assertEqual(orders[0]['revision'],2);self.assertIn('old source',orders[0]['note'])
 def test_existing_or_in_list_duplicates_require_explicit_confirmation(self):
  b=self.body([self.record(),self.record(kg=2000)]);p=self.preview(b);self.assertEqual([r['queue_matches'] for r in p['rows']],[[1],[0]]);before=self.document()
  with self.assertRaises(Problem):self.save(self.reviewed(b))
  self.assertEqual(before,self.document());self.save(self.reviewed(b,[{'decision':'create','new_entry_confirmed':True}]*2));self.assertEqual(len(self.store.snapshot()['feed_orders']),2)
  b=self.body();p=self.preview(b);self.assertEqual(len(p['rows'][0]['matches']),2)
  with self.assertRaises(Problem):self.save(self.reviewed(b))
 def test_two_corrections_cannot_overwrite_same_existing_row_and_nothing_commits(self):
  old=self.add('feed_orders',**self.record());b=self.body([self.second(),self.record(kg=1000),self.record(kg=2000)]);request=self.reviewed(b,[{'decision':'create'},{'decision':'update','existing_id':old['id']},{'decision':'update','existing_id':old['id']}]);before=self.document()
  with self.assertRaises(Problem) as e:self.save(request)
  self.assertEqual(e.exception.code,'feed_bulk_same_target');self.assertEqual(before,self.document())
 def test_stale_preview_invalidates_whole_list_and_retries_are_idempotent(self):
  b=self.body([self.record(),self.second()]);request=self.reviewed(b);self.add('feed_orders',**self.record(kg=2000));before=self.document()
  with self.assertRaises(Problem):self.save(request)
  self.assertEqual(before,self.document());request=self.reviewed(b,[{'decision':'create','new_entry_confirmed':True},{'decision':'create'}]);key=str(uuid.uuid4());r=self.save(request,key);before=self.document();self.assertEqual(self.save(request,key)['ids'],r['ids']);self.assertEqual(before,self.document())
  with self.assertRaises(Problem):self.save(request)
  with self.assertRaises(Problem):self.save(request|{'date':'2026-10-09'},key)
 def test_shared_bin_explicit_split_and_optional_type_survive(self):
  barn=self.add('barns',name='16棟');batch=self.add('batches',name='OTHER',barn_id=barn['id'],entry_date='2026-10-10',entry_count=100,status='active');bin=self.add('feed_bins',name='shared',barn_ids=[self.barn['id'],barn['id']],vendor='新農科',active=True);r=self.record(feed_bin_id=bin['id'],target_batch_ids=[self.batch['id'],batch['id']],kg=4000,item='',bin_allocations=[{'batch_id':self.batch['id'],'kg':2000},{'batch_id':batch['id'],'kg':2000}]);self.save(self.reviewed(self.body([r])));saved=self.store.snapshot()['feed_orders'][0];self.assertEqual(saved['bin_allocations'],r['bin_allocations']);self.assertEqual(saved['date'],'2026-10-08');self.assertEqual(saved['kg'],4000)
 def test_invalid_last_row_and_mixed_dates_or_limits_are_rejected(self):
  second=self.second();before=self.document()
  for body in (self.body([self.record(),second|{'kg':0}]),self.body([self.record(),second|{'date':'2026-10-09'}]),{'date':'2026-10-08','rows':[]},self.body([self.record()]*51),{'date':'bad','rows':[{'record':self.record()}]}):
   with self.assertRaises((Problem,Invalid)):self.preview(body)
   self.assertEqual(before,self.document())
 def test_permissions_and_forged_decisions_rollback_first_row(self):
  old=self.add('feed_orders',**self.record());b=self.body([self.second(),self.record(kg=2000)]);p=self.preview(b,self.staff);self.assertFalse(p['rows'][1]['matches'][0]['can_update']);request=b|{'preview_token':p['preview_token']};request=copy.deepcopy(request);request['rows'][0]['decision']='create';request['rows'][1].update(decision='update',existing_id=old['id']);before=self.document()
  with self.assertRaises(Problem):self.save(request,user=self.staff)
  self.assertEqual(before,self.document())
  with self.assertRaises(Problem):self.preview(b,self.viewer)
  with self.assertRaises(Problem):self.save({},user=self.viewer)
 def test_voided_match_is_not_restored_and_backup_preserves_list(self):
  old=self.add('feed_orders',**self.record());self.store.mutate(self.admin,'feed_orders',{'revision':1},str(uuid.uuid4()),old['id'],delete=True);b=self.body();p=self.preview(b);self.assertEqual(p['rows'][0]['voided_matches'][0]['id'],old['id'])
  with self.assertRaises(Problem):self.save(self.reviewed(b))
  self.save(self.reviewed(b,[{'decision':'create','new_entry_confirmed':True}]));clone=Store(Path(self.tmp.name)/'restored');clone.import_backup(self.admin,self.store.export_backup());self.assertEqual(clone.snapshot()['feed_orders'],self.store.snapshot()['feed_orders']);self.assertNotEqual(clone.snapshot()['feed_orders'][0]['id'],old['id'])

class CloudFeedBulkTests(FeedBulkTests):
 def setUp(self):
  super().setUp();from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
