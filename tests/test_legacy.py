import base64,copy,csv,io,json,tempfile,threading,unittest,uuid,urllib.request,urllib.error,http.cookiejar
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.legacy import review,reconcile,parse_counts,allocate
from app.store import Store,Problem
from app.domain import herd,Invalid,age
from app.server import Server,statistics,filter_rows
from legacy_fixture import workbook_fixture

class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.store=Store(self.folder/'farm.db')
        self.admin=self.store.create_initial_admin('tester','legacy-test-password');self.staff=self.store.create_user('reader','legacy-test-password','viewer')
        self.raw=workbook_fixture();self.payload={'filename':'test.xlsx','base64':base64.b64encode(self.raw).decode(),'counts_text':'1/50\n2/49','counts_as_of':'2026-10-12','closed_barns':[],'source_url':''}
    def tearDown(self):self.temp.cleanup()
    def apply(self):return self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))
    def test_reads_cached_values_preserves_original_and_excludes_old_table(self):
        report=review(self.raw);self.assertEqual(report['totals']['entry'],100);self.assertEqual(report['totals']['remaining'],90)
        self.assertEqual(len(report['rows'][0]['events']),6);self.assertIn('肉豬各周存欄頭數(舊) ',report['sheets']);self.assertIsNone(report['rows'][0]['weights'][0]['sample_count'])
    def test_backcast_oct12_and_current_group_conservation(self):
        report=review(self.raw);plan=reconcile(report,parse_counts('1/50\n2/49'),'2026-10-12')
        self.assertEqual(plan['rows'][0]['snapshots']['2026-10-12']['remaining'],99);self.assertEqual(sum(plan['rows'][0]['current'].values()),90)
        self.assertEqual(allocate(7,{1:2,2:3}),{1:3,2:4})
    def test_large_difference_is_not_silently_micro_adjusted(self):
        payload=self.payload|{'counts_text':'1/10\n2/10'}
        with self.assertRaisesRegex(Invalid,'large_allocation_adjustment'):self.store.import_workbook(self.admin,payload,str(uuid.uuid4()))
        self.assertFalse(self.store.snapshot()['batches'])
    def test_atomic_import_headcounts_originals_and_no_fake_movements_or_weights(self):
        result=self.apply();data=self.store.snapshot();self.assertEqual(result['batches_added'],2)
        self.assertEqual(base64.b64decode(data['workbooks'][0]['base64']),self.raw)
        self.assertFalse(data['movements']);self.assertFalse(data['weights'])
        self.assertTrue(list((self.folder/'backups').glob('before-workbook-import-*')))
        self.assertEqual(herd(data['batches'],data['movements'],'2026-10-14')['remaining'],90)
    def test_group_survival_real_barn_denominator_unknown_and_historical_unknown(self):
        self.apply();d=self.store.snapshot();whole=herd(d['batches'],d['movements'],'2026-10-14')
        self.assertEqual(whole['survival'],96);self.assertEqual(whole['outgoing'],6)
        partial=herd(d['batches'],d['movements'],'2026-10-14',[d['batches'][0]['id']]);self.assertIsNone(partial['entry']);self.assertIsNone(partial['survival']);self.assertIsNotNone(partial['remaining']);self.assertEqual(partial['dead'],1);self.assertEqual(partial['culled'],1);self.assertIsNone(partial['sold'])
        self.assertEqual(herd(d['batches'],d['movements'],'2026-10-12')['remaining'],99)
        self.assertIsNone(herd(d['batches'],d['movements'],'2026-10-13')['remaining'])
    def test_future_change_uses_baseline_without_double_count_and_retains_original(self):
        self.apply();d=self.store.snapshot();bid=d['batches'][0]['id']
        self.store.mutate(self.admin,'movements',{'date':'2026-10-15','batch_id':bid,'type':'death','quantity':1,'note':''},str(uuid.uuid4()))
        d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],89);self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['dead'],5)
        self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14')['remaining'],90)
    def test_reliable_historical_feed_can_be_added_without_changing_pig_baseline(self):
        self.apply();b=self.store.snapshot()['batches'][0]
        usage=self.store.mutate(self.admin,'usages',{'batch_id':b['id'],'start':'2026-10-12','end':'2026-10-14','method':'direct','kg':50},str(uuid.uuid4()))
        self.assertEqual(usage['kg'],50);d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14')['remaining'],90)
        self.assertIsNone(statistics(d,{'to':['2026-10-14']})['aggregate_fcr'])
    def test_legacy_daily_reentry_blocked_admin_census_correction_allowed(self):
        self.apply();b=self.store.snapshot()['batches'][0]
        with self.assertRaises(Problem):self.store.mutate(self.admin,'movements',{'date':'2026-10-14','batch_id':b['id'],'type':'death','quantity':1},str(uuid.uuid4()))
        self.store.mutate(self.admin,'movements',{'date':'2026-10-14','batch_id':b['id'],'type':'adjustment','quantity':1},str(uuid.uuid4()))
        d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14')['remaining'],91)
    def test_repeated_and_concurrent_import_cannot_duplicate_or_override_age(self):
        self.apply();b=self.store.snapshot()['batches'][0]
        self.store.mutate(self.admin,'batches',b|{'entry_age_days':81},str(uuid.uuid4()),b['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.apply(),range(2)))
        self.assertTrue(all(r['already_imported'] for r in results));d=self.store.snapshot();self.assertEqual(len(d['batches']),2);self.assertEqual(d['batches'][0]['entry_age_days'],81)
    def test_backup_roundtrip_dedup_and_schema2_preservation(self):
        self.apply();doc=self.store.export_backup();clone=Store(self.folder/'clone.db');clone.import_backup(self.admin,doc);clone.import_backup(self.admin,doc)
        self.assertEqual(len(clone.snapshot()['workbooks']),1);self.assertEqual(len(clone.snapshot()['batches']),2)
        self.assertEqual(base64.b64decode(clone.snapshot()['workbooks'][0]['base64']),self.raw)
    def test_readonly_import_and_source_edits_rejected(self):
        with self.assertRaises(Problem):self.store.import_workbook(self.staff,self.payload,str(uuid.uuid4()))
        self.apply();book=self.store.snapshot()['workbooks'][0]
        with self.assertRaises(Problem):self.store.mutate(self.admin,'workbooks',book,str(uuid.uuid4()),book['id'])
    def test_legacy_histories_filters_keep_unknown_barn_unassigned(self):
        self.apply();d=self.store.snapshot();rows=filter_rows('movements',d,{'from':['2026-10-13'],'to':['2026-10-14'],'type':['sale']})
        self.assertEqual(sum(r['quantity'] for r in rows),5);self.assertTrue(any(r['batch_id'] is None for r in rows))
        first=next(b for b in d['batches'] if b['legacy_barn']==1)
        scoped=filter_rows('movements',d,{'barn_id':[first['barn_id']],'type':['sale']});self.assertEqual(sum(r['quantity'] for r in scoped),2)
        self.assertEqual(statistics(d,{'from':['2026-10-12'],'to':['2026-10-14']})['interval']['death'],3)
        self.assertIsNone(statistics(d,{'from':['2026-10-12'],'to':['2026-10-14'],'barn_id':[first['barn_id']]})['interval']['sale'])
    def test_new_and_legacy_same_barn_batches_do_not_mix(self):
        self.apply();d=self.store.snapshot();old=d['batches'][0]
        new=self.store.mutate(self.admin,'batches',{'barn_id':old['barn_id'],'name':'New batch','group':'','entry_date':'2026-10-15','entry_count':10,'entry_age_days':None,'status':'active'},str(uuid.uuid4()))
        d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15',[new['id']])['remaining'],10)
        self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],100)
    def test_full_farm_before_known_source_period_is_unknown_single_unborn_batch_is_zero(self):
        self.apply();d=self.store.snapshot()
        self.assertIsNone(statistics(d,{'to':['2026-01-01']})['cumulative']['remaining'])
        self.assertEqual(statistics(d,{'to':['2026-01-01'],'batch_id':[d['batches'][0]['id']]})['cumulative']['remaining'],0)
    def test_closed_barn_final_stock_and_first_entry_age(self):
        self.store.import_workbook(self.admin,self.payload|{'closed_barns':[2]},str(uuid.uuid4()));d=self.store.snapshot();closed=next(b for b in d['batches'] if b['legacy_barn']==2)
        self.assertEqual(closed['status'],'ended');self.assertEqual(herd(d['batches'],d['movements'],'2026-10-14',[closed['id']])['remaining'],0)
        self.assertEqual(age(closed,'2026-10-14'),105)
    def test_confirmed_empty_period_excluded_from_fcr_but_nonzero_feed_is_not_hidden(self):
        self.store.import_workbook(self.admin,self.payload|{'closed_barns':[2]},str(uuid.uuid4()));d=self.store.snapshot();live=next(b for b in d['batches'] if b['legacy_barn']==1);closed=next(b for b in d['batches'] if b['legacy_barn']==2)
        for on,mean in [('2026-10-15',50),('2026-10-29',60)]:self.store.mutate(self.admin,'weights',{'date':on,'batch_id':live['id'],'count':2,'total_kg':2*mean,'representative':True},str(uuid.uuid4()))
        self.store.mutate(self.admin,'usages',{'start':'2026-10-15','end':'2026-10-29','batch_id':live['id'],'method':'direct','kg':2250},str(uuid.uuid4()))
        query={'group':['JD-TEST'],'to':['2026-10-29']};result=statistics(self.store.snapshot(),query)
        self.assertEqual(result['aggregate_fcr'],2.5);self.assertEqual(result['empty_fcr_batches'],1);self.assertEqual(result['incomplete_fcr_batches'],0)
        self.store.mutate(self.admin,'usages',{'start':'2026-10-15','end':'2026-10-29','batch_id':closed['id'],'method':'direct','kg':10},str(uuid.uuid4()))
        self.assertIsNone(statistics(self.store.snapshot(),query)['aggregate_fcr'])
    def test_malformed_xlsx_and_duplicate_counts_rejected(self):
        with self.assertRaises(Invalid):review(b'not a zip')
        with self.assertRaises(Invalid):parse_counts('1/50\n1/49')
    def test_http_import_server_permissions_and_history_csv_consistency(self):
        server=Server(('127.0.0.1',0),self.store);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def call(path,body=None,csrf=None):
            headers={'Content-Type':'application/json','Idempotency-Key':str(uuid.uuid4())}
            if csrf:headers['X-CSRF-Token']=csrf
            return op.open(urllib.request.Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers))
        try:
            with call('/api/login',{'username':'reader','password':'legacy-test-password'}) as r:reader=json.load(r)
            with self.assertRaises(urllib.error.HTTPError) as e:call('/api/workbook/import',self.payload,reader['csrf'])
            self.assertEqual(e.exception.code,403)
            with call('/api/login',{'username':'tester','password':'legacy-test-password'}) as r:admin=json.load(r)
            with call('/api/workbook/import',self.payload,admin['csrf']) as r:self.assertEqual(r.status,201)
            query='from=2026-10-13&to=2026-10-14&type=sale'
            with call('/api/movements?'+query) as r:rows=json.load(r)
            with call('/api/export?kind=movements&'+query) as r:csv_rows=list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
            self.assertEqual({r['id'] for r in rows},{r['id'] for r in csv_rows});self.assertTrue(all(r['calculation_source']=='legacy_excel_readonly' for r in csv_rows))
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main(verbosity=2)
