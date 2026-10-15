"""Password changes and one-use setup links; hashes and tokens never enter audit."""
import hashlib,hmac,secrets,sqlite3,time
from .store import Problem,password_hash,verify_password


def validate_password(value):
    if not isinstance(value,str) or not 12<=len(value)<=512 or not value.strip():raise Problem('invalid_user')
    return value


def change_password(store,user,current,new):
    validate_password(new)
    db=store.connect()
    try:
        old=db.execute('SELECT hash,revision FROM users WHERE id=?',(user['id'],)).fetchone()
        if not isinstance(current,str) or not old or not verify_password(current,old['hash']):raise Problem('invalid_current_password')
        revision=old['revision']
    finally:db.close()
    store.backup_sqlite(label='before-password-change')
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT hash,revision FROM users WHERE id=?',(user['id'],)).fetchone()
        if old['revision']!=revision:raise Problem('revision_conflict',409)
        if not verify_password(current,old['hash']):raise Problem('invalid_current_password')
        db.execute('UPDATE users SET hash=?,revision=revision+1 WHERE id=?',(password_hash(new),user['id']))
        db.execute('INSERT INTO account_security(user_id,must_change) VALUES(?,0) ON CONFLICT(user_id) DO UPDATE SET must_change=0,setup_hash=NULL,setup_expires=NULL',(user['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        store.audit(db,user['id'],'change-password','users',user['id'],{'revision':revision},{'revision':revision+1,'password_changed':True})
        db.commit();return {'ok':True,'login_required':True}
    finally:db.close()


def issue_setup(store,actor,user_id,before_revision):
    store.require(actor,True)
    if actor['id']==user_id:raise Problem('use_own_password_form')
    store.backup_sqlite(label='before-account-setup')
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        user=db.execute('SELECT id,username,revision,active FROM users WHERE id=?',(user_id,)).fetchone()
        if not user or not user['active']:raise Problem('not_found',404)
        if user['revision']!=before_revision:raise Problem('revision_conflict',409)
        token=secrets.token_urlsafe(32);expires=time.time()+48*3600
        db.execute('UPDATE users SET hash=?,revision=revision+1 WHERE id=?',(password_hash(secrets.token_urlsafe(32)),user_id))
        db.execute('INSERT INTO account_security VALUES(?,1,?,?) ON CONFLICT(user_id) DO UPDATE SET must_change=1,setup_hash=excluded.setup_hash,setup_expires=excluded.setup_expires',
            (user_id,hashlib.sha256(token.encode()).hexdigest(),expires))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        store.audit(db,actor['id'],'issue-account-setup','users',user_id,{'revision':user['revision']},
            {'revision':user['revision']+1,'must_change':True,'expires_at':expires})
        db.commit();return {'username':user['username'],'token':token,'expires_at':expires,'revision':user['revision']+1}
    finally:db.close()


def activate(store,username,token,password):
    validate_password(password)
    if not isinstance(username,str) or not isinstance(token,str) or not 32<=len(token)<=128:raise Problem('invalid_setup_link')
    db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        user=db.execute('SELECT u.id,u.revision,u.active,s.setup_hash,s.setup_expires FROM users u JOIN account_security s ON u.id=s.user_id WHERE u.username=?',(username,)).fetchone()
        if not user or not user['active'] or not user['setup_hash'] or not user['setup_expires'] or user['setup_expires']<=time.time() or not hmac.compare_digest(user['setup_hash'],hashlib.sha256(token.encode()).hexdigest()):raise Problem('invalid_setup_link')
        db.execute('UPDATE users SET hash=?,revision=revision+1 WHERE id=?',(password_hash(password),user['id']))
        db.execute('UPDATE account_security SET must_change=0,setup_hash=NULL,setup_expires=NULL WHERE user_id=?',(user['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        store.audit(db,user['id'],'activate-account','users',user['id'],None,{'password_changed':True,'revision':user['revision']+1})
        db.commit();return {'ok':True,'login_required':True}
    finally:db.close()


def ensure_role_accounts(store,actor):
    store.require(actor,True);result=[]
    for name,role in [('farmviewer','viewer'),('farmeditor','staff'),('farmmanager','admin')]:
        db=store.connect()
        try:existing=db.execute('SELECT id,username,role FROM users WHERE username=?',(name,)).fetchone()
        finally:db.close()
        if existing:result.append(dict(existing)|{'created':False});continue
        try:created=store.create_user(name,secrets.token_urlsafe(32),role,actor['id'],must_change=True)
        except Problem as error:
            if error.code!='username_exists':raise
            result.append({'username':name,'created':False});continue
        result.append(created|{'created':True})
    return result
