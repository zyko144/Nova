from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QWidget
from media_view import MediaView

class FloatingPlayer(QDialog):
    def __init__(self,browser,view):
        super().__init__(browser,Qt.WindowType.Window|Qt.WindowType.WindowStaysOnTopHint);self.browser=browser;self.view=view;self.index=browser.tabs.indexOf(view);self.setWindowTitle('Nova · Lecteur flottant');self.resize(480,310);self.setMinimumSize(320,220);self.setStyleSheet('QDialog{background:#09060f}QPushButton{background:#21142f;color:#eadcf8;border:0;border-radius:8px;padding:7px 12px}QLabel{color:#cab8dc}')
        root=QVBoxLayout(self);root.setContentsMargins(5,5,5,5);row=QHBoxLayout();row.addWidget(QLabel('Lecteur Nova'));row.addStretch();back=QPushButton('Revenir à l’onglet');back.clicked.connect(self.close);row.addWidget(back);root.addLayout(row)
        self.placeholder=QWidget();self.placeholder.url=view.url;self.placeholder.title=view.title;layout=QVBoxLayout(self.placeholder);label=QLabel('Lecture dans la fenêtre flottante');label.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(label);button=QPushButton('Revenir à l’onglet');button.clicked.connect(self.close);layout.addWidget(button,0,Qt.AlignmentFlag.AlignCenter)
        browser.tabs.blockSignals(True);browser.tabs.removeTab(self.index);browser.tabs.insertTab(self.index,self.placeholder,'Lecteur flottant');browser.tabs.setCurrentIndex(self.index);browser.tabs.blockSignals(False);root.addWidget(view);view._floating=True;browser._active_view=self.placeholder;browser.resume_view(view);view.show();self.show();self.rebind()
    def rebind(self):
        if isinstance(self.view,MediaView):self.view.send('reparent',str(int(self.view.winId())))
    def closeEvent(self,event):
        browser=self.browser;index=browser.tabs.indexOf(self.placeholder)
        if index>=0:
            browser.tabs.blockSignals(True);browser.tabs.removeTab(index);browser.tabs.insertTab(index,self.view,self.view.title());browser.tabs.setCurrentIndex(index);browser.tabs.blockSignals(False);self.view._floating=False;browser._active_view=self.view;self.view.show();self.rebind();browser.sync(force=True)
        self.placeholder.deleteLater();browser.floating=None;super().closeEvent(event)
