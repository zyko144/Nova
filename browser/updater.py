import hashlib,json,re,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import Qt,QTimer,QUrl,Signal,QObject,QSize
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QApplication,QPlainTextEdit
from ui import NovaDialog,generated_icon
from version import VERSION,REPOSITORY,RELEASE_ASSET

def version_tuple(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',value)
    return tuple(map(int,match.groups())) if match else None

def release_asset(release):
    if release.get('draft') or release.get('prerelease') or version_tuple(release.get('tag_name','')) is None:return None
    for item in release.get('assets',[]):
        url=urlsplit(item.get('browser_download_url',''));digest=item.get('digest','')
        if item.get('name')==RELEASE_ASSET and url.scheme=='https' and url.netloc=='github.com' and url.path.startswith('/'+REPOSITORY+'/releases/download/') and re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest) and type(item.get('size'))==int and 0<item['size']<1500*1024*1024:
            return item
    return None

class UpdateToast(QFrame):
    def __init__(self,browser,title,message,callback=None,action_text='Voir la mise à jour',symbol='download'):
        super().__init__(browser,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating);self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet('QFrame{background:#110c19;border:1px solid #4a2a66;border-radius:15px}QLabel{color:#c8b9d8;border:0;background:transparent;font-size:12px}QPushButton{background:#28133d;color:#eee2fa;border:0;border-radius:8px;padding:7px 12px;font-size:12px}')
        if browser.private:
            from ui import neutral_style
            self.setStyleSheet(neutral_style(self.styleSheet()))
        self.setFixedWidth(345);layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,16);layout.setSpacing(10)
        row=QHBoxLayout();symbol_label=QLabel();symbol_label.setPixmap(generated_icon(symbol,24).pixmap(24,24));symbol_label.setFixedSize(28,28);row.addWidget(symbol_label);heading=QLabel(title);heading.setStyleSheet('font-weight:600;color:#f2eafa;font-size:14px');row.addWidget(heading);row.addStretch()
        close=QPushButton();close.setIcon(generated_icon('close',14));close.setIconSize(QSize(14,14));close.setToolTip('Fermer');close.setFixedSize(24,24);close.setStyleSheet('QPushButton{padding:0;background:transparent;border:0;border-radius:7px}QPushButton:hover{background:#28183a}');close.clicked.connect(self.close);row.addWidget(close);layout.addLayout(row)
        label=QLabel(message);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);layout.addWidget(label)
        if callback:
            button=QPushButton(action_text);button.clicked.connect(lambda:(self.close(),callback()));layout.addWidget(button,0,Qt.AlignmentFlag.AlignLeft)
        else:QTimer.singleShot(8000,self.close)
        self.adjustSize();self.reposition(browser);self.show()
    def reposition(self,browser):
        point=browser.mapToGlobal(browser.rect().bottomRight());self.move(point.x()-self.width()-20,point.y()-self.height()-20)

