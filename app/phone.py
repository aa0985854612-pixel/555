"""Temporary public HTTPS access to the same laptop database using Quick Tunnel.

No passwords or tunnel credentials are written to logs. The local origin binds only
to loopback; only this launcher's child process is stopped on exit.
"""
import argparse,contextlib,json,os,queue,re,signal,subprocess,sys,threading,time,urllib.request
from pathlib import Path
from .desktop import data_directory,profile_id,existing_instance,create_first_account,open_browser
from .server import Server
from .store import Store,VERSION
from .tunnel_binary import verify_binary

URL_PATTERN=re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com(?![a-z0-9.:-])')

@contextlib.contextmanager
def phone_lock(folder):
    """OS locks survive crashes without leaving a permanent 'already running' flag."""
    path=Path(folder)/'phone.lock'
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RuntimeError('Phone mode is already running. Use the HTTPS address in the other START_PHONE window.')
        try:yield
        finally:
            stream.seek(0)
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)

def remote_health(url,expected_profile):
    """Use normal certificate verification and configured outbound proxies."""
    request=urllib.request.Request(url+'/api/health',headers={'Cache-Control':'no-cache'})
    try:
        with urllib.request.urlopen(request,timeout=4) as response:info=json.load(response)
        return info.get('ok') is True and info.get('version')==VERSION and info.get('profile_id')==expected_profile
    except (OSError,ValueError):return False

class QuickTunnel:
    def __init__(self,binary,local_url,config,process_factory=subprocess.Popen):
        self.url=None;self.connected=False;self.events=queue.Queue()
        command=[str(binary),'tunnel','--config',str(config),'--no-autoupdate','--metrics','127.0.0.1:0','--management-diagnostics=false','--protocol','http2','--loglevel','info','--url',local_url]
        options={'stdout':subprocess.PIPE,'stderr':subprocess.STDOUT,'stdin':subprocess.DEVNULL,'text':True,'encoding':'utf-8','errors':'replace','bufsize':1}
        options['env']={key:value for key,value in os.environ.items() if not key.startswith('TUNNEL_') and key not in ('NO_TLS_VERIFY','NO_AUTOUPDATE')}
        # Inherit the launcher's console: Windows window-close/Ctrl+C reaches
        # the owned connector too, instead of leaving a hidden detached child.
        self.process=process_factory(command,**options)
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                # Keep only lifecycle markers, never raw Cloudflare logs/credentials.
                match=URL_PATTERN.search(line)
                if match:self.events.put(('url',match.group(0)))
                if 'Registered tunnel connection' in line:self.events.put(('connected',True))
                if 'Unregistered tunnel connection' in line:self.events.put(('connected',False))
        finally:self.events.put(('ended',None))

    def update(self,timeout=.2):
        try:kind,value=self.events.get(timeout=timeout)
        except queue.Empty:return
        if kind=='url':self.url=value
        elif kind=='connected':self.connected=value
        elif kind=='ended':self.connected=False

    def wait_ready(self,expected_profile,timeout=120,check=remote_health):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.update()
            if self.process.poll() is not None:raise RuntimeError('HTTPS connector stopped before connecting. Check Internet/firewall, then restart START_PHONE.bat.')
            if self.url and self.connected and check(self.url,expected_profile):return self.url
        raise RuntimeError('HTTPS connection could not be verified. Your records are kept. Check Internet/firewall and retry; START_WINDOWS.bat still works on the laptop.')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        if self.process.stdout:self.process.stdout.close()

def run(folder,binary,no_browser=False,timeout=120):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    platform='windows-amd64' if sys.platform=='win32' else 'linux-amd64'
    binary=verify_binary(binary,platform)
    with phone_lock(folder):
        # Refuse to migrate a database still served by an older desktop version.
        # A same-version desktop may keep running against the shared database.
        for port in range(8080,8090):existing_instance(port,profile_id(folder/'data'/'pigledger.sqlite3'))
        store=Store(folder/'data'/'pigledger.sqlite3')
        create_first_account(store)
        store.backup_sqlite(label='before-phone-'+VERSION)
        # An explicit empty config prevents loading another Cloudflare account's tunnel.
        config=folder/'phone-connector.yml';config.write_text('{}\n',encoding='utf-8')
        url_file=folder/'PHONE_URL.txt';url_file.unlink(missing_ok=True)
        server=Server(('127.0.0.1',0),store,secure=True)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        tunnel=None
        try:
            print('\nPigLedger '+VERSION+' — 手機外出連線模式',flush=True)
            print('正在建立 HTTPS 連線，請稍候。筆電必須保持開機、連網。',flush=True)
            tunnel=QuickTunnel(binary,f'http://127.0.0.1:{server.server_port}',config)
            url=tunnel.wait_ready(profile_id(store.path),timeout,check=remote_health)
            server.public_host=url.removeprefix('https://')
            url_file.write_text(url+'/\n',encoding='utf-8')
            print('\n手機網址（已檢查連線）： '+url+'/',flush=True)
            print('在手機 Safari 或 Chrome 輸入這個網址，用筆電的同一個帳號密碼登入。',flush=True)
            print('網址也存到： '+str(url_file),flush=True)
            print('請保留此視窗。不要讓筆電睡眠。按 Ctrl+C 停止手機連線，資料會保留。',flush=True)
            print('這是臨時網址，下次啟動可能改變，並非全天候正式雲端主機。',flush=True)
            if not no_browser:open_browser(url+'/')
            last_check=time.monotonic();was_online=True
            while True:
                tunnel.update(.5)
                if tunnel.process.poll() is not None:raise RuntimeError('Phone connection ended. Restart START_PHONE.bat to get a new HTTPS address. Your data is kept.')
                if time.monotonic()-last_check>=15:
                    online=remote_health(url,profile_id(store.path))
                    if online!=was_online:
                        print('手機連線已恢復。' if online else '手機連線暫時中斷：尚未確認送出的紀錄請在 App 重試，勿重填。',flush=True)
                    was_online=online;last_check=time.monotonic()
        finally:
            if tunnel:tunnel.close()
            server.shutdown();server.server_close();worker.join(timeout=2)
            url_file.unlink(missing_ok=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Temporary HTTPS phone access; same laptop accounts and records.')
    parser.add_argument('--data-dir',type=Path);parser.add_argument('--connector',type=Path)
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--startup-timeout',type=float,default=120)
    args=parser.parse_args(argv)
    if sys.version_info<(3,12):raise SystemExit('Python 3.12 or later is required.')
    asset='cloudflared-windows-amd64.exe' if sys.platform=='win32' else 'cloudflared-linux-amd64'
    binary=args.connector or Path(__file__).resolve().parents[1]/'connectors'/asset
    previous=signal.getsignal(signal.SIGTERM)
    def stop(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:run(args.data_dir or data_directory(),binary,args.no_browser,args.startup_timeout)
    except KeyboardInterrupt:print('\n手機連線已停止，已儲存的帳號與紀錄保留在筆電。')
    except (RuntimeError,OSError) as e:print('啟動未完成： '+str(e),flush=True);return 1
    finally:signal.signal(signal.SIGTERM,previous)
    return 0

if __name__=='__main__':raise SystemExit(main())
