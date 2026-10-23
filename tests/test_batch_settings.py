"""Self-service edits are previewed, atomic, scoped and retry safe."""
import base64
import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from app.store import Store, Problem
from app.batch_settings import preview, save
from app.domain import herd
from app.history import source_history
from app.review import farm_today
from legacy_fixture import workbook_fixture


class BatchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'db')
        self.user = self.store.create_user('owner', '83000011')
        self.a = self.batch('9棟', 459)
        self.b = self.batch('23棟', 245)
        self.add('movements', batch_id=self.b['id'], date='2026-10-20', type='sale', quantity=163)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, kind, **body):
        return self.store.mutate(self.user, kind, body, str(uuid.uuid4()))

    def batch(self, name, count):
        barn = self.add('barns', name=name)
        return self.add('batches', barn_id=barn['id'], name='JD-115-23', entry_date='2026-06-12', entry_count=count, status='active')

    def request(self, mode='entry'):
        d = self.store.snapshot()
        rows = [b for b in d['batches'] if b['name'] == 'JD-115-23']
        body = {'mode': mode, 'batch_id': rows[0]['id'], 'reason': 'verified count', 'rows': []}
        if mode == 'stock':
            body['date'] = farm_today()
            body['rows'] = [{'id': b['id'], 'revision': b['revision'], 'remaining': None} for b in rows]
        else:
            body.update(name=rows[0]['name'], preserve_entry_total=True)
            for b in rows:
                barn = next(x for x in d['barns'] if x['id'] == b['barn_id'])
                body['rows'].append({'id': b['id'], 'revision': b['revision'], 'barn_revision': barn['revision'], 'barn_name': barn['name'], 'fields': {}})
        return body

    def apply(self, body, key=None):
        p = preview(self.store, self.user, body)
        return save(self.store, self.user, body | {'preview_token': p['preview_token']}, key or str(uuid.uuid4()))

    def stored(self):
        return {k:v for k,v in self.store.export_backup().items() if k!='exported_at'}

    def test_redistribute_entries_atomically_and_preview_without_writes(self):
        body = self.request();body['rows'][0]['fields']['entry_count'] = 469;body['rows'][1]['fields']['entry_count'] = 235
        before = self.stored()
        p = preview(self.store, self.user, body)
        self.assertEqual(self.stored(), before)
        self.assertEqual(p['before']['entry'], 704);self.assertEqual(p['after']['entry'], 704)
        self.assertEqual([r['after']-r['before'] for r in p['rows']], [10, -10])
        self.apply(body);self.assertEqual([b['entry_count'] for b in self.store.snapshot()['batches']], [469, 235])

    def test_counted_stock_preserves_entry_and_other_exit_totals(self):
        body = self.request('stock');body['rows'][1]['remaining'] = 80
        before = self.store.snapshot();p = preview(self.store, self.user, body)
        self.assertEqual(p['rows'][1]['before'], 82);self.assertEqual(p['rows'][1]['after'], 80)
        self.apply(body);d = self.store.snapshot()
        self.assertEqual(d['batches'], before['batches']);self.assertEqual(d['movements'][-1]['quantity'], -2)
        self.assertEqual(d['movements'][-1]['type'], 'adjustment');self.assertEqual(d['movements'][-1]['note'], 'verified count')
        self.assertEqual(herd(d['batches'], d['movements'], farm_today())['entry'], 704)

    def test_zero_is_a_real_count_and_blank_barn_is_unchanged(self):
        body = self.request('stock');body['rows'][1]['remaining'] = 0;self.apply(body)
        d = self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],farm_today(),[self.b['id']])['remaining'], 0)
        self.assertEqual(herd(d['batches'],d['movements'],farm_today(),[self.a['id']])['remaining'],459)

    def test_later_identical_recount_creates_a_new_record(self):
        body=self.request('stock');body['rows'][1]['remaining']=80;self.apply(body)
        first=self.store.snapshot()['movements'][-1]['id']
        self.add('movements',batch_id=self.b['id'],date=farm_today(),type='adjustment',quantity=5,note='later correction')
        self.apply(body);d=self.store.snapshot()
        self.assertEqual(len(d['movements']),4);self.assertNotEqual(d['movements'][-1]['id'],first)
        self.assertEqual(herd(d['batches'],d['movements'],farm_today(),[self.b['id']])['remaining'],80)

    def test_no_changes_and_invalid_values_are_rejected(self):
        with self.assertRaisesRegex(Problem, 'batch_settings_no_changes'):preview(self.store,self.user,self.request())
        for value in (-1, 1.5, True, 'invalid', []):
            body=self.request();body['rows'][0]['fields']['entry_count']=value
            with self.subTest(value=value),self.assertRaises(Problem):preview(self.store,self.user,body)
        body=self.request();body['rows'][0]['fields']={'entry_date':None}
        with self.assertRaises(Problem):preview(self.store,self.user,body)

    def test_total_guard_can_be_released_for_manual_source_correction(self):
        body=self.request();body['rows'][0]['fields']['entry_count']=460
        with self.assertRaisesRegex(Problem,'batch_settings_total_mismatch'):preview(self.store,self.user,body)
        body['preserve_entry_total']=False;self.apply(body)
        self.assertEqual(self.store.snapshot()['batches'][0]['entry_count'],460)

    def test_role_and_scope_and_reason_are_enforced(self):
        body=self.request('stock');body['rows'][1]['remaining']=81
        for role in ('staff','viewer'):
            user=self.store.create_user(role,'83000012',role)
            for fn in (lambda:preview(self.store,user,body),lambda:save(self.store,user,body,str(uuid.uuid4()))):
                with self.assertRaises(Problem) as cm:fn()
                self.assertEqual(cm.exception.status,403)
        for changed in (body|{'reason':''},body|{'rows':body['rows'][:1]},body|{'rows':body['rows']+[body['rows'][0]]}):
            with self.assertRaises(Problem):preview(self.store,self.user,changed)
        bad=copy.deepcopy(body);bad['rows'][0]['remaining']=-1
        with self.assertRaises(Problem):preview(self.store,self.user,bad)

    def test_preview_binds_values_and_all_concurrent_changes(self):
        body=self.request('stock');body['rows'][1]['remaining']=81;p=preview(self.store,self.user,body)
        altered=copy.deepcopy(body);altered['rows'][1]['remaining']=80
        with self.assertRaisesRegex(Problem,'revision_conflict'):save(self.store,self.user,altered|{'preview_token':p['preview_token']},str(uuid.uuid4()))
        self.add('movements',batch_id=self.a['id'],date=farm_today(),type='death',quantity=1)
        with self.assertRaisesRegex(Problem,'revision_conflict'):save(self.store,self.user,body|{'preview_token':p['preview_token']},str(uuid.uuid4()))

    def test_retry_and_atomic_rollback(self):
        body=self.request('stock');body['rows'][1]['remaining']=81;p=preview(self.store,self.user,body);body['preview_token']=p['preview_token'];key=str(uuid.uuid4())
        first=save(self.store,self.user,body,key);again=save(self.store,self.user,body,key)
        self.assertEqual(first['changed'],again['changed']);self.assertEqual(len(self.store.snapshot()['movements']),2)
        with self.assertRaisesRegex(Problem,'idempotency_mismatch'):save(self.store,self.user,body|{'reason':'changed'},key)
        entry=self.request();entry['rows'][0]['barn_name']='renamed';entry['rows'][1]['fields']={'entry_date':'2026-12-01'}
        before=self.stored()
        with self.assertRaises(Problem):self.apply(entry)
        self.assertEqual(before,self.stored())

    def test_preserves_unrelated_fields_and_supports_entry_lots_and_name(self):
        body=self.request();body['name']='JD-CORRECTED';body['rows'][0]['fields']={'entry_mean_kg':21.58,'weekly_start_date':'2026-06-19','report_entry_lots':[{'date':'2026-06-12','count':459,'mean_kg':21.58}],'report_entry_lots_source':'entry slip'}
        self.apply(body);d=self.store.snapshot();self.assertEqual(d['batches'][0]['entry_mean_kg'],21.58)
        self.assertTrue(all(b['name']=='JD-CORRECTED' for b in d['batches']))
        self.assertEqual(d['movements'][0]['batch_id'],self.b['id'])
        db=self.store.connect();self.assertTrue(all('verified count' in r['after_value'] for r in db.execute("SELECT after_value FROM audit WHERE action='batch-settings'")));db.close()

    def test_legacy_split_totals_and_renamed_barn_keep_history_ids(self):
        self.store.import_workbook(self.user,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
        d=self.store.snapshot();members=[b for b in d['batches'] if b.get('legacy_source')];before=source_history(d);body={'mode':'entry','batch_id':members[0]['id'],'name':members[0]['name'],'reason':'entry tickets','preserve_entry_total':True,'rows':[]}
        for i,b in enumerate(members):
            barn=next(x for x in d['barns'] if x['id']==b['barn_id'])
            body['rows'].append({'id':b['id'],'revision':b['revision'],'barn_revision':barn['revision'],'barn_name':'renamed 1' if i==0 else barn['name'],'fields':{}})
        self.apply(body);after=source_history(self.store.snapshot())
        self.assertEqual([(r['id'],r.get('batch_id'),r.get('barn_id')) for r in before],[(r['id'],r.get('batch_id'),r.get('barn_id')) for r in after])

    def test_future_stock_and_future_negative_balance_are_rejected(self):
        body=self.request('stock');body['date']='2099-01-01';body['rows'][1]['remaining']=81
        with self.assertRaisesRegex(Problem,'batch_settings_future_stock'):preview(self.store,self.user,body)
        self.add('movements',batch_id=self.b['id'],date='2026-12-01',type='sale',quantity=80)
        body=self.request('stock');body['rows'][1]['remaining']=79
        with self.assertRaisesRegex(Problem,'insufficient_heads'):preview(self.store,self.user,body)

    def test_cloud_uses_the_same_atomic_review_and_retry(self):
        from app.cloud_store import CloudStore,migrate
        from cloud_fixture import HranaFixture
        fixture=HranaFixture(Path(self.tmp.name)/'cloud')
        try:
            cloud=CloudStore('libsql://test.turso.io','synthetic-token',fixture);migrate(self.store,cloud);self.store=cloud
            body=self.request();body['rows'][0]['fields']['entry_count']=469;body['rows'][1]['fields']['entry_count']=235
            self.apply(body);self.assertEqual([b['entry_count'] for b in self.store.snapshot()['batches']],[469,235])
            body=self.request('stock');body['rows'][1]['remaining']=70;p=preview(self.store,self.user,body);request=body|{'preview_token':p['preview_token']};key=str(uuid.uuid4())
            save(self.store,self.user,request,key);save(self.store,self.user,request,key)
            self.assertEqual(len(self.store.snapshot()['movements']),2)
        finally:fixture.close()

    def test_confirmed_legacy_entries_redistribute_together_and_stay_raw(self):
        from test_source_assignment import SourceAssignmentTests
        case=SourceAssignmentTests();case.setUp()
        try:
            case.complete_stock_basis();s=case.store;d=s.snapshot();members=d['batches'];body={'mode':'entry','batch_id':members[0]['id'],'name':members[0]['name'],'reason':'verified reallocation','preserve_entry_total':True,'rows':[]}
            for i,b in enumerate(members):
                barn=next(x for x in d['barns'] if x['id']==b['barn_id'])
                body['rows'].append({'id':b['id'],'revision':b['revision'],'barn_revision':barn['revision'],'barn_name':barn['name'],'fields':{'entry_count':55 if i==0 else 45}})
            p=preview(s,case.admin,body);self.assertEqual(p['before']['entry'],100);self.assertEqual(p['after']['entry'],100)
            self.assertEqual([r['after']-r['before'] for r in p['rows']],[5,-5])
            save(s,case.admin,body|{'preview_token':p['preview_token']},str(uuid.uuid4()))
            after=s.snapshot();self.assertEqual([b['entry_count'] for b in after['batches']],[55,45]);self.assertEqual(after['workbooks'],d['workbooks']);self.assertEqual(after['movements'],d['movements'])
            db=s.connect()
            for row in db.execute("SELECT data FROM records WHERE kind='batches'"):
                stored=__import__('json').loads(row['data']);self.assertNotIn('legacy_group',stored);self.assertNotIn('legacy_heads',stored)
            db.close()
            clone=Store(Path(self.tmp.name)/'restored');clone.import_backup(self.user,s.export_backup());self.assertEqual([b['entry_count'] for b in clone.snapshot()['batches']],[55,45])
            bad=copy.deepcopy(body);bad['rows'][0]['fields']['entry_count']=56
            for r,b in zip(bad['rows'],after['batches']):r['revision']=b['revision']
            bad['preserve_entry_total']=False
            with self.assertRaisesRegex(Problem,'legacy_entry_total_mismatch'):preview(s,case.admin,bad)
        finally:case.tearDown()
