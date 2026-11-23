import sys,uuid,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Browser,QUrl,Qt,QPoint,MediaView
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QPushButton
from pages import InternalPage

class InteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaInteractionTest-'+uuid.uuid4().hex)
    def test_home_search_submission_stays_in_nova(self):
        window=Browser();self.assertEqual(window.resolve('python').host(),'www.google.com');window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);window.show();view=window.current();loaded=QSignalSpy(view.loadFinished)
        def wait_for(count):
            deadline=time.monotonic()+8
            while loaded.count()<count and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
            return loaded.count()>=count
        try:
            self.assertTrue(wait_for(1));window.set_search_engine('Nova Search');self.assertTrue(wait_for(2))
            view.page().runJavaScript("document.querySelector('input[name=q]').value='python';document.querySelector('form').requestSubmit()")
            self.assertTrue(wait_for(3));self.assertTrue(view.url().toString().startswith(window.search.base));self.assertTrue(window.address.text().startswith('nova://search?q=python'))
        finally:window.set_search_engine('Google');window.close();self.app.processEvents()
    def test_toolbar_tabs_address_and_compact_settings(self):
        window=Browser();window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);window.show()
        original=window.current();other=window.new_tab();window.tabs.setCurrentWidget(original)
        window.top_tabs.moveTab(0,1);self.assertIs(window.current(),original)
        window.address.setFocus();window.address.setText('adresse en cours');other.urlChanged.emit(QUrl('https://example.com'))
        self.assertEqual(window.address.text(),'adresse en cours')
        # Directly construct the media host wrapper; no external site or binary is needed.
        window.open_media(QUrl('https://example.com'))
        self.assertIsInstance(window.current(),MediaView)
        count=window.tabs.count()
        button=window.bar.widgetForAction(window.bar.actions()[3]);QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        self.assertIs(window.current(),original);self.assertEqual(window.tabs.count(),count)
        window.go_forward();self.assertIsInstance(window.current(),MediaView)
        window.restore_previous(window.current());self.assertIs(window.current(),original)
        self.assertEqual(window.resolve('python').host(),'www.google.com')
        account=window.open_account();self.assertFalse(hasattr(account,'password'))
        window.sync_client.set_google_identity({'email':'fixture@example.test','name':'Compte test','sub':'fixture'},'fixture-token','fixture-nonce')
        self.assertEqual(account.identity.text(),'Compte test');self.assertEqual(account.email.text(),'fixture@example.test')
        window.sync_client.logout();self.assertEqual(account.identity.text(),'Non connecté')
        page=window.open_settings(2);self.app.processEvents()
        for width in (1672,1100,900):
            window.resize(width,750);self.app.processEvents()
            self.assertEqual(page.content.x(),245)
            for button in page.findChildren(QPushButton):
                if button.isVisible():self.assertLessEqual(button.mapTo(page,QPoint(button.width(),0)).x(),page.width())
        # Many tabs must share the available width rather than disappear.
        for i in range(12):window.add_internal(InternalPage('fixture','Fixture',window),'Fixture '+str(i),'logo')
        window.resize(1100,750);self.app.processEvents()
        self.assertLess(window.top_tabs.tabRect(0).width(),100)
        self.assertLessEqual(window.top_tabs.tabRect(window.top_tabs.count()-1).right(),window.top_tabs.width())
        while window.tabs.count()>1:window.close_tab(window.tabs.count()-1)
        window.close_tab(0);self.assertEqual(window.tabs.count(),1)
        self.assertEqual(window.current().page().backgroundColor().name(),'#07060e')
        window.close();self.app.processEvents()
if __name__=='__main__':unittest.main()
