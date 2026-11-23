import json
from datetime import datetime
from PySide6.QtCore import Qt,QUrl,QByteArray,Signal,QTimer,QObject,QSize,QRectF,QBuffer,QIODevice
from PySide6.QtGui import QPainter,QColor,QFont,QPixmap,QImageReader,QPainterPath
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QLineEdit,QVBoxLayout,QHBoxLayout,
    QGridLayout,QListWidget,QListWidgetItem,QStackedWidget,QScrollArea,QCheckBox,QComboBox)
from ui import generated_icon,ASSETS,NovaMessage
from version import VERSION
from google_flow import GoogleFlow

PAGE_STYLE='''QWidget#novaPage{background:#050408;color:#eee8f6}QFrame#sidebar{background:#08060e;border-right:1px solid #2b183b}QFrame#card{background:#100c18;border:1px solid #2c1d3d;border-radius:18px}QLabel{color:#bbadcb;background:transparent;font-size:13px}QLabel#pageTitle{font-size:27px;color:#faf4ff;font-weight:600}QLabel#cardTitle{font-size:18px;color:#f0e7fb;font-weight:600}QLabel#brand{font-size:16px;color:#f3eaff;font-weight:600}QPushButton{background:#201030;border:1px solid #44205f;border-radius:11px;color:#e3d0fa;padding:11px 17px;font-size:13px}QPushButton:hover{background:#301647;border-color:#8651b6}QPushButton#primary{background:#8225df;border:0;color:white}QPushButton#theme{background:#09050f;border:1px solid #3d2257;min-height:50px}QPushButton#theme:checked{border:2px solid #a256ff;background:#241039}QLineEdit,QComboBox{background:#08050d;color:#eee4fa;border:1px solid #342046;border-radius:12px;padding:11px;font-size:13px}QLineEdit:focus{border-color:#a050ef}QListWidget{background:transparent;border:0;outline:0;color:#bdb0d0;font-size:14px}QListWidget::item{padding:13px 12px;margin:3px 0;border-radius:13px}QListWidget::item:selected{background:#291343;color:white;border:1px solid #8546dc}QListWidget::item:hover:!selected{background:#15101e}QScrollArea{background:transparent;border:0}QScrollBar:vertical{width:7px;background:transparent;margin:4px}QScrollBar::handle:vertical{background:#3a2551;border-radius:3px;min-height:40px}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}QCheckBox{color:#d9cce8;font-size:13px;spacing:12px}QCheckBox::indicator{width:38px;height:20px;border-radius:10px;background:#342c43;border:0}QCheckBox::indicator:checked{background:#8b2af4;border:1px solid #b281ff}QCheckBox::indicator:unchecked{background:#302a3b;border:1px solid #4a405b}'''

def text(value,style=None):
    label=QLabel(value);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
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

def section(layout,title,description=''):
    block=QWidget();content=QVBoxLayout(block);content.setContentsMargins(0,0,0,0);content.setSpacing(10)
    label=text(title,'sectionTitle');label.setStyleSheet('font-size:17px;font-weight:600;color:#e4e4e8;padding-top:4px');content.addWidget(label)
    if description:
        hint=text(description);hint.setStyleSheet('font-size:12px;color:#96969f');content.addWidget(hint)
    frame=QFrame();frame.setObjectName('settingGroup');rows=QVBoxLayout(frame);rows.setContentsMargins(0,0,0,0);rows.setSpacing(0);content.addWidget(frame);layout.addWidget(block);return rows

def preference_row(layout,title,description,control):
    control.setAccessibleName(title);control.setAccessibleDescription(description)
    row=QWidget();row.setObjectName('preferenceRow');h=QHBoxLayout(row);h.setContentsMargins(16,13,16,13);h.setSpacing(22);labels=QVBoxLayout();labels.setSpacing(4);name=text(title);name.setStyleSheet('color:#e1e1e6;font-size:13px;font-weight:500');labels.addWidget(name)
    if description:
        hint=text(description);hint.setStyleSheet('color:#9797a1;font-size:12px');labels.addWidget(hint)
    h.addLayout(labels,1);h.addWidget(control,0,Qt.AlignmentFlag.AlignVCenter);layout.addWidget(row);return row

