import sys,time,uuid,unittest,json
from html import escape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Browser,QUrl,Qt,MediaView
from PySide6.QtTest import QTest

class PerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setApplicationName('NovaPerformanceTest-'+uuid.uuid4().hex)
    def wait(self,predicate,seconds=4):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.app.processEvents()
            if predicate():return True
            time.sleep(.01)
        return False
    def window(self):
        window=Browser();window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);window.show();return window
    def test_classic_media_resumes_only_previously_playing_and_notifies_once(self):
        window=self.window();view=window.current();window.data.pop('background_pause_hint_shown',None)
        fixture="""<html><video id='playing'></video><video id='manual'></video><script>window.pauseCalls=0;window.playCalls=0;for(const id of ['playing','manual']){const e=document.getElementById(id);let paused=id==='manual';Object.defineProperty(e,'paused',{get:()=>paused});Object.defineProperty(e,'ended',{get:()=>false});e.pause=()=>{paused=true;pauseCalls++};e.play=()=>{paused=false;playCalls++;return Promise.resolve()};}</script></html>"""
        fixture=fixture.replace('</html>','<iframe srcdoc="'+escape(fixture,quote=True)+'"></iframe></html>')
        def evaluate(script,frame=None):
            values=[];(frame or view.page()).runJavaScript('JSON.stringify('+script+')',lambda value:values.append(value));self.assertTrue(self.wait(lambda:bool(values)));return json.loads(values[0])
        try:
            view.page().home_pending=True;view.setHtml(fixture,QUrl('about:blank'))
            self.assertTrue(self.wait(lambda:not view.page().isLoading()))
            with patch.object(window.updater,'notify') as notice:
                other=window.new_tab();self.assertTrue(self.wait(lambda:notice.call_count==1))
                window.tabs.setCurrentWidget(view)
                self.assertEqual(evaluate('[playing.paused,manual.paused,pauseCalls,playCalls]'),[False,True,1,1])
                self.assertEqual(evaluate('[playing.paused,manual.paused,pauseCalls,playCalls]',view.page().mainFrame().children()[0]),[False,True,1,1])
                window.tabs.setCurrentWidget(other);self.assertTrue(self.wait(lambda:getattr(view,'_nova_suspended',False)));window.tabs.setCurrentWidget(view)
                self.assertEqual(evaluate('[playing.paused,manual.paused]'),[False,True]);self.assertEqual(notice.call_count,1)
                self.assertEqual(notice.call_args.kwargs['action_text'],'Ouvrir les paramètres');notice.call_args.args[2]();self.assertEqual(window.current().nav.currentRow(),7)
        finally:window.close();self.app.processEvents()
    def test_idle_services_styles_and_batched_history(self):
        window=self.window()
        try:
            self.assertIsNone(window.search);window.open_settings(7);self.assertIsNone(window.search)
            size=len(window.styleSheet());tab_size=len(window.top_tabs.styleSheet())
            for i in range(30):window.apply_theme();window.update_tab_style()
            self.assertEqual(len(window.styleSheet()),size);self.assertEqual(len(window.top_tabs.styleSheet()),tab_size)
            window.data['history']=[];window.save();writes=[];original=Path.write_text
            def write(path,*args,**kwargs):
                if path==window.datafile.with_suffix('.tmp'):writes.append(path)
                return original(path,*args,**kwargs)
            with patch.object(Path,'write_text',write):
                for i in range(20):window.loaded(SimpleNamespace(url=lambda:QUrl('https://fixture.example.test/'),title=lambda:'Fixture'),True)
                self.assertTrue(self.wait(lambda:not window._save_timer.isActive()))
            self.assertEqual(len(writes),1);self.assertEqual(len(window.data['history']),1)
            self.assertEqual(json.loads(window.datafile.read_text(encoding='utf-8'))['history'][0]['title'],'Fixture')
        finally:window.close();self.app.processEvents()
    def test_home_suggestions_use_our_ui_and_safe_local_data(self):
        window=self.window();view=window.current();loads=[];view.loadFinished.connect(lambda ok:loads.append(ok))
        def evaluate(script):
            values=[];view.page().runJavaScript('JSON.stringify('+script+')',lambda value:values.append(value));self.assertTrue(self.wait(lambda:bool(values)));return json.loads(values[0])
        try:
            self.assertTrue(self.wait(lambda:bool(loads)))
            window.data['history']=[{'title':'<img src=x onerror=alert(1)> Nova','url':'https://example.test/nova'},{'title':'Nova unsafe','url':'javascript:alert(1)'}];window.data['recent_searches']=[];window.refresh_home_tabs()
            self.assertTrue(self.wait(lambda:len(loads)>=2))
            evaluate("(()=>{const q=document.querySelector('input[name=q]');q.value='nova';q.dispatchEvent(new Event('input',{bubbles:true}));return true})()")
            self.assertTrue(self.wait(lambda:evaluate("document.querySelectorAll('#homeSuggestions a').length")>=2))
            self.assertTrue(evaluate("document.querySelector('#homeSuggestions img')===null"))
            self.assertEqual(evaluate("[...document.querySelectorAll('#homeSuggestions a')].filter(a=>a.href.startsWith('javascript:')).length"),0)
            self.assertTrue(evaluate("document.querySelector('#homeSuggestions').textContent.includes('Rechercher avec Google')"))
            evaluate("document.querySelector('input[name=q]').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown'}))")
            self.assertEqual(evaluate('document.activeElement.tagName'),'A')
            evaluate("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
            self.assertTrue(evaluate("document.getElementById('homeSuggestions').hidden"))
        finally:window.close();self.app.processEvents()
    def test_native_tab_pause_resume_and_setting(self):
        with patch.object(MediaView,'start',lambda self:None):
            window=self.window()
            try:
                window.open_media(QUrl('https://example.test/'));media=window.current();commands=[];media.send=lambda *args:commands.append(args)
                other=window.new_tab();self.assertIn(('suspend',),commands)
                window.tabs.setCurrentWidget(media);self.assertIn(('resume','focus'),commands)
                window.set_background_pause(False);commands.clear();window.tabs.setCurrentWidget(other);self.assertNotIn(('suspend',),commands)
                window.set_background_pause(True);self.assertIn(('suspend',),commands)
            finally:window.close();self.app.processEvents()
    def test_keyboard_suggestion_commits_once(self):
        window=self.window();helper=window.address_suggestions;helper.completer.popup().setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        try:
            window.data['history']=[];window.data['bookmarks']=[];window.data['recent_searches']=[]
            calls=[];window.navigate=lambda url:calls.append(url.toString());window.address.setFocus();QTest.keyClicks(window.address,'nova')
            self.app.processEvents();self.assertEqual(helper.model.rowCount(),2)
            QTest.keyClick(window.address,Qt.Key.Key_Down);QTest.keyClick(window.address,Qt.Key.Key_Return);self.app.processEvents()
            self.assertEqual(len(calls),1);self.assertIn('google.com/search?q=nova',calls[0])
        finally:window.close();self.app.processEvents()
