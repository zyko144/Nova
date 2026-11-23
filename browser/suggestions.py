from urllib.parse import quote_plus,urlsplit
from PySide6.QtCore import QStringListModel,Qt
from PySide6.QtWidgets import QCompleter

def suggestions(query,data):
    query=query.strip()
    if len(query)<2 or len(query)>300:return []
    match=query.casefold();items=[];seen=set()
    engine=data.get('preferences',{}).get('search_engine','Google');search_prefix={'Google':'https://www.google.com/search?q=','DuckDuckGo':'https://duckduckgo.com/?q=','Bing':'https://www.bing.com/search?q='}.get(engine,'https://www.google.com/search?q=')
    for entry in data.get('bookmarks',[])+data.get('history',[])[:300]:
        url=entry.get('url','');title=entry.get('title','')
        if url.startswith(('https://','http://')) and url not in seen and (match in url.casefold() or match in title.casefold()):
            seen.add(url);items.append((title[:55]+' · '+urlsplit(url).netloc,url))
            if len(items)==4:break
    for previous in data.get('recent_searches',[])[:30]:
        if match in previous.casefold() and previous!=query:items.append(('Reprendre : '+previous,search_prefix+quote_plus(previous)))
        if len(items)>=6:break
    items.extend([('Rechercher : '+query,search_prefix+quote_plus(query)),('YouTube : '+query,'https://www.youtube.com/results?search_query='+quote_plus(query))])
    return items[:8]

class AddressSuggestions:
    def __init__(self,browser):
        self.browser=browser;self.destinations={};self.model=QStringListModel();self.completer=QCompleter(self.model,browser)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.popup().setCursor(Qt.CursorShape.ArrowCursor)
        self.completer.popup().setStyleSheet('QListView{background:#100b18;color:#d9cce7;border:1px solid #382248;border-radius:10px;padding:6px;font:13px "Segoe UI"}QListView::item{padding:9px 13px;border-radius:7px}QListView::item:selected{background:#29163e}')
        browser.address.setCompleter(self.completer);browser.address.textEdited.connect(self.update);self.completer.activated[str].connect(self.choose)
    def update(self,value):
        items=suggestions(value,self.browser.data);self.destinations=dict(items);self.model.setStringList([label for label,url in items])
        self.completer.setCompletionPrefix('')
        if items:self.completer.complete()
        else:self.completer.popup().hide()
    def choose(self,label):
        from PySide6.QtCore import QUrl
        if label in self.destinations:self.browser.navigate(QUrl(self.destinations[label]))
