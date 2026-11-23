import sys, json, uuid, os
from pathlib import Path
from urllib.parse import quote_plus,urlsplit,parse_qs
from PySide6.QtCore import QUrl, QStandardPaths, Qt, QTimer, QSize, QByteArray, QPoint,QLockFile,Signal
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPixmap, QPainter,QColor,QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QToolBar,
    QLineEdit, QMessageBox, QFileDialog, QInputDialog, QMenu, QWidget,
    QHBoxLayout, QVBoxLayout, QToolButton, QTabBar, QLabel, QSizeGrip)
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from design import HOME, LOGO, svg_icon, render_home, SHORTCUTS
from media_view import MediaView, media_url, helper_path
from ui import generated_icon,NovaTabBar,NovaInput,NovaMessage,ShortcutDialog
from pages import InternalPage,SettingsPage,AccountPage,SyncClient
from home_assets import canonical_url
from updater import Updater
from vault import Vault,secure_origin
from form_bridge import install_bridge
from ui import NovaDialog
from suggestions import AddressSuggestions
from PySide6.QtWidgets import QPushButton,QScrollArea
import hashlib,time
from nova_search import LocalSearch
QMessageBox=NovaMessage
QInputDialog=NovaInput

def icon(name,size=26):
    if name!='logo':
        generated=generated_icon(name,size)
        if not generated.isNull():return generated
    renderer=QSvgRenderer(QByteArray((LOGO if name=='logo' else svg_icon(name)).encode()))
    pixmap=QPixmap(size,size); pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap); renderer.render(painter); painter.end()
    return QIcon(pixmap)

class TitleBar(QWidget):
    def __init__(self,window):
        super().__init__(window); self.window=window; self.drag=None
        self.setFixedHeight(54); self.setObjectName('titleBar')
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.window.windowHandle().startSystemMove()
    def mouseDoubleClickEvent(self,event): self.window.toggle_maximized()

def destination(text):
    text = text.strip()
    url = QUrl(text)
    if url.scheme().lower() in ('http', 'https') and url.host():
        return url
    if not url.scheme() and ' ' not in text and ('.' in text or text.startswith('localhost')):
        url = QUrl('https://' + text)
        if url.host(): return url
    return QUrl('https://www.google.com/search?q=' + quote_plus(text))

class Page(QWebEnginePage):
    def __init__(self, profile, window):
        super().__init__(profile, window)
        self.window = window
        self.home_pending = False
        self.media_bypass = False
    def acceptNavigationRequest(self, url, kind, main):
        if main and self.home_pending and url.scheme() == 'data':
            self.home_pending = False
            return True
        if main and url.host()=='nova.local':
            callback={'/add':self.window.add_shortcut,'/settings':self.window.open_settings,'/vpn':lambda:self.window.open_settings(3),'/account':self.window.open_account}.get(url.path(),self.window.open_settings)
            QTimer.singleShot(0,callback)
            return False
        if main and not self.media_bypass and media_url(url) and helper_path().exists():
            QTimer.singleShot(0,lambda:self.window.open_media(url,self))
            return False
        return url.scheme().lower() in ('https', 'http', 'about')
    def createWindow(self, kind):
        return self.window.new_tab().page()

class NovaWebView(QWebEngineView):
    def __init__(self,window):super().__init__();self.window=window
    def contextMenuEvent(self,event):
        request=self.lastContextMenuRequest();menu=QMenu(self.window)
        menu.setStyleSheet('QMenu{background:#100b19;color:#e3d7ef;border:1px solid #332242;border-radius:13px;padding:7px}QMenu::item{padding:9px 24px;border-radius:7px;margin:2px}QMenu::item:selected{background:#28173d}QMenu::separator{height:1px;background:#2b1e39;margin:5px}')
        link=request.linkUrl()
        if link.isValid() and link.scheme() in ('http','https'):
            menu.addAction(icon('plus'),'Ouvrir dans un nouvel onglet').triggered.connect(lambda:self.window.new_tab(link))
            menu.addAction('Copier l’adresse du lien').triggered.connect(lambda:QApplication.clipboard().setText(link.toString()))
            if self.url().scheme()=='about' and link.host()!='nova.local':
                title=next((x['title'] for x in self.window.data['shortcuts'] if x['url']==link.toString()),None)
                if title is None:title=next((n for n,u,s in SHORTCUTS if QUrl(u)==link),link.host())
                menu.addSeparator();menu.addAction('Modifier le raccourci…').triggered.connect(lambda:self.window.edit_shortcut(link.toString(),title));menu.addAction('Supprimer le raccourci').triggered.connect(lambda:self.window.remove_shortcut(link.toString()))
            menu.addSeparator()
        if request.selectedText():menu.addAction('Copier la sélection').triggered.connect(lambda:self.page().triggerAction(QWebEnginePage.WebAction.Copy))
        if request.isContentEditable():menu.addAction('Coller').triggered.connect(lambda:self.page().triggerAction(QWebEnginePage.WebAction.Paste))
        menu.addAction(icon('back'),'Retour').triggered.connect(self.back)
        menu.addAction(icon('forward'),'Suivant').triggered.connect(self.forward)
        menu.addAction(icon('reload'),'Actualiser').triggered.connect(self.reload)
        menu.addSeparator();menu.addAction(icon('settings'),'Paramètres Nova').triggered.connect(self.window.open_settings)
        menu.exec(event.globalPos())

