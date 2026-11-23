"""User consent through Windows Hello; unavailable/failed verification fails closed."""
import subprocess,threading
from PySide6.QtCore import QObject,Signal

class Hello(QObject):
    result=Signal(bool)
    def __init__(self,parent):super().__init__(parent);self.busy=False;self.result.connect(self.finished);self.callback=None
    def verify(self,callback):
        if self.busy:return
        self.busy=True;self.callback=callback;handle=str(int(self.parent().winId()))
        def worker():
            try:
                from media_view import helper_path
                r=subprocess.run([str(helper_path()),'--hello',handle],capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
                ok=r.returncode==0 and r.stdout.strip()=='VERIFIED'
            except (OSError,subprocess.TimeoutExpired):ok=False
            try:self.result.emit(ok)
            except RuntimeError:pass
        threading.Thread(target=worker,daemon=True).start()
    def finished(self,ok):
        callback=self.callback;self.callback=None;self.busy=False
        if not ok:
            from ui import NovaMessage
            NovaMessage.information(self.parent(),'Coffre verrouillé','Windows Hello n’a pas validé le déverrouillage ou n’est pas disponible. Aucun mot de passe n’a été rempli.')
        if callback:callback(ok)
