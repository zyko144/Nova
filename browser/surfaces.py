"""Rounded backplates and physical clipping for popup viewports."""
from PySide6.QtCore import QObject,QEvent,QRectF,Qt
from PySide6.QtGui import QPainter,QPainterPath,QRegion,QColor
from PySide6.QtWidgets import QFrame

class RoundedFrame(QFrame):
    def __init__(self,parent=None,flags=Qt.WindowType.Widget):
        super().__init__(parent,flags);self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,True)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source);painter.fillRect(self.rect(),Qt.GlobalColor.transparent);painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver);painter.setPen(QColor('#3a3a42'));painter.setBrush(QColor(getattr(self,'popup_color','#19191d')));painter.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),16,16)

class RoundedPopupFilter(QObject):
    def __init__(self,widget,radius):super().__init__(widget);self.radius=radius
    def eventFilter(self,widget,event):
        if event.type() in (QEvent.Type.Show,QEvent.Type.Resize):
            path=QPainterPath();path.addRoundedRect(QRectF(widget.rect()),self.radius,self.radius);widget.setMask(QRegion(path.toFillPolygon().toPolygon()))
        return False

def round_popup(widget,radius=14):
    if getattr(widget,'_rounding_filter',None):return
    widget._rounding_filter=RoundedPopupFilter(widget,radius);widget.installEventFilter(widget._rounding_filter)
