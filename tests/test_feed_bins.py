"""Shared-bin totals never become invented per-barn feed consumption."""
import unittest,tempfile,uuid,copy
from pathlib import Path
from app.store import Store,Problem
from app.feed import initial_bins,order_scope,YANG_QUAN_BARNS
from app.server import filter_rows,statistics
from app.weekly import weekly_report
from app.domain import herd

class FeedBinTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('worker','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.barns=[self.add('barns',name=f'{n}棟') for n in (1,2,11)];self.batches=[self.add('batches',barn_id=b['id'],name='SAME' if i<2 else 'OTHER',entry_date='2026-10-01',entry_count=100,status='active',entry_age_days=70) for i,b in enumerate(self.barns)]
  self.bin=self.add('feed_bins',name='1、2',vendor='養全',barn_ids=[b['id'] for b in self.barns[:2]],active=True)
  self.dual=[self.add('feed_bins',name=f'11-{i}',vendor='新農科',barn_ids=[self.barns[2]['id']],active=True) for i in (1,2)]
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**d):return self.store.mutate(self.admin,kind,d,str(uuid.uuid4()))
 def body(self,**patch):return {'date':'2026-10-12','kg':2000,'display_unit':'ton','item':'大豬料','feed_bin_id':self.bin['id'],'target_batch_ids':[b['id'] for b in self.batches[:2]],'allocations':[]}|patch
 def order(self,**patch):return self.store.mutate(self.staff,'feed_orders',self.body(**patch),str(uuid.uuid4()))
 def report(self,**q):return weekly_report(self.store.snapshot(),{'cohort':['SAME|2026-10-01'],'from':['2026-10-01'],'to':['2026-10-15']}|{k:[v] for k,v in q.items()},today='2026-10-15')
 def test_confirmed_vendor_and_all_23_physical_bins(self):
  barns=[{'id':str(n),'name':f'{n}棟'} for n in range(1,25)];bins=initial_bins(barns);self.assertEqual(len(bins),23)
  self.assertEqual({int(id) for b in bins if b['vendor']=='養全' for id in b['barn_ids']},YANG_QUAN_BARNS)
  self.assertEqual({b['name'] for b in bins if b['barn_ids']==['11']},{'11-1','11-2'});self.assertEqual({b['name'] for b in bins if b['barn_ids']==['14']},{'14-1','14-2'});self.assertEqual({b['name'] for b in bins if b['barn_ids']==['15']},{'15-1','15-2'})
  for pair in (['1','2'],['3','4'],['5','6'],['16','17']):self.assertEqual(sum(b['barn_ids']==pair for b in bins),1)
 def test_three_types_and_default_vendor_snapshot_are_saved(self):
  for item in ('大豬料','仔豬料','哺乳二期料'):
   r=self.order(item=item);self.assertEqual(r['vendor'],'養全');self.assertEqual(r['item'],item);self.assertEqual(r['feed_bin_snapshot']['barn_names'],['1棟','2棟'])
  with self.assertRaises(Problem):self.order(item='虛構料別')
 def test_whole_cohort_and_farm_count_shared_order_only_once(self):
  self.order();data=self.store.snapshot();r=self.report();self.assertEqual(r['totals']['feed_orders'],2000);self.assertEqual(len([e for w in r['weeks'] for e in w['feed_details']]),1)
  self.assertEqual(statistics(data,{})['feed_order_kg'],2000);self.assertEqual(statistics(data,{'cohort':['SAME|2026-10-01']})['feed_order_kg'],2000);self.assertEqual(len(data['feed_orders']),1)
 def test_single_barn_shows_shared_reference_without_half_or_double_quantity(self):
  self.order();q={'barn_id':[self.barns[0]['id']]};data=self.store.snapshot();rows=filter_rows('feed_orders',data,q)
  self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['scope_attribution']['kg']);self.assertEqual(rows[0]['kg'],2000)
  r=self.report(barn_id=self.barns[0]['id']);self.assertIsNone(r['totals']['feed_orders']);self.assertEqual(r['known_totals']['feed_orders'],0);self.assertEqual(sum(e['kg'] for w in r['weeks'] for e in w['feed_shared_details']),2000)
  self.assertIsNone(statistics(data,q)['feed_order_kg'])
 def test_shared_bin_crossing_cohorts_is_not_fully_charged_to_each(self):
  b=self.store.mutate(self.admin,'batches',self.batches[1]|{'name':'OTHER-COHORT'},str(uuid.uuid4()),self.batches[1]['id']);self.order();r=self.report();self.assertIsNone(r['totals']['feed_orders']);self.assertEqual(r['known_totals']['feed_orders'],0)
  d=self.store.snapshot();self.assertEqual(order_scope(d['feed_orders'][0],d,None)['kg'],2000)
 def test_double_bins_are_separate_orders_but_one_barn_total(self):
  for bin in self.dual:self.order(feed_bin_id=bin['id'],target_batch_ids=[self.batches[2]['id']],item='仔豬料',kg=1000)
  d=self.store.snapshot();rows=filter_rows('feed_orders',d,{'barn_id':[self.barns[2]['id']]});self.assertEqual(len(rows),2);self.assertEqual(len(filter_rows('feed_orders',d,{'feed_bin_id':[self.dual[0]['id']]})),1);self.assertEqual(statistics(d,{'barn_id':[self.barns[2]['id']]})['feed_order_kg'],2000)
 def test_missing_targets_are_visible_pending_not_assigned_to_current_batch(self):
  self.order(target_batch_ids=[]);r=self.report();self.assertIsNone(r['totals']['feed_orders']);self.assertEqual(r['known_totals']['feed_orders'],0);self.assertTrue(any(p['reason']=='shared_bin_unallocated' for p in r['pending']))
 def test_assigned_old_batch_does_not_leak_into_new_batch(self):
  self.order();new=self.add('batches',barn_id=self.barns[0]['id'],name='NEW',entry_date='2026-10-10',entry_count=50,status='active');d=self.store.snapshot();self.assertEqual(filter_rows('feed_orders',d,{'batch_id':[new['id']]}),[])
 def test_invalid_target_or_duplicate_barn_allocations_are_rejected(self):
  for patch in ({'target_batch_ids':[self.batches[2]['id']]},{'target_batch_ids':[self.batches[0]['id']]*2},{'allocations':[{'batch_id':self.batches[0]['id'],'kg':2000}]}):
   with self.assertRaises(Problem):self.order(**patch)
 def test_client_cannot_forge_or_rewrite_saved_snapshot(self):
  r=self.order(feed_bin_snapshot={'name':'fake'});self.assertEqual(r['feed_bin_snapshot']['name'],'1、2')
  r2=self.store.mutate(self.staff,'feed_orders',self.body(feed_bin_snapshot={'name':'fake'},revision=r['revision'],vendor='養全'),str(uuid.uuid4()),r['id']);self.assertEqual(r2['feed_bin_snapshot'],r['feed_bin_snapshot'])
 def test_bin_members_locked_with_orders_but_vendor_changes_do_not_relabel_history(self):
  r=self.order();edited=self.store.mutate(self.admin,'feed_bins',self.bin|{'vendor':'新農科','name':'1/2共桶'},str(uuid.uuid4()),self.bin['id'])
  old=self.store.snapshot()['feed_orders'][0];self.assertEqual(old['vendor'],'養全');self.assertEqual(old['feed_bin_snapshot']['name'],'1、2')
  with self.assertRaises(Problem):self.store.mutate(self.admin,'feed_bins',edited|{'barn_ids':[self.barns[0]['id']]},str(uuid.uuid4()),edited['id'])
 def test_permissions_and_revision_conflicts(self):
  for u in (self.staff,self.viewer):
   with self.assertRaises(Problem) as e:self.store.mutate(u,'feed_bins',{'name':'X'},str(uuid.uuid4()))
   self.assertEqual(e.exception.status,403)
  with self.assertRaises(Problem):self.store.mutate(self.viewer,'feed_orders',self.body(),str(uuid.uuid4()))
  r=self.order();self.store.mutate(self.staff,'feed_orders',self.body(revision=r['revision'],kg=2500),str(uuid.uuid4()),r['id'])
  with self.assertRaises(Problem):self.store.mutate(self.staff,'feed_orders',self.body(revision=r['revision']),str(uuid.uuid4()),r['id'])
 def test_idempotency_and_backup_restore_preserve_shared_scope(self):
  key=str(uuid.uuid4());r=self.store.mutate(self.staff,'feed_orders',self.body(),key);self.assertEqual(self.store.mutate(self.staff,'feed_orders',self.body(),key)['id'],r['id'])
  doc=self.store.export_backup();clone=Store(Path(self.tmp.name)/'restore');clone.import_backup(self.admin,doc);clone.import_backup(self.admin,doc);self.assertEqual(len(clone.snapshot()['feed_orders']),1);self.assertEqual(len(clone.snapshot()['feed_bins']),3)
 def test_orders_leave_herd_receipts_and_actual_consumption_unchanged(self):
  d=self.store.snapshot();before=herd(d['batches'],d['movements'],'2026-10-15');self.order();d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15'),before);self.assertEqual(d['deliveries'],[]);self.assertEqual(d['usages'],[])
 def test_report_header_has_configured_supplier_and_actual_recorded_types(self):
  self.order(item='哺乳二期料');setup=self.report()['feed_setup'];self.assertEqual(setup['configured_vendors'],['養全']);self.assertEqual(setup['recorded_types'],['哺乳二期料']);self.assertEqual(setup['recorded_vendors'],['養全'])
 def test_barn_vendor_setting_and_old_clients_preserve_default(self):
  b=self.barns[0];updated=self.store.mutate(self.admin,'barns',b|{'feed_vendor':'新農科'},str(uuid.uuid4()),b['id'])
  oldclient=self.store.mutate(self.admin,'barns',{'name':b['name'],'group':'test','revision':updated['revision']},str(uuid.uuid4()),b['id'])
  self.assertEqual(oldclient['feed_vendor'],'新農科')
  with self.assertRaises(Problem) as conflict:self.store.mutate(self.admin,'barns',updated|{'feed_vendor':'養全'},str(uuid.uuid4()),b['id'])
  self.assertEqual(conflict.exception.status,409)
 def test_barn_supplier_is_validated_and_admin_only(self):
  b=self.barns[0]
  for invalid in ('other',None,[],1):
   with self.assertRaises(Problem):self.store.mutate(self.admin,'barns',b|{'feed_vendor':invalid},str(uuid.uuid4()),b['id'])
  for user in (self.staff,self.viewer):
   with self.assertRaises(Problem) as denied:self.store.mutate(user,'barns',b|{'feed_vendor':'養全'},str(uuid.uuid4()),b['id'])
   self.assertEqual(denied.exception.status,403)
 def test_changing_barn_supplier_preserves_order_and_other_barn(self):
  old=self.order();b=self.barns[0];self.store.mutate(self.admin,'barns',b|{'feed_vendor':'新農科'},str(uuid.uuid4()),b['id'])
  data=self.store.snapshot();self.assertEqual(data['feed_orders'][0],old);self.assertEqual(data['barns'][1],self.barns[1]);self.assertEqual(data['feed_bins'][0],self.bin)
  self.assertEqual(self.report()['feed_setup']['recorded_vendors'],['養全'])
  self.assertEqual(self.report(barn_id=b['id'])['feed_setup']['configured_vendors'],['新農科'])
 def test_backup_with_and_without_barn_supplier_is_roundtrippable(self):
  b=self.barns[0];self.store.mutate(self.admin,'barns',b|{'feed_vendor':'養全'},str(uuid.uuid4()),b['id'])
  doc=self.store.export_backup();clone=Store(Path(self.tmp.name)/'barn-restore');clone.import_backup(self.admin,doc)
  self.assertEqual({b['id']:b.get('feed_vendor') for b in clone.snapshot()['barns']},{b['id']:b.get('feed_vendor') for b in self.store.snapshot()['barns']})
 def test_legacy_orders_without_bins_keep_original_free_text_and_scope(self):
  old=self.add('feed_orders',date='2026-10-12',kg=500,display_unit='kg',vendor='新農科',item='舊來源料名',allocations=[{'batch_id':self.batches[0]['id'],'kg':500}]);self.order();self.assertEqual(self.store.snapshot()['feed_orders'][0]['item'],'舊來源料名');self.assertEqual(self.report()['totals']['feed_orders'],2500)

class CloudFeedBinTests(FeedBinTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
