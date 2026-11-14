import io, json, os, sys, tempfile, threading, unittest, tarfile
from pathlib import Path
from datetime import date, timedelta
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import domain as d
import server as s

class Rules(unittest.TestCase):
    def test_rotation(self):
        for day,person in [('2026-11-12','Jody'),('2026-11-18','Jody'),('2026-11-19','Marcus'),('2026-11-25','Marcus'),('2026-11-26','Jody'),('2027-01-07','Jody')]:
            self.assertEqual(d.worker(date.fromisoformat(day)),person)
    def test_brandon_preserves_future(self):
        self.assertEqual(d.worker(date(2026,11,15),{'2026-11-12':'Brandon'}),'Brandon')
        self.assertEqual(d.worker(date(2026,11,19),{'2026-11-12':'Brandon'}),'Marcus')
        self.assertEqual(d.worker(date(2026,11,15),{'2026-11-12':'Brandon'},{'2026-11-15':'Jody'}),'Jody')
    def test_bottles(self):
        for i in range(7): self.assertEqual(d.bottle_order(date(2026,11,23)+timedelta(days=i)),date(2026,11,18))
    def test_seed_exceptions(self):
        rows=d.seed_requirements(); self.assertEqual(len(rows),59)
        self.assertFalse(any(r['facility']=='D01' for r in rows))
        find=lambda f,g: next(r for r in rows if r['facility']==f and r['group']==g)
        for f,g,end in [('P05','VOC','2026-12-31'),('P03','VOC','2028-12-31'),('P08','Combined radium','2031-12-31'),('P07','Combined radium','2034-12-31')]:
            self.assertEqual(find(f,g)['window_end'],end)
    def test_month_end(self):
        event=dict(date='2027-01-31',repeat='monthly')
        self.assertEqual([x['date'] for x in d.event_occurrences(event,date(2027,1,1),date(2027,3,31))],['2027-01-31','2027-02-28','2027-03-31'])
    def test_leap_day(self):
        event=dict(date='2024-02-29',repeat='yearly',repeat_until='2028-12-31')
        self.assertEqual([x['date'] for x in d.event_occurrences(event,date(2026,1,1),date(2028,12,31))],['2026-02-28','2027-02-28','2028-02-29'])
    def test_balancing(self):
        rows=[dict(id=i,reviewed=True,stage='Planned',planned=None,cost=100,window_start='2027-01-01',window_end='2028-12-31') for i in range(4)]
        plan=d.propose(rows,date(2026,11,14),100)
        self.assertEqual(len({p['planned'][:7] for p in plan}),4)
        self.assertTrue(all('2027-01-01'<=p['planned']<='2028-12-31' for p in plan))
    def test_conflicts_and_unknown_cost(self):
        r=dict(id=1,reviewed=True,stage='Planned',planned=None,cost=500,window_start='2026-01-01',window_end='2026-12-31')
        self.assertIn('conflict',d.propose([r],date(2026,11,14),100)[0])
        self.assertIn('conflict',d.propose([r],date(2027,1,1))[0])
        self.assertEqual(r['window_end'],'2026-12-31')
        r['cost']=None
        with self.assertRaises(ValueError):d.propose([r],date(2026,11,14))
        r['reviewed']=False
        self.assertEqual(d.propose([r],date(2026,11,14)),[])

