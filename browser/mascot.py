"""Nova's generated glass mascot: occasional sprite changes, no idle render loop."""
import random
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QSize,Signal,QRectF
from PySide6.QtGui import QImageReader,QPixmap,QPainter,QPainterPath
from PySide6.QtWidgets import QWidget,QApplication
from motion import enabled

class Mascot(QWidget):
    stateChanged=Signal()
    def __init__(self,browser,parent=None):
        super().__init__(parent);self.browser=browser;self.state=0;self.frames=[];self.setMinimumSize(220,200);self.setMaximumSize(470,380)
        for name in ('nova-mascot.png','nova-mascot-blink.png','nova-mascot-glance.png'):
            reader=QImageReader(str(Path(__file__).parent/'assets'/name));reader.setScaledSize(QSize(1024,683));self.frames.append(QPixmap.fromImage(reader.read()))
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.animate)
        self.return_timer=QTimer(self);self.return_timer.setSingleShot(True);self.return_timer.timeout.connect(self.neutral)
        browser.preferenceChanged.connect(self.preference_changed);QApplication.instance().applicationStateChanged.connect(self.activity_changed)
    def preference_changed(self,key,value):
        if key=='animations':self.refresh_activity()
    def activity_changed(self,*args):self.refresh_activity()
    def refresh_activity(self):
        active=self.isVisible() and enabled(self.browser) and QApplication.instance().applicationState()==Qt.ApplicationState.ApplicationActive
        if active:
            if not self.timer.isActive():self.timer.start(random.randint(2800,6000))
        else:self.timer.stop();self.return_timer.stop();self.neutral()
    def animate(self):
        if not self.isVisible() or not enabled(self.browser):return
        self.state=1 if random.randrange(4)!=0 else 2;self.update();self.stateChanged.emit();self.return_timer.start(130 if self.state==1 else 900);self.timer.start(random.randint(4000,7500))
    def neutral(self):self.state=0;self.update();self.stateChanged.emit()
    def showEvent(self,event):super().showEvent(event);self.refresh_activity()
    def hideEvent(self,event):super().hideEvent(event);self.timer.stop();self.return_timer.stop();self.neutral()
    def enterEvent(self,event):
        super().enterEvent(event)
        if enabled(self.browser):self.state=2;self.update();self.stateChanged.emit();self.return_timer.start(900)
    def paintEvent(self,event):
        neutral=self.frames[0]
        if neutral.isNull():
            return
        painter=QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.SmoothPixmapTransform)
        size=neutral.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
        x=(self.width()-size.width())/2
        y=(self.height()-size.height())/2
        painter.translate(x,y)
        painter.scale(size.width()/1536,size.height()/1024)
        target=QRectF(0,0,1536,1024)
        painter.drawPixmap(target,neutral,QRectF(neutral.rect()))
        frame=self.frames[self.state]
        if self.state and not frame.isNull():
            eyes=QPainterPath()
            eyes.addRoundedRect(QRectF(872,509,110,124),19,19)
            eyes.addRoundedRect(QRectF(1050,477,104,111),17,17)
            painter.setClipPath(eyes)
            painter.drawPixmap(target,frame,QRectF(frame.rect()))
