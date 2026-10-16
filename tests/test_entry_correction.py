"""Entry corrections use synthetic source data, never the production herd."""
import base64,copy,io,json,tempfile,unittest,uuid
from pathlib import Path
from zipfile import ZipFile
from app.store import Store,Problem
from app.domain import herd
from app.history import source_history
from app.operations import void_preview,void_record
from legacy_fixture import workbook_fixture


def single_barn_workbook():
 out=io.BytesIO()
 with ZipFile(io.BytesIO(workbook_fixture())) as src,ZipFile(out,'w') as dst:
  for name in src.namelist():
   raw=src.read(name)
   if name.endswith('sheet1.xml'):raw=raw.decode().replace('第1.2棟','第15棟').encode()
   if name.endswith('comments1.xml'):raw=raw.decode().replace('(1棟)','(15棟)').replace('(2棟)','(15棟)').encode()
   dst.writestr(name,raw)
 return out.getvalue()

class EntryCorrectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
  self.admin=self.store.create_user('owner','synthetic-owner-password')
  self.payload={'filename':'synthetic.xlsx','base64':base64.b64encode(single_barn_workbook()).decode(),'counts_as_of':'2026-10-12','counts_text':'15/99'}
  self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))
 def tearDown(self):self.tmp.cleanup()
 def batch(self):return self.store.snapshot()['batches'][0]
 def change(self,count,reason='verified actual entry',key=None,batch=None,user=None):
  b=batch or self.batch();return self.store.mutate(user or self.admin,'batches',b|{'entry_count':count,'entry_count_reason':reason},key or str(uuid.uuid4()),b['id'])
 def stats(self,on='2026-10-14'):
  d=self.store.snapshot();return herd(d['batches'],d['movements'],on)
 def test_correction_recalculates_entry_balance_survival_and_keeps_exits(self):
  before=self.stats();self.change(120);after=self.stats()
  self.assertEqual(after['entry'],120);self.assertEqual(after['remaining'],before['remaining']+20)
  self.assertAlmostEqual(after['survival'],(120-after['dead'])/120*100)
  for k in ('sold','culled','dead','added','adjustment'):self.assertEqual(before[k],after[k])
  self.change(95);self.assertEqual(self.stats()['remaining'],before['remaining']-5)
 def test_repeated_enrichment_and_history_dates_apply_delta_once(self):
  earlier=self.stats('2026-10-12');self.change(120);d=self.store.snapshot()
  for _ in range(3):self.store.enrich_legacy(d)
  self.assertEqual(herd(d['batches'],d['movements'],'2026-10-12')['remaining'],earlier['remaining']+20)
  self.assertEqual(self.stats('2026-09-08')['entry'],0)
 def test_requires_reason_even_when_restoring_original_count(self):
  with self.assertRaises(Problem):self.change(120,reason=' ')
  self.change(120)
  with self.assertRaises(Problem):self.change(100,reason='')
  self.assertEqual(self.batch()['entry_count'],120)
 def test_negative_fractional_blank_and_impossible_counts_are_rejected(self):
  for count in (-1,1.5,None,0,5):
   with self.subTest(count=count),self.assertRaises(Problem):self.change(count)
  self.assertEqual(self.batch()['entry_count'],100)
 def test_server_roles_are_enforced(self):
  for role in ('staff','viewer'):
   user=self.store.create_user(role,'synthetic-role-password',role)
   with self.assertRaises(Problem) as e:self.change(120,user=user)
   self.assertEqual(e.exception.status,403)
 def test_retry_is_idempotent_and_stale_revision_conflicts(self):
  old=self.batch();key=str(uuid.uuid4());a=self.change(120,key=key,batch=old)
  self.assertEqual(a,self.change(120,key=key,batch=old))
  with self.assertRaises(Problem) as e:self.change(130,batch=old)
  self.assertEqual(e.exception.status,409);self.assertEqual(self.batch()['entry_count'],120)
 def test_original_source_and_unrelated_fields_preserved_with_audit(self):
  original=copy.deepcopy(self.store.snapshot());self.change(120)
  d=self.store.snapshot();self.assertEqual(d['workbooks'],original['workbooks']);self.assertEqual(d['movements'],original['movements'])
  db=self.store.connect();event=db.execute("SELECT * FROM audit WHERE kind='batches' AND action='update' ORDER BY seq DESC").fetchone();db.close()
  self.assertEqual(json.loads(event['before_value'])['entry_count'],100)
  self.assertEqual(json.loads(event['after_value'])['entry_count'],120)
  self.assertEqual(json.loads(event['after_value'])['entry_count_reason'],'verified actual entry')
 def test_reimport_and_backup_restore_keep_correction(self):
  self.change(120);self.assertTrue(self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))['already_imported'])
  clone=Store(Path(self.tmp.name)/'restored');clone.import_backup(self.admin,self.store.export_backup())
  d=clone.snapshot();self.assertEqual(d['batches'][0]['entry_count'],120);self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14'),self.stats())
 def test_source_void_and_correction_do_not_double_adjust(self):
  self.change(120);before=self.stats();d=self.store.snapshot();row=next(r for r in source_history(d) if r['type']=='death' and r.get('batch_id'))
  p=void_preview(self.store,self.admin,d,'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'duplicate'},str(uuid.uuid4()))
  self.assertEqual(self.stats()['remaining'],before['remaining']+row['quantity']);self.assertEqual(self.stats()['entry'],120)
 def test_future_movements_cannot_become_negative_after_correction(self):
  b=self.batch();self.store.mutate(self.admin,'movements',{'batch_id':b['id'],'date':'2026-10-15','type':'sale','quantity':85},str(uuid.uuid4()))
  with self.assertRaises(Problem):self.change(90)
  self.assertEqual(self.batch()['entry_count'],100)
 def test_source_reference_cannot_be_removed_to_bypass_validation(self):
  b=self.batch()
  with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',b|{'legacy_source':None,'entry_count':120},str(uuid.uuid4()),b['id'])
 def test_unrelated_batch_edit_preserves_correction_reason(self):
  self.change(120);b=self.batch();self.store.mutate(self.admin,'batches',b|{'group':'new group','entry_count_reason':''},str(uuid.uuid4()),b['id'])
  self.assertEqual(self.batch()['entry_count_reason'],'verified actual entry');self.assertEqual(self.stats()['entry'],120)
