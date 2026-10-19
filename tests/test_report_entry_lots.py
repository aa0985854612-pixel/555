import copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.weekly import weekly_report

class EntryLotReportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.user=self.store.create_user('owner','83000011');barn=self.add('barns',name='15棟')
  self.batch=self.add('batches',barn_id=barn['id'],name='JD-115-40.41',entry_date='2026-10-09',entry_count=1052,entry_age_days=71,entry_mean_kg=21.36,status='active')
  self.lots=[{'date':'2026-10-09','count':702,'mean_kg':21.36},{'date':'2026-10-16','count':350,'mean_kg':None}]
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**body):return self.store.mutate(self.user,kind,body,str(uuid.uuid4()))
 def save(self,**extra):return self.store.mutate(self.user,'batches',self.batch|extra,str(uuid.uuid4()),self.batch['id'])
 def test_lots_and_default_report_date_do_not_add_pigs(self):
  self.save(report_entry_lots=self.lots,report_entry_lots_source='source702 + confirmed1052 total',weekly_start_date='2026-10-16');d=self.store.snapshot();before=copy.deepcopy(d);r=weekly_report(d,{'batch_id':[self.batch['id']],'to':['2026-10-19']},today='2026-10-19')
  self.assertEqual(r['from'],'2026-10-16');self.assertEqual(r['weeks'][0]['anchor'],'2026-10-16');self.assertEqual([x['count'] for x in r['entry_details']],[702,350]);self.assertEqual([x['date'] for x in r['entry_details']],['2026-10-09','2026-10-16']);self.assertIsNone(r['entry_details'][1]['mean_kg']);self.assertIsNone(r['entry_mean_kg']);self.assertEqual(r['cumulative']['entry'],1052);self.assertEqual(r['cumulative']['remaining'],1052);self.assertEqual(d,before)
 def test_custom_earlier_period_is_still_queryable(self):
  self.save(report_entry_lots=self.lots,report_entry_lots_source='verified',weekly_start_date='2026-10-16');r=weekly_report(self.store.snapshot(),{'batch_id':[self.batch['id']],'from':['2026-10-09'],'to':['2026-10-19']});self.assertEqual(r['weeks'][0]['anchor'],'2026-10-09')
 def test_lot_count_must_match_existing_entry_total(self):
  lots=copy.deepcopy(self.lots);lots[1]['count']=351
  with self.assertRaisesRegex(Problem,'report_entry_total_mismatch'):self.save(report_entry_lots=lots,report_entry_lots_source='verified')
 def test_dates_counts_weights_and_source_are_validated(self):
  for lot,field in [({'date':'2026-10-09','count':350,'mean_kg':None},'date'),({'date':'2026-10-16','count':0,'mean_kg':None},'count'),({'date':'2026-10-16','count':350,'mean_kg':-1},'weight')]:
   with self.subTest(field=field),self.assertRaises(Problem):self.save(report_entry_lots=[self.lots[0],lot],report_entry_lots_source='verified')
  with self.assertRaisesRegex(Problem,'entry_source_required'):self.save(report_entry_lots=self.lots,report_entry_lots_source='')
  with self.assertRaisesRegex(Problem,'before_entry'):self.save(weekly_start_date='2026-10-08')
 def test_older_batch_editor_preserves_report_fields(self):
  self.batch=self.save(report_entry_lots=self.lots,report_entry_lots_source='verified',weekly_start_date='2026-10-16');payload={k:v for k,v in self.batch.items() if k not in ('report_entry_lots','report_entry_lots_source','weekly_start_date')};updated=self.store.mutate(self.user,'batches',payload|{'note':'other edit'},str(uuid.uuid4()),self.batch['id']);self.assertEqual(updated['report_entry_lots'],self.lots);self.assertEqual(updated['weekly_start_date'],'2026-10-16')
 def test_unlink_keeps_all_records_attached_to_their_original_batch(self):
  barn=self.add('barns',name='21棟');second=self.add('batches',barn_id=barn['id'],name='JD-115-40.41',entry_date='2026-10-16',entry_count=318,status='active',same_batch_as=self.batch['id']);movement=self.add('movements',batch_id=second['id'],date='2026-10-18',type='death',quantity=1)
  second=self.store.mutate(self.user,'batches',second|{'name':'JD-115-41','same_batch_as':None,'weekly_start_date':'2026-10-16'},str(uuid.uuid4()),second['id']);d=self.store.snapshot();r=weekly_report(d,{'batch_id':[second['id']],'to':['2026-10-19']});self.assertEqual(r['name'],'JD-115-41');self.assertEqual(r['barns'],['21棟']);self.assertEqual(r['cumulative']['entry'],318);self.assertEqual(r['cumulative']['dead'],1);self.assertEqual(next(m for m in d['movements'] if m['id']==movement['id'])['batch_id'],second['id']);self.assertEqual(r['from'],'2026-10-16')
