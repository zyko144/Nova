"""Explicit, read-only imports from selected local profiles or export files."""
import csv,json,os,sqlite3,time
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit

def safe_url(value):
    try:
        p=urlsplit(value)
        return value if p.scheme in ('http','https') and p.hostname and not p.username and not p.password else ''
    except ValueError:return ''

def profiles():
    local=Path(os.environ.get('LOCALAPPDATA',''));roaming=Path(os.environ.get('APPDATA',''));items=[]
    for name,root in [('Chrome',local/'Google/Chrome/User Data'),('Edge',local/'Microsoft/Edge/User Data'),('Brave',local/'BraveSoftware/Brave-Browser/User Data')]:
        if root.is_dir():
            for p in root.iterdir():
                if p.is_dir() and (p.name=='Default' or p.name.startswith('Profile ')) and ((p/'Bookmarks').exists() or (p/'History').exists()):items.append((name+' · '+p.name,p))
    root=roaming/'Opera Software/Opera Stable'
    if root.is_dir():items.append(('Opera',root))
    return sorted(items,key=lambda item:(not item[0].startswith('Chrome'),item[1].name!='Default',item[0]))

def password_exports(directory,now=None):
    """Inspect filenames and metadata only; never read passwords during discovery."""
    directory=Path(directory);now=time.time() if now is None else now;found=[]
    if not directory.is_dir():return []
    for path in directory.glob('*.csv'):
        name=path.stem.casefold()
        if not any(word in name for word in ('password','mots de passe','mots_de_passe','mots-de-passe')):continue
        try:
            stat=path.stat()
            if path.is_symlink() or not path.is_file() or not 0<stat.st_size<=30*1024*1024 or not 0<=now-stat.st_mtime<=7*86400:continue
            found.append((stat.st_mtime,path))
        except OSError:continue
    return [path for _,path in sorted(found,reverse=True)]

def bookmark_tree(data):
    result=[];stack=[data]
    while stack and len(result)<2000:
        node=stack.pop()
        if isinstance(node,dict):
            url=safe_url(str(node.get('url','')))
            if url:result.append({'url':url,'title':str(node.get('name',node.get('title','')))[:250]})
            stack.extend(v for v in node.values() if isinstance(v,(list,dict)))
        elif isinstance(node,list):stack.extend(reversed(node))
    return result

class BookmarksHTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.current={'url':safe_url(dict(attrs).get('href','')),'title':''}
    def handle_data(self,data):
        if self.current is not None:self.current['title']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:
            if self.current['url'] and len(self.rows)<2000:self.rows.append(self.current)
            self.current=None

def read_export(path):
    path=Path(path)
    if path.stat().st_size>30*1024*1024:raise ValueError('Fichier trop volumineux (30 Mio maximum).')
    text=path.read_text(encoding='utf-8-sig');result={'bookmarks':[],'history':[],'credentials':[]}
    if path.suffix.lower()=='.csv':
        reader=csv.DictReader(text.splitlines())
        if not {'url','username','password'}.issubset(reader.fieldnames or []):raise ValueError('CSV attendu : url, username, password.')
        for row in reader:
            if len(result['credentials'])>=500:break
            if row['url'].startswith('https://') and safe_url(row['url']) and row['password']:result['credentials'].append({k:row[k][:4096] for k in ('url','username','password')})
    elif path.suffix.lower() in ('.html','.htm'):
        parser=BookmarksHTML();parser.feed(text);result['bookmarks']=parser.rows
    else:
        data=json.loads(text)
        if isinstance(data,dict) and 'Browser History' in data:
            result['history']=[{'url':r['url'],'title':str(r.get('title',''))[:250]} for r in data['Browser History'][:300] if isinstance(r,dict) and safe_url(r.get('url',''))]
        else:result['bookmarks']=bookmark_tree(data)
    return result

def read_profile(path,bookmarks=True,history=True):
    path=Path(path);result={'bookmarks':[],'history':[],'credentials':[]}
    if bookmarks and (path/'Bookmarks').is_file():result['bookmarks']=bookmark_tree(json.loads((path/'Bookmarks').read_text(encoding='utf-8')))
    if history and (path/'History').is_file():
        source=sqlite3.connect((path/'History').resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
        try:
            source.execute('PRAGMA query_only=ON')
            rows=source.execute('SELECT url,title FROM urls ORDER BY last_visit_time DESC LIMIT 300').fetchall()
            result['history']=[{'url':u,'title':str(t or '')[:250]} for u,t in rows if safe_url(u)]
        finally:source.close()
    return result

def apply_import(browser,result):
    counts={}
    for key,limit in [('bookmarks',2000),('history',300)]:
        existing=browser.data.setdefault(key,[]);seen={r['url'] for r in existing};new=[r for r in result.get(key,[]) if r['url'] not in seen and not seen.add(r['url'])];browser.data[key]=(existing+new)[:limit];counts[key]=min(len(new),max(0,limit-len(existing)))
    credentials=result.get('credentials',[]);counts['credentials']=0
    if credentials and browser.vault is None:raise ValueError('Le coffre Windows est indisponible.')
    for row in credentials:
        if browser.vault.for_site(row['url']) and any(r['username']==row['username'] for r in browser.vault.for_site(row['url'])):continue
        browser.vault.put(row['url'],row['username'],row['password']);counts['credentials']+=1
    browser.save();return counts
