"""Date corrections preserve imported quantities, source IDs and real barn assignments."""
import unittest,tempfile,uuid,base64,copy,json
from pathlib import Path
from app.store import Store,encode,Problem
from app.history import source_history
from app.source_dates import identity
from app.domain import herd
from app.weekly import weekly_report
from app.operations import void_preview,void_record
from app.source_assignment import identity as assignment_identity
from legacy_fixture import workbook_fixture
from test_source_assignment import unassigned_fixture

class SourceDateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011')
  self.store.import_workbook(self.admin,{'filename':'test.xlsx','base64':base64.b64encode(unassigned_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/49\n2/50'},str(uuid.uuid4()))
 def tearDown(self):self.tmp.cleanup()
 def original(self,typ='sale',date='2026-10-14'):
  return next(r for r in source_history(self.store.snapshot(),apply_date_reviews=False) if r['type']==typ and r['date']==date)
 def review(self,row=None,on='2026-10-13',**patch):
  r=row or self.original();return identity(r)|{'parts':[{'date':on,'quantity':r['quantity'],'note':on[5:].replace('-','/')+' 核對後紀錄'+str(r['quantity'])}], 'reason':'使用者確認新北星期二出豬'}|patch
 def save(self,review):
  db=self.store.connect()
  try:
   db.execute('BEGIN IMMEDIATE');stored=db.execute("SELECT id,data FROM records WHERE kind='workbooks'").fetchone();book=json.loads(stored['data']);book['source_date_reviews']=[review];book['revision']+=1
   db.execute('UPDATE records SET data=?,revision=? WHERE id=?',(encode(book),book['revision'],book['id']));self.store.validate_global(self.store.snapshot(db));db.commit()
  finally:db.close()
 def test_wednesday_sale_becomes_tuesday_without_changing_id_quantity_or_cull(self):
  before=self.store.snapshot();row=self.original();books=copy.deepcopy(before['workbooks']);review=self.review();review['parts'][0]['outgoing_destination']='新北';self.save(review);after=self.store.snapshot();r=next(r for r in source_history(after) if r['id']==row['id'])
  self.assertEqual((r['date'],r['quantity'],r['outgoing_destination']),('2026-10-13',2,'新北'));self.assertEqual(r['source_original_date'],'2026-10-14');self.assertEqual(r['source_original_note'],row['note'])
  for key in ('base64','sha256','report','plan'):self.assertEqual(books[0][key],after['workbooks'][0][key])
  self.assertEqual(herd(before['batches'],before['movements'],'2026-10-15'),herd(after['batches'],after['movements'],'2026-10-15'));self.assertEqual(next(r for r in source_history(after) if r['type']=='cull')['date'],'2026-10-14')
  self.store.enrich_legacy(after);self.store.enrich_legacy(after);self.assertEqual(len([r for r in source_history(after) if r['id']==row['id']]),1)
  report=weekly_report(after,{'cohort':['JD-TEST|2026-09-09'],'to':['2026-10-15']},today='2026-10-15');event=next(e for w in report['weeks'] for e in w['events'] if e['id']==row['id']);self.assertEqual(event['date'],'2026-10-13');self.assertEqual(event['outgoing_destination'],'新北')
 def test_market_part_moves_while_on_farm_part_keeps_its_date(self):
  row=self.original('death');before=self.store.snapshot();review=self.review(row,parts=[{'date':'2026-10-14','quantity':1,'note':'10/14棟內死亡1頭'},{'date':'2026-10-13','quantity':1,'note':'10/13市場死亡1頭（新北）'}]);self.save(review);d=self.store.snapshot();parts=[r for r in source_history(d) if r.get('source_original_id')==row['id']]
  self.assertEqual(sorted((r['date'],r['quantity']) for r in parts),[('2026-10-13',1),('2026-10-14',1)]);self.assertEqual(len({r['id'] for r in parts}),2);self.assertEqual(parts[0]['id'],row['id']);self.assertTrue(all(r['batch_id']==row['batch_id'] for r in parts));self.assertEqual(sum(r['quantity'] for r in parts),row['quantity']);self.assertEqual(herd(before['batches'],before['movements'],'2026-10-15'),herd(d['batches'],d['movements'],'2026-10-15'))
 def test_existing_barn_assignment_survives_date_correction_and_later_edit(self):
  r=self.original('death','2026-10-11');b=next(b for b in self.store.snapshot()['batches'] if b['legacy_barn']==1);b=self.store.mutate(self.admin,'batches',b|{'source_assignments':[assignment_identity(r)|{'reason':'確認1棟'}]},str(uuid.uuid4()),b['id']);self.save(self.review(r,on='2026-10-12'));b=self.store.mutate(self.admin,'batches',b|{'note':'edit'},str(uuid.uuid4()),b['id']);d=self.store.snapshot();changed=next(x for x in source_history(d) if x['id']==r['id']);self.assertEqual((changed['date'],changed['barn_number']),('2026-10-12',1));self.assertEqual(changed['assignment_review']['date'],'2026-10-11')
 def test_crossing_baseline_moves_snapshot_count_once(self):
  raw=self.original('death','2026-10-11');target=next(b for b in self.store.snapshot()['batches'] if b['legacy_barn']==1);self.store.mutate(self.admin,'batches',target|{'source_assignments':[assignment_identity(raw)|{'reason':'確認1棟'}]},str(uuid.uuid4()),target['id'])
  before=self.store.snapshot();b=next(b for b in before['batches'] if b['legacy_barn']==2);heads=b['legacy_heads']['2026-10-12'];self.save(self.review(self.original('death'),on='2026-10-12'));after=self.store.snapshot();b=next(b for b in after['batches'] if b['legacy_barn']==2);self.assertEqual(b['legacy_heads']['2026-10-12'],heads-2);self.assertEqual(b['legacy_values']['2026-10-12']['dead'],2)
  self.store.enrich_legacy(after);self.assertEqual(next(b for b in after['batches'] if b['legacy_barn']==2)['legacy_heads']['2026-10-12'],heads-2)
 def test_invalid_identity_total_destination_and_parts_are_rejected(self):
  original=self.review()
  for patch in ({'quantity':3},{'original_date':'2026-10-13'},{'source_row_id':str(uuid.uuid4())},{'reason':''},{'parts':[]},{'parts':[{'date':'2026-10-13','quantity':1,'note':'x'}]},{'parts':[{'date':'bad','quantity':2,'note':'x'}]},{'parts':[{'date':'2026-10-13','quantity':True,'note':'x'}]}):
   with self.assertRaises((Problem,ValueError)):self.save(original|patch)
  bad=self.review(self.original('death'));bad['parts'][0]['outgoing_destination']='新北'
  with self.assertRaises((Problem,ValueError)):self.save(bad)
 def test_backup_restore_retains_immutable_source_and_corrections(self):
  row=self.original();self.save(self.review());clone=Store(Path(self.tmp.name)/'restored');doc=self.store.export_backup();clone.import_backup(self.admin,doc);clone.import_backup(self.admin,doc);r=next(r for r in source_history(clone.snapshot()) if r['id']==row['id']);self.assertEqual(r['date'],'2026-10-13');self.assertEqual(len(clone.snapshot()['workbooks']),1)
 def test_void_corrected_source_restores_quantity_once(self):
  row=self.original();self.save(self.review());d=self.store.snapshot();before=herd(d['batches'],d['movements'],'2026-10-15');p=void_preview(self.store,self.admin,d,'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'reason':'test','preview_token':p['preview_token']},str(uuid.uuid4()));d=self.store.snapshot();after=herd(d['batches'],d['movements'],'2026-10-15');self.assertEqual(after['remaining'],before['remaining']+2);self.assertNotIn(row['id'],[r['id'] for r in source_history(d)])

class CloudSourceDateTests(SourceDateTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