def connect_owned(signal,callback,owner):
    connection=signal.connect(callback)
    def detach(*args):
        try:
            if connection:QObject.disconnect(connection)
        except (RuntimeError,TypeError):pass
    owner.destroyed.connect(detach)

def bind_preference(browser,control,key,default=False,callback=None):
    control.setProperty('preferenceKey',key);control.setChecked(browser.data['preferences'].get(key,default))
    def changed(value):
        browser.data['preferences'][key]=value;browser.save();browser.preferenceChanged.emit(key,value)
        if callback:callback(value)
    def refresh(name,value):
        if name==key:
            blocked=control.blockSignals(True);control.setChecked(bool(value));control.blockSignals(blocked)
    control.toggled.connect(changed);connect_owned(browser.preferenceChanged,refresh,control)
    if key=='ai_suggestions':
        def available(*args):
            allowed=not browser.private and browser.text_services_allowed();control.setEnabled(allowed);control.setToolTip('Toujours désactivé en navigation privée.' if browser.private else 'Désactivé par le réglage général de confidentialité.' if not allowed else '')
        connect_owned(browser.preferenceChanged,lambda name,value:available() if name=='text_services' else None,control);available()
    return control

class InternalPage(QWidget):
    def __init__(self,path,title,browser):
        super().__init__();self.path=path;self._title=title;self.browser=browser;self.setObjectName('novaPage');self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);self.setStyleSheet(PAGE_STYLE+'''QLabel{font-size:12px}QLabel#pageTitle{font-size:24px}QLabel#cardTitle{font-size:16px}QPushButton{padding:8px 14px;font-size:12px;border-radius:9px}QLineEdit,QComboBox{padding:9px 12px;font-size:12px}QListWidget::item{padding:6px 10px;margin:2px 0;border-radius:10px}''')
    def url(self):return QUrl('nova://'+self.path)
    def title(self):return self._title
    def back(self):self.browser.home()
    def forward(self):pass
    def reload(self):pass

class Toggle(QCheckBox):
    def sizeHint(self):return QSize(340,32)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setOpacity(1 if self.isEnabled() else .4);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setFont(QFont('Segoe UI',10));painter.setPen(QColor('#ccccd1'))
        painter.drawText(self.rect().adjusted(0,0,-58,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,self.text())
        x=self.width()-40;y=(self.height()-20)/2
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(('#b8b8bd' if getattr(self.window(),'private',False) else '#9271d7') if self.isChecked() else '#3a3a40'));painter.drawRoundedRect(QRectF(x,y,38,20),10,10)
        painter.setBrush(QColor('#f4f4f5' if self.isChecked() else '#b5b5bc'));painter.drawEllipse(QRectF(x+(20 if self.isChecked() else 3),y+3,14,14))
    def hitButton(self,pos):return self.rect().contains(pos)