class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();s.DATA=Path(cls.temp.name);s.DB=s.DATA/'calendar.sqlite3'
        os.environ['ADMIN_PASSWORD']='testing-password-12345';s.initialize()
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),s.Handler)
        cls.base=f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
    def setUp(self):self.client=build_opener(HTTPCookieProcessor(CookieJar()));self.csrf=''
    def req(self,path,body=None,method=None):
        h={'Content-Type':'application/json','X-CSRF-Token':self.csrf}
        payload=json.dumps(body).encode() if body is not None else None
        with self.client.open(Request(self.base+path,data=payload,headers=h,method=method)) as r:
            result=r.read();return json.loads(result) if r.headers['Content-Type'].startswith('application/json') else result
    def login(self):self.csrf=self.req('/api/login',{'password':'testing-password-12345'})['csrf']
    def test_private_state(self):
        with self.assertRaises(HTTPError) as cm:self.req('/api/state')
        self.assertEqual(cm.exception.code,401)
    def test_csrf(self):
        self.login();self.csrf='wrong'
        with self.assertRaises(HTTPError) as cm:self.req('/api/navigation',{'month':'2027-02'})
        self.assertEqual(cm.exception.code,403)
    def test_shared_navigation(self):
        self.login();self.req('/api/navigation',{'month':'2027-02'})
        self.assertEqual(self.req('/api/state')['wall_month'],'2027-02')
        self.req('/api/navigation',{'month':None})
    def test_event_export(self):
        self.login();row=self.req('/api/events',dict(title='Pump inspection',date='2027-02-01',end_date='',kind='maintenance',repeat='weekly',repeat_until='2027-02-15',notes='Check seal',employee='Jody'))
        events=self.req('/api/events?start=2027-02-01&end=2027-02-28')
        self.assertEqual(len([e for e in events if e.get('id')==row['id']]),3)
        md=self.req('/api/export?start=2027-02-01&end=2027-02-15').decode()
        self.assertIn('Pump inspection',md);self.assertIn('Responsible:',md)
    def test_window_and_completion_validation(self):
        self.login();r=self.req('/api/state')['requirements'][0];r.update(reviewed=True,planned='2029-01-01')
        with self.assertRaises(HTTPError):self.req('/api/requirements',r)
        r.update(planned=None,stage='Complete',actual=None)
        with self.assertRaises(HTTPError):self.req('/api/requirements',r)
    def test_bottle_events(self):
        self.login();r=self.req('/api/state')['requirements'][0];r.update(reviewed=True,planned='2026-12-08',cost=200,stage='Planned')
        self.req('/api/requirements',r);events=self.req('/api/events?start=2026-12-01&end=2026-12-10')
        self.assertTrue(any(e['kind']=='bottles' and e['date']=='2026-12-02' for e in events))
        self.assertTrue(any(e['kind']=='sample' and e['date']=='2026-12-08' for e in events))
    def test_backup(self):
        self.login()
        with tarfile.open(fileobj=io.BytesIO(self.req('/api/backup')),mode='r:gz') as f:self.assertIn('calendar.sqlite3',f.getnames())
    def test_concurrent_edits_rejected(self):
        self.login();row=self.req('/api/events',dict(title='Concurrency test',date='2027-01-01',kind='general',repeat='none'))
        stale={**row};row['title']='First edit';self.req('/api/events',row)
        stale['title']='Stale edit'
        with self.assertRaises(HTTPError) as cm:self.req('/api/events',stale)
        self.assertEqual(cm.exception.code,409)
    def test_month_rollover_and_idle_reset(self):
        import time
        from datetime import datetime
        from zoneinfo import ZoneInfo
        settings={**s.DEFAULTS,'wall_month':'2026-10','wall_day':'2026-11-30','wall_changed':time.time()}
        self.assertEqual(s.wall_month(settings,datetime(2026,12,1,tzinfo=ZoneInfo('America/New_York'))),'2026-12')
        settings['wall_changed']=time.time()-301
        self.assertEqual(s.wall_month(settings,datetime(2026,11,14,tzinfo=ZoneInfo('America/New_York'))),'2026-11')
    def test_public_power(self):self.assertEqual(set(self.req('/api/display-state')),{'active','timezone','on','off'})
    def test_directory_escape(self):
        with self.assertRaises(HTTPError) as cm:self.req('/../server.py')
        self.assertEqual(cm.exception.code,404)

if __name__=='__main__':unittest.main()
