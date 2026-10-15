"""1.5.0: isolated transactions, source-baseline corrections and paper weighing."""
import base64,copy,json,tempfile,unittest,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.store import Store,Problem
from app.domain import herd,Invalid,combined_weights
from app.operations import void_preview,void_record,save_weighing
from app.history import source_history
from app.server import statistics,client_snapshot,filter_rows
from legacy_fixture import workbook_fixture

class RedesignTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'farm.db');self.admin=self.store.create_user('owner','synthetic-owner-password');self.staff=self.store.create_user('editor','synthetic-editor-password','staff');self.viewer=self.store.create_user('reader','synthetic-viewer-password','viewer')
  self.barn=self.add('barns',name='19棟',group='A');self.batch=self.add('batches',name='JD-TEST',barn_id=self.barn['id'],entry_date='2026-01-01',entry_count=100,entry_age_days=70,status='active')
 def tearDown(self):self.temp.cleanup()
 def add(self,kind,**values):return self.store.mutate(self.admin,kind,values,str(uuid.uuid4()))
 def job(self,**patch):return {'session_id':str(uuid.uuid4()),'date':'2026-01-15','batch_id':self.batch['id'],'pens':[{'pen':'1A','section':'head','individual_kg':[50,50]},{'pen':'4B','section':'middle','count':4,'total_kg':240}]}|patch
 def void(self,kind,rid):
  p=void_preview(self.store,self.admin,self.store.snapshot(),kind,rid);return void_record(self.store,self.admin,{'kind':kind,'id':rid,'reason':'synthetic correction','preview_token':p['preview_token']},str(uuid.uuid4()))
 def test_session_uses_actual_counts_and_weighted_mean(self):
  r=save_weighing(self.store,self.staff,self.job(),str(uuid.uuid4()));rows=self.store.snapshot()['weights'];self.assertEqual(len(rows),2);self.assertEqual(r['session_number'],1);self.assertAlmostEqual(combined_weights(rows)[0]['mean'],340/6);self.assertEqual(rows[0]['section'],'head')
 def test_bad_second_pen_rolls_back_entire_session(self):
  with self.assertRaises((Invalid,Problem)):save_weighing(self.store,self.staff,self.job(pens=[{'individual_kg':[50]},{'individual_kg':[0]}]),str(uuid.uuid4()))
  self.assertEqual(self.store.snapshot()['weights'],[])
 def test_session_retry_and_same_id_new_key_do_not_duplicate(self):
  p=self.job();key=str(uuid.uuid4());first=save_weighing(self.store,self.staff,p,key);repeat=save_weighing(self.store,self.staff,p,key);self.assertEqual(first['ids'],repeat['ids']);self.assertTrue(save_weighing(self.store,self.staff,p,str(uuid.uuid4()))['already_saved']);self.assertEqual(len(self.store.snapshot()['weights']),2)
 def test_session_id_conflict_does_not_overwrite(self):
  p=self.job();save_weighing(self.store,self.staff,p,str(uuid.uuid4()));p['pens'][0]['individual_kg']=[60]
  with self.assertRaises(Problem):save_weighing(self.store,self.staff,p,str(uuid.uuid4()))
 def test_new_session_numbers_survive_voids_and_same_date(self):
  a=save_weighing(self.store,self.admin,self.job(),str(uuid.uuid4()));self.void('weights',a['ids'][0]);self.void('weights',a['ids'][1]);b=save_weighing(self.store,self.admin,self.job(),str(uuid.uuid4()));self.assertEqual(b['session_number'],2)
 def test_viewer_cannot_save_weighing_or_preview_void(self):
  with self.assertRaises(Problem):save_weighing(self.store,self.viewer,self.job(),str(uuid.uuid4()))
  for u in (self.staff,self.viewer):
   with self.assertRaises(Problem):void_preview(self.store,u,self.store.snapshot(),'weights','none')
 def test_operational_void_preview_and_audit_recalculate(self):
  row=self.add('movements',date='2026-01-02',batch_id=self.batch['id'],type='death',quantity=2);p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);self.assertEqual(p['impact']['farm_before']['remaining'],98);self.assertEqual(p['impact']['farm_after']['remaining'],100);self.void('movements',row['id']);self.assertEqual(self.store.snapshot()['movements'],[])
  db=self.store.connect();r=json.loads(db.execute('SELECT data FROM records WHERE id=?',(row['id'],)).fetchone()[0]);self.assertEqual(r['void_reason'],'synthetic correction');self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE action='void'").fetchone()[0],1);db.close()
 def test_void_requires_reason_and_current_preview(self):
  row=self.add('movements',date='2026-01-02',batch_id=self.batch['id'],type='death',quantity=1);p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);body={'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':''}
  with self.assertRaises(Problem):void_record(self.store,self.admin,body,str(uuid.uuid4()))
  self.add('movements',date='2026-01-03',batch_id=self.batch['id'],type='death',quantity=1);body['reason']='test'
  with self.assertRaises(Problem) as e:void_record(self.store,self.admin,body,str(uuid.uuid4()))
  self.assertEqual(e.exception.status,409)
 def test_void_retry_is_idempotent(self):
  row=self.add('movements',date='2026-01-02',batch_id=self.batch['id'],type='death',quantity=1);p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);body={'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'duplicate'};key=str(uuid.uuid4());void_record(self.store,self.admin,body,key);self.assertTrue(void_record(self.store,self.admin,body,key)['voided']);self.assertEqual(herd(self.store.snapshot()['batches'],[],'2026-01-03')['remaining'],100)
 def test_cohort_label_contains_barn_and_date(self):
  c=client_snapshot(self.store.snapshot(),'x')['cohorts'][0];self.assertEqual(c['barns'],['19棟']);self.assertEqual(c['entry_date'],'2026-01-01')
 def test_period_deaths_and_cumulative_not_mixed(self):
  for on,q in [('2026-01-02',2),('2026-01-03',3)]:self.add('movements',date=on,batch_id=self.batch['id'],type='death',quantity=q)
  stats=statistics(self.store.snapshot(),{'from':['2026-01-03'],'to':['2026-01-03']});self.assertEqual(stats['death_summary']['total'],3);self.assertEqual(stats['cumulative']['dead'],5);self.assertEqual(stats['cohorts'][0]['period_deaths'],3)
 def test_date_only_death_summary_means_that_day(self):
  self.add('movements',date='2026-01-02',batch_id=self.batch['id'],type='death',quantity=2);stats=statistics(self.store.snapshot(),{'to':['2026-01-03']});self.assertEqual(stats['death_summary']['total'],0);self.assertEqual(stats['cumulative']['dead'],2)
 def test_backup_retains_weighing_session_and_void(self):
  r=save_weighing(self.store,self.admin,self.job(),str(uuid.uuid4()));self.void('weights',r['ids'][0]);clone=Store(self.root/'restore.db');clone.import_backup(self.admin,self.store.export_backup());self.assertEqual(len(clone.snapshot()['weights']),1);self.assertEqual(clone.snapshot()['weights'][0]['session_id'],r['session_id'])

class SourceVoidTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'farm.db');self.admin=self.store.create_user('owner','synthetic-owner-password');self.payload={'filename':'source.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'};self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))
 def tearDown(self):self.temp.cleanup()
 def target(self):return next(r for r in source_history(self.store.snapshot()) if r['type']=='death' and r.get('batch_id') and r['date']=='2026-10-14')
 def test_baseline_source_void_adds_back_once_and_keeps_source_file(self):
  row=self.target();p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);q=row['quantity'];before=herd(self.store.snapshot()['batches'],[],'2026-10-14');body={'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'source error'};void_record(self.store,self.admin,body,str(uuid.uuid4()));d=self.store.snapshot();after=herd(d['batches'],d['movements'],'2026-10-14');self.assertEqual(after['remaining'],before['remaining']+q);self.assertEqual(after['dead'],before['dead']-q);self.assertFalse(any(r['id']==row['id'] for r in source_history(d)));self.assertEqual(d['workbooks'][0]['base64'],self.payload['base64']);self.assertTrue(self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))['already_imported']);self.assertEqual(herd(self.store.snapshot()['batches'],[],'2026-10-14')['remaining'],after['remaining'])
 def test_source_void_backup_restores_without_resurrection(self):
  row=self.target();p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'source error'},str(uuid.uuid4()));clone=Store(self.root/'restore.db');clone.import_backup(self.admin,self.store.export_backup());self.assertFalse(any(r['id']==row['id'] for r in source_history(clone.snapshot())))
 def test_new_workbook_missing_archive_does_not_remove_old_history(self):
  d=self.store.snapshot();book=d['workbooks'][0];old=copy.deepcopy(book);old['id']='version-old';old['base_book_id']=book['id'];old['report']['archive_rows']=[copy.deepcopy(book['report']['rows'][0])];old['report']['archive_rows'][0]['name']='ARCHIVE';new=copy.deepcopy(book);new['id']='version-new';new['base_book_id']=book['id'];new['report']['as_of']='2026-10-16';new['report']['archive_rows']=[];d['workbooks']+=[old,new];self.assertTrue(any(r['archive'] and r['legacy_batch']=='ARCHIVE' for r in source_history(d)))
 def test_void_anchor_survives_source_date_correction_without_resurrection(self):
  d=self.store.snapshot();row=self.target();d['source_voids']=[{'source_row_id':row['id'],'target_kind':'movements','source_record':row}]
  book=d['workbooks'][0];event=next(e for e in book['report']['rows'][0]['events'] if e['date']==row['date'] and e['type']==row['type'] and any(a['barn']==row['barn_number'] for a in e['allocations']));event['date']='2026-10-13'
  self.assertFalse(any(r.get('source_anchor')==row['source_anchor'] for r in source_history(d)))
 def test_source_void_retains_identity_when_sheet_title_whitespace_changes(self):
  row=self.target();p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'source error'},str(uuid.uuid4()));d=self.store.snapshot();book=d['workbooks'][0];version=copy.deepcopy(book);version.update(id='new-source-version',base_book_id=book['id'],approved_cohorts=[r['name']+'|'+r['entry_date'] for r in book['report']['rows']]);version['report']['sheet']+='  ';version['report']['as_of']='2026-10-15';d['workbooks'].append(version);self.store.validate_global(d);self.assertFalse(any(r['id']==row['id'] for r in source_history(d)))

 def test_tampered_baseline_void_quantity_rejected_on_restore(self):
  row=self.target();p=void_preview(self.store,self.admin,self.store.snapshot(),'movements',row['id']);void_record(self.store,self.admin,{'kind':'movements','id':row['id'],'preview_token':p['preview_token'],'reason':'source error'},str(uuid.uuid4()));doc=self.store.export_backup()
  for record in doc['records']:
   if record['kind']=='source_voids':
    data=json.loads(record['data']);data['source_record']['quantity']=99999;record['data']=json.dumps(data)
  clone=Store(self.root/'tampered.db')
  with self.assertRaises(Problem):clone.import_backup(self.admin,doc)

 def test_source_weight_void_removes_mean_without_fake_weights(self):
  row=next(r for r in source_history(self.store.snapshot(),'weights'));p=void_preview(self.store,self.admin,self.store.snapshot(),'weights',row['id']);void_record(self.store,self.admin,{'kind':'weights','id':row['id'],'preview_token':p['preview_token'],'reason':'unreliable mean'},str(uuid.uuid4()));self.assertEqual(source_history(self.store.snapshot(),'weights'),[])
