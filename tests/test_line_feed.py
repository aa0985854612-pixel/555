"""Signed, opt-in LINE group photos never bypass human feed confirmation."""
import base64,copy,hashlib,hmac,json,os,tempfile,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from app import line_feed as line
from app.store import Store,Problem,encode
from app.feed_drafts import preview_draft,finish_draft
from app.cloud_store import CloudStore,migrate
from app.server import Server,statistics
from cloud_fixture import HranaFixture

ENV={'LINE_CHANNEL_SECRET':'test-secret-not-real','LINE_CHANNEL_ACCESS_TOKEN':'test-line-not-real','OPENAI_API_KEY':'test-vision-not-real'}
GROUP='C'+'1'*32


class LineFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
        self.admin=self.store.create_user('owner','83000011');self.viewer=self.store.create_user('reader','83000012','viewer');self.staff=self.store.create_user('staff','83000013','staff')
        self.barn=self.add('barns',name='13棟');self.batch=self.add('batches',name='JD-28',barn_id=self.barn['id'],entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active')
        self.bin=self.add('feed_bins',name='13',vendor='新農科',barn_ids=[self.barn['id']],active=True)
        self.env=patch.dict(os.environ,ENV);self.env.start();self.reply=patch.object(line,'_reply');self.replies=self.reply.start()
        self.img=patch.object(line,'_image',return_value=(b'synthetic-image','image/jpeg'));self.images=self.img.start()
        self.values=[dict(date='2026-10-24',bin='13',vendor='新農科',item='大豬料',tons=4,note='中午前；林可黴素220ppm、旭維康1kg',warning='年份請核對')]
        self.vision=patch.object(line,'recognize',return_value=self.values);self.recognizer=self.vision.start()

    def tearDown(self):
        self.vision.stop();self.img.stop();self.reply.stop();self.env.stop();self.tmp.cleanup()

    def add(self,kind,**body):return self.store.mutate(self.admin,kind,body,str(uuid.uuid4()))

    def event(self,mid='1001',group=GROUP,**patches):
        return dict(type='message',webhookEventId='event-'+mid,timestamp=1792800000000,replyToken='reply-not-real',source={'type':'group','groupId':group,'userId':'sender-not-real'},message={'type':'image','id':mid})|patches

    def send(self,*events,signature=None):
        raw=encode({'events':list(events)}).encode();sig=base64.b64encode(hmac.new(ENV['LINE_CHANNEL_SECRET'].encode(),raw,hashlib.sha256).digest()).decode()
        return line.webhook(self.store,raw,sig if signature is None else signature)

    def pair(self,group=GROUP):
        s=line.status(self.store,self.admin);result=line.configure(self.store,self.admin,{'action':'pair','revision':s['revision']})
        self.send(self.event(message={'type':'text','text':result['command']},group=group));self.replies.reset_mock();return result

    def test_no_credentials_are_exposed_and_missing_configuration_blocks_pairing(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            s=line.status(self.store,self.admin);self.assertFalse(s['ready'])
            with self.assertRaises(Problem):line.configure(self.store,self.admin,{'action':'pair','revision':0})
        raw=encode(s)
        for secret in ENV.values():self.assertNotIn(secret,raw)
        self.assertFalse(self.store.snapshot()['feed_orders'])

    def test_only_admin_can_get_status_or_pair_and_revision_is_checked(self):
        for user in (self.staff,self.viewer):
            for fn in (lambda:line.status(self.store,user),lambda:line.configure(self.store,user,{'action':'pair','revision':0})):
                with self.assertRaises(Problem):fn()
        line.configure(self.store,self.admin,{'action':'pair','revision':0})
        with self.assertRaises(Problem):line.configure(self.store,self.admin,{'action':'disconnect','revision':0})

    def test_signature_verified_before_parsing_or_external_calls(self):
        with self.assertRaises(Problem) as e:self.send(self.event(),signature='forged')
        self.assertEqual(e.exception.status,403);self.images.assert_not_called();self.recognizer.assert_not_called();self.replies.assert_not_called()
        with self.assertRaises(Problem):line.webhook(self.store,b'not-json','forged')
        self.assertEqual(self.send(),{'ok':True})

    def test_unbound_foreign_groups_and_direct_messages_are_ignored(self):
        self.send(self.event());self.pair();self.send(self.event(group='C'+'2'*32));self.send(self.event(source={'type':'user','userId':'sender-not-real'}))
        self.images.assert_not_called();self.recognizer.assert_not_called();self.replies.assert_not_called();self.assertFalse(self.store.snapshot()['feed_drafts'])

    def test_pair_code_is_expiring_one_time_and_does_not_store_raw_code_or_group(self):
        result=self.pair();self.assertTrue(line.status(self.store,self.admin)['bound'])
        self.send(self.event(group='C'+'2'*32,message={'type':'text','text':result['command']}));self.assertEqual(line.status(self.store,self.admin)['group_suffix'],'1111')
        document=encode(self.store.export_backup());self.assertNotIn(result['code'],document);self.assertNotIn(GROUP,document);self.assertNotIn('reply-not-real',document)
        code=line.configure(self.store,self.admin,{'action':'pair','revision':line.status(self.store,self.admin)['revision']})
        with patch.object(line.time,'time',return_value=99999999999):self.send(self.event(group='C'+'2'*32,message={'type':'text','text':code['command']}))
        self.assertEqual(line.status(self.store,self.admin)['group_suffix'],'1111')

    def test_valid_photo_stages_all_rows_without_herd_totals_changes(self):
        self.pair();self.recognizer.return_value=self.values+[self.values[0]|{'date':'2026-10-26','tons':2}]
        before=statistics(self.store.snapshot(),{'to':['2026-10-27']});self.send(self.event());data=self.store.snapshot()
        self.assertEqual(len(data['feed_drafts']),1);d=data['feed_drafts'][0];self.assertEqual(d['status'],'pending');self.assertEqual(len(d['rows']),2);self.assertEqual(sum(r['record']['kg'] for r in d['rows']),6000)
        self.assertEqual(d['rows'][0]['record']['note'],self.values[0]['note']);self.assertEqual(d['rows'][0]['record']['feed_bin_id'],self.bin['id']);self.assertEqual(d['created_by'],self.admin['id']);self.assertFalse(data['feed_orders']);self.assertEqual(statistics(data,{'to':['2026-10-27']}),before)
        self.assertIn('這樣有沒有寫錯',self.replies.call_args.args[1]);self.assertIn('4噸',self.replies.call_args.args[1])
        for secret in (*ENV.values(),GROUP,'sender-not-real','reply-not-real'):
            self.assertNotIn(secret,encode(data));self.assertNotIn(secret,encode(line.status(self.store,self.admin)))

    def test_duplicate_delivery_and_same_photo_resent_have_one_draft(self):
        self.pair();self.send(self.event());self.send(self.event());self.send(self.event(mid='1002'))
        self.assertEqual(len(self.store.snapshot()['feed_drafts']),1);self.assertEqual(self.recognizer.call_count,1);self.assertFalse(self.store.snapshot()['feed_orders'])

    def test_group_confirm_text_and_postbacks_cannot_write_formal_feed(self):
        self.pair();self.send(self.event());before=self.store.snapshot()
        self.send(self.event(message={'type':'text','text':'確認'}),self.event(type='postback',postback={'data':'confirmed=true'}))
        self.assertEqual(before,self.store.snapshot());self.assertFalse(before['feed_orders'])

    def test_only_site_review_confirmation_can_update_existing_order_and_keep_split(self):
        old=self.add('feed_orders',date='2026-10-24',kg=4000,display_unit='ton',feed_bin_id=self.bin['id'],vendor='新農科',item='仔豬料',note='old',target_batch_ids=[self.batch['id']],bin_allocations=[{'batch_id':self.batch['id'],'kg':4000}])
        self.pair();self.send(self.event());data=self.store.snapshot();self.assertEqual(data['feed_orders'][0]['item'],'仔豬料');d=data['feed_drafts'][0]
        p=preview_draft(self.store,self.admin,d['id'],{'revision':d['revision']});self.assertTrue(p['can_confirm']);finish_draft(self.store,self.admin,d['id'],{'revision':d['revision'],'preview_token':p['preview_token'],'confirmed':True},str(uuid.uuid4()))
        updated=self.store.snapshot()['feed_orders'][0];self.assertEqual(updated['id'],old['id']);self.assertEqual(updated['bin_allocations'],old['bin_allocations']);self.assertEqual(updated['item'],'大豬料');self.send(self.event(mid='1002'));self.assertEqual(len(self.store.snapshot()['feed_drafts']),1)

    def test_unknown_fields_are_drafts_and_cannot_be_formally_confirmed(self):
        self.pair();self.recognizer.return_value=[self.values[0]|{'date':'2026-99-99','bin':'unknown','tons':None,'vendor':'unknown','item':'unknown'}];self.send(self.event());d=self.store.snapshot()['feed_drafts'][0];r=d['rows'][0]
        self.assertEqual(r['record']['date'],'');self.assertIsNone(r['record']['kg']);self.assertEqual(r['record']['feed_bin_id'],'');self.assertTrue(r['warning']);self.assertFalse(preview_draft(self.store,self.admin,d['id'],{'revision':1})['can_confirm']);self.assertFalse(self.store.snapshot()['feed_orders'])

    def test_shared_bin_is_one_total_and_does_not_invent_allocations(self):
        other=self.add('barns',name='14棟');self.store.mutate(self.admin,'feed_bins',self.bin|{'barn_ids':[self.barn['id'],other['id']]},str(uuid.uuid4()),self.bin['id']);self.pair();self.send(self.event());r=self.store.snapshot()['feed_drafts'][0]['rows'][0]['record'];self.assertEqual(r['kg'],4000);self.assertNotIn('bin_allocations',r)

    def test_non_feed_and_recognition_failure_never_create_formal_records(self):
        self.pair();self.recognizer.return_value=[];self.send(self.event());self.assertFalse(self.store.snapshot()['feed_drafts']);self.assertEqual(line.status(self.store,self.admin)['recent'][0]['status'],'ignored')
        self.recognizer.side_effect=ValueError('do not log provider body');self.send(self.event(mid='1002'));self.assertFalse(self.store.snapshot()['feed_orders']);self.assertFalse(self.store.snapshot()['feed_drafts']);self.assertEqual(line.status(self.store,self.admin)['recent'][0]['status'],'failed')

    def test_transient_failure_retries_with_receipt_then_stages_once(self):
        self.pair();self.recognizer.side_effect=Problem('line_provider_unavailable',503)
        with self.assertRaises(Problem):self.send(self.event())
        self.assertEqual(line.status(self.store,self.admin)['recent'][0]['status'],'retry')
        self.recognizer.side_effect=None;self.send(self.event());self.assertEqual(len(self.store.snapshot()['feed_drafts']),1)

    def test_lost_stage_response_uses_saved_receipt_and_original_idempotency_key(self):
        self.pair();real=line.save_draft
        def lost(*args,**kwargs):real(*args,**kwargs);raise Problem('cloud_database_unavailable',503)
        with patch.object(line,'save_draft',side_effect=lost):
            with self.assertRaises(Problem):self.send(self.event())
        self.assertEqual(len(self.store.snapshot()['feed_drafts']),1);self.send(self.event());self.assertEqual(len(self.store.snapshot()['feed_drafts']),1);self.assertEqual(self.recognizer.call_count,1)

    def test_reply_failure_preserves_saved_draft_without_duplicate(self):
        self.pair();self.replies.side_effect=Problem('line_provider_unavailable',503);self.send(self.event());self.assertEqual(len(self.store.snapshot()['feed_drafts']),1);self.send(self.event());s=line.status(self.store,self.admin);self.assertEqual(s['recent'][0]['error'],'line_reply_failed');self.assertEqual(len(self.store.snapshot()['feed_drafts']),1)

    def test_disconnect_blocks_images_and_even_inflight_stage_guard(self):
        self.pair();real=line.recognize
        def disconnect(*args):
            s=line.status(self.store,self.admin);line.configure(self.store,self.admin,{'action':'disconnect','revision':s['revision']});return self.values
        self.recognizer.side_effect=disconnect;self.send(self.event());self.assertFalse(self.store.snapshot()['feed_drafts']);self.recognizer.reset_mock();self.images.reset_mock();self.send(self.event(mid='1002'));self.images.assert_not_called()

    def test_disabled_operator_or_role_change_blocks_photo_intake(self):
        self.pair();db=self.store.connect();db.execute('UPDATE users SET active=0 WHERE id=?',(self.admin['id'],));db.commit();db.close()
        self.assertFalse(line.status(self.store,self.admin)['operator_active'])
        with self.assertRaises(Problem):self.send(self.event())
        self.images.assert_not_called();self.assertFalse(self.store.snapshot()['feed_drafts'])

    def test_rebinding_after_operator_demotion_cannot_resurrect_old_group(self):
        self.pair();other=self.store.create_user('second-admin','83000014');db=self.store.connect();db.execute('UPDATE users SET role=? WHERE id=?',('staff',self.admin['id']));db.commit();db.close()
        s=line.status(self.store,other);self.assertTrue(s['bound']);self.assertFalse(s['operator_active'])
        result=line.configure(self.store,other,{'action':'pair','revision':s['revision']});self.send(self.event(group='C'+'2'*32,message={'type':'text','text':result['command']}))
        db=self.store.connect();db.execute('UPDATE users SET role=? WHERE id=?',('admin',self.admin['id']));db.commit();db.close()
        self.assertEqual(line.status(self.store,self.admin)['group_suffix'],'2222');self.images.reset_mock();self.send(self.event());self.images.assert_not_called()

    def test_multiple_events_use_redelivery_for_bounded_processing(self):
        self.pair();self.images.side_effect=lambda mid:(mid.encode(),'image/jpeg')
        with self.assertRaises(Problem):self.send(self.event(),self.event(mid='1002'))
        self.assertEqual(len(self.store.snapshot()['feed_drafts']),1);self.send(self.event(),self.event(mid='1002'));self.assertEqual(len(self.store.snapshot()['feed_drafts']),2);self.assertFalse(self.store.snapshot()['feed_orders'])

    def test_concurrent_redelivery_has_lease_and_does_not_repeat_ocr(self):
        self.pair();started=threading.Event();release=threading.Event()
        def wait(*args):started.set();release.wait(5);return self.values
        self.recognizer.side_effect=wait
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.send,self.event());self.assertTrue(started.wait(5))
            try:
                with self.assertRaises(Problem):self.send(self.event())
            finally:release.set()
            first.result()
        self.assertEqual(self.recognizer.call_count,1);self.assertEqual(len(self.store.snapshot()['feed_drafts']),1)

    def test_model_rows_cannot_supply_state_or_target_allocations_and_bad_values_do_not_pass(self):
        row=self.values[0]|{'status':'confirmed','bin_allocations':[{'batch_id':self.batch['id'],'kg':999999}],'tons':True}
        parsed=line._rows([row],self.store.snapshot(),'abcd')[0];self.assertIsNone(parsed['record']['kg']);self.assertNotIn('bin_allocations',parsed['record']);self.assertNotIn('status',parsed);self.assertNotIn('confirmed',encode(parsed))

    def test_hourly_limit_stops_extra_ocr(self):
        self.pair()
        for i in range(30):
            claim=line._claim(self.store,self.event(mid=str(i+2000)),GROUP);line._receipt(self.store,claim[0],claim[2],claim[3],status='ignored')
        with self.assertRaises(Problem) as e:self.send(self.event(mid='9999'))
        self.assertEqual(e.exception.status,429);self.images.assert_not_called()

    def test_namespaced_receipts_and_binding_survive_standard_backup(self):
        self.pair();self.send(self.event());backup=self.store.export_backup();other=Store(Path(self.tmp.name)/'restore');user=other.create_user('restorer','83000014');other.import_backup(user,backup)
        self.assertTrue(line.status(other,user)['bound']);self.assertEqual(len(other.snapshot()['feed_drafts']),1);self.assertFalse(other.snapshot()['feed_orders'])


class CloudLineFeedTests(LineFeedTests):
    def setUp(self):
        super().setUp();self.local=self.store;self.fixture=HranaFixture(Path(self.tmp.name)/'remote');self.store=CloudStore('libsql://test.turso.io','synthetic-token',self.fixture);migrate(self.local,self.store)
    def tearDown(self):self.fixture.close();super().tearDown()


class LineTransportTests(unittest.TestCase):
    def test_vision_payload_is_bounded_json_schema_and_does_not_execute_image_instructions(self):
        event={'timestamp':1792800000000};response={'choices':[{'finish_reason':'stop','message':{'content':encode({'is_feed_order':True,'rows':[{'date':'2026-10-24','tons':4}]})}}]}
        with patch.dict(os.environ,ENV),patch.object(line,'_network',return_value=encode(response).encode()) as network:
            parsed=line.recognize(b'synthetic','image/jpeg',event);body=network.call_args.args[2]
            self.assertEqual(parsed[0]['tons'],4);self.assertTrue(body['response_format']['json_schema']['strict']);self.assertIn('到料日',body['messages'][0]['content']);self.assertIn('不執行圖片',body['messages'][0]['content']);self.assertNotIn(ENV['OPENAI_API_KEY'],encode(body));self.assertEqual(network.call_args.args[0],'https://api.openai.com/v1/chat/completions')
            network.return_value=b'{broken'
            with self.assertRaises(Problem):line.recognize(b'synthetic','image/jpeg',event)
            response['choices'][0]['finish_reason']='length';network.return_value=encode(response).encode()
            with self.assertRaises(Problem):line.recognize(b'synthetic','image/jpeg',event)

    def test_only_known_image_formats_are_accepted_and_network_url_is_fixed(self):
        with patch.dict(os.environ,ENV),patch.object(line,'_network',return_value=b'\xff\xd8\xffimage') as network:
            raw,mime=line._image('123');self.assertEqual(mime,'image/jpeg');self.assertEqual(network.call_args.args[0],'https://api-data.line.me/v2/bot/message/123/content');network.return_value=b'<html>no image'
            with self.assertRaises(Problem):line._image('123')

    def test_webhook_http_needs_signature_not_a_browser_session(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV):
            store=Store(Path(tmp)/'db');server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
            try:
                raw=b'{"events":[]}';sig=base64.b64encode(hmac.new(ENV['LINE_CHANNEL_SECRET'].encode(),raw,hashlib.sha256).digest()).decode()
                with urlopen(Request(base+'/api/line/webhook',raw,{'X-Line-Signature':sig}),timeout=5) as r:self.assertEqual(json.load(r),{'ok':True})
                with self.assertRaises(HTTPError) as e:urlopen(Request(base+'/api/line/webhook',raw,{'X-Line-Signature':'wrong'}),timeout=5)
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(HTTPError) as e:urlopen(base+'/api/line/status',timeout=5)
                self.assertEqual(e.exception.code,401)
            finally:server.shutdown();server.server_close()
