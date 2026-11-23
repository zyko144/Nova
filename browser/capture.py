from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Qt,QRect,QPoint
from PySide6.QtGui import QPainter,QColor,QPen

class RegionCapture(QDialog):
    def __init__(self,parent,pixmap):
        super().__init__(parent,Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint);self.picture=pixmap;self.anchor=QPoint();self.area=QRect();self.result_pixmap=None;self.resize(pixmap.size());self.setCursor(Qt.CursorShape.CrossCursor)
    def paintEvent(self,event):
        p=QPainter(self);p.drawPixmap(0,0,self.picture);p.fillRect(self.rect(),QColor(0,0,0,115))
        if not self.area.isNull():p.drawPixmap(self.area,self.picture,self.area);p.setPen(QPen(QColor('#ddd'),1));p.drawRect(self.area)
        p.setPen(QColor('#fff'));p.drawText(18,28,'Glissez pour sélectionner une zone · Échap pour annuler')
    def mousePressEvent(self,event):self.anchor=event.position().toPoint();self.area=QRect(self.anchor,self.anchor);self.update()
    def mouseMoveEvent(self,event):self.area=QRect(self.anchor,event.position().toPoint()).normalized().intersected(self.rect());self.update()
    def mouseReleaseEvent(self,event):
        if self.area.width()>8 and self.area.height()>8:self.result_pixmap=self.picture.copy(self.area);self.accept()
