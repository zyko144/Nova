from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl,QObject,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QProgressBar,QScrollArea,QWidget

def size(value):
    for unit in ('o','Kio','Mio','Gio'):
        if value<1024:return f'{value:.1f} {unit}'
        value/=1024
    return f'{value:.1f} Tio'

class Downloads(QDialog):
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.setWindowTitle('Téléchargements Nova');self.resize(510,500);self.setStyleSheet('QDialog,QWidget{background:#0c0912;color:#dfd3ed}QLabel{font:13px "Segoe UI"}QPushButton{background:#21142e;color:#e5d5f5;border:1px solid #3c254f;border-radius:8px;padding:7px 12px}QProgressBar{border:0;background:#241b30;border-radius:3px;height:5px;max-height:5px}QProgressBar::chunk{background:#a45ff0;border-radius:3px}')
        root=QVBoxLayout(self);root.setContentsMargins(24,22,24,22);title=QLabel('Téléchargements');title.setStyleSheet('font-size:23px;font-weight:600');root.addWidget(title);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();self.rows=QVBoxLayout(content);self.rows.setSpacing(22);self.empty=QLabel('Vos fichiers apparaîtront ici.');self.rows.addWidget(self.empty);self.rows.addStretch();scroll.setWidget(content);root.addWidget(scroll);self.items=[];self.timer=QTimer(self);self.timer.setInterval(300);self.timer.timeout.connect(self.refresh)
    def add(self,item,path):
        self.empty.hide();widget=QWidget();layout=QVBoxLayout(widget);label=QLabel(Path(path).name);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);layout.addWidget(label);status=QLabel();layout.addWidget(status);progress=QProgressBar();progress.setTextVisible(False);layout.addWidget(progress);row=QHBoxLayout();pause=QPushButton('Pause');cancel=QPushButton('Annuler');folder=QPushButton('Dossier');row.addWidget(pause);row.addWidget(cancel);row.addStretch();row.addWidget(folder);layout.addLayout(row);pause.clicked.connect(lambda:item.resume() if item.isPaused() or item.state().name=='DownloadInterrupted' else item.pause());cancel.clicked.connect(item.cancel);folder.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent))));self.rows.insertWidget(0,widget);self.items.append((item,status,progress,pause,cancel));item.stateChanged.connect(self.refresh);self.refresh();self.timer.start()
    def refresh(self,*args):
        active=False
        for item,label,bar,pause,cancel in self.items:
            try:
                state=item.state().name;done=item.receivedBytes();total=item.totalBytes();running=state in ('DownloadRequested','DownloadInProgress');resumable=state=='DownloadInterrupted' and (item.data.get('resumable',False) if hasattr(item,'isNative') else True);active|=running
                bar.setRange(0,100 if total>0 else 0);bar.setValue(int(done*100/total) if total>0 else 0);pause.setVisible(running or resumable);cancel.setVisible(running or resumable);pause.setText('Reprendre' if item.isPaused() or resumable else 'Pause')
                text='Terminé' if state=='DownloadCompleted' else 'Annulé' if state=='DownloadCancelled' else 'Interrompu : '+item.interruptReasonString() if state=='DownloadInterrupted' else 'En pause' if item.isPaused() else size(done)+(' / '+size(total) if total>0 else '')
                label.setText(text)
            except RuntimeError:pause.hide();cancel.hide()
        if not active:self.timer.stop()
        elif not self.timer.isActive():self.timer.start()

class NativeDownload(QObject):
    stateChanged=Signal()
    isNative=True
    def __init__(self,view,ident,path):super().__init__(view);self.view=view;self.ident=ident;self.path=path;self.data={'state':'DownloadInProgress','received':0,'total':0,'paused':False,'resumable':False}
    def update(self,data):self.data.update(data);self.stateChanged.emit()
    def state(self):
        from types import SimpleNamespace
        return SimpleNamespace(name=self.data['state'])
    def receivedBytes(self):return self.data.get('received',0)
    def totalBytes(self):return self.data.get('total',0)
    def isPaused(self):return self.data.get('paused',False) or self.data.get('state')=='DownloadInterrupted'
    def interruptReasonString(self):return self.data.get('reason','')
    def pause(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'pause'}))
    def resume(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'resume'}))
    def cancel(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'cancel'}))
