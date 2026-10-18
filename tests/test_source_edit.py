"""Imported edits preserve source bytes, identities, stock and split siblings."""
import unittest,tempfile,base64,uuid,copy
from pathlib import Path
from app.store import Store,Problem
from app.source_edit import preview,save,duplicate_token
from app.history import source_history
from app.domain import herd,Invalid
from app.operations import void_preview,void_record
from test_source_assignment import unassigned_fixture

class SourceEditTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.viewer=self.store.create_user('viewer','83000012','viewer')
  self.store.import_workbook(self.admin,{'filename':'test.xlsx','base64':base64.b64encode(unassigned_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/49\n2/50'},str(uuid.uuid4()))
 def tearDown(self):self.tmp.cleanup()
 def row(self,typ='death',on='2026-10-14'):
  return next(r for r in source_history(self.store.snapshot()) if r['type']==typ and r['date']==on)
 def request(self,row=None,**changes):
  row=row or self.row();return {'id':row['id'],'date':row['date'],'quantity':row['quantity'],'batch_id':row['batch_id'],'note':row['note'],'outgoing_destination':row.get('outgoing_destination',''),'reason':'核對紙本後更正'}|changes
 def apply(self,payload,key=None):
  p=preview(self.store,self.admin,payload);return save(self.store,self.admin,payload|{'preview_token':p['preview_token']},key or str(uuid.uuid4()))
 def test_quantity_date_destination_and_id_preserve_original_and_stock_once(self):
  row=self.row('sale');before=self.store.snapshot();p=self.request(row,date='2026-10-13',quantity=3,outgoing_destination='新北');self.apply(p);after=self.store.snapshot();r=next(r for r in source_history(after) if r['id']==row['id']);self.assertEqual((r['date'],r['quantity'],r['outgoing_destination']),('2026-10-13',3,'新北'))
  for field in ('base64','report','plan','sha256'):self.assertEqual(before['workbooks'][0][field],after['workbooks'][0][field])
  self.assertEqual(herd(after['batches'],after['movements'],'2026-10-15')['remaining'],herd(before['batches'],before['movements'],'2026-10-15')['remaining']-1)
  self.store.enrich_legacy(after);self.store.enrich_legacy(after);self.assertEqual(herd(after['batches'],after['movements'],'2026-10-15')['remaining'],herd(before['batches'],before['movements'],'2026-10-15')['remaining']-1)
  self.apply(self.request(r,date=row['date'],quantity=row['quantity'],outgoing_destination=''));d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15'),herd(before['batches'],before['movements'],'2026-10-15'))
 def test_move_across_baseline_and_barns_updates_each_balance(self):
  before=self.store.snapshot();row=self.row();old=row['batch_id'];new=next(b['id'] for b in before['batches'] if b['id']!=old);self.apply(self.request(row,date='2026-10-12',batch_id=new,quantity=1));after=self.store.snapshot()
  for bid,delta in ((old,2),(new,-1)):
   self.assertEqual(herd(after['batches'],after['movements'],'2026-10-15',[bid])['remaining'],herd(before['batches'],before['movements'],'2026-10-15',[bid])['remaining']+delta)
  self.assertEqual(herd(after['batches'],after['movements'],'2026-10-12',[new])['remaining'],herd(before['batches'],before['movements'],'2026-10-12',[new])['remaining']-1)
 def test_unknown_barn_assignment_does_not_guess_old_stock(self):
  row=self.row('death','2026-10-11');target=self.store.snapshot()['batches'][0]['id'];self.apply(self.request(row,batch_id=target));d=self.store.snapshot();r=next(r for r in source_history(d) if r['id']==row['id']);self.assertEqual(r['batch_id'],target);self.assertTrue(all(b['legacy_heads']['2026-10-12'] is None for b in d['batches']))
 def test_idempotency_revision_role_validation(self):
  p=self.request();pre=preview(self.store,self.admin,p);payload=p|{'preview_token':pre['preview_token']};key=str(uuid.uuid4());save(self.store,self.admin,payload,key);before=self.store.export_backup()['records'];save(self.store,self.admin,payload,key);self.assertEqual(before,self.store.export_backup()['records'])
  with self.assertRaises(Problem):save(self.store,self.admin,payload,str(uuid.uuid4()))
  with self.assertRaises(Problem):preview(self.store,self.viewer,p)
  for change in ({'quantity':0},{'quantity':True},{'quantity':1000001},{'date':'bad'},{'date':'2025-01-01'},{'batch_id':str(uuid.uuid4())},{'reason':''},{'outgoing_destination':'新北'}):
   with self.assertRaises((Problem,Invalid,ValueError)):preview(self.store,self.admin,p|change)
 def test_split_part_edits_do_not_change_sibling_or_source_date_review(self):
  from app.source_dates import identity
  from app.store import encode
  import json
  raw=self.row();db=self.store.connect();book=json.loads(db.execute("SELECT data FROM records WHERE kind='workbooks'").fetchone()['data']);review=identity(raw)|{'parts':[{'date':'2026-10-14','quantity':1,'note':'棟內'},{'date':'2026-10-13','quantity':1,'note':'市場'}],'reason':'分開核對'};book['source_date_reviews']=[review];db.execute('UPDATE records SET data=? WHERE id=?',(encode(book),book['id']));db.commit();db.close()
  parts=[r for r in source_history(self.store.snapshot()) if r.get('source_original_id')==raw['id']];child=parts[1];self.apply(self.request(child,date='2026-10-12',quantity=2));after=self.store.snapshot();now=[r for r in source_history(after) if r.get('source_original_id')==raw['id']];self.assertEqual(now[0],parts[0]);self.assertEqual((now[1]['id'],now[1]['quantity'],now[1]['date']),(child['id'],2,'2026-10-12'));self.assertEqual(after['workbooks'][0]['source_date_reviews'],[review]);self.store.enrich_legacy(after);self.assertEqual([r for r in source_history(after) if r.get('source_original_id')==raw['id']],now)
 def test_unassigning_old_known_event_makes_barn_totals_unknown_not_zero(self):
  row=self.row();self.apply(self.request(row,date='2026-10-12',batch_id=None));d=self.store.snapshot();self.assertTrue(all(b['legacy_values']['2026-10-12']['dead'] is None for b in d['batches']));self.assertTrue(all(b['legacy_heads']['2026-10-12'] is None for b in d['batches']))
 def test_source_preview_does_not_write_and_stale_confirmation_rejects(self):
  before=self.store.export_backup()['records'];p=self.request();result=preview(self.store,self.admin,p);self.assertEqual(before,self.store.export_backup()['records']);self.assertEqual(len(result['impact']['barns']),2)
  barn=self.store.snapshot()['barns'][0];self.store.mutate(self.admin,'barns',barn|{'group':'changed'},str(uuid.uuid4()),barn['id'])
  with self.assertRaises(Problem) as e:save(self.store,self.admin,p|{'preview_token':result['preview_token']},str(uuid.uuid4()))
  self.assertEqual(e.exception.code,'revision_conflict')
 def test_void_edited_record_and_backup_restore(self):
  row=self.row();self.apply(self.request(row,quantity=1));d=self.store.snapshot();base=herd(d['batches'],d['movements'],'2026-10-15')['remaining'];p=void_preview(self.store,self.admin,d,'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'reason':'作廢','preview_token':p['preview_token']},str(uuid.uuid4()));d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],base+1)
  clone=Store(Path(self.tmp.name)/'restore');clone.import_backup(self.admin,self.store.export_backup());self.assertEqual(source_history(clone.snapshot()),source_history(d))
 def test_duplicate_against_source_requires_explicit_confirmation_and_excludes_self(self):
  self.apply(self.request(date='2026-10-15'))
  b=next(b for b in self.store.snapshot()['batches'] if b['id']==self.row(on='2026-10-15')['batch_id']);r={'date':'2026-10-15','batch_id':b['id'],'type':'death','quantity':2}
  with self.assertRaises(Problem) as e:self.store.mutate(self.admin,'movements',r,str(uuid.uuid4()))
  self.assertEqual(e.exception.code,'movement_duplicate')
  clean=self.store.validate('movements',r,self.store.snapshot(),self.admin);token=duplicate_token(self.store.snapshot(),clean);m=self.store.mutate(self.admin,'movements',r|{'duplicate_confirmation':token},str(uuid.uuid4()));self.assertNotIn('duplicate_confirmation',m)
  # Editing an unrelated property still warns about the other source event.
  with self.assertRaises(Problem):self.store.mutate(self.admin,'movements',m|{'note':'changed'},str(uuid.uuid4()),m['id'])

class CloudSourceEditTests(SourceEditTests):
 def setUp(self):
  super().setUp();from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
