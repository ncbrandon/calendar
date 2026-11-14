#!/usr/bin/env python3
"""Waterworks Calendar 1.0 — dependency-free, local/VPN small-team server."""
import base64
import hashlib
import hmac
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sqlite3
import tarfile
import threading
import time
from datetime import date, datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from domain import (PEOPLE, FACILITIES, parse_date, week_start, worker, bottle_order,
                    month_add, shift_year, event_occurrences, holidays, seed_requirements, propose)

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('DATA_DIR', ROOT/'data')).resolve()
DB=DATA/'calendar.sqlite3'
LOCK=threading.RLock()
SESSIONS={}
LOGIN_ATTEMPTS={}
WEATHER={'time':0,'value':None,'key':None}
STAGES=['Verify records','Planned','Ordered','Received','Collected','Delivered','Results received','Reviewed','Complete','Resample needed']
DEFAULTS=dict(title='West Jefferson · Waterworks', timezone='America/New_York',
    workdays=[0,1,2,3,4], on='07:00', off='17:00', effects='seasonal',
    holidays=True, payroll_enabled=False, payroll_start=3, payday=4,
    latitude=None, longitude=None, monthly_budget=None, wall_month=None, wall_changed=0,
    dark_dates=[], wake_until=0)

class Problem(Exception):
    def __init__(self,message,status=400): self.message,self.status=message,status

def connect():
    con=sqlite3.connect(DB,timeout=20)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    return con

def now(): return datetime.now(ZoneInfo(settings()['timezone']))
def settings():
    with connect() as c: return json.loads(c.execute("SELECT value FROM meta WHERE key='settings'").fetchone()[0])
def set_settings(s):
    with connect() as c: c.execute("UPDATE meta SET value=? WHERE key='settings'",(json.dumps(s),))
def rows(table):
    with connect() as c: return [dict(id=r['id'],**json.loads(r['data'])) for r in c.execute(f'SELECT id,data FROM {table} ORDER BY id')]
def save_row(table,payload,row_id=None):
    body={k:v for k,v in payload.items() if k!='id'}
    with connect() as c:
        if row_id:
            old=c.execute(f'SELECT data FROM {table} WHERE id=?',(int(row_id),)).fetchone()
            if not old: raise Problem('Record not found.',404)
            revision=json.loads(old['data']).get('revision',0)
            if payload.get('revision',0)!=revision: raise Problem('Another editor changed this record. Close, refresh, and reopen it.',409)
            body['revision']=revision+1
            c.execute(f'UPDATE {table} SET data=? WHERE id=?',(json.dumps(body),int(row_id)))
        else:
            body['revision']=1
            row_id=c.execute(f'INSERT INTO {table}(data) VALUES(?)',(json.dumps(body),)).lastrowid
    return dict(id=int(row_id),**body)
def audit(action,payload):
    with connect() as c: c.execute('INSERT INTO audit(time,action,data) VALUES(?,?,?)',(datetime.now().isoformat(),action,json.dumps(payload)))
def hash_password(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode(),salt,300000).hex()
def initialize():
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/'uploads').mkdir(exist_ok=True)
    with connect() as c:
        c.executescript('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS requirements(id INTEGER PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS assignments(date TEXT,scope TEXT,person TEXT,PRIMARY KEY(date,scope)); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,time TEXT,action TEXT,data TEXT);')
        if not c.execute("SELECT 1 FROM meta WHERE key='settings'").fetchone():
            c.execute('INSERT INTO meta VALUES(?,?)',('settings',json.dumps(DEFAULTS)))
        if not c.execute("SELECT 1 FROM meta WHERE key='password'").fetchone():
            password=os.environ.get('ADMIN_PASSWORD','')
            if len(password)<12: raise RuntimeError('Set ADMIN_PASSWORD to at least 12 characters on first start.')
            salt=secrets.token_bytes(16)
            c.execute('INSERT INTO meta VALUES(?,?)',('password',json.dumps({'salt':salt.hex(),'hash':hash_password(password,salt)})))
        if not c.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
            for r in seed_requirements(): c.execute('INSERT INTO requirements(data) VALUES(?)',(json.dumps(r),))
            c.execute('INSERT INTO meta VALUES(?,?)',('seeded','1'))

