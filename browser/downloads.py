from pathlib import Path
import time
from popups import AnchorPopup
from menus import menu_icon,NovaMenu
from PySide6.QtCore import Qt,QTimer,QUrl,QObject,Signal,QPoint
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QProgressBar,QScrollArea,QWidget,QToolButton

def size(value):
    for unit in ('o','Kio','Mio','Gio'):
        if value<1024:return f'{value:.1f} {unit}'
        value/=1024
    return f'{value:.1f} Tio'

class DownloadRow(QWidget):
    def __init__(self,panel,item,path):
        super().__init__();self.panel=panel;self.item=item;self.path=Path(path);self.sample=(time.monotonic(),0);self.rate=0;self.last=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,8,0,12);layout.setSpacing(7)
        top=QHBoxLayout();symbol=QLabel();symbol.setFixedSize(22,22);symbol.setPixmap(menu_icon('page').pixmap(22,22));top.addWidget(symbol)
        self.title=QLabel();self.title.setStyleSheet('color:#eeeef2;font-size:13px;font-weight:500');self.title.setToolTip(self.path.name);self.title.setFixedWidth(260);top.addWidget(self.title,1)
        self.more=QToolButton();self.more.setText('⋯');self.more.setToolTip('Actions du téléchargement');self.more.clicked.connect(self.actions);top.addWidget(self.more);layout.addLayout(top)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        self.bar=QProgressBar();self.bar.setTextVisible(False);self.bar.setFixedHeight(4);self.bar.setStyleSheet('QProgressBar{border:0;background:#36363f;border-radius:2px}QProgressBar::chunk{background:#a281dc;border-radius:2px}');layout.addWidget(self.bar)
        controls=QHBoxLayout();self.pause=QPushButton('Pause');self.cancel=QPushButton('Annuler');self.folder=QToolButton();self.folder.setIcon(menu_icon('folder',18));self.folder.setToolTip('Afficher le dossier');self.folder.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path.parent))))
        self.pause.clicked.connect(self.toggle_pause);self.cancel.clicked.connect(self.item.cancel);controls.addWidget(self.pause);controls.addWidget(self.cancel);controls.addStretch();controls.addWidget(self.folder);layout.addLayout(controls)
        item.stateChanged.connect(panel.refresh)
    def toggle_pause(self):
        item=self.item
        if item.isPaused() or item.state().name=='DownloadInterrupted':item.resume()
        else:item.pause()
        self.sample=(time.monotonic(),item.receivedBytes());self.rate=0;self.panel.timer.start();self.panel.refresh()
    def actions(self):
        menu=NovaMenu(self.panel.browser);state=self.item.state().name;active=state in ('DownloadRequested','DownloadInProgress')
        if state=='DownloadCompleted':menu.entry('Ouvrir le fichier','page',self.open_file)
        menu.entry('Afficher le dossier','folder',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path.parent))))
        menu.entry('Annuler et retirer' if active else 'Retirer de la liste','trash',self.remove)
        menu.exec(self.more.mapToGlobal(QPoint(0,self.more.height())));menu.deleteLater()
    def open_file(self):
        from security import download_warning
        from ui import NovaMessage
        if download_warning(self.path.name) and NovaMessage.question(self.panel.browser,'Ouvrir le fichier',self.path.name+'\nOuvrir ce fichier téléchargé ?')!=NovaMessage.StandardButton.Yes:return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
    def remove(self):
        if self.item.state().name in ('DownloadRequested','DownloadInProgress'):self.item.cancel()
        self.panel.items.remove(self);self.setParent(None);self.deleteLater();self.panel.empty.setVisible(not self.panel.items);self.panel.scroll.setFixedHeight(min(360,max(90,len(self.panel.items)*140)));self.panel.adjustSize();self.panel.reposition();self.panel.refresh()
    def refresh(self):
        item=self.item;state=item.state().name;done=item.receivedBytes();total=item.totalBytes();paused=item.isPaused();running=state in ('DownloadRequested','DownloadInProgress');native=hasattr(item,'isNative');resumable=state=='DownloadInterrupted' and (item.data.get('resumable',False) if native else True)
        now=time.monotonic();elapsed=now-self.sample[0]
        if elapsed>=.25:
            instant=max(0,done-self.sample[1])/elapsed;self.rate=instant if not self.rate else self.rate*.55+instant*.45;self.sample=(now,done)
        supported=not native or item.data.get('supportsPause',True)
        status='Terminé · '+size(done) if state=='DownloadCompleted' else 'Annulé' if state=='DownloadCancelled' else ('En pause' if resumable and paused else 'Échec : '+item.interruptReasonString()) if state=='DownloadInterrupted' else 'En pause' if paused else size(done)+(' / '+size(total) if total>0 else '')+' · '+f'{self.rate/1000000:.2f} Mo/s'
        snapshot=(state,done,total,paused,resumable,status)
        if snapshot!=self.last:
            self.last=snapshot;self.status.setText(status);self.bar.setRange(0,100 if total>0 or not running else 0);self.bar.setValue(min(100,int(done*100/total)) if total>0 else 0);self.bar.setVisible(state!='DownloadCancelled');self.pause.setVisible(supported and (running or resumable));self.cancel.setVisible(supported and (running or resumable));self.pause.setText('Reprendre' if paused or resumable else 'Pause');self.title.setText(self.title.fontMetrics().elidedText(self.path.name,Qt.TextElideMode.ElideMiddle,260))
        return running and not paused

class Downloads(AnchorPopup):
    def __init__(self,browser):
        super().__init__(browser,'Téléchargements',430);self.heading('Téléchargements','download')
        scroll=QScrollArea();self.scroll=scroll;scroll.setWidgetResizable(True);scroll.setFixedHeight(90);content=QWidget();self.rows=QVBoxLayout(content);self.rows.setContentsMargins(0,0,8,0);self.rows.setSpacing(7);self.empty=QLabel('Vos téléchargements apparaîtront ici.');self.empty.setWordWrap(True);self.rows.addWidget(self.empty);self.rows.addStretch();scroll.setWidget(content);self.body.addWidget(scroll)
        hint=QLabel('Retirer de la liste conserve le fichier sur votre PC.');hint.setWordWrap(True);self.body.addWidget(hint);self.items=[];self.timer=QTimer(self);self.timer.setInterval(400);self.timer.timeout.connect(self.refresh)
    def add(self,item,path):
        self.empty.hide();row=DownloadRow(self,item,path);self.rows.insertWidget(0,row);self.items.append(row);self.refresh();self.timer.start()
    def refresh(self,*args):
        active=False
        for row in tuple(self.items):
            try:active=row.refresh() or active
            except RuntimeError:row.pause.hide();row.cancel.hide()
        if active and not self.timer.isActive():self.timer.start()
        elif not active:self.timer.stop()
    def show_panel(self,toggle=False):
        if self.browser._private_locked:return
        if toggle and self.isVisible():self.hide();return
        self.refresh();self.scroll.setFixedHeight(min(360,max(90,len(self.items)*140)));self.adjustSize();self.reposition();self.show();self.raise_()

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
