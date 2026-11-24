from surfaces import round_popup
from urllib.parse import quote_plus,urlsplit
from PySide6.QtCore import QStringListModel,Qt,QSize,QRect,QRectF,QTimer,QModelIndex
from PySide6.QtGui import QColor,QFont,QPainter
from PySide6.QtWidgets import QCompleter,QStyledItemDelegate,QStyle
from ui import generated_icon

def suggestions(query,data):
    query=query.strip()
    if len(query)<2 or len(query)>300:return []
    match=query.casefold();items=[];seen=set()
    engine=data.get('preferences',{}).get('search_engine','Google');search_prefix={'Nova Search':data.get('nova_search_base','https://nova.local/')+'search?q=','Google':'https://www.google.com/search?q=','DuckDuckGo':'https://duckduckgo.com/?q=','Bing':'https://www.bing.com/search?q='}.get(engine,'https://www.google.com/search?q=')
    for entry in data.get('bookmarks',[])+data.get('history',[])[:300]:
        url=entry.get('url','');title=entry.get('title','')
        if url.startswith(('https://','http://')) and url not in seen and (match in url.casefold() or match in title.casefold()):
            seen.add(url);items.append((title[:55]+' · '+urlsplit(url).netloc,url))
            if len(items)==4:break
    for previous in data.get('recent_searches',[])[:30]:
        if match in previous.casefold() and previous!=query:items.append(('Reprendre : '+previous,search_prefix+quote_plus(previous)))
        if len(items)>=4:break
    items.extend([('Rechercher : '+query,search_prefix+quote_plus(query)),('YouTube : '+query,'https://www.youtube.com/results?search_query='+quote_plus(query))])
    return items[:-2][:4]+items[-2:]

class SuggestionDelegate(QStyledItemDelegate):
    def __init__(self,helper):super().__init__(helper.browser);self.helper=helper
    def sizeHint(self,option,index):return QSize(520,54)
    def paint(self,painter,option,index):
        label=index.data() or '';url=self.helper.items[index.row()][1] if index.row()<len(self.helper.items) else '';rect=option.rect
        title,detail,symbol=label,urlsplit(url).netloc,'home'
        if label.startswith('Rechercher : '):title=label[13:];detail='Rechercher avec '+self.helper.browser.data['preferences'].get('search_engine','Google');symbol='search'
        elif label.startswith('YouTube : '):title=label[10:];detail='Rechercher sur YouTube';symbol='video'
        elif label.startswith('Reprendre : '):title=label[12:];detail='Recherche récente';symbol='reload'
        elif label.startswith('IA : '):title=label[5:];detail='';symbol='search'
        else:title=label.rsplit(' · ',1)[0];detail=urlsplit(url).netloc+urlsplit(url).path.rstrip('/')
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & (QStyle.StateFlag.State_Selected|QStyle.StateFlag.State_MouseOver):
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#251733'));painter.drawRoundedRect(QRectF(rect).adjusted(3,3,-3,-3),9,9)
        painter.drawPixmap(rect.x()+16,rect.y()+17,generated_icon(symbol,20).pixmap(20,20))
        painter.setFont(QFont('Segoe UI',10));painter.setPen(QColor('#eee6f6'));title=painter.fontMetrics().elidedText(title,Qt.TextElideMode.ElideRight,max(20,rect.width()-85));painter.drawText(QRect(rect.x()+49,rect.y()+7,rect.width()-85,22),Qt.AlignmentFlag.AlignVCenter,title)
        painter.setFont(QFont('Segoe UI',9));painter.setPen(QColor('#9685a7'));detail=painter.fontMetrics().elidedText(detail,Qt.TextElideMode.ElideRight,max(20,rect.width()-85));painter.drawText(QRect(rect.x()+49,rect.y()+29,rect.width()-85,17),Qt.AlignmentFlag.AlignVCenter,detail)
        painter.setPen(QColor('#79678d'));painter.drawText(rect.adjusted(0,0,-14,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,'↗');painter.restore()

class AddressSuggestions:
    def __init__(self,browser):
        self.browser=browser;self.destinations={};self.items=[];self.ignore_return=False;self.model=QStringListModel(browser);self.completer=QCompleter(self.model,browser)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setMaxVisibleItems(6);self.completer.popup().setItemDelegate(SuggestionDelegate(self));self.completer.popup().setUniformItemSizes(True);self.completer.popup().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.completer.popup().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.completer.popup().setCursor(Qt.CursorShape.ArrowCursor)
        round_popup(self.completer.popup(),12)
        self.completer.popup().setStyleSheet('QListView{background:#0e0b14;color:#d9cce7;border:1px solid #382b44;border-radius:12px;padding:5px;outline:0}QScrollBar:vertical{width:5px;background:transparent}QScrollBar::handle:vertical{background:#3c2b4e;border-radius:2px}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}')
        browser.address.setCompleter(self.completer);browser.address.textEdited.connect(self.update);self.completer.activated[QModelIndex].connect(self.choose_index)
    def update(self,value):
        if self.browser.presentation:self.completer.popup().hide();return
        items=suggestions(value,self.browser.data);self.items=items;self.destinations=dict(items);self.model.setStringList([label for label,url in items])
        self.completer.setCompletionPrefix('')
        if items:
            width=max(300,min(660,self.browser.address.width()));popup=self.completer.popup();popup.setMinimumWidth(width);popup.setMaximumWidth(width);popup.setFixedHeight(len(items)*54+12);self.completer.complete(QRect(0,0,width,self.browser.address.height()))
        else:self.completer.popup().hide()
        self.browser.ai.request('address',value,self.ai_results)
    def ai_results(self,query,values):
        if not self.browser.address.hasFocus() or self.browser.address.text()!=query or not self.completer.popup().isVisible():return
        base=suggestions(query,self.browser.data)
        if len(base)<2:return
        prefix=base[-2][1].rsplit('=',1)[0]+'='
        proposals=[('IA : '+value,prefix+quote_plus(value)) for value in values]
        self.items=(base[:-2][:1]+proposals[:3]+base[-2:])[:6];self.destinations=dict(self.items);self.model.setStringList([label for label,url in self.items]);self.completer.popup().setFixedHeight(len(self.items)*54+12)
    def choose_index(self,index):
        if index.isValid() and index.row()<len(self.items):self.choose(*self.items[index.row()])
    def choose(self,label,url=None):
        from PySide6.QtCore import QUrl
        target=url or self.destinations.get(label)
        if target:
            self.ignore_return=True;self.browser.address.setText(target);self.browser.navigate(QUrl(target));QTimer.singleShot(0,self.clear_return)
    def clear_return(self):self.ignore_return=False
