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
import hashlib,time,re

PAUSE_MEDIA="""(()=>{const playing=[...document.querySelectorAll('video,audio')].filter(e=>!e.paused&&!e.ended);window.__novaPausedMedia=[...new Set([...(window.__novaPausedMedia||[]).filter(e=>e.isConnected),...playing])];playing.forEach(e=>e.pause());return playing.length;})()"""
RESUME_MEDIA="""(()=>{const media=window.__novaPausedMedia||[];window.__novaPausedMedia=[];media.filter(e=>e.isConnected).forEach(e=>{try{e.play()?.catch(()=>{});}catch{}});})()"""
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
        if main and url.scheme() in ('http','https'):
            if not self.window.permit_navigation(url,self.window.current()):return False
            target=upgrade_http(url.toString(),self.window.http_exceptions)
            if target!=url.toString():QTimer.singleShot(0,lambda:self.setUrl(QUrl(target)));return False
        if main and not self.media_bypass and media_url(url) and helper_path().exists():
            QTimer.singleShot(0,lambda:self.window.open_media(url,self))
            return False
        return url.scheme().lower() in ('https', 'http', 'about')
    def createWindow(self, kind):
        return None

class NovaWebView(QWebEngineView):
    def __init__(self,window):super().__init__();self.window=window
    def contextMenuEvent(self,event):
        from menus import NovaMenu,menu_icon
        request=self.lastContextMenuRequest();menu=NovaMenu(self.window)
        link=request.linkUrl()
        if link.isValid() and link.scheme() in ('http','https'):
            menu.addAction(menu_icon('plus'),'Ouvrir dans un nouvel onglet').triggered.connect(lambda:self.window.new_tab(link))
            menu.addAction(menu_icon('copy'),'Copier l’adresse du lien').triggered.connect(lambda:self.window.copy_link(link.toString()))
            if self.url().scheme()=='about' and link.host()!='nova.local':
                title=next((x['title'] for x in self.window.data['shortcuts'] if x['url']==link.toString()),None)
                if title is None:title=next((n for n,u,s in SHORTCUTS if QUrl(u)==link),link.host())
                menu.addSeparator();menu.addAction(menu_icon('settings'),'Modifier le raccourci…').triggered.connect(lambda:self.window.edit_shortcut(link.toString(),title));menu.addAction(menu_icon('trash'),'Supprimer le raccourci').triggered.connect(lambda:self.window.remove_shortcut(link.toString()))
            menu.addSeparator()
        image=request.mediaUrl()
        if request.mediaType().name=='MediaTypeImage':
            menu.section('Image')
            for title,symbol,action in [('Enregistrer l’image sous…','download',QWebEnginePage.WebAction.DownloadImageToDisk),('Copier l’image','copy',QWebEnginePage.WebAction.CopyImageToClipboard),('Copier l’adresse de l’image','copy',QWebEnginePage.WebAction.CopyImageUrlToClipboard)]:
                menu.addAction(menu_icon(symbol),title).triggered.connect(lambda checked=False,a=action:self.page().triggerAction(a))
            if image.scheme() in ('http','https'):menu.entry('Ouvrir l’image dans un nouvel onglet','plus',lambda:self.window.new_tab(image))
            menu.addSeparator()
        if request.selectedText():menu.addAction(menu_icon('copy'),'Copier la sélection').triggered.connect(lambda:self.page().triggerAction(QWebEnginePage.WebAction.Copy))
        if request.isContentEditable():menu.addAction(menu_icon('paste'),'Coller').triggered.connect(lambda:self.page().triggerAction(QWebEnginePage.WebAction.Paste))
        menu.addAction(menu_icon('back'),'Retour').triggered.connect(self.back)
        menu.addAction(menu_icon('forward'),'Suivant').triggered.connect(self.forward)
        menu.addAction(menu_icon('reload'),'Actualiser').triggered.connect(self.reload)
        menu.addSeparator();menu.addAction(menu_icon('translate'),'Traduire en français').triggered.connect(lambda:self.window.translate_french(request.selectedText()))
        menu.addAction(menu_icon('capture'),'Capture de la page').triggered.connect(self.window.capture_page)
        menu.addAction(menu_icon('settings'),'Paramètres Nova').triggered.connect(self.window.open_settings)
        menu.exec(event.globalPos());menu.deleteLater()

from features import Features
from security import upgrade_http,suspicious

