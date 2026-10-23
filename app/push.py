"""Opt-in Web Push, committed-audit outbox, and deduplicated Taipei reminders."""
import base64, hashlib, json, os, time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from .store import Problem, encode, now
from .notification_schema import PUSH_SCHEMA

KINDS = {'movements':('豬隻異動','biến động đàn'), 'feed_orders':('叫料','đặt cám'),
         'weights':('秤重','cân'), 'daily_checks':('巡場確認','xác nhận kiểm tra'),
         'deliveries':('到料','nhập cám'), 'usages':('耗料','tiêu thụ cám'),
         'work_tasks':('工作安排','công việc')}


def configured():
    return all(os.environ.get(k) for k in ('PIGLEDGER_PUSH_PRIVATE_KEY','PIGLEDGER_PUSH_PUBLIC_KEY','CRON_SECRET'))


def initialize(store):
    db=store.connect()
    try:db.executescript(PUSH_SCHEMA);db.commit()
    finally:db.close()


def _decoded(value, length):
    if not isinstance(value,str) or len(value)>200:raise Problem('invalid_push_subscription')
    try:raw=base64.b64decode(value+'='*(-len(value)%4),altchars=b'-_',validate=True)
    except (ValueError,TypeError):raise Problem('invalid_push_subscription') from None
    if len(raw)!=length:raise Problem('invalid_push_subscription')
    return raw


def validate_subscription(value):
    if not isinstance(value,dict):raise Problem('invalid_push_subscription')
    endpoint=value.get('endpoint');keys=value.get('keys',{})
    if not isinstance(endpoint,str) or len(endpoint)>2048:raise Problem('invalid_push_subscription')
    try:
        u=urlsplit(endpoint);host=u.hostname or ''
        allowed=host in ('fcm.googleapis.com','android.googleapis.com','updates.push.services.mozilla.com','web.push.apple.com') or host.endswith('.push.apple.com')
        if not allowed or u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.fragment:raise ValueError()
    except ValueError:raise Problem('invalid_push_subscription') from None
    if not isinstance(keys,dict):raise Problem('invalid_push_subscription')
    public=_decoded(keys.get('p256dh'),65);_decoded(keys.get('auth'),16)
    if public[0]!=4:raise Problem('invalid_push_subscription')
    return endpoint,keys['p256dh'],keys['auth']


def status(store,user):
    result={'configured':configured(),'public_key':os.environ.get('PIGLEDGER_PUSH_PUBLIC_KEY',''),
            'reminder_time':'10:00','timezone':'Asia/Taipei','devices':[]}
    if not result['configured']:return result
    db=store.connect()
    try:result['devices']=[dict(r) for r in db.execute('SELECT id,new_records,daily_reminder,language FROM push_subscriptions WHERE user_id=?',(user['id'],))]
    finally:db.close()
    return result


def subscribe(store,user,body):
    if not configured():raise Problem('push_not_configured',503)
    if not isinstance(body,dict):raise Problem('invalid_push_preferences')
    endpoint,key,auth=validate_subscription(body.get('subscription'))
    if any(not isinstance(body.get(k),bool) for k in ('new_records','daily_reminder')):raise Problem('invalid_push_preferences')
    language=body.get('language','zh')
    if language not in ('zh','vi'):raise Problem('invalid_push_preferences')
    sid=hashlib.sha256(endpoint.encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT user_id,created_at FROM push_subscriptions WHERE id=?',(sid,)).fetchone()
        count=db.execute('SELECT COUNT(*) FROM push_subscriptions WHERE user_id=?',(user['id'],)).fetchone()[0]
        if count>=8 and (not old or old['user_id']!=user['id']):raise Problem('push_device_limit')
        # An endpoint may only be used by the current account on a shared phone.
        seq=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0]
        if not old or old['user_id']!=user['id']:
            db.execute('DELETE FROM push_deliveries WHERE subscription_id=?',(sid,))
        else:
            db.execute("DELETE FROM push_deliveries WHERE subscription_id=? AND status!='sent'",(sid,))
        db.execute('INSERT INTO push_subscriptions VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id,endpoint=excluded.endpoint,p256dh=excluded.p256dh,auth=excluded.auth,new_records=excluded.new_records,daily_reminder=excluded.daily_reminder,language=excluded.language,since_seq=excluded.since_seq,created_at=excluded.created_at',
                   (sid,user['id'],endpoint,key,auth,int(body['new_records']),int(body['daily_reminder']),language,seq,old['created_at'] if old and old['user_id']==user['id'] else now()))
        db.commit();return {'id':sid,'new_records':body['new_records'],'daily_reminder':body['daily_reminder']}
    finally:db.close()


