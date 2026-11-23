import sys,unittest,uuid,json,time
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from security import suspicious,download_warning,sensitive_link,without_sensitive,upgrade_http

class RulesTest(unittest.TestCase):
    def test_domain_warnings_do_not_flag_real_brand_domains(self):
        self.assertFalse(suspicious('https://accounts.google.com/'))
        self.assertTrue(suspicious('https://google.com.evil.test/'))
        self.assertTrue(suspicious('https://gооgle.test/'))
    def test_download_and_sensitive_link_checks(self):
        self.assertTrue(download_warning('photo.jpg.exe'));self.assertFalse(download_warning('photo.jpg'))
        url='https://example.test/reset?token=private&q=hello'
        self.assertTrue(sensitive_link(url));self.assertEqual(without_sensitive(url),'https://example.test/reset?q=hello')
        self.assertEqual(upgrade_http('http://example.test/a'),'https://example.test/a');self.assertEqual(upgrade_http('http://localhost/a'),'http://localhost/a')
    def test_signed_updates_reject_tampering_and_other_keys(self):
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        import update_signature
        key=Ed25519PrivateKey.generate();public=base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
        data={'version':'4.0.0','size':123,'sha256':'a'*64};data['signature']=base64.b64encode(key.sign(update_signature.canonical(data))).decode()
        asset={'size':123,'digest':'sha256:'+'a'*64}
        with patch.object(update_signature,'UPDATE_PUBLIC_KEY',public):
            self.assertTrue(update_signature.verify_manifest(data,asset,'v4.0.0'))
            self.assertFalse(update_signature.verify_manifest(dict(data,size=124),asset,'v4.0.0'))
            self.assertFalse(update_signature.verify_manifest(data,asset,'v4.0.1'))
        self.assertFalse(update_signature.verify_manifest(data,asset,'v4.0.0'))

class PrivacyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaPrivacyTest-'+uuid.uuid4().hex)
    def tearDown(self):
        from main import Browser
        from PySide6.QtCore import QCoreApplication,QEvent
        for w in self.app.topLevelWidgets():
            if isinstance(w,Browser):w.close();w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def test_private_profile_never_persists_or_calls_online_suggestions(self):
        from main import Browser,QUrl
        b=Browser(private=True);self.assertTrue(b.profile.isOffTheRecord());self.assertIsNone(b.vault)
        b.loaded(b.current(),True);b.resolve('private search');b.save();b._session_ready=True;b.save_session()
        self.assertFalse(b.datafile.exists());self.assertEqual(b.data['history'],[]);self.assertNotIn('recent_searches',b.data);self.assertNotIn('session',b.data)
        with patch.object(b.ai.network,'post') as post:b.ai.request('address','private query',lambda *a:None);b.ai.send();post.assert_not_called()
        self.assertIn('Vous êtes en navigation privée',b.home_markup());self.assertNotIn('#bd57ff',b.home_markup());b.close()
    def test_form_close_guard_and_permission_expiry(self):
        from main import Browser
        b=Browser();v=b.current();v._dirty=True
        from ui import NovaMessage
        with patch.object(NovaMessage,'question',return_value=NovaMessage.StandardButton.No):self.assertFalse(b.confirm_close(v))
        v._dirty=False;b.grants[('https://example.test','AudioCapture')]=(time.monotonic()-1,v)
        with patch.object(b,'revoke_site') as revoke:b.expire_permissions();revoke.assert_called_once_with(v)
        b.close()
    def test_startup_registry_uses_quoted_executable(self):
        import startup
        with patch.object(sys,'frozen',True,create=True),patch.object(startup.winreg,'CreateKey'),patch.object(startup.winreg,'SetValueEx') as write:
            self.assertTrue(startup.set_startup(True));self.assertTrue(write.call_args.args[-1].startswith('"'));self.assertTrue(write.call_args.args[-1].endswith('" --startup'))
    def test_user_login_popup_returns_to_its_opener(self):
        import threading
        from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
        from main import Browser,Qt,QUrl
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                body=("<script>opener.postMessage('returned','*');window.close()</script>" if self.path=='/child' else "<button style='width:200px;height:100px' onclick=\"document.title='clicked';let login=window.open('about:blank','login','width=500,height=500');login.location='/child'\">Login</button><script>addEventListener('message',e=>{if(e.data==='returned')document.title='auth-returned'})</script>").encode()
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        b=Browser();b.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);b.show();v=b.current()
        def wait(test,seconds=5):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                self.app.processEvents()
                if test():return True
                time.sleep(.01)
            return False
        try:
            v.setUrl(QUrl('http://127.0.0.1:'+str(server.server_port)+'/'))
            self.assertTrue(wait(lambda:not v.page().isLoading() and v.url().host()=='127.0.0.1'))
            QTest.mouseClick(v.focusProxy() or v,Qt.MouseButton.LeftButton,pos=QPoint(70,40))
            self.assertTrue(wait(lambda:v.title()=='auth-returned'),str((v.title(),b.tabs.count(),b.events)));self.assertTrue(wait(lambda:b.tabs.count()==1))
        finally:b.close();server.shutdown();server.server_close()
