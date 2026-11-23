import importlib.util,json,os,secrets,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit,parse_qs
from urllib.error import HTTPError
import google_login
import google_desktop
spec=importlib.util.spec_from_file_location('nova_server',Path(__file__).with_name('server.py'));server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class GoogleTest(unittest.TestCase):
    def test_desktop_nonce_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            server=server_module.ThreadingHTTPServer(('127.0.0.1',0),server_module.Handler);server.store=server_module.Store(Path(directory)/'test.db');threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            def call(path,data):
                try:
                    with urlopen(Request(base+'/v1/oauth/google/desktop/'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=10) as response:return response.status,json.load(response)
                except HTTPError as error:return error.code,json.load(error)
            try:
                status,challenge=call('start',{});self.assertEqual(status,200)
                with patch.object(google_desktop,'verify_token',return_value={'sub':'desktop-fixture','email':'desktop@example.test','email_verified':True}) as verify:
                    status,session=call('finish',{'login_id':challenge['login_id'],'id_token':'fixture-token'})
                    self.assertEqual(status,200);self.assertEqual(session['email'],'desktop@example.test')
                    verify.assert_called_once_with('fixture-token',challenge['nonce'])
                    self.assertEqual(call('finish',{'login_id':challenge['login_id'],'id_token':'fixture-token'})[0],401)
                _,challenge=call('start',{})
                with patch.object(google_desktop,'verify_token',side_effect=ValueError('bad nonce')):
                    self.assertEqual(call('finish',{'login_id':challenge['login_id'],'id_token':'fixture-token'})[0],401)
            finally:server.shutdown();server.server_close()
    def test_configuration_and_single_use_pkce_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            server=server_module.ThreadingHTTPServer(('127.0.0.1',0),server_module.Handler);server.store=server_module.Store(Path(directory)/'test.db');threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            def call(path,data):
                try:
                    with urlopen(Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=10) as response:return response.status,json.load(response)
                except HTTPError as error:return error.code,json.load(error)
            verifier=secrets.token_urlsafe(48);body={'return_uri':'http://127.0.0.1:34567/nova-google-callback','state':secrets.token_urlsafe(32),'challenge':google_login.challenge(verifier)}
            try:
                with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':'','NOVA_PUBLIC_ORIGIN':''}):self.assertEqual(call('/v1/oauth/google/start',body)[0],503)
                with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'fixture-client','GOOGLE_CLIENT_SECRET':'fixture-secret','NOVA_PUBLIC_ORIGIN':'https://sync.example.test'}):
                    status,data=call('/v1/oauth/google/start',body);self.assertEqual(status,200);state=parse_qs(urlsplit(data['authorization_url']).query)['state'][0]
                    with patch.object(google_login,'exchange_google',return_value={'sub':'fixture-subject','email':'google@example.test','email_verified':True}):
                        try:build_opener(NoRedirect).open(base+'/v1/oauth/google/callback?code=fixture&state='+state)
                        except HTTPError as response:
                            self.assertEqual(response.code,302);location=response.headers['Location']
                    code=parse_qs(urlsplit(location).query)['code'][0]
                    status,session=call('/v1/oauth/google/exchange',{'code':code,'verifier':verifier});self.assertEqual(status,200);self.assertEqual(session['email'],'google@example.test')
                    self.assertEqual(call('/v1/oauth/google/exchange',{'code':code,'verifier':verifier})[0],401)
            finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