def unsubscribe(store,user,sid):
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM push_subscriptions WHERE id=? AND user_id=?',(sid,user['id'])).fetchone():
            db.execute('DELETE FROM push_deliveries WHERE subscription_id=?',(sid,));db.execute('DELETE FROM push_subscriptions WHERE id=?',(sid,))
        db.commit();return {'ok':True}
    finally:db.close()


def revoke_user_devices(db,user_id):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='push_subscriptions'").fetchone():
        db.execute('DELETE FROM push_deliveries WHERE subscription_id IN (SELECT id FROM push_subscriptions WHERE user_id=?)',(user_id,))
        db.execute('DELETE FROM push_subscriptions WHERE user_id=?',(user_id,))


def _eligible(db):
    return [dict(s) for s in db.execute('SELECT s.* FROM push_subscriptions s JOIN users u ON u.id=s.user_id LEFT JOIN account_security a ON a.user_id=u.id WHERE u.active=1 AND COALESCE(a.must_change,0)=0')]


def _queue(db,s,key,category,payload):
    db.execute('INSERT INTO push_deliveries(subscription_id,event_key,category,payload) VALUES(?,?,?,?) ON CONFLICT(subscription_id,event_key) DO NOTHING',(s['id'],key,category,encode(payload)))


def queue_records(store):
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');subs=_eligible(db)
        if not subs:return 0
        since=min(s['since_seq'] for s in subs)
        rows=[dict(r) for r in db.execute('SELECT a.seq,a.user_id,a.action,a.kind,a.record_id,a.after_value,u.username FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.seq>? ORDER BY a.seq LIMIT 500',(since,))]
        if not rows:return 0
        references=[(r['kind'],r['id'],json.loads(r['data'])) for r in db.execute("SELECT kind,id,data FROM records WHERE deleted=0 AND kind IN ('barns','batches')")]
        barns={rid:value['name'] for kind,rid,value in references if kind=='barns'}
        batches={rid:barns.get(value.get('barn_id'),'') for kind,rid,value in references if kind=='batches'}
        queued=0
        for s in subs:
            for r in rows:
                if r['seq']<=s['since_seq'] or not s['new_records'] or r['user_id']==s['user_id'] or r['kind'] not in KINDS or r['action'] not in ('create','create-weighing','bulk-zero-create'):continue
                value=json.loads(r['after_value'] or '{}')
                key='record:'+r['kind']+':'+(value.get('session_id') or r['record_id'])
                if r['action']=='bulk-zero-create':key='record:daily_checks:bulk:'+r['user_id']+':'+value['date']
                vi=s['language']=='vi';label=KINDS[r['kind']][int(vi)];date=value.get('date') or value.get('start') or ''
                body=(f"{r['username'] or ''} đã ghi {label}" if vi else f"{r['username'] or ''}新增{label}紀錄")+(f'（{date}）' if date else '')
                barn=batches.get(value.get('batch_id'),'')
                if not barn and value.get('feed_bin_snapshot'):barn='、'.join(value['feed_bin_snapshot'].get('barn_names',[]))
                if barn and r['action']!='bulk-zero-create':body=barn+' · '+body
                # Never put notes, medication or source files on a lock screen.
                payload={'title':'Gia Đắc' if vi else '嘉得肉豬紀錄','body':body,'tag':key,'url':'/#'+('weights' if r['kind']=='weights' else 'feed' if r['kind']=='feed_orders' else 'calendar' if r['kind']=='work_tasks' else 'daily')}
                _queue(db,s,key,'records',payload);queued+=1
            db.execute('UPDATE push_subscriptions SET since_seq=MAX(since_seq,?) WHERE id=?',(rows[-1]['seq'],s['id']))
        db.commit();return queued
    finally:db.close()


def queue_reminders(store,instant=None):
    instant=instant or datetime.now(timezone.utc)
    local=instant.astimezone(timezone(timedelta(hours=8)));due=local.replace(hour=10,minute=0,second=0,microsecond=0)
    if local<due:return 0
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');count=0
        for s in _eligible(db):
            if not s['daily_reminder'] or datetime.fromisoformat(s['created_at'])>due:continue
            vi=s['language']=='vi';key='daily:'+local.date().isoformat()
            payload={'title':'Nhắc ghi chép Gia Đắc' if vi else '嘉得每日登記提醒','body':'Hãy kiểm tra trại và ghi biến động, lượng cám đặt hôm nay.' if vi else '記得巡場，並登記今天的豬隻異動與叫料。','tag':key,'url':'/#daily'}
            _queue(db,s,key,'daily',payload);count+=1
        db.commit();return count
    finally:db.close()


