import unittest, tempfile, uuid, threading, json, urllib.request, urllib.error, http.cookiejar, csv, io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.store import Store, Problem, VERSION
from app.domain import herd, age, combined_weights, performance, consumption
from app.server import Server, statistics, filter_rows

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'data.sqlite3')
        self.admin=self.store.create_user('admin','83000008')
        self.staff=self.store.create_user('staff','83000008','staff')
        self.viewer=self.store.create_user('viewer','83000008','viewer')
        self.barn=self.add('barns',name='9棟',group='A')
        self.batch=self.batch_new('B1',1000)
    def tearDown(self):self.temp.cleanup()
    def add(self,kind,**d):return self.store.mutate(self.admin,kind,d,str(uuid.uuid4()))
    def batch_new(self,name,n,barn=None,**kwargs):return self.add('batches',barn_id=(barn or self.barn)['id'],name=name,group='A',entry_date='2026-01-01',entry_count=n,entry_age_days=70,status='active',**kwargs)
    def move(self,kind,q,date='2026-01-02',batch=None,**kwargs):return self.add('movements',date=date,batch_id=(batch or self.batch)['id'],type=kind,quantity=q,**kwargs)
    def weight(self,date,mean,count=2,batch=None,**kwargs):return self.add('weights',date=date,batch_id=(batch or self.batch)['id'],count=count,total_kg=mean*count,representative=True,**kwargs)
    def usage(self,start,end,kg,batch=None):return self.add('usages',batch_id=(batch or self.batch)['id'],start=start,end=end,method='direct',kg=kg)
    def perf(self,batch=None):
        d=self.store.snapshot();return performance(batch or self.batch,d['batches'],d['movements'],d['weights'],d['usages'],d['deliveries'],'2026-02-01')
    def balance(self,on='2026-02-01',ids=None):
        d=self.store.snapshot();return herd(d['batches'],d['movements'],on,ids)
    def test_01_basic_herd_rule(self):
        self.move('sale',150);self.move('cull',20);self.move('death',5)
        h=self.balance();self.assertEqual(h['remaining'],825);self.assertEqual(h['outgoing'],170);self.assertEqual(h['survival'],99.5)
    def test_02_old_new_batch_isolation(self):
        new=self.batch_new('B2',100);self.move('death',5)
        self.assertEqual(self.balance(ids=[new['id']])['remaining'],100)
    def test_03_historical_date(self):
        self.move('sale',100,date='2026-01-20');self.assertEqual(self.balance('2026-01-10')['remaining'],1000)
    def test_04_delivery_not_consumption_and_tons(self):
        self.add('deliveries',date='2026-01-02',kg=2000,display_unit='ton',vendor='養全',allocations=[{'batch_id':self.batch['id'],'kg':2000}])
        s=statistics(self.store.snapshot(),{});self.assertEqual(s['delivery_kg'],2000);self.assertIsNone(s['consumption_kg'])
    def test_05_shared_delivery_allocations(self):
        b=self.batch_new('B2',100)
        self.add('deliveries',date='2026-01-02',kg=2000,display_unit='ton',vendor='',allocations=[{'batch_id':self.batch['id'],'kg':500},{'batch_id':b['id'],'kg':1500}])
        d=self.store.snapshot();self.assertEqual(statistics(d,{})['delivery_kg'],2000);self.assertEqual(statistics(d,{'batch_id':[b['id']]})['delivery_kg'],1500)
        with self.assertRaises(Problem):self.add('deliveries',date='2026-01-02',kg=2000,display_unit='ton',vendor='',allocations=[{'batch_id':b['id'],'kg':100}])
    def test_confirmed_zero_consumption_is_distinct_from_unknown(self):
        self.usage('2026-01-01','2026-01-15',0)
        self.assertEqual(statistics(self.store.snapshot(),{})['consumption_kg'],0)

    def test_06_overlap_rejected_source_switch(self):
        u=self.usage('2026-01-01','2026-01-15',100)
        with self.assertRaises(Problem) as ctx:self.usage('2026-01-10','2026-01-20',100)
        self.assertEqual(ctx.exception.code,'overlapping_usage')
        self.store.mutate(self.admin,'usages',u|{'active':False},str(uuid.uuid4()),u['id'])
        self.add('usages',start='2026-01-01',end='2026-01-15',batch_id=self.batch['id'],method='inventory',opening=100,closing=20,loss=0,transfer_in=0,transfer_out=0)
        s=statistics(self.store.snapshot(),{});self.assertEqual(s['consumption_kg'],80)
    def test_07_weighted_mean(self):
        self.weight('2026-01-02',50,2);self.weight('2026-01-02',60,4)
        ws=combined_weights(self.store.snapshot()['weights']);self.assertAlmostEqual(ws[0]['mean'],340/6)
    def test_08_adg(self):
        self.weight('2026-01-01',50);self.weight('2026-01-15',61.2)
        self.assertAlmostEqual(self.perf()['adg'],0.8)
    def test_09_fcr(self):
        b=self.batch_new('100 head',100);self.weight('2026-01-01',50,batch=b);self.weight('2026-01-15',60,batch=b);self.usage('2026-01-01','2026-01-15',2500,batch=b)
        self.assertEqual(self.perf(b)['fcr'],2.5)
    def test_10_invalid_fcr_conditions(self):
        self.weight('2026-01-01',50);self.weight('2026-01-15',60)
        self.assertIsNone(self.perf()['fcr']);self.usage('2026-01-01','2026-01-15',2500)
        self.move('death',1);self.assertIsNone(self.perf()['fcr'])
        self.assertIn('movement_weight_required',self.perf()['reasons'])
    def test_single_weight_preserves_mean_without_adg_or_fcr(self):
        self.weight('2026-01-01',50)
        p=self.perf();self.assertEqual(p['last']['mean'],50);self.assertIsNone(p['adg']);self.assertIsNone(p['fcr'])
    def test_10b_zero_and_negative_gain(self):
        self.weight('2026-01-01',50);self.weight('2026-01-15',50);self.usage('2026-01-01','2026-01-15',100)
        self.assertIsNone(self.perf()['fcr']);self.assertIn('nonpositive_gain',self.perf()['reasons'])
        self.weight('2026-01-16',40);self.assertLess(self.perf()['adg'],0)
    def test_10c_corrected_movement_fcr(self):
        b=self.batch_new('100 head',100);self.weight('2026-01-01',50,batch=b);self.weight('2026-01-15',60,batch=b)
        self.move('sale',10,batch=b,total_weight_kg=550);self.usage('2026-01-01','2026-01-15',2375,batch=b)
        p=self.perf(b);self.assertEqual(p['gain'],950);self.assertEqual(p['fcr'],2.5)
    def test_11_filters_combined_and_date_only(self):
        self.move('sale',10);self.move('death',2,date='2026-01-03')
        d=self.store.snapshot();q={'from':['2026-01-02'],'to':['2026-01-02']}
        self.assertEqual(len(filter_rows('movements',d,q)),1)
        q|={'barn_id':[self.barn['id']],'batch_id':[self.batch['id']],'type':['sale']};self.assertEqual(len(filter_rows('movements',d,q)),1)
    def test_13_idempotency_concurrent(self):
        key=str(uuid.uuid4());body=dict(date='2026-01-02',batch_id=self.batch['id'],type='death',quantity=1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            ids=list(pool.map(lambda _:self.store.mutate(self.staff,'movements',body,key)['id'],range(6)))
        self.assertEqual(len(set(ids)),1);self.assertEqual(self.balance()['dead'],1)
        with self.assertRaises(Problem):self.store.mutate(self.staff,'movements',body|{'quantity':2},key)
    def test_13b_concurrent_capacity(self):
        body=dict(date='2026-01-02',batch_id=self.batch['id'],type='sale',quantity=600)
        def go(_):
            try:return self.store.mutate(self.staff,'movements',body,str(uuid.uuid4()))
            except Problem as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(go,range(2)))
        self.assertEqual(sum(isinstance(r,dict) for r in results),1);self.assertEqual(self.balance()['remaining'],400)
    def test_13c_optimistic_conflict(self):
        m=self.move('sale',10);self.store.mutate(self.admin,'movements',m|{'quantity':11},str(uuid.uuid4()),m['id'])
        with self.assertRaises(Problem) as e:self.store.mutate(self.admin,'movements',m|{'quantity':12},str(uuid.uuid4()),m['id'])
        self.assertEqual(e.exception.code,'revision_conflict')
    def test_14_roles(self):
        with self.assertRaises(Problem) as e:self.store.mutate(self.viewer,'movements',{},str(uuid.uuid4()))
        self.assertEqual(e.exception.status,403)
        with self.assertRaises(Problem):self.store.mutate(self.staff,'batches',{},str(uuid.uuid4()))
        m=self.move('death',1)
        with self.assertRaises(Problem):self.store.mutate(self.staff,'movements',m,str(uuid.uuid4()),m['id'])
    def test_age_and_transfer(self):
        target_barn=self.add('barns',name='10棟',group='A')
        target=self.batch_new('receiving',0,barn=target_barn,cohort_id=self.batch['id'])
        self.move('transfer',200,target_batch_id=target['id'])
        self.assertEqual(self.balance()['remaining'],1000);self.assertEqual(self.balance()['denominator'],1000)
        self.assertEqual(self.balance(ids=[target['id']])['remaining'],200);self.assertEqual(age(target,'2026-01-08'),77)
    def test_unknown_age_zero_denominator(self):
        b=self.add('batches',barn_id=self.barn['id'],name='unknown',entry_date='2026-01-01',entry_count=0,status='active')
        self.assertIsNone(age(b,'2026-01-02'));self.assertIsNone(self.balance(ids=[b['id']])['survival'])
    def test_count_date_validation_and_ended(self):
        for q in (0,-1,1.5,1001):
            with self.assertRaises(Problem):self.move('death',q)
        with self.assertRaises(Problem):self.move('death',1,date='2025-12-31')
        b=self.store.mutate(self.admin,'batches',self.batch|{'status':'ended'},str(uuid.uuid4()),self.batch['id'])
        with self.assertRaises(Problem):self.store.mutate(self.staff,'movements',dict(date='2026-01-02',batch_id=b['id'],type='death',quantity=1),str(uuid.uuid4()))
    def test_inventory_half_open_negative_and_recalculate(self):
        self.add('deliveries',date='2026-01-10',kg=20,display_unit='kg',vendor='',allocations=[{'batch_id':self.batch['id'],'kg':20}])
        a=self.add('usages',start='2026-01-01',end='2026-01-10',batch_id=self.batch['id'],method='inventory',opening=10,closing=20,loss=0,transfer_in=0,transfer_out=0)
        b=self.add('usages',start='2026-01-10',end='2026-01-20',batch_id=self.batch['id'],method='inventory',opening=20,closing=0,loss=0,transfer_in=0,transfer_out=0)
        ds=self.store.snapshot()['deliveries'];self.assertEqual(consumption(a,ds),-10);self.assertEqual(consumption(b,ds),40)
    def test_weight_individual_and_same_day_retention(self):
        a=self.add('weights',date='2026-01-02',batch_id=self.batch['id'],individual_kg=[10.123,20.456])
        self.assertEqual(a['count'],2);self.assertEqual(a['total_kg'],30.579)
        self.weight('2026-01-02',40);self.assertEqual(len(self.store.snapshot()['weights']),2)
    def test_backup_import_repeat_preserves_tombstone(self):
        m=self.move('death',1);doc=self.store.export_backup()
        a=self.store.import_backup(self.admin,doc);self.assertEqual(a['added'],0)
        self.store.mutate(self.admin,'movements',m,str(uuid.uuid4()),m['id'],delete=True)
        self.store.import_backup(self.admin,doc);self.assertEqual(len(self.store.snapshot()['movements']),0)
        self.assertTrue(list((Path(self.temp.name)/'backups').glob('before-import*.sqlite3')))
    def test_backup_after_delete_restores_tombstones_and_remains_repeatable(self):
        m=self.move('death',1)
        self.store.mutate(self.admin,'movements',m,str(uuid.uuid4()),m['id'],delete=True)
        doc=self.store.export_backup();fresh=Store(Path(self.temp.name)/'deleted-restore.sqlite3')
        fresh.import_backup(self.admin,doc);fresh.import_backup(self.admin,doc)
        self.assertEqual(len(fresh.snapshot()['movements']),0)
        db=fresh.connect();row=db.execute('SELECT revision,deleted,data FROM records WHERE id=?',(m['id'],)).fetchone()
        self.assertEqual(row['deleted'],1);self.assertEqual(row['revision'],json.loads(row['data'])['revision']);db.close()

    def test_restore_new_database_accounts_and_history(self):
        self.move('death',1);doc=self.store.export_backup();fresh=Store(Path(self.temp.name)/'restored.sqlite3')
        restored=fresh.import_backup(self.admin,doc);self.assertGreater(restored['added'],0)
        self.assertEqual(len(fresh.snapshot()['movements']),1)
        db=fresh.connect();self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],3);self.assertGreater(db.execute('SELECT count(*) FROM audit').fetchone()[0],3);db.close()
    def test_retroactive_negative_and_referenced_delete(self):
        self.move('sale',900,date='2026-01-20')
        with self.assertRaises(Problem):self.move('sale',200,date='2026-01-02')
        with self.assertRaises(Problem):self.store.mutate(self.admin,'batches',self.batch,str(uuid.uuid4()),self.batch['id'],delete=True)
        self.assertEqual(len(self.store.snapshot()['batches']),1)
    def test_aggregate_fcr_complete_same_period_only(self):
        b=self.batch_new('second',100);self.weight('2026-01-01',50);self.weight('2026-01-15',60);self.usage('2026-01-01','2026-01-15',25000)
        self.assertIsNone(statistics(self.store.snapshot(),{})['aggregate_fcr'])
        self.weight('2026-01-01',50,batch=b);self.weight('2026-01-15',60,batch=b);self.usage('2026-01-01','2026-01-15',3000,batch=b)
        self.assertAlmostEqual(statistics(self.store.snapshot(),{})['aggregate_fcr'],28000/11000)

    def test_schema_upgrade_backs_up_and_preserves_users_records(self):
        self.move('death',1)
        db=self.store.connect();before=[tuple(r) for r in db.execute('SELECT id,username,hash,role FROM users')];db.execute('ALTER TABLE users DROP COLUMN revision');db.execute('PRAGMA user_version=1');db.commit();db.close()
        upgraded=Store(self.store.path);db=upgraded.connect()
        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
        self.assertEqual([tuple(r) for r in db.execute('SELECT id,username,hash,role FROM users')],before);db.close()
        self.assertEqual(len(upgraded.snapshot()['movements']),1)
        self.assertTrue(list((Path(self.temp.name)/'backups').glob('before-migration*.sqlite3')))
    def test_transfer_manual_age_priority(self):
        target=self.batch_new('transfer',0,cohort_id=self.batch['id'])
        target=self.store.mutate(self.admin,'batches',target|{'entry_age_days':81},str(uuid.uuid4()),target['id'])
        self.assertEqual(target['entry_age_days'],81)
        target=self.store.mutate(self.admin,'batches',target|{'name':'edited'},str(uuid.uuid4()),target['id'])
        self.assertEqual(target['entry_age_days'],81)
    def test_arrivals_adjustments_and_survival_denominator(self):
        self.move('arrival',100);self.move('adjustment',-5);self.move('death',11)
        h=self.balance();self.assertEqual(h['denominator'],1100);self.assertEqual(h['survival'],99);self.assertEqual(h['remaining'],1084)
    def test_same_day_endpoint_order_blocks_fcr(self):
        self.weight('2026-01-01',50);self.weight('2026-01-15',60);self.usage('2026-01-01','2026-01-15',100)
        self.move('sale',10,date='2026-01-15',total_weight_kg=600)
        self.assertIsNone(self.perf()['fcr']);self.assertIn('endpoint_movement_order_unknown',self.perf()['reasons'])
    def test_inventory_vendor_item_and_usage_filter_half_open(self):
        self.add('deliveries',date='2026-01-02',kg=100,display_unit='kg',vendor='養全',item='A',allocations=[{'batch_id':self.batch['id'],'kg':100}])
        self.add('deliveries',date='2026-01-02',kg=200,display_unit='kg',vendor='新農科',item='B',allocations=[{'batch_id':self.batch['id'],'kg':200}])
        u=self.add('usages',start='2026-01-01',end='2026-01-10',batch_id=self.batch['id'],method='inventory',opening=10,closing=0,vendor='養全',item='A')
        d=self.store.snapshot();self.assertEqual(consumption(u,d['deliveries']),110)
        self.assertEqual(len(filter_rows('usages',d,{'from':['2026-01-10']})),0)
        self.assertEqual(len(filter_rows('usages',d,{'vendor':['新農科']})),0)
    def test_malformed_backup_rejected_atomically(self):
        doc=self.store.export_backup();doc['records'][0]['id']='<script>'
        with self.assertRaises(Problem):self.store.import_backup(self.admin,doc)
        self.assertEqual(len(self.store.snapshot()['barns']),1)

