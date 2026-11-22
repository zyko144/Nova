"""Nova Sync: self-hosted account API. Run behind HTTPS (see deployment files)."""
import argparse, base64, hashlib, hmac, json, os, re, secrets, sqlite3, threading, time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager

MAX_BODY=1024*1024
PASSWORD_ROUNDS=600_000
TOKEN_LIFETIME=7*24*3600

class Store:
    def __init__(self,path):
        self.path=str(path); Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots(user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL);
            ''')
        self.rates=defaultdict(deque); self.rate_lock=threading.Lock()
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()
    def permit(self,address):
        now=time.time()
        with self.rate_lock:
            queue=self.rates[address]
            while queue and queue[0]<now-600:queue.popleft()
            if len(queue)>=30:return False
            queue.append(now)
            if len(self.rates)>10000:
                for key in list(self.rates):
                    if not self.rates[key] or self.rates[key][-1]<now-600:self.rates.pop(key,None)
        return True

def derive(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),PASSWORD_ROUNDS).hex()
def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()
def clean_snapshot(value):
    if not isinstance(value,dict):raise ValueError('Snapshot invalide')
    result={}
    for key,maximum in [('bookmarks',2000),('history',300),('shortcuts',100),('tabs',100)]:
        items=value.get(key,[])
        if not isinstance(items,list) or len(items)>maximum:raise ValueError('Liste invalide : '+key)
        safe=[]
        for item in items:
            if not isinstance(item,dict):continue
            url=item.get('url',''); title=item.get('title','')
            if isinstance(url,str) and isinstance(title,str) and len(url)<=8192 and url.startswith(('https://','http://')):
                safe.append({'url':url,'title':title[:250]})
        result[key]=safe
    hidden=value.get('hidden_shortcuts',[])
    if not isinstance(hidden,list) or len(hidden)>2000:raise ValueError('Raccourcis supprimés invalides')
    result['hidden_shortcuts']=[u for u in hidden if isinstance(u,str) and len(u)<=8192 and u.startswith(('https://','http://'))]
    preferences=value.get('preferences',{})
    if not isinstance(preferences,dict):preferences={}
    prefs={'profileName':str(preferences.get('profileName','Personnel'))[:60]}
    for key,values in [('theme',('black','violet')),('search_engine',('Google','DuckDuckGo','Bing'))]:
        if preferences.get(key) in values:prefs[key]=preferences[key]
    accent=preferences.get('accent','')
    if isinstance(accent,str) and re.fullmatch(r'#[a-fA-F0-9]{6}',accent):prefs['accent']=accent
    for key in ('adblock','tab_icons','compact_tabs','webrtc_public'):
        if type(preferences.get(key))==bool:prefs[key]=preferences[key]
    result['preferences']=prefs
    return result

class Handler(BaseHTTPRequestHandler):
    server_version='NovaSync/1.0'; sys_version=''
    def log_message(self,*args):pass  # Never log credentials, tokens, browsing URLs or bodies.
    def reply(self,status,value):
        raw=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(raw)
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<=MAX_BODY:raise ValueError('Corps de requête trop volumineux ou absent')
        if self.headers.get_content_type()!='application/json':raise ValueError('Format JSON requis')
        value=json.loads(self.rfile.read(length))
        if not isinstance(value,dict):raise ValueError('Objet JSON requis')
        return value
    def user(self):
        header=self.headers.get('Authorization','')
        if not header.startswith('Bearer ') or len(header)>256:return None
        with self.server.store.connect() as db:
            row=db.execute('SELECT user_id FROM sessions WHERE token=? AND expires>?',(token_hash(header[7:]),int(time.time()))).fetchone()
        return row[0] if row else None
    def snapshot(self,user_id):
        with self.server.store.connect() as db:
            row=db.execute('SELECT revision,data FROM snapshots WHERE user_id=?',(user_id,)).fetchone()
        return {'revision':row[0],'data':json.loads(row[1])} if row else {'revision':0,'data':clean_snapshot({})}
    def do_GET(self):
        if self.path=='/health':self.reply(200,{'status':'ok','service':'Nova Sync'});return
        if self.path!='/v1/snapshot':self.reply(404,{'error':'Route inconnue'});return
        user_id=self.user()
        if not user_id:self.reply(401,{'error':'Session expirée ou absente'});return
        self.reply(200,self.snapshot(user_id))
    def do_POST(self):
        try:self.post()
        except (ValueError,UnicodeError,TypeError):self.reply(400,{'error':'Requête invalide'})
        except sqlite3.Error:self.reply(503,{'error':'Stockage temporairement indisponible'})
    def post(self):
        if self.path in ('/v1/register','/v1/login'):
            if not self.server.store.permit(self.client_address[0]):self.reply(429,{'error':'Trop de tentatives. Réessayez dans 10 minutes.'});return
            data=self.body();email=data.get('email','');password=data.get('password','')
            if not isinstance(email,str) or not isinstance(password,str):raise ValueError()
            email=email.strip().lower()
            if not re.fullmatch(r'[^\s@]{1,100}@[^\s@]{1,150}\.[^\s@]{2,60}',email) or not 12<=len(password)<=256:
                self.reply(400,{'error':'Adresse e-mail valide et mot de passe de 12 à 256 caractères requis'});return
            with self.server.store.connect() as db:
                if self.path=='/v1/register':
                    ident=secrets.token_hex(16);salt=secrets.token_hex(16)
                    try:db.execute('INSERT INTO users VALUES(?,?,?,?)',(ident,email,salt,derive(password,salt)))
                    except sqlite3.IntegrityError:self.reply(409,{'error':'Création impossible avec cette adresse'});return
                else:
                    row=db.execute('SELECT id,salt,password FROM users WHERE email=?',(email,)).fetchone()
                    valid=hmac.compare_digest(derive(password,row[1] if row else '0'*32),row[2] if row else '0'*64)
                    if not row or not valid:self.reply(401,{'error':'Identifiants incorrects'});return
                    ident=row[0]
                token=secrets.token_urlsafe(48)
                db.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
                db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),ident,int(time.time())+TOKEN_LIFETIME))
            self.reply(200,{'token':token,'email':email});return
        user_id=self.user()
        if not user_id:self.reply(401,{'error':'Session expirée ou absente'});return
        if self.path=='/v1/logout':
            with self.server.store.connect() as db:db.execute('DELETE FROM sessions WHERE token=?',(token_hash(self.headers['Authorization'][7:]),))
            self.reply(200,{'ok':True});return
        if self.path=='/v1/snapshot':
            body=self.body(); data=clean_snapshot(body.get('data'));revision=body.get('revision')
            if type(revision)!=int or revision<0:raise ValueError()
            with self.server.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT revision FROM snapshots WHERE user_id=?',(user_id,)).fetchone()
                current=row[0] if row else 0
                if current!=revision:
                    self.reply(409,{'error':'Les données ont changé sur un autre appareil. Synchronisez à nouveau.'});return
                new=current+1
                db.execute('INSERT INTO snapshots VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(user_id,new,json.dumps(data)))
            self.reply(200,{'revision':new});return
        self.reply(404,{'error':'Route inconnue'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8766);parser.add_argument('--db',default=os.environ.get('NOVA_DB','data/nova-sync.sqlite3'))
    args=parser.parse_args();server=ThreadingHTTPServer((args.host,args.port),Handler);server.store=Store(args.db)
    server.timeout=30
    print(f'Nova Sync écoute sur {args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
