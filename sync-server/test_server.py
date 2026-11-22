import importlib.util,json,secrets,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

spec=importlib.util.spec_from_file_location('nova_server',Path(__file__).with_name('server.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class SyncTest(unittest.TestCase):
    def test_accounts_sync_conflicts_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            server=module.ThreadingHTTPServer(('127.0.0.1',0),module.Handler);server.store=module.Store(Path(folder)/'test.db')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            def call(path,data=None,token=''):
                req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
                try:
                    with urlopen(req,timeout=10) as response:return response.status,json.load(response)
                except HTTPError as error:return error.code,json.load(error)
            try:
                self.assertEqual(call('/v1/snapshot')[0],401)
                password=secrets.token_urlsafe(20)
                code,account=call('/v1/register',{'email':'one@example.test','password':password});self.assertEqual(code,200);token=account['token']
                self.assertEqual(call('/v1/login',{'email':'one@example.test','password':'incorrect-password'})[0],401)
                code,second_session=call('/v1/login',{'email':'one@example.test','password':password});self.assertEqual(code,200)
                code,snapshot=call('/v1/snapshot',{'revision':0,'data':{'bookmarks':[{'url':'https://example.com','title':'Example'},{'url':'javascript:alert(1)','title':'invalid'}],'cookies':'must not sync'}},token);self.assertEqual((code,snapshot['revision']),(200,1))
                data=call('/v1/snapshot',token=second_session['token'])[1];self.assertEqual(len(data['data']['bookmarks']),1);self.assertNotIn('cookies',data['data'])
                self.assertEqual(call('/v1/snapshot',{'revision':0,'data':{}},token)[0],409)
                other=call('/v1/register',{'email':'two@example.test','password':password})[1]['token'];self.assertEqual(call('/v1/snapshot',token=other)[1]['revision'],0)
                self.assertEqual(call('/v1/logout',{},token)[0],200);self.assertEqual(call('/v1/snapshot',token=token)[0],401)
            finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
