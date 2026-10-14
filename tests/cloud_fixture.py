"""Hrana protocol simulator backed by isolated SQLite, NOT the live Turso service."""
import sqlite3
import threading
import uuid
from app.cloud_store import value_in, value_out

class HranaFixture:
    def __init__(self,path):
        self.path=path;self.streams={};self.lock=threading.Lock();self.requests=0
    def __call__(self,url,payload):
        with self.lock:
            self.requests+=1
            baton=payload.get('baton')
            if baton:
                db=self.streams[baton]
            else:
                baton=str(uuid.uuid4())
                db=sqlite3.connect(self.path,timeout=10,check_same_thread=False,isolation_level=None)
                db.execute('PRAGMA journal_mode=WAL')
                self.streams[baton]=db
        responses=[]
        for request in payload['requests']:
            typ=request['type']
            if typ=='close':
                db.close()
                with self.lock:del self.streams[baton]
                baton=None;response={'type':'close'}
            elif typ=='execute':response={'type':'execute','result':self.execute(db,request['stmt'])}
            elif typ=='batch':
                results=[];errors=[]
                for step in request['batch']['steps']:
                    cond=step.get('condition')
                    if cond and results[cond['step']] is None:
                        results.append(None);errors.append(None);continue
                    try:
                        results.append(self.execute(db,step['stmt']));errors.append(None)
                    except sqlite3.Error as e:
                        results.append(None);errors.append({'code':getattr(e,'sqlite_errorname','SQLITE_ERROR')})
                response={'type':'batch','result':{'step_results':results,'step_errors':errors}}
            else:raise AssertionError('Unknown protocol request')
            responses.append({'type':'ok','response':response})
        return {'baton':baton,'base_url':None,'results':responses}
    def execute(self,db,stmt):
        cursor=db.execute(stmt['sql'],[value_in(v) for v in stmt['args']])
        cols=[{'name':c[0],'decltype':None} for c in cursor.description or []]
        rows=[[value_out(v) for v in r] for r in cursor.fetchall()] if cols else []
        return {'cols':cols,'rows':rows,'affected_row_count':max(0,cursor.rowcount),'last_insert_rowid':str(cursor.lastrowid or 0)}
    def close(self):
        for db in self.streams.values():db.close()
        self.streams.clear()
