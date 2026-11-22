import json
from datetime import datetime
from PySide6.QtCore import Qt,QUrl,QByteArray,Signal,QTimer,QSize,QRectF
from PySide6.QtGui import QPainter,QColor,QFont,QPixmap
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QLineEdit,QVBoxLayout,QHBoxLayout,
    QGridLayout,QListWidget,QListWidgetItem,QStackedWidget,QScrollArea,QCheckBox,QComboBox)
from ui import generated_icon,ASSETS,NovaMessage
from version import VERSION

PAGE_STYLE='''QWidget#novaPage{background:#050408;color:#eee8f6}QFrame#sidebar{background:#08060e;border-right:1px solid #2b183b}QFrame#card{background:#100c18;border:1px solid #2c1d3d;border-radius:18px}QLabel{color:#bbadcb;background:transparent;font-size:13px}QLabel#pageTitle{font-size:27px;color:#faf4ff;font-weight:600}QLabel#cardTitle{font-size:18px;color:#f0e7fb;font-weight:600}QLabel#brand{font-size:16px;color:#f3eaff;font-weight:600}QPushButton{background:#201030;border:1px solid #44205f;border-radius:11px;color:#e3d0fa;padding:11px 17px;font-size:13px}QPushButton:hover{background:#301647;border-color:#8651b6}QPushButton#primary{background:#8225df;border:0;color:white}QPushButton#theme{background:#09050f;border:1px solid #3d2257;min-height:50px}QPushButton#theme:checked{border:2px solid #a256ff;background:#241039}QLineEdit,QComboBox{background:#08050d;color:#eee4fa;border:1px solid #342046;border-radius:12px;padding:11px;font-size:13px}QLineEdit:focus{border-color:#a050ef}QListWidget{background:transparent;border:0;outline:0;color:#bdb0d0;font-size:14px}QListWidget::item{padding:13px 12px;margin:3px 0;border-radius:13px}QListWidget::item:selected{background:#291343;color:white;border:1px solid #8546dc}QListWidget::item:hover:!selected{background:#15101e}QScrollArea{background:transparent;border:0}QScrollBar:vertical{width:7px;background:transparent;margin:4px}QScrollBar::handle:vertical{background:#3a2551;border-radius:3px;min-height:40px}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}QCheckBox{color:#d9cce8;font-size:13px;spacing:12px}QCheckBox::indicator{width:38px;height:20px;border-radius:10px;background:#342c43;border:0}QCheckBox::indicator:checked{background:#8b2af4;border:1px solid #b281ff}QCheckBox::indicator:unchecked{background:#302a3b;border:1px solid #4a405b}'''

def text(value,style=None):
    label=QLabel(value);label.setWordWrap(True)
    if style:label.setObjectName(style)
    return label

def card(title,subtitle=''):
    frame=QFrame();frame.setObjectName('card');layout=QVBoxLayout(frame);layout.setContentsMargins(20,18,20,18);layout.setSpacing(12)
    layout.addWidget(text(title,'cardTitle'))
    if subtitle:layout.addWidget(text(subtitle))
    return frame,layout

def action(layout,label,callback,primary=False):
    button=QPushButton(label)
    if primary:button.setObjectName('primary')
    button.setMaximumWidth(420)
    button.clicked.connect(callback);layout.addWidget(button,0,Qt.AlignmentFlag.AlignLeft);return button

def setting_action(layout,title,description,button_text,callback,primary=False):
    row=QHBoxLayout();row.setSpacing(24)
    labels=QVBoxLayout();labels.setSpacing(5);labels.addWidget(text(title,'rowTitle'));labels.addWidget(text(description));row.addLayout(labels,1)
    button=QPushButton(button_text);button.setMinimumWidth(130);button.setMaximumWidth(220)
    if primary:button.setObjectName('primary')
    button.clicked.connect(callback);row.addWidget(button,0,Qt.AlignmentFlag.AlignVCenter)
    layout.addLayout(row);return button

