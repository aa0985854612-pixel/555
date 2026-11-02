"""Disposable representative farm shared by workspace design acceptance scripts."""
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import tempfile,threading,uuid
from app.store import Store
from app.server import Server
from app.review import farm_today
from app.domain import day
@contextmanager
def workspace_fixture(cloud=False):
 with tempfile.TemporaryDirectory() as tmp:
  store=Store(Path(tmp)/'db');admin=store.create_user('owner','83000111');staff=store.create_user('worker','83000112','staff');reader=store.create_user('reader','83000113','viewer');start=day(farm_today())-timedelta(days=90)
  def on(n):return (start+timedelta(days=n)).isoformat()
  def add(kind,**body):return store.mutate(admin,kind,body,str(uuid.uuid4()))
  barns={n:add('barns',name=f'{n}棟',feed_vendor='養全' if n in (1,2,12,14) else '新農科') for n in (1,2,8,12,14,24)}
  batches={}
  for n,barn in barns.items():batches[n]=add('batches',name='JD-DEMO-31' if n in (1,2) else 'JD-DEMO-'+str(n),barn_id=barn['id'],entry_date=on(0),entry_count=50 if n==24 else 700 if n==2 else 500,status='active',entry_age_days=70,entry_mean_kg=23.5,**({'same_batch_as':batches[1]['id']} if n==2 else {}))
  bins={}
  for name,ns in [('1、2',(1,2)),('8',(8,)),('12',(12,)),('14-1',(14,)),('24',(24,))]:bins[name]=add('feed_bins',name=name,barn_ids=[barns[n]['id'] for n in ns],vendor='新農科' if ns[0]==8 else '養全',active=True)
  for i in range(35):add('movements',date=on(10+i),batch_id=batches[(1,2,8,12,14)[i%5]]['id'],type='death',quantity=1,note='巡場登記 '+str(i+1))
  for i in range(8):add('movements',date=on(60+i*3),batch_id=batches[1 if i%2 else 8]['id'],type='sale',quantity=20+i,outgoing_destination=('嘉義','南投')[i%2],outgoing_trip='第1車' if i%2 else '第2車')
  add('movements',date=on(82),batch_id=batches[24]['id'],type='sale',quantity=50,outgoing_destination='嘉義')
  for i in range(18):
   bin=bins[('1、2','8','12','14-1')[i%4]];add('feed_orders',date=on(20+i*3),kg=(2+i%3)*1000,display_unit='ton',feed_bin_id=bin['id'],target_batch_ids=[b['id'] for b in batches.values() if b['barn_id'] in bin['barn_ids']],item='大豬料' if i%3==0 else '仔豬料',note='飼料登記 '+str(i+1))
  for kg,unit in ((1250,'ton'),(1500,'ton'),(1000,'kg')):add('deliveries',date=on(80),kg=kg,display_unit=unit,allocations=[{'batch_id':batches[8]['id'],'kg':kg}],item='仔豬料',vendor='新農科',note='舊到料紀錄')
  for n in (1,8,14):
   for date,mean in [(on(15),55),(on(50),75)]:add('weights',date=date,batch_id=batches[n]['id'],individual_kg=[mean-5,mean-2,mean,mean+1,mean+2,mean+4],pen='1A',representative=True)
  remote=None
  if cloud:
   from app.cloud_store import CloudStore,migrate
   from cloud_fixture import HranaFixture
   remote=HranaFixture(Path(tmp)/'remote');target=CloudStore('libsql://test.turso.io','synthetic-token',remote);migrate(store,target);store=target
  server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:yield {'store':store,'admin':admin,'staff':staff,'reader':reader,'barns':barns,'batches':batches,'bins':bins,'on':on,'url':f'http://127.0.0.1:{server.server_port}'}
  finally:
   server.shutdown();server.server_close()
   if remote:remote.close()