def send_webpush(subscription,payload):
    from pywebpush import webpush, WebPushException
    import requests
    class NoRedirectSession(requests.Session):
        def request(self,*args,**kwargs):
            kwargs['allow_redirects']=False
            return super().request(*args,**kwargs)
    info={'endpoint':subscription['endpoint'],'keys':{'p256dh':subscription['p256dh'],'auth':subscription['auth']}}
    try:
        response=webpush(info,data=encode(payload),vapid_private_key=os.environ['PIGLEDGER_PUSH_PRIVATE_KEY'],vapid_claims={'sub':os.environ.get('PIGLEDGER_PUSH_SUBJECT','https://555-rho-nine.vercel.app')},ttl=3600,timeout=4,requests_session=NoRedirectSession())
        return response.status_code
    except WebPushException as e:return e.response.status_code if e.response is not None else 503
    except Exception:return 503


def deliver(store,sender=None,budget=12,subscription_id=None):
    sender=sender or send_webpush;stop=time.monotonic()+budget;sent=failed=0
    for _ in range(12):
        if time.monotonic()>=stop:break
        db=store.connect();job=None
        try:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT d.*,s.endpoint,s.p256dh,s.auth,s.user_id FROM push_deliveries d JOIN push_subscriptions s ON s.id=d.subscription_id JOIN users u ON u.id=s.user_id LEFT JOIN account_security a ON a.user_id=u.id WHERE u.active=1 AND COALESCE(a.must_change,0)=0 AND (? IS NULL OR d.subscription_id=?) AND ((d.category='records' AND s.new_records=1) OR (d.category='daily' AND s.daily_reminder=1) OR d.category='test') AND ((d.status='pending' AND d.next_attempt<=?) OR (d.status='sending' AND d.lease_until<?)) ORDER BY d.next_attempt LIMIT 1",(subscription_id,subscription_id,time.time(),time.time())).fetchone()
            if row:
                job=dict(row);db.execute("UPDATE push_deliveries SET status='sending',attempts=attempts+1,lease_until=? WHERE subscription_id=? AND event_key=?",(time.time()+60,job['subscription_id'],job['event_key']))
            db.commit()
        finally:db.close()
        if not job:break
        code=sender(job,json.loads(job['payload']));db=store.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if code in (404,410):
                current=db.execute('SELECT p256dh,auth FROM push_subscriptions WHERE id=?',(job['subscription_id'],)).fetchone()
                if current and current['p256dh']==job['p256dh'] and current['auth']==job['auth']:
                    db.execute('DELETE FROM push_subscriptions WHERE id=?',(job['subscription_id'],));db.execute('DELETE FROM push_deliveries WHERE subscription_id=?',(job['subscription_id'],))
            elif 200<=code<300:
                db.execute("UPDATE push_deliveries SET status='sent',lease_until=0 WHERE subscription_id=? AND event_key=?",(job['subscription_id'],job['event_key']));sent+=1
            else:
                attempts=job['attempts']+1
                db.execute('UPDATE push_deliveries SET status=?,next_attempt=?,lease_until=0 WHERE subscription_id=? AND event_key=?',('failed' if attempts>=5 else 'pending',time.time()+min(3600,60*2**attempts),job['subscription_id'],job['event_key']));failed+=1
            db.commit()
        finally:db.close()
    return {'sent':sent,'failed':failed}


def dispatch_pending(store,include_reminders=False):
    if not configured():return {'configured':False}
    if include_reminders:
        try:
            from pywebpush import webpush
        except ImportError:raise Problem('push_not_configured',503) from None
    queue_records(store)
    if include_reminders:queue_reminders(store)
    result=deliver(store)
    if include_reminders:result['transport_ready']=True
    db=store.connect()
    try:db.execute("DELETE FROM push_deliveries WHERE status IN ('sent','failed') AND created_at<datetime('now','-30 days')");db.commit()
    finally:db.close()
    return result


def test_notification(store,user,sid):
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM push_subscriptions WHERE id=? AND user_id=?',(sid,user['id'])).fetchone()
        if not row:raise Problem('push_device_not_found',404)
        s=dict(row);key='test:'+str(time.time_ns())
        _queue(db,s,key,'test',{'title':'嘉得通知測試','body':'這台裝置已能接收通知。','tag':key,'url':'/#daily'});db.commit()
    finally:db.close()
    return deliver(store,subscription_id=sid)
