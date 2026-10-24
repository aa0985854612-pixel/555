"""Shortcut records share the real herd/feed records and derived inventory."""
import copy,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app.store import Store,Problem
from app.domain import Invalid,herd,consumption,performance
from app.quick_record import parse,preview,save,history
from app.bin_stock import stock
from app.server import filter_rows,statistics
from app.cloud_store import CloudStore,migrate,read_document
from cloud_fixture import HranaFixture


class QuickParserTests(unittest.TestCase):
    def test_all_requested_feed_variants_and_fullwidth_decimal(self):
        cases={'10/15 13棟2噸':('2026-10-15',2000),'10/15 13棟 2噸':('2026-10-15',2000),'10月15日13棟2噸':('2026-10-15',2000),'13棟今天到料2噸':('2026-10-24',2000),'13棟到料2000公斤':('2026-10-24',2000),'13棟飼料2T':('2026-10-24',2000),'１０／１５　１３棟１．５噸':('2026-10-15',1500),'13棟到料1,500公斤':('2026-10-24',1500)}
        for text,(date,kg) in cases.items():
            with self.subTest(text=text):
                p=parse(text,'2026-10-24');self.assertFalse(p['errors']);self.assertEqual(p['date'],date);self.assertEqual(p['barn_number'],13);self.assertEqual(p['type'],'delivery');self.assertEqual(p['quantity']*(1000 if p['unit']=='ton' else 1),kg)
    def test_types_are_distinct_and_units_validated(self):
        for word,type in [('叫料','order'),('死','death'),('淘汰','cull'),('出豬','sale'),('進豬','arrival')]:
            p=parse('13棟'+word+('2噸' if type=='order' else '3隻'),'2026-10-24');self.assertFalse(p['errors']);self.assertEqual(p['type'],type)
        for text in ('13棟死1.5隻','13棟進豬2噸','13棟到料3隻','13棟死2隻出豬3隻','13棟2噸14棟3噸','10/15 10/16 13棟2噸','13棟2噸另外3','13棟0噸','13棟-1噸','10/32 13棟2噸','2噸','13棟','13棟3隻'):
            with self.subTest(text=text):self.assertTrue(parse(text,'2026-10-24')['errors'])
        for text in ('13棟不要出豬3隻','13棟還沒到料2噸','13棟叫量2噸','chuong 13 chua nhan cam 2 tan'):
            with self.subTest(text=text):self.assertTrue(parse(text,'2026-10-24')['errors'])
        for text in ('10 / 15 13棟2噸','13棟叫飼料2噸','13棟請登記死了3隻'):
            with self.subTest(text=text):self.assertFalse(parse(text,'2026-10-24')['errors'])
    def test_vietnamese_dates_text_and_defaults(self):
        for text,type in [('15/10 chuồng 13 nhận cám 2 tấn','delivery'),('chuồng 13 đặt cám 2000 kg','order'),('chuồng 13 chết 3 con','death'),('chuồng 13 loại 2 con','cull'),('chuồng 13 xuất heo 8 con','sale'),('chuồng 13 nhập heo 20 con','arrival')]:
            p=parse(text,'2026-10-24','vi');self.assertFalse(p['errors'],p);self.assertEqual(p['type'],type)
        self.assertEqual(parse('15/10 chuồng 13 nhận cám 2 tấn','2026-10-24','vi')['date'],'2026-10-15');self.assertIn('quick_date_day_month',parse('5/10 chuồng 13 2 tan','2026-10-24','vi')['notes']);self.assertEqual(parse('2025-10-15 13棟2噸','2026-10-24')['date'],'2025-10-15')


class QuickRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.admin=self.store.create_user('owner','83000011');self.staff=self.store.create_user('writer','83000012','staff');self.other=self.store.create_user('other','83000013','staff');self.viewer=self.store.create_user('reader','83000014','viewer')
        self.barn=self.add('barns',name='13棟');self.batch=self.add('batches',barn_id=self.barn['id'],name='JD-test',entry_date='2026-01-01',entry_age_days=70,entry_count=100,status='active');self.bin=self.add('feed_bins',name='13',barn_ids=[self.barn['id']],vendor='新農科',active=True,capacity_kg=10000,safe_fill_percent=85,inventory_enabled=True,inventory_date='2026-10-01',inventory_opening_kg=1000)
        self.clock=patch('app.quick_record.today',return_value='2026-10-24');self.clock.start()
    def tearDown(self):self.clock.stop();self.tmp.cleanup()
    def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))
    def data(self):return self.store.snapshot(include_source=False)
    def document(self):
        db=self.store.connect()
        try:return read_document(db)
        finally:db.close()
    def request(self,text='10/15 13棟2噸',**patches):return {'text':text,'operation_id':str(uuid.uuid4()),'language':'zh'}|patches
    def prepare(self,request,user=None):return preview(self.store,user or self.admin,request)
    def write(self,request,user=None,key=None,**patches):
        p=self.prepare(request,user);self.assertTrue(p['can_confirm'],p);body={'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']}|patches
        return save(self.store,user or self.admin,body,key or str(uuid.uuid4()))
    def inventory(self):return stock(self.data(),next(b for b in self.data()['feed_bins'] if b['id']==self.bin['id']),'2026-10-24')
    def edit_request(self,row,text,action='update'):return self.request(text,action=action,kind=row['kind'],id=row['id'],revision=row['revision'])

    def test_preview_never_writes_and_explicit_confirmation_required(self):
        request=self.request();before=self.document();p=self.prepare(request);self.assertTrue(p['can_confirm']);self.assertEqual(before,self.document());self.assertEqual(p['inventory']['before']['kg'],1000);self.assertEqual(p['inventory']['after']['kg'],3000)
        for confirmed in (False,'true',None):
            with self.assertRaises(Problem):save(self.store,self.admin,{'request':request,'preview_token':p['preview_token'],'confirmed':confirmed},str(uuid.uuid4()))
        self.assertEqual(before,self.document())
    def test_feed_arrival_is_real_delivery_and_updates_original_statistics(self):
        result=self.write(self.request());data=self.data();self.assertEqual(result['kind'],'deliveries');self.assertEqual(len(data['deliveries']),1);self.assertFalse(data['feed_orders']);r=data['deliveries'][0];self.assertEqual(r['kg'],2000);self.assertEqual(r['allocations'],[{'batch_id':self.batch['id'],'kg':2000}]);self.assertEqual(r['requested_barn_id'],self.barn['id']);self.assertEqual(self.inventory()['kg'],3000)
        s=statistics(data,{'batch_id':[self.batch['id']],'to':['2026-10-24']});self.assertEqual(s['delivery_kg'],2000);self.assertIsNone(s['consumption_kg']);self.assertEqual(len(filter_rows('deliveries',data,{'barn_id':[self.barn['id']]})),1)
    def test_kg_conversion_and_orders_never_increase_arrival_or_stock(self):
        self.write(self.request('13棟到料1500公斤'));self.assertEqual(self.inventory()['kg'],2500);self.write(self.request('13棟叫料2噸'));data=self.data();self.assertEqual(len(data['feed_orders']),1);self.assertEqual(data['feed_orders'][0]['kg'],2000);self.assertEqual(len(data['deliveries']),1);self.assertEqual(self.inventory()['kg'],2500)
    def test_death_cull_sale_arrival_reuse_herd_and_survival_rules(self):
        for text in ('13棟死3隻','13棟淘汰5隻','13棟出豬8隻','13棟進豬20隻'):self.write(self.request(text))
        d=self.data();h=herd(d['batches'],d['movements'],'2026-10-24',[self.batch['id']]);self.assertEqual(h['remaining'],104);self.assertEqual(h['dead'],3);self.assertEqual(h['culled'],5);self.assertEqual(h['sold'],8);self.assertEqual(h['added'],20);self.assertAlmostEqual(h['survival'],117/120*100)
    def test_edit_and_delete_arrival_recalculate_net_stock_and_history(self):
        first=self.write(self.request());edited=self.write(self.edit_request(first,'10/15 13棟1.5噸'));self.assertEqual(edited['id'],first['id']);self.assertEqual(len(self.data()['deliveries']),1);self.assertEqual(self.inventory()['kg'],2500)
        self.assertEqual(history(self.store,self.admin,{})['rows'][0]['status'],'modified');self.write(self.edit_request(edited,'',action='delete'));self.assertEqual(self.inventory()['kg'],1000);self.assertFalse(self.data()['deliveries']);self.assertEqual(history(self.store,self.admin,{})['rows'][0]['status'],'deleted')
    def test_shared_bin_adds_only_once_and_does_not_guess_per_batch_consumption(self):
        other=self.add('barns',name='14棟');batch=self.add('batches',barn_id=other['id'],name='JD-other',entry_date='2026-01-01',entry_count=100,status='active');self.store.mutate(self.admin,'feed_bins',self.bin|{'barn_ids':[self.barn['id'],other['id']]},str(uuid.uuid4()),self.bin['id']);self.write(self.request());data=self.data();r=data['deliveries'][0];self.assertFalse(r['allocations']);self.assertEqual(self.inventory()['kg'],3000)
        self.assertEqual(statistics(data,{'to':['2026-10-24']})['delivery_kg'],2000)
        for b in (self.batch,batch):
            stats=statistics(data,{'batch_id':[b['id']],'to':['2026-10-24']});self.assertIsNone(stats['delivery_kg']);self.assertEqual(stats['shared_delivery_kg'],2000)
        self.assertEqual(statistics(data,{'group':[''],'to':['2026-10-24']})['delivery_kg'],2000)
    def test_capacity_warning_requires_ack_and_safe_percent_is_configurable(self):
        request=self.request('13棟到料8噸');p=self.prepare(request);self.assertIn('quick_capacity_exceeded',p['warnings']);before=self.document()
        with self.assertRaises(Problem):self.write(request,acknowledged=[])
        self.assertEqual(before,self.document());self.write(request);self.assertEqual(self.inventory()['kg'],9000)
        bin=next(b for b in self.data()['feed_bins'] if b['id']==self.bin['id']);self.store.mutate(self.admin,'feed_bins',bin|{'safe_fill_percent':95},str(uuid.uuid4()),bin['id']);self.assertEqual(self.inventory()['safe_capacity_kg'],9500)
    def test_deleting_arrival_with_recorded_usage_warns_negative_stock(self):
        first=self.write(self.request());self.add('usages',batch_id=self.batch['id'],start='2026-10-01',end='2026-10-24',method='direct',kg=2000,feed_bin_id=self.bin['id']);self.assertEqual(self.inventory()['kg'],1000);request=self.edit_request(first,'',action='delete');p=self.prepare(request);self.assertIn('quick_stock_negative',p['warnings'])
        with self.assertRaises(Problem):self.write(request,acknowledged=[])
        self.assertEqual(self.inventory()['kg'],1000)
    def test_same_request_retry_and_duplicate_operation_never_add_twice(self):
        request=self.request();p=self.prepare(request);body={'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']};key=str(uuid.uuid4());first=save(self.store,self.admin,body,key);before=self.document();second=save(self.store,self.admin,body,key);self.assertEqual(first['id'],second['id']);self.assertEqual(before,self.document())
        p=self.prepare(request)
        with self.assertRaises(Problem):save(self.store,self.admin,body|{'preview_token':p['preview_token'],'acknowledged':p['warnings']},str(uuid.uuid4()))
        self.assertEqual(len(self.data()['deliveries']),1)
    def test_same_day_identical_new_operation_requires_separate_confirmation(self):
        self.write(self.request());second=self.request();p=self.prepare(second);self.assertIn('quick_possible_duplicate',p['warnings'])
        with self.assertRaises(Problem):self.write(second,acknowledged=[])
        self.write(second);self.assertEqual(len(self.data()['deliveries']),2);self.assertEqual(self.inventory()['kg'],5000)
    def test_retired_operation_cannot_be_reused_after_deletion(self):
        request=self.request();first=self.write(request);self.write(self.edit_request(first,'',action='delete'));before=self.document()
        with self.assertRaises(Problem):self.write(request)
        self.assertEqual(before,self.document())
    def test_original_unlinked_same_scope_arrival_is_detected_as_possible_duplicate(self):
        self.add('deliveries',date='2026-10-15',kg=2000,display_unit='ton',vendor='',allocations=[{'batch_id':self.batch['id'],'kg':2000}]);request=self.request();p=self.prepare(request);self.assertIn('quick_possible_duplicate',p['warnings'])
        with self.assertRaises(Problem):self.write(request,acknowledged=['quick_stock_unknown'])
        self.assertEqual(len(self.data()['deliveries']),1)
    def test_disabled_inventory_still_warns_if_load_alone_exceeds_configured_capacity(self):
        self.store.mutate(self.admin,'feed_bins',self.bin|{'inventory_enabled':False},str(uuid.uuid4()),self.bin['id']);request=self.request('13棟9噸');p=self.prepare(request);self.assertIn('quick_capacity_exceeded',p['warnings'])
        with self.assertRaises(Problem):self.write(request,acknowledged=[])
        self.assertFalse(self.data()['deliveries'])
    def test_moving_arrival_recalculates_both_bins_without_adding_another_record(self):
        first=self.write(self.request());other=self.add('feed_bins',name='13-2',barn_ids=[self.barn['id']],vendor='新農科',active=True,capacity_kg=10000,inventory_enabled=True,inventory_date='2026-10-01',inventory_opening_kg=200)
        request=self.edit_request(first,'10/15 13棟2噸');request['corrections']={'feed_bin_id':other['id']};p=self.prepare(request);self.assertEqual(len(p['inventories']),2);self.write(request);self.assertEqual(len(self.data()['deliveries']),1);self.assertEqual(self.inventory()['kg'],1000);self.assertEqual(stock(self.data(),other,'2026-10-24')['kg'],2200)
    def test_stale_proof_rejected_after_bin_capacity_or_stock_or_head_changes(self):
        request=self.request();p=self.prepare(request);self.write(self.request('13棟死1隻'));before=self.document()
        with self.assertRaises(Problem):save(self.store,self.admin,{'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']},str(uuid.uuid4()))
        self.assertEqual(before,self.document())
    def test_user_cannot_change_request_after_preview(self):
        request=self.request();p=self.prepare(request);request['text']='13棟9噸';before=self.document()
        with self.assertRaises(Problem):save(self.store,self.admin,{'request':request,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']},str(uuid.uuid4()))
        self.assertEqual(before,self.document())
    def test_viewer_foreign_staff_cannot_write_or_modify_and_owner_can_delete(self):
        with self.assertRaises(Problem):self.prepare(self.request(),self.viewer)
        first=self.write(self.request(),self.staff);request=self.edit_request(first,'13棟1.5噸')
        for user in (self.other,self.viewer):
            with self.assertRaises(Problem):self.prepare(request,user)
        self.assertFalse(next(r for r in history(self.store,self.other,{})['rows'] if r['record']['id']==first['id'])['can_edit']);self.write(self.edit_request(first,'',action='delete'),self.staff);self.assertFalse(self.data()['deliveries'])
    def test_invalid_dates_barns_nonpositive_amounts_and_insufficient_heads_rejected(self):
        for text in ('13棟0噸','13棟-2噸','10/32 13棟2噸','999棟2噸','13棟死101隻','13棟死1.5隻','2027-01-01 13棟2噸','13棟2噸14棟2噸'):
            before=self.document()
            try:p=self.prepare(self.request(text));self.assertFalse(p['can_confirm'],p)
            except (Problem,Invalid):pass
            self.assertEqual(before,self.document(),text)
    def test_multi_bin_requires_choice_and_never_selects_first_arbitrarily(self):
        other=self.add('feed_bins',name='13-2',barn_ids=[self.barn['id']],vendor='新農科',active=True);request=self.request();p=self.prepare(request);self.assertFalse(p['can_confirm']);self.assertIn('quick_bin_required',p['errors']);self.assertEqual(len(p['bin_choices']),2)
        request['corrections']={'feed_bin_id':other['id']};self.write(request);self.assertEqual(self.data()['deliveries'][0]['feed_bin_id'],other['id']);self.assertEqual(self.inventory()['kg'],1000)
    def test_unknown_batch_requires_manual_choice_and_before_entry_cannot_be_guessed(self):
        self.store.mutate(self.admin,'batches',self.batch|{'status':'ended'},str(uuid.uuid4()),self.batch['id']);request=self.request();p=self.prepare(request);self.assertFalse(p['can_confirm']);request['corrections']={'batch_id':self.batch['id']};self.write(request)
        self.assertFalse(self.prepare(self.request('2025-10-15 13棟2噸',corrections={'batch_id':self.batch['id']}))['can_confirm'])
    def test_old_unlinked_arrivals_make_stock_unknown_instead_of_inventing_zero(self):
        self.add('deliveries',date='2026-10-15',kg=1000,display_unit='kg',vendor='',allocations=[{'batch_id':self.batch['id'],'kg':1000}]);s=self.inventory();self.assertFalse(s['known']);self.assertIsNone(s['kg']);self.assertIn('inventory_delivery_bin_unknown',s['reasons']);self.assertIn('quick_stock_unknown',self.prepare(self.request())['warnings'])
    def test_direct_usage_decreases_stock_once_and_inventory_usage_can_be_unknown(self):
        self.write(self.request());self.add('usages',batch_id=self.batch['id'],start='2026-10-01',end='2026-10-24',method='direct',kg=500,feed_bin_id=self.bin['id']);self.assertEqual(self.inventory()['kg'],2500);self.assertEqual(self.inventory()['consumed_kg'],500)
    def test_usage_spanning_baseline_or_query_day_is_not_silently_split(self):
        self.add('usages',batch_id=self.batch['id'],start='2026-09-30',end='2026-10-25',method='direct',kg=500);s=self.inventory();self.assertIsNone(s['kg']);self.assertIn('inventory_usage_spans_date',s['reasons'])
    def test_multi_bin_usage_without_assignment_makes_stock_unknown(self):
        self.add('feed_bins',name='13-2',barn_ids=[self.barn['id']],vendor='新農科',active=True);self.add('usages',batch_id=self.batch['id'],start='2026-10-01',end='2026-10-24',method='direct',kg=500);self.assertIn('inventory_usage_bin_unknown',self.inventory()['reasons'])
    def test_shared_receipts_do_not_understate_inventory_derived_fcr_consumption(self):
        usage={'method':'inventory','batch_id':self.batch['id'],'start':'2026-10-01','end':'2026-10-24','opening':1000,'closing':500,'transfer_in':0,'transfer_out':0,'loss':0};delivery={'date':'2026-10-15','kg':2000,'vendor':'新農科','item':'','feed_bin_id':self.bin['id'],'target_batch_ids':[self.batch['id']],'allocations':[]};self.assertIsNone(consumption(usage,[delivery]));self.assertEqual(consumption(usage|{'method':'direct','kg':400},[delivery]),400)
    def test_quick_metadata_survives_normal_movement_edit_and_cannot_be_forged(self):
        first=self.write(self.request('13棟死3隻'));row=self.data()['movements'][0];r=self.store.mutate(self.admin,'movements',row|{'quantity':2},str(uuid.uuid4()),row['id']);self.assertEqual(r['quick_source'],row['quick_source']);self.assertEqual(history(self.store,self.admin,{})['rows'][0]['status'],'modified')
        with self.assertRaises(Problem):self.store.mutate(self.admin,'movements',dict(date='2026-10-24',batch_id=self.batch['id'],type='death',quantity=1,quick_source=row['quick_source']),str(uuid.uuid4()))
    def test_full_form_fields_and_explicit_shared_delivery_allocation_are_preserved(self):
        other=self.add('barns',name='14棟');batch=self.add('batches',barn_id=other['id'],name='JD-other',entry_date='2026-01-01',entry_count=100,status='active');self.store.mutate(self.admin,'feed_bins',self.bin|{'barn_ids':[self.barn['id'],other['id']]},str(uuid.uuid4()),self.bin['id']);first=self.write(self.request());request=self.edit_request(first,'10/15 13棟2噸');request['corrections']={'vendor':'養全','item':'大豬料','note':'完整原表單備註','allocations':[{'batch_id':self.batch['id'],'kg':1200},{'batch_id':batch['id'],'kg':800}]};self.write(request);data=self.data();r=data['deliveries'][0];self.assertEqual(r['note'],'完整原表單備註');self.assertEqual(r['vendor'],'養全');self.assertEqual(r['item'],'大豬料');self.assertEqual(statistics(data,{'batch_id':[self.batch['id']],'to':['2026-10-24']})['delivery_kg'],1200);self.assertEqual(self.inventory()['kg'],3000)
        request=self.edit_request({'kind':'deliveries','id':r['id'],'revision':r['revision']},'10/15 13棟1.5噸');before=self.document()
        with self.assertRaises((Invalid,Problem)):self.prepare(request)
        self.assertEqual(before,self.document())
    def test_original_movement_full_form_keeps_destination_trip_weight_capabilities(self):
        first=self.write(self.request('13棟出豬8隻'));r=self.data()['movements'][0];saved=self.store.mutate(self.admin,'movements',r|{'outgoing_destination':'南投','outgoing_trip':'A車','total_weight_kg':800},str(uuid.uuid4()),r['id']);self.assertEqual(saved['outgoing_destination'],'南投');self.assertEqual(saved['outgoing_trip'],'A車');self.assertEqual(saved['total_weight_kg'],800);self.assertEqual(saved['quantity'],8);self.assertEqual(saved['quick_source']['initial_text'],'13棟出豬8隻')
    def test_full_form_batch_change_updates_barn_source_without_losing_initial_text(self):
        self.write(self.request('13棟死3隻'));r=self.data()['movements'][0];barn=self.add('barns',name='14棟');batch=self.add('batches',barn_id=barn['id'],name='JD-other',entry_date='2026-01-01',entry_count=100,status='active');saved=self.store.mutate(self.admin,'movements',r|{'batch_id':batch['id']},str(uuid.uuid4()),r['id']);self.assertEqual(saved['quick_source']['barn_id'],barn['id']);self.assertEqual(saved['quick_source']['initial_text'],r['quick_source']['initial_text']);d=self.data();self.assertEqual(herd(d['batches'],d['movements'],'2026-10-24',[self.batch['id']])['remaining'],100)
    def test_generic_arrival_mutation_cannot_bypass_stock_confirmation(self):
        first=self.write(self.request());r=self.data()['deliveries'][0]
        with self.assertRaises(Problem):self.store.mutate(self.admin,'deliveries',r|{'kg':100000},str(uuid.uuid4()),r['id'])
        self.assertEqual(self.inventory()['kg'],3000)
    def test_bin_membership_cannot_change_with_linked_arrival_and_config_can(self):
        self.write(self.request());other=self.add('barns',name='14棟');before=self.document()
        with self.assertRaises((Problem,Invalid)):self.store.mutate(self.admin,'feed_bins',self.bin|{'barn_ids':[other['id']]},str(uuid.uuid4()),self.bin['id'])
        self.assertEqual(before,self.document());bin=next(b for b in self.data()['feed_bins'] if b['id']==self.bin['id']);self.store.mutate(self.admin,'feed_bins',bin|{'inventory_opening_kg':2000},str(uuid.uuid4()),bin['id']);self.assertEqual(self.inventory()['kg'],4000)
    def test_history_paginates_searches_and_retains_audit_on_delete(self):
        first=self.write(self.request());second=self.write(self.request('13棟死2隻'));h=history(self.store,self.admin,{'q':['死']});self.assertEqual(h['total'],1);self.assertEqual(h['rows'][0]['record']['id'],second['id']);self.assertEqual(len(history(self.store,self.admin,{'limit':['1']})['rows']),1);self.write(self.edit_request(first,'',action='delete'));db=self.store.connect()
        try:self.assertTrue(any(r['action']=='delete' for r in db.execute('SELECT action FROM audit WHERE record_id=?',(first['id'],))))
        finally:db.close()
    def test_shortcut_creation_uses_existing_notification_outbox_without_duplicate_or_note_leak(self):
        import base64
        from app.push import subscribe,queue_records
        key=base64.urlsafe_b64encode(b'\x04'+b'\0'*64).decode().rstrip('=');auth=base64.urlsafe_b64encode(b'\0'*16).decode().rstrip('=')
        with patch('app.push.configured',return_value=True):subscribe(self.store,self.staff,{'subscription':{'endpoint':'https://fcm.googleapis.com/fcm/send/quick-synthetic','keys':{'p256dh':key,'auth':auth}},'new_records':True,'daily_reminder':False,'language':'zh'})
        self.prepare(self.request());self.assertEqual(queue_records(self.store),0);first=self.write(self.request());self.assertEqual(queue_records(self.store),1);self.assertEqual(queue_records(self.store),0);self.write(self.edit_request(first,'10/15 13棟1.5噸'));self.assertEqual(queue_records(self.store),0)
        db=self.store.connect()
        try:
            jobs=[dict(r) for r in db.execute('SELECT * FROM push_deliveries')];self.assertEqual(len(jobs),1);self.assertIn('到料',jobs[0]['payload']);self.assertNotIn('10/15 13棟2噸',jobs[0]['payload'])
        finally:db.close()
    def test_standard_backup_preserves_quick_sources_physical_links_and_stock(self):
        self.write(self.request());self.write(self.request('13棟叫料2噸'));backup=self.store.export_backup();other=Store(Path(self.tmp.name)/'restore');u=other.create_user('restorer','83000015');other.import_backup(u,backup);data=other.snapshot();bin=next(b for b in data['feed_bins'] if b['id']==self.bin['id']);self.assertEqual(stock(data,bin,'2026-10-24')['kg'],3000);self.assertEqual(history(other,u,{})['total'],2)
    def test_removing_arrival_that_supports_inventory_usage_recomputes_old_usage(self):
        first=self.write(self.request());usage=self.add('usages',batch_id=self.batch['id'],start='2026-10-01',end='2026-10-24',method='inventory',opening=1000,closing=500);self.assertEqual(consumption(usage,self.data()['deliveries']),2500);edited=self.write(self.edit_request(first,'10/15 13棟1.5噸'));self.assertEqual(consumption(usage,self.data()['deliveries']),2000);self.assertEqual(self.inventory()['kg'],500)


class CloudQuickRecordTests(QuickRecordTests):
    def setUp(self):
        super().setUp();self.local=self.store;self.fixture=HranaFixture(Path(self.tmp.name)/'remote');self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.local,self.store)
    def tearDown(self):self.fixture.close();super().tearDown()