def get_assignments():
    with connect() as c:
        allrows=c.execute('SELECT * FROM assignments').fetchall()
    return ({r['date']:r['person'] for r in allrows if r['scope']=='week'}, {r['date']:r['person'] for r in allrows if r['scope']=='day'})

def validate_requirement(r):
    if r.get('facility') not in FACILITIES: raise Problem('Choose a listed P-code; D01 is excluded.')
    if not isinstance(r.get('group'),str) or not r['group'].strip(): raise Problem('A sample group is required.')
    start,end=parse_date(r['window_start']),parse_date(r['window_end'])
    if start>end: raise Problem('Window end precedes window start.')
    if not isinstance(r.get('years'),int) or not 1<=r['years']<=20: raise Problem('Recurrence must be 1–20 years.')
    if not isinstance(r.get('reviewed'),bool): raise Problem('Review flag must be true or false.')
    if r.get('stage') not in STAGES: raise Problem('Unknown sample stage.')
    if r.get('cost') is not None:
        if not isinstance(r['cost'],(int,float)) or not 0<=r['cost']<=10000000: raise Problem('Enter a valid estimated cost.')
    if r.get('planned'):
        d=parse_date(r['planned'])
        if not r['reviewed']: raise Problem('Review the requirement before planning collection.')
        if not start<=d<=end: raise Problem('Collection must fall inside the approved window.')
    if r.get('actual'):
        d=parse_date(r['actual'])
        if d>now().date(): raise Problem('Actual collection cannot be in the future.')
    if r.get('stage')=='Complete' and (not r.get('actual') or not r['reviewed']):
        raise Problem('Completion requires review and an actual collection date. Confirm accepted results/reporting before closing.')
    if r.get('stage') in ['Collected','Delivered','Results received','Reviewed'] and not r.get('actual'):
        raise Problem('Enter the actual collection date for this stage.')
    return r

def generated_events(start,end):
    out=[]
    for e in rows('events'): out.extend(event_occurrences(e,start,end))
    s=settings()
    if s['holidays']:
        for y in range(start.year-1,end.year+2):
            for d,name in holidays(y):
                if start<=d<=end: out.append(dict(date=str(d),title=name,kind='holiday',notes='Federal reference holiday; configure facility closures separately.'))
    for r in rows('requirements'):
        planned=r.get('planned')
        deadline=r['window_end']
        if r['stage']=='Complete':
            day=r.get('actual') or planned
            if day and str(start)<=day<=str(end): out.append(dict(date=day,title=f"✓ {r['facility']} · {r['group']}",kind='complete',requirement_id=r['id']))
            continue
        if str(start)<=deadline<=str(end):
            out.append(dict(date=deadline,title=f"{'DEADLINE' if r['reviewed'] else 'VERIFY'} · {r['facility']} {r['group']}",kind='deadline',requirement_id=r['id']))
        if planned:
            if str(start)<=planned<=str(end): out.append(dict(date=planned,title=f"Pull · {r['facility']} {r['group']}",kind='sample',requirement_id=r['id']))
            order=str(bottle_order(parse_date(planned)))
            if str(start)<=order<=str(end): out.append(dict(date=order,title=f"Bottles · {r['facility']} {r['group']}",kind='bottles',requirement_id=r['id']))
    if s['payroll_enabled']:
        d=start
        while d<=end:
            if d.weekday()==s['payroll_start']: out.append(dict(date=str(d),title='Payroll week begins',kind='payroll'))
            if d.weekday()==(s['payroll_start']+6)%7: out.append(dict(date=str(d),title='Payroll week ends',kind='payroll'))
            if d.weekday()==s['payday']: out.append(dict(date=str(d),title='Payday',kind='payroll'))
            d+=timedelta(days=1)
    return sorted(out,key=lambda e:(e['date'],e.get('time',''),e['title']))