class Browser(QMainWindow):
    searchStatus=Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Nova Browser')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(1672, 941); self.setMinimumSize(900,600)
        self.setWindowIcon(icon('logo',64))
        self.root = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        self.root.mkdir(parents=True, exist_ok=True)
        self.datafile = self.root / 'settings.json'
        try: self.data = json.loads(self.datafile.read_text(encoding='utf-8'))
        except (OSError, ValueError): self.data = {}
        self.data.setdefault('profiles', {'default': 'Personnel'})
        self.data.setdefault('active', 'default')
        self.data.setdefault('bookmarks', [])
        self.data.setdefault('history', [])
        self.data.setdefault('shortcuts',[])
        self.data.setdefault('hidden_shortcuts',[])
        self.data.setdefault('preferences',{'theme':'violet','tab_icons':True,'adblock':True,'webrtc_public':True})
        self.search=LocalSearch(self.root/'search'/'index.sqlite3')
        if not self.data.get('nova_search_migrated'):
            self.data['preferences']['search_engine']='Nova Search';self.data['nova_search_migrated']=True
        if not self.data.get('google_search_default_v1'):
            self.data['preferences']['search_engine']='Google';self.data['google_search_default_v1']=True
        endpoint=self.data['preferences'].get('nova_search_endpoint','');target=QUrl(endpoint)
        self.search_base=endpoint.rstrip('/')+'/' if target.scheme()=='https' and target.host() and not target.userName() and not target.password() and not target.hasQuery() and not target.hasFragment() else self.search.base
        self.data['nova_search_base']=self.search_base
        self.sync_client=SyncClient(self)
        try:self.vault=Vault(self.root/'vault.dat')
        except (OSError,ValueError):self.vault=None
        self.last_emails={};self.capture_times={};self.credential_prompt=None
        self.profile = QWebEngineProfile(self.data['active'], self)
        folder = self.root / 'profiles' / self.data['active']
        self.profile.setPersistentStoragePath(str(folder / 'storage'))
        self.profile.setCachePath(str(folder / 'cache'))
        self.profile.setHttpCacheMaximumSize(256 * 1024 * 1024)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        self.profile.downloadRequested.connect(self.download)
        self.tabs = QTabWidget()
        self.tabs.setAutoFillBackground(True)
        palette=self.tabs.palette();palette.setColor(QPalette.ColorRole.Window,QColor('#07060e'));self.tabs.setPalette(palette)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBar().hide()
        self.setCentralWidget(self.tabs)
        chrome=QWidget(); chrome.setObjectName('chrome'); column=QVBoxLayout(chrome); column.setContentsMargins(0,0,0,0); column.setSpacing(0)
        self.titlebar=TitleBar(self); row=QHBoxLayout(self.titlebar); row.setContentsMargins(14,0,0,0); row.setSpacing(0)
        logo=QLabel(); logo.setPixmap(icon('logo',40).pixmap(40,40)); row.addWidget(logo)
        self.top_tabs=NovaTabBar(); self.top_tabs.setDocumentMode(True); self.top_tabs.setTabsClosable(True); self.top_tabs.setMovable(True); self.top_tabs.setExpanding(False)
        self.top_tabs.currentChanged.connect(self.activate_tab)
        self.top_tabs.tabCloseRequested.connect(self.close_tab)
        self.top_tabs.tabMoved.connect(self.move_tab)
        row.addWidget(self.top_tabs)
        def button(name,callback,tip,width=42):
            btn=QToolButton(); btn.setAutoRaise(True); btn.setCursor(Qt.CursorShape.ArrowCursor);btn.setIcon(icon(name)); btn.setIconSize(QSize(20,20)); btn.setFixedSize(width,54); btn.setToolTip(tip); btn.clicked.connect(callback); return btn
        row.addWidget(button('plus',lambda:self.new_tab(),'Nouvel onglet (Ctrl+T)'))
        row.addStretch()
        row.addWidget(button('min',self.showMinimized,'Réduire',48))
        row.addWidget(button('max',self.toggle_maximized,'Agrandir',48))
        close=button('close',self.close,'Fermer',52); close.setObjectName('closeWindow'); row.addWidget(close)
        column.addWidget(self.titlebar)
        self.bar=bar=QToolBar('Navigation'); bar.setMovable(False); bar.setIconSize(QSize(26,26)); bar.setFixedHeight(58)
        column.addWidget(bar); self.setMenuWidget(chrome); self.chrome=chrome
        for name, callback, shortcut,tip in [('back', self.go_back, 'Alt+Left','Précédent'), ('forward', self.go_forward, 'Alt+Right','Suivant'), ('reload', lambda:self.current().reload(), 'Ctrl+R','Actualiser'), ('home', self.home, 'Alt+Home','Accueil')]:
            action = bar.addAction(icon(name),tip); action.triggered.connect(lambda checked=False, cb=callback:cb()); action.setShortcut(shortcut)
        self.address = QLineEdit(); self.address.setPlaceholderText('Rechercher ou entrer une adresse…')
        self.address.setFixedHeight(38)
        self.address.addAction(icon('search'),QLineEdit.ActionPosition.LeadingPosition)
        self.address.returnPressed.connect(lambda:self.navigate(self.resolve(self.address.text())))
        bar.addWidget(self.address)
        for name,callback,tip in [('star',self.bookmark,'Ajouter aux favoris'),('download',self.downloads_menu,'Téléchargements'),('extensions',self.extensions_info,'Extensions'),('profile',self.open_account,'Compte Google'),('settings',self.open_settings,'Paramètres'),('menu',self.menu,'Menu Nova')]:
            action=bar.addAction(icon(name),tip);action.triggered.connect(callback)
            if name=='profile':self.profile_action=action
        self.sync_client.signedIn.connect(self.update_google_profile);self.sync_client.avatarChanged.connect(self.update_google_profile)
        for key, callback in [('Ctrl+L', lambda:self.address.setFocus()), ('Ctrl+W', lambda:self.close_tab(self.tabs.currentIndex())), ('Ctrl+Tab', lambda:self.tabs.setCurrentIndex((self.tabs.currentIndex()+1)%self.tabs.count())), ('F11', lambda:self.showNormal() if self.isFullScreen() else self.showFullScreen())]:
            action=QAction(self); action.setShortcut(QKeySequence(key)); action.triggered.connect(callback); self.addAction(action)
        self.setStyleSheet('''QMainWindow,QTabWidget::pane{background:#07060e;border:0}QToolBar{background:#100d1c;border:0;padding:10px;spacing:8px}QToolButton{color:#d4c4ff;background:transparent;border:0;border-radius:10px;padding:8px;font-size:22px}QToolButton:hover{background:#302047}QLineEdit{background:#080710;border:1px solid #292034;border-radius:21px;padding:12px 18px;color:#eee;font-size:15px;min-width:300px}QTabBar::tab{background:#0a0811;color:#a99dbf;padding:13px 26px;min-width:130px;max-width:220px}QTabBar::tab:selected{background:#20162f;color:#f5eeff;border-top:2px solid #9b46ff}QMenu{background:#171120;color:#eee;border:1px solid #4b3069}QMenu::item{padding:9px 25px}QMenu::item:selected{background:#4b2568}QStatusBar{background:#100d1c;color:#c5b4df}''')
        self.setStyleSheet(self.styleSheet()+'''QWidget#chrome,QWidget#titleBar{background:#080611}QToolBar{background:#100d1c;padding:4px 16px;spacing:16px;border-bottom:1px solid #21172e}QToolButton{padding:6px}QToolButton#closeWindow:hover{background:#b62b51}QTabBar::tab{background:transparent;min-width:170px;max-width:230px;padding:14px 20px;border:0;color:#b8abc9}QTabBar::tab:selected{background:#1a1429;border-top:0;border-top-left-radius:20px;border-top-right-radius:20px;color:#f8f1ff}QLineEdit{padding:10px 16px;border-radius:24px;min-width:200px;border:0;background:#080610}QTabWidget::pane{border:0}''')
        for action in bar.actions():
            widget=bar.widgetForAction(action)
            if isinstance(widget,QToolButton): widget.setIconSize(QSize(24,24)); widget.setFixedSize(34,36);widget.setAutoRaise(True);widget.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(self.styleSheet()+'''QTabBar::tab{min-width:155px;max-width:215px;padding:9px 17px;margin:3px 0;border:1px solid transparent;border-radius:14px;font-size:13px}QTabBar::tab:selected{border:1px solid #2b203d;border-radius:14px;background:#1b142a}QToolBar{spacing:12px;padding:3px 14px}QLineEdit{font-size:14px;padding:7px 12px;border:1px solid #151020;border-radius:19px}''')
        self.top_tabs.setFont(__import__('PySide6.QtGui',fromlist=['QFont']).QFont('Segoe UI',11))
        self.download_records=[]
        self.statusBar().hide()
        self.resize_grip=QSizeGrip(self); self.resize_grip.setFixedSize(18,18)
        self.apply_theme()
        self.new_tab()
        self.update_tab_style()
        self.updater=Updater(self)
        self.address_suggestions=AddressSuggestions(self)
    def save(self):
        saved={k:v for k,v in self.data.items() if k!='nova_search_base'}
        temp=self.datafile.with_suffix('.tmp'); temp.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8'); temp.replace(self.datafile)
    def update_google_profile(self,*args):
        client=self.sync_client;self.profile_action.setIcon(QIcon(client.avatar) if not client.avatar.isNull() else icon('profile'))
        self.profile_action.setToolTip((client.google_profile.get('name') or client.email or 'Compte Google')+('\n'+client.email if client.email else ''))
    def current(self): return self.tabs.currentWidget()
    def activate_tab(self,index):
        view=self.top_tabs.tabData(index) if index>=0 else None
        if view is not None and self.tabs.indexOf(view)>=0:self.tabs.setCurrentWidget(view)
    def move_tab(self,old,new):
        selected=self.top_tabs.tabData(self.top_tabs.currentIndex())
        self.tabs.blockSignals(True);self.tabs.tabBar().moveTab(old,new)
        if selected is not None:self.tabs.setCurrentWidget(selected)
        self.tabs.blockSignals(False);self.tab_changed()
    def tab_changed(self,*args):
        self.sync(force=True)
    def media_shortcut(self,view,command):
        if self.tabs.indexOf(view)<0:return
        if command=='address':
            self.activateWindow();self.address.setFocus(Qt.FocusReason.ShortcutFocusReason);self.address.selectAll()
        elif command=='new-tab':self.new_tab()
        elif command=='close-tab':self.close_tab(self.tabs.indexOf(view))
        elif command=='next-tab':self.tabs.setCurrentIndex((self.tabs.currentIndex()+1)%self.tabs.count())
        elif command=='previous-tab':self.tabs.setCurrentIndex((self.tabs.currentIndex()-1)%self.tabs.count())
        elif command=='fullscreen':self.fullscreen(not self.isFullScreen())
        elif command=='exit-fullscreen' and self.isFullScreen():self.fullscreen(False)
    def resolve(self,value):
        if value.strip().lower() in ('youtube','yt'):return QUrl('https://www.youtube.com/')
        if value.strip().lower().startswith(('yt ','youtube ')):return QUrl('https://www.youtube.com/results?search_query='+quote_plus(value.strip().split(' ',1)[1]))
        if value.strip().startswith('nova://'):return QUrl(value.strip())
        result=destination(value)
        if result.host()=='www.google.com' and result.path()=='/search':
            engine=self.data.get('preferences',{}).get('search_engine','Nova Search')
            if engine=='Nova Search':
                searches=self.data.setdefault('recent_searches',[]);self.data['recent_searches']=([value.strip()]+[x for x in searches if x!=value.strip()])[:30];self.save()
                return QUrl(self.search_url(value.strip()))
            if engine=='DuckDuckGo':return QUrl('https://duckduckgo.com/?q='+quote_plus(value.strip()))
            if engine=='Bing':return QUrl('https://www.bing.com/search?q='+quote_plus(value.strip()))
        if result.host()=='www.google.com' and result.path()=='/search':
            searches=self.data.setdefault('recent_searches',[]);self.data['recent_searches']=([value.strip()]+[x for x in searches if x!=value.strip()])[:30];self.save()
        return result
    def apply_theme(self):
        black=self.data.get('preferences',{}).get('theme')=='black'
        bg='#030304' if black else '#080611';bar='#08080b' if black else '#100c19'
        self.setStyleSheet(self.styleSheet()+f'''QWidget#chrome,QWidget#titleBar{{background:{bg};border:0}}QToolBar{{background:{bar};border:0;padding:3px 14px;spacing:12px}}QToolButton{{background:transparent;border:0;padding:0;border-radius:9px}}QToolButton:hover{{background:rgba(132,76,185,23)}}QToolButton:pressed{{background:rgba(132,76,185,38)}}QToolButton#closeWindow:hover{{background:rgba(220,59,108,45)}}QTabBar{{background:transparent;border:0}}QTabBar::tab,QTabBar::tab:selected{{background:transparent;border:0;margin:0;padding:0 12px;height:42px;min-width:220px}}''')
        self.top_tabs.setDrawBase(False)
    def set_theme(self,theme):
        self.data['preferences']['theme']=theme;self.save();self.apply_theme();self.refresh_home_tabs()
    def set_accent(self,color):
        self.data['preferences']['accent']=color;self.save();self.refresh_home_tabs()
        self.setStyleSheet(self.styleSheet()+f'QMenu::item:selected{{background:{color}44}}QLineEdit:focus{{border:1px solid {color}}}')
    def set_search_engine(self,engine):self.data['preferences']['search_engine']=engine;self.save();self.refresh_home_tabs()
    def search_url(self,query=''):return self.search_base+('search?q='+quote_plus(query) if query else '')
    def configure_search_server(self):
        value,ok=QInputDialog.getText(self,'Serveur Nova Search','Adresse HTTPS du serveur Nova Search (vide pour l’index local) :',text=self.data['preferences'].get('nova_search_endpoint',''))
        if not ok:return
        value=value.strip();url=QUrl(value)
        if value and (url.scheme()!='https' or not url.host() or url.userName() or url.password() or url.hasQuery() or url.hasFragment()):
            QMessageBox.information(self,'Adresse invalide','Indiquez l’adresse HTTPS de votre serveur Nova Search, sans clé API.');return
        self.search_base=value.rstrip('/')+'/' if value else self.search.base;self.data['nova_search_base']=self.search_base;self.data['preferences']['nova_search_endpoint']=value;self.save();self.refresh_home_tabs();self.searchStatus.emit('Recherche Web configurée.' if value else 'Index local activé.')
    def index_search_site(self):
        from nova_search.index import canonical
        from nova_search.crawler import crawl
        import threading
        if getattr(self,'search_crawling',False):self.searchStatus.emit('Une exploration est déjà en cours.');return
        value,ok=QInputDialog.getText(self,'Ajouter un site à l’index Nova','Adresse HTTPS publique du site (20 pages maximum) :')
        if not ok:return
        url=canonical(value.strip())
        if not url:self.searchStatus.emit('Utilisez une adresse HTTPS publique valide.');return
        self.search_crawling=True;self.searchStatus.emit('Exploration en arrière-plan…')
        def run():
            try:
                count=crawl(self.search.index,[url],limit=20,report=self.searchStatus.emit);self.searchStatus.emit(str(count)+' page(s) ajoutée(s). Rechargez Nova Search pour consulter le nouvel index.')
            finally:self.search_crawling=False
        threading.Thread(target=run,daemon=True).start()
    def update_tab_style(self,*args):
        self.top_tabs.compact=self.data['preferences'].get('compact_tabs',False)
        self.top_tabs.show_icons=self.data['preferences'].get('tab_icons',True)
        self.top_tabs.setStyleSheet(self.top_tabs.styleSheet()+('QTabBar::tab{min-width:155px;max-width:180px}' if self.top_tabs.compact else 'QTabBar::tab{min-width:220px;max-width:240px}'))
        self.top_tabs.update()
    def decorate_tab(self,index):
        close=QToolButton(self.top_tabs);close.setIcon(icon('close',22));close.setIconSize(QSize(20,20));close.setFixedSize(26,26);close.setAutoRaise(True)
        close.setStyleSheet('QToolButton{background:transparent;border:0;padding:0;border-radius:8px}QToolButton:hover{background:rgba(150,100,200,25)}')
        close.setCursor(Qt.CursorShape.ArrowCursor)
        close.clicked.connect(lambda:self.close_tab(self.top_tabs.tabAt(close.mapTo(self.top_tabs,close.rect().center()))))
        self.top_tabs.setTabButton(index,QTabBar.ButtonPosition.RightSide,close)
    def add_internal(self,view,name,ico):
        self.top_tabs.blockSignals(True);index=self.top_tabs.addTab(icon(ico),name);self.top_tabs.setTabData(index,view);self.decorate_tab(index);self.top_tabs.blockSignals(False)
        self.tabs.addTab(view,name);self.tabs.setCurrentWidget(view);self.sync();return view
    def open_settings(self,section=0):
        if type(section)!=int:section=0
        if section==3:section=2
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,SettingsPage):self.tabs.setCurrentIndex(i);view.nav.setCurrentRow(section);return view
        view=SettingsPage(self);view.nav.setCurrentRow(section);return self.add_internal(view,'Paramètres','settings')
    def open_account(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i),AccountPage):self.tabs.setCurrentIndex(i);return self.tabs.widget(i)
        return self.add_internal(AccountPage(self),'Compte Google','profile')
    def refresh_home_tabs(self):
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,QWebEngineView) and view.url().scheme()=='about':
                view.page().home_pending=True;view.setHtml(render_home(self.data),QUrl('about:blank'))
    def sync_snapshot(self):
        preferences=dict(self.data['preferences']);preferences['profileName']=self.data['profiles'].get(self.profile.storageName(),'Personnel')
        return {'bookmarks':self.data['bookmarks'],'history':self.data['history'][:300],'shortcuts':self.data['shortcuts'],'hidden_shortcuts':self.data['hidden_shortcuts'],'tabs':[{'url':self.tabs.widget(i).url().toString(),'title':self.tabs.widget(i).title()} for i in range(self.tabs.count()) if self.tabs.widget(i).url().scheme() in ('https','http')],'preferences':preferences}
    def apply_web_preferences(self,*args):
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,QWebEngineView):view.settings().setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly,self.data['preferences'].get('webrtc_public',True))
    def set_adblock(self,enabled):
        self.data['preferences']['adblock']=enabled;self.save()
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,MediaView):view.send('adblock-toggle','on' if enabled else 'off')
    def open_blocker_settings(self):
        self.new_tab();self.compatible_video()
        view=self.current()
        if isinstance(view,MediaView):
            if view.ready:view.send('adblock-settings')
            else:view.readyChanged.connect(lambda:view.send('adblock-settings'))
    def clear_cache(self):self.profile.clearHttpCache();QMessageBox.information(self,'Cache vidé','Le cache du moteur classique a été vidé. Vos favoris et connexions sont conservés.')
    def clear_cookies(self):
        if QMessageBox.question(self,'Effacer les cookies','Les sites du moteur classique seront déconnectés. Continuer ?')==QMessageBox.StandardButton.Yes:self.profile.cookieStore().deleteAllCookies()
    def sleep_tabs(self):
        count=0
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,QWebEngineView) and view is not self.current() and view.url().scheme() in ('https','http'):
                view.page().setLifecycleState(QWebEnginePage.LifecycleState.Frozen);count+=1
        return count
    def optimize(self):
        self.profile.clearHttpCache();count=self.sleep_tabs()
        QMessageBox.information(self,'Optimisation terminée',f'Cache classique vidé et {count} onglet(s) classique(s) inactif(s) mis en veille. Les lecteurs vidéo et connexions sont conservés.')
    def toggle_maximized(self): self.showNormal() if self.isMaximized() else self.showMaximized()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'top_tabs'):self.top_tabs.updateGeometry()
        if hasattr(self,'updater') and self.updater.toast:
            try:self.updater.toast.reposition(self)
            except RuntimeError:pass
        if hasattr(self,'resize_grip'): self.resize_grip.move(self.width()-18,self.height()-18)
    def fullscreen(self,on):
        self.chrome.setVisible(not on)
        self.showFullScreen() if on else self.showNormal()
    def navigate(self,url):
        self.address.clearFocus()
        if url.scheme()=='nova':
            if url.host()=='search':self.navigate(QUrl(self.search_url(parse_qs(urlsplit(url.toString()).query).get('q',[''])[0])));return
            self.open_account() if url.host()=='account' else self.open_settings();return
        if isinstance(self.current(),InternalPage):self.new_tab(url);return
        if media_url(url) and helper_path().exists() and not isinstance(self.current(),MediaView): self.open_media(url)
        else:
            self.current().setUrl(url)
            if isinstance(self.current(),MediaView):self.current().send('focus')
            else:self.current().setFocus()
    def go_back(self):
        view=self.current()
        if view is None:return
        if isinstance(view,InternalPage):self.home();return
        view.back()
    def go_forward(self):
        view=self.current()
        media=getattr(view,'forward_media',None)
        if media is not None:
            index=self.tabs.indexOf(view);view.forward_media=None
            media.setParent(self.tabs);self.tabs.blockSignals(True);self.tabs.removeTab(index);self.tabs.insertTab(index,media,media.title());self.tabs.setCurrentIndex(index);self.tabs.blockSignals(False)
            media.previous_view=view;view.setParent(media);view.hide();self.top_tabs.setTabData(index,media);self.top_tabs.setTabText(index,media.title()[:28]);media.show();media.send('resume');self.sync(force=True)
        elif view is not None:view.forward()
    def compatible_video(self):
        url=self.current().url()
        if url.scheme() in ('http','https'): self.open_media(url)
        else: self.open_media(QUrl('https://www.youtube.com/'))
    def classic_mode(self):
        url=self.current().url()
        view=self.new_tab(); view.page().media_bypass=True; view.setUrl(url)
    def open_media(self,url,page=None):
        if page is not None:
            candidates=[self.tabs.widget(i) for i in range(self.tabs.count()) if isinstance(self.tabs.widget(i),QWebEngineView) and self.tabs.widget(i).page()==page]
            if not candidates: return
            old=candidates[0]
        else: old=self.current()
        if isinstance(old,MediaView): old.setUrl(url); return
        if isinstance(old,InternalPage):self.new_tab();old=self.current()
        hidden=getattr(old,'forward_media',None)
        if hidden is not None:hidden.stop();hidden.deleteLater();old.forward_media=None
        index=self.tabs.indexOf(old)
        profile=self.root/'profiles'/self.profile.storageName()/'media'
        view=MediaView(url,profile,self)
        view.previous_view=old
        if not self.data['preferences'].get('adblock',True):view.arguments.append('--no-adblock')
        view.titleChanged.connect(lambda title:self.title(view,title))
        view.iconChanged.connect(lambda image:self.tab_favicon(view,image))
        view.urlChanged.connect(lambda u:self.page_url_changed(view))
        view.loadFinished.connect(lambda ok:self.loaded(view,ok))
        view.fullscreenChanged.connect(self.fullscreen)
        view.newTabRequested.connect(lambda value:self.new_tab(QUrl(value)))
        view.settingsRequested.connect(self.open_settings)
        view.credentialCaptured.connect(lambda payload:self.capture_credentials(view,payload))
        view.fillRequested.connect(lambda username:self.fill_credentials(view,username))
        view.backRequested.connect(lambda:self.restore_previous(view))
        view.shortcutRequested.connect(lambda command:self.media_shortcut(view,command))
        view.readyChanged.connect(lambda:view.send('focus') if self.current() is view and not self.address.hasFocus() else None)
        view.historyChanged.connect(lambda:self.sync() if self.current() is view else None)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index); self.tabs.insertTab(index,view,'Vidéo'); self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        self.top_tabs.setTabData(index,view);self.top_tabs.setTabText(index,'Vidéo'); self.top_tabs.setTabIcon(index,icon('video')); self.top_tabs.setCurrentIndex(index)
        old.stop();old.setParent(view);old.hide();self.sync(force=True)
    def restore_previous(self,view,home=False):
        index=self.tabs.indexOf(view)
        if index<0:return
        previous=view.previous_view
        if previous is None:return
        view.previous_view=None
        previous.setParent(self.tabs)
        self.tabs.blockSignals(True);self.tabs.removeTab(index);self.tabs.insertTab(index,previous,previous.title() or 'Nouvel onglet');self.tabs.setCurrentIndex(index);self.tabs.blockSignals(False)
        self.top_tabs.setTabData(index,previous);self.top_tabs.setTabText(index,previous.title()[:28] or 'Nouvel onglet')
        self.top_tabs.setTabIcon(index,previous.icon() if not previous.icon().isNull() else icon('logo'));self.top_tabs.setCurrentIndex(index)
        view.setParent(previous);view.hide();view.send('suspend');previous.forward_media=view;previous.show();self.sync(force=True)
        if home:self.home()
    def add_shortcut(self):
        dialog=ShortcutDialog(self)
        if dialog.exec():
            url=dialog.address.text();self.data['shortcuts']=[x for x in self.data['shortcuts'] if x['url']!=url]
            self.data['hidden_shortcuts']=[u for u in self.data['hidden_shortcuts'] if u!=url]
            self.data['shortcuts'].append({'title':dialog.name.text().strip(),'url':url});self.save();self.refresh_home_tabs()
    def remove_shortcut(self,url):
        url=canonical_url(url)
        self.data['shortcuts']=[x for x in self.data['shortcuts'] if canonical_url(x['url'])!=url]
        if url not in self.data['hidden_shortcuts']:self.data['hidden_shortcuts'].append(url)
        self.save();self.refresh_home_tabs()
    def edit_shortcut(self,url,title):
        dialog=ShortcutDialog(self,title,url)
        if dialog.exec():
            self.remove_shortcut(url)
            newurl=canonical_url(dialog.address.text());self.data['hidden_shortcuts']=[u for u in self.data['hidden_shortcuts'] if canonical_url(u)!=newurl]
            self.data['shortcuts'].append({'title':dialog.name.text().strip(),'url':newurl});self.save();self.refresh_home_tabs()
    def extensions_info(self):
        view=self.current()
        if isinstance(view,MediaView):
            if view.adblock_enabled: view.send('adblock-settings')
            else: QMessageBox.information(self,'Bloqueur de publicités','uBlock Origin Lite : '+view.adblock_name)
        else: QMessageBox.information(self,'Bloqueur de publicités','uBlock Origin Lite est intégré aux onglets du moteur vidéo compatible. Utilisez le bouton vidéo pour ouvrir ce site avec le bloqueur, puis l’icône Extensions pour ses réglages.')
    def downloads_menu(self):
        QMessageBox.information(self,'Téléchargements','\n'.join(self.download_records[-15:]) or 'Aucun téléchargement dans cette session.')
    def new_tab(self, url=None):
        view=NovaWebView(self); page=Page(self.profile,self);page.setBackgroundColor(QColor('#07060e')); view.setPage(page)
        install_bridge(self,view)
        settings=page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly,self.data['preferences'].get('webrtc_public',True))
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        page.fullScreenRequested.connect(lambda request:(request.accept(),self.fullscreen(request.toggleOn())))
        page.permissionRequested.connect(self.permission)
        page.certificateError.connect(lambda error:error.rejectCertificate())
        page.renderProcessTerminated.connect(lambda *args:self.statusBar().showMessage('Onglet interrompu : rechargez la page.'))
        self.top_tabs.blockSignals(True)
        index=self.top_tabs.addTab(icon('logo'),'Nouvel onglet');self.top_tabs.setTabData(index,view);self.decorate_tab(index)
        self.top_tabs.blockSignals(False)
        self.tabs.addTab(view,'Nouvel onglet'); self.tabs.setCurrentWidget(view)
        view.titleChanged.connect(lambda title:self.title(view,title))
        view.iconChanged.connect(lambda image:self.tab_favicon(view,image))
        view.urlChanged.connect(lambda u:self.page_url_changed(view))
        view.loadFinished.connect(lambda ok:self.loaded(view,ok))
        if isinstance(url,QUrl): view.setUrl(url)
        else:
            page.home_pending=True
            view.setHtml(render_home(self.data),QUrl('about:blank'))
        return view
    def home(self):
        if isinstance(self.current(),MediaView):self.restore_previous(self.current(),home=True);return
        if isinstance(self.current(),InternalPage):
            previous=self.current();index=self.tabs.currentIndex();view=self.new_tab();self.top_tabs.moveTab(self.tabs.indexOf(view),index);self.close_tab(self.tabs.indexOf(previous));return
        self.current().page().home_pending=True
        self.current().setHtml(render_home(self.data),QUrl('about:blank'))
    def close_tab(self,index):
        if not 0<=index<self.tabs.count():return
        view=self.tabs.widget(index)
        hidden=getattr(view,'forward_media',None)
        if hidden is not None:hidden.stop();hidden.deleteLater();view.forward_media=None
        # Keep the stack populated before removing its last native surface.
        if self.tabs.count()==1:self.new_tab()
        view.hide()
        self.top_tabs.blockSignals(True); self.top_tabs.removeTab(index); self.top_tabs.blockSignals(False)
        self.tabs.removeTab(index)
        if isinstance(view,MediaView):
            if view.previous_view is not None:view.previous_view.page().deleteLater();view.previous_view.deleteLater();view.previous_view=None
            view.stop(); view.deleteLater()
        elif isinstance(view,InternalPage):view.deleteLater()
        elif view: view.page().deleteLater(); view.deleteLater()
        if not self.tabs.count(): self.new_tab()
    def title(self,view,title):
        index=self.tabs.indexOf(view)
        if index>=0:
            self.tabs.setTabText(index,title[:28] or 'Nouvel onglet'); self.tabs.setTabToolTip(index,title)
            self.top_tabs.setTabText(index,title[:28] or 'Nouvel onglet'); self.top_tabs.setTabToolTip(index,title)
    def tab_favicon(self,view,image):
        index=self.tabs.indexOf(view)
        if index>=0:
            value=image if not image.isNull() else icon('logo')
            self.tabs.setTabIcon(index,value);self.top_tabs.setTabIcon(index,value)
    def capture_credentials(self,view,payload):
        if self.vault is None or not isinstance(payload,dict):return
        origin=secure_origin(view.url().toString())
        if not origin:return
        username=str(payload.get('username',''))[:254].strip();password=payload.get('password','')
        if not isinstance(password,str) or len(password)>4096:return
        prefs=self.data['preferences']
        if username:
            self.last_emails[origin]=username
            if prefs.get('remember_emails',True):
                try:self.vault.remember_email(username)
                except OSError:pass
        else:username=self.last_emails.get(origin,'')
        if not password or not username or not prefs.get('save_passwords',True):return
        if any(record['username']==username and record['password']==password for record in self.vault.for_site(origin)):return
        fingerprint=hashlib.sha256((origin+'\0'+username+'\0'+password).encode()).hexdigest()
        if time.monotonic()-self.capture_times.get(fingerprint,0)<30 or self.credential_prompt is not None:return
        self.capture_times={fingerprint:time.monotonic()}
        dialog=NovaDialog(self,'Enregistrer sur Nova ?',origin+'\n'+username+'\nLe mot de passe sera protégé par votre session Windows, uniquement sur cet appareil.')
        self.credential_prompt=dialog
        secret={'value':password}
        row=QHBoxLayout();row.addStretch();no=QPushButton('Pas maintenant');no.clicked.connect(dialog.reject);row.addWidget(no)
        yes=QPushButton('Enregistrer sur Nova');yes.setObjectName('primary');row.addWidget(yes);dialog.body.addLayout(row)
        def save():
            try:self.vault.put(origin,username,secret['value'])
            except (OSError,ValueError):QMessageBox.information(self,'Coffre indisponible','Nova n’a pas enregistré le mot de passe. Vérifiez la protection de votre session Windows.')
            dialog.accept()
        def finished(*args):secret.clear();self.credential_prompt=None;dialog.deleteLater()
        yes.clicked.connect(save);dialog.finished.connect(finished);dialog.setModal(False);dialog.show()
    def fill_credentials(self,view,username=''):
        if self.vault is None:return
        origin=secure_origin(view.url().toString())
        if not origin:return
        records=self.vault.for_site(origin);prefs=self.data['preferences'];record=next((x for x in records if x['username']==username),None)
        if record is None and not username and len(records)==1:record=records[0]
        payload={'origin':origin,'emails':self.vault.data['emails'] if prefs.get('remember_emails',True) else []}
        if record and prefs.get('autofill',True):payload.update(username=record['username'],password=record['password'])
        if isinstance(view,MediaView):view.send('autofill',json.dumps(payload))
        elif isinstance(view,QWebEngineView):view.page().runJavaScript('window.__novaFill?.('+json.dumps(payload)+')')
    def open_vault(self):
        dialog=NovaDialog(self,'Identifiants enregistrés','Stockage local protégé par Windows. Les mots de passe ne sont pas synchronisés.')
        dialog.setMinimumWidth(540)
        if self.vault is None:dialog.body.addWidget(QLabel('Le coffre Windows est indisponible.'))
        else:
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMaximumHeight(330);scroll.setMinimumHeight(120);scroll.setStyleSheet('QScrollArea{border:0;background:transparent}');content=QWidget();items=QVBoxLayout(content)
            for record in list(self.vault.data['credentials']):
                row=QHBoxLayout();label=QLabel(record['origin']+'\n'+record['username']);label.setTextFormat(Qt.TextFormat.PlainText);row.addWidget(label);row.addStretch();button=QPushButton('Supprimer');row.addWidget(button);items.addLayout(row)
                def remove(checked=False,r=record,b=button):
                    if QMessageBox.question(dialog,'Supprimer cet identifiant ?',r['origin']+'\n'+r['username'])==QMessageBox.StandardButton.Yes:self.vault.delete(r['origin'],r['username']);b.setEnabled(False);b.setText('Supprimé')
                button.clicked.connect(remove)
            if not self.vault.data['credentials']:items.addWidget(QLabel('Aucun identifiant enregistré.'))
            scroll.setWidget(content);dialog.body.addWidget(scroll)
        dialog.buttons('Fermer','Annuler');dialog.exec()
    def page_url_changed(self,view):
        if view is self.current():self.sync()
    def sync(self,*args,force=False):
        if not self.current(): return
        if isinstance(self.current(),QWebEngineView):self.current().page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
        self.top_tabs.blockSignals(True); self.top_tabs.setCurrentIndex(self.tabs.currentIndex()); self.top_tabs.blockSignals(False)
        url=self.current().url()
        own_search=url.toString().startswith(self.search_base)
        query=parse_qs(urlsplit(url.toString()).query).get('q',[''])[0] if own_search else ''
        display='nova://search'+('?q='+quote_plus(query) if query else '') if own_search else '' if url.scheme()=='about' else url.toString()
        if force or not self.address.hasFocus():self.address.setText(display)
        self.address.setToolTip('Nova Search · index indépendant sur cet appareil' if own_search else 'HTTPS : connexion chiffrée' if url.scheme()=='https' else 'Vérifiez le protocole et le domaine avant de saisir des données.')
        view=self.current()
        back=isinstance(view,InternalPage) or (view.can_back or view.previous_view is not None if isinstance(view,MediaView) else view.history().canGoBack() if isinstance(view,QWebEngineView) else False)
        forward=(view.can_forward if isinstance(view,MediaView) else view.history().canGoForward() or getattr(view,'forward_media',None) is not None if isinstance(view,QWebEngineView) else False)
        self.bar.actions()[0].setEnabled(back);self.bar.actions()[1].setEnabled(forward)
    def loaded(self,view,ok):
        if not ok: self.statusBar().showMessage('Chargement impossible ou interrompu.',6000); return
        url=view.url().toString()
        if url.startswith(('https://','http://')) and not url.startswith(self.search.base):
            self.data['history'].insert(0,{'title':view.title(),'url':url})
            self.data['history']=self.data['history'][:300]; self.save()
        self.statusBar().showMessage('Prêt',2000)
        if self.current() is view:self.sync()
    def permission(self,permission):
        answer=QMessageBox.question(self,'Autorisation du site',f'{permission.origin().toString()} demande : {permission.permissionType().name}.\nAutoriser ?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes: permission.grant()
        else: permission.deny()
    def bookmark(self):
        url=self.current().url().toString()
        if not url.startswith(('http://','https://')): return
        if not any(x['url']==url for x in self.data['bookmarks']):
            self.data['bookmarks'].append({'title':self.current().title(),'url':url}); self.save()
        self.statusBar().showMessage('Favori enregistré',3000)
    def download(self,item):
        path,_=QFileDialog.getSaveFileName(self,'Enregistrer le téléchargement',str(Path.home()/'Downloads'/Path(item.downloadFileName()).name))
        if not path: item.cancel(); return
        item.setDownloadDirectory(str(Path(path).parent)); item.setDownloadFileName(Path(path).name); item.accept()
        self.download_records.append(Path(path).name)
        item.stateChanged.connect(lambda state:self.statusBar().showMessage(f'Téléchargement : {item.downloadFileName()} · {state.name}'))
    def menu(self):
        menu=QMenu(self)
        menu.addAction(icon('settings'),'Paramètres Nova').triggered.connect(self.open_settings)
        menu.addAction(icon('profile'),'Compte Google').triggered.connect(self.open_account)
        menu.addAction(icon('plus'),'Ajouter une application…').triggered.connect(self.add_shortcut)
        menu.addSeparator()
        for title,key in [('Favoris','bookmarks'),('Historique','history')]:
            sub=menu.addMenu(title)
            for entry in self.data[key][:40]:
                sub.addAction(entry['title'][:60] or entry['url']).triggered.connect(lambda checked=False,u=entry['url']:self.new_tab(QUrl(u)))
            if not self.data[key]: sub.addAction('Aucun élément').setEnabled(False)
        profiles=menu.addMenu('Profils locaux')
        for ident,name in self.data['profiles'].items():
            profiles.addAction(('✓ ' if ident==self.data['active'] else '')+name).triggered.connect(lambda checked=False,i=ident:self.switch_profile(i))
        profiles.addAction('Créer un profil…').triggered.connect(self.create_profile)
        menu.addAction('Compte Google').triggered.connect(self.open_account)
        menu.addAction('Moteur vidéo compatible (YouTube / directs)').triggered.connect(self.compatible_video)
        menu.addAction('Bloqueur de publicités : réglages uBlock Origin Lite').triggered.connect(self.extensions_info)
        menu.addAction('Ouvrir ce site avec le moteur classique (connexions)').triggered.connect(self.classic_mode)
        menu.addAction('Effacer historique et cache').triggered.connect(self.clear)
        menu.addAction('À propos et sécurité').triggered.connect(lambda:QMessageBox.information(self,'Nova Browser','Nova Browser · Qt WebEngine et WebView2\n\nNova Search utilise notre index indépendant, encore limité. Vos profils et votre coffre chiffré par Windows restent sur cet ordinateur.\n\nConnexion au compte via Google. uBlock Origin Lite dans le moteur vidéo. Mises à jour distribuées sur GitHub. Version de développement non auditée.'))
        menu.exec(self.mapToGlobal(self.rect().topRight())-QPoint(320,-100))
    def create_profile(self):
        name,ok=QInputDialog.getText(self,'Créer un profil local','Nom (sans compte cloud ni mot de passe) :')
        if ok and name.strip():
            ident=uuid.uuid4().hex; self.data['profiles'][ident]=name.strip()[:60]; self.switch_profile(ident)
    def switch_profile(self,ident):
        self.data['active']=ident; self.save()
        QMessageBox.information(self,'Profil enregistré','Fermez puis relancez Nova pour utiliser ce profil et ses cookies séparés.')
    def clear(self):
        self.data['history']=[]; self.profile.clearHttpCache(); self.save()
        self.statusBar().showMessage('Historique et cache effacés. Les cookies de connexion sont conservés.',6000)
    def closeEvent(self,event):
        self.save()
        self.search.close()
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            hidden=getattr(view,'forward_media',None)
            if hidden is not None:hidden.stop()
            if isinstance(view,MediaView): view.stop()
            elif isinstance(view,QWebEngineView): view.setPage(QWebEnginePage(view))
        super().closeEvent(event)

if __name__=='__main__':
    app=QApplication(sys.argv); app.setApplicationName('NovaBrowserSmoke-'+uuid.uuid4().hex if '--smoke-test' in sys.argv else 'NovaBrowser'); app.setOrganizationName('NovaBrowser')
    local_server=None
    if '--smoke-test' not in sys.argv:
        profile_root=Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation));profile_root.mkdir(parents=True,exist_ok=True)
        instance_name='NovaBrowser-'+hashlib.sha256(str(profile_root).encode()).hexdigest()[:16]
        instance_lock=QLockFile(str(profile_root/'browser.lock'))
        if not instance_lock.tryLock(0):
            existing=QLocalSocket();existing.connectToServer(instance_name)
            if existing.waitForConnected(500):existing.write(b'activate');existing.waitForBytesWritten(500)
            sys.exit(0)
        local_server=QLocalServer(app);local_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption);local_server.removeServer(instance_name);local_server.listen(instance_name)
        app.aboutToQuit.connect(instance_lock.unlock)
    window=Browser()
    if local_server is not None:
        def activate_existing():
            connection=local_server.nextPendingConnection()
            if connection:
                connection.close();connection.deleteLater()
            if window.isMinimized():window.showNormal()
            window.raise_();window.activateWindow()
        local_server.newConnection.connect(activate_existing)
    if '--smoke-test' in sys.argv:window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    window.show()
    if '--smoke-test' in sys.argv:
        def check():
            def checked(title):
                print('SMOKE_TITLE='+str(title),flush=True)
                window.grab().save(str(Path(__file__).parent/'preview.png'))
                window.open_settings()
                QTimer.singleShot(500,settings_capture)
            def settings_capture():
                window.grab().save(str(Path(__file__).parent/'settings-preview.png'))
                window.open_account()
                QTimer.singleShot(300,lambda:(window.grab().save(str(Path(__file__).parent/'account-preview.png')),app.quit()))
            view=next((window.tabs.widget(i) for i in range(window.tabs.count()) if isinstance(window.tabs.widget(i),QWebEngineView)),None)
            if view:view.page().runJavaScript('document.title',checked)
            else:app.exit(2)
        QTimer.singleShot(7000,check)
    sys.exit(app.exec())
