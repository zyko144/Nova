import sys,tempfile,unittest,uuid,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from private_access import PrivateStore

class StoreTest(unittest.TestCase):
    def test_confirmation_encryption_and_recovery_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private.dat';s=PrivateStore(path)
            with self.assertRaises(ValueError):s.configure('729184','729185')
            self.assertFalse(path.exists());recovery=s.configure('729184','729184')
            self.assertNotIn(b'729184',path.read_bytes());self.assertNotIn(recovery.encode(),path.read_bytes());self.assertTrue(PrivateStore(path).verify('729184'));self.assertTrue(s.verify(recovery,True))
            old=s.data['salt'];s.configure('839275','839275');self.assertNotEqual(old,s.data['salt']);self.assertFalse(s.verify(recovery,True));self.assertFalse(s.verify('729184'));self.assertTrue(s.verify('839275'))
    def test_attempt_limit_survives_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private.dat';s=PrivateStore(path);s.configure('729184','729184')
            with patch('private_access.time.time',return_value=1000):
                for i in range(5):self.assertFalse(s.verify('000000'))
                self.assertGreater(PrivateStore(path).remaining(),0);self.assertFalse(PrivateStore(path).verify('729184'))
            with patch('private_access.time.time',return_value=1031):self.assertTrue(PrivateStore(path).verify('729184'))
    def test_corrupt_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'private.dat';p.write_bytes(b'not-a-protected-record');s=PrivateStore(p);self.assertTrue(s.corrupt);self.assertFalse(s.verify('729184'))

class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaPrivateGate-'+uuid.uuid4().hex)
    def tearDown(self):
        from main import Browser
        from PySide6.QtCore import QCoreApplication,QEvent
        for b in self.app.topLevelWidgets():
            if isinstance(b,Browser):b.close();b.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def test_no_window_created_without_access(self):
        from main import Browser
        b=Browser()
        with patch('private_access.PrivateAccess.request',return_value=False),patch('main.Browser') as constructor:
            self.assertIsNone(b.private_window());constructor.assert_not_called()
        b.close()
    def test_disabled_text_services_block_network_and_translation(self):
        from main import Browser
        b=Browser();b.data['preferences']['ai_suggestions']=True;b.set_text_services(False)
        with patch.object(b.ai.network,'post') as post,patch.object(b,'new_tab') as new,patch.object(b.updater,'notify'):
            b.ai.request('address','maison',lambda *a:None);b.ai.send();post.assert_not_called();b.translate_french('texte de test');new.assert_not_called()
        b.set_text_services(True);b.data['preferences']['online_translation']=False
        with patch.object(b,'new_tab') as new,patch.object(b.updater,'notify'):b.translate_french('texte de test');new.assert_not_called()
        b.close()
    def test_locked_private_content_cannot_be_exported(self):
        from main import Browser,Qt
        b=Browser(private=True);b.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);b.show();b.lock_private_window();self.assertTrue(b._private_locked);self.assertTrue(b.tabs.isHidden());self.assertTrue(b.chrome.isHidden())
        with patch('features.QFileDialog.getSaveFileName') as dialog:b.capture_page();dialog.assert_not_called()
        with patch('private_access.PrivateAccess.request',return_value=False):b.unlock_private_window();self.assertTrue(b._private_locked)
        with patch('private_access.PrivateAccess.request',return_value=True):b.unlock_private_window();self.assertFalse(b._private_locked);self.assertFalse(b.tabs.isHidden())
        b.close()
    def test_first_entry_creates_confirmed_code_with_recovery_ack(self):
        from main import Browser,Qt
        from private_access import PrivateAccess
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QLineEdit,QPushButton,QCheckBox,QLabel
        b=Browser();access=PrivateAccess(b);original=access.dialog;stages=[]
        with tempfile.TemporaryDirectory() as directory:
            access.store=PrivateStore(Path(directory)/'code.dat')
            def hidden(*args):
                d=original(*args);d.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);return d
            drive=QTimer(b);drive.setInterval(25);timeout=QTimer(b);timeout.setSingleShot(True)
            def step():
                d=self.app.activeModalWidget()
                if not d:return
                heading=d.findChild(QLabel,'heading').text()
                if heading=='Créer votre code privé':
                    fields=d.findChildren(QLineEdit);fields[0].setText('729184');fields[1].setText('729184');stages.append('confirmed')
                    next(x for x in d.findChildren(QPushButton) if x.text()=='Créer le code').click()
                elif heading=='Conservez votre code de secours':
                    d.findChild(QCheckBox).setChecked(True);stages.append('recovery')
                    next(x for x in d.findChildren(QPushButton) if x.text()=='Continuer').click()
            drive.timeout.connect(step);timeout.timeout.connect(lambda:self.app.activeModalWidget().reject() if self.app.activeModalWidget() else None)
            with patch.object(access,'dialog',side_effect=hidden):
                drive.start();timeout.start(3000)
                try:self.assertTrue(access.setup())
                finally:drive.stop();timeout.stop()
            self.assertEqual(stages,['confirmed','recovery']);self.assertTrue(access.store.verify('729184'))
        b.close()
