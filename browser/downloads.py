from pathlib import Path
import time
from popups import AnchorPopup
from menus import menu_icon,NovaMenu
from PySide6.QtCore import Qt,QTimer,QUrl,QObject,Signal,QPoint,QFileInfo,QStandardPaths,QRect,QEvent
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QProgressBar,QScrollArea,QWidget,QToolButton,QLineEdit,QFileIconProvider,QFrame

def size(value):
    for unit in ('o','Ko','Mo','Go'):
        if value<1000:return (f'{value:.1f} {unit}').replace('.',',')
        value/=1000
    return (f'{value:.1f} To').replace('.',',')

class DownloadRow(QWidget):
    def __init__(self,panel,item,path):
        super().__init__();self.panel=panel;self.item=item;self.path=Path(path);self.sample=(time.monotonic(),0);self.rate=0;self.last=None
        root=QHBoxLayout(self);root.setContentsMargins(0,9,0,9);root.setSpacing(10)
        symbol=QLabel();symbol.setFixedSize(20,22);symbol.setAlignment(Qt.AlignmentFlag.AlignTop);symbol.setPixmap(QFileIconProvider().icon(QFileInfo(str(self.path))).pixmap(20,20));root.addWidget(symbol,0,Qt.AlignmentFlag.AlignTop)
        content=QVBoxLayout();content.setContentsMargins(0,0,0,0);content.setSpacing(5);top=QHBoxLayout();top.setSpacing(3)
        self.title=QLabel(self.path.name);self.title.setTextFormat(Qt.TextFormat.PlainText);self.title.setWordWrap(True);self.title.setMaximumHeight(38);self.title.setToolTip(self.path.name);self.title.setStyleSheet('color:#f2f2f2;font-size:13px');top.addWidget(self.title,1)
        self.pause=QToolButton();self.pause.setFixedSize(20,20);self.pause.setToolTip('Mettre en pause');self.pause.setText('Ⅱ');self.pause.clicked.connect(self.toggle_pause);top.addWidget(self.pause)
        self.cancel=QToolButton();self.cancel.setFixedSize(20,20);self.cancel.setIcon(menu_icon('close',14));self.cancel.setToolTip('Annuler');self.cancel.clicked.connect(self.item.cancel);top.addWidget(self.cancel)
        self.more=QToolButton();self.more.setFixedSize(20,20);self.more.setText('⋯');self.more.setToolTip('Actions du téléchargement');self.more.clicked.connect(self.actions);top.addWidget(self.more);content.addLayout(top)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setStyleSheet('font-size:12px;color:#c2c2c2');content.addWidget(self.status)
        self.link=QPushButton('Ouvrir un fichier');self.link.setCursor(Qt.CursorShape.ArrowCursor);self.link.setStyleSheet('QPushButton{color:#75c9ff;background:transparent;border:0;padding:0;text-align:left;font-size:12px}QPushButton:hover{text-decoration:underline}');self.link.clicked.connect(self.open_file);content.addWidget(self.link,0,Qt.AlignmentFlag.AlignLeft)
        self.bar=QProgressBar();self.bar.setTextVisible(False);self.bar.setFixedHeight(3);self.bar.setStyleSheet('QProgressBar{border:0;background:#444448;border-radius:1px}QProgressBar::chunk{background:#55baf0;border-radius:1px}');content.addWidget(self.bar);root.addLayout(content,1);item.stateChanged.connect(panel.refresh)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for label in (symbol,self.title,self.status):label.installEventFilter(self)
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.MouseButtonDblClick and event.button()==Qt.MouseButton.LeftButton:
            self.open_file();event.accept();return True
        return super().eventFilter(watched,event)
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.open_file();event.accept()
        else:super().mouseDoubleClickEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.open_file();event.accept()
        else:super().keyPressEvent(event)
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
        if self.item.state().name!='DownloadCompleted':return
        if not self.path.is_file():self.panel.browser.updater.notify('Fichier introuvable',self.path.name+' a été déplacé ou supprimé.');return
        from security import download_warning
        from ui import NovaMessage
        if download_warning(self.path.name) and NovaMessage.question(self.panel.browser,'Ouvrir le fichier',self.path.name+'\nOuvrir ce fichier téléchargé ?')!=NovaMessage.StandardButton.Yes:return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
    def remove(self):
        if self.item.state().name in ('DownloadRequested','DownloadInProgress'):self.item.cancel()
        self.panel.items.remove(self);self.setParent(None);self.deleteLater();self.panel.apply_filter();self.panel.refresh()
    def refresh(self):
        item=self.item;state=item.state().name;done=item.receivedBytes();total=item.totalBytes();paused=item.isPaused();running=state in ('DownloadRequested','DownloadInProgress');native=hasattr(item,'isNative');resumable=state=='DownloadInterrupted' and (item.data.get('resumable',False) if native else True)
        now=time.monotonic();elapsed=now-self.sample[0]
        if elapsed>=.25:
            instant=max(0,done-self.sample[1])/elapsed;self.rate=instant if not self.rate else self.rate*.55+instant*.45;self.sample=(now,done)
        supported=not native or item.data.get('supportsPause',True)
        status='Annulé' if state=='DownloadCancelled' else 'Téléchargement interrompu · '+item.interruptReasonString() if state=='DownloadInterrupted' and not resumable else 'En pause' if paused else size(done)+(' / '+size(total) if total>0 else '')+' · '+f'{self.rate/1000000:.2f} Mo/s'.replace('.',',')
        snapshot=(state,done,total,paused,resumable,status)
        if snapshot!=self.last:
            self.last=snapshot;self.status.setText(status);self.status.setVisible(state!='DownloadCompleted');self.link.setVisible(state=='DownloadCompleted');self.bar.setRange(0,100 if total>0 or not running else 0);self.bar.setValue(min(100,int(done*100/total)) if total>0 else 0);self.bar.setVisible(running);self.pause.setVisible(supported and (running or resumable));self.cancel.setVisible(running or resumable);self.pause.setText('▷' if paused or resumable else 'Ⅱ');self.pause.setToolTip('Reprendre' if paused or resumable else 'Mettre en pause')
            self.ensurePolished();width=self.panel.width()-60;controls=20+(23 if supported and (running or resumable) else 0)+(23 if running or resumable else 0)
            title_height=max(20,min(38,self.title.fontMetrics().boundingRect(QRect(0,0,width-controls,100),Qt.TextFlag.TextWordWrap,self.path.name).height()))
            detail_height=self.link.fontMetrics().height() if state=='DownloadCompleted' else min(45,self.status.fontMetrics().boundingRect(QRect(0,0,width,100),Qt.TextFlag.TextWordWrap,status).height())
            self.setFixedHeight(18+title_height+5+detail_height+(8 if running else 0))
        return running and not paused

