"""Local desktop launcher. Binds to loopback and keeps data outside version folders."""
import argparse, getpass, hashlib, json, os, sys, threading, urllib.request, webbrowser
from pathlib import Path
from .store import Store, Problem, VERSION
from .server import Server


def data_directory():
    if sys.platform=='win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')/'PigLedger'
    if sys.platform=='darwin':return Path.home()/'Library'/'Application Support'/'PigLedger'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local'/'share')/'PigLedger'


def profile_id(db_path):
    return hashlib.sha256(str(Path(db_path).resolve()).encode()).hexdigest()[:16]


def existing_instance(port, expected_profile):
    try:
        # This is a local laptop request, not an outbound proxy operation.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=0.5) as r:
            info=json.load(r)
        if info.get('profile_id')!=expected_profile:return None
        if info.get('version')!=VERSION:raise RuntimeError('Close the older PigLedger window before starting this version. Your data will be kept.')
        return f'http://127.0.0.1:{port}/'
    except (OSError,ValueError):return None


def create_first_account(store, read_name=input, read_password=getpass.getpass):
    db=store.connect()
    try:existing=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    finally:db.close()
    if existing:return False
    print('\nFIRST USE: create your laptop administrator account.')
    print('The cloud development account is not copied to this laptop.')
    username=read_name('Username [farmadmin]: ').strip() or 'farmadmin'
    while True:
        password=read_password('Choose a password (at least 12 characters; typing is hidden): ')
        confirm=read_password('Enter the same password again: ')
        if password!=confirm:print('Passwords differ. Please try again.');continue
        if not 12<=len(password)<=512:print('Password must have 12 to 512 characters.');continue
        try:
            store.create_initial_admin(username,password)
        except Problem as e:
            if e.code=='already_initialized':return False
            raise
        print('Administrator created. Use this username and password in the browser.')
        return True


def open_browser(url):
    if not webbrowser.open(url):print('Please copy the address above into Chrome or Edge.')


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args(argv)
    if sys.version_info<(3,12):raise SystemExit('Python 3.12 or later is required.')
    folder=(args.data_dir or data_directory()).resolve()
    db_path=folder/'data'/'pigledger.sqlite3'
    pid=profile_id(db_path)
    for port in range(args.port,args.port+10):
        address=existing_instance(port,pid)
        if address:
            print('PigLedger is already running:',address)
            if not args.no_browser:open_browser(address)
            return
    folder.mkdir(parents=True,exist_ok=True)
    store=Store(db_path)
    create_first_account(store)
    server=None
    for port in range(args.port,args.port+10):
        try:server=Server(('127.0.0.1',port),store);break
        except OSError as e:
            import errno
            if e.errno not in (errno.EADDRINUSE,10048):raise
            address=existing_instance(port,pid)
            if address:
                if not args.no_browser:open_browser(address)
                return
    if server is None:raise SystemExit('Ports are busy. Close the previous PigLedger window and try again.')
    url=f'http://127.0.0.1:{server.server_port}/'
    print('\nPigLedger '+VERSION+' is ready: '+url)
    print('Your database: '+str(db_path))
    print('Keep this window open while using the app. Ctrl+C stops the app safely.')
    if not args.no_browser:
        timer=threading.Timer(.3,open_browser,args=(url,));timer.daemon=True;timer.start()
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nStopped. All saved records are kept on this laptop.')
    finally:server.server_close()

if __name__=='__main__':main()
