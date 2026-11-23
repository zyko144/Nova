"""Bounded HTTPS crawler; never reads browser cookies, history or credentials."""
import http.client,ipaddress,socket,time
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
from urllib.robotparser import RobotFileParser
from .index import canonical

AGENT='NovaBot/0.1 (+https://github.com/zyko144/Nova)'

def public_addresses(host):
    addresses=list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):raise ValueError('Adresse réseau privée ou réservée refusée')
    return addresses

def fetch(url,redirects=0,allowed_host=None):
    url=canonical(url)
    if not url or redirects>4:raise ValueError('URL HTTPS invalide')
    p=urlsplit(url)
    if allowed_host and p.hostname!=allowed_host:raise ValueError('Redirection hors du site refusée')
    addresses=public_addresses(p.hostname)
    connection=http.client.HTTPSConnection(p.hostname,timeout=12)
    # Pin the validated destination while preserving TLS certificate/SNI checks.
    connection._create_connection=lambda address,timeout,source_address=None:socket.create_connection((addresses[0],443),timeout,source_address)
    try:
        connection.request('GET',p.path+('?' + p.query if p.query else ''),headers={'User-Agent':AGENT,'Accept':'text/html,text/plain;q=0.9','Accept-Encoding':'identity'})
        response=connection.getresponse();headers=dict((k.lower(),v) for k,v in response.getheaders())
        if response.status in (301,302,303,307,308):
            return fetch(urljoin(url,headers.get('location','')),redirects+1,allowed_host)
        body=response.read(1024*1024+1)
        if len(body)>1024*1024:raise ValueError('Page trop volumineuse')
        return response.status,headers,body,url
    finally:connection.close()

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.title=[];self.text=[];self.links=[];self.in_title=False;self.hidden=0;self.noindex=False;self.nofollow=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='title':self.in_title=True
        if tag in ('script','style','noscript','template'):self.hidden+=1
        if tag=='a' and 'nofollow' not in a.get('rel','').lower().split():self.links.append(a.get('href',''))
        if tag=='meta' and a.get('name','').lower() in ('robots','novabot'):
            flags=a.get('content','').lower().replace(',',' ').split();self.noindex|='noindex' in flags or 'none' in flags;self.nofollow|='nofollow' in flags or 'none' in flags
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if tag in ('script','style','noscript','template'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,value):
        if self.in_title:self.title.append(value)
        elif not self.hidden:self.text.append(value)

def crawl(index,seeds,limit=30,report=print):
    queue=deque(canonical(s) for s in seeds);allowed={urlsplit(s).hostname for s in queue if s};seen=set();robots={};last={};indexed=0
    while queue and len(seen)<max(1,min(10000,limit)):
        url=queue.popleft()
        if not url or url in seen:continue
        seen.add(url);p=urlsplit(url);origin='https://'+p.hostname
        try:
            if p.hostname not in robots:
                status,headers,body,_=fetch(origin+'/robots.txt',allowed_host=p.hostname)
                if status>=500 or status in (401,403,429):robots[p.hostname]=None
                else:
                    robot=RobotFileParser();robot.parse(body.decode('utf-8','replace').splitlines() if status==200 else []);robots[p.hostname]=robot
                last[p.hostname]=time.monotonic()
            robot=robots[p.hostname]
            if robot is None or not robot.can_fetch('NovaBot',url):report('Ignorée (robots) : '+url);continue
            delay=max(1.0,float(robot.crawl_delay('NovaBot') or 1));time.sleep(max(0,delay-(time.monotonic()-last.get(p.hostname,0))))
            status,headers,body,final=fetch(url,allowed_host=p.hostname);last[p.hostname]=time.monotonic()
            if status!=200 or 'text/html' not in headers.get('content-type',''):continue
            doc=Document();doc.feed(body.decode('utf-8','replace'));flags=headers.get('x-robots-tag','').lower()
            if doc.noindex or 'noindex' in flags or 'none' in flags:index.remove(final);continue
            if index.put(final,' '.join(doc.title).strip(),' '.join(' '.join(doc.text).split())):indexed+=1;report('Indexée : '+final)
            if not doc.nofollow and 'nofollow' not in flags:
                for link in doc.links[:300]:
                    target=canonical(urljoin(final,link));t=urlsplit(target)
                    if target and t.hostname in allowed and not t.query and target not in seen and len(queue)<2000:queue.append(target)
        except (OSError,ValueError,http.client.HTTPException) as error:report('Ignorée : '+url+' ('+type(error).__name__+')')
    return indexed
