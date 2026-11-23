"""Installed WebView2 extensions, managed through their real profile APIs."""
import json
from PySide6.QtCore import Qt,QTimer,QUrl,QPoint
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QToolButton,QPushButton,QScrollArea
from popups import AnchorPopup
from menus import menu_icon
from pages import Toggle
from media_view import MediaView

class Extensions(AnchorPopup):
    def __init__(self,browser):
        super().__init__(browser,'Extensions',420);self.heading('Extensions','extensions');self.view=None;self.service=None;self.items=[];self.busy=False
        hint=QLabel('Extensions installées dans le moteur compatible.');hint.setWordWrap(True);self.body.addWidget(hint)
        self.status=QLabel('Chargement…');self.status.setWordWrap(True);self.body.addWidget(self.status)
        scroll=QScrollArea();self.scroll=scroll;scroll.setWidgetResizable(True);scroll.setFixedHeight(70);container=QWidget();self.rows=QVBoxLayout(container);self.rows.setContentsMargins(0,0,0,0);self.rows.setSpacing(12);self.rows.addStretch();scroll.setWidget(container);self.body.addWidget(scroll)
        footer=QHBoxLayout();self.restore=QPushButton('Rétablir le bloqueur');self.restore.clicked.connect(lambda:self.command('restore',{}));footer.addWidget(self.restore);footer.addStretch();settings=QToolButton();settings.setIcon(menu_icon('settings',20));settings.setToolTip('Paramètres des extensions');settings.clicked.connect(lambda:(self.hide(),browser.open_settings(5)));footer.addWidget(settings);self.body.addLayout(footer)
        self.idle=QTimer(self);self.idle.setSingleShot(True);self.idle.setInterval(20000);self.idle.timeout.connect(self.stop_service)
    def choose_view(self):
        current=self.browser.current()
        if isinstance(current,MediaView) and not current.stopping:return current
        for view in self.browser.findChildren(MediaView):
            if not view.stopping and view is not self.service:return view
        if self.service is None or self.service.stopping:
            profile=self.browser.root/'profiles'/self.browser.profile.storageName()/'media'
            view=MediaView(QUrl('about:blank'),profile,self.browser);view.hide();view._extension_service=True
            if self.browser.private:view.arguments.append('--private')
            if not self.browser.data['preferences'].get('adblock',True):view.arguments.append('--no-adblock')
            if self.browser.data['preferences'].get('builtin_blocker_removed',False):view.arguments.append('--skip-builtin')
            view.securityEvent.connect(lambda data:self.browser.native_security(view,data));self.service=view
        return self.service
    def open_panel(self):
        if self.browser._private_locked:return
        if self.isVisible():self.hide();return
        self.idle.stop();self.view=self.choose_view();self.status.setText('Chargement…');self.adjustSize();self.reposition();self.show();self.raise_();self.view.send('extensions-list')
    def command(self,name,data):
        if self.busy or self.browser._private_locked:return
        self.busy=True;self.status.setText('Mise à jour…');self.view=self.choose_view();self.view.send('extensions-'+name,json.dumps(data))
    def update_data(self,view,data):
        if view is not self.view:return
        self.busy=False
        if data.get('type')=='extensions-error':self.status.setText('Impossible de modifier l’extension : '+str(data.get('message','')));return
        self.items=data.get('items',[])
        while self.rows.count()>1:
            child=self.rows.takeAt(0).widget()
            if child:child.deleteLater()
        for item in self.items:
            row=QWidget();h=QHBoxLayout(row);h.setContentsMargins(0,7,0,7);h.setSpacing(10);symbol=QLabel();symbol.setFixedSize(24,24);symbol.setPixmap(menu_icon('extensions').pixmap(24,24));h.addWidget(symbol)
            texts=QVBoxLayout();texts.setSpacing(4);title=QLabel(str(item.get('name','Extension')));title.setTextFormat(Qt.TextFormat.PlainText);title.setWordWrap(True);title.setStyleSheet('color:#eeeef2;font-size:13px;font-weight:500');texts.addWidget(title);state=QLabel('Activée' if item.get('enabled') else 'Désactivée');texts.addWidget(state);h.addLayout(texts,1)
            toggle=Toggle('');toggle.setFixedSize(42,28);toggle.setChecked(bool(item.get('enabled')));toggle.setAccessibleName('Activer '+str(item.get('name','')));toggle.setToolTip('Activer / désactiver');ident=str(item.get('id',''));toggle.toggled.connect(lambda enabled,ident=ident:self.command('enable',{'id':ident,'enabled':enabled}));h.addWidget(toggle)
            remove=QToolButton();remove.setIcon(menu_icon('trash',18));remove.setToolTip('Supprimer l’extension');remove.clicked.connect(lambda checked=False,ident=ident:self.command('remove',{'id':ident}));h.addWidget(remove);self.rows.insertWidget(self.rows.count()-1,row)
        self.scroll.setFixedHeight(min(250,max(65,len(self.items)*72)));self.adjustSize()
        if self.isVisible():self.reposition()
        self.status.setText(f'{len(self.items)} extension'+('s' if len(self.items)!=1 else '')+' installée'+('s' if len(self.items)!=1 else '') if self.items else 'Aucune extension installée.')
        builtin=next((item for item in self.items if item.get('builtin')),None);self.restore.setVisible(builtin is None)
        if data.get('affected'):
            prefs=self.browser.data['preferences'];prefs['builtin_blocker_removed']=builtin is None
            if builtin:prefs['adblock']=bool(builtin.get('enabled'))
            elif data.get('removed'):prefs['adblock']=False
            self.browser.save();self.browser.preferenceChanged.emit('adblock',prefs.get('adblock',True))
            for other in self.browser.findChildren(MediaView):
                if not other.stopping:other.send('adblock-toggle','on' if prefs.get('adblock',True) else 'off')
    def hideEvent(self,event):
        super().hideEvent(event)
        if self.service:self.idle.start()
    def stop_service(self):
        if self.service:
            service=self.service;self.service=None
            if self.view is service:self.view=None
            service.stop();service.deleteLater()