class SyncClient(QWidget):
    statusChanged=Signal(str)
    signedIn=Signal(str)
    changed=Signal()
    avatarChanged=Signal()
    restored=Signal(object,str,str)
    restoreFailed=Signal(int,str)
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.network=QNetworkAccessManager(self);self.token='';self.email='';self.endpoint='';self.auth_endpoint='';self.revision=0;self.busy=False;self.remote_tabs=[]
        self.timer=QTimer(self);self.timer.setInterval(120000);self.timer.timeout.connect(self.synchronize)
        self.google=GoogleFlow(self)
        self.last_status='';self.statusChanged.connect(lambda message:setattr(self,'last_status',message))
        self.google_profile={};self.avatar=QPixmap();self.identity_generation=0;self.google_refresh='';self._restore_busy=False
        self.google_renew=QTimer(self);self.google_renew.setInterval(45*60*1000);self.google_renew.timeout.connect(self.load_google_identity)
        self.restored.connect(self.restore_identity)
        self.restoreFailed.connect(self.restore_failure)
        if not browser.private:QTimer.singleShot(0,self.load_google_identity)
    def set_google_identity(self,claims,token,nonce,refresh_token=''):
        from google_session import save_session
        if self.google_profile.get('sub')!=claims.get('sub'):self.google_refresh=''
        self.google_refresh=refresh_token or self.google_refresh
        self.identity_generation+=1;self.google_profile={k:str(claims.get(k,''))[:500] for k in ('name','email','picture','sub')};self.email=claims['email'];self.avatar=QPixmap()
        try:
            save_session(self.browser.root,claims,token,nonce,self.google_refresh)
        except OSError:pass
        self.google_renew.start(45*60*1000)
        self.signedIn.emit(self.email);self.avatarChanged.emit();self.load_avatar()
    def load_google_identity(self):
        import threading
        from google_session import read_session,restore_session
        from google_flow import verify_identity,desktop_secret
        if self._restore_busy:return
        try:data=read_session(self.browser.root)
        except (OSError,ValueError):return
        generation=self.identity_generation;secret=desktop_secret(self.browser);self._restore_busy=True
        def verify():
            try:
                claims,token,nonce,refresh=restore_session(data,secret,verify_identity);claims['_restore_generation']=generation;claims['_refresh_token']=refresh;self.restored.emit(claims,token,nonce)
            except Exception as error:self.restoreFailed.emit(generation,str(error))
        threading.Thread(target=verify,daemon=True).start()
    def restore_identity(self,claims,token,nonce):
        self._restore_busy=False
        if claims.pop('_restore_generation',-1)!=self.identity_generation:return
        refresh=claims.pop('_refresh_token','');self.set_google_identity(claims,token,nonce,refresh);self.statusChanged.emit('Compte Google connecté.')
    def restore_failure(self,generation,message):
        self._restore_busy=False
        if generation==self.identity_generation:
            self.statusChanged.emit(message)
            if 'indisponible' in message:self.google_renew.start(5*60*1000)
    def load_avatar(self):
        generation=self.identity_generation;url=QUrl(self.google_profile.get('picture',''));host=url.host().lower()
        if url.scheme()!='https' or not (host=='googleusercontent.com' or host.endswith('.googleusercontent.com')):return
        request=QNetworkRequest(url);request.setTransferTimeout(10000);request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        reply=self.network.get(request);data=bytearray()
        def read():
            data.extend(bytes(reply.readAll()))
            if len(data)>1024*1024:reply.abort()
        def done():
            read()
            if generation==self.identity_generation and len(data)<=1024*1024:
                buffer=QBuffer();buffer.setData(QByteArray(bytes(data)));buffer.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buffer);size=reader.size()
                if size.isValid() and max(size.width(),size.height())<=2048:
                    reader.setScaledSize(QSize(96,96));picture=reader.read()
                    if not picture.isNull():
                        self.avatar=QPixmap(96,96);self.avatar.fill(Qt.GlobalColor.transparent);painter=QPainter(self.avatar);painter.setRenderHint(QPainter.RenderHint.Antialiasing);clip=QPainterPath();clip.addEllipse(0,0,96,96);painter.setClipPath(clip);painter.drawImage(0,0,picture);painter.end();self.avatarChanged.emit()
            reply.deleteLater()
        reply.readyRead.connect(read);reply.finished.connect(done)
    def request(self,path,payload,callback,failed=None):
        if self.busy:
            self.statusChanged.emit('Une opération est déjà en cours.')
            if failed:failed()
            return
        url=QUrl(self.endpoint)
        if url.userName() or url.password() or url.hasQuery() or url.hasFragment() or (url.scheme()!='https' and not (url.scheme()=='http' and url.host() in ('127.0.0.1','localhost','::1'))):
            self.statusChanged.emit('Adresse du serveur invalide. Utilisez HTTPS, ou HTTP sur localhost pour un essai.')
            if failed:failed()
            return
        self.busy=True
        req=QNetworkRequest(QUrl(self.endpoint.rstrip('/')+path));req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json');req.setTransferTimeout(20000)
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        if self.token and self.endpoint==self.auth_endpoint:req.setRawHeader(b'Authorization',('Bearer '+self.token).encode())
        reply=self.network.get(req) if payload is None else self.network.post(req,QByteArray(json.dumps(payload).encode()))
        def done():
            self.busy=False
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:data=json.loads(bytes(reply.readAll()).decode())
            except (ValueError,UnicodeError):data={}
            if not status or not 200<=int(status)<300:
                self.statusChanged.emit(data.get('error') or 'Connexion impossible. Vérifiez le serveur et son certificat HTTPS.')
                if failed:failed()
            else:callback(data)
            reply.deleteLater()
        reply.finished.connect(done)
    def login(self,endpoint,email,password,register=False):
        self.endpoint=endpoint.strip().rstrip('/');self.statusChanged.emit('Création du compte…' if register else 'Connexion…')
        self.request('/v1/register' if register else '/v1/login',{'email':email,'password':password},self.accept_session)
    def accept_session(self,data):
        self.token=data['token'];self.email=data['email'];self.auth_endpoint=self.endpoint;self.browser.data['sync_endpoint']=self.endpoint;self.browser.save()
        self.signedIn.emit(self.email);self.statusChanged.emit('Connecté. Prêt à synchroniser.');self.timer.start();self.synchronize()
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
        self.google_renew.stop();self.google_refresh=''
        if self.token and self.endpoint==self.auth_endpoint:self.request('/v1/logout',{},lambda data:None)
        self.identity_generation+=1;self.google_profile={};self.avatar=QPixmap()
        try:(self.browser.root/'google-account.dat').unlink(missing_ok=True)
        except OSError:pass
        self.google.cancel();self.token='';self.email='';self.auth_endpoint='';self.timer.stop();self.signedIn.emit('');self.avatarChanged.emit();self.statusChanged.emit('Déconnecté. Les données locales restent disponibles.')
    def restore_tabs(self):
        for entry in self.remote_tabs[:30]:
            url=QUrl(entry.get('url',''))
            if url.scheme() in ('http','https'):self.browser.new_tab(url)
        self.statusChanged.emit('Onglets de la dernière synchronisation restaurés.')

