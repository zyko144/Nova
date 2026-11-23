from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRectF,QPoint
from PySide6.QtGui import QPainter,QColor,QPixmap,QIcon,QFont,QBitmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,
    QDialogButtonBox,QMessageBox as OriginalMessageBox,QTabBar,QToolButton,QGridLayout,QFrame)

ASSETS=Path(__file__).parent/'assets'
CONTROL_NAMES=['back','forward','reload','home','star','download','extensions','profile','settings','vpn','plus','close','min','max','search','video']
_icons={}
def generated_icon(name,size=24):
    if name not in CONTROL_NAMES:return QIcon()
    key=(name,size)
    if key not in _icons:
        atlas=QPixmap(str(ASSETS/'nova-controls.png'))
        if atlas.isNull():return QIcon()
        index=CONTROL_NAMES.index(name); col=index%4;row=index//4
        x=round(col*atlas.width()/4);y=round(row*atlas.height()/4)
        rect=(x,y,round((col+1)*atlas.width()/4)-x,round((row+1)*atlas.height()/4)-y)
        # Sampling a sprite cell is performed at render time, preserving source artwork.
        cell=atlas.copy(*rect)
        cell.setMask(QBitmap.fromImage(cell.toImage().createAlphaMask()))
        _icons[key]=QIcon(cell.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    return _icons[key]

DIALOG_STYLE='''QDialog{background:#0b0811;color:#f3eefa;border:1px solid #39234e;border-radius:22px}QLabel{color:#c3b6d4;background:transparent;font-size:13px}QLabel#heading{color:#f8f3ff;font-size:23px;font-weight:600}QLineEdit{background:#050408;color:#f4edf9;border:1px solid #30203f;border-radius:12px;padding:12px;font-size:14px;min-width:280px}QLineEdit:focus{border-color:#9550ee}QPushButton{background:#1b112a;color:#e5d6fa;border:1px solid #3d2457;border-radius:11px;padding:10px 18px;font-size:13px}QPushButton:hover{background:#2b1743;border-color:#7643a5}QPushButton#primary{background:#7e25df;color:white;border:0}QPushButton#quiet{background:transparent;border:0;padding:6px}'''

class NovaDialog(QDialog):
    def __init__(self,parent,title,subtitle=''):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(neutral_style(DIALOG_STYLE) if getattr(parent,'private',False) else DIALOG_STYLE); self.setMinimumWidth(430)
        self.body=QVBoxLayout(self);self.body.setContentsMargins(26,24,26,24);self.body.setSpacing(16)
        row=QHBoxLayout();heading=QLabel(title);heading.setObjectName('heading');row.addWidget(heading);row.addStretch()
        close=QPushButton('×');close.setFixedSize(28,28);close.setObjectName('quiet');close.clicked.connect(self.reject);row.addWidget(close);self.body.addLayout(row)
        if subtitle:
            label=QLabel(subtitle);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);self.body.addWidget(label)
    def buttons(self,accept='Valider',cancel='Annuler'):
        row=QHBoxLayout();row.addStretch()
        no=QPushButton(cancel);no.clicked.connect(self.reject);row.addWidget(no)
        yes=QPushButton(accept);yes.setObjectName('primary');yes.clicked.connect(self.accept);row.addWidget(yes)
        self.body.addLayout(row);return yes
    def mousePressEvent(self,event):
        if event.position().y()<60 and self.windowHandle():self.windowHandle().startSystemMove()

class NovaInput:
    @staticmethod
    def getText(parent,title,label,*args,**kwargs):
        dialog=NovaDialog(parent,title,label);edit=QLineEdit();edit.setText(kwargs.get('text',''));edit.setEchoMode(kwargs.get('echo',QLineEdit.EchoMode.Normal));dialog.body.addWidget(edit);dialog.buttons()
        edit.returnPressed.connect(dialog.accept);edit.setFocus()
        ok=dialog.exec()==QDialog.DialogCode.Accepted
        return edit.text(),ok

class NovaMessage:
    StandardButton=OriginalMessageBox.StandardButton
    @staticmethod
    def information(parent,title,text,*args):
        dialog=NovaDialog(parent,title,text);row=QHBoxLayout();row.addStretch();btn=QPushButton('Compris');btn.setObjectName('primary');btn.clicked.connect(dialog.accept);row.addWidget(btn);dialog.body.addLayout(row);dialog.exec()
        return NovaMessage.StandardButton.Ok
    @staticmethod
    def question(parent,title,text,*args):
        dialog=NovaDialog(parent,title,text);dialog.buttons('Autoriser','Annuler')
        return NovaMessage.StandardButton.Yes if dialog.exec()==QDialog.DialogCode.Accepted else NovaMessage.StandardButton.No

SUGGESTIONS=[('YouTube','https://www.youtube.com'),('Google','https://www.google.com'),('Twitch','https://www.twitch.tv'),('Discord','https://discord.com'),('Spotify','https://open.spotify.com'),('GitHub','https://github.com'),('Reddit','https://www.reddit.com'),('Outlook','https://outlook.live.com')]

