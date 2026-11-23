"""Shared Nova completions with a server-held provider credential. Only the search text is sent, never browsing or vault data."""
import json,re,time
from datetime import datetime,timezone
from collections import OrderedDict
from PySide6.QtCore import QObject,QTimer,QUrl,QByteArray
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest

NOVA_AI_ENDPOINT='https://nova-browser-ai-zyko144-zeev2.vercel.app/api/suggest'

def permitted(query):
    query=query.strip()
    return 2<=len(query)<=160 and not re.search(r'https?://|@|sk-|gsk_|GOCSPX|^[^\s]+\.[a-zA-Z]{2,}(?:/|$)',query,re.I) and not any(ord(c)<32 for c in query)

def clean_values(content,query):
    data=json.loads(content);values=data.get('suggestions',[]) if isinstance(data,dict) else [];result=[]
    if not isinstance(values,list):return []
    for value in values:
        if isinstance(value,str):
            value=' '.join(value.split())[:120]
            if permitted(value) and value.casefold()!=query.strip().casefold() and value.casefold() not in [v.casefold() for v in result]:result.append(value)
        if len(result)==3:break
    return result

class AISuggestions(QObject):
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.network=QNetworkAccessManager(self);self.cache=OrderedDict();self.pending={};self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(700);self.timer.timeout.connect(self.send);self.reply=None;self.last_sent=0.;self.backoff=0.
    def request(self,source,query,callback):
        self.pending.pop(source,None)
        self.pending[source]=(query,callback)
        if not self.browser.data['preferences'].get('ai_suggestions',True) or not NOVA_AI_ENDPOINT or not permitted(query):return
        cache=self.cache.get(query.casefold().strip())
        if cache and time.monotonic()-cache[0]<900:self.timer.stop();callback(query,cache[1]);return
        self.timer.start(700)
    def send(self):
        if self.reply or not self.pending or time.monotonic()<self.backoff:return
        if not self.browser.data['preferences'].get('ai_suggestions',True) or not NOVA_AI_ENDPOINT:return
        if time.monotonic()-self.last_sent<2.5:self.timer.start(2500);return
        query,callback=list(self.pending.values())[-1]
        if not permitted(query):return
        day=datetime.now(timezone.utc).date().isoformat();budget=self.browser.data.get('ai_budget',{})
        used=budget.get('count',0) if budget.get('day')==day else 0
        if used>=900:return
        self.browser.data['ai_budget']={'day':day,'count':used+1};self.browser.schedule_save();self.last_sent=time.monotonic()
        request=QNetworkRequest(QUrl(NOVA_AI_ENDPOINT));request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json');request.setTransferTimeout(5000);request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        payload={'query':query}
        reply=self.network.post(request,QByteArray(json.dumps(payload).encode()));self.reply=reply
        def done():
            self.reply=None
            try:
                status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if status==429:self.backoff=time.monotonic()+60;return
                if status!=200:self.backoff=time.monotonic()+15;return
                raw=bytes(reply.readAll())
                if len(raw)>65536:return
                data=json.loads(raw);values=clean_values(json.dumps(data),query)
                if not self.browser.data['preferences'].get('ai_suggestions',True):return
                self.cache[query.casefold().strip()]=(time.monotonic(),values)
                while len(self.cache)>80:self.cache.popitem(last=False)
                for current,deliver in list(self.pending.values()):
                    if current==query:deliver(query,values)
            except (ValueError,KeyError,IndexError,TypeError,RuntimeError):pass
            finally:
                reply.deleteLater()
                if self.pending and list(self.pending.values())[-1][0]!=query:self.timer.start(700)
        reply.finished.connect(done)
