import copy
import tempfile
import unittest
import uuid
from pathlib import Path

from app.store import Problem, Store
from app.weekly import weekly_report


class VaccinePlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'db')
        self.admin=self.store.create_user('owner','83000011')
        self.staff=self.store.create_user('staff','83000012','staff')
        self.batches=[]
        for name in ('15棟','21棟'):
            barn=self.add('barns',name=name)
            self.batches.append(self.add('batches',barn_id=barn['id'],name='DEMO',
                entry_date='2026-07-01',entry_count=100,entry_age_days=71,status='active'))
        self.doses={key:{'date':'','bottles':None,'done':False} for key in ('pr1','app1','pr2','app2')}
        self.doses['pr1']={'date':'2026-08-08','bottles':2,'done':False}
        self.doses['app1']={'date':'2026-08-09','bottles':1.5,'done':True}

    def tearDown(self):
        self.tmp.cleanup()

    def add(self,kind,**body):
        return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))

    def test_saved_and_revised_per_barn_are_in_correct_weekly_reports(self):
        plan=self.add('vaccine_plans',batch_id=self.batches[0]['id'],doses=self.doses)
        data=self.store.snapshot()
        one=weekly_report(data,{'batch_id':[self.batches[0]['id']],'all_records':['1']},today='2026-10-01')
        other=weekly_report(data,{'batch_id':[self.batches[1]['id']],'all_records':['1']},today='2026-10-01')
        whole=weekly_report(data,{'cohort':['DEMO|2026-07-01'],'all_records':['1']},today='2026-10-01')
        self.assertEqual(one['vaccine_plans'][0]['doses'],self.doses)
        self.assertEqual(other['vaccine_plans'],[])
        self.assertEqual(whole['vaccine_plans'][0]['id'],plan['id'])
        changed=copy.deepcopy(self.doses)
        changed['pr1']['done']=True
        saved=self.store.mutate(self.admin,'vaccine_plans',plan|{'doses':changed},str(uuid.uuid4()),plan['id'])
        self.assertTrue(saved['doses']['pr1']['done'])
        self.assertEqual(self.store.snapshot()['batches'],data['batches'])
        with self.assertRaisesRegex(Problem,'revision_conflict'):
            self.store.mutate(self.admin,'vaccine_plans',plan|{'doses':changed},str(uuid.uuid4()),plan['id'])

    def test_shared_plan_follows_cohort_for_single_barn_and_preserves_older_plans(self):
        old=self.add('vaccine_plans',batch_id=self.batches[0]['id'],doses=self.doses)
        doses=copy.deepcopy(self.doses)
        doses['pr1']['done']=True
        shared=self.add('vaccine_plans',batch_id=self.batches[1]['id'],scope='cohort',doses=doses)
        snapshot=self.store.snapshot()
        for batch in self.batches:
            report=weekly_report(snapshot,{'batch_id':[batch['id']],'all_records':['1']},today='2026-10-01')
            self.assertIn(shared['id'],[p['id'] for p in report['vaccine_plans']])
        first=weekly_report(snapshot,{'batch_id':[self.batches[0]['id']],'all_records':['1']},today='2026-10-01')
        self.assertIn(old['id'],[p['id'] for p in first['vaccine_plans']])
        with self.assertRaisesRegex(Problem,'vaccine_plan_exists'):
            self.add('vaccine_plans',batch_id=self.batches[0]['id'],scope='cohort',doses=doses)
        without_scope={key:value for key,value in shared.items() if key!='scope'}
        with self.assertRaisesRegex(Problem,'revision_conflict'):
            self.store.mutate(self.admin,'vaccine_plans',without_scope,str(uuid.uuid4()),shared['id'])
        self.assertEqual(len(self.store.snapshot()['vaccine_plans']),2)

    def test_validation_permissions_and_idempotency(self):
        invalid=copy.deepcopy(self.doses)
        invalid['pr1']={'date':'','bottles':1,'done':True}
        with self.assertRaisesRegex(Problem,'invalid_vaccine_plan'):
            self.add('vaccine_plans',batch_id=self.batches[0]['id'],doses=invalid)
        with self.assertRaisesRegex(Problem,'forbidden'):
            self.store.mutate(self.staff,'vaccine_plans',{'batch_id':self.batches[0]['id'],'doses':self.doses},str(uuid.uuid4()))
        request={'batch_id':self.batches[0]['id'],'doses':self.doses}
        key=str(uuid.uuid4())
        first=self.store.mutate(self.admin,'vaccine_plans',request,key)
        self.assertEqual(self.store.mutate(self.admin,'vaccine_plans',request,key),first)
        with self.assertRaisesRegex(Problem,'vaccine_plan_exists'):
            self.add('vaccine_plans',**request)
        self.assertEqual(len(self.store.snapshot()['vaccine_plans']),1)


if __name__=='__main__':
    unittest.main()