class InternalPage(QWidget):
    def __init__(self,path,title,browser):
        super().__init__();self.path=path;self._title=title;self.browser=browser;self.setObjectName('novaPage');self.setStyleSheet(PAGE_STYLE+'''QLabel{font-size:12px}QLabel#pageTitle{font-size:24px}QLabel#cardTitle{font-size:16px}QPushButton{padding:8px 14px;font-size:12px;border-radius:9px}QLineEdit,QComboBox{padding:9px 12px;font-size:12px}QListWidget::item{padding:6px 10px;margin:2px 0;border-radius:10px}''')
    def url(self):return QUrl('nova://'+self.path)
    def title(self):return self._title
    def back(self):self.browser.home()
    def forward(self):pass
    def reload(self):pass

class Toggle(QCheckBox):
    def sizeHint(self):return QSize(340,32)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setFont(QFont('Segoe UI',10));painter.setPen(QColor('#cfc4dc'))
        painter.drawText(self.rect().adjusted(0,0,-58,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,self.text())
        x=self.width()-40;y=(self.height()-20)/2
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#8c2be7' if self.isChecked() else '#302a3b'));painter.drawRoundedRect(QRectF(x,y,38,20),10,10)
        painter.setBrush(QColor('#f3eaff' if self.isChecked() else '#a39bb4'));painter.drawEllipse(QRectF(x+(20 if self.isChecked() else 3),y+3,14,14))
    def hitButton(self,pos):return self.rect().contains(pos)

class SyncClient(QWidget):
    statusChanged=Signal(str)
    signedIn=Signal(str)
    changed=Signal()
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.network=QNetworkAccessManager(self);self.token='';self.email='';self.endpoint='';self.revision=0;self.busy=False;self.remote_tabs=[]
        self.timer=QTimer(self);self.timer.setInterval(120000);self.timer.timeout.connect(self.synchronize)
    def request(self,path,payload,callback):
        if self.busy:self.statusChanged.emit('Une opération est déjà en cours.');return
        url=QUrl(self.endpoint)
        if url.userName() or url.password() or url.hasQuery() or url.hasFragment() or (url.scheme()!='https' and not (url.scheme()=='http' and url.host() in ('127.0.0.1','localhost','::1'))):
            self.statusChanged.emit('Adresse du serveur invalide. Utilisez HTTPS, ou HTTP sur localhost pour un essai.');return
        self.busy=True
        req=QNetworkRequest(QUrl(self.endpoint.rstrip('/')+path));req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json');req.setTransferTimeout(20000)
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        if self.token:req.setRawHeader(b'Authorization',('Bearer '+self.token).encode())
        reply=self.network.get(req) if payload is None else self.network.post(req,QByteArray(json.dumps(payload).encode()))
        def done():
            self.busy=False
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:data=json.loads(bytes(reply.readAll()).decode())
            except (ValueError,UnicodeError):data={}
            if not status or not 200<=int(status)<300:
                self.statusChanged.emit(data.get('error') or 'Connexion impossible. Vérifiez le serveur et son certificat HTTPS.')
            else:callback(data)
            reply.deleteLater()
        reply.finished.connect(done)
    def login(self,endpoint,email,password,register=False):
        self.endpoint=endpoint.strip().rstrip('/');self.statusChanged.emit('Création du compte…' if register else 'Connexion…')
        def accepted(data):
            self.token=data['token'];self.email=data['email'];self.browser.data['sync_endpoint']=self.endpoint;self.browser.save()
            self.signedIn.emit(self.email);self.statusChanged.emit('Connecté. Prêt à synchroniser.');self.timer.start();self.synchronize()
        self.request('/v1/register' if register else '/v1/login',{'email':email,'password':password},accepted)
    def synchronize(self):
        if not self.token:self.statusChanged.emit('Connectez-vous d’abord à votre compte Nova.');return
        if self.busy:return
        self.statusChanged.emit('Synchronisation en cours…')
        def pulled(response):
            remote=response.get('data',{});self.revision=response.get('revision',0)
            local=self.browser.sync_snapshot()
            merged={}
            for key,maximum in [('bookmarks',2000),('history',300),('shortcuts',100)]:
                items=[];seen=set()
                for entry in local.get(key,[])+remote.get(key,[]):
                    if not isinstance(entry,dict):continue
                    url=entry.get('url','')
                    if not isinstance(url,str) or not url.startswith(('https://','http://')) or url in seen:continue
                    seen.add(url);items.append({'url':url,'title':str(entry.get('title',''))[:250]})
                merged[key]=items[:maximum]
            hidden=list(set(local.get('hidden_shortcuts',[]))|set(remote.get('hidden_shortcuts',[])))
            merged['hidden_shortcuts']=hidden
            merged['shortcuts']=[entry for entry in merged['shortcuts'] if entry['url'] not in hidden]
            merged['tabs']=local['tabs']
            use_remote=not self.browser.data.get('last_sync') and response.get('revision',0)>0
            merged['preferences']={**local['preferences'],**remote.get('preferences',{})} if use_remote else local['preferences']
            self.remote_tabs=remote.get('tabs',[])
            def pushed(result):
                self.revision=result['revision']
                for key in ('bookmarks','history','shortcuts'):self.browser.data[key]=merged[key]
                self.browser.data['hidden_shortcuts']=hidden
                self.browser.data['preferences'].update({k:v for k,v in merged['preferences'].items() if k!='profileName'})
                self.browser.apply_theme();self.browser.update_tab_style();self.browser.apply_web_preferences()
                self.browser.data['last_sync']=datetime.now().isoformat(timespec='seconds');self.browser.save();self.browser.refresh_home_tabs()
                self.changed.emit();self.statusChanged.emit('Synchronisé à '+datetime.now().strftime('%H:%M')+' · favoris, historique, raccourcis et onglets.');
            self.request('/v1/snapshot',{'revision':self.revision,'data':merged},pushed)
        self.request('/v1/snapshot',None,pulled)
    def logout(self):
        def done(data):self.token='';self.email='';self.timer.stop();self.signedIn.emit('');self.statusChanged.emit('Déconnecté. Les données locales restent disponibles.')
        if self.token:self.request('/v1/logout',{},done)
    def restore_tabs(self):
        for entry in self.remote_tabs[:30]:
            url=QUrl(entry.get('url',''))
            if url.scheme() in ('http','https'):self.browser.new_tab(url)
        self.statusChanged.emit('Onglets de la dernière synchronisation restaurés.')

class AccountPage(InternalPage):
    def __init__(self,browser):
        super().__init__('account','Compte Nova',browser)
        outer=QVBoxLayout(self);outer.setContentsMargins(45,30,45,30);outer.setSpacing(18)
        outer.addWidget(text('Votre compte Nova','pageTitle'));outer.addWidget(text('Votre navigateur, vos données, sur vos appareils.'))
        row=QHBoxLayout();row.setSpacing(25)
        frame,form=card('Connexion et inscription','Connectez Nova à votre serveur de synchronisation auto-hébergé.');row.addWidget(frame,1)
        self.endpoint=QLineEdit(browser.data.get('sync_endpoint',''));self.endpoint.setPlaceholderText('https://sync.votre-domaine.fr')
        self.email=QLineEdit();self.email.setPlaceholderText('vous@exemple.fr')
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setPlaceholderText('12 caractères minimum')
        self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.EchoMode.Password);self.confirm.setPlaceholderText('Confirmer le mot de passe pour créer un compte')
        for title,widget in [('Serveur Nova Sync',self.endpoint),('Adresse e-mail',self.email),('Mot de passe',self.password),('Confirmation pour une inscription',self.confirm)]:form.addWidget(text(title));form.addWidget(widget)
        buttons=QHBoxLayout();action(buttons,'Se connecter',lambda:self.authenticate(False),True);action(buttons,'Créer un compte',lambda:self.authenticate(True));form.addLayout(buttons)
        form.addWidget(text('Aucun serveur n’est configuré par défaut. Le dossier NovaSync-server contient le serveur et les instructions d’hébergement.'))
        frame,right=card('Synchronisation','Favoris · historique · raccourcis · onglets');row.addWidget(frame,1)
        self.identity=text('Non connecté','cardTitle');right.addWidget(self.identity)
        self.status=text('Choisissez un serveur puis créez votre compte.');right.addWidget(self.status)
        action(right,'Synchroniser maintenant',browser.sync_client.synchronize,True)
        action(right,'Restaurer les onglets de l’autre appareil',browser.sync_client.restore_tabs)
        action(right,'Se déconnecter',browser.sync_client.logout)
        right.addWidget(text('Synchronisation automatique toutes les 2 minutes après connexion. Les mots de passe de sites et les cookies Google restent sur cet ordinateur. Le serveur peut lire les données synchronisées.'))
        right.addStretch();outer.addLayout(row);outer.addStretch()
        browser.sync_client.statusChanged.connect(self.status.setText);browser.sync_client.signedIn.connect(self.identity_changed)
        self.identity_changed(browser.sync_client.email)
    def identity_changed(self,email):self.identity.setText(email or 'Non connecté');self.password.clear();self.confirm.clear()
    def authenticate(self,register):
        if register and self.password.text()!=self.confirm.text():self.status.setText('Les deux mots de passe ne correspondent pas.');return
        if len(self.password.text())<12:self.status.setText('Utilisez un mot de passe d’au moins 12 caractères.');return
        self.browser.sync_client.login(self.endpoint.text(),self.email.text(),self.password.text(),register)

