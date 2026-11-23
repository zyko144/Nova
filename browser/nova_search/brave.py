"""Server-only Brave adapter. No subscription key or results are persisted."""
import json,os,time
from datetime import datetime,timezone
from urllib.parse import urlencode,urlsplit,urlunsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from html.parser import HTMLParser

class SearchUnavailable(Exception):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):raise HTTPError(req.full_url,code,'Redirect refused',headers,fp)

class Text(HTMLParser):
    def __init__(self,value):super().__init__(convert_charrefs=True);self.parts=[];self.feed(value)
    def handle_data(self,value):self.parts.append(value)

def plain(value):return ''.join(Text(str(value)).parts)[:800]
def result_url(value):
    try:
        p=urlsplit(value)
        return urlunsplit(p) if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''
    except ValueError:return ''

class BraveSearch:
    def __init__(self,local,key=None,daily_limit=None):
        self.local=local;self.key=key if key is not None else os.environ.get('BRAVE_API_KEY','').strip()
        self.limit=max(0,int(daily_limit if daily_limit is not None else os.environ.get('BRAVE_DAILY_LIMIT','200')))
        with local.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS api_budget(day TEXT PRIMARY KEY,requests INTEGER NOT NULL)')
    def stats(self):return {**self.local.stats(),'provider':'Brave','configured':bool(self.key),'daily_limit':self.limit}
    def suggest(self,query):return []  # Typing does not consume paid API calls.
    def reserve(self):
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        with self.local.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT requests FROM api_budget WHERE day=?',(day,)).fetchone()
            if (row[0] if row else 0)>=self.limit:raise SearchUnavailable('Le plafond quotidien de recherches Nova est atteint. Réessayez demain.')
            db.execute('INSERT INTO api_budget VALUES(?,1) ON CONFLICT(day) DO UPDATE SET requests=requests+1',(day,))
            db.execute('DELETE FROM api_budget WHERE day<?',(day,))
    def search(self,query,kind='all',page=1,order='relevance'):
        page=max(1,min(10,int(page)));start=time.perf_counter()
        empty={'results':[],'total':None,'page':page,'milliseconds':0,'provider':'Brave','has_more':False}
        if not query.strip():return empty
        if not self.key:raise SearchUnavailable('La recherche Web Nova attend sa configuration serveur. Ajoutez la clé Brave sur le serveur pour activer la couverture Web.')
        self.reserve()
        params={'q':query[:300],'count':10,'offset':page-1,'country':'FR','search_lang':'fr','ui_lang':'fr-FR','safesearch':'moderate','text_decorations':'false','result_filter':'web,query'}
        request=Request('https://api.search.brave.com/res/v1/web/search?'+urlencode(params),headers={'X-Subscription-Token':self.key,'Accept':'application/json','Accept-Encoding':'identity'})
        try:
            with build_opener(NoRedirect()).open(request,timeout=12) as response:raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError()
            data=json.loads(raw)
        except HTTPError as error:
            if error.code==429:raise SearchUnavailable('Quota Brave temporairement atteint. Réessayez plus tard.') from None
            if error.code in (401,403):raise SearchUnavailable('La clé de recherche du serveur doit être vérifiée par son administrateur.') from None
            raise SearchUnavailable('La recherche Web est temporairement indisponible.') from None
        except (OSError,URLError,ValueError):raise SearchUnavailable('La recherche Web ne répond pas. Réessayez dans un instant.') from None
        if not isinstance(data,dict):raise SearchUnavailable('Réponse du moteur de recherche invalide.')
        web=data.get('web') or {};query_info=data.get('query') or {}
        if not isinstance(web,dict) or not isinstance(query_info,dict):raise SearchUnavailable('Réponse du moteur de recherche invalide.')
        items=web.get('results') or []
        if not isinstance(items,list):raise SearchUnavailable('Réponse du moteur de recherche invalide.')
        results=[];seen=set()
        for item in items[:10]:
            if not isinstance(item,dict):continue
            url=result_url(item.get('url',''))
            if not url or url in seen:continue
            seen.add(url);results.append({'url':url,'title':plain(item.get('title',''))[:240],'description':plain(item.get('description','')),'kind':'web','source':'brave','updated':0})
        return {**empty,'results':results,'has_more':bool(query_info.get('more_results_available')) and page<10,'milliseconds':round((time.perf_counter()-start)*1000,1)}
