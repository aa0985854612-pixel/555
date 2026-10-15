"""Vercel Python entry point. Reuses the same routes, rules and server permissions."""
import threading
import time
import hashlib
from types import SimpleNamespace
from urllib.parse import urlparse
from app.server import Handler
from app.store import Problem
from app.cloud_store import CloudStore

_ready={}
_ready_lock=threading.Lock()

class handler(Handler):
    def run(self,method):
        original=self.server
        # Error responses also need the HTTPS context, including missing credentials.
        self.server=SimpleNamespace(store=None,secure=True,public_host=None,
            instance='',login_attempts={},lock=threading.Lock())
        try:
            store=CloudStore() if urlparse(self.path).path.startswith('/api/') else None
            self.server.store=store
            self.server.instance=store.identity if store else ''
            # Never expose a misleading green health result for an uninitialized DB.
            if store:
                key=hashlib.sha256((store.url+'\0'+store.token).encode()).hexdigest()
                with _ready_lock:ready=_ready.get(key,0)>time.monotonic()
                if not ready:
                    store.assert_ready()
                    with _ready_lock:
                        if len(_ready)>64:_ready.clear()
                        _ready[key]=time.monotonic()+30
            super().run(method)
        except Problem as e:self.send({'error':e.code},e.status)
        finally:self.server=original
