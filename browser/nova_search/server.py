import json,secrets,threading,time
from collections import deque
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs,quote_plus
from .index import Index
from .web import page,STYLE,SCRIPT
from .brave import SearchUnavailable,SearchQuotaReached

class SearchServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,index,prefix):
        self.index=index;self.prefix=prefix;super().__init__(address,Handler)
        self.rate_lock=threading.Lock();self.requests={}
    def permit(self,address):
        now=time.monotonic()
        with self.rate_lock:
            if len(self.requests)>2000:self.requests={k:v for k,v in self.requests.items() if v and v[-1]>now-60}
            entries=self.requests.setdefault(address,deque())
            while entries and entries[0]<now-60:entries.popleft()
            if len(entries)>=30:return False
            entries.append(now);return True

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def setup(self):super().setup();self.connection.settimeout(10)
    def reply(self,status,body,content='text/html; charset=utf-8'):
        raw=body.encode() if isinstance(body,str) else body
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store');self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        if len(self.path)>4096:self.reply(414,'Requête trop longue');return
        parsed=urlsplit(self.path);prefix=self.server.prefix
        host=self.headers.get('Host','').split(':')[0]
        if self.server.server_address[0]=='127.0.0.1' and host not in ('127.0.0.1','localhost'):self.reply(403,'Hôte refusé');return
        if not parsed.path.startswith(prefix):self.reply(404,'Page introuvable');return
        route=parsed.path[len(prefix):];args=parse_qs(parsed.query);q=args.get('q',[''])[0][:300]
        if route=='style.css':self.reply(200,STYLE,'text/css; charset=utf-8');return
        if route=='app.js':self.reply(200,SCRIPT,'text/javascript; charset=utf-8');return
        if route=='suggest':self.reply(200,json.dumps(self.server.index.suggest(q),ensure_ascii=False),'application/json');return
        if route not in ('','search','about','api/search','health'):self.reply(404,'Page introuvable');return
        if route=='health':self.reply(200,json.dumps(self.server.index.stats()),'application/json');return
        if route not in ('search','api/search'):q=''
        kind=args.get('kind',['all'])[0];order=args.get('order',['relevance'])[0]
        try:number=int(args.get('page',['1'])[0])
        except ValueError:number=1
        if q and route in ('search','api/search') and not self.server.permit(self.client_address[0]):
            self.reply(429,'Trop de recherches. Réessayez dans une minute.');return
        try:found=self.server.index.search(q,kind,number,order)
        except SearchQuotaReached as error:
            fallback='https://www.google.com/search?q='+quote_plus(q)
            if route=='api/search':self.reply(429,json.dumps({'error':str(error),'fallback_url':fallback},ensure_ascii=False),'application/json');return
            self.send_response(302);self.send_header('Location',fallback);self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length','0');self.end_headers();return
        except SearchUnavailable as error:
            found={'results':[],'total':0,'page':1,'milliseconds':0,'provider':'Brave','has_more':False,'error':str(error)}
            if route=='api/search':self.reply(503,json.dumps(found,ensure_ascii=False),'application/json');return
        if route=='api/search':self.reply(200,json.dumps(found,ensure_ascii=False),'application/json');return
        self.reply(503 if found.get('error') else 200,page(q,found,self.server.index.stats(),kind,order,route=='about'))

class LocalSearch:
    def __init__(self,path):
        self.index=Index(path);self.server=SearchServer(('127.0.0.1',0),self.index,'/s/'+secrets.token_urlsafe(24)+'/')
        self.base='http://127.0.0.1:'+str(self.server.server_port)+self.server.prefix
        threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.1},daemon=True).start()
    def url(self,query=''):return self.base+('search?q='+quote_plus(query) if query else '')
    def close(self):
        def shutdown():self.server.shutdown();self.server.server_close()
        threading.Thread(target=shutdown,daemon=True).start()
