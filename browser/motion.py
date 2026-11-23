"""Short visual transitions; no navigation or close action waits for them."""
import ctypes,sys
from PySide6.QtCore import Qt,QPropertyAnimation,QEasingCurve

def enabled(browser):
    if browser is not None and not browser.data['preferences'].get('animations',True):return False
    if sys.platform=='win32':
        value=ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(value),0) and not value.value:return False
    return True

def fade_popup(widget,browser=None):
    old=getattr(widget,'_nova_fade',None)
    if old:old.stop();old.deleteLater()
    if not enabled(browser):widget.setWindowOpacity(1);return
    animation=QPropertyAnimation(widget,b'windowOpacity',widget);animation.setDuration(90);animation.setStartValue(.72);animation.setEndValue(1.0);animation.setEasingCurve(QEasingCurve.Type.OutCubic);widget._nova_fade=animation;animation.start()

def close_tab(tabbar,index,browser):
    """Fade a mouse-transparent snapshot; the real tab is removed immediately."""
    from PySide6.QtWidgets import QLabel,QGraphicsOpacityEffect
    old=getattr(tabbar,'_closing_ghost',None)
    if old is not None:
        old.hide();old.deleteLater();tabbar._closing_ghost=None
    if not enabled(browser) or not tabbar.isVisible():return
    rect=tabbar.tabRect(index).intersected(tabbar.rect())
    if rect.isEmpty():return
    snapshot=tabbar.grab(rect)
    ghost=QLabel(tabbar);ghost.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True);ghost.setPixmap(snapshot);ghost.setGeometry(rect)
    effect=QGraphicsOpacityEffect(ghost);ghost.setGraphicsEffect(effect)
    animation=QPropertyAnimation(effect,b'opacity',ghost);animation.setDuration(90);animation.setStartValue(.45);animation.setEndValue(0.0);animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    tabbar._closing_ghost=ghost;ghost._animation=animation
    def finished():
        if getattr(tabbar,'_closing_ghost',None) is ghost:tabbar._closing_ghost=None
        ghost.deleteLater()
    animation.finished.connect(finished);ghost.show();ghost.raise_();animation.start()
