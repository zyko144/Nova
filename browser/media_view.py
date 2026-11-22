import json, sys,base64
from pathlib import Path
from PySide6.QtCore import QProcess, QUrl, Signal, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel,QApplication
from PySide6.QtGui import QPixmap,QIcon

def media_url(url):
    host = url.host().lower()
    return host in ('youtu.be','youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','twitch.tv','www.twitch.tv','player.twitch.tv')

def helper_path():
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    if not getattr(sys,'frozen',False): return base / 'MediaHost' / 'bin-runtime' / 'NovaMediaHost.exe'
    return base / 'MediaHost' / 'NovaMediaHost.exe'

class MediaView(QWidget):
    titleChanged = Signal(str)
    urlChanged = Signal(QUrl)
    loadFinished = Signal(bool)
    fullscreenChanged = Signal(bool)
    diagnostic = Signal(object)
    newTabRequested = Signal(str)
    settingsRequested = Signal()
    readyChanged = Signal()
    iconChanged = Signal(object)
    backRequested = Signal()
    shortcutRequested = Signal(str)
    def __init__(self,url,profile,parent=None):
        super().__init__(parent)
        self._url=QUrl(url); self._title='Vidéo'; self.buffer=b''; self.ready=False
        self.pending_url=None
        self.pending_commands=[]
        self.stopping=False
        self.previous_view=None
        self.adblock_enabled=False
        self.adblock_name='En cours de chargement'
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setStyleSheet('background:#05040c;color:#cbb9e8;')
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.label=QLabel('Démarrage du moteur vidéo…',self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.layout.addWidget(self.label)
        self.process=QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read_events)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.arguments=[str(int(self.winId())),str(profile),url.toString()]
        QTimer.singleShot(0,self.start)
    def start(self):
        if self.stopping or self.process.state()!=QProcess.ProcessState.NotRunning:return
        path=helper_path()
        if not path.exists():
            self.label.setText('Moteur vidéo manquant : conservez le dossier MediaHost près de NovaBrowser.exe.'); return
        if self.pending_url:self.arguments[2]=self.pending_url;self.pending_url=None
        self.process.start(str(path),self.arguments)
    def process_error(self,error):
        if not self.stopping:self.label.setText('Moteur vidéo indisponible. Utilisez Actualiser pour réessayer.')
    def read_events(self):
        self.buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try: event=json.loads(line)
            except (ValueError,UnicodeError): continue
            kind=event.get('type'); value=event.get('value')
            if kind=='url':
                if self.pending_url and not self.ready:continue
                self._url=QUrl(value); self.urlChanged.emit(self._url)
            elif kind=='title': self._title=value; self.titleChanged.emit(value)
            elif kind=='favicon' and isinstance(value,str) and len(value)<512000:
                try:
                    pixmap=QPixmap();pixmap.loadFromData(base64.b64decode(value));self.iconChanged.emit(QIcon(pixmap))
                except (ValueError,TypeError):pass
            elif kind=='loaded': self.loadFinished.emit(event.get('ok',False))
            elif kind=='ready':
                self.ready=True; self.label.hide()
                if self.pending_url: self.send('navigate',self.pending_url); self.pending_url=None
                commands,self.pending_commands=self.pending_commands,[]
                for command,value in commands:self.send(command,value)
                self.readyChanged.emit()
            elif kind=='error': self.label.setText('Erreur du moteur vidéo : '+str(value))
            elif kind=='fullscreen': self.fullscreenChanged.emit(bool(value))
            elif kind=='open-tab':self.newTabRequested.emit(str(value))
            elif kind=='open-settings':self.settingsRequested.emit()
            elif kind=='back-home':self.backRequested.emit()
            elif kind=='shortcut':self.shortcutRequested.emit(str(value))
            elif kind=='probe': self.diagnostic.emit(value)
            elif kind=='adblock':
                self.adblock_enabled=bool(event.get('enabled')); self.adblock_name=event.get('name','')
                self.diagnostic.emit(event)
    def send(self,command,value=''):
        if self.stopping and command!='close':return
        if self.ready and self.process.state()==QProcess.ProcessState.Running:
            self.process.write((json.dumps({'command':command,'value':value})+'\n').encode())
        elif command!='close':
            self.pending_commands.append((command,value))
    def setUrl(self,url):
        self._url=QUrl(url); self.urlChanged.emit(self._url)
        if self.ready: self.send('navigate',url.toString())
        else: self.pending_url=url.toString()
    def url(self): return self._url
    def title(self): return self._title
    def back(self): self.send('back')
    def forward(self): self.send('forward')
    def reload(self):
        if not self.stopping and self.process.state()==QProcess.ProcessState.NotRunning:
            self.ready=False;self.pending_url=self._url.toString();self.label.setText('Redémarrage du moteur vidéo…');self.label.show();self.start()
        else:self.send('reload')
    def stop(self):
        if self.stopping:return
        self.send('close')
        self.stopping=True;self.pending_commands.clear()
        process=self.process
        process.setParent(QApplication.instance())
        process.finished.connect(process.deleteLater)
        def reap():
            try:
                if process.state()!=QProcess.ProcessState.NotRunning:process.kill()
                else:process.deleteLater()
            except RuntimeError:pass
        QTimer.singleShot(800,reap)
    def finished(self,*args):
        self.ready=False
        if not self.stopping:self.label.show();self.label.setText('Le moteur vidéo s’est arrêté. Utilisez Actualiser pour réessayer.')
