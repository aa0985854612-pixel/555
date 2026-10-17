"""Optional outgoing destination is metadata; counts and permissions stay intact."""
import copy,json,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.weekly import weekly_report
from app.domain import herd
from app.server import statistics

class OutgoingDestinationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('editor','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer');self.batches=[]
  for n in (9,23):
   barn=self.add('barns',name=f'{n}棟');self.batches.append(self.add('batches',name='DEMO',barn_id=barn['id'],entry_date='2026-01-01',entry_age_days=71,entry_count=100,status='active'))
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**d):return self.store.mutate(self.admin,kind,d,str(uuid.uuid4()))
 def move(self,destination='',typ='sale',index=0,**extra):return self.add('movements',batch_id=self.batches[index]['id'],date='2026-01-02',type=typ,quantity=1,outgoing_destination=destination,**extra)
 def report(self,**query):return weekly_report(self.store.snapshot(),{'cohort':['DEMO|2026-01-01'],'to':['2026-01-14']}|{k:[v] for k,v in query.items()},today='2026-01-14')
 def test_three_places_and_culls_are_preserved(self):
  records=[self.move(city,typ) for city in ('新北','南投','嘉義') for typ in ('sale','cull')];r=self.report();self.assertEqual(set(r['outgoing_destinations']),{'新北','南投','嘉義'});self.assertEqual({e['id']:e['outgoing_destination'] for w in r['weeks'] for e in w['events']},{m['id']:m['outgoing_destination'] for m in records});self.assertEqual(r['totals']['sale'],3);self.assertEqual(r['totals']['cull'],3);self.assertEqual(r['cumulative']['survival'],100)
 def test_old_records_and_free_text_are_not_guessed(self):
  m=self.add('movements',batch_id=self.batches[0]['id'],date='2026-01-02',type='sale',quantity=1,note='原文：新北或嘉義，尚未確認');r=self.report();self.assertEqual(r['outgoing_destinations'],[]);self.assertEqual(r['weeks'][0]['events'][0]['outgoing_destination'],'');self.assertEqual(r['weeks'][0]['events'][0]['note'],m['note'])
 def test_destination_edit_changes_no_stock_or_other_note(self):
  m=self.move('新北',note='司機備註');before=self.store.snapshot();metrics=statistics(before,{'from':['2026-01-01'],'to':['2026-01-14']});saved=self.store.mutate(self.admin,'movements',m|{'outgoing_destination':'南投'},str(uuid.uuid4()),m['id']);after=self.store.snapshot();self.assertEqual(statistics(after,{'from':['2026-01-01'],'to':['2026-01-14']}),metrics);self.assertEqual(saved['note'],'司機備註');db=self.store.connect()
  try:self.assertEqual(json.loads(db.execute("SELECT after_value FROM audit WHERE kind='movements' ORDER BY seq DESC LIMIT 1").fetchone()['after_value'])['outgoing_destination'],'南投')
  finally:db.close()
 def test_old_client_edit_preserves_but_explicit_clear_and_type_change_remove_place(self):
  m=self.move('嘉義');old={k:v for k,v in m.items() if k!='outgoing_destination'};m=self.store.mutate(self.admin,'movements',old|{'note':'舊用戶端更正'},str(uuid.uuid4()),m['id']);self.assertEqual(m['outgoing_destination'],'嘉義');m=self.store.mutate(self.admin,'movements',m|{'outgoing_destination':''},str(uuid.uuid4()),m['id']);self.assertEqual(m['outgoing_destination'],'');m=self.store.mutate(self.admin,'movements',m|{'outgoing_destination':'新北'},str(uuid.uuid4()),m['id']);old={k:v for k,v in m.items() if k!='outgoing_destination'};m=self.store.mutate(self.admin,'movements',old|{'type':'death'},str(uuid.uuid4()),m['id']);self.assertNotIn('outgoing_destination',m)
 def test_invalid_places_and_nonoutgoing_types_are_rejected(self):
  for destination in (None,True,[],{},'台北','新北\n','=SUM(1,2)'):
   with self.assertRaises(Problem):self.move(destination)
  for typ in ('death','arrival','adjustment'):
   with self.assertRaises(Problem):self.move('新北',typ)
 def test_editor_ownership_viewer_and_revision_checks(self):
  payload={'date':'2026-01-02','batch_id':self.batches[0]['id'],'type':'sale','quantity':1,'outgoing_destination':'新北'}
  with self.assertRaises(Problem) as e:self.store.mutate(self.viewer,'movements',payload,str(uuid.uuid4()))
  self.assertEqual(e.exception.status,403);m=self.store.mutate(self.staff,'movements',payload,str(uuid.uuid4()));updated=self.store.mutate(self.staff,'movements',m|{'outgoing_destination':'嘉義'},str(uuid.uuid4()),m['id']);self.assertEqual(updated['outgoing_destination'],'嘉義')
  with self.assertRaises(Problem) as e:self.store.mutate(self.staff,'movements',m,str(uuid.uuid4()),m['id'])
  self.assertEqual(e.exception.status,409);owned=self.move('新北')
  with self.assertRaises(Problem) as e:self.store.mutate(self.staff,'movements',owned|{'outgoing_destination':'南投'},str(uuid.uuid4()),owned['id'])
  self.assertEqual(e.exception.status,403)
 def test_week_and_barn_filters_keep_each_shipment(self):
  a=self.move('新北');b=self.move('南投',index=1);later=self.add('movements',batch_id=self.batches[0]['id'],date='2026-01-08',type='sale',quantity=2,outgoing_destination='嘉義');r=self.report();self.assertEqual([len(w['events']) for w in r['weeks']],[2,1]);self.assertEqual(self.report(barn_id=self.batches[1]['barn_id'])['outgoing_destinations'],['南投']);self.assertEqual(self.report(**{'from':'2026-01-08'})['outgoing_destinations'],['嘉義']);self.assertEqual({e['id'] for w in r['weeks'] for e in w['events']},{a['id'],b['id'],later['id']})
 def test_backup_restore_and_idempotent_retry(self):
  payload={'date':'2026-01-02','batch_id':self.batches[0]['id'],'type':'sale','quantity':1,'outgoing_destination':'南投'};key=str(uuid.uuid4());m=self.store.mutate(self.admin,'movements',payload,key);self.assertEqual(m,self.store.mutate(self.admin,'movements',payload,key));clone=Store(Path(self.tmp.name)/'restore');backup=self.store.export_backup();clone.import_backup(self.admin,backup);clone.import_backup(self.admin,backup);self.assertEqual(len(clone.snapshot()['movements']),1);self.assertEqual(clone.snapshot()['movements'][0]['outgoing_destination'],'南投')
 def test_void_excludes_note_without_deleting_original_evidence(self):
  m=self.move('嘉義');self.store.mutate(self.admin,'movements',m,str(uuid.uuid4()),m['id'],delete=True);self.assertEqual(self.report()['outgoing_destinations'],[]);backup=self.store.export_backup();row=next(r for r in backup['records'] if r['id']==m['id']);self.assertEqual(row['deleted'],1);self.assertEqual(json.loads(row['data'])['outgoing_destination'],'嘉義')

class CloudOutgoingDestinationTests(OutgoingDestinationTests):
 def setUp(self):
  super().setUp()
  from cloud_fixture import HranaFixture
  from app.cloud_store import CloudStore,migrate
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
