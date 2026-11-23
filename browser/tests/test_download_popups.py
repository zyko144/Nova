import json,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import Browser,QApplication,Qt
from PySide6.QtCore import QCoreApplication,QEvent,QPoint
from PySide6.QtWidgets import QWidget
from downloads import NativeDownload
from menus import NovaMenu,native_context_menu,save_context_image
from extensions_panel import Extensions

class DownloadPopupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaPopupTests-'+uuid.uuid4().hex)
    def setUp(self):
        self.browser=Browser();self.browser.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);self.browser.show();self.view=QWidget(self.browser);self.view.send=Mock();self.view.reload=Mock()
    def tearDown(self):
        self.browser.close();self.browser.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def test_native_image_menu_returns_original_command_id(self):
        data={'id':'context-1','items':[{'name':'copyImage','command':50122,'enabled':True}],'kind':'Image','source':'https://i.pinimg.com/image.jpg'}
        def choose(menu,point):next(a for a in menu.actions() if a.text()=='Copier l’image').trigger()
        with patch.object(NovaMenu,'exec',choose):native_context_menu(self.browser,self.view,data)
        command,value=self.view.send.call_args.args;self.assertEqual(command,'context-result');self.assertEqual(json.loads(value),{'id':'context-1','command':50122})
    def test_image_save_uses_nova_dialog_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'pinterest.jpg');url='https://i.pinimg.com/originals/test.jpg'
            with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName',return_value=(path,'')),patch.object(self.browser,'downloads_menu'):
                save_context_image(self.browser,self.view,url)
            command,value=self.view.send.call_args.args;self.assertEqual(command,'save-image');self.assertEqual(json.loads(value)['url'],url);self.assertEqual(json.loads(value)['path'],path);self.assertFalse(Path(path).exists())
    def test_progress_speed_pause_and_remove_preserve_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'image.png';path.write_bytes(b'kept');item=NativeDownload(self.view,'download',str(path));panel=self.browser.download_panel;panel.add(item,str(path));row=panel.items[0]
            with patch('downloads.time.monotonic',return_value=11):
                row.sample=(10,0);row.rate=0;item.update({'received':2000000,'total':10000000});panel.refresh()
            self.assertEqual(row.bar.value(),20);self.assertIn('2.00 Mo/s',row.status.text());row.pause.click();self.assertEqual(json.loads(self.view.send.call_args.args[1])['action'],'pause')
            item.update({'paused':True});row.pause.click();self.assertEqual(json.loads(self.view.send.call_args.args[1])['action'],'resume')
            item.update({'state':'DownloadCompleted'});row.remove();self.assertEqual(path.read_bytes(),b'kept');self.assertFalse(panel.items);self.assertFalse(panel.timer.isActive())
    def test_extensions_use_actual_ids_for_toggle_and_removal(self):
        panel=Extensions(self.browser);panel.view=self.view
        panel.update_data(self.view,{'type':'extensions-state','items':[{'id':'actual-id','name':'Bloqueur','enabled':True,'builtin':True}]})
        self.assertEqual(panel.items[0]['id'],'actual-id')
        with patch.object(panel,'choose_view',return_value=self.view):panel.command('enable',{'id':'actual-id','enabled':False})
        self.assertEqual(self.view.send.call_args.args[0],'extensions-enable');self.assertEqual(json.loads(self.view.send.call_args.args[1]),{'id':'actual-id','enabled':False})
        panel.busy=False
        with patch.object(panel,'choose_view',return_value=self.view):panel.command('remove',{'id':'actual-id'})
        self.assertEqual(self.view.send.call_args.args[0],'extensions-remove');panel.deleteLater()