def weather(s):
    if s.get('latitude') is None or s.get('longitude') is None: return None
    key=(s['latitude'],s['longitude'])
    if WEATHER['key']!=key or time.time()-WEATHER['time']>900:
        try:
            u=f"https://api.open-meteo.com/v1/forecast?latitude={key[0]}&longitude={key[1]}&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=auto"
            with urlopen(u,timeout=4) as res: value=json.load(res)['current']
            WEATHER.update(key=key,time=time.time(),value=value)
        except Exception:
            # Retain last data with its age; the browser falls back after 30 minutes.
            if WEATHER['key']!=key: WEATHER.update(key=key,time=0,value=None)
    return {'current':WEATHER['value'],'fetched':WEATHER['time'],'stale':time.time()-WEATHER['time']>1800}

def wall_month(s,t):
    if not s['wall_month'] or time.time()-s['wall_changed']>300 or s.get('wall_day',str(t.date()))[:7]!=t.strftime('%Y-%m'): return t.strftime('%Y-%m')
    return s['wall_month']

def export_markdown(start,end):
    weeks,days=get_assignments()
    events=generated_events(start,end)
    reqs={r['id']:r for r in rows('requirements')}
    def clean(v): return str(v).replace('\r','').replace('\n','\n  ')
    lines=['# Waterworks Calendar',f'\nPeriod: {start} through {end}',f'\nExported: {now().isoformat()}', '\nRotation: Thursday–Wednesday; Jody anchored November 12, 2026.','\nD01 excluded. Draft requirements are unverified source records.']
    d=start
    while d<=end:
        lines += [f'\n## {d:%A, %Y-%m-%d}', f'\nResponsible: {worker(d,weeks,days)}']
        for e in events:
            if e['date']!=str(d): continue
            lines += [f"\n### {clean(e['title'])}", f"- Type: {e['kind']}"]
            if e.get('notes'): lines.append('- Notes: '+clean(e['notes']))
            if e.get('time'): lines.append('- Time: '+clean(e['time']))
            if e.get('requirement_id'):
                r=reqs[e['requirement_id']]
                for k in ['window_start','window_end','stage','planned','actual','cost','source','source_status','notes']:
                    lines.append(f'- {k.replace("_"," ").capitalize()}: {clean(r.get(k))}')
        d+=timedelta(days=1)
    lines += ['\n## Requirement register (all periods)']
    for r in reqs.values():
        lines += [f"\n- {r['facility']} / {clean(r['group'])}: {r['window_start']}–{r['window_end']}; {r['stage']}; reviewed={r['reviewed']}; planned={r.get('planned')}; actual={r.get('actual')}; cost={r.get('cost')}; source={clean(r['source'])}"]
    return '\n'.join(lines)+'\n'

