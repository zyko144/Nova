"""Hidden native HTTP transfer: closing its tab must not cancel the download."""
import hashlib,sys,time,threading,tempfile,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Browser,QUrl,Qt
from PySide6.QtWidgets import QFileDialog
from PySide6.QtTest import QTest

payload=(b'Nova native download test\n'*260000)[:6*1024*1024]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename="transfer.bin"');self.send_header('Content-Length',str(len(payload)));self.end_headers()
        try:
            for offset in range(0,len(payload),65536):self.wfile.write(payload[offset:offset+65536]);self.wfile.flush();time.sleep(.025)
        except (BrokenPipeError,ConnectionResetError):pass
    def log_message(self,*args):pass

def wait(predicate,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        QTest.qWait(20)
        if predicate():return
    raise AssertionError('Native transfer timed out')

server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
app=QApplication([]);app.setApplicationName('NovaTransferTest-'+uuid.uuid4().hex)
b=Browser();b.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);b.download_panel.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);b.data['welcome_completed']=True;b.show();b.updater.notify=lambda *args,**kwargs:None
try:
    with tempfile.TemporaryDirectory(prefix='Nova-download-test-') as folder,patch.object(QFileDialog,'getSaveFileName',return_value=(str(Path(folder)/'transfer.bin'),'')):
        b.open_media(QUrl(f'http://127.0.0.1:{server.server_port}/transfer.bin'));view=b.current()
        wait(lambda:bool(b.download_panel.items) and b.download_panel.items[0].item.receivedBytes()>0)
        item=b.download_panel.items[0].item
        assert item.state().name=='DownloadInProgress'
        b.close_tab(b.tabs.indexOf(view));assert view in b.download_panel.retained_views and not view.stopping
        wait(lambda:item.state().name=='DownloadCompleted')
        saved=Path(folder)/'transfer.bin';assert hashlib.sha256(saved.read_bytes()).digest()==hashlib.sha256(payload).digest()
        assert view not in b.download_panel.retained_views
        print(f'PASS: {len(payload)} bytes completed after closing native tab, hash verified')
finally:
    b.close();QTest.qWait(1000);server.shutdown()
