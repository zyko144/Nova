import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from updater import version_tuple,release_asset
from PySide6.QtCore import QObject,Signal,QByteArray,QTimer,QUrl
from PySide6.QtNetwork import QNetworkRequest

class UpdateTest(unittest.TestCase):
    def test_qt_reply_header_and_cached_release(self):
        import uuid
        from main import QApplication,Browser
        app=QApplication.instance() or QApplication([]);app.setApplicationName('NovaUpdaterTest-'+uuid.uuid4().hex)
        browser=Browser();updater=browser.updater;notifications=[];updater.notify=lambda *args:notifications.append(args)
        class Reply(QObject):
            finished=Signal()
            def __init__(self,status):super().__init__();self.status=status
            def attribute(self,key):return self.status
            def readAll(self):return QByteArray(b'{"tag_name":"v3.3.0","draft":false,"prerelease":false,"assets":[]}')
            def rawHeader(self,key):
                if not isinstance(key,str):raise TypeError('Qt 6.12 requires a string header name')
                return QByteArray(b'"test-etag"')
        class Network:
            def get(self,request):
                self.reply=Reply(304 if request.hasRawHeader('If-None-Match') else 200)
                QTimer.singleShot(0,self.reply.finished.emit);return self.reply
        updater.network=Network();updater.check();app.processEvents()
        self.assertEqual(updater.available['tag_name'],'v3.3.0');self.assertEqual(updater.etag,b'"test-etag"');self.assertEqual(len(notifications),1)
        updater.check();app.processEvents();self.assertEqual(updater.available['tag_name'],'v3.3.0');self.assertFalse(updater.busy)
        browser.close();app.processEvents()
    def test_versions_and_verified_assets(self):
        self.assertGreater(version_tuple('v3.3.0'),version_tuple('3.2.0'))
        self.assertIsNone(version_tuple('../../3.3.0'))
        release={'tag_name':'v3.3.0','assets':[{'name':'NovaBrowser-Windows-x64.zip','size':100,'digest':'sha256:'+'a'*64,'browser_download_url':'https://github.com/zyko144/Nova/releases/download/v3.3.0/NovaBrowser-Windows-x64.zip'}]}
        self.assertIsNotNone(release_asset(release))
        for mutation in [lambda r:r['assets'][0].update(digest=''),lambda r:r['assets'][0].update(browser_download_url='https://evil.example/update.zip'),lambda r:r.update(prerelease=True),lambda r:r['assets'][0].update(size=-1)]:
            bad=copy.deepcopy(release);mutation(bad);self.assertIsNone(release_asset(bad))
if __name__=='__main__':unittest.main()
