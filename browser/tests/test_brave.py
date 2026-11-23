import io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nova_search.index import Index
from nova_search.brave import BraveSearch,SearchUnavailable
from nova_search.web import page

class BraveTest(unittest.TestCase):
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
