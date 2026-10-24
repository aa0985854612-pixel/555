"""Unconfirmed photo drafts cannot become feed totals; confirmation is atomic and reviewed."""
import copy,json,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.feed_drafts import save_draft,preview_draft,finish_draft
from app.server import statistics
from app.weekly import weekly_report
from app.cloud_store import CloudStore,migrate,read_document
from cloud_fixture import HranaFixture

class FeedDraftTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('editor','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.barn=self.add('barns',name='13棟');self.batch=self.add('batches',name='JD-28',barn_id=self.barn['id'],entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active');self.bin=self.add('feed_bins',name='13',vendor='新農科',barn_ids=[self.barn['id']],active=True)
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))
 def record(self,**patch):return dict(date='2026-10-20',kg=2000,feed_bin_id=self.bin['id'],vendor='新農科',item='仔豬料',note='林可黴素 110ppm、旭維康 1kg',display_unit='ton')|patch
 def payload(self,records=None):return {'draft':{'title':'照片叫料核對','source':'chat_photo','sources':[{'name':'photo.jpg'}],'rows':[{'key':str(uuid.uuid4()),'record':r,'bin_label':'13','warning':'','choice':'auto'} for r in (records or [self.record()])]}}
 def stage(self,payload=None,user=None,key=None,rid=None):return save_draft(self.store,user or self.admin,payload or self.payload(),key or str(uuid.uuid4()),rid)
 def draft(self,rid):return next(d for d in self.store.snapshot()['feed_drafts'] if d['id']==rid)
 def preview(self,rid,user=None):return preview_draft(self.store,user or self.admin,rid,{'revision':self.draft(rid)['revision']})
 def confirm(self,p,user=None,key=None,**patch):return finish_draft(self.store,user or self.admin,p['id'],dict(revision=p['revision'],preview_token=p['preview_token'],confirmed=True)|patch,key or str(uuid.uuid4()))
 def doc(self):
  db=self.store.connect()
  try:return read_document(db)
  finally:db.close()
 def test_staging_and_preview_do_not_add_feed_or_change_herd_reports(self):
  data=self.store.snapshot();before=statistics(data,{'to':['2026-10-24']});r=self.stage();p=self.preview(r['id']);self.assertTrue(p['can_confirm']);after=self.store.snapshot();self.assertFalse(after['feed_orders']);self.assertEqual(self.draft(r['id'])['status'],'pending');self.assertEqual(statistics(after,{'to':['2026-10-24']}),before)
  report=weekly_report(after,{'batch_id':[self.batch['id']],'to':['2026-10-24']},today='2026-10-24');self.assertEqual(report['totals']['feed_orders'],0);self.assertFalse(any(w['feed_details'] for w in report['weeks']))
 def test_explicit_checkbox_and_current_proof_are_required(self):
  r=self.stage();p=self.preview(r['id']);before=self.doc()
  for patch in ({'confirmed':False},{'confirmed':'true'},{'preview_token':'forged'}):
   with self.assertRaises(Problem):self.confirm(p,**patch)
   self.assertEqual(before,self.doc())
  self.confirm(p);self.assertEqual(len(self.store.snapshot()['feed_orders']),1);self.assertEqual(self.draft(r['id'])['status'],'confirmed')
 def test_mixed_dates_save_together_and_retry_does_not_double_count(self):
  p=self.preview(self.stage(self.payload([self.record(),self.record(date='2026-10-21',kg=3000)]))['id']);key=str(uuid.uuid4());result=self.confirm(p,key=key);before=self.doc();retry=self.confirm(p,key=key);self.assertEqual(result['confirmed_ids'],retry['confirmed_ids']);self.assertEqual(before,self.doc());self.assertEqual(sum(o['kg'] for o in self.store.snapshot()['feed_orders']),5000)
  with self.assertRaises(Problem):self.confirm(p)
 def test_existing_order_updates_only_after_confirmation_and_preserves_allocations(self):
  old=self.add('feed_orders',**self.record(kg=4000,note='original note',target_batch_ids=[self.batch['id']],bin_allocations=[{'batch_id':self.batch['id'],'kg':4000}]))
  r=self.stage(self.payload([self.record(kg=4000,item='大豬料')]));p=self.preview(r['id']);self.assertEqual(p['rows'][0]['decision'],'update');self.assertEqual(self.store.snapshot()['feed_orders'][0]['item'],'仔豬料');self.confirm(p);saved=self.store.snapshot()['feed_orders'][0];self.assertEqual(saved['id'],old['id']);self.assertEqual(saved['bin_allocations'],old['bin_allocations']);self.assertIn('original note',saved['note']);self.assertEqual(saved['item'],'大豬料')
 def test_changed_quantity_cannot_silently_change_previously_confirmed_split(self):
  old=self.add('feed_orders',**self.record(target_batch_ids=[self.batch['id']],bin_allocations=[{'batch_id':self.batch['id'],'kg':2000}]))
  r=self.stage(self.payload([self.record(kg=4000)]));p=self.preview(r['id']);self.assertFalse(p['can_confirm']);self.assertIn('allocation_total_mismatch',p['rows'][0]['errors']);before=self.doc()
  with self.assertRaises(Problem):self.confirm(p)
  self.assertEqual(before,self.doc())
 def test_cancel_is_persistent_and_cannot_confirm_later(self):
  r=self.stage();finish_draft(self.store,self.admin,r['id'],{'revision':r['revision']},str(uuid.uuid4()),cancel=True);self.assertEqual(self.draft(r['id'])['status'],'cancelled');self.assertFalse(self.store.snapshot()['feed_orders'])
  with self.assertRaises(Problem):self.preview(r['id'])
 def test_incomplete_rows_can_be_staged_but_never_confirmed(self):
  r=self.stage(self.payload([self.record(date='',kg=None,item='')]));p=self.preview(r['id']);self.assertFalse(p['can_confirm']);before=self.doc()
  with self.assertRaises(Problem):self.confirm(p)
  self.assertEqual(before,self.doc())
 def test_concurrent_order_or_draft_edit_invalidates_proof(self):
  r=self.stage();p=self.preview(r['id']);self.add('feed_orders',**self.record(target_batch_ids=[self.batch['id']]));before=self.doc()
  with self.assertRaises(Problem):self.confirm(p)
  self.assertEqual(before,self.doc());p=self.preview(r['id']);body=self.payload([self.record(kg=3000)]);body['revision']=r['revision'];self.stage(body,rid=r['id']);before=self.doc()
  with self.assertRaises(Problem):self.confirm(p)
  self.assertEqual(before,self.doc())
 def test_duplicate_rows_need_explicit_another_order_and_cannot_update_one_twice(self):
  payload=self.payload([self.record(),self.record()]);r=self.stage(payload);p=self.preview(r['id']);self.assertFalse(p['can_confirm']);self.assertFalse(self.store.snapshot()['feed_orders'])
  for row in payload['draft']['rows']:row['choice']='create'
  payload['revision']=r['revision'];self.stage(payload,rid=r['id']);self.confirm(self.preview(r['id']));self.assertEqual(len(self.store.snapshot()['feed_orders']),2)
  self.store.mutate(self.admin,'feed_orders',{'revision':1},str(uuid.uuid4()),self.store.snapshot()['feed_orders'][1]['id'],delete=True)
  # Voided same-day records require a conscious alternative, not automatic restoration.
  p=self.preview(self.stage(self.payload())['id']);self.assertFalse(p['can_confirm'])
 def test_viewer_foreign_staff_and_generic_mutations_cannot_bypass_review(self):
  with self.assertRaises(Problem):self.stage(user=self.viewer)
  r=self.stage()
  for fn in (lambda:self.preview(r['id'],self.staff),lambda:finish_draft(self.store,self.staff,r['id'],{'revision':1},str(uuid.uuid4()),cancel=True),lambda:self.store.mutate(self.admin,'feed_drafts',{'status':'confirmed'},str(uuid.uuid4()))):
   with self.assertRaises(Problem):fn()
  own=self.stage(user=self.staff);self.confirm(self.preview(own['id'],self.staff),user=self.staff);self.assertEqual(self.store.snapshot()['feed_orders'][0]['created_by'],self.staff['id'])
 def test_staff_cannot_use_draft_to_overwrite_an_admin_order(self):
  self.add('feed_orders',**self.record(target_batch_ids=[self.batch['id']]));p=self.preview(self.stage(user=self.staff)['id'],self.staff);self.assertFalse(p['can_confirm']);self.assertIn('feed_draft_admin_required',p['rows'][0]['errors'])
 def test_direct_confirmed_status_is_rejected_and_stage_retry_is_idempotent(self):
  payload=self.payload();key=str(uuid.uuid4());first=self.stage(payload,key=key);before=self.doc();self.assertEqual(self.stage(payload,key=key),{k:v for k,v in first.items() if not k.startswith('_')});self.assertEqual(before,self.doc());payload['draft']['status']='confirmed'
  with self.assertRaises(Problem):self.stage(payload)
 def test_backup_restore_retains_pending_and_confirmed_states(self):
  pending=self.stage();done=self.stage(self.payload([self.record(date='2026-10-21')]));self.confirm(self.preview(done['id']));backup=self.store.export_backup();other=Store(Path(self.tmp.name)/'restore');owner=other.create_user('restore','83000014');other.import_backup(owner,backup);states={d['id']:d['status'] for d in other.snapshot()['feed_drafts']};self.assertEqual(states,{pending['id']:'pending',done['id']:'confirmed'});self.assertEqual(len(other.snapshot()['feed_orders']),1)
 def test_operator_script_stages_deterministically_and_never_confirms(self):
  from scripts.stage_feed_photos import stage
  doc={'title':'相片先核對','sources':[{'name':'example.jpg'}],'rows':[{'date':'2026-10-20','bin':'13','vendor':'新農科','item':'仔豬料','tons':2,'note':'原圖文字'}]}
  first=stage(self.store,self.admin,doc);second=stage(self.store,self.admin,doc);self.assertEqual(first,second);self.assertEqual(first['status'],'pending');self.assertFalse(first['feed_orders_written']);self.assertFalse(self.store.snapshot()['feed_orders']);self.assertEqual(len(self.store.snapshot()['feed_drafts']),1)
 def test_atomic_validation_failure_leaves_no_partial_feed(self):
  records=[self.record(),self.record(date='2026-10-21',feed_bin_id='missing')];p=self.preview(self.stage(self.payload(records))['id']);before=self.doc()
  with self.assertRaises(Problem):self.confirm(p)
  self.assertEqual(before,self.doc());self.assertFalse(self.store.snapshot()['feed_orders'])

class CloudFeedDraftTests(FeedDraftTests):
 def setUp(self):
  super().setUp();self.local=self.store;self.fixture=HranaFixture(Path(self.tmp.name)/'remote');self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.local,self.store)
 def tearDown(self):self.fixture.close();super().tearDown()