class Downloads(AnchorPopup):
    def __init__(self,browser):
        super().__init__(browser,'Téléchargements',360);self.popup_color='#202020';self.body.setContentsMargins(15,9,12,10);self.body.setSpacing(8)
        self.setStyleSheet(self.styleSheet()+'QFrame#novaPopup{background:#202020;border:1px solid #353535;border-radius:16px}QToolButton{padding:3px;background:transparent;border:0;font-size:14px}QToolButton:hover{background:#343434}QScrollArea,QScrollArea QWidget{background:transparent}')
        header=QHBoxLayout();title=QLabel('Téléchargements');title.setStyleSheet('font-size:14px;font-weight:600;color:white');header.addWidget(title,1)
        for name,tip,callback in [('folder','Ouvrir le dossier Téléchargements',self.open_folder),('search','Rechercher un téléchargement',self.toggle_search),('menu','Plus d’options',self.options)]:
            button=QToolButton();button.setText('⋯') if name=='menu' else button.setIcon(menu_icon(name,17));button.setFixedSize(24,28);button.setToolTip(tip);button.clicked.connect(callback);header.addWidget(button)
        self.body.addLayout(header);line=QFrame();line.setFixedHeight(1);line.setStyleSheet('background:#353535');self.body.addWidget(line)
        self.search=QLineEdit();self.search.setPlaceholderText('Rechercher un téléchargement');self.search.setStyleSheet('background:#292929;border:1px solid #444;color:white;padding:6px;border-radius:5px');self.search.hide();self.search.textChanged.connect(self.apply_filter);self.body.addWidget(self.search)
        scroll=QScrollArea();self.scroll=scroll;scroll.setWidgetResizable(True);scroll.setFixedHeight(65);content=QWidget();self.rows=QVBoxLayout(content);self.rows.setContentsMargins(0,0,3,0);self.rows.setSpacing(0);self.empty=QLabel('Aucun téléchargement.');self.empty.setWordWrap(True);self.rows.addWidget(self.empty);self.rows.addStretch();scroll.setWidget(content);self.body.addWidget(scroll);self.items=[];self.retained_views=set();self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.refresh)
    def open_folder(self):
        folder=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation) or str(Path.home());QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
    def toggle_search(self):
        self.search.setVisible(self.search.isHidden());self.adjustSize()
        if self.search.isVisible():self.search.setFocus()
        else:self.search.clear()
    def options(self):
        menu=NovaMenu(self.browser);menu.entry('Ouvrir le dossier','folder',self.open_folder)
        def clear():
            for row in tuple(self.items):
                if row.item.state().name not in ('DownloadRequested','DownloadInProgress'):row.remove()
        menu.entry('Retirer les téléchargements terminés','trash',clear);menu.exec(self.mapToGlobal(QPoint(self.width()-20,40)));menu.deleteLater()
    def apply_filter(self,*args):
        query=self.search.text().strip().casefold();count=0
        for row in self.items:
            visible=query in row.path.name.casefold();row.setVisible(visible);count+=visible
        self.empty.setVisible(not count);self.empty.setText('Aucun résultat.' if query else 'Aucun téléchargement.');height=sum(row.height() for row in self.items if not row.isHidden());self.scroll.setFixedHeight(min(400,max(65,height)));self.adjustSize()
        if self.isVisible():self.reposition()
    def add(self,item,path):
        row=DownloadRow(self,item,path);self.rows.insertWidget(0,row);self.items.append(row);self.apply_filter();self.refresh();self.timer.start()
    def refresh(self,*args):
        active=False
        for row in tuple(self.items):
            try:active=row.refresh() or active
            except RuntimeError:row.pause.hide();row.cancel.hide()
        if active and not self.timer.isActive():self.timer.start()
        elif not active:self.timer.stop()
        for view in tuple(self.retained_views):
            if not self.view_has_transfers(view):
                self.retained_views.remove(view);view.stop();view.deleteLater()
    def view_has_transfers(self,view):
        return any(getattr(row.item,'view',None) is view and (row.item.state().name in ('DownloadRequested','DownloadInProgress') or row.item.state().name=='DownloadInterrupted' and row.item.data.get('resumable',False)) for row in self.items)
    def retain_view(self,view):
        if not self.view_has_transfers(view):return False
        # QTabWidget.removeTab keeps the stack as parent. Preserve its native
        # window handle so the download host is not mistaken for an orphan.
        view.hide();view.send('suspend');self.retained_views.add(view);return True
    def stop_retained(self):
        for view in tuple(self.retained_views):view.stop();view.deleteLater()
        self.retained_views.clear()
    def show_panel(self,toggle=False):
        if self.browser._private_locked:return
        if toggle and self.isVisible():self.hide();return
        self.refresh();self.apply_filter();self.adjustSize();self.reposition();self.show();self.raise_()

