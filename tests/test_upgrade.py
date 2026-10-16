"""1.4.0 regressions: synthetic data, isolated databases, no production writes."""
import base64,copy,http.cookiejar,io,json,sqlite3,tempfile,threading,unittest,urllib.error,urllib.request,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile
from app.store import Store,Problem,verify_password
from app.domain import performance,combined_weights,herd
from app.accounts import change_password,issue_setup,activate,ensure_role_accounts
from app.cloud_store import CloudStore,migrate,upgrade_cloud,read_document,fingerprint
from app.server import Server,filter_rows,statistics
from cloud_fixture import HranaFixture
from legacy_fixture import workbook_fixture


def advanced_workbook(barn=True):
    """One actual new event, not an extra copy of the old cumulative totals."""
    original=workbook_fixture();out=io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source,ZipFile(out,'w') as target:
        for name in source.namelist():
            data=source.read(name)
            if name.endswith('sheet1.xml'):
                text=data.decode()
                for ref,value in [('B1','46310'),('S4','88'),('S6','88'),('Z4','6'),('Z6','6'),('AF6','6')]:
                    import re
                    text=re.sub(r'(<c r="'+ref+r'"><v>)[^<]+',lambda m:m[1]+value,text)
                data=text.encode()
            if name=='xl/comments1.xml':
                text=data.decode().replace('10/14死2頭(2棟)','10/14死2頭(2棟)\n10/15死2頭'+('(2棟)' if barn else ''))
                data=text.encode()
            target.writestr(name,data)
    return out.getvalue()


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name);self.store=Store(self.path/'db.sqlite3')
        self.admin=self.store.create_user('owner','83000010')
        self.staff=self.store.create_user('writer','83000010','staff')
        self.viewer=self.store.create_user('reader','83000010','viewer')
        self.barn=self.store.mutate(self.admin,'barns',{'name':'1棟','group':'A'},str(uuid.uuid4()))
        self.batch=self.store.mutate(self.admin,'batches',{'name':'B','barn_id':self.barn['id'],'group':'A','entry_date':'2026-01-01','entry_count':100,'entry_age_days':70,'status':'active','entry_mean_kg':50},str(uuid.uuid4()))
    def tearDown(self):self.temp.cleanup()
    def test_entry_mean_and_first_sample_calculate_adg_without_fake_fcr(self):
        self.store.mutate(self.admin,'weights',{'date':'2026-01-15','batch_id':self.batch['id'],'count':2,'total_kg':122.4,'representative':True},str(uuid.uuid4()))
        d=self.store.snapshot();p=performance(self.batch,d['batches'],d['movements'],d['weights'],d['usages'],d['deliveries'],'2026-01-15')
        self.assertAlmostEqual(p['adg'],.8);self.assertEqual(p['days'],14);self.assertEqual(p['first']['source'],'entry_mean');self.assertIsNone(p['fcr'])
    def test_entry_mean_invalid_date_and_nonpositive_weight_rejected(self):
        for patch in ({'entry_mean_kg':0},{'entry_mean_kg':-1},{'entry_mean_date':'2025-12-31'}):
            with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',self.batch|patch,str(uuid.uuid4()),self.batch['id'])
    def test_undated_source_weight_never_uses_entry_date_as_measurement_date(self):
        from unittest.mock import patch
        d=self.store.snapshot();row={'id':'source-unknown','date':None,'entry_date':'2026-01-01','batch_id':self.batch['id'],'mean_kg':50,'source_mean':True}
        with patch('app.server.source_history',return_value=[row]):
            self.assertEqual(filter_rows('weights',d,{'from':['2026-01-01'],'to':['2026-01-01']}),[])
            self.assertEqual(len(filter_rows('weights',d,{})),1)

    def test_source_means_are_not_averaged_without_counts(self):
        rows=[{'id':'a','batch_id':'b','date':'2026-01-01','count':None,'total_kg':None,'mean_kg':50}, {'id':'b','batch_id':'b','date':'2026-01-01','count':None,'total_kg':None,'mean_kg':60}]
        self.assertEqual(combined_weights(rows),[])
        self.assertEqual(combined_weights(rows[:1])[0]['mean'],50)
    def test_staff_can_correct_own_record_only_and_cannot_delete(self):
        original=self.store.mutate(self.staff,'movements',{'date':'2026-01-02','batch_id':self.batch['id'],'type':'death','quantity':1},str(uuid.uuid4()))
        updated=self.store.mutate(self.staff,'movements',original|{'quantity':2},str(uuid.uuid4()),original['id'])
        self.assertEqual(updated['quantity'],2)
        with self.assertRaises(Problem):self.store.mutate(self.viewer,'movements',updated,str(uuid.uuid4()),updated['id'])
        with self.assertRaises(Problem):self.store.mutate(self.staff,'movements',updated,str(uuid.uuid4()),updated['id'],True)
        other=self.store.mutate(self.admin,'movements',{'date':'2026-01-02','batch_id':self.batch['id'],'type':'death','quantity':1},str(uuid.uuid4()))
        with self.assertRaises(Problem):self.store.mutate(self.staff,'movements',other|{'quantity':2},str(uuid.uuid4()),other['id'])
    def test_every_role_can_change_own_password_without_hash_in_audit(self):
        for user in (self.admin,self.staff,self.viewer):
            change_password(self.store,user,'83000010','83000013')
        db=self.store.connect()
        try:
            for user in db.execute('SELECT * FROM users'):self.assertTrue(verify_password('83000013',user['hash']))
            audit=''.join(str(tuple(r)) for r in db.execute('SELECT before_value,after_value FROM audit'))
            self.assertNotIn('83000013',audit);self.assertNotIn('83000010',audit)
        finally:db.close()
    def test_wrong_current_password_preserves_account(self):
        with self.assertRaises(Problem) as error:change_password(self.store,self.viewer,'incorrect-value','83000013')
        self.assertEqual(error.exception.code,'invalid_current_password')
        db=self.store.connect()
        try:self.assertTrue(verify_password('83000010',db.execute('SELECT hash FROM users WHERE id=?',(self.viewer['id'],)).fetchone()[0]))
        finally:db.close()
    def test_setup_link_is_one_use_and_reissue_invalidates_previous(self):
        first=issue_setup(self.store,self.admin,self.viewer['id'],1)
        second=issue_setup(self.store,self.admin,self.viewer['id'],first['revision'])
        with self.assertRaises(Problem):activate(self.store,'reader',first['token'],'83000013')
        activate(self.store,'reader',second['token'],'83000013')
        with self.assertRaises(Problem):activate(self.store,'reader',second['token'],'83000001')
        db=self.store.connect()
        try:
            row=db.execute('SELECT * FROM account_security WHERE user_id=?',(self.viewer['id'],)).fetchone()
            self.assertEqual(row['must_change'],0);self.assertIsNone(row['setup_hash'])
            self.assertNotIn(second['token'],str([tuple(r) for r in db.execute('SELECT * FROM audit')]))
        finally:db.close()
    def test_setup_expiry_and_nonadmin_denied(self):
        with self.assertRaises(Problem):issue_setup(self.store,self.staff,self.viewer['id'],1)
        link=issue_setup(self.store,self.admin,self.viewer['id'],1);db=self.store.connect();db.execute('UPDATE account_security SET setup_expires=0');db.commit();db.close()
        with self.assertRaises(Problem):activate(self.store,'reader',link['token'],'83000013')
    def test_setup_concurrency_consumes_token_once(self):
        link=issue_setup(self.store,self.admin,self.viewer['id'],1)
        def attempt(_):
            try:activate(self.store,'reader',link['token'],'83000013');return True
            except Problem:return False
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(attempt,range(2))),1)
    def test_role_account_creation_is_repeatable_and_preserves_originals(self):
        db=self.store.connect();before=[tuple(r) for r in db.execute('SELECT * FROM users')];db.close()
        first=ensure_role_accounts(self.store,self.admin);second=ensure_role_accounts(self.store,self.admin)
        self.assertEqual(sum(r['created'] for r in first),3);self.assertEqual(sum(r['created'] for r in second),0)
        db=self.store.connect()
        try:
            for original in before:self.assertEqual(tuple(db.execute('SELECT * FROM users WHERE id=?',(original[0],)).fetchone()),original)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM account_security WHERE must_change=1').fetchone()[0],3)
        finally:db.close()
    def test_security_backup_restores_flags_without_reactivating_old_links(self):
        link=issue_setup(self.store,self.admin,self.viewer['id'],1);document=self.store.export_backup();clone=Store(self.path/'restore.db')
        clone.import_backup(self.admin,document);db=clone.connect()
        try:
            row=db.execute('SELECT * FROM account_security WHERE user_id=?',(self.viewer['id'],)).fetchone();self.assertEqual(row['must_change'],1);self.assertIsNone(row['setup_hash'])
        finally:db.close()
    def test_restored_backup_retains_original_request_and_does_not_rebook_retry(self):
        key=str(uuid.uuid4());payload={'name':'backup-request-check','group':''}
        first=self.store.mutate(self.admin,'barns',payload,key)
        clone=Store(self.path/'restore-idempotency.db');clone.import_backup(self.admin,self.store.export_backup())
        repeated=clone.mutate(self.admin,'barns',payload,key)
        self.assertEqual(first,repeated);self.assertEqual(len(clone.snapshot()['barns']),2)

    def test_cloud_schema_upgrade_preserves_original_data(self):
        fixture=HranaFixture(self.path/'remote.db');cloud=CloudStore('libsql://test.turso.io','synthetic-token',fixture)
        try:
            migrate(self.store,cloud);db=sqlite3.connect(fixture.path);db.execute('DROP TABLE account_security');db.execute("UPDATE cloud_metadata SET value='3'");db.commit();db.close()
            old=cloud.connect();before=read_document(old);old.close()
            upgrade_cloud(cloud,finalize=False);cloud.assert_ready()
            compat=cloud.connect();self.assertEqual(compat.execute("SELECT value FROM cloud_metadata WHERE key='schema_version'").fetchone()[0],'3');compat.close()
            upgrade_cloud(cloud);cloud.assert_ready();new=cloud.connect()
            try:self.assertEqual(fingerprint(before),fingerprint(read_document(new)))
            finally:new.close()
        finally:fixture.close()


class WorkbookUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db.sqlite3');self.admin=self.store.create_user('owner','83000010')
        self.original={'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_text':'1/49\n2/50','counts_as_of':'2026-10-12','closed_barns':[],'source_url':''}
        self.store.import_workbook(self.admin,self.original,str(uuid.uuid4()))
        self.payload={'filename':'synthetic-update.xlsx','base64':base64.b64encode(advanced_workbook()).decode(),'source_url':''}
    def tearDown(self):self.temp.cleanup()
    def second(self):return next(b for b in self.store.snapshot()['batches'] if b['legacy_barn']==2)
    def test_incremental_import_retains_batches_and_avoids_duplicate_manual_death(self):
        b=self.second();manual=self.store.mutate(self.admin,'movements',{'batch_id':b['id'],'date':'2026-10-15','type':'death','quantity':2},str(uuid.uuid4()))
        before=[(b['id'],b['revision']) for b in self.store.snapshot()['batches']]
        preview=self.store.validate('workbooks',self.payload,self.store.snapshot(),self.admin)
        self.assertEqual(preview['update_summary']['matched_manual'],1)
        self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()));self.assertTrue(self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()))['already_imported'])
        d=self.store.snapshot();self.assertEqual([(b['id'],b['revision']) for b in d['batches']],before)
        h=herd(d['batches'],d['movements'],'2026-10-15');self.assertEqual(h['remaining'],88);self.assertEqual(h['dead'],6)
        history=filter_rows('movements',d,{'from':['2026-10-15'],'to':['2026-10-15'],'type':['death']})
        self.assertEqual([r['id'] for r in history],[manual['id']])
    def test_conflict_keeps_manual_and_preserves_source(self):
        b=self.second();self.store.mutate(self.admin,'movements',{'batch_id':b['id'],'date':'2026-10-15','type':'death','quantity':1},str(uuid.uuid4()))
        result=self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()));self.assertEqual(len(result['update_summary']['pending_cohorts']),1)
        d=self.store.snapshot();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],89)
        self.assertEqual(base64.b64decode(d['workbooks'][-1]['base64']),advanced_workbook())
    def test_unmatched_known_barn_event_updates_stock_once(self):
        self.store.import_workbook(self.admin,self.payload,str(uuid.uuid4()));d=self.store.snapshot()
        self.assertEqual(len(d['movements']),1);self.assertTrue(d['movements'][0]['_source_derived'])
        self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],88)
        self.assertEqual(sum(r['quantity'] for r in filter_rows('movements',d,{'from':['2026-10-15']})),2)
    def test_unassigned_outflow_never_becomes_fake_single_barn_stock(self):
        payload=self.payload|{'base64':base64.b64encode(advanced_workbook(False)).decode()}
        self.store.import_workbook(self.admin,payload,str(uuid.uuid4()));d=self.store.snapshot()
        self.assertEqual(herd(d['batches'],d['movements'],'2026-10-15')['remaining'],88)
        self.assertIsNone(herd(d['batches'],d['movements'],'2026-10-15',[self.second()['id']])['remaining'])
    def test_source_mean_visible_without_fake_sample_count(self):
        rows=filter_rows('weights',self.store.snapshot(),{})
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['mean_kg'],50);self.assertIsNone(rows[0]['count']);self.assertIsNone(rows[0]['total_kg'])
    def test_preview_conflict_detects_concurrent_manual_write(self):
        preview=self.store.validate('workbooks',self.payload,self.store.snapshot(),self.admin)
        self.store.mutate(self.admin,'movements',{'batch_id':self.second()['id'],'date':'2026-10-15','type':'death','quantity':1},str(uuid.uuid4()))
        with self.assertRaises(Problem) as error:self.store.import_workbook(self.admin,self.payload|{'preview_token':preview['update_summary']['preview_token']},str(uuid.uuid4()))
        self.assertEqual(error.exception.code,'revision_conflict')
    def test_manual_entry_denominator_requires_source_and_cohort_total_balance(self):
        d=self.store.snapshot();a,b=d['batches']
        with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',a|{'entry_count':50},str(uuid.uuid4()),a['id'])
        self.store.mutate(self.admin,'batches',a|{'entry_count':50,'entry_count_source':'verified arrival sheet'},str(uuid.uuid4()),a['id'])
        with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',b|{'entry_count':49,'entry_count_source':'verified arrival sheet'},str(uuid.uuid4()),b['id'])
        self.store.mutate(self.admin,'batches',b|{'entry_count':50,'entry_count_source':'verified arrival sheet'},str(uuid.uuid4()),b['id'])
        self.assertEqual(herd(self.store.snapshot()['batches'],[], '2026-10-14',[a['id']])['survival'],98)