class ShortcutDialog(NovaDialog):
    def __init__(self,parent,name='',url=''):
        super().__init__(parent,'Modifier le raccourci' if name else 'Ajouter une application','Un site favori, à votre façon. Choisissez une suggestion ou entrez son adresse.')
        self.setMinimumWidth(540)
        suggestions=QGridLayout();suggestions.setSpacing(8)
        for i,(title,address) in enumerate(SUGGESTIONS):
            button=QPushButton(title);button.clicked.connect(lambda checked=False,n=title,u=address:self.choose(n,u));suggestions.addWidget(button,i//4,i%4)
        self.body.addLayout(suggestions)
        self.name=QLineEdit(name);self.name.setPlaceholderText('Nom de l’application')
        self.address=QLineEdit(url);self.address.setPlaceholderText('https://exemple.fr')
        self.body.addWidget(QLabel('Nom'));self.body.addWidget(self.name);self.body.addWidget(QLabel('Adresse du site'));self.body.addWidget(self.address)
        self.error=QLabel('');self.error.setStyleSheet('color:#ef9db3');self.body.addWidget(self.error)
        self.buttons('Enregistrer' if name else 'Ajouter')
    def choose(self,name,url):self.name.setText(name);self.address.setText(url)
    def accept(self):
        from urllib.parse import urlsplit
        url=self.address.text().strip()
        if '://' not in url:url='https://'+url
        parsed=urlsplit(url)
        if not self.name.text().strip() or parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username:
            self.error.setText('Indiquez un nom et une adresse HTTP ou HTTPS valide.');return
        self.address.setText(url);super().accept()

class NovaTabBar(QTabBar):
    def __init__(self,parent=None):
        super().__init__(parent);self.setDrawBase(False);self.setIconSize(QSize(18,18));self.setMouseTracking(True)
        self.setStyleSheet('QTabBar{background:transparent;border:0}QTabBar::tab{height:42px;min-width:220px;padding:0 12px;margin:0;border:0;background:transparent}QTabBar QToolButton{background:transparent;border:0;border-radius:8px;padding:0}QTabBar QToolButton:hover{background:rgba(130,70,200,30)}')
    def available_width(self):return max(80,self.parentWidget().width()-294) if self.parentWidget() else 1000
    def tabSizeHint(self,index):
        view=self.tabData(index)
        if view is not None and getattr(view,'_pinned',False):return QSize(46,54)
        preferred=180 if getattr(self,'compact',False) else 240
        return QSize(max(44,min(preferred,self.available_width()//max(1,self.count()))),54)
    def minimumTabSizeHint(self,index):return self.tabSizeHint(index)
    def sizeHint(self):return QSize(min(self.available_width(),sum(self.tabSizeHint(i).width() for i in range(self.count()))),54)
    def minimumSizeHint(self):return QSize(44,54)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont('Segoe UI',10))
        for i in range(self.count()):
            rect=self.tabRect(i);selected=i==self.currentIndex()
            view=self.tabData(i);state=''
            if view is not None:
                if getattr(view,'_muted',False):state='×♪'
                elif getattr(view,'_floating',False):state='↗'
                elif getattr(view,'_nova_suspended',False):state='Ⅱ'
                elif getattr(view,'_audible',False):state='♪'
                elif hasattr(view,'page'):
                    try:state='♪' if view.page().recentlyAudible() else ''
                    except RuntimeError:pass
            if selected:
                painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#242424' if getattr(self,'private_mode',False) else '#191224'));painter.drawRoundedRect(QRectF(rect).adjusted(0,9,0,-8),15,15)
            pinned=bool(view is not None and getattr(view,'_pinned',False));narrow=rect.width()<85
            close=self.tabButton(i,QTabBar.ButtonPosition.RightSide)
            if close:close.setVisible(not pinned and (not narrow or selected))
            if getattr(self,'show_icons',True) and (pinned or not narrow or not selected):
                image=self.tabIcon(i).pixmap(16,16);painter.drawPixmap(rect.x()+(rect.width()-16)//2 if narrow else rect.x()+14,rect.center().y()-8,image)
            if narrow:continue
            if state:
                painter.setPen(QColor('#b68bdd'));painter.drawText(rect.adjusted(0,0,-33,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,state)
            painter.setPen(QColor('#eeeeee' if selected else '#999999') if getattr(self,'private_mode',False) else QColor('#eee5fa' if selected else '#9488a7'))
            textRect=rect.adjusted(47 if getattr(self,'show_icons',True) else 17,0,-54 if state else -34,0)
            text=painter.fontMetrics().elidedText(self.tabText(i),Qt.TextElideMode.ElideRight,textRect.width())
            painter.drawText(textRect,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,text)


def neutral_style(style):
    import re
    def gray(match):
        c=QColor(match.group());v=round(.2126*c.red()+.7152*c.green()+.0722*c.blue());return '#'+format(v,'02x')*3
    style=re.sub(r'#[0-9a-fA-F]{6}(?![0-9a-fA-F])',gray,style)
    def rgba(match):
        r,g,b,a=match.groups();v=round(.2126*int(r)+.7152*int(g)+.0722*int(b));return f'rgba({v},{v},{v},{a})'
    return re.sub(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)',rgba,style)


def monochrome(icon,size=24):
    pixmap=icon.pixmap(size,size)
    if pixmap.isNull():return icon
    painter=QPainter(pixmap);painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn);painter.fillRect(pixmap.rect(),QColor('#bbbbbb'));painter.end();return QIcon(pixmap)
