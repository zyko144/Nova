import io,json,sys,tempfile,unittest
import threading
from urllib.request import build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nova_search.index import Index
from nova_search.brave import BraveSearch,SearchUnavailable
from nova_search.web import page
from nova_search.server import SearchServer

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class BraveTest(unittest.TestCase):
    def test_quota_redirects_to_google_without_calling_brave(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter=BraveSearch(Index(Path(directory)/'index.db'),'fixture-key',0);server=SearchServer(('127.0.0.1',0),adapter,'/');threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                with patch('nova_search.brave.build_opener') as api:
                    with self.assertRaises(HTTPError) as redirected:build_opener(NoRedirect()).open('http://127.0.0.1:'+str(server.server_port)+'/search?q=ecole+%26+python')
                    self.assertEqual(redirected.exception.code,302);target=urlsplit(redirected.exception.headers['Location']);self.assertEqual(target.netloc,'www.google.com');self.assertEqual(parse_qs(target.query)['q'],['ecole & python']);api.assert_not_called()
            finally:server.shutdown();server.server_close()
    def test_server_key_mapping_quota_and_no_result_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            local=Index(Path(directory)/'index.db');adapter=BraveSearch(local,'fixture-api-key',1);before=local.stats()
            response={'query':{'more_results_available':True},'web':{'results':[{'url':'https://example.test/page','title':'<b>Résultat Web</b>','description':'Une description.'},{'url':'javascript:alert(1)','title':'Blocked'}]}}
            stream=io.BytesIO(json.dumps(response).encode());opener=MagicMock();opener.open.return_value=stream
            with patch('nova_search.brave.build_opener',return_value=opener):result=adapter.search('test')
            request=opener.open.call_args.args[0];self.assertEqual(request.get_header('X-subscription-token'),'fixture-api-key')
            self.assertEqual(len(result['results']),1);self.assertEqual(result['results'][0]['title'],'Résultat Web');self.assertTrue(result['has_more']);self.assertIsNone(result['total'])
            self.assertEqual(local.stats(),before)
            with self.assertRaises(SearchUnavailable):adapter.search('again')
            html=page('test',result,adapter.stats());self.assertIn('fournis par Brave',html);self.assertNotIn('None résultat',html)
    def test_missing_key_never_claims_web_results(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter=BraveSearch(Index(Path(directory)/'index.db'),'',10)
            with self.assertRaises(SearchUnavailable):adapter.search('test')
            self.assertFalse(adapter.stats()['configured'])
if __name__=='__main__':unittest.main()
