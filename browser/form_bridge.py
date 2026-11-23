import json
from pathlib import Path
from PySide6.QtCore import QObject,Slot,QFile,QIODevice
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
from vault import secure_origin

class FormBridge(QObject):
    def __init__(self,browser,view):super().__init__(view);self.browser=browser;self.view=view
    @Slot(str)
    def message(self,raw):
        if len(raw)>20000:return
        try:message=json.loads(raw)
        except ValueError:return
        if isinstance(message,dict) and message.get('type') in ('nova-dirty','nova-capture-state'):
            self.browser.protection_message(self.view,message);return
        if isinstance(message,dict) and message.get('type')=='nova-search-suggest' and self.view.url().scheme()=='about' and self.view is self.browser.current():
            query=str(message.get('query',''))[:160]
            def received(value,items):
                try:
                    if self.view.url().scheme()=='about' and self.view is self.browser.current():self.view.page().runJavaScript('window.__novaAiSuggestions?.('+json.dumps(value)+','+json.dumps(items)+')')
                except RuntimeError:pass
            self.browser.ai.request('home',query,received);return
        origin=secure_origin(self.view.url().toString())
        if not origin or not isinstance(message,dict):return
        if message.get('type')=='nova-fill-request':self.browser.fill_credentials(self.view,str(message.get('username',''))[:254])
        elif message.get('type')=='nova-capture':self.browser.capture_credentials(self.view,message)

def install_bridge(browser,view):
    bridge=FormBridge(browser,view);channel=QWebChannel(view);channel.registerObject('novaForms',bridge);view.page().setWebChannel(channel)
    source=QFile(':/qtwebchannel/qwebchannel.js')
    if not source.open(QIODevice.OpenModeFlag.ReadOnly):return
    library=bytes(source.readAll()).decode();source.close()
    script=QWebEngineScript();script.setName('Nova form assistant');script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld);script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady);script.setRunsOnSubFrames(False)
    code=(Path(__file__).parent/'protection.js').read_text(encoding='utf-8')+'\n'+(Path(__file__).parent/'autofill.js').read_text(encoding='utf-8')
    script.setSourceCode(library+'\nnew QWebChannel(qt.webChannelTransport,c=>{window.__novaBridge=c.objects.novaForms;'+code+'});')
    view.page().scripts().insert(script);view.form_bridge=bridge;view.form_channel=channel

    protection=QWebEngineScript();protection.setName('Nova temporary permissions');protection.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld);protection.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady);protection.setRunsOnSubFrames(True);protection.setSourceCode((Path(__file__).parent/'protection.js').read_text(encoding='utf-8'));view.page().scripts().insert(protection)
