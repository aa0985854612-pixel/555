"""Persistent Turso/libSQL HTTP storage for Vercel; never uses /tmp as a database.

Uses Hrana v2's connection baton, retaining BEGIN IMMEDIATE through validation,
audit and idempotency writes. There are deliberately no automatic write retries.
"""
import base64
import hashlib
import json
import os
import sqlite3
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from .store import Store, Problem, SCHEMA, SCHEMA_VERSION, encode, now

TABLES=('records','users','requests','audit','account_security')
CLOUD_SCHEMA='''
CREATE TABLE IF NOT EXISTS cloud_backups(id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, label TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cloud_login_attempts(key TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cloud_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''

def endpoint(database_url):
    parts=urlsplit(database_url)
    if (parts.scheme not in ('https','libsql') or not parts.hostname
            or parts.username or parts.password or parts.port not in (None,443)
            or parts.query or parts.fragment or parts.path not in ('','/')):
        raise Problem('cloud_database_configuration',503)
    return urlunsplit(('https',parts.netloc,'/v2/pipeline','',''))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        # Do not forward the database credential to a redirected destination.
        raise Problem('cloud_database_redirect',503)

def value_out(value):
    if value is None:return {'type':'null'}
    if isinstance(value,(bool,int)):return {'type':'integer','value':str(int(value))}
    if isinstance(value,float):return {'type':'float','value':value}
    if isinstance(value,bytes):return {'type':'blob','base64':base64.b64encode(value).decode()}
    if isinstance(value,str):return {'type':'text','value':value}
    raise TypeError('Unsupported SQL parameter')

def value_in(value):
    typ=value['type']
    if typ=='null':return None
    if typ=='integer':return int(value['value'])
    if typ=='float':return float(value['value'])
    if typ=='text':return value['value']
    if typ=='blob':return base64.b64decode(value['base64'])
    raise Problem('cloud_database_protocol',503)

class Row(Mapping):
    def __init__(self,columns,values):self.columns=columns;self.values=values
    def __getitem__(self,key):return self.values[key if isinstance(key,int) else self.columns.index(key)]
    def __iter__(self):return iter(self.columns)
    def __len__(self):return len(self.columns)

class Cursor:
    def __init__(self,result):
        columns=[c['name'] for c in result['cols']]
        self.rows=iter([Row(columns,[value_in(v) for v in row]) for row in result['rows']])
        self.rowcount=result.get('affected_row_count',0)
        self.lastrowid=result.get('last_insert_rowid')
    def fetchone(self):return next(self.rows,None)
    def fetchall(self):return list(self.rows)
    def __iter__(self):return self.rows

class Connection:
    def __init__(self,url,token,transport=None):
        self.url=endpoint(url);self.origin=urlsplit(self.url).netloc
        self.token=token;self.baton=None;self.in_transaction=False;self.closed=False;self.pending=[]
        self.transport=transport or self._http
    def _http(self,url,payload):
        req=Request(url,encode(payload).encode(),{'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
        try:
            with build_opener(NoRedirect()).open(req,timeout=15) as response:
                return json.loads(response.read())
        except (URLError,HTTPError,TimeoutError,ValueError):
            # Provider errors can contain statement values or tokens. Never log them.
            raise Problem('cloud_database_unavailable',503) from None
    def _request(self,request):
        if self.closed:raise RuntimeError('Database connection is closed')
        response=self.transport(self.url,{'baton':self.baton,'requests':[request]})
        self.baton=response.get('baton')
        redirect=response.get('base_url')
        if redirect:
            parts=urlsplit(redirect)
            same_provider=(self.origin.endswith('.turso.io') and (parts.hostname or '').endswith('.turso.io'))
            if parts.scheme!='https' or (parts.netloc!=self.origin and not same_provider) or parts.username or parts.port not in (None,443) or parts.query or parts.fragment:
                raise Problem('cloud_database_redirect',503)
            self.url=urlunsplit(('https',parts.netloc,'/v2/pipeline','',''))
        item=response['results'][0]
        if item['type']=='error':self._error(item.get('error',{}))
        return item.get('response',{})
    def _error(self,error):
        code=error.get('code','')
        if code.startswith('SQLITE_CONSTRAINT'):raise sqlite3.IntegrityError('Constraint violation')
        if code in ('SQLITE_BUSY','SQLITE_LOCKED','TRANSACTION_TIMEOUT','STREAM_EXPIRED'):
            raise Problem('cloud_database_busy',503)
        raise Problem('cloud_database_query',503)
    def batch(self,statements):
        steps=[]
        for i,(sql,parameters) in enumerate(statements):
            step={'stmt':{'sql':sql,'args':[value_out(v) for v in parameters],'want_rows':True}}
            if i:step['condition']={'type':'ok','step':i-1}
            steps.append(step)
        result=self._request({'type':'batch','batch':{'steps':steps}})['result']
        for error in result['step_errors']:
            if error:self._error(error)
        for sql,_ in statements:
            command=sql.strip().split(None,1)[0].upper()
            if command=='BEGIN':self.in_transaction=True
            elif command in ('COMMIT','ROLLBACK'):self.in_transaction=False
        return [Cursor(r) for r in result['step_results']]
    def execute(self,sql,parameters=()):
        command=sql.strip().split(None,1)[0].upper()
        # sqlite3 implicitly starts a transaction for DML, which session routes rely on.
        if command in ('INSERT','UPDATE','DELETE','REPLACE') and not self.in_transaction:
            self.execute('BEGIN IMMEDIATE')
        if command in ('INSERT','UPDATE','DELETE','REPLACE'):
            self.pending.append((sql,parameters))
            return Cursor({'cols':[],'rows':[]})
        if self.pending:
            statements=self.pending+[(sql,parameters)];self.pending=[]
            return self.batch(statements)[-1]
        result=self._request({'type':'execute','stmt':{'sql':sql,'args':[value_out(v) for v in parameters],'want_rows':True}})
        if command=='BEGIN':self.in_transaction=True
        elif command in ('COMMIT','ROLLBACK'):self.in_transaction=False
        return Cursor(result['result'])
    def executescript(self,sql):
        # Only controlled schema constants, never user SQL; no sqlite implicit COMMIT.
        statements=[(statement,()) for statement in sql.split(';') if statement.strip()]
        if statements:self.batch(statements)
    def commit(self):
        if self.in_transaction:self.execute('COMMIT')
    def close(self):
        if self.closed:return
        try:
            if self.baton:self._request({'type':'close'})
        except Exception:
            # A lost connection may have committed. The caller's idempotency key
            # resolves that uncertainty on retry; cleanup must not hide the result.
            pass
        finally:self.closed=True;self.baton=None;self.in_transaction=False;self.pending=[]

def fingerprint(document):
    return hashlib.sha256(encode({table:sorted(document.get(table,[]),key=encode) for table in TABLES}).encode()).hexdigest()

def read_document(db):
    available={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    tables=[table for table in TABLES if table in available]
    if isinstance(db,Connection):
        if db.pending:
            statements=db.pending;db.pending=[];db.batch(statements)
        cursors=db.batch([('SELECT * FROM '+table,()) for table in tables])
        result={table:[dict(r) for r in cursor] for table,cursor in zip(tables,cursors)}
    else:result={table:[dict(r) for r in db.execute('SELECT * FROM '+table)] for table in tables}
    return {table:result.get(table,[]) for table in TABLES}

class CloudStore(Store):
    def __init__(self,url=None,token=None,transport=None):
        self.url=url or os.environ.get('TURSO_DATABASE_URL','')
        self.token=token or os.environ.get('TURSO_AUTH_TOKEN','')
        if not self.url or not self.token:raise Problem('cloud_database_configuration',503)
        endpoint(self.url)
        self.transport=transport
        # Stable cursor/profile identity across function instances and redeploys.
        self.identity=hashlib.sha256(self.url.encode()).hexdigest()[:16]
        self.path=Path('/cloud')/self.identity
    def connect(self):return Connection(self.url,self.token,self.transport)
    def assert_ready(self):
        db=self.connect()
        try:
            tables={row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cloud_metadata','cloud_backups','account_security')")}
            if not {'cloud_backups','account_security'}<=tables:raise Problem('cloud_database_uninitialized',503)
            if 'cloud_metadata' in tables:
                row=db.execute("SELECT value FROM cloud_metadata WHERE key='schema_version'").fetchone()
                version=row['value'] if row else None
                if version not in ('3',str(SCHEMA_VERSION)):raise Problem('cloud_database_uninitialized',503)
            elif db.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA_VERSION:
                # Read compatibility for previously migrated libSQL databases.
                # Never create or update schema from a normal API request.
                raise Problem('cloud_database_uninitialized',503)
        finally:db.close()
    def backup_sqlite(self,db=None,label='backup'):
        # Cloud backups stay in protected persistent storage, never ephemeral /tmp.
        owned=db is None;db=db or self.connect()
        try:
            if owned:db.execute('BEGIN IMMEDIATE')
            document=read_document(db)
            rid=str(uuid.uuid4())
            db.execute('INSERT INTO cloud_backups VALUES(?,?,?,?)',(rid,now(),label,encode(document)))
            if owned:db.commit()
            return 'cloud-backup:'+rid
        finally:
            if owned:db.close()
    def reserve_login_attempt(self,key):
        key=hashlib.sha256(encode(key).encode()).hexdigest()
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            cutoff=time.time()-900
            row=db.execute('SELECT data FROM cloud_login_attempts WHERE key=?',(key,)).fetchone()
            attempts=[t for t in json.loads(row['data']) if t>cutoff] if row else []
            if len(attempts)>=10:raise Problem('login_limited',429)
            db.execute('INSERT INTO cloud_login_attempts VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(key,encode(attempts+[time.time()])))
            db.commit()
        finally:db.close()
    def clear_login_attempts(self,key):
        db=self.connect()
        try:
            db.execute('DELETE FROM cloud_login_attempts WHERE key=?',(hashlib.sha256(encode(key).encode()).hexdigest(),));db.commit()
        finally:db.close()

def migrate(source,cloud):
    """Exact account/data migration to an empty target; safe repeat, never overwrite.

    Sessions are deliberately not migrated: the new hostname requires a new login.
    """
    backup=source.backup_sqlite(label='before-vercel-migration')
    local=source.connect()
    try:
        local.execute('BEGIN');document=read_document(local)
    finally:local.close()
    db=cloud.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        tables={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'cloud_metadata' in tables:
            marker=db.execute("SELECT value FROM cloud_metadata WHERE key='schema_version'").fetchone()
            if marker and marker['value'] not in ('3',str(SCHEMA_VERSION)):raise Problem('cloud_migration_conflict',409)
        if any(t in tables for t in TABLES[:4]):
            if not set(TABLES[:4]).issubset(tables):raise Problem('cloud_migration_conflict',409)
            current=read_document(db)
            if any(current.values()):
                if fingerprint(current)!=fingerprint(document):raise Problem('cloud_migration_conflict',409)
                db.executescript(SCHEMA);db.executescript(CLOUD_SCHEMA)
                db.execute("INSERT INTO cloud_metadata(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(SCHEMA_VERSION),))
                db.commit()
                return {'already_migrated':True,'source_backup':str(backup),'counts':{k:len(v) for k,v in document.items()}}
        db.executescript(SCHEMA);db.executescript(CLOUD_SCHEMA)
        for table in TABLES:
            for row in document[table]:
                columns=list(row)
                db.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',tuple(row.values()))
        if fingerprint(read_document(db))!=fingerprint(document):raise Problem('cloud_migration_verification',500)
        # Turso can reject PRAGMA assignments while allowing normal table writes.
        # Keep the cloud schema marker in the same verified migration transaction.
        db.execute("INSERT INTO cloud_metadata(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(SCHEMA_VERSION),))
        db.execute('INSERT INTO cloud_backups VALUES(?,?,?,?)',(str(uuid.uuid4()),now(),'initial-vercel-migration',encode(document)))
        db.commit()
        return {'already_migrated':False,'source_backup':str(backup),'counts':{k:len(v) for k,v in document.items()}}
    finally:db.close()


def upgrade_cloud(cloud,finalize=True):
    """Explicit, backed-up schema-only update. Never called by normal requests."""
    cloud.backup_sqlite(label='before-schema-4')
    db=cloud.connect()
    try:
        db.execute('BEGIN IMMEDIATE');before=read_document(db)
        marker=db.execute("SELECT value FROM cloud_metadata WHERE key='schema_version'").fetchone()
        if not marker or marker['value'] not in ('3',str(SCHEMA_VERSION)):raise Problem('cloud_migration_conflict',409)
        db.executescript(SCHEMA);db.executescript(CLOUD_SCHEMA)
        if fingerprint(read_document(db))!=fingerprint(before):raise Problem('cloud_migration_verification',500)
        if finalize:db.execute("UPDATE cloud_metadata SET value=? WHERE key='schema_version'",(str(SCHEMA_VERSION),))
        db.commit();return {'schema':SCHEMA_VERSION,'original_document_unchanged':True}
    finally:db.close()