class HTTPTests(AppTests):
    def setUp(self):
        super().setUp();self.server=Server(('127.0.0.1',0),self.store);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();super().tearDown()
    def client(self,username):
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        req=urllib.request.Request(self.base+'/api/login',data=json.dumps({'username':username,'password':'83000008'}).encode(),headers={'Content-Type':'application/json'})
        with op.open(req) as r:me=json.load(r)
        return op,me
    def test_http_auth_csrf_roles(self):
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.base+'/api/snapshot')
        self.assertEqual(e.exception.code,401)
        op,me=self.client('viewer');body=json.dumps(dict(date='2026-01-02',batch_id=self.batch['id'],type='sale',quantity=1)).encode()
        for headers,status in (({},403),({'X-CSRF-Token':me['csrf']},403)):
            with self.assertRaises(urllib.error.HTTPError) as e:op.open(urllib.request.Request(self.base+'/api/movements',data=body,headers=headers))
            self.assertEqual(e.exception.code,status)
        with self.assertRaises(urllib.error.HTTPError):op.open(self.base+'/api/backup')
    def test_http_csv_filters_and_injection(self):
        self.move('sale',10,note='=HYPERLINK("evil")');self.move('death',2,date='2026-01-03')
        op,me=self.client('admin');q='from=2026-01-02&to=2026-01-02&batch_id='+self.batch['id']+'&barn_id='+self.barn['id']+'&type=sale'
        with op.open(self.base+'/api/movements?'+q) as r:listed=json.load(r)
        with op.open(self.base+'/api/export?kind=movements&'+q) as r:export=list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
        self.assertEqual(len(export),len(listed));self.assertEqual(export[0]['id'],listed[0]['id']);self.assertTrue(export[0]['note'].startswith("'="))
    def test_http_snapshot_cursor_is_consistent(self):
        op,me=self.client('admin')
        with op.open(self.base+'/api/snapshot') as r:first=json.load(r)
        with op.open(self.base+'/api/snapshot?since='+first['cursor']) as r:self.assertTrue(json.load(r)['unchanged'])
        self.move('death',1)
        with op.open(self.base+'/api/snapshot?since='+first['cursor']) as r:changed=json.load(r)
        self.assertEqual(len(changed['movements']),1);self.assertNotEqual(changed['cursor'],first['cursor'])

    def test_http_cookie_and_manifest_security(self):
        op,me=self.client('admin')
        with op.open(self.base+'/manifest.webmanifest') as r:manifest=json.load(r)
        self.assertEqual(manifest['display'],'standalone')
        with op.open(self.base+'/') as r:self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])

    def test_http_account_revision_and_disable(self):
        op,me=self.client('admin')
        with op.open(self.base+'/api/users') as r:users=json.load(r)
        staff=next(u for u in users if u['role']=='staff')
        before={k:staff[k] for k in ('role','active','revision')}
        body=json.dumps({'role':'viewer','active':True,'before':before,'password':'83000003'}).encode()
        headers={'Content-Type':'application/json','X-CSRF-Token':me['csrf']}
        with op.open(urllib.request.Request(self.base+'/api/users/'+staff['id'],data=body,headers=headers,method='PUT')) as r:self.assertEqual(r.status,200)
        with self.assertRaises(urllib.error.HTTPError) as e:op.open(urllib.request.Request(self.base+'/api/users/'+staff['id'],data=body,headers=headers,method='PUT'))
        self.assertEqual(e.exception.code,409)

# Avoid repeating domain tests on the HTTP subclass.
for name in list(AppTests.__dict__):
    if name.startswith('test_') and name not in HTTPTests.__dict__:setattr(HTTPTests,name,None)

if __name__=='__main__':unittest.main(verbosity=2)
