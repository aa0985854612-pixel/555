"""Whole-source assignment changes attribution, never books a second movement."""
import unittest,tempfile,uuid,base64,io,copy,json
from pathlib import Path
from zipfile import ZipFile
from app.store import Store,Problem
from app.history import source_history
from app.source_assignment import identity
from app.domain import herd
from app.operations import void_preview,void_record
from legacy_fixture import workbook_fixture

def unassigned_fixture():
 out=io.BytesIO()
 with ZipFile(io.BytesIO(workbook_fixture())) as old,ZipFile(out,'w') as new:
  for name in old.namelist():new.writestr(name,old.read(name).replace(b'10/11\xe6\xad\xbb1\xe9\xa0\xad(1\xe6\xa3\x9f)',b'10/11\xe6\xad\xbb1\xe9\xa0\xad') if name=='xl/comments1.xml' else old.read(name))
 return out.getvalue()

class SourceAssignmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('worker','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
  self.store.import_workbook(self.admin,{'filename':'test.xlsx','base64':base64.b64encode(unassigned_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/49\n2/50'},str(uuid.uuid4()))
  self.batches=self.store.snapshot()['batches'];self.target=next(b for b in self.batches if b['legacy_barn']==1);self.record=next(r for r in source_history(self.store.snapshot()) if r.get('date')=='2026-10-11');self.review=identity(self.record)|{'reason':'使用者確認死亡歸屬1棟'}
 def tearDown(self):self.tmp.cleanup()
 def assign(self,review=None,user=None,key=None):return self.store.mutate(user or self.admin,'batches',self.target|{'source_assignments':[review or self.review]},key or str(uuid.uuid4()),self.target['id'])
 def test_assignment_preserves_source_id_and_farm_totals(self):
  d=self.store.snapshot();farm=herd(d['batches'],d['movements'],'2026-10-15');heads={b['id']:herd(d['batches'],d['movements'],'2026-10-15',[b['id']])['remaining'] for b in d['batches']};books=copy.deepcopy(d['workbooks']);self.assign();after=self.store.snapshot();r=next(r for r in source_history(after) if r['id']==self.record['id'])
  self.assertEqual(r['batch_id'],self.target['id']);self.assertEqual(r['quantity'],1);self.assertEqual(r['date'],'2026-10-11');self.assertIn('使用者確認',r['note']);self.assertEqual(after['workbooks'],books);self.assertEqual(herd(after['batches'],after['movements'],'2026-10-15'),farm);self.assertEqual(after['movements'],d['movements'])
  for b in after['batches']:self.assertEqual(herd(after['batches'],after['movements'],'2026-10-15',[b['id']])['remaining'],heads[b['id']])
 def test_baseline_deaths_become_known_without_stock_reallocation(self):
  self.assign();d=self.store.snapshot();counts={b['legacy_barn']:herd(d['batches'],d['movements'],'2026-10-14',[b['id']])['dead'] for b in d['batches']};self.assertEqual(counts,{1:1,2:3})
 def test_idempotent_retry_and_old_client_edit_preserve_review(self):
  key=str(uuid.uuid4());a=self.assign(key=key);b=self.assign(key=key);self.assertEqual(a,b)
  payload={k:v for k,v in a.items() if k!='source_assignments'};edited=self.store.mutate(self.admin,'batches',payload,str(uuid.uuid4()),a['id']);self.assertEqual(edited['source_assignments'],[self.review]);self.assertEqual(len([r for r in source_history(self.store.snapshot()) if r['id']==self.record['id']]),1)
 def test_roles_and_stale_revisions_rejected(self):
  for u in (self.staff,self.viewer):
   with self.assertRaises(Problem) as e:self.assign(user=u)
   self.assertEqual(e.exception.status,403)
  self.assign()
  with self.assertRaises(Problem) as e:self.assign()
  self.assertEqual(e.exception.status,409)
 def test_forged_date_quantity_source_and_reason_rejected(self):
  for patch in ({'quantity':2},{'quantity':True},{'source_row_id':[]},{'date':'2026-10-12'},{'source_row_id':str(uuid.uuid4())},{'reason':''},{'cohort':'OTHER'}):
   with self.assertRaises(Problem):self.assign(self.review|patch)
 def test_different_batch_and_duplicate_assignment_rejected(self):
  self.assign();other=next(b for b in self.store.snapshot()['batches'] if b['id']!=self.target['id'])
  with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',other|{'source_assignments':[self.review]},str(uuid.uuid4()),other['id'])
 def test_backup_restore_retains_assignment_and_source(self):
  self.assign();clone=Store(Path(self.tmp.name)/'restore');doc=self.store.export_backup();clone.import_backup(self.admin,doc);clone.import_backup(self.admin,doc);rows=source_history(clone.snapshot());self.assertEqual(next(r for r in rows if r['id']==self.record['id'])['batch_id'],self.target['id'])
 def test_void_then_reimported_explicit_allocation_stays_void(self):
  self.assign();d=self.store.snapshot();p=void_preview(self.store,self.admin,d,'movements',self.record['id']);void_record(self.store,self.admin,{'kind':'movements','id':self.record['id'],'reason':'test','preview_token':p['preview_token']},str(uuid.uuid4()));d=self.store.snapshot();self.assertNotIn(self.record['id'],[r['id'] for r in source_history(d)])
  for book in d['workbooks']:
   for row in book['report']['rows']:
    for event in row['events']:
     if event.get('date')=='2026-10-11':event['allocations']=[{'barn':1,'quantity':1}]
  self.assertFalse(any(r.get('date')=='2026-10-11' for r in source_history(d)))

 def complete_stock_basis(self):
  raw=source_history(self.store.snapshot());reviews=[identity(r)|{'reason':'confirmed fixture'} for r in raw if not r.get('batch_id')]
  for old in self.store.snapshot()['batches']:
   patch=old|{'entry_count':50,'entry_count_source':'confirmed fixture','stock_basis':{'mode':'entry_minus_source_outflows','reason':'confirmed no transfers'}}
   if old['id']==self.target['id']:patch['source_assignments']=reviews
   self.store.mutate(self.admin,'batches',patch,str(uuid.uuid4()),old['id'])
 def test_complete_source_rebuilds_only_split_and_preserves_totals(self):
  before=self.store.snapshot();total=herd(before['batches'],before['movements'],'2026-10-14');self.complete_stock_basis();d=self.store.snapshot()
  self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14'),total);heads={b['legacy_barn']:herd(d['batches'],d['movements'],'2026-10-14',[b['id']])['remaining'] for b in d['batches']};self.assertEqual(heads,{1:43,2:47});self.assertFalse(any(b.get('legacy_stock_pending') for b in d['batches']))
  self.assertEqual(self.store.snapshot()['batches'],d['batches'])
 def test_incomplete_source_does_not_rebuild(self):
  self.assign();before=self.store.snapshot();old=before['batches'][0];self.store.mutate(self.admin,'batches',old|{'stock_basis':{'mode':'entry_minus_source_outflows','reason':'test'}},str(uuid.uuid4()),old['id']);after=self.store.snapshot();self.assertTrue(next(b for b in after['batches'] if b['id']==old['id'])['legacy_stock_pending']);self.assertEqual(herd(before['batches'],before['movements'],'2026-10-14'),herd(after['batches'],after['movements'],'2026-10-14'))
 def test_conflicting_group_entry_total_keeps_original_stock(self):
  self.complete_stock_basis();d=self.store.snapshot();b=d['batches'][0]
  with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',b|{'entry_count':49},str(uuid.uuid4()),b['id'])
  d['batches'][0]['entry_count']=49;self.store.enrich_legacy(d);self.assertTrue(all(b.get('legacy_stock_pending') for b in d['batches']))
 def test_stock_basis_survives_old_client_and_backup(self):
  self.complete_stock_basis();b=self.store.snapshot()['batches'][0];payload={k:v for k,v in b.items() if k not in ('stock_basis','source_assignments')};self.store.mutate(self.admin,'batches',payload,str(uuid.uuid4()),b['id']);self.assertEqual(self.store.snapshot()['batches'][0]['stock_basis'],b['stock_basis']);clone=Store(Path(self.tmp.name)/'stock-restore');clone.import_backup(self.admin,self.store.export_backup());self.assertEqual(herd(clone.snapshot()['batches'],clone.snapshot()['movements'],'2026-10-14',[b['id']])['remaining'],herd(self.store.snapshot()['batches'],self.store.snapshot()['movements'],'2026-10-14',[b['id']])['remaining'])
 def test_invalid_stock_basis_rejected(self):
  for basis in ({'mode':'guess','reason':'x'},{'mode':'entry_minus_source_outflows','reason':''},True):
   with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',self.target|{'stock_basis':basis},str(uuid.uuid4()),self.target['id'])

class CloudSourceAssignmentTests(SourceAssignmentTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
