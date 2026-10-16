"""Explicit same-batch grouping preserves physical arrivals and source identities."""
import base64,copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.domain import herd
from app.history import cohort_key
from app.server import client_snapshot,statistics,filter_rows
from app.weekly import weekly_report
from legacy_fixture import workbook_fixture
class CohortLinkTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.owner=self.store.create_user('owner','83000011');self.barns=[self.add('barns',name=f'{n}棟',group='') for n in (1,2)]
  self.first=self.add('batches',name='SYNTHETIC',barn_id=self.barns[0]['id'],entry_date='2026-10-09',entry_count=100,entry_age_days=71,status='active');self.second=self.add('batches',name='SYNTHETIC',barn_id=self.barns[1]['id'],entry_date='2026-10-16',entry_count=30,entry_age_days=71,status='active')
 def tearDown(self):self.tmp.cleanup()
 def add(self,kind,**d):return self.store.mutate(self.owner,kind,d,str(uuid.uuid4()))
 def record(self,bid):return next(b for b in self.store.snapshot()['batches'] if b['id']==bid)
 def link(self,child=None,parent=None,**kw):
  b=self.record(child or self.second['id']);return self.store.mutate(self.owner,'batches',b|{'same_batch_as':parent or self.first['id']}|kw,str(uuid.uuid4()),b['id'])
 def test_different_dates_stay_separate_until_explicit_link_without_changing_counts(self):
  before=self.store.snapshot();self.assertNotEqual(*[cohort_key(b) for b in before['batches']]);self.link();after=self.store.snapshot();self.assertEqual(*[cohort_key(b) for b in after['batches']]);self.assertEqual(after['batches'][1]['entry_date'],'2026-10-16')
  for key in ('entry_count','entry_age_days','age_date','entry_mean_kg'):self.assertEqual(before['batches'][1][key],after['batches'][1][key])
  for on in ('2026-10-09','2026-10-15','2026-10-16'):self.assertEqual(herd(before['batches'],[],on),herd(after['batches'],[],on))
 def test_summary_and_filters_share_root_date_and_include_both_barns(self):
  self.link();d=self.store.snapshot();snapshot=client_snapshot(d,'test');self.assertEqual(len(snapshot['cohorts']),1);self.assertEqual(snapshot['cohorts'][0]['entry_date'],'2026-10-09');self.assertEqual(snapshot['cohorts'][0]['barns'],['1棟','2棟']);q={'cohort':['SYNTHETIC|2026-10-09'],'to':['2026-10-16']};self.assertEqual(statistics(d,q)['cumulative']['entry'],130);self.assertEqual(len(filter_rows('batches',d,q)),2);self.assertTrue(statistics(d,q)['cohorts'][0]['age_mixed'])
 def test_weekly_shared_anchor_keeps_deaths_in_each_actual_period(self):
  self.link();self.add('movements',date='2026-10-16',batch_id=self.second['id'],type='death',quantity=1);d=self.store.snapshot();r=weekly_report(d,{'cohort':['SYNTHETIC|2026-10-09'],'to':['2026-10-16']},today='2026-10-16');self.assertEqual([w['known']['death'] for w in r['weeks']],[0,1]);self.assertTrue(r['age_mixed']);self.assertIsNone(r['entry_age_days']);self.assertEqual({b['entry_date'] for b in r['barn_ages']},{'2026-10-09','2026-10-16'})
 def test_internal_transfer_does_not_inflate_cohort_entry_denominator(self):
  self.link();self.add('movements',date='2026-10-16',batch_id=self.first['id'],type='transfer',quantity=10,target_batch_id=self.second['id']);d=self.store.snapshot();h=herd(d['batches'],d['movements'],'2026-10-16');self.assertEqual(h['denominator'],130);self.assertEqual(h['remaining'],130)
 def test_old_client_omitting_new_field_preserves_existing_link(self):
  self.link();b=self.record(self.second['id']);payload={k:v for k,v in b.items() if k!='same_batch_as'};self.store.mutate(self.owner,'batches',payload|{'entry_mean_kg':22},str(uuid.uuid4()),b['id']);self.assertEqual(self.record(b['id'])['same_batch_as'],self.first['id'])
 def test_unlink_keeps_own_arrival_and_restores_independent_group(self):
  self.link();b=self.record(self.second['id']);self.store.mutate(self.owner,'batches',b|{'same_batch_as':None},str(uuid.uuid4()),b['id']);self.assertNotEqual(cohort_key(self.record(b['id'])),cohort_key(self.record(self.first['id'])));self.assertEqual(self.record(b['id'])['entry_count'],30)
 def test_cycles_and_earlier_child_dates_are_rejected(self):
  self.link()
  with self.assertRaises(Problem):self.link(self.first['id'],self.second['id'])
  # Same-day roots exercise cycle detection independently of date validation.
  third=self.add('barns',name='3棟',group='');b=self.add('batches',barn_id=third['id'],name='THIRD',entry_date='2026-10-09',entry_count=20,status='active');self.link(self.first['id'],b['id'])
  with self.assertRaises(Problem) as e:self.link(b['id'],self.first['id'])
  self.assertEqual(e.exception.code,'cohort_link_cycle')
 def test_referenced_root_cannot_be_deleted(self):
  self.link();b=self.record(self.first['id'])
  with self.assertRaises(Problem):self.store.mutate(self.owner,'batches',{'revision':b['revision']},str(uuid.uuid4()),b['id'],delete=True)
  self.assertEqual(len(self.store.snapshot()['batches']),2)
 def test_role_restrictions_and_stale_revision_are_enforced(self):
  b=self.second
  for role in ('viewer','staff'):
   with self.assertRaises(Problem) as e:self.store.mutate(self.owner|{'role':role},'batches',b|{'same_batch_as':self.first['id']},str(uuid.uuid4()),b['id'])
   self.assertEqual(e.exception.status,403)
  self.link()
  with self.assertRaises(Problem) as e:self.store.mutate(self.owner,'batches',b|{'same_batch_as':None},str(uuid.uuid4()),b['id'])
  self.assertEqual(e.exception.status,409)
 def test_backup_restore_preserves_links_ids_and_historical_source(self):
  self.link();doc=self.store.export_backup();clone=Store(Path(self.tmp.name)/'clone');clone.import_backup(self.owner,doc);self.assertEqual({b['id']:cohort_key(b) for b in clone.snapshot()['batches']},{b['id']:cohort_key(b) for b in self.store.snapshot()['batches']})
 def test_link_to_legacy_root_preserves_original_source_and_ended_barn(self):
  self.store.import_workbook(self.owner,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()));d=self.store.snapshot();root=next(b for b in d['batches'] if b.get('legacy_source'));books=copy.deepcopy(d['workbooks']);self.link(parent=root['id']);new=self.store.snapshot();self.assertEqual(new['workbooks'],books);self.assertEqual(cohort_key(self.record(self.second['id'])),cohort_key(root))
  with self.assertRaises(Problem):self.link(root['id'],self.first['id'])