class Updater(QObject):
    statusChanged=Signal(str)
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.network=QNetworkAccessManager(self);self.available=None;self.busy=False;self.checked_at=0.;self.etag=b'';self.notified='';self.toast=None;self.archive=None
        self.directory=browser.root/'updates';self.directory.mkdir(exist_ok=True)
        self.timer=QTimer(self);self.timer.setInterval(300000);self.timer.timeout.connect(self.check)
        if not browser.private and QApplication.applicationName()=='NovaBrowser':
            self.timer.start();QTimer.singleShot(1500,self.startup)
            QApplication.instance().applicationStateChanged.connect(self.focused)
    def startup(self):
        result=self.directory/'update-result.json'
        if result.exists():
            try:
                value=json.loads(result.read_text(encoding='utf-8-sig'));result.unlink()
                self.notify('Mise à jour installée' if value.get('success') else 'Mise à jour interrompue',value.get('message','Nova est prêt.'))
            except (OSError,ValueError):pass
        previous=self.browser.data.get('last_version')
        if previous and previous!=VERSION:self.notify('Nova a été mis à jour',f'La version {VERSION} est installée.')
        self.browser.data['last_version']=VERSION;self.browser.save();self.check()
    def focused(self,state):
        if state==Qt.ApplicationState.ApplicationActive and time.monotonic()-self.checked_at>60:self.check()
    def notify(self,title,message,callback=None,action_text='Voir la mise à jour',symbol='download'):
        if self.browser.presentation and title!='Mode présentation':return
        if self.toast:
            try:self.toast.close()
            except RuntimeError:pass
        self.toast=UpdateToast(self.browser,title,message,callback,action_text,symbol)
    def check(self,manual=False):
        if self.busy:return
        self.busy=True;self.checked_at=time.monotonic();self.statusChanged.emit('Recherche de mises à jour…')
        request=QNetworkRequest(QUrl('https://api.github.com/repos/'+REPOSITORY+'/releases/latest'));request.setRawHeader(b'User-Agent',('NovaBrowser/'+VERSION).encode());request.setRawHeader(b'Accept',b'application/vnd.github+json');request.setTransferTimeout(15000)
        if self.etag:request.setRawHeader(b'If-None-Match',self.etag)
        reply=self.network.get(request)
        def finished():
            self.busy=False;status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:
                if status==304:
                    if self.available:
                        self.statusChanged.emit('Version '+self.available['tag_name']+' disponible.')
                        if manual:self.details()
                    else:self.statusChanged.emit('Nova '+VERSION+' est à jour.')
                    return
                if status==404:self.statusChanged.emit('Aucune version publiée sur GitHub pour le moment.');return
                if status!=200:self.statusChanged.emit('Vérification indisponible. Réessayez plus tard.');return
                raw=bytes(reply.readAll())
                if len(raw)>2*1024*1024:raise ValueError()
                release=json.loads(raw);remote=version_tuple(release.get('tag_name',''))
                self.etag=bytes(reply.rawHeader('ETag'))
                if remote and remote>version_tuple(VERSION) and not release.get('prerelease') and not release.get('draft'):
                    self.available=release;tag=release['tag_name'];self.statusChanged.emit('Version '+tag+' disponible.')
                    if tag!=self.notified:self.notified=tag;self.notify('Nouvelle version disponible','Nova '+tag+' est prêt à télécharger.',self.details)
                    if manual:self.details()
                else:self.statusChanged.emit('Nova '+VERSION+' est à jour.')
            except (ValueError,TypeError,KeyError):self.statusChanged.emit('Réponse GitHub invalide.')
            finally:reply.deleteLater()
        reply.finished.connect(finished)
    def details(self):
        if not self.available:return
        release=self.available;dialog=NovaDialog(self.browser,'Mise à jour Nova',release.get('tag_name',''))
        notes=QPlainTextEdit();notes.setReadOnly(True);notes.setPlainText((release.get('body') or 'Améliorations et correctifs de Nova.')[:6000]);notes.setMaximumHeight(170);notes.setStyleSheet('background:#08050e;color:#cdbbdc;border:1px solid #32203f;border-radius:9px;padding:10px');dialog.body.addWidget(notes)
        asset=release_asset(release)
        if asset:
            button=QPushButton('Télécharger la mise à jour');button.setObjectName('primary');button.clicked.connect(lambda:(dialog.accept(),self.download(asset)));dialog.body.addWidget(button,0,Qt.AlignmentFlag.AlignRight)
        else:
            label=QLabel('Le paquet Windows vérifiable n’est pas encore disponible.');label.setWordWrap(True);dialog.body.addWidget(label)
        dialog.exec()
    def download(self,asset,verified=False):
        if self.busy:return
        if not verified:
            self.verify_release_signature(asset);return
        self.busy=True;self.statusChanged.emit('Téléchargement de la mise à jour…')
        version=self.available['tag_name'].lstrip('v');path=self.directory/('Nova-'+version+'.zip.part')
        try:handle=path.open('wb')
        except OSError:self.busy=False;self.statusChanged.emit('Impossible de créer le fichier de mise à jour.');return
        digest=hashlib.sha256();received=0;last_progress=-1;write_failed=False
        request=QNetworkRequest(QUrl(asset['browser_download_url']));request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy);request.setTransferTimeout(60000)
        reply=self.network.get(request)
        def read():
            nonlocal received,last_progress,write_failed
            data=bytes(reply.readAll());received+=len(data)
            if received>asset['size']:reply.abort();return
            try:handle.write(data);digest.update(data)
            except OSError:write_failed=True;reply.abort();return
            progress=int(received*100/asset['size'])
            if progress!=last_progress:last_progress=progress;self.statusChanged.emit(f'Téléchargement : {progress} %')
        def finished():
            read();handle.close();self.busy=False
            valid=not write_failed and reply.error()==QNetworkReply.NetworkError.NoError and received==asset['size'] and digest.hexdigest().lower()==asset['digest'].split(':')[1].lower()
            reply.deleteLater()
            if not valid:
                path.unlink(missing_ok=True);self.statusChanged.emit('Téléchargement incomplet ou intégrité non vérifiée. Installation annulée.');return
            final=path.with_suffix('');path.replace(final);self.archive=(final,digest.hexdigest(),version);self.statusChanged.emit('Mise à jour vérifiée, prête à installer.');self.install_prompt()
        reply.readyRead.connect(read);reply.finished.connect(finished)
    def verify_release_signature(self,asset):
        manifest=next((x for x in self.available.get('assets',[]) if x.get('name')=='NOVA-UPDATE.json'),None)
        url=urlsplit(manifest.get('browser_download_url','') if manifest else '')
        prefix='/'+REPOSITORY+'/releases/download/'+self.available['tag_name']+'/'
        if not manifest or url.scheme!='https' or url.netloc!='github.com' or not url.path.startswith(prefix):
            self.statusChanged.emit('Signature de mise à jour absente. Installation annulée.');return
        self.busy=True;self.statusChanged.emit('Vérification de la signature Nova…')
        request=QNetworkRequest(QUrl(manifest['browser_download_url']));request.setTransferTimeout(15000);request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reply=self.network.get(request)
        def done():
            self.busy=False
            try:
                from update_signature import verify_manifest
                raw=bytes(reply.readAll())
                if reply.error()!=QNetworkReply.NetworkError.NoError or len(raw)>4096 or not verify_manifest(json.loads(raw),asset,self.available['tag_name']):raise ValueError()
                self.download(asset,True)
            except (ValueError,TypeError,KeyError):self.statusChanged.emit('Signature Nova invalide. Installation bloquée.')
            finally:reply.deleteLater()
        reply.finished.connect(done)
    def install_prompt(self):
        if not self.archive:return
        dialog=NovaDialog(self.browser,'Mise à jour prête','Nova va se fermer, installer la nouvelle version et redémarrer. Vos profils et données sont conservés.')
        button=QPushButton('Installer et redémarrer');button.setObjectName('primary');button.clicked.connect(lambda:(dialog.accept(),self.install()));dialog.body.addWidget(button,0,Qt.AlignmentFlag.AlignRight);dialog.exec()
    def install(self):
        if not self.archive or not getattr(sys,'frozen',False):self.statusChanged.emit('Installation automatique disponible dans l’exécutable Windows.');return
        archive,digest,version=self.archive
        helper=Path(__file__).parent/'update-install.ps1'
        if not helper.exists():self.statusChanged.emit('Assistant d’installation absent.');return
        import os,shutil
        # Copy helper out of the installation directory before that directory is moved.
        script=self.directory/'install.ps1';shutil.copy2(helper,script)
        try:
            subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Archive',str(archive),'-Sha256',digest,'-InstallPath',str(Path(sys.executable).parent),'-ParentPid',str(os.getpid()),'-Version',version,'-StatePath',str(self.directory)],creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError:self.statusChanged.emit('Impossible de démarrer l’installation.');return
        self.browser.close()
