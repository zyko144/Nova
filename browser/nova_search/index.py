import re,sqlite3,time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from .catalog import CATALOG

def canonical(url):
    try:
        p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):return ''
        return urlunsplit(('https',p.hostname.lower(),p.path or '/',p.query,''))
    except ValueError:return ''

def terms(query):return re.findall(r'[^\W_]+',query[:300],re.UNICODE)[:16]

class Index:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(url UNINDEXED,title,body,kind UNINDEXED,source UNINDEXED,updated UNINDEXED,tokenize="unicode61 remove_diacritics 2");
              CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);''')
            if not db.execute("SELECT 1 FROM meta WHERE key='catalog-v1'").fetchone():
                for url,title,body,kind in CATALOG:self.put(url,title,body,kind,'catalogue',db=db)
                db.execute("INSERT INTO meta VALUES('catalog-v1','1')")
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def put(self,url,title,body,kind='web',source='exploration',db=None):
        url=canonical(url)
        if not url or not title.strip():return False
        if db is None:
            with self.connect() as connection:return self.put(url,title,body,kind,source,connection)
        db.execute('DELETE FROM pages WHERE url=?',(url,))
        db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?)',(url,title.strip()[:240],body[:100000],kind,source,int(time.time())))
        return True
    def remove(self,url):
        with self.connect() as db:db.execute('DELETE FROM pages WHERE url=?',(canonical(url),))
    def stats(self):
        with self.connect() as db:
            rows=db.execute('SELECT source,count(*) AS n FROM pages GROUP BY source').fetchall()
        return {'pages':sum(r['n'] for r in rows),'crawled':sum(r['n'] for r in rows if r['source']=='exploration')}
    def search(self,query,kind='all',page=1,order='relevance'):
        words=terms(query);page=max(1,min(100,int(page)));start=time.perf_counter()
        if not words:return {'results':[],'total':0,'page':page,'milliseconds':0}
        expression=' AND '.join('"'+w+'"' for w in words)
        where='pages MATCH ?';args=[expression]
        if kind in ('guides','communauté'):where+=' AND kind=?';args.append(kind)
        # Query text is tokenized and bound; user input cannot become SQL or FTS syntax.
        with self.connect() as db:
            total=db.execute('SELECT count(*) FROM pages WHERE '+where,args).fetchone()[0]
            sort='CAST(updated AS INTEGER) DESC' if order=='recent' else 'bm25(pages,0,6,1,0,0,0)'
            rows=db.execute("SELECT url,title,snippet(pages,2,'','',' … ',38) AS description,kind,source,updated FROM pages WHERE "+where+' ORDER BY '+sort+' LIMIT 10 OFFSET ?',args+[(page-1)*10]).fetchall()
        return {'results':[dict(r) for r in rows],'total':total,'page':page,'milliseconds':round((time.perf_counter()-start)*1000,1)}
    def suggest(self,query):
        words=terms(query)
        if not words:return []
        expression=' AND '.join('"'+w+'"'+('*' if i==len(words)-1 else '') for i,w in enumerate(words))
        with self.connect() as db:rows=db.execute('SELECT title FROM pages WHERE pages MATCH ? ORDER BY bm25(pages,0,6,1,0,0,0) LIMIT 6',(expression,)).fetchall()
        return [r['title'] for r in rows]
