"""Shared subtle motion and a locally bundled water chime."""
import time
from pathlib import Path
from PySide6.QtCore import QUrl,QPropertyAnimation,QPoint,QEasingCurve
from PySide6.QtWidgets import QApplication

def enter(widget,browser):
    from motion import enabled,fade_popup
    fade_popup(widget,browser)
    if enabled(browser):
        position=widget.pos();animation=QPropertyAnimation(widget,b'pos',widget);animation.setDuration(140);animation.setStartValue(position+QPoint(0,10));animation.setEndValue(position);animation.setEasingCurve(QEasingCurve.Type.OutCubic);widget._entry_animation=animation;animation.start()

def sound(browser):
    app=QApplication.instance()
    if app.applicationName()!='NovaBrowser' or not browser.data['preferences'].get('notification_sounds',True):return
    now=time.monotonic()
    if now-float(app.property('nova_last_sound') or 0)<1:return
    try:
        from PySide6.QtMultimedia import QSoundEffect
        effect=getattr(app,'_nova_sound',None)
        if effect is None:
            effect=QSoundEffect(app);effect.setSource(QUrl.fromLocalFile(str(Path(__file__).parent/'assets'/'notification-water.wav')));effect.setVolume(.16);app._nova_sound=effect
        app.setProperty('nova_last_sound',now);effect.play()
    except (ImportError,RuntimeError):pass
