import sys,json,uuid,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_suggestions import permitted,clean_values
from main import QApplication,Browser,Qt
from onboarding import Welcome
from PySide6.QtCore import QCoreApplication,QEvent

class AITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaAIIntegration-'+uuid.uuid4().hex)
    def tearDown(self):
        # Release WebEngine profiles between tests rather than waiting for cyclic GC.
        for widget in self.app.topLevelWidgets():
            if isinstance(widget,Browser):widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def test_search_scope_and_sanitized_output(self):
        self.assertTrue(permitted('mai'));self.assertFalse(permitted('https://private.test/path'));self.assertFalse(permitted('person@example.test'));self.assertFalse(permitted('gsk_fixture-secret'))
        self.assertEqual(clean_values('{"suggestions":["maison","mail","https://bad.test","maison",4]}','mai'),['maison','mail'])
    def test_disabled_service_and_cache_do_not_call_api(self):
        browser=Browser();browser.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        try:
            ai=browser.ai;ai.key='fixture';browser.data['preferences']['ai_suggestions']=False
            with patch.object(ai.network,'post') as post:
                ai.request('address','mai',lambda *args:None);ai.send();post.assert_not_called()
                browser.data['preferences']['ai_suggestions']=True
                import time
                ai.cache['mai']=(time.monotonic(),['maison','mail']);values=[];ai.request('address','mai',lambda q,result:values.extend(result));self.assertEqual(values,['maison','mail']);post.assert_not_called()
        finally:browser.close();self.app.processEvents()
    def test_shared_service_works_without_provider_key(self):
        browser=Browser()
        try:
            ai=browser.ai;browser.data['preferences']['ai_suggestions']=True
            with patch.object(ai.network,'post',return_value=MagicMock()) as post:
                ai.request('address','mai',lambda *args:None);ai.timer.stop();ai.send()
                request,body=post.call_args.args
                self.assertEqual(request.url().host(),'nova-browser-ai-zyko144-zeev2.vercel.app')
                self.assertFalse(request.hasRawHeader('Authorization'))
                self.assertEqual(json.loads(bytes(body)),{'query':'mai'})
        finally:browser.close();self.app.processEvents()
    def test_welcome_and_import_stay_in_browser_window(self):
        browser=Browser();browser.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);browser.show()
        try:
            browser.show_welcome();welcome=browser.welcome;self.assertFalse(welcome.isWindow());welcome.step=1;welcome.render();welcome.perform();self.assertFalse(welcome.import_panel.isWindow());welcome.import_panel.reject();welcome.skip_step();self.assertEqual(welcome.step,1);welcome.skip_step();self.assertEqual(welcome.step,2)
        finally:browser.close();self.app.processEvents()
    def test_default_browser_registration_uses_user_capabilities(self):
        import default_browser
        with patch.object(sys,'frozen',True,create=True),patch.object(default_browser.winreg,'OpenKey'),patch.object(default_browser.winreg,'DeleteValue'),patch.object(default_browser.winreg,'CreateKey') as create,patch.object(default_browser.winreg,'SetValueEx') as write,patch.object(default_browser.QDesktopServices,'openUrl') as open_settings:
            default_browser.register_browser();self.assertTrue(open_settings.called)
            values=[call.args for call in write.call_args_list];self.assertTrue(any(args[1]=='https' and args[-1]=='NovaBrowserURL' for args in values));self.assertTrue(any('--open-url "%1"' in str(args[-1]) for args in values));self.assertFalse(any('UserChoice' in str(call.args) for call in create.call_args_list))
    def test_default_browser_prompt_is_once_and_never_changes_choice(self):
        browser=Browser();browser.data.pop('default_browser_prompt_shown',None)
        try:
            with patch.object(QApplication,'applicationName',return_value='NovaBrowser'),patch('default_browser.is_default_browser',return_value=False),patch.object(browser.updater,'notify') as notify:
                browser.offer_default_browser();browser.offer_default_browser();self.assertEqual(notify.call_count,1);self.assertEqual(notify.call_args.kwargs['action_text'],'Choisir Nova')
            browser.data.pop('default_browser_prompt_shown',None)
            with patch.object(QApplication,'applicationName',return_value='NovaBrowser'),patch('default_browser.is_default_browser',return_value=True),patch.object(browser.updater,'notify') as notify:
                browser.offer_default_browser();notify.assert_not_called()
        finally:browser.close();self.app.processEvents()
