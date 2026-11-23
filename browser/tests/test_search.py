import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen,Request
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nova_search.index import Index,canonical
from nova_search.server import LocalSearch
from nova_search.crawler import Document,public_addresses,crawl

class SearchTest(unittest.TestCase):
    def test_ranking_accents_filters_and_safe_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            index=Index(Path(directory)/'index.db')
            index.put('https://a.example.test/','Architecture moderne','Architecture, bâtiments et villes.','guides')
            index.put('https://b.example.test/','Carnet de voyage','Une promenade et une architecture moderne.','web')
            result=index.search('architecture moderne');self.assertEqual(result['results'][0]['url'],'https://a.example.test/')
            self.assertEqual(index.search('architecture',kind='guides')['total'],1)
            index.put('https://c.example.test/','Éléphant','Un animal sauvage')
            self.assertEqual(index.search('elephant')['total'],1)
            self.assertIn('Architecture moderne',index.suggest('architec'))
            self.assertEqual(index.search('" OR * <script>')['total'],0)
            self.assertEqual(index.search('')['total'],0)
            index.remove('https://c.example.test/');self.assertEqual(index.search('elephant')['total'],0)
            self.assertEqual(canonical('javascript:alert(1)'),'')
    def test_http_html_escaping_and_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            local=LocalSearch(Path(directory)/'index.db')
            try:
                local.index.put('https://example.test/','<script>alert(1)</script>','Safe example')
                with urlopen(local.url('Safe')) as response:
                    html=response.read().decode();self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>alert(1)</script>',html)
                    self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
                with urlopen(local.base+'api/search?q=python') as response:self.assertGreater(json.load(response)['total'],0)
                with urlopen(local.base+'suggest?q=pyth') as response:self.assertTrue(json.load(response))
                with self.assertRaises(HTTPError) as refused:urlopen(local.base.replace(local.server.prefix,'/'))
                self.assertEqual(refused.exception.code,404)
                with self.assertRaises(HTTPError) as refused:urlopen(Request(local.base,headers={'Host':'evil.test'}))
                self.assertEqual(refused.exception.code,403)
            finally:local.server.shutdown();local.server.server_close()
    def test_crawler_blocks_private_ips_and_honors_noindex(self):
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):public_addresses('example.test')
        doc=Document();doc.feed('<title>Test</title><meta name="robots" content="noindex,nofollow"><script>secret</script><p>Visible</p>')
        self.assertTrue(doc.noindex);self.assertTrue(doc.nofollow);self.assertNotIn('secret',doc.text)
        with tempfile.TemporaryDirectory() as directory:
            index=Index(Path(directory)/'index.db')
            def fetch(url,**kwargs):
                if url.endswith('robots.txt'):return 200,{},b'User-agent: *\nDisallow: /blocked',url
                return 200,{'content-type':'text/html'},b'<title>Fixture</title><meta name="robots" content="noindex"><p>sample</p>',url
            with patch('nova_search.crawler.fetch',side_effect=fetch),patch('time.sleep'):
                self.assertEqual(crawl(index,['https://example.test/blocked','https://example.test/open'],limit=2,report=lambda message:None),0)
            self.assertEqual(index.search('Fixture')['total'],0)
if __name__=='__main__':unittest.main()
