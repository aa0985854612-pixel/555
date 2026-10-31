"""Live overview excludes cleared, ended and future batches without changing history."""
import tempfile,unittest,uuid
from pathlib import Path
from app.store import Store
from app.server import statistics
class CurrentFarmTests(unittest.TestCase):
 cloud=False
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'db');self.u=self.s.create_user('owner','83000011');self.remote=None
  self.barns={n:self.add('barns',name=f'{n}棟') for n in (1,9,12)}
  self.batches={n:self.add('batches',name='TEST-'+str(n),barn_id=b['id'],entry_date='2026-06-01',entry_count=1000 if n==1 else 100,status='active') for n,b in self.barns.items()}
  if self.cloud:
   from cloud_fixture import HranaFixture
   from app.cloud_store import CloudStore,migrate
   self.remote=HranaFixture(Path(self.tmp.name)/'remote');target=CloudStore('libsql://test.turso.io','synthetic-token',self.remote);migrate(self.s,target);self.s=target
 def tearDown(self):
  if self.remote:self.remote.close()
  self.tmp.cleanup()
 def add(self,kind,**body):return self.s.mutate(self.u,kind,body,str(uuid.uuid4()))
 def summary(self,on='2026-10-31'):return statistics(self.s.snapshot(),{'summary':['1'],'to':[on]})
 def sale(self,n,q,date='2026-10-30'):return self.add('movements',batch_id=self.batches[n]['id'],date=date,type='sale',quantity=q,outgoing_destination='嘉義')
 def test_five_hundred_sales_becomes_four_hundred_after_barn9_is_empty(self):
  self.sale(1,400);self.sale(9,100);s=self.summary();self.assertEqual(s['cumulative']['sold'],500);self.assertEqual(s['current_farm']['herd']['sold'],400);self.assertNotIn(self.batches[9]['id'],s['current_farm']['ids']);self.assertEqual(len(self.s.snapshot()['movements']),2)
 def test_future_clearance_is_not_applied_early(self):
  self.sale(1,400);self.sale(9,100,'2026-11-01');self.assertIn(self.batches[9]['id'],self.summary()['current_farm']['ids']);self.assertNotIn(self.batches[9]['id'],self.summary('2026-11-01')['current_farm']['ids'])
 def test_ended_and_future_batches_do_not_enter_current_totals(self):
  self.sale(12,20);b=self.batches[12];self.s.mutate(self.u,'batches',b|{'status':'ended'},str(uuid.uuid4()),b['id']);future=self.add('batches',name='NEXT',barn_id=self.barns[9]['id'],entry_date='2026-11-02',entry_count=200,status='active');summary=self.summary();self.assertEqual(summary['current_farm']['herd']['sold'],0);self.assertNotIn(b['id'],summary['current_farm']['ids']);self.assertNotIn(future['id'],summary['current_farm']['ids']);self.assertEqual(summary['cumulative']['sold'],20)
 def test_new_batch_does_not_bring_old_cleared_sales_into_overview(self):
  self.sale(9,100);new=self.add('batches',name='NEW-9',barn_id=self.barns[9]['id'],entry_date='2026-10-31',entry_count=50,status='active');s=self.summary();self.assertEqual(s['current_farm']['herd']['sold'],0);self.assertIn(new['id'],s['current_farm']['ids']);self.assertEqual(s['cumulative']['sold'],100)
class CloudCurrentFarmTests(CurrentFarmTests):cloud=True