class Browser(Features,QMainWindow):
    searchStatus=Signal(str)
    preferenceChanged=Signal(str,object)
    def __init__(self,private=False,isolated=False):
        super().__init__()
        self.private=private;self.isolated=isolated;self._closing_window=False
        self.setWindowTitle('Nova')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(1672, 941); self.setMinimumSize(900,600)
        self.setWindowIcon(icon('logo',64))
        self._private_dir=None
        if private:
            import tempfile
            self._private_dir=Path(tempfile.mkdtemp(prefix='Nova-private-'))
        self.root = Path(self._private_dir) if private else Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        self.root.mkdir(parents=True, exist_ok=True)
        self.datafile = self.root / 'settings.json'
        try: self.data = {} if private else json.loads(self.datafile.read_text(encoding='utf-8'))
        except (OSError, ValueError): self.data = {}
        self.data.setdefault('profiles', {'default': 'Personnel'})
        self.data.setdefault('active', 'default')
        self.data.setdefault('bookmarks', [])
        self.data.setdefault('history', [])
        self.data.setdefault('shortcuts',[])
        self.data.setdefault('hidden_shortcuts',[])
        self.data.setdefault('preferences',{'theme':'violet','tab_icons':True,'adblock':True,'webrtc_public':True})
        if private:
            self.data['welcome_completed']=True;self.data['preferences'].update(theme='black',accent='#bbbbbb',search_engine='Google',ai_suggestions=False)
        self.init_features()
        self.search=None
        self._active_view=None
        self._save_timer=QTimer(self);self._save_timer.setSingleShot(True);self._save_timer.setInterval(250);self._save_timer.timeout.connect(self.save)
        self._last_settings=None
        if not self.data.get('nova_search_migrated'):
            self.data['preferences']['search_engine']='Nova Search';self.data['nova_search_migrated']=True
        if not self.data.get('google_search_default_v1'):
            self.data['preferences']['search_engine']='Google';self.data['google_search_default_v1']=True
        endpoint=self.data['preferences'].get('nova_search_endpoint','');target=QUrl(endpoint)
        self.search_base=endpoint.rstrip('/')+'/' if target.scheme()=='https' and target.host() and not target.userName() and not target.password() and not target.hasQuery() and not target.hasFragment() else ''
        self.data['nova_search_base']=self.search_base or 'https://nova.local/'
        if self.data['preferences'].get('search_engine','Google')=='Nova Search' and not self.search_base:self.ensure_search()
        self.sync_client=SyncClient(self)
        try:self.vault=None if private else Vault(self.root/'vault.dat')
        except (OSError,ValueError):self.vault=None
        self.last_emails={};self.capture_times={};self.credential_prompt=None
        from ai_suggestions import AISuggestions
        self.ai=AISuggestions(self)
        self.profile = QWebEngineProfile(self) if private else QWebEngineProfile(self.data['active'], self)
        folder = self.root / 'profiles' / self.data['active']
        if not private:
            self.profile.setPersistentStoragePath(str(folder / 'storage'))
            self.profile.setCachePath(str(folder / 'cache'))
        self.profile.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime)
        if private:self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setHttpCacheMaximumSize(256 * 1024 * 1024)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies if private else QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
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
        logo=QLabel();logo.setFixedWidth(36);logo.setAlignment(Qt.AlignmentFlag.AlignCenter);logo.setPixmap(icon('logo',30).pixmap(30,30));row.addWidget(logo);row.addSpacing(12)
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
        self.address.returnPressed.connect(self.submit_address)
        bar.addWidget(self.address)
        for name,callback,tip in [('star',self.bookmark,'Ajouter aux favoris'),('download',self.downloads_menu,'Téléchargements'),('extensions',self.extensions_info,'Extensions'),('profile',self.open_account,'Compte Google'),('settings',self.open_settings,'Paramètres'),('menu',self.menu,'Menu Nova')]:
            action=bar.addAction(icon(name),tip);action.triggered.connect(callback)
            if name=='profile':self.profile_action=action
        self.sync_client.signedIn.connect(self.update_google_profile);self.sync_client.avatarChanged.connect(self.update_google_profile)
        for key, callback in [('Ctrl+L', lambda:self.address.setFocus()), ('Ctrl+W', lambda:self.close_tab(self.tabs.currentIndex())), ('Ctrl+Tab', lambda:self.tabs.setCurrentIndex((self.tabs.currentIndex()+1)%self.tabs.count())), ('F11', self.toggle_browser_fullscreen)]:
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
        self._base_style=self.styleSheet()
        self.apply_theme()
        self.new_tab()
        self.update_tab_style()
        self.updater=Updater(self)
        self.address_suggestions=AddressSuggestions(self)
        from downloads import Downloads
        self.download_panel=Downloads(self)
        self._session_timer=QTimer(self);self._session_timer.setSingleShot(True);self._session_timer.setInterval(600);self._session_timer.timeout.connect(self.save_session)
        self.previous_session=self.data.get('session',{});self._session_ready=False
        self.setup_feature_ui()
        QTimer.singleShot(0,self.start_session)
    def save(self):
        self._save_timer.stop()
        if self.private:return
        saved={k:v for k,v in self.data.items() if k!='nova_search_base'}
        serialized=json.dumps(saved,ensure_ascii=False,indent=2)
        if serialized==self._last_settings:return
        temp=self.datafile.with_suffix('.tmp');temp.write_text(serialized,encoding='utf-8');temp.replace(self.datafile);self._last_settings=serialized
    def schedule_save(self):
        if not self._save_timer.isActive():self._save_timer.start()
    def update_google_profile(self,*args):
        client=self.sync_client;self.profile_action.setIcon(QIcon(client.avatar) if not client.avatar.isNull() else icon('profile'))
        self.profile_action.setToolTip((client.google_profile.get('name') or client.email or 'Compte Google')+('\n'+client.email if client.email else ''))
    def current(self):
        view=self.tabs.currentWidget();floating=getattr(self,'floating',None)
        return floating.view if floating and view is floating.placeholder else view
    def floating_player(self):
        if self._private_locked:return
        if getattr(self,'floating',None):self.floating.raise_();return
        view=self.current()
        if not isinstance(view,(MediaView,QWebEngineView)):return
        from floating import FloatingPlayer
        self.floating=FloatingPlayer(self,view)
    def activate_tab(self,index):
        view=self.top_tabs.tabData(index) if index>=0 else None
        if view is not None and self.tabs.indexOf(view)>=0:self.tabs.setCurrentWidget(view)
    def move_tab(self,old,new):
        selected=self.top_tabs.tabData(self.top_tabs.currentIndex())
        self.tabs.blockSignals(True);self.tabs.tabBar().moveTab(old,new)
        if selected is not None:self.tabs.setCurrentWidget(selected)
        self.tabs.blockSignals(False);self.tab_changed()
    def tab_changed(self,*args):
        current=self.current();previous=self._active_view
        if previous is not current:
            if getattr(self,'_video_fullscreen_active',False):self.exit_video_fullscreen(previous)
            if previous is not None and not getattr(previous,'_closing',False):
                if isinstance(previous,MediaView):previous.send('thumbnail')
                try:previous._preview=previous.grab().scaled(280,160,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                except RuntimeError:pass
                if time.monotonic()-getattr(previous,'_visited_at',time.monotonic())>300:self.revoke_site(previous)
            if current is not None:current._visited_at=time.monotonic()
            self._active_view=current
            if previous is not None and not getattr(previous,'_closing',False) and self.data['preferences'].get('pause_background_tabs',True):self.pause_view(previous)
            if current is not None:self.resume_view(current)
        self.sync(force=True)
        if hasattr(self,'_session_timer') and self._session_ready:self._session_timer.start()
        self.top_tabs.update()
    def save_session(self):
        if self.private or not self._session_ready:return
        from sessions import snapshot
        self.data['session']=snapshot(self);self.save()
    def start_session(self):
        self._session_ready=True
        if self.private or QApplication.applicationName()!='NovaBrowser':return
        if self.previous_session.get('tabs'):
            self.updater.notify('Retrouvez vos onglets','Votre dernière session est disponible.',self.restore_session,action_text='Restaurer la session',symbol='reload')
        if not self.data.get('welcome_completed'):
            self.show_welcome()
        else:QTimer.singleShot(4000,self.offer_default_browser)
    def offer_default_browser(self):
        if QApplication.applicationName()!='NovaBrowser' or self.data.get('default_browser_prompt_shown'):return
        from default_browser import is_default_browser
        if is_default_browser():return
        welcome=getattr(self,'welcome',None)
        if welcome:
            try:
                if welcome.isVisible():return
            except RuntimeError:pass
        self.data['default_browser_prompt_shown']=True;self.save()
        self.updater.notify('Votre navigateur, par défaut','Ouvrez vos liens directement dans Nova. Choisissez Nova dans les paramètres Windows.',self.make_default,action_text='Choisir Nova',symbol='home')
    def show_welcome(self):
        from onboarding import Welcome
        existing=getattr(self,'welcome',None)
        if existing:
            try:
                if existing.isVisible():existing.raise_();return
            except RuntimeError:pass
        self.welcome=Welcome(self);self.welcome.setGeometry(0,self.titlebar.height(),self.width(),self.height()-self.titlebar.height());self.welcome.show();self.welcome.raise_()
    def restore_session(self):
        tabs=self.previous_session.get('tabs',[]);created=[]
        from import_data import safe_url
        for entry in tabs[:100]:
            url=safe_url(entry.get('url',''))
            if url:
                v=self.new_tab(QUrl(url));v._pinned=bool(entry.get('pinned'));v._muted=bool(entry.get('muted'));created.append(v)
                if v._muted:
                    if isinstance(v,MediaView):v.send('mute','on')
                    else:v.page().setAudioMuted(True)
        if created:self.tabs.setCurrentWidget(created[min(self.previous_session.get('selected',0),len(created)-1)])
        self.top_tabs.updateGeometry();self.top_tabs.update()
        self.previous_session={};self.save_session()
    def open_import(self):
        if self.private:return
        from onboarding import ImportDialog
        ImportDialog(self).exec()
    def make_default(self):
        from default_browser import register_browser
        try:register_browser()
        except (OSError,ValueError) as error:QMessageBox.information(self,'Navigateur par défaut',str(error))
    def pause_view(self,view):
        if getattr(view,"_floating",False):return
        if getattr(view,'_nova_suspended',False) or getattr(view,'_closing',False):return
        if isinstance(view,MediaView):view._nova_suspended=True;view.send('suspend')
        elif isinstance(view,QWebEngineView):
            view._nova_suspended=True;page=view.page()
            def paused(count):
                try:
                    if isinstance(count,(int,float)) and count>0:self.background_pause_notice(view,int(count))
                    if view is not self.current() and getattr(view,'_nova_suspended',False) and not page.isLoading() and page.recommendedState()==QWebEnginePage.LifecycleState.Frozen:page.setLifecycleState(QWebEnginePage.LifecycleState.Frozen)
                except RuntimeError:pass
            self.run_media_script(view,PAUSE_MEDIA,paused)
    def run_media_script(self,view,script,callback=None):
        frames=[view.page().mainFrame()]
        for frame in frames:
            if frame.isValid() and len(frames)<128:frames.extend(frame.children()[:128-len(frames)])
        frames=[frame for frame in frames if frame.isValid()]
        if not frames:
            if callback:callback(0)
            return
        pending=[len(frames)];count=[0]
        def completed(value):
            if isinstance(value,(int,float)):count[0]+=int(value)
            pending[0]-=1
            if not pending[0] and callback:callback(count[0])
        for frame in frames:
            try:frame.runJavaScript(script,0,completed)
            except RuntimeError:completed(0)
    def resume_view(self,view):
        if not getattr(view,'_nova_suspended',False):return
        view._nova_suspended=False
        if isinstance(view,MediaView):view.send('resume','focus' if view is self.current() else '')
        elif isinstance(view,QWebEngineView):view.page().setLifecycleState(QWebEnginePage.LifecycleState.Active);self.run_media_script(view,RESUME_MEDIA)
    def set_background_pause(self,enabled):
        self.data['preferences']['pause_background_tabs']=enabled;self.save()
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if enabled and view is not self.current():self.pause_view(view)
            else:self.resume_view(view)
    def background_pause_notice(self,view,count):
        if count<=0 or view is self.current() or self.tabs.indexOf(view)<0 or not self.data['preferences'].get('pause_background_tabs',True) or self.data.get('background_pause_hint_shown'):return
        self.data['background_pause_hint_shown']=True;self.save()
        self.updater.notify('Lecture mise en pause','Nova met les vidéos et l’audio en pause quand vous quittez un onglet. Vous pouvez désactiver cette option dans les paramètres.',lambda:self.open_settings(7),action_text='Ouvrir les paramètres',symbol='video')
        toast=self.updater.toast
        if toast:
            toast.dismiss_timer=QTimer(toast);toast.dismiss_timer.setSingleShot(True);toast.dismiss_timer.timeout.connect(toast.close);toast.dismiss_timer.start(12000)
    def media_shortcut(self,view,command):
        if self.tabs.indexOf(view)<0:return
        if command=='address':
            self.activateWindow();self.address.setFocus(Qt.FocusReason.ShortcutFocusReason);self.address.selectAll()
        elif command=='private':self.private_window()
        elif command=='mute':self.toggle_mute()
        elif command=='capture':self.capture_page()
        elif command=='focus-mode':self.toggle_focus()
        elif command=='presentation':self.toggle_presentation()
        elif command=='site':self.site_panel()
        elif command=='new-tab':self.new_tab()
        elif command=='close-tab':self.close_tab(self.tabs.indexOf(view))
        elif command=='next-tab':self.tabs.setCurrentIndex((self.tabs.currentIndex()+1)%self.tabs.count())
        elif command=='previous-tab':self.tabs.setCurrentIndex((self.tabs.currentIndex()-1)%self.tabs.count())
        elif command=='fullscreen':self.toggle_browser_fullscreen()
        elif command=='exit-fullscreen':self.exit_video_fullscreen()
    def resolve(self,value):
        if value.strip().lower() in ('youtube','yt'):return QUrl('https://www.youtube.com/')
        if value.strip().lower().startswith(('yt ','youtube ')):return QUrl('https://www.youtube.com/results?search_query='+quote_plus(value.strip().split(' ',1)[1]))
        if value.strip().startswith('nova://'):return QUrl(value.strip())
        result=destination(value)
        if not self.private and result.host()=='www.google.com' and result.path()=='/search':
            engine=self.data.get('preferences',{}).get('search_engine','Nova Search')
            if engine=='Nova Search':
                searches=self.data.setdefault('recent_searches',[]);self.data['recent_searches']=([value.strip()]+[x for x in searches if x!=value.strip()])[:30];self.schedule_save()
                return QUrl(self.search_url(value.strip()))
            if engine=='DuckDuckGo':return QUrl('https://duckduckgo.com/?q='+quote_plus(value.strip()))
            if engine=='Bing':return QUrl('https://www.bing.com/search?q='+quote_plus(value.strip()))
        if not self.private and result.host()=='www.google.com' and result.path()=='/search':
            searches=self.data.setdefault('recent_searches',[]);self.data['recent_searches']=([value.strip()]+[x for x in searches if x!=value.strip()])[:30];self.schedule_save()
        return result
    def submit_address(self):
        if not self.address_suggestions.ignore_return:self.navigate(self.resolve(self.address.text()))
    def apply_theme(self):
        if getattr(self,'private',False) and hasattr(self,'_base_style'):
            self.private_theme();return
        black=self.data.get('preferences',{}).get('theme')=='black'
        accent=self.data['preferences'].get('accent','#9338ff')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',str(accent)):accent='#9338ff'
        if getattr(self,'_applied_theme',None)==(black,accent):return
        self._applied_theme=(black,accent)
        bg='#030304' if black else '#080611';bar='#08080b' if black else '#100c19'
        self.setStyleSheet(self._base_style+f'''QWidget#chrome,QWidget#titleBar{{background:{bg};border:0}}QToolBar{{background:{bar};border:0;padding:3px 14px;spacing:12px}}QToolButton{{background:transparent;border:0;padding:0;border-radius:9px}}QToolButton:hover{{background:rgba(132,76,185,23)}}QToolButton:pressed{{background:rgba(132,76,185,38)}}QToolButton#closeWindow:hover{{background:rgba(220,59,108,45)}}QTabBar{{background:transparent;border:0}}QTabBar::tab,QTabBar::tab:selected{{background:transparent;border:0;margin:0;padding:0 12px;height:42px;min-width:220px}}QMenu::item:selected{{background:{accent}44}}QLineEdit:focus{{border:1px solid {accent}}}''')
        self.top_tabs.setDrawBase(False)
    def set_theme(self,theme):
        self.data['preferences']['theme']=theme;self.save();self.apply_theme();self.refresh_home_tabs()
    def set_accent(self,color):
        self.data['preferences']['accent']=color;self.save();self.refresh_home_tabs()
        self.apply_theme()
    def ensure_search(self):
        if self.search is None:
            from nova_search import LocalSearch
            self.search=LocalSearch(self.root/'search'/'index.sqlite3')
        if not self.search_base:self.search_base=self.search.base;self.data['nova_search_base']=self.search_base
        return self.search
    def set_search_engine(self,engine):
        self.data['preferences']['search_engine']=engine
        if engine=='Nova Search' and not self.search_base:self.ensure_search()
        self.save();self.refresh_home_tabs()
    def search_url(self,query=''):
        if not self.search_base:self.ensure_search()
        return self.search_base+('search?q='+quote_plus(query) if query else '')
    def configure_search_server(self):
        value,ok=QInputDialog.getText(self,'Serveur Nova Search','Adresse HTTPS du serveur Nova Search (vide pour l’index local) :',text=self.data['preferences'].get('nova_search_endpoint',''))
        if not ok:return
        value=value.strip();url=QUrl(value)
        if value and (url.scheme()!='https' or not url.host() or url.userName() or url.password() or url.hasQuery() or url.hasFragment()):
            QMessageBox.information(self,'Adresse invalide','Indiquez l’adresse HTTPS de votre serveur Nova Search, sans clé API.');return
        self.search_base=value.rstrip('/')+'/' if value else self.search.base if self.search else ''
        if not self.search_base and self.data['preferences'].get('search_engine')=='Nova Search':self.ensure_search()
        self.data['nova_search_base']=self.search_base or 'https://nova.local/';self.data['preferences']['nova_search_endpoint']=value;self.save();self.refresh_home_tabs();self.searchStatus.emit('Recherche Web configurée.' if value else 'Index local activé.')
    def index_search_site(self):
        from nova_search.index import canonical
        from nova_search.crawler import crawl
        import threading
        if getattr(self,'search_crawling',False):self.searchStatus.emit('Une exploration est déjà en cours.');return
        value,ok=QInputDialog.getText(self,'Ajouter un site à l’index Nova','Adresse HTTPS publique du site (20 pages maximum) :')
        if not ok:return
        url=canonical(value.strip())
        if not url:self.searchStatus.emit('Utilisez une adresse HTTPS publique valide.');return
        self.ensure_search()
        self.search_crawling=True;self.searchStatus.emit('Exploration en arrière-plan…')
        def run():
            try:
                count=crawl(self.search.index,[url],limit=20,report=self.searchStatus.emit);self.searchStatus.emit(str(count)+' page(s) ajoutée(s). Rechargez Nova Search pour consulter le nouvel index.')
            finally:self.search_crawling=False
        threading.Thread(target=run,daemon=True).start()
    def update_tab_style(self,*args):
        self.top_tabs.compact=self.data['preferences'].get('compact_tabs',False)
        self.top_tabs.show_icons=self.data['preferences'].get('tab_icons',True)
        self.top_tabs.updateGeometry()
        self.top_tabs.update()
    def decorate_tab(self,index):
        close=QToolButton(self.top_tabs);close.setIcon(icon('close',22));close.setIconSize(QSize(20,20));close.setFixedSize(26,26);close.setAutoRaise(True)
        close.setStyleSheet('QToolButton{background:transparent;border:0;padding:0;border-radius:8px}QToolButton:hover{background:rgba(150,100,200,25)}')
        if self.private:
            from ui import monochrome
            close.setIcon(monochrome(close.icon(),20))
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
        view=SettingsPage(self)
        if self.private:
            from ui import neutral_style,monochrome
            for child in [view]+view.findChildren(QWidget):
                if child.styleSheet():child.setStyleSheet(neutral_style(child.styleSheet()))
            for j in range(view.nav.count()):view.nav.item(j).setIcon(monochrome(view.nav.item(j).icon(),23))
        view.nav.setCurrentRow(section);return self.add_internal(view,'Paramètres','settings')
    def open_account(self):
        if self.private:
            NovaMessage.information(self,'Navigation privée','Le compte Nova et le coffre ne sont pas utilisés dans cette fenêtre.');return
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i),AccountPage):self.tabs.setCurrentIndex(i);return self.tabs.widget(i)
        return self.add_internal(AccountPage(self),'Compte Google','profile')
    def refresh_home_tabs(self):
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            if isinstance(view,QWebEngineView) and view.url().scheme()=='about':
                view.page().home_pending=True;view.setHtml(self.home_markup(),QUrl('about:blank'))
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
                self.pause_view(view);count+=1
        return count
    def optimize(self):
        self.profile.clearHttpCache();count=self.sleep_tabs()
        QMessageBox.information(self,'Optimisation terminée',f'Cache classique vidé et {count} onglet(s) classique(s) inactif(s) mis en veille. Les lecteurs vidéo et connexions sont conservés.')
    def toggle_maximized(self): self.showNormal() if self.isMaximized() else self.showMaximized()
    def resizeEvent(self,event):
        if getattr(self,'_lock_overlay',None):self._lock_overlay.setGeometry(self.rect())
        super().resizeEvent(event)
        if hasattr(self,'top_tabs'):self.top_tabs.updateGeometry()
        if hasattr(self,'updater') and self.updater.toast:
            try:self.updater.toast.reposition(self)
            except RuntimeError:pass
        if hasattr(self,'resize_grip'): self.resize_grip.move(self.width()-18,self.height()-18)
        if getattr(self,'welcome',None):
            try:self.welcome.setGeometry(0,self.titlebar.height(),self.width(),self.height()-self.titlebar.height())
            except RuntimeError:self.welcome=None
    def fullscreen(self,on,view=None):
        if on:
            if view is not None and view is not self.current():return
            if getattr(self,'_video_fullscreen_active',False):return
            self._video_fullscreen_active=True;self._video_fullscreen_owner=view or self.current();self._before_video_state=self.windowState();self._before_video_chrome=not self.chrome.isHidden()
            self.chrome.hide();self.showFullScreen()
        else:
            if not getattr(self,'_video_fullscreen_active',False):return
            if view is not None and view is not self._video_fullscreen_owner:return
            self._video_fullscreen_active=False;self._video_fullscreen_owner=None
            self.chrome.setVisible(self._before_video_chrome and not self._private_locked)
            state=self._before_video_state
            if state & Qt.WindowState.WindowFullScreen:self.showFullScreen()
            elif state & Qt.WindowState.WindowMaximized:self.showMaximized()
            else:self.showNormal()
    def exit_video_fullscreen(self,view=None):
        if not getattr(self,'_video_fullscreen_active',False):return
        owner=getattr(self,'_video_fullscreen_owner',None)
        if view is not None and view is not owner:return
        try:
            if isinstance(owner,MediaView):owner.send('exit-fullscreen')
            elif isinstance(owner,QWebEngineView):owner.page().runJavaScript('if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});')
        except RuntimeError:pass
        self.fullscreen(False,owner)
    def toggle_browser_fullscreen(self):
        if getattr(self,'_video_fullscreen_active',False):self.exit_video_fullscreen();return
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
    def navigate(self,url):
        self.address.clearFocus()
        if not self.permit_navigation(url,self.current()):return
        url=QUrl(upgrade_http(url.toString(),self.http_exceptions))
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
            self.pause_view(view);media.previous_view=view;view.setParent(media);view.hide();self.top_tabs.setTabData(index,media);self.top_tabs.setTabText(index,media.title()[:28]);media.show();self._active_view=media;self.resume_view(media);self.sync(force=True)
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
        if self.private:view.arguments.append('--private')
        if self.data['preferences'].get('builtin_blocker_removed',False):view.arguments.append('--skip-builtin')
        view.securityEvent.connect(lambda payload:self.native_security(view,payload))
        view.previous_view=old;view._pinned=getattr(old,'_pinned',False);view._muted=getattr(old,'_muted',False)
        if view._muted:view.send('mute','on')
        if not self.data['preferences'].get('adblock',True):view.arguments.append('--no-adblock')
        view.titleChanged.connect(lambda title:self.title(view,title))
        view.iconChanged.connect(lambda image:self.tab_favicon(view,image))
        view.urlChanged.connect(lambda u:self.page_url_changed(view))
        view.loadFinished.connect(lambda ok:self.loaded(view,ok))
        view.fullscreenChanged.connect(lambda enabled:self.fullscreen(enabled,view))
        view.newTabRequested.connect(lambda value:self.new_tab(QUrl(value)))
        view.settingsRequested.connect(self.open_settings)
        view.credentialCaptured.connect(lambda payload:self.capture_credentials(view,payload))
        view.fillRequested.connect(lambda username:self.fill_credentials(view,username))
        view.backRequested.connect(lambda:self.restore_previous(view))
        view.shortcutRequested.connect(lambda command:self.media_shortcut(view,command))
        view.readyChanged.connect(lambda:view.send('focus') if self.current() is view and not self.address.hasFocus() else None)
        view.historyChanged.connect(lambda:self.sync() if self.current() is view else None)
        view.mediaPaused.connect(lambda count:self.background_pause_notice(view,count))
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index); self.tabs.insertTab(index,view,'Vidéo'); self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        self.top_tabs.setTabData(index,view);self.top_tabs.setTabText(index,'Vidéo'); self.top_tabs.setTabIcon(index,icon('video')); self.top_tabs.setCurrentIndex(index)
        old.stop();old.setParent(view);old.hide();self.pause_view(old);self._active_view=view;self.sync(force=True)
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
        view.setParent(previous);view.hide();self.pause_view(view);previous.forward_media=view;previous.show();self._active_view=previous;self.resume_view(previous);self.sync(force=True)
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
        if self._private_locked:return
        if not hasattr(self,'extension_panel'):
            from extensions_panel import Extensions
            self.extension_panel=Extensions(self)
        self.extension_panel.open_panel()
    def downloads_menu(self,checked=None):
        if self._private_locked:return
        self.download_panel.show_panel(toggle=isinstance(checked,bool))
    def new_tab(self, url=None):
        view=NovaWebView(self); page=Page(self.profile,self);page.setBackgroundColor(QColor('#080808' if self.private else '#07060e')); view.setPage(page)
        install_bridge(self,view)
        settings=page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly,self.data['preferences'].get('webrtc_public',True))
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        page.fullScreenRequested.connect(lambda request:(request.accept(),self.fullscreen(request.toggleOn(),view)) if view is self.current() else request.reject())
        page.permissionRequested.connect(lambda permission:self.ask_permission(view,permission.origin().toString(),permission.permissionType().name,lambda yes:permission.grant() if yes else permission.deny()))
        page.newWindowRequested.connect(lambda request:self.popup_request(view,request))
        page.certificateError.connect(lambda error:error.rejectCertificate())
        page.renderProcessTerminated.connect(lambda *args:self.statusBar().showMessage('Onglet interrompu : rechargez la page.'))
        self.top_tabs.blockSignals(True)
        index=self.top_tabs.addTab(getattr(self,'private_icon',icon('logo')),'Navigation privée' if self.private else 'Nouvel onglet');self.top_tabs.setTabData(index,view);self.decorate_tab(index)
        self.top_tabs.blockSignals(False)
        self.tabs.addTab(view,'Nouvel onglet'); self.tabs.setCurrentWidget(view)
        view.titleChanged.connect(lambda title:self.title(view,title))
        view.iconChanged.connect(lambda image:self.tab_favicon(view,image))
        view.urlChanged.connect(lambda u:self.page_url_changed(view))
        view.loadFinished.connect(lambda ok:self.loaded(view,ok))
        page.recentlyAudibleChanged.connect(lambda *args:self.top_tabs.update())
        if isinstance(url,QUrl):
            if self.permit_navigation(url,view):view.setUrl(QUrl(upgrade_http(url.toString(),self.http_exceptions)))
        else:
            page.home_pending=True
            view.setHtml(self.home_markup(),QUrl('about:blank'))
        return view
    def home(self):
        if isinstance(self.current(),MediaView):self.restore_previous(self.current(),home=True);return
        if isinstance(self.current(),InternalPage):
            previous=self.current();index=self.tabs.currentIndex();view=self.new_tab();self.top_tabs.moveTab(self.tabs.indexOf(view),index);self.close_tab(self.tabs.indexOf(previous));return
        self.current().page().home_pending=True
        self.current().setHtml(self.home_markup(),QUrl('about:blank'))
    def close_tab(self,index):
        if not 0<=index<self.tabs.count():return
        if getattr(self,"floating",None) and self.tabs.widget(index) is self.floating.placeholder:self.floating.close()
        view=self.tabs.widget(index)
        if not self.confirm_close(view):return
        from motion import close_tab as animate_close_tab
        animate_close_tab(self.top_tabs,index,self)
        self.exit_video_fullscreen(view)
        self.revoke_site(view)
        view._closing=True
        hidden=getattr(view,'forward_media',None)
        if hidden is not None:hidden.stop();hidden.deleteLater();view.forward_media=None
        # Keep the stack populated before removing its last native surface.
        if self.tabs.count()==1:self.new_tab()
        view.hide()
        self.top_tabs.blockSignals(True); self.top_tabs.removeTab(index); self.top_tabs.blockSignals(False)
        self.tabs.removeTab(index)
        if hasattr(self,'_session_timer') and self._session_ready:self._session_timer.start()
        if isinstance(view,MediaView):
            if view.previous_view is not None:view.previous_view.page().deleteLater();view.previous_view.deleteLater();view.previous_view=None
            view.stop(); view.deleteLater()
        elif isinstance(view,InternalPage):view.deleteLater()
        elif view: view.page().deleteLater(); view.deleteLater()
        if not self.tabs.count(): self.new_tab()
    def title(self,view,title):
        if self.presentation:return
        index=self.tabs.indexOf(view)
        if index>=0:
            self.tabs.setTabText(index,title[:28] or 'Nouvel onglet'); self.tabs.setTabToolTip(index,title)
            self.top_tabs.setTabText(index,title[:28] or 'Nouvel onglet'); self.top_tabs.setTabToolTip(index,'' if self.presentation else title)
    def tab_favicon(self,view,image):
        if self.presentation:return
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
    def fill_credentials(self,view,username='',verified=False):
        if self.vault is None:return
        origin=secure_origin(view.url().toString())
        if not origin:return
        warning=suspicious(view.url().toString())
        if warning:
            key='blocked-fill:'+origin
            if time.monotonic()-self.capture_times.get(key,0)>60:
                self.capture_times[key]=time.monotonic();self.updater.notify('Remplissage bloqué',warning,symbol='shield')
            return
        if self.data['preferences'].get('hello_vault',False) and not verified and time.monotonic()>self.hello_until:
            def unlocked(ok):
                if ok and self.tabs.indexOf(view)>=0 and secure_origin(view.url().toString())==origin:self.hello_until=time.monotonic()+120;self.fill_credentials(view,username,True)
            self.hello.verify(unlocked);return
        records=self.vault.for_site(origin);prefs=self.data['preferences'];record=next((x for x in records if x['username'].strip().casefold()==username.strip().casefold()),None)
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
        parsed=urlsplit(view.url().toString());origin=parsed.scheme+'://'+parsed.netloc
        previous=getattr(view,'_permission_origin','')
        if previous!=origin:view._load_ok=None
        if previous and previous!=origin:
            self.grants={k:v for k,v in self.grants.items() if not (k[0]==previous and v[1] is view)}
            self.view_script(view,'window.__novaStopCapture?.()')
            if isinstance(view,MediaView):view.send('revoke')
        view._permission_origin=origin
        if view is self.current():self.sync()
        if hasattr(self,'_session_timer') and self._session_ready:self._session_timer.start()
    def sync(self,*args,force=False):
        if not self.current(): return
        if isinstance(self.current(),QWebEngineView):self.current().page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
        self.top_tabs.blockSignals(True); self.top_tabs.setCurrentIndex(self.tabs.currentIndex()); self.top_tabs.blockSignals(False)
        if self.presentation:return
        url=self.current().url()
        own_search=bool(self.search_base) and url.toString().startswith(self.search_base)
        query=parse_qs(urlsplit(url.toString()).query).get('q',[''])[0] if own_search else ''
        display='nova://search'+('?q='+quote_plus(query) if query else '') if own_search else '' if url.scheme()=='about' else url.toString()
        if force or not self.address.hasFocus():self.address.setText(display)
        self.address.setToolTip('Nova Search · index indépendant sur cet appareil' if own_search else 'HTTPS : connexion chiffrée' if url.scheme()=='https' else 'Vérifiez le protocole et le domaine avant de saisir des données.')
        view=self.current()
        back=isinstance(view,InternalPage) or (view.can_back or view.previous_view is not None if isinstance(view,MediaView) else view.history().canGoBack() if isinstance(view,QWebEngineView) else False)
        forward=(view.can_forward if isinstance(view,MediaView) else view.history().canGoForward() or getattr(view,'forward_media',None) is not None if isinstance(view,QWebEngineView) else False)
        self.bar.actions()[0].setEnabled(back);self.bar.actions()[1].setEnabled(forward)
    def loaded(self,view,ok):
        view._load_ok=bool(ok)
        if not ok:
            self.statusBar().showMessage('Chargement impossible ou interrompu.',6000)
            if isinstance(view,QWebEngineView):self.http_failure(view,view.url().toString())
            return
        if view is not self.current() and (self.data['preferences'].get('pause_background_tabs',True) or getattr(view,'_nova_suspended',False)):
            view._nova_suspended=False;self.pause_view(view)
        url=view.url().toString()
        if not self.private and url.startswith(('https://','http://')) and not (self.search and url.startswith(self.search.base)):
            self.data['history']=([{'title':view.title(),'url':url}]+[entry for entry in self.data['history'] if entry.get('url')!=url])[:300];self.schedule_save()
        self.statusBar().showMessage('Prêt',2000)
        if self.current() is view:self.sync()
    def permission(self,permission):
        if permission.permissionType().name=='ClipboardReadWrite':permission.deny();return
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
        if self._private_locked:item.cancel();return
        path,_=QFileDialog.getSaveFileName(self,'Enregistrer le téléchargement',str(Path.home()/'Downloads'/Path(item.downloadFileName()).name))
        if not path or not self.allow_download(Path(path).name,item.url().toString()): item.cancel(); return
        item.setDownloadDirectory(str(Path(path).parent)); item.setDownloadFileName(Path(path).name); item.accept()
        self.download_panel.add(item,path);self.downloads_menu()
        self.download_records.append(Path(path).name)
        item.stateChanged.connect(lambda state:self.statusBar().showMessage(f'Téléchargement : {item.downloadFileName()} · {state.name}'))
    def menu(self):
        if self._private_locked:return
        from menus import build_main_menu
        menu=build_main_menu(self)
        anchor=self.bar.widgetForAction(next(a for a in self.bar.actions() if a.text()=='Menu Nova'))
        menu.exec(anchor.mapToGlobal(QPoint(anchor.width()-menu.sizeHint().width(),anchor.height()+6)));menu.deleteLater()
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
        if not self._closing_window:
            if any(not self.confirm_close(self.tabs.widget(i)) for i in range(self.tabs.count())):event.ignore();return
            self._closing_window=True
        if getattr(self,"floating",None):self.floating.close()
        if hasattr(self,'extension_panel'):self.extension_panel.hide();self.extension_panel.stop_service()
        self._session_timer.stop();self.save_session()
        self.save()
        if self.search:self.search.close()
        for i in range(self.tabs.count()):
            view=self.tabs.widget(i)
            hidden=getattr(view,'forward_media',None)
            if hidden is not None:hidden.stop()
            if isinstance(view,MediaView): view.stop()
            elif isinstance(view,QWebEngineView): view.setPage(QWebEnginePage(view))
        super().closeEvent(event)
        if self.private:
            import subprocess
            processes=[]
            for v in self.findChildren(MediaView):
                if v.process.processId():processes.append(str(v.process.processId()))
            try:
                job=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).parent/'private-cleanup.ps1'),'-Directory',str(self.root),'-ProcessIds',','.join(processes)],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                Features.cleanup_jobs.append(job)
            except OSError:pass
            self.data.clear();self.grants.clear();self.events.clear();self.profile.deleteLater();self.deleteLater()


