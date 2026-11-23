from PySide6.QtCore import Qt,QPoint
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel,QToolButton,QApplication
from menus import menu_icon
from motion import fade_popup

class AnchorPopup(QFrame):
    def __init__(self,browser,anchor,width=440):
        super().__init__(browser,Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint);self.browser=browser;self.anchor=anchor;self.setObjectName('novaPopup');self.setFixedWidth(width)
        self.setStyleSheet('QFrame#novaPopup{background:#19191d;border:1px solid #3a3a42;border-radius:12px}QWidget{color:#dcdce4}QLabel{background:transparent;border:0;color:#a3a3af;font-size:12px}QToolButton{background:transparent;border:0;border-radius:6px;padding:5px}QToolButton:hover{background:#33333c}QPushButton{background:#2a2a32;color:#dddde6;border:1px solid #43434e;border-radius:7px;padding:7px 12px}QScrollArea{border:0;background:transparent}QScrollBar:vertical{width:5px;background:transparent}QScrollBar::handle:vertical{background:#4b4b56;border-radius:2px;min-height:25px}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}')
        self.body=QVBoxLayout(self);self.body.setContentsMargins(17,16,17,13);self.body.setSpacing(14)
    def heading(self,title,symbol):
        row=QHBoxLayout();image=QLabel();image.setPixmap(menu_icon(symbol).pixmap(22,22));row.addWidget(image);label=QLabel(title);label.setStyleSheet('font-size:16px;font-weight:600;color:#eeeef2');row.addWidget(label);row.addStretch();close=QToolButton();close.setIcon(menu_icon('close',16));close.setToolTip('Fermer');close.setCursor(Qt.CursorShape.ArrowCursor);close.clicked.connect(self.close);row.addWidget(close);self.body.addLayout(row)
    def reposition(self):
        action=next((a for a in self.browser.bar.actions() if a.text()==self.anchor),None);widget=self.browser.bar.widgetForAction(action) if action else self.browser.bar
        point=widget.mapToGlobal(QPoint(widget.width()-self.width(),widget.height()+7));screen=QApplication.screenAt(point) or self.browser.screen();area=screen.availableGeometry();point.setX(max(area.left()+8,min(point.x(),area.right()-self.width()-8)));point.setY(max(area.top()+8,min(point.y(),area.bottom()-self.height()-8)));self.move(point)
    def open_popup(self):
        if self.browser._private_locked:return
        if self.isVisible():self.close();return
        self.adjustSize();self.reposition();self.show();self.raise_()
    def showEvent(self,event):
        super().showEvent(event);fade_popup(self,self.browser)