class AccountPage(InternalPage):
    def __init__(self,browser):
        super().__init__('account','Compte Google',browser)
        outer=QVBoxLayout(self);outer.setContentsMargins(40,32,40,32);outer.setSpacing(14)
        outer.addWidget(text('Votre compte','pageTitle'))
        outer.addWidget(text('Retrouvez votre identité Google dans Nova.'))
        frame,body=card('Google');frame.setMaximumWidth(580)
        row=QHBoxLayout();self.avatar=QLabel();self.avatar.setFixedSize(56,56);self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter);self.avatar.setStyleSheet('background:#20132f;border-radius:28px;color:#d1afff;font-size:23px');row.addWidget(self.avatar)
        labels=QVBoxLayout();self.identity=text('Non connecté','cardTitle');self.email=text('');labels.addWidget(self.identity);labels.addWidget(self.email);row.addLayout(labels);row.addStretch();body.addLayout(row)
        self.status=text('Connectez-vous avec Google pour afficher votre nom et votre photo.');body.addWidget(self.status)
        self.signin=action(body,'Continuer avec Google',lambda:browser.sync_client.google.start(''),True)
        self.signout=action(body,'Se déconnecter',browser.sync_client.logout)
        body.addWidget(text('Cette connexion identifie votre compte dans Nova. Elle ne connecte pas automatiquement les sites ouverts et n’active pas de synchronisation cloud.'))
        outer.addWidget(frame);outer.addStretch()
        browser.sync_client.statusChanged.connect(self.status.setText);browser.sync_client.signedIn.connect(self.identity_changed);browser.sync_client.avatarChanged.connect(self.refresh_avatar)
        self.identity_changed(browser.sync_client.email)
        if browser.sync_client.last_status:self.status.setText(browser.sync_client.last_status)
    def identity_changed(self,email):
        profile=self.browser.sync_client.google_profile;self.identity.setText(profile.get('name') or email or 'Non connecté');self.email.setText(email)
        self.signin.setText('Changer de compte Google' if email else 'Continuer avec Google');self.signout.setVisible(bool(email));self.refresh_avatar()
    def refresh_avatar(self):
        client=self.browser.sync_client
        if client.avatar.isNull():self.avatar.setPixmap(QPixmap());self.avatar.setText((client.google_profile.get('name') or client.email or 'G')[:1].upper())
        else:self.avatar.setText('');self.avatar.setPixmap(client.avatar.scaled(56,56,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

class SettingsPage(InternalPage):
    sections=[('Apparence','settings'),('Onglets','plus'),('Confidentialité','vpn'),('VPN','vpn'),('Téléchargements','download'),('Extensions et publicités','extensions'),('Recherche','search'),('Performances','video'),('Compte et démarrage','profile'),('À propos','home'),('Identifiants et saisie','profile')]
    def __init__(self,browser):
        super().__init__('settings','Paramètres',browser)
        self.setStyleSheet(self.styleSheet()+SETTINGS_STYLE)
        root=QHBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(245);side=QVBoxLayout(sidebar);side.setContentsMargins(18,22,18,20)
        brand=QHBoxLayout();logo=QLabel();logo.setPixmap(browser.windowIcon().pixmap(52,52));brand.addWidget(logo);brand.addWidget(text('Nova','brand'));side.addLayout(brand);side.addSpacing(20)
        self.nav=QListWidget();self.nav.setIconSize(QSize(19,19))
        for name,ico in self.sections:
            item=QListWidgetItem(generated_icon(ico,26),'Compte Google' if name=='Compte et synchronisation' else name);item.setToolTip(name);item.setSizeHint(QSize(200,36));self.nav.addItem(item)
        self.nav.item(3).setHidden(True)
        self.nav.setStyleSheet('QListWidget{padding:0;border:0;background:transparent}QListWidget::item{margin:3px 6px 3px 1px;padding:6px 9px;border:1px solid transparent;border-radius:10px}QListWidget::item:selected{background:#241337;border:1px solid #7340a3;color:#eee5f7}')
        side.addWidget(self.nav);side.addWidget(text('Nova · Version de développement'));root.addWidget(sidebar)
        content=QWidget();self.content=content;content.setFixedWidth(min(1020,max(0,browser.width()-245)));col=QVBoxLayout(content);col.setContentsMargins(30,26,30,25);col.setSpacing(20)
        header=QHBoxLayout();titles=QVBoxLayout();titleLabel=text('Paramètres','pageTitle');titleLabel.setMinimumWidth(260);titles.addWidget(titleLabel);titles.addWidget(text('Personnalisez votre navigateur.'));header.addLayout(titles);header.addStretch()
        search=QLineEdit();search.setPlaceholderText('Rechercher un réglage…');search.setMaximumWidth(290);search.setMinimumWidth(160);header.addWidget(search);col.addLayout(header)
        self.stack=QStackedWidget();col.addWidget(self.stack);root.addWidget(content);root.addStretch(1)
        for index,(name,_) in enumerate(self.sections):
            scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();body.setObjectName('settingsBody');body.setStyleSheet('QWidget#settingsBody{background:transparent}');layout=QVBoxLayout(body);layout.setContentsMargins(0,0,4,0);layout.setSpacing(16 if index==2 else 22)
            self.build_section(index,layout);layout.addStretch();scroll.setWidget(body);self.stack.addWidget(scroll)
        self.nav.currentRowChanged.connect(lambda i:titleLabel.setText(self.sections[i][0]) if 0<=i<len(self.sections) else None)
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
        if hasattr(self,'content'):self.content.setFixedWidth(min(1020,max(0,self.width()-245)))
        if hasattr(self,'appearance_preview'):self.appearance_preview.setVisible(self.width()>=1050)
    def toggle(self,layout,label,key,default=False,callback=None):
        button=Toggle(label);button.setFixedHeight(33);layout.addWidget(button);return bind_preference(self.browser,button,key,default,callback)
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
            rows=section(layout,'Envois de texte','Contrôlez les services facultatifs qui reçoivent votre saisie.')
            def switch(key,default,callback=None):
                t=Toggle('');t.setFixedSize(42,24);return bind_preference(b,t,key,default,callback)
            master=switch('text_services',True,b.set_text_services);ai=switch('ai_suggestions',True,b.set_online_suggestions);translation=switch('online_translation',True)
            preference_row(rows,'Services de texte en ligne','Désactive les suggestions distantes et la traduction de Nova.',master)
            preference_row(rows,'Suggestions en ligne','Le texte saisi est envoyé au service Nova pour proposer des recherches.',ai)
            preference_row(rows,'Traduction en ligne','Le texte ou l’adresse est transmis à Google Traduction uniquement à votre demande.',translation)
            def enabled(*args):ai.setEnabled(master.isChecked() and not b.private);translation.setEnabled(master.isChecked())
            master.toggled.connect(enabled);connect_owned(b.preferenceChanged,lambda name,value:enabled() if name=='text_services' else None,master);enabled()
            hint=text('Ces contrôles concernent les services Nova. Les recherches validées, les connexions et les échanges des sites restent actifs. Les suggestions en ligne sont désactivées en privé.');hint.setStyleSheet('color:#8d8d98;font-size:11px');layout.addWidget(hint)
            rows=section(layout,'Navigation privée','Une session séparée, avec un code d’accès conservé uniquement sur cet appareil.')
            change=QPushButton('Créer / modifier');change.clicked.connect(b.change_private_code);preference_row(rows,'Code d’accès','Création, confirmation et récupération protégée.',change)
            lock=QPushButton('Verrouiller');lock.setEnabled(b.private);lock.clicked.connect(b.lock_private_window);preference_row(rows,'Verrouiller cette fenêtre','Disponible dans une fenêtre privée.',lock)
            rows=section(layout,'Protection et données')
            controls=QPushButton('Ouvrir');controls.clicked.connect(b.site_panel);preference_row(rows,'Protection du site','Autorisations temporaires, données et activité.',controls)
            clear=QPushButton('Effacer…');clear.clicked.connect(b.clear);preference_row(rows,'Historique et cache','Les cookies de connexion sont conservés.',clear)
            cookies=QPushButton('Gérer…');cookies.clicked.connect(b.clear_cookies);preference_row(rows,'Cookies et connexions','Efface les cookies du profil classique avec votre accord.',cookies)
            self.toggle(layout,'Limiter les adresses réseau exposées par WebRTC','webrtc_public',True,b.apply_web_preferences)
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
            ai_frame,ai_layout=card('Suggestions de recherche','Complétions et corrections avec le service Nova.');layout.addWidget(ai_frame)
            self.toggle(ai_layout,'Suggestions en ligne','ai_suggestions',True,b.set_online_suggestions)
            action(ai_layout,'Contrôler les envois de texte',lambda:self.nav.setCurrentRow(2))
            ai_layout.addWidget(text('Le texte de recherche est envoyé au service Nova puis à Groq après une pause de frappe. Aucun historique, favori, formulaire ni mot de passe. Aucune clé à saisir. Propositions locales si le quota partagé est atteint.'))
            frame,c=card('Moteur de recherche');layout.addWidget(frame);combo=QComboBox();combo.addItems(['Nova Search','Google','DuckDuckGo','Bing']);combo.setCurrentText(b.data.get('preferences',{}).get('search_engine','Nova Search'));combo.currentTextChanged.connect(b.set_search_engine);c.addWidget(combo)
            c.addWidget(text('Nova Search conserve l’interface Nova. Un serveur connecté à Brave API active la recherche Web. Au plafond quotidien ou au quota Brave, Google prend automatiquement le relais. Sans serveur, seul le petit index local est utilisé.'))
            action(c,'Ouvrir Nova Search',lambda:b.new_tab(QUrl(b.search_url())))
            action(c,'Configurer le serveur de recherche Web…',b.configure_search_server)
            action(c,'Ajouter un site à l’index…',b.index_search_site)
            search_status=text(str(b.search.index.stats()['pages'])+' pages dans l’index local.' if b.search else 'Index local au repos : il démarre uniquement lorsque vous l’utilisez.');c.addWidget(search_status);b.searchStatus.connect(search_status.setText)
            c.addWidget(text('L’exploration se fait en arrière-plan, sur le site demandé uniquement, avec respect des exclusions robots.txt.'))
        elif index==7:
            frame,c=card('Optimiser le navigateur','Allégez les onglets et l’espace occupé, sans supprimer vos comptes.');layout.addWidget(frame)
            self.toggle(c,'Mettre en pause les onglets en arrière-plan','pause_background_tabs',True,b.set_background_pause)
            c.addWidget(text('Les vidéos et l’audio sont mis en pause dès que vous quittez un onglet. Au retour, seule une lecture interrompue par Nova reprend. Désactivez cette option pour écouter un live en arrière-plan.'))
            action(c,'Voir l’activité et la mémoire des onglets',b.resource_panel)
            setting_action(c,'Optimisation rapide','Vider le cache et mettre en veille les onglets classiques inactifs.','Optimiser',b.optimize,True)
            setting_action(c,'Onglets inactifs','Réduire l’activité des onglets classiques en arrière-plan.','Mettre en veille',b.sleep_tabs)
            setting_action(c,'Fichiers temporaires','Conserver les favoris et les connexions.','Vider le cache',b.clear_cache)
            c.addWidget(text('L’optimisation manuelle allège les onglets classiques. La pause des lecteurs vidéo en arrière-plan se règle avec l’option ci-dessus. Le cache disque est plafonné à 256 Mio.'))
        elif index==8:
            from startup import set_startup
            frame,start=card('Démarrage');layout.addWidget(frame)
            self.toggle(start,'Lancer Nova à l’ouverture de Windows','start_with_windows',True,set_startup)
            self.toggle(start,'Ouvrir en plein écran (F11 pour quitter)','start_fullscreen',True)
            action(layout,'Définir Nova comme navigateur par défaut',b.make_default)
            action(layout,"Importer mes données…",b.open_import)
            frame,c=card('Compte Google','Votre nom, votre photo et votre identité dans Nova.');layout.addWidget(frame);action(c,'Ouvrir mon compte',b.open_account,True);c.addWidget(text('Connexion Google uniquement pour le moment. La synchronisation cloud reste désactivée.'))
        elif index==10:
            frame,c=card('Identifiants et saisie','Un coffre local, protégé par votre session Windows.');layout.addWidget(frame)
            self.toggle(c,'Proposer d’enregistrer les mots de passe','save_passwords',True)
            self.toggle(c,'Remplir les identifiants enregistrés sur le même site','autofill',True)
            self.toggle(c,'Retenir les adresses e-mail utilisées dans les formulaires','remember_emails',True)
            self.toggle(c,'Déverrouiller le remplissage avec Windows Hello','hello_vault',False)
            action(c,'Gérer les identifiants',b.open_vault)
            c.addWidget(text('Nova demande votre accord avant chaque nouvel enregistrement de mot de passe. Le remplissage est limité au même site HTTPS. Le coffre n’est jamais envoyé à Nova Sync.'))
        else:
            frame,c=card('Nova '+VERSION,'Qt WebEngine + WebView2');layout.addWidget(frame)
            c.addWidget(text('Interface Nova, moteur vidéo compatible et uBlock Origin Lite. Version de développement non auditée.'))
            frame,c=card('Mises à jour','Les nouvelles versions sont distribuées depuis zyko144/Nova sur GitHub.');layout.addWidget(frame)
            self.update_status=text('Version installée : '+VERSION);c.addWidget(self.update_status)
            action(c,'Rechercher une mise à jour',lambda:b.updater.check(manual=True))
            action(c,'Voir la version disponible',lambda:b.updater.details())
            b.updater.statusChanged.connect(self.update_status.setText)
            c.addWidget(text('Vérification au démarrage, au retour dans Nova et toutes les 5 minutes. Notification dès qu’une nouvelle version est détectée.'))


SETTINGS_STYLE="""QWidget#novaPage{background:#101012}QFrame#sidebar{background:#131315;border-right:1px solid #29292e}QFrame#card{background:#18181c;border:1px solid #303035;border-radius:10px}QFrame#settingGroup{background:#19191d;border:1px solid #303035;border-radius:10px}QWidget#preferenceRow{background:transparent;border-bottom:1px solid #2a2a30}QLabel{color:#aaaab5}QLabel#pageTitle{color:#eeeeef;font-size:24px}QLabel#cardTitle{color:#e4e4e8;font-size:16px}QLineEdit,QComboBox{background:#18181c;color:#dddde3;border:1px solid #34343a;border-radius:8px}QPushButton{background:#242429;color:#dddddf;border:1px solid #42424a;border-radius:7px;padding:7px 12px;font-size:12px}QPushButton:hover{background:#303036;border-color:#666673}QPushButton#primary{background:#7956bd;border:0}QPushButton:disabled{color:#6c6c77;background:#1d1d21;border-color:#2d2d33}QScrollBar::handle:vertical{background:#42424b;border-radius:3px}"""
