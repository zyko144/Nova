"""Compact browser tools and per-window privacy/security controls."""
import json,time,tempfile,shutil
from pathlib import Path
from urllib.parse import quote,urlsplit
from PySide6.QtCore import Qt,QTimer,QUrl,QEvent,QSize,QByteArray
from PySide6.QtGui import QAction,QKeySequence,QIcon,QPixmap,QPainter,QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication,QLabel,QPushButton,QPlainTextEdit,QHBoxLayout,QVBoxLayout,QWidget,QMenu,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView)
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from media_view import MediaView
from ui import NovaDialog,NovaMessage
from security import suspicious,host_of,sensitive_link,without_sensitive,download_warning,upgrade_http

class Features:
    windows=[]
    cleanup_jobs=[]
    def init_features(self):
        self.events=[];self.grants={};self.http_exceptions=set();self.trusted_once=set();self.presentation=False;self.focus_mode=False;self.private_previews={};self.hello_until=0
        from windows_hello import Hello
        self.hello=Hello(self)
        self.permission_timer=QTimer(self);self.permission_timer.setInterval(15000);self.permission_timer.timeout.connect(self.expire_permissions);self.permission_timer.start()
    def setup_feature_ui(self):
        from main import icon
        action=QAction(icon('shield'),'Protection de ce site',self);action.triggered.connect(self.site_panel);self.bar.insertAction(self.bar.actions()[4],action)
        self.capture_indicator=QLabel();self.capture_indicator.setStyleSheet('color:#eee;background:#333;border-radius:8px;padding:4px 9px;font-size:11px');self.capture_indicator.hide();self.bar.addWidget(self.capture_indicator)
        if self.private:
            self.setWindowTitle('Nova · Navigation privée');self.private_theme();badge=QLabel('Navigation privée');badge.setStyleSheet('color:#ccc;font-size:11px;padding:3px 8px;background:#252525;border-radius:9px');self.bar.addWidget(badge)
        for key,cb in [('Ctrl+Shift+N',self.private_window),('Ctrl+Shift+S',self.capture_page),('Ctrl+Shift+M',self.toggle_mute),('Ctrl+Shift+F',self.toggle_focus),('Ctrl+Shift+P',self.toggle_presentation)]:
            a=QAction(self);a.setShortcut(QKeySequence(key));a.triggered.connect(cb);self.addAction(a)
        self.top_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.top_tabs.customContextMenuRequested.connect(self.tab_menu)
        self.top_tabs.installEventFilter(self);self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(600);self.preview_timer.timeout.connect(self.show_tab_preview);self.hover_index=-1;self.preview_popup=None
        self.recovery_timer=QTimer(self);self.recovery_timer.setSingleShot(True);self.recovery_timer.setInterval(350);self.recovery_timer.timeout.connect(self.save_session)
    def private_theme(self):
        from private_home import PRIVATE_LOGO
        from design import svg_icon
        p=QPixmap(64,40);p.fill(Qt.GlobalColor.transparent);r=QSvgRenderer(QByteArray(PRIVATE_LOGO.encode()));paint=QPainter(p);r.render(paint);paint.end();self.setWindowIcon(QIcon(p));self.private_icon=QIcon(p)
        for label in self.titlebar.findChildren(QLabel):
            if not label.pixmap().isNull():label.setPixmap(p.scaled(30,20,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.top_tabs.private_mode=True
        self.profile_action.setVisible(False) if hasattr(self,'profile_action') else None
        names={'Précédent':'back','Suivant':'forward','Actualiser':'reload','Accueil':'home','Protection de ce site':'shield','Ajouter aux favoris':'star','Téléchargements':'download','Extensions':'extensions','Paramètres':'settings','Menu Nova':'menu'}
        for action in self.bar.actions():
            name=names.get(action.text())
            if name:
                pix=QPixmap(24,24);pix.fill(Qt.GlobalColor.transparent);renderer=QSvgRenderer(QByteArray(svg_icon(name,'#cccccc').encode()));painter=QPainter(pix);renderer.render(painter);painter.end();action.setIcon(QIcon(pix))
        self.setStyleSheet(self.styleSheet()+'''QMainWindow,QTabWidget::pane,QWidget#chrome,QWidget#titleBar{background:#080808}QToolBar{background:#111111;border-bottom:1px solid #242424}QLineEdit{background:#191919;color:#e5e5e5;border:1px solid #333}QToolButton:hover{background:#292929}QMenu{background:#171717;color:#ddd;border:1px solid #333}QMenu::item:selected{background:#303030}''')
        from ui import neutral_style,monochrome
        from PySide6.QtWidgets import QToolButton
        for button in self.chrome.findChildren(QToolButton):button.setIcon(monochrome(button.icon(),24))
        for action in self.address.actions():action.setIcon(monochrome(action.icon(),20))
        self.setStyleSheet(neutral_style(self.styleSheet()))
        self.chrome.setStyleSheet('QToolButton{color:#ccc}');self.top_tabs.update()
    def home_markup(self):
        if self.private:
            from private_home import render_private
            return render_private()
        from design import render_home
        return render_home(self.data)
    def private_window(self,url=None,isolated=False):
        from main import Browser
        w=Browser(private=True,isolated=isolated);Features.windows.append(w);w.destroyed.connect(lambda:Features.windows.remove(w) if w in Features.windows else None);w.showFullScreen() if w.data['preferences'].get('start_fullscreen',True) else w.show()
        if isinstance(url,QUrl):w.navigate(url)
        return w
    def local_event(self,view,message):
        # RAM only, domain only. Private windows never write protection events.
        self.events.insert(0,(host_of(view.url().toString()) if view else '',message,time.strftime('%H:%M')));self.events=self.events[:100]
    def permit_navigation(self,url,view=None):
        value=url.toString();reason=suspicious(value)
        if reason and host_of(value) not in self.trusted_once:
            self.local_event(view,reason)
            if NovaMessage.question(self,'Vérifiez cette adresse',reason+'\n\nContinuer vers ce domaine ?')!=NovaMessage.StandardButton.Yes:return False
            self.trusted_once.add(host_of(value))
        return True
    def copy_link(self,url):
        if sensitive_link(url):
            if NovaMessage.question(self,'Lien sensible','Ce lien contient un paramètre de connexion ou de réinitialisation. Le partager peut donner accès à votre compte.\n\nCopier une version sans ces paramètres ?')==NovaMessage.StandardButton.Yes:url=without_sensitive(url)
            else:return
        QApplication.clipboard().setText(url)
    def allow_download(self,name,source=''):
        destination=host_of(source);current=host_of(self.current().url().toString())
        if destination and current and destination!=current:
            self.local_event(self.current(),'Téléchargement redirigé vers '+destination);self.updater.notify('Destination du téléchargement',current+' → '+destination)
        warning=download_warning(name)
        if warning and NovaMessage.question(self,'Vérifier le téléchargement',name+'\n'+warning+'\nSource : '+host_of(source)+'\n\nEnregistrer quand même ?')!=NovaMessage.StandardButton.Yes:return False
        return True
    def translate_french(self,selection=''):
        url=self.current().url().toString()
        if self.private and NovaMessage.question(self,'Traduire en français','La traduction envoie le texte ou l’adresse de la page à Google Traduction. Continuer ?')!=NovaMessage.StandardButton.Yes:return
        if not selection and sensitive_link(url):
            if NovaMessage.question(self,'Adresse sensible','Cette adresse contient un paramètre de connexion. Traduire une version sans ce paramètre ?')!=NovaMessage.StandardButton.Yes:return
            url=without_sensitive(url)
        if selection:target='https://translate.google.com/?sl=auto&tl=fr&text='+quote(selection[:12000])+'&op=translate'
        elif url.startswith(('http://','https://')):target='https://translate.google.com/translate?sl=auto&tl=fr&u='+quote(url,safe='')
        else:return
        self.new_tab(QUrl(target))
    def toggle_mute(self,view=None):
        if isinstance(view,bool) or view is None:view=self.current()
        muted=not getattr(view,'_muted',False);view._muted=muted
        if isinstance(view,MediaView):view.send('mute','on' if muted else 'off')
        elif isinstance(view,QWebEngineView):view.page().setAudioMuted(muted)
        self.top_tabs.update()
    def toggle_pin(self,view):
        view._pinned=not getattr(view,'_pinned',False)
        companion=getattr(view,'previous_view',None) or getattr(view,'forward_media',None)
        if companion is not None:companion._pinned=view._pinned
        index=self.tabs.indexOf(view)
        self.top_tabs.moveTab(index,0 if view._pinned else self.top_tabs.count()-1);self.top_tabs.updateGeometry();self.top_tabs.update();self.save_session()
    def tab_menu(self,point):
        index=self.top_tabs.tabAt(point)
        if index<0:return
        view=self.top_tabs.tabData(index);menu=QMenu(self)
        menu.addAction('Désépingler' if getattr(view,'_pinned',False) else 'Épingler cet onglet',lambda:self.toggle_pin(view))
        menu.addAction('Réactiver le son' if getattr(view,'_muted',False) else 'Couper le son',lambda:self.toggle_mute(view))
        menu.addAction('Mettre en veille',lambda:self.pause_view(view))
        menu.addSeparator();menu.addAction('Fermer',lambda:self.close_tab(self.tabs.indexOf(view)));menu.exec(self.top_tabs.mapToGlobal(point))
    def toggle_focus(self):
        self.focus_mode=not self.focus_mode;self.bar.setVisible(not self.focus_mode)
        if self.focus_mode:self.updater.notify('Mode concentration','Ctrl + Maj + F pour retrouver la barre de navigation.')
    def toggle_presentation(self):
        self.presentation=not self.presentation
        if self.presentation:
            self.address_suggestions.completer.popup().hide();self.address_suggestions.completer.popup().setEnabled(False)
            for i in range(self.top_tabs.count()):self.top_tabs.setTabText(i,'Onglet '+str(i+1));self.top_tabs.setTabIcon(i,QIcon());self.top_tabs.setTabToolTip(i,'')
            self.address.clear();self.profile_action.setVisible(False);self.updater.notify('Mode présentation','Les titres, suggestions et l’adresse sont masqués. Ctrl + Maj + P pour revenir.')
        else:
            self.address_suggestions.completer.popup().setEnabled(True);self.profile_action.setVisible(not self.private)
            for i in range(self.tabs.count()):self.title(self.tabs.widget(i),self.tabs.widget(i).title())
            self.sync(force=True)
        self.top_tabs.update()
    def notes(self):
        d=NovaDialog(self,'Bloc-notes','Notes locales'+(' · effacées à la fermeture de la fenêtre privée' if self.private else ' · enregistrées sur cet appareil'))
        d.setMinimumWidth(470);edit=QPlainTextEdit();edit.setMinimumHeight(260);edit.setStyleSheet('background:#141414;color:#ddd;border:1px solid #333;border-radius:8px;padding:12px');edit.setPlainText(self.data.get('notes',''));d.body.addWidget(edit)
        timer=QTimer(d);timer.setSingleShot(True);timer.setInterval(400)
        def save():self.data['notes']=edit.toPlainText()[:100000];self.save()
        timer.timeout.connect(save);edit.textChanged.connect(lambda:timer.start());d.finished.connect(lambda *args:save());d.buttons('Fermer','Annuler');d.exec()
    def capture_page(self):
        view=self.current();d=NovaDialog(self,'Capturer la page','Choisissez la zone et le format.');mode=[]
        for title,key in [('Page visible · PNG','visible'),('Sélectionner une zone · PNG','region'),('Page complète · PDF','pdf')]:
            b=QPushButton(title);b.clicked.connect(lambda checked=False,k=key:(mode.append(k),d.accept()));d.body.addWidget(b,0,Qt.AlignmentFlag.AlignLeft)
        if d.exec()!=d.DialogCode.Accepted or not mode:return
        kind=mode[0];extension='pdf' if kind=='pdf' else 'png';path,_=QFileDialog.getSaveFileName(self,'Enregistrer la capture',str(Path.home()/'Pictures'/('Nova-capture.'+extension)),('Document PDF (*.pdf)' if kind=='pdf' else 'Image PNG (*.png)'))
        if not path:return
        if isinstance(view,MediaView):
            view._capture_target=(path,kind)
            view.send('capture',json.dumps({'path':path,'mode':kind}));return
        if kind=='pdf' and isinstance(view,QWebEngineView):view.page().printToPdf(path)
        else:self.save_capture(view.grab(),path,kind,view)
    def save_capture(self,pixmap,path,mode,view):
        if mode=='region':
            from capture import RegionCapture
            d=RegionCapture(self,pixmap);d.move(view.mapToGlobal(view.rect().topLeft()))
            if d.exec()!=d.DialogCode.Accepted:return
            pixmap=d.result_pixmap
        if not pixmap.save(path,'PNG'):NovaMessage.information(self,'Capture','Impossible d’enregistrer cette capture.')
    def native_security(self,view,data):
        kind=data.get('type')
        if kind=='dirty':view._dirty=bool(data.get('value'))
        elif kind=='capture-state':self.protection_message(view,dict(data,type='nova-capture-state'))
        elif kind=='translate':self.translate_french(str(data.get('value','')))
        elif kind=='copy-link':self.copy_link(str(data.get('value','')))
        elif kind=='permission':
            ident=str(data.get('id',''));origin=str(data.get('origin',''));permission=str(data.get('kind',''))
            self.ask_permission(view,origin,permission,lambda yes:view.send('permission-result',json.dumps({'id':ident,'allow':yes})))
        elif kind=='security':
            self.local_event(view,str(data.get('message',''))[:300])
            if data.get('action')=='navigate':
                url=QUrl(str(data.get('url','')))
                if self.permit_navigation(url,view):view.send('navigate',url.toString())
            elif data.get('action')=='http':self.http_failure(view,str(data.get('url','')))
        elif kind=='download-request':
            ident=str(data.get('id',''));name=Path(str(data.get('name','download'))).name
            if not self.allow_download(name,str(data.get('url',''))):view.send('download-answer',json.dumps({'id':ident,'path':''}));return
            path,_=QFileDialog.getSaveFileName(self,'Enregistrer le téléchargement',str(Path.home()/'Downloads'/name))
            view.send('download-answer',json.dumps({'id':ident,'path':path}))
            if path:
                from downloads import NativeDownload
                item=NativeDownload(view,ident,path);view._downloads=getattr(view,'_downloads',{});view._downloads[ident]=item;self.download_panel.add(item,path);self.downloads_menu()
        elif kind=='download-state':
            item=getattr(view,'_downloads',{}).get(str(data.get('id','')))
            if item:item.update(data)
        elif kind=='screenshot':
            if data.get('ok') and data.get('mode')=='region':
                path=str(data.get('path',''));self.save_capture(QPixmap(path),path,'region',view)
            else:self.updater.notify('Capture enregistrée' if data.get('ok') else 'Capture impossible',str(data.get('path','')))
    def http_failure(self,view,url):
        if not url.startswith('https://') or host_of(url) in self.http_exceptions:return
        def retry():
            if NovaMessage.question(self,'Connexion non chiffrée','La connexion HTTPS a échoué. Continuer en HTTP exposera les données échangées avec ce site.\n\nContinuer cette fois ?')==NovaMessage.StandardButton.Yes:
                self.http_exceptions.add(host_of(url));
                if isinstance(view,MediaView):view.send('allow-http',host_of(url))
                view.setUrl(QUrl('http://'+url[len('https://'):]))
        self.updater.notify('HTTPS indisponible',host_of(url)+' · Nova ne revient pas automatiquement en HTTP.',retry,action_text='Voir les options',symbol='shield')
    def popup_request(self,view,request):
        now=time.monotonic()
        if not request.isUserInitiated() or now-getattr(view,'_last_popup',0)<2:
            self.local_event(view,'Fenêtre publicitaire ou ouverture répétée bloquée');return
        view._last_popup=now
        if self.permit_navigation(request.requestedUrl(),view):
            child=self.new_tab();child._popup=True;request.openIn(child.page())
            def close_popup():
                child._dirty=False;self.close_tab(self.tabs.indexOf(child))
            child.page().windowCloseRequested.connect(close_popup)
    def view_script(self,view,script):
        if isinstance(view,MediaView):view.send('script',script)
        elif isinstance(view,QWebEngineView):self.run_media_script(view,script)
    def revoke_site(self,view,emergency=False):
        parsed=urlsplit(view.url().toString());origin=parsed.scheme+'://'+parsed.netloc
        self.grants={k:v for k,v in self.grants.items() if k[0]!=origin}
        for p in self.profile.listPermissionsForOrigin(QUrl(origin)):p.reset()
        self.view_script(view,'window.__novaStopCapture?.()')
        if isinstance(view,MediaView):view.send('revoke')
        if emergency:
            self.view_script(view,'window.__novaEmergency?.()');view._muted=True
            if isinstance(view,MediaView):view.send('emergency')
            elif isinstance(view,QWebEngineView):view.page().setAudioMuted(True);view.stop();view.setUrl(QUrl('about:blank'))
        view._capture_audio=False;view._capture_video=False;self.capture_indicator.hide();self.local_event(view,'Accès caméra et micro retirés'+(' · arrêt de la page' if emergency else ''))
    def ask_permission(self,view,origin,kind,deliver):
        if kind in ('ClipboardReadWrite','ClipboardRead'):
            self.local_event(view,'Lecture automatique du presse-papiers bloquée');deliver(False);return
        parsed=urlsplit(origin);origin=parsed.scheme+'://'+parsed.netloc
        key=(origin,kind);grant=self.grants.get(key)
        if grant and grant[0]>time.monotonic() and grant[1] is view:deliver(True);return
        label={'AudioCapture':'Microphone','MediaAudioCapture':'Microphone','VideoCapture':'Caméra','MediaVideoCapture':'Caméra','MediaAudioVideoCapture':'Caméra et microphone','Geolocation':'Position','Notifications':'Notifications'}.get(kind,kind)
        d=NovaDialog(self,'Autorisation du site',origin+'\n'+label+'\nAccès limité à cet onglet et à la durée choisie.');row=QHBoxLayout()
        def allow(seconds):
            if self.tabs.indexOf(view)<0 or urlsplit(view.url().toString()).netloc!=parsed.netloc or view.url().scheme()!=parsed.scheme:d.reject();return
            self.grants[key]=(time.monotonic()+seconds,view);deliver(True);d.accept()
        for text,seconds in [('Cette fois',300),('10 minutes',600)]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,s=seconds:allow(s));row.addWidget(b)
        no=QPushButton('Bloquer');no.clicked.connect(d.reject);row.addWidget(no);d.body.addLayout(row)
        if d.exec()!=d.DialogCode.Accepted:deliver(False)
    def expire_permissions(self):
        Features.cleanup_jobs[:]=[p for p in Features.cleanup_jobs if p.poll() is None]
        now=time.monotonic();views={v for expiry,v in self.grants.values() if expiry<=now}
        for view in views:
            try:self.revoke_site(view)
            except RuntimeError:pass
    def protection_message(self,view,data):
        kind=data.get('type')
        if kind=='nova-dirty':view._dirty=bool(data.get('value'))
        elif kind=='nova-capture-state':
            view._capture_audio=bool(data.get('audio'));view._capture_video=bool(data.get('video'));self.update_capture_indicator()
    def update_capture_indicator(self):
        active=[v for v in (self.tabs.widget(i) for i in range(self.tabs.count())) if getattr(v,'_capture_audio',False) or getattr(v,'_capture_video',False)]
        self.capture_indicator.setText('● Micro / caméra · '+', '.join(host_of(v.url().toString()) for v in active)[:70]);self.capture_indicator.setVisible(bool(active))
    def confirm_close(self,view):
        return not getattr(view,'_dirty',False) or NovaMessage.question(self,'Texte non envoyé','Cet onglet contient du texte saisi dans un formulaire. Fermer et perdre cette saisie ?')==NovaMessage.StandardButton.Yes
    def build_site_panel(self):
        from PySide6.QtWidgets import QFrame
        from main import icon
        view=self.current();url=view.url().toString();host=host_of(url)
        d=QFrame(self,Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint);d.setFixedWidth(350);d.setStyleSheet('QFrame{background:#15131a;border:1px solid #35313d;border-radius:12px}QLabel{color:#b8b3c1;border:0;background:transparent;font-size:12px}QPushButton{background:transparent;border:0;border-radius:7px;color:#e1dce7;text-align:left;padding:10px 9px;font-size:12px}QPushButton:hover{background:#28232f}')
        from ui import neutral_style
        if self.private:d.setStyleSheet(neutral_style(d.styleSheet()))
        layout=QVBoxLayout(d);layout.setContentsMargins(17,16,17,14);layout.setSpacing(4);heading=QLabel('Protection du site');heading.setStyleSheet('font-size:17px;font-weight:600;color:#eee;border:0');layout.addWidget(heading);domain=QLabel(host or 'Page Nova');domain.setTextFormat(Qt.TextFormat.PlainText);domain.setWordWrap(True);layout.addWidget(domain);layout.addSpacing(10)
        status=QLabel('✓ Connexion HTTPS' if url.startswith('https://') else 'Page locale' if not host else 'Connexion HTTP non chiffrée');layout.addWidget(status);layout.addSpacing(10)
        reason=suspicious(url)
        if reason:
            warning=QLabel(reason);warning.setWordWrap(True);layout.addWidget(warning)
        def action(title,symbol,cb):
            b=QPushButton(title);b.setCursor(Qt.CursorShape.ArrowCursor);b.setIcon(icon(symbol,18));b.setIconSize(QSize(17,17));b.clicked.connect(lambda:(d.close(),cb()));layout.addWidget(b)
        action('Autorisations temporaires','shield',lambda:self.permissions_panel(view))
        capture='Caméra et micro · En cours' if getattr(view,'_capture_audio',False) or getattr(view,'_capture_video',False) else 'Caméra et micro · Inactifs'
        action(capture,'video',lambda:self.revoke_site(view))
        action('Effacer les données du site','close',lambda:self.clear_site(view))
        action('Ouvrir en session isolée','plus',lambda:self.private_window(QUrl(url),True))
        action('Journal de protection','shield',self.protection_log);layout.addSpacing(5)
        action('Arrêter l’activité du site','close',lambda:self.revoke_site(view,True));d.adjustSize();return d
    def site_panel(self):
        self.site_popup=self.build_site_panel();anchor=self.bar.widgetForAction(next(a for a in self.bar.actions() if a.text()=='Protection de ce site'));self.site_popup.move(anchor.mapToGlobal(anchor.rect().bottomLeft()));self.site_popup.show()
    def permissions_panel(self,view):
        host=host_of(view.url().toString());d=NovaDialog(self,'Autorisations',host);now=time.monotonic()
        for (origin,kind),(expiry,owner) in self.grants.items():
            if host_of(origin)==host and owner is view:d.body.addWidget(QLabel(kind+' · '+str(max(0,int((expiry-now)/60)))+' min restantes'))
        b=QPushButton('Retirer tous les accès temporaires');b.clicked.connect(lambda:(self.revoke_site(view),d.accept()));d.body.addWidget(b);d.buttons('Fermer','Annuler');d.exec()
    def clear_site(self,view):
        url=view.url().toString();host=host_of(url)
        if not host or NovaMessage.question(self,'Effacer les données de ce site',host+'\nCookies, stockage local et connexions de ce site seront supprimés. Continuer ?')!=NovaMessage.StandardButton.Yes:return
        self.revoke_site(view)
        if isinstance(view,MediaView):view.send('clear-site')
        else:
            store=self.profile.cookieStore()
            def cookie(item):
                domain=item.domain().lstrip('.')
                if host==domain or host.endswith('.'+domain):store.deleteCookie(item)
            store.cookieAdded.connect(cookie);store.loadAllCookies();QTimer.singleShot(2000,lambda:store.cookieAdded.disconnect(cookie))
            self.view_script(view,"(()=>{localStorage.clear();sessionStorage.clear();caches.keys().then(k=>Promise.all(k.map(x=>caches.delete(x))));indexedDB.databases?.().then(d=>d.forEach(x=>indexedDB.deleteDatabase(x.name)));navigator.serviceWorker?.getRegistrations().then(r=>r.forEach(x=>x.unregister()));})()")
        self.local_event(view,'Données du site effacées');self.updater.notify('Données du site effacées',host+' · rechargez la page pour repartir.')
    def protection_log(self):
        d=NovaDialog(self,'Journal de protection','Événements de cette fenêtre · mémoire uniquement');edit=QPlainTextEdit();edit.setReadOnly(True);edit.setPlainText('\n\n'.join(t+' · '+host+'\n'+message for host,message,t in self.events) or 'Aucun événement.');edit.setMinimumSize(460,280);d.body.addWidget(edit);d.buttons('Fermer','Annuler');d.exec()
    def resource_panel(self):
        d=NovaDialog(self,'Activité des onglets','État des onglets et mémoire du processus de rendu.');d.setMinimumWidth(620);table=QTableWidget(self.tabs.count(),4);table.setHorizontalHeaderLabels(['Onglet','État','Mémoire','Action']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);table.setMinimumHeight(280)
        from resources import renderer_memory
        memory=renderer_memory(self)
        for j in range(self.tabs.count()):
            candidate=self.tabs.widget(j)
            if isinstance(candidate,MediaView):candidate.send('resources')
        for i in range(self.tabs.count()):
            v=self.tabs.widget(i);table.setItem(i,0,QTableWidgetItem(v.title()[:50]));table.setItem(i,1,QTableWidgetItem('En veille' if getattr(v,'_nova_suspended',False) else 'Actif'));pid=v.page().renderProcessPid() if isinstance(v,QWebEngineView) else v.process.processId() if isinstance(v,MediaView) else 0;value=getattr(v,'_renderer_memory',0) if isinstance(v,MediaView) else memory.get(pid);table.setItem(i,2,QTableWidgetItem(f'{value/1048576:.0f} Mio' if value else '—'));button=QPushButton('Mettre en veille');button.clicked.connect(lambda checked=False,view=v:self.pause_view(view));table.setCellWidget(i,3,button)
        def refresh_native():
            if not d.isVisible():return
            for j in range(min(table.rowCount(),self.tabs.count())):
                candidate=self.tabs.widget(j)
                if isinstance(candidate,MediaView) and getattr(candidate,'_renderer_memory',0):table.setItem(j,2,QTableWidgetItem(f'{candidate._renderer_memory/1048576:.0f} Mio'))
        QTimer.singleShot(700,refresh_native)
        d.body.addWidget(table);d.body.addWidget(QLabel('Les processus peuvent être partagés entre onglets. La mémoire n’est pas additionnable.'));d.buttons('Fermer','Annuler');d.exec()
    def show_tab_preview(self):
        i=self.hover_index
        if self.presentation or not 0<=i<self.tabs.count() or i==self.tabs.currentIndex():return
        view=self.top_tabs.tabData(i);p=QLabel(self,Qt.WindowType.ToolTip);p.setStyleSheet('background:#171717;color:#ddd;border:1px solid #333;border-radius:10px;padding:12px;font-size:12px');p.setTextFormat(Qt.TextFormat.PlainText)
        preview=getattr(view,'_preview',None)
        if preview is not None and not preview.isNull():p.setPixmap(preview);p.setToolTip(view.title())
        else:p.setText(view.title()[:90]+'\n'+host_of(view.url().toString()))
        p.move(self.top_tabs.mapToGlobal(self.top_tabs.tabRect(i).bottomLeft()));p.show();self.preview_popup=p
    def eventFilter(self,obj,event):
        if obj is getattr(self,'top_tabs',None):
            if event.type()==QEvent.Type.MouseMove:
                index=obj.tabAt(event.position().toPoint())
                if index!=self.hover_index:
                    self.hover_index=index;self.preview_timer.start()
                    if self.preview_popup:self.preview_popup.close();self.preview_popup=None
            elif event.type() in (QEvent.Type.Leave,QEvent.Type.MouseButtonPress):
                self.preview_timer.stop()
                if self.preview_popup:self.preview_popup.close();self.preview_popup=None
        return super().eventFilter(obj,event)
