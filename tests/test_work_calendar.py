import copy,tempfile,unittest,uuid
from pathlib import Path
from app.store import Store,Problem
from app.work_calendar import calendar_week

class WorkCalendarTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('worker','83000012','staff');self.viewer=self.store.create_user('reader','83000013','viewer')
 def tearDown(self):self.tmp.cleanup()
 def add(self,actor=None,**extra):return self.store.mutate(actor or self.admin,'work_tasks',dict(title='洗水塔',mode='weekly',weekday=0,start_date='2026-10-01',note='1、2棟')|extra,str(uuid.uuid4()))
 def test_monday_sunday_boundaries_year_and_leap_day(self):
  for selected,start,end in [('2026-10-25','2026-10-19','2026-10-25'),('2026-10-19','2026-10-19','2026-10-25'),('2027-01-01','2026-12-28','2027-01-03'),('2028-02-29','2028-02-28','2028-03-05')]:
   week=calendar_week({},selected);self.assertEqual((week['from'],week['to']),(start,end));self.assertEqual([d['weekday'] for d in week['days']],list(range(7)))
 def test_recurrence_dates_once_inclusive_end_and_time_sort(self):
  weekly=self.add(time='09:00');once=self.add(mode='once',date='2026-10-19',time='08:00');self.add(active=False);self.add(start_date='2026-10-20');self.add(end_date='2026-10-18');last=self.add(end_date='2026-10-19',time='07:00');self.add(mode='once',date='2026-10-26')
  snap=self.store.snapshot();before=copy.deepcopy(snap);week=calendar_week(snap,'2026-10-22');self.assertEqual([r['id'] for r in week['days'][0]['tasks']],[last['id'],once['id'],weekly['id']]);self.assertFalse(any(d['tasks'] for d in week['days'][1:]));self.assertEqual(snap,before)
  future=calendar_week(snap,'2026-10-26');self.assertNotIn(once['id'],[r['id'] for r in future['days'][0]['tasks']])
 def test_invalid_fields_rejected_before_persistence(self):
  before=self.store.export_backup()
  for bad in [dict(title=' '),dict(title='a'*121),dict(mode='month'),dict(weekday=7),dict(weekday=True),dict(weekday='1'),dict(time='25:00'),dict(time='8:00'),dict(active='false'),dict(note='a'*1001),dict(start_date='bad'),dict(end_date='2026-09-01'),dict(mode='once',date='')]:
   with self.subTest(bad=bad),self.assertRaises(Problem):self.add(**bad)
  self.assertEqual(before['records'],self.store.export_backup()['records'])
 def test_permissions_and_optimistic_revision(self):
  task=self.add(actor=self.staff)
  with self.assertRaisesRegex(Problem,'forbidden'):self.add(actor=self.viewer)
  other=self.store.create_user('other','83000014','staff')
  with self.assertRaisesRegex(Problem,'forbidden'):self.store.mutate(other,'work_tasks',task|{'title':'unauthorized'},str(uuid.uuid4()),task['id'])
  updated=self.store.mutate(self.staff,'work_tasks',task|{'active':False},str(uuid.uuid4()),task['id']);self.assertEqual(updated['revision'],2)
  with self.assertRaisesRegex(Problem,'revision_conflict'):self.store.mutate(self.staff,'work_tasks',task,str(uuid.uuid4()),task['id'])
  self.assertFalse(any(d['tasks'] for d in calendar_week(self.store.snapshot(),'2026-10-19')['days']))
 def test_idempotent_retry_backup_and_farm_isolation(self):
  barn=self.store.mutate(self.admin,'barns',{'name':'15棟'},str(uuid.uuid4()));before=self.store.export_backup();key=str(uuid.uuid4());body=dict(title='臨時送貨',mode='once',date='2026-10-20')
  task=self.store.mutate(self.admin,'work_tasks',body,key);self.assertEqual(task,self.store.mutate(self.admin,'work_tasks',body,key));after=self.store.export_backup();self.assertEqual([r for r in after['records'] if r['kind']!='work_tasks'],before['records']);self.assertEqual(after['users'],before['users']);self.assertEqual(len(self.store.snapshot()['work_tasks']),1)
  with tempfile.TemporaryDirectory() as other:
   restored=Store(Path(other)/'db');admin=restored.create_user('restore','83000015');restored.import_backup(admin,after);self.assertEqual(restored.snapshot()['work_tasks'],self.store.snapshot()['work_tasks']);self.assertEqual(restored.snapshot()['barns'][0]['id'],barn['id'])

class CloudWorkCalendarTests(WorkCalendarTests):
 def setUp(self):
  super().setUp()
  from app.cloud_store import CloudStore,migrate
  from cloud_fixture import HranaFixture
  self.fixture=HranaFixture(Path(self.tmp.name)/'remote');cloud=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.store,cloud);self.store=cloud
 def tearDown(self):self.fixture.close();super().tearDown()