class NativeDownload(QObject):
    stateChanged=Signal()
    isNative=True
    def __init__(self,view,ident,path):super().__init__(view.window());self.view=view;self.ident=ident;self.path=path;self.data={'state':'DownloadInProgress','received':0,'total':0,'paused':False,'resumable':False}
    def update(self,data):self.data.update(data);self.stateChanged.emit()
    def state(self):
        from types import SimpleNamespace
        return SimpleNamespace(name=self.data['state'])
    def receivedBytes(self):return self.data.get('received',0)
    def totalBytes(self):return self.data.get('total',0)
    def isPaused(self):return self.data.get('paused',False) or self.data.get('state')=='DownloadInterrupted'
    def interruptReasonString(self):
        reason=self.data.get('reason','')
        return {'NetworkFailed':'Problème de connexion','NetworkDisconnected':'Connexion perdue','ServerFailed':'Le serveur ne répond pas','ServerForbidden':'Le serveur refuse le téléchargement','ServerUnauthorized':'Connexion au site nécessaire','FileAccessDenied':'Accès au dossier refusé','FileNoSpace':'Espace disque insuffisant','FileNameTooLong':'Nom de fichier trop long','UserPaused':'En pause','UserCanceled':'Annulé','FileBlockedByPolicy':'Fichier bloqué par Windows'}.get(reason,reason)
    def pause(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'pause'}))
    def resume(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'resume'}))
    def cancel(self):self.view.send('download-control',__import__('json').dumps({'id':self.ident,'action':'cancel'}))
