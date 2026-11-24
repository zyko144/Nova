import sys,uuid,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Browser,Qt,QUrl
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QWidget,QPushButton
from PySide6.QtTest import QTest
from downloads import NativeDownload
from ui import NovaDialog
from updater import UpdateToast

class BrowserPolishTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaPolishTest-'+uuid.uuid4().hex)
    def setUp(self):
        self.b=Browser();self.b.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);self.b.show()
    def tearDown(self):
        self.b.close();self.b.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def test_new_tab_keeps_address_focus_when_home_loads(self):
        self.b.new_tab();self.assertIs(self.b.focusWidget(),self.b.address);QTest.qWait(250);self.assertIs(self.b.focusWidget(),self.b.address)
        self.b.address.setText('ma recherche');QTest.qWait(50);self.assertEqual(self.b.address.text(),'ma recherche')
    def test_permission_decision_survives_repeated_request_and_alias(self):
        view=self.b.current();delivered=Mock()
        def choose(dialog):
            names=[button.text() for button in dialog.findChildren(QPushButton)]
            self.assertNotIn('10 minutes',names);self.assertNotIn('Cette fois',names)
            next(button for button in dialog.findChildren(QPushButton) if button.text()=='Autoriser').click();return NovaDialog.DialogCode.Accepted
        with patch.object(view,'url',return_value=QUrl('https://pinterest.com/')),patch.object(NovaDialog,'exec',choose):self.b.ask_permission(view,'https://pinterest.com/','AudioCapture',delivered)
        delivered.assert_called_once_with(True);self.assertTrue(self.b.data['site_permissions']['https://pinterest.com']['microphone'])
        self.b.grants.clear();delivered.reset_mock()
        with patch.object(NovaDialog,'exec',side_effect=AssertionError('Repeated prompt')):self.b.ask_permission(view,'https://pinterest.com','MediaAudioCapture',delivered)
        delivered.assert_called_once_with(True)
    def test_closed_download_view_is_kept_until_transfer_finishes(self):
        view=QWidget(self.b);view.send=Mock();view.stop=Mock();item=NativeDownload(view,'download','test.zip');panel=self.b.download_panel;panel.add(item,'test.zip');parent=view.parent()
        self.assertTrue(panel.retain_view(view));self.assertIs(view.parent(),parent);self.assertIs(item.parent(),self.b);view.stop.assert_not_called()
        item.update({'state':'DownloadCompleted','received':100,'total':100});self.assertNotIn(view,panel.retained_views);view.stop.assert_called_once()
    def test_toast_has_transparent_rounded_corners(self):
        with patch.object(UpdateToast,'show',lambda toast:None):toast=UpdateToast(self.b,'Notification','Votre choix est retenu.',silent=True)
        toast.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);toast.show();self.app.processEvents();image=toast.grab().toImage();self.assertEqual(image.pixelColor(0,0).alpha(),0);self.assertGreater(image.pixelColor(20,20).alpha(),200);toast.close()
    def test_notification_sound_can_be_disabled(self):
        from notification_effects import sound
        original=self.app.applicationName();self.app.setApplicationName('NovaBrowser');self.b.data['preferences']['notification_sounds']=False
        try:
            with patch('PySide6.QtMultimedia.QSoundEffect') as effect:sound(self.b);effect.assert_not_called()
        finally:self.app.setApplicationName(original)