class Handler(BaseHTTPRequestHandler):
    server_version='WaterworksCalendar/1.0'
    def log_message(self,fmt,*args):
        # Never log query strings, passwords, session cookies, or file bodies.
        print(f'{self.address_string()} {self.command} {urlparse(self.path).path}',flush=True)
    def send(self,status,body=b'',content_type='application/json',extra=None):
        if isinstance(body,(dict,list)): body=json.dumps(body).encode()
        elif isinstance(body,str): body=body.encode()
        self.send_response(status)
        for k,v in {'Content-Type':content_type,'Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Content-Security-Policy':"default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",**(extra or {})}.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)
    def body(self,limit=2*1024*1024):
        n=int(self.headers.get('Content-Length','0'))
        if n<0 or n>limit: raise Problem('Upload exceeds allowed size.',413)
        return self.rfile.read(n)
    def json_body(self):
        obj=json.loads(self.body())
        if not isinstance(obj,dict): raise Problem('Expected a JSON object.')
        return obj
    def auth(self,write=False):
        jar=cookies.SimpleCookie()
        try: jar.load(self.headers.get('Cookie',''))
        except cookies.CookieError: raise Problem('Sign in required.',401)
        token=jar.get('ww_session')
        sess=SESSIONS.get(token.value if token else '')
        if not sess or sess['expires']<time.time(): raise Problem('Sign in required.',401)
        if write and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),sess['csrf']): raise Problem('Refresh the page and sign in again.',403)
        return sess
    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def do_DELETE(self): self.route('DELETE')
    def route(self,method):
        try:
            if method=='GET': self.get()
            else:
                with LOCK: self.mutate(method)
        except Problem as e: self.send(e.status,{'error':e.message})
        except (ValueError,KeyError,TypeError,OverflowError) as e: self.send(400,{'error':f'Invalid input: {e}'})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception:
            import traceback; traceback.print_exc()
            self.send(500,{'error':'Server error. See server log; your previous saved records are retained.'})
    def get(self):
        u=urlparse(self.path); p=u.path; q=parse_qs(u.query)
        if p=='/api/health': return self.send(200,{'ok':True,'version':'1.0.0'})
        if p=='/api/display-state':
            s=settings(); t=now(); active=(t.weekday() in s['workdays'] and str(t.date()) not in s['dark_dates'] and s['on']<=t.strftime('%H:%M')<s['off']) or s['wake_until']>time.time()
            return self.send(200,{'active':active,'timezone':s['timezone'],'on':s['on'],'off':s['off']})
        if p=='/api/session':
            sess=self.auth(); return self.send(200,{'csrf':sess['csrf']})
        if p.startswith('/api/') or p.startswith('/uploads/'):
            self.auth()
        if p=='/api/state':
            s=settings(); t=now(); weeks,days=get_assignments()
            return self.send(200,dict(settings=s,today=str(t.date()),server_time=t.isoformat(),wall_month=wall_month(s,t),requirements=rows('requirements'),files=rows('files'),media=rows('media'),weeks=weeks,days=days,weather=weather(s),stages=STAGES))
        if p=='/api/events':
            start=parse_date(q.get('start',[str(now().date())])[0]); end=parse_date(q.get('end',[str(start)])[0])
            if end<start or (end-start).days>1100: raise Problem('Choose up to three years.')
            return self.send(200,generated_events(start,end))
        if p=='/api/export':
            start=parse_date(q['start'][0]); end=parse_date(q['end'][0])
            if end<start or (end-start).days>3660: raise Problem('Choose up to ten years.')
            return self.send(200,export_markdown(start,end),'text/markdown; charset=utf-8',{'Content-Disposition':'attachment; filename="waterworks-calendar.md"'})
        if p=='/api/backup':
            with LOCK:
                out=io.BytesIO()
                temp=DATA/'snapshot.sqlite3'
                try:
                    with connect() as source, sqlite3.connect(temp) as target: source.backup(target)
                    with tarfile.open(fileobj=out,mode='w:gz') as archive:
                        archive.add(temp,arcname='calendar.sqlite3')
                        archive.add(DATA/'uploads',arcname='uploads')
                    return self.send(200,out.getvalue(),'application/gzip',{'Content-Disposition':'attachment; filename="waterworks-backup.tar.gz"'})
                finally: temp.unlink(missing_ok=True)
        if p.startswith('/uploads/'):
            name=p.split('/')[-1]
            if not name or '/' in unquote(name) or '..' in name: raise Problem('Not found.',404)
            path=DATA/'uploads'/name
            if not path.is_file(): raise Problem('Not found.',404)
            ctype=mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if ctype=='application/pdf': return self.send(200,path.read_bytes(),ctype,{'Content-Disposition':'attachment; filename="document.pdf"'})
            return self.send(200,path.read_bytes(),ctype)
        if p.startswith('/api/'): raise Problem('Not found.',404)
        name=p.lstrip('/') or 'index.html'
        path=(ROOT/'static'/name).resolve()
        if not path.is_relative_to(ROOT/'static') or not path.is_file(): raise Problem('Not found.',404)
        return self.send(200,path.read_bytes(),mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
    def mutate(self,method):
        p=urlparse(self.path).path
        if p=='/api/login' and method=='POST':
            body=self.json_body(); address=self.client_address[0]; attempts=LOGIN_ATTEMPTS.get(address,[])
            attempts=[t for t in attempts if time.time()-t<300]
            if len(attempts)>=10: raise Problem('Too many attempts. Wait five minutes.',429)
            with connect() as c: saved=json.loads(c.execute("SELECT value FROM meta WHERE key='password'").fetchone()[0])
            password=body.get('password','')
            if not isinstance(password,str) or not hmac.compare_digest(hash_password(password,bytes.fromhex(saved['salt'])),saved['hash']):
                LOGIN_ATTEMPTS[address]=attempts+[time.time()]; raise Problem('Incorrect password.',401)
            LOGIN_ATTEMPTS.pop(address,None)
            # Drop expired sessions so long-lived kiosks do not leak session entries.
            for key in list(SESSIONS):
                if SESSIONS[key]['expires']<time.time(): del SESSIONS[key]
            token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
            SESSIONS[token]={'csrf':csrf,'expires':time.time()+30*86400}
            secure='; Secure' if os.environ.get('COOKIE_SECURE')=='1' else ''
            return self.send(200,{'csrf':csrf},'application/json',{'Set-Cookie':f'ww_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000{secure}'})
        sess=self.auth(write=True)
        if p=='/api/logout':
            jar=cookies.SimpleCookie(self.headers.get('Cookie','')); SESSIONS.pop(jar['ww_session'].value,None)
            return self.send(200,{'ok':True},extra={'Set-Cookie':'ww_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict'})
        if method=='DELETE':
            _,_,table,rowid=p.split('/')
            if table not in ['events','media']: raise Problem('Deletion is only available for events and media schedules.')
            with connect() as c: c.execute(f'DELETE FROM {table} WHERE id=?',(int(rowid),))
            audit('delete '+table,{'id':rowid}); return self.send(200,{'ok':True})
        if p=='/api/upload':
            name=Path(unquote(self.headers.get('X-Filename','upload'))).name
            ext=Path(name).suffix.lower()
            if ext not in ['.pdf','.txt','.md','.csv','.gif','.png','.jpg','.jpeg','.webp','.mp4','.webm']:
                raise Problem('Supported: PDF, text, Markdown, CSV, GIF, PNG, JPG, WebP, MP4, WebM.')
            body=self.body(80*1024*1024)
            if not body: raise Problem('Empty upload.')
            filename=secrets.token_hex(16)+ext
            (DATA/'uploads'/filename).write_bytes(body)
            record=save_row('files',{'name':name,'url':'/uploads/'+filename,'bytes':len(body),'uploaded':now().isoformat(),'kind':'document' if ext in ['.pdf','.txt','.md','.csv'] else 'media'})
            audit('upload',{'id':record['id'],'name':name}); return self.send(200,record)
        b=self.json_body()
        if p=='/api/settings':
            s=settings()
            for k in ['title','timezone','workdays','on','off','effects','holidays','payroll_enabled','payroll_start','payday','latitude','longitude','monthly_budget','dark_dates']:
                if k in b: s[k]=b[k]
            ZoneInfo(s['timezone'])
            for field in ['on','off']:
                datetime.strptime(s[field],'%H:%M')
            if s['on']>=s['off']: raise Problem('Work hours must start before they end on the same day.')
            if not isinstance(s['workdays'],list) or any(not isinstance(d,int) or d not in range(7) for d in s['workdays']): raise Problem('Invalid workdays.')
            if s['effects'] not in ['off','seasonal','weather','snow','leaves','rain']: raise Problem('Invalid effect.')
            if s['payroll_start'] not in range(7) or s['payday'] not in range(7): raise Problem('Invalid payroll day.')
            for k,lo,hi in [('latitude',-90,90),('longitude',-180,180)]:
                if s[k] is not None and not lo<=s[k]<=hi: raise Problem('Invalid coordinates.')
            if (s['latitude'] is None)!=(s['longitude'] is None): raise Problem('Enter both weather coordinates.')
            if s['monthly_budget'] is not None and s['monthly_budget']<0: raise Problem('Budget must be nonnegative.')
            for d in s['dark_dates']: parse_date(d)
            set_settings(s); audit('settings',s); return self.send(200,{'ok':True})
        if p=='/api/wake':
            s=settings(); s['wake_until']=time.time()+1800; set_settings(s); return self.send(200,{'ok':True})
        if p=='/api/navigation':
            s=settings()
            value=b.get('month')
            if value: parse_date(value+'-01')
            s['wall_month']=value; s['wall_changed']=time.time(); s['wall_day']=str(now().date()); set_settings(s)
            return self.send(200,{'ok':True})
        if p=='/api/assignments':
            day=parse_date(b['date']); scope=b.get('scope','day'); person=b.get('person')
            if scope not in ['day','week']: raise Problem('Invalid assignment scope.')
            if person is not None and person not in PEOPLE: raise Problem('Invalid employee.')
            key=str(week_start(day) if scope=='week' else day)
            with connect() as c:
                if person is None: c.execute('DELETE FROM assignments WHERE date=? AND scope=?',(key,scope))
                else: c.execute('INSERT OR REPLACE INTO assignments VALUES(?,?,?)',(key,scope,person))
            audit('assignment',dict(date=key,scope=scope,person=person)); return self.send(200,{'ok':True})
        if p=='/api/events':
            title=b.get('title','').strip()
            if not title or len(title)>200: raise Problem('Enter a title of 1–200 characters.')
            start=parse_date(b['date']); end=parse_date(b.get('end_date') or b['date'])
            if end<start or (end-start).days>366: raise Problem('Invalid event date range.')
            if b.get('repeat','none') not in ['none','weekly','monthly','yearly']: raise Problem('Invalid recurrence.')
            if b.get('repeat_until') and parse_date(b['repeat_until'])<start: raise Problem('Recurrence ends before event starts.')
            if b.get('time'): datetime.strptime(b['time'],'%H:%M')
            if b.get('kind') not in ['general','holiday','weekend','payroll','maintenance']: raise Problem('Invalid event type.')
            if b.get('employee') not in PEOPLE+['',None]: raise Problem('Invalid employee.')
            b['title']=title; saved=save_row('events',b,b.get('id')); audit('save event',saved); return self.send(200,saved)
        if p=='/api/requirements':
            saved=save_row('requirements',validate_requirement(b),b.get('id')); audit('save requirement',saved); return self.send(200,saved)
        if p=='/api/requirements/next':
            old=next((r for r in rows('requirements') if r['id']==b['id']),None)
            if not old or old['stage']!='Complete': raise Problem('Close the current requirement before opening its next period.')
            new={**old}; new.pop('id')
            for field in ['window_start','window_end']: new[field]=str(shift_year(parse_date(old[field]),old['years']))
            if any(r['facility']==new['facility'] and r['group']==new['group'] and r['window_start']==new['window_start'] for r in rows('requirements')): raise Problem('Next period already exists.')
            new.update(reviewed=False,planned=None,actual=None,stage='Verify records',source_status='New period inferred from prior recurrence; confirm current state schedule.')
            saved=save_row('requirements',new); audit('open next period',saved); return self.send(200,saved)
        if p=='/api/plan':
            return self.send(200,propose(rows('requirements'),now().date(),settings()['monthly_budget']))
        if p=='/api/plan/apply':
            reqs={r['id']:r for r in rows('requirements')}
            updates=[]
            for item in b.get('proposals',[]):
                old=reqs.get(item['id'])
                if not old or old['stage']=='Complete' or old.get('planned') or item.get('revision',0)!=old.get('revision',0): raise Problem('Plan changed. Generate proposals again.',409)
                r={**old,'planned':item['planned'],'stage':'Planned','revision':old.get('revision',0)+1}; validate_requirement(r); updates.append(r)
            with connect() as c:
                for r in updates: c.execute('UPDATE requirements SET data=? WHERE id=?',(json.dumps({k:v for k,v in r.items() if k!='id'}),r['id']))
            audit('apply plan',updates); return self.send(200,{'count':len(updates)})
        if p=='/api/media':
            file=next((f for f in rows('files') if f['id']==b['file_id'] and f['kind']=='media'),None)
            if not file: raise Problem('Upload and choose a GIF, image, or video first.')
            if parse_date(b['start'])>parse_date(b['end']): raise Problem('Media end precedes start.')
            if b['screen'] not in ['both','left','right']: raise Problem('Invalid screen.')
            if b.get('condition','always') not in ['always','snow','rain','leaves','clear']: raise Problem('Invalid media condition.')
            b['url']=file['url']; b['name']=file['name']
            saved=save_row('media',b,b.get('id')); audit('save media',saved); return self.send(200,saved)
        raise Problem('Not found.',404)

def main():
    initialize()
    host=os.environ.get('HOST','0.0.0.0'); port=int(os.environ.get('PORT','8080'))
    print(f'Waterworks Calendar running on {host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
if __name__=='__main__': main()
