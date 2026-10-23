"""Optional trip IDs survive edits, source corrections and portable backups."""
import tempfile,unittest,uuid,copy
from pathlib import Path
from app.store import Store,Problem
from app.domain import Invalid,herd
from app.server import statistics
from app.weekly import weekly_report


class OutgoingTripTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.user=self.store.create_user('owner','83000011');self.batches=[]
  for n in (12,24):
   barn=self.add('barns',name=f'{n}棟');self.batches.append(self.add('batches',barn_id=barn['id'],name='DEMO',entry_date='2026-10-09',entry_count=300,status='active'))
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**values):return self.store.mutate(self.user,kind,values,str(uuid.uuid4()))
 def movement(self,**values):return self.add('movements',**({'batch_id':self.batches[0]['id'],'date':'2026-10-20','type':'sale','quantity':30,'outgoing_destination':'南投','outgoing_trip':'第1車'}|values))
 def test_trip_metadata_keeps_raw_records_and_weekly_counts(self):
  a=self.movement();b=self.movement(batch_id=self.batches[1]['id']);d=self.store.snapshot();old=copy.deepcopy(d)
  r=weekly_report(d,{'cohort':['DEMO|2026-10-09'],'to':['2026-10-23']},today='2026-10-23');events=[e for w in r['weeks'] for e in w['events']]
  self.assertEqual({e['id'] for e in events},{a['id'],b['id']});self.assertEqual([e['outgoing_trip'] for e in events],['第1車','第1車']);self.assertEqual(r['totals']['sale'],60);self.assertEqual(d,old)
 def test_metadata_edit_preserves_stock_and_old_client_does_not_clear_trip(self):
  m=self.movement();before=statistics(self.store.snapshot(),{'summary':['1'],'to':['2026-10-23']})
  m=self.store.mutate(self.user,'movements',m|{'outgoing_trip':' 第2車 '},str(uuid.uuid4()),m['id']);self.assertEqual(m['outgoing_trip'],'第2車')
  self.assertEqual(statistics(self.store.snapshot(),{'summary':['1'],'to':['2026-10-23']}),before)
  old={k:v for k,v in m.items() if k!='outgoing_trip'};m=self.store.mutate(self.user,'movements',old|{'note':'older client'},str(uuid.uuid4()),m['id']);self.assertEqual(m['outgoing_trip'],'第2車')
  m=self.store.mutate(self.user,'movements',m|{'outgoing_trip':''},str(uuid.uuid4()),m['id']);self.assertEqual(m['outgoing_trip'],'')
 def test_invalid_trip_values_and_nonshipment_types_rejected(self):
  for value in (None,True,[],{},'x'*81,'第1車\n','\t第1車','車\x7f次'):
   with self.subTest(value=value),self.assertRaises(Problem):self.movement(outgoing_trip=value)
  for typ in ('death','arrival','adjustment'):
   with self.subTest(typ=typ),self.assertRaises(Problem):self.movement(type=typ,outgoing_destination='')
  death=self.movement(type='death',outgoing_destination='',outgoing_trip='');self.assertNotIn('outgoing_trip',death)
 def test_backup_and_retry_preserve_trip_without_another_movement(self):
  body={'batch_id':self.batches[0]['id'],'date':'2026-10-20','type':'sale','quantity':30,'outgoing_destination':'南投','outgoing_trip':'第1車'};key=str(uuid.uuid4())
  first=self.store.mutate(self.user,'movements',body,key);self.assertEqual(self.store.mutate(self.user,'movements',body,key),first)
  with self.assertRaisesRegex(Problem,'idempotency_mismatch'):self.store.mutate(self.user,'movements',body|{'outgoing_trip':'第2車'},key)
  clone=Store(Path(self.tmp.name)/'clone');clone.import_backup(self.user,self.store.export_backup());self.assertEqual(clone.snapshot()['movements'][0]['outgoing_trip'],'第1車');self.assertEqual(len(clone.snapshot()['movements']),1)
 def test_imported_source_trip_is_optional_backward_compatible_and_audited(self):
  from test_source_edit import SourceEditTests
  from app.source_edit import preview,save
  from app.history import source_history
  case=SourceEditTests();case.setUp()
  try:
   row=case.row('sale');before=case.store.snapshot();p=case.request(row,outgoing_destination='南投',outgoing_trip='第1車');case.apply(p);d=case.store.snapshot();updated=next(r for r in source_history(d) if r['id']==row['id'])
   self.assertEqual(updated['outgoing_trip'],'第1車');self.assertEqual(updated['quantity'],row['quantity']);self.assertEqual(d['workbooks'][0]['base64'],before['workbooks'][0]['base64'])
   self.assertEqual(herd(d['batches'],d['movements'],'2026-10-23'),herd(before['batches'],before['movements'],'2026-10-23'))
   old=case.request(updated,note='old client edit');case.apply(old);d=case.store.snapshot();self.assertEqual(next(r for r in source_history(d) if r['id']==row['id'])['outgoing_trip'],'第1車')
   clone=Store(Path(self.tmp.name)/'source-clone');clone.import_backup(self.user,case.store.export_backup());self.assertEqual(next(r for r in source_history(clone.snapshot()) if r['id']==row['id'])['outgoing_trip'],'第1車')
   for value in ('第1車\n',None,True):
    with self.assertRaises((Invalid,Problem)):preview(case.store,case.admin,case.request(updated,outgoing_trip=value))
   with self.assertRaises((Invalid,Problem)):preview(case.store,case.admin,case.request(case.row('death'),outgoing_trip='第1車'))
  finally:case.tearDown()
 def test_cloud_record_preserves_trip(self):
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  fixture=HranaFixture(Path(self.tmp.name)/'cloud')
  try:
   cloud=CloudStore('libsql://test.turso.io','synthetic-token',fixture);migrate(self.store,cloud);self.store=cloud
   m=self.movement();old={k:v for k,v in m.items() if k!='outgoing_trip'};updated=self.store.mutate(self.user,'movements',old|{'note':'cloud edit'},str(uuid.uuid4()),m['id']);self.assertEqual(updated['outgoing_trip'],'第1車')
  finally:fixture.close()