class SettingsPage(InternalPage):
    sections=[('Apparence','settings'),('Onglets','plus'),('Confidentialité et sécurité','vpn'),('VPN','vpn'),('Téléchargements','download'),('Extensions et publicités','extensions'),('Moteur de recherche','search'),('Optimiser le navigateur','video'),('Compte et synchronisation','profile'),('À propos','home')]
    def __init__(self,browser):
        super().__init__('settings','Paramètres',browser)
        root=QHBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(245);side=QVBoxLayout(sidebar);side.setContentsMargins(18,22,18,20)
        brand=QHBoxLayout();logo=QLabel();logo.setPixmap(browser.windowIcon().pixmap(52,52));brand.addWidget(logo);brand.addWidget(text('Nova Browser','brand'));side.addLayout(brand);side.addSpacing(20)
        self.nav=QListWidget();self.nav.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(23,23))
        for name,ico in self.sections:
            item=QListWidgetItem(generated_icon(ico,26),'Compte et synchro' if name=='Compte et synchronisation' else name);item.setToolTip(name);item.setSizeHint(QSize(200,40));self.nav.addItem(item)
        self.nav.setStyleSheet('QListWidget{padding:0;border:0;background:transparent}QListWidget::item{margin:3px 6px 3px 1px;padding:6px 9px;border:1px solid transparent;border-radius:10px}QListWidget::item:selected{background:#241337;border:1px solid #7340a3;color:#eee5f7}')
        side.addWidget(self.nav);side.addWidget(text('Nova · Version de développement'));root.addWidget(sidebar)
        content=QWidget();self.content=content;content.setFixedWidth(min(1120,max(0,browser.width()-245)));col=QVBoxLayout(content);col.setContentsMargins(30,26,30,25);col.setSpacing(20)
        header=QHBoxLayout();titles=QVBoxLayout();titleLabel=text('Paramètres','pageTitle');titleLabel.setMinimumWidth(260);titles.addWidget(titleLabel);titles.addWidget(text('Personnalisez votre navigateur.'));header.addLayout(titles);header.addStretch()
        search=QLineEdit();search.setPlaceholderText('Rechercher un réglage…');search.setMaximumWidth(290);search.setMinimumWidth(160);header.addWidget(search);col.addLayout(header)
        self.stack=QStackedWidget();col.addWidget(self.stack);root.addWidget(content);root.addStretch(1)
        for index,(name,_) in enumerate(self.sections):
            scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();body.setStyleSheet('background:transparent');layout=QVBoxLayout(body);layout.setContentsMargins(0,0,4,0);layout.setSpacing(22)
            self.build_section(index,layout);layout.addStretch();scroll.setWidget(body);self.stack.addWidget(scroll)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex);self.nav.setCurrentRow(0)
        search.textChanged.connect(lambda value:self.filter(value))
    def filter(self,value):
        first=None
        for i,(name,_) in enumerate(self.sections):
            matches=value.casefold() in name.casefold();self.nav.item(i).setHidden(not matches)
            if matches and first is None:first=i
        if first is not None:self.nav.setCurrentRow(first)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'content'):self.content.setFixedWidth(min(1120,max(0,self.width()-245)))
        if hasattr(self,'appearance_preview'):self.appearance_preview.setVisible(self.width()>=1050)
    def toggle(self,layout,label,key,default=False,callback=None):
        button=Toggle(label);button.setFixedHeight(33);button.setChecked(self.browser.data.get('preferences',{}).get(key,default));layout.addWidget(button)
        def changed(value):
            self.browser.data.setdefault('preferences',{})[key]=value;self.browser.save()
            if callback:callback(value)
        button.toggled.connect(changed);return button
    def build_section(self,index,layout):
        b=self.browser
        if index==0:
            frame,c=card('Apparence','Choisissez votre ambiance Nova.');layout.addWidget(frame)
            appearance=QHBoxLayout();appearance.setSpacing(28)
            preview=QLabel();self.appearance_preview=preview;preview.setFixedSize(290,155);pixmap=QPixmap(str(ASSETS/'home-preview.png'))
            if not pixmap.isNull():preview.setPixmap(pixmap.scaled(290,155,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            preview.setStyleSheet('background:#050308;border:1px solid #442060;border-radius:12px');appearance.addWidget(preview)
            controls=QVBoxLayout();controls.addWidget(text('Thème'));row=QHBoxLayout()
            for key,name in [('violet','Sombre violet'),('black','Noir profond')]:
                button=QPushButton(name);button.setObjectName('theme');button.setFixedSize(145,58);button.setCheckable(True);button.setAutoExclusive(True);button.setChecked(b.data.get('preferences',{}).get('theme','violet')==key);button.clicked.connect(lambda checked=False,t=key:b.set_theme(t));row.addWidget(button)
            row.addStretch();controls.addLayout(row);controls.addWidget(text('Couleur d’accent'))
            colors=QHBoxLayout()
            for color in ['#9338ff','#5264ff','#11b3ec','#e535a4','#f04469','#f29932','#20bd86']:
                btn=QPushButton();btn.setFixedSize(30,30);btn.setStyleSheet(f'background:{color};border-radius:15px;border:2px solid #281d38');btn.clicked.connect(lambda checked=False,v=color:b.set_accent(v));colors.addWidget(btn)
            colors.addStretch();controls.addLayout(colors);appearance.addLayout(controls,1);c.addLayout(appearance)
            frame,c=card('Onglets','Gérez votre espace de travail.');layout.addWidget(frame)
            self.toggle(c,'Afficher les icônes des onglets','tab_icons',True,b.update_tab_style)
            self.toggle(c,'Utiliser des onglets compacts','compact_tabs',False,b.update_tab_style)
            frame,c=card('Confidentialité et sécurité','Gardez le contrôle sur vos données.');layout.addWidget(frame)
            action(c,'Ouvrir les options de confidentialité',lambda:self.nav.setCurrentRow(2))
        elif index==1:
            frame,c=card('Onglets');layout.addWidget(frame)
            self.toggle(c,'Afficher les icônes des onglets','tab_icons',True,b.update_tab_style)
            self.toggle(c,'Onglets compacts','compact_tabs',False,b.update_tab_style)
            action(c,'Ouvrir un nouvel onglet',b.new_tab)
            action(c,'Mettre en veille les onglets classiques inactifs',b.sleep_tabs)
        elif index==2:
            frame,c=card('Confidentialité et sécurité','Les certificats HTTPS et la sandbox restent activés.');layout.addWidget(frame)
            self.toggle(c,'Activer uBlock Origin Lite dans le moteur vidéo','adblock',True,b.set_adblock)
            self.toggle(c,'Limiter les adresses réseau exposées par WebRTC (moteur classique)','webrtc_public',True,b.apply_web_preferences)
            frame,c=card('Données de navigation');layout.addWidget(frame)
            setting_action(c,'Historique et cache','Supprimer les pages visitées et les fichiers temporaires.','Effacer',b.clear)
            setting_action(c,'Cookies et connexions','Déconnecter les sites du profil classique.','Gérer les cookies',b.clear_cookies)
        elif index==3:
            frame,c=card('VPN','VPN non configuré');layout.addWidget(frame)
            iconlabel=QLabel();iconlabel.setPixmap(generated_icon('vpn',72).pixmap(72,72));c.addWidget(iconlabel)
            c.addWidget(text('Nova ne fournit pas encore de tunnel VPN. Un simple changement d’icône ne protège pas votre trafic. Vous pouvez utiliser le VPN Windows ou celui de votre fournisseur.'))
            action(c,'Ouvrir les paramètres VPN Windows',lambda:__import__('PySide6.QtGui',fromlist=['QDesktopServices']).QDesktopServices.openUrl(QUrl('ms-settings:network-vpn')))
        elif index==4:
            frame,c=card('Téléchargements','Choisissez l’emplacement pour chaque fichier.');layout.addWidget(frame);action(c,'Voir les téléchargements de cette session',b.downloads_menu)
            c.addWidget(text('Le lecteur vidéo utilise le gestionnaire de téléchargements du moteur Edge intégré.'))
        elif index==5:
            frame,c=card('Extensions et publicités','uBlock Origin Lite est intégré au moteur vidéo compatible.');layout.addWidget(frame)
            self.toggle(c,'Activer le bloqueur de publicités','adblock',True,b.set_adblock)
            action(c,'Ouvrir le bloqueur et ses réglages',b.open_blocker_settings)
            c.addWidget(text('Le filtrage est appliqué aux sites ouverts en mode compatible. Les publicités intégrées à certaines vidéos peuvent évoluer.'))
        elif index==6:
            frame,c=card('Moteur de recherche');layout.addWidget(frame);combo=QComboBox();combo.addItems(['Google','DuckDuckGo','Bing']);combo.setCurrentText(b.data.get('preferences',{}).get('search_engine','Google'));combo.currentTextChanged.connect(b.set_search_engine);c.addWidget(combo)
        elif index==7:
            frame,c=card('Optimiser le navigateur','Allégez les onglets et l’espace occupé, sans supprimer vos comptes.');layout.addWidget(frame)
            setting_action(c,'Optimisation rapide','Vider le cache et mettre en veille les onglets classiques inactifs.','Optimiser',b.optimize,True)
            setting_action(c,'Onglets inactifs','Réduire leur activité sans interrompre les lecteurs vidéo.','Mettre en veille',b.sleep_tabs)
            setting_action(c,'Fichiers temporaires','Conserver les favoris et les connexions.','Vider le cache',b.clear_cache)
            c.addWidget(text('La mise en veille concerne les onglets classiques : les pages peuvent se recharger à leur réactivation. Les lecteurs vidéo restent actifs pour préserver les directs. Le cache disque est plafonné à 256 Mio.'))
        elif index==8:
            frame,c=card('Compte et synchronisation','Retrouvez vos favoris, raccourcis et onglets sur vos appareils.');layout.addWidget(frame);action(c,'Ouvrir mon compte Nova',b.open_account,True);c.addWidget(text('Nécessite un serveur Nova Sync à héberger. Aucun serveur public n’est configuré par défaut.'))
        else:
            frame,c=card('Nova Browser '+VERSION,'Qt WebEngine + WebView2');layout.addWidget(frame)
            c.addWidget(text('Interface Nova, moteur vidéo compatible et uBlock Origin Lite. Version de développement non auditée.'))
            frame,c=card('Mises à jour','Les nouvelles versions sont distribuées depuis zyko144/Nova sur GitHub.');layout.addWidget(frame)
            self.update_status=text('Version installée : '+VERSION);c.addWidget(self.update_status)
            action(c,'Rechercher une mise à jour',lambda:b.updater.check(manual=True))
            action(c,'Voir la version disponible',lambda:b.updater.details())
            b.updater.statusChanged.connect(self.update_status.setText)
            c.addWidget(text('Vérification au démarrage, au retour dans Nova et toutes les 5 minutes. Notification dès qu’une nouvelle version est détectée.'))
