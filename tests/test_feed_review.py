"""Reviewed quantities: atomic corrections, concurrent edits, roles and retries."""
import json,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.feed_review import preview_feed_order,save_reviewed_feed
from app.cloud_store import CloudStore,migrate,read_document
from cloud_fixture import HranaFixture

class FeedReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('editor','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.barn=self.add('barns',name='15棟');self.batch=self.add('batches',name='JD-NEW',barn_id=self.barn['id'],entry_date='2026-10-09',entry_count=100,status='active');self.bin=self.add('feed_bins',name='15-1',barn_ids=[self.barn['id']],vendor='新農科',active=True)
 def document(self):
  db=self.store.connect()
  try:return read_document(db)
  finally:db.close()
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**d):return self.store.mutate(self.admin,kind,d,str(uuid.uuid4()))
 def record(self,**patch):return dict(date='2026-10-08',kg=8000,display_unit='ton',vendor='新農科',item='哺乳二期料',feed_bin_id=self.bin['id'],target_batch_ids=[self.batch['id']],note='source photo')|patch
 def preview(self,record=None,user=None,rid=None):return preview_feed_order(self.store,user or self.admin,{'record':record or self.record(),'rid':rid})
 def request(self,preview,record=None,**patch):return dict(record=record or self.record(),rid=preview['rid'],preview_token=preview['preview_token'],decision='create')|patch
 def save(self,body,user=None,key=None):return save_reviewed_feed(self.store,user or self.admin,body,key or str(uuid.uuid4()))
 def test_preview_is_read_only_and_matches_date_bin_even_if_type_changed(self):
  old=self.add('feed_orders',**self.record(kg=6000,item='仔豬料'));self.add('feed_orders',**self.record(date='2026-10-07'));before=self.document();p=self.preview();self.assertEqual([r['id'] for r in p['matches']],[old['id']]);self.assertEqual(p['record']['kg'],8000);self.assertEqual(before,self.document())
 def test_correction_preserves_id_creator_notes_and_before_after_audit(self):
  old=self.add('feed_orders',**self.record(kg=2000,note='manual source'));p=self.preview();self.save(self.request(p,decision='update',existing_id=old['id']));r=self.store.snapshot()['feed_orders'][0]
  self.assertEqual((r['id'],r['created_at'],r['created_by']),(old['id'],old['created_at'],old['created_by']));self.assertEqual(r['kg'],8000);self.assertEqual(r['revision'],2);self.assertIn('manual source',r['note']);self.assertIn('source photo',r['note'])
  db=self.store.connect();a=db.execute("SELECT * FROM audit WHERE action='update' AND record_id=?",(r['id'],)).fetchone();db.close();self.assertEqual(json.loads(a['before_value'])['kg'],2000);self.assertEqual(json.loads(a['after_value'])['kg'],8000)
 def test_concurrent_create_and_edit_invalidate_preview_without_overwrite(self):
  p=self.preview();self.add('feed_orders',**self.record());before=self.document()
  with self.assertRaises(Problem):self.save(self.request(p))
  self.assertEqual(before,self.document());old=self.store.snapshot()['feed_orders'][0];p=self.preview();self.store.mutate(self.admin,'feed_orders',self.record(kg=5000,revision=old['revision']),str(uuid.uuid4()),old['id']);before=self.document()
  with self.assertRaises(Problem):self.save(self.request(p,decision='update',existing_id=old['id']))
  self.assertEqual(before,self.document())
 def test_saved_retry_is_idempotent_and_new_key_cannot_replay_stale_preview(self):
  p=self.preview();body=self.request(p);key=str(uuid.uuid4());result=self.save(body,key=key);before=self.document();retry=self.save(body,key=key);self.assertEqual(retry['id'],result['id']);self.assertEqual(before,self.document())
  with self.assertRaises(Problem):self.save(body)
  with self.assertRaises(Problem):self.save(body|{'new_entry_confirmed':True},key=key)
  self.assertEqual(len(self.store.snapshot()['feed_orders']),1)
 def test_duplicate_requires_explicit_new_entry_and_retains_both_valid_events(self):
  self.add('feed_orders',**self.record());p=self.preview()
  with self.assertRaises(Problem):self.save(self.request(p))
  self.save(self.request(p,new_entry_confirmed=True));self.assertEqual(len(self.store.snapshot()['feed_orders']),2)
 def test_viewer_and_foreign_staff_update_cannot_bypass_server_permissions(self):
  for fn in (lambda:self.preview(user=self.viewer),lambda:self.save({},user=self.viewer)):
   with self.assertRaises(Problem):fn()
  old=self.add('feed_orders',**self.record());p=self.preview(user=self.staff);self.assertFalse(p['matches'][0]['can_update'])
  with self.assertRaises(Problem):self.save(self.request(p,decision='update',existing_id=old['id']),user=self.staff)
  with self.assertRaises(Problem):self.preview(self.record(revision=1),self.staff,old['id'])
  self.assertEqual(self.store.snapshot()['feed_orders'][0]['revision'],1)
 def test_own_editor_can_edit_note_and_explicit_edit_cannot_switch_target(self):
  old=self.store.mutate(self.staff,'feed_orders',self.record(note='remove me'),str(uuid.uuid4()));new=self.record(note='',revision=1);p=self.preview(new,self.staff,old['id']);self.save(self.request(p,new,decision='update',existing_id=old['id']),user=self.staff);self.assertEqual(self.store.snapshot()['feed_orders'][0]['note'],'')
  other=self.add('feed_orders',**self.record());new=self.record(revision=2);p=self.preview(new,rid=old['id'])
  with self.assertRaises(Problem):self.save(self.request(p,new,decision='update',existing_id=other['id']))
 def test_unrelated_other_day_order_does_not_force_another_review(self):
  p=self.preview();self.add('feed_orders',**self.record(date='2026-10-07'));self.save(self.request(p));self.assertEqual(len(self.store.snapshot()['feed_orders']),2)
 def test_voided_order_is_not_restored_or_offered_as_update(self):
  old=self.add('feed_orders',**self.record());self.store.mutate(self.admin,'feed_orders',{'revision':1},str(uuid.uuid4()),old['id'],delete=True);p=self.preview();self.assertFalse(p['matches']);self.assertEqual(p['voided_matches'][0]['id'],old['id'])
  with self.assertRaises(Problem):self.save(self.request(p))
  with self.assertRaises(Problem):self.save(self.request(p,decision='update',existing_id=old['id']))
  self.assertFalse(self.store.snapshot()['feed_orders'])
 def test_legacy_single_barn_allocation_is_compared_to_new_bin_record(self):
  old=self.add('feed_orders',date='2026-10-08',kg=2000,display_unit='ton',vendor='新農科',item='',allocations=[{'batch_id':self.batch['id'],'kg':2000}]);p=self.preview();self.assertEqual(p['matches'][0]['id'],old['id'])

class CloudFeedReviewTests(FeedReviewTests):
 def setUp(self):
  super().setUp();self.local=self.store;self.fixture=HranaFixture(Path(self.tmp.name)/'remote');self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.local,self.store)
 def tearDown(self):self.fixture.close();super().tearDown()