if __name__=='__main__':
    app=QApplication(sys.argv); app.setApplicationName('NovaBrowserSmoke-'+uuid.uuid4().hex if '--smoke-test' in sys.argv else 'NovaBrowser'); app.setOrganizationName('NovaBrowser')
    external_url=next((value for value in sys.argv[1:] if QUrl(value).scheme() in ('http','https') and QUrl(value).host()),'')
    local_server=None
    if '--smoke-test' not in sys.argv:
        profile_root=Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation));profile_root.mkdir(parents=True,exist_ok=True)
        instance_name='NovaBrowser-'+hashlib.sha256(str(profile_root).encode()).hexdigest()[:16]
        instance_lock=QLockFile(str(profile_root/'browser.lock'))
        if not instance_lock.tryLock(0):
            existing=QLocalSocket();existing.connectToServer(instance_name)
            if existing.waitForConnected(500):existing.write(json.dumps({'url':external_url}).encode()+b'\n');existing.waitForBytesWritten(500)
            sys.exit(0)
        local_server=QLocalServer(app);local_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption);local_server.removeServer(instance_name);local_server.listen(instance_name)
        app.aboutToQuit.connect(instance_lock.unlock)
    window=Browser()
    if local_server is not None:
        def activate_existing():
            connection=local_server.nextPendingConnection()
            if connection:
                buffer=bytearray()
                def receive():
                    buffer.extend(bytes(connection.readAll()))
                    if len(buffer)>8192:connection.close();connection.deleteLater();return
                    if b'\n' not in buffer:return
                    try:
                        value=json.loads(bytes(buffer).split(b'\n',1)[0]).get('url','');url=QUrl(value)
                        if url.scheme() in ('http','https') and url.host():window.new_tab(url)
                    except (ValueError,AttributeError,TypeError):pass
                    connection.close();connection.deleteLater()
                connection.readyRead.connect(receive)
                if connection.bytesAvailable():receive()
            if window.isMinimized():window.showNormal()
            window.raise_();window.activateWindow()
        local_server.newConnection.connect(activate_existing)
    if '--smoke-test' in sys.argv:window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    if '--smoke-test' in sys.argv:window.show()
    elif window.data['preferences'].get('start_fullscreen',True):window.showFullScreen()
    else:window.show()
    if getattr(sys,'frozen',False) and '--smoke-test' not in sys.argv:
        from startup import set_startup,integrate
        from default_browser import register_browser
        try:
            register_browser(False);set_startup(window.data['preferences'].get('start_with_windows',True));integrate()
            window.data['startup_configured']=True;window.save()
        except (OSError,ValueError):pass
    if external_url:QTimer.singleShot(0,lambda:window.new_tab(QUrl(external_url)))
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
