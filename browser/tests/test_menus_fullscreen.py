import sys,uuid,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Browser,Qt
from menus import build_main_menu
from PySide6.QtCore import QCoreApplication,QEvent

class MenuFullscreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaMenusTest-'+uuid.uuid4().hex)
    def tearDown(self):
        for w in self.app.topLevelWidgets():
            if isinstance(w,Browser):w.close();w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def window(self):
        b=Browser();b.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);b.show();return b
    def test_close_is_immediate_and_animation_can_be_disabled(self):
        b=self.window();b.new_tab();count=b.tabs.count()
        with patch('motion.enabled',return_value=True):b.close_tab(0)
        self.assertEqual(b.tabs.count(),count-1)
        ghost=getattr(b.top_tabs,'_closing_ghost',None)
        if ghost is not None:self.assertTrue(ghost.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        b.data['preferences']['animations']=False
        from motion import enabled
        self.assertFalse(enabled(b))
        b.new_tab();b.close_tab(0);self.assertIsNone(getattr(b.top_tabs,'_closing_ghost',None));b.close()
    def test_image_menu_uses_engine_download_and_clipboard_actions(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from main import NovaWebView,QUrl,QWebEnginePage,QPoint
        from menus import NovaMenu
        b=self.window();view=NovaWebView(b);page=Mock()
        request=SimpleNamespace(linkUrl=lambda:QUrl(),mediaUrl=lambda:QUrl('data:image/png;base64,AA=='),mediaType=lambda:SimpleNamespace(name='MediaTypeImage'),selectedText=lambda:'',isContentEditable=lambda:False)
        def choose(menu,point):
            names=[a.text() for a in menu.actions()]
            self.assertIn('Copier l’image',names)
            next(a for a in menu.actions() if a.text()=='Enregistrer l’image sous…').trigger()
        with patch.object(view,'lastContextMenuRequest',return_value=request),patch.object(view,'page',return_value=page),patch.object(NovaMenu,'exec',choose):
            view.contextMenuEvent(SimpleNamespace(globalPos=lambda:QPoint()))
        page.triggerAction.assert_called_once_with(QWebEnginePage.WebAction.DownloadImageToDisk)
        view.deleteLater();b.close()
    def test_menu_keeps_actions_and_hides_personal_groups_in_presentation(self):
        b=self.window();menu=build_main_menu(b);actions=[a for a in menu.actions() if a.text()]
        self.assertEqual(sum(a.text()=='Compte Google' for a in actions),1)
        self.assertTrue(all(not a.icon().isNull() for a in actions))
        count=b.tabs.count();next(a for a in actions if a.text().startswith('Nouvel onglet')).trigger();self.assertEqual(b.tabs.count(),count+1)
        menu.deleteLater();b.presentation=True;private=build_main_menu(b)
        self.assertFalse(any(a.text() in ('Compte Google','Historique','Favoris','Profils locaux') for a in private.actions()));private.deleteLater();b.close()
    def test_leaving_video_restores_each_browser_window_state(self):
        b=self.window();v=b.current()
        for enter,state in [(b.showFullScreen,'full'),(b.showNormal,'normal')]:
            enter();self.app.processEvents();b.fullscreen(True,v);b.fullscreen(True,v);self.assertTrue(b.chrome.isHidden());b.fullscreen(False,v);self.assertFalse(b.chrome.isHidden())
            self.assertEqual(b.isFullScreen(),state=='full');self.assertEqual(b.isMaximized(),state=='max')
            b.fullscreen(False,v);self.assertEqual(b.isFullScreen(),state=='full')
        # Windows does not maximize a WA_DontShowOnScreen surface; verify the
        # restoration call for an actual maximized state independently.
        with patch.object(b,'windowState',return_value=Qt.WindowState.WindowMaximized):b.fullscreen(True,v)
        with patch.object(b,'showMaximized') as maximize:b.fullscreen(False,v);maximize.assert_called_once_with()
        b.close()
    def test_switching_video_tab_and_f11_preserve_browser_fullscreen(self):
        b=self.window();v=b.current();b.showFullScreen();b.fullscreen(True,v);b.new_tab();self.assertTrue(b.isFullScreen());self.assertFalse(b.chrome.isHidden())
        v=b.current();b.fullscreen(True,v);b.toggle_browser_fullscreen();self.assertTrue(b.isFullScreen());self.assertFalse(b.chrome.isHidden());self.assertFalse(b._video_fullscreen_active)
        b.toggle_browser_fullscreen();self.assertFalse(b.isFullScreen());b.close()
