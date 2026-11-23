import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vault import Vault,secure_origin
from suggestions import suggestions

class VaultTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI')
    def test_google_configuration_is_encrypted_and_readable(self):
        from types import SimpleNamespace
        from google_flow import save_desktop_secret,desktop_secret
        with tempfile.TemporaryDirectory() as directory:
            browser=SimpleNamespace(root=Path(directory));save_desktop_secret(browser,'fixture-google-client-secret')
            self.assertEqual(desktop_secret(browser),'fixture-google-client-secret')
            self.assertNotIn(b'fixture-google-client-secret',(browser.root/'google-client.dat').read_bytes())
    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI')
    def test_encrypted_storage_and_origin_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'vault.dat';vault=Vault(path)
            vault.put('https://example.test/login','person@example.test','fixture-password-123')
            self.assertNotIn(b'fixture-password',path.read_bytes());self.assertNotIn(b'person@example',path.read_bytes())
            restored=Vault(path);self.assertEqual(restored.for_site('https://example.test/account')[0]['username'],'person@example.test')
            self.assertEqual(restored.for_site('http://example.test'),[]);self.assertEqual(restored.for_site('https://other.test'),[])
            self.assertIn('person@example.test',restored.data['emails'])
            restored.delete('https://example.test','person@example.test');self.assertEqual(restored.for_site('https://example.test'),[])
    def test_origin_and_local_suggestions(self):
        self.assertEqual(secure_origin('https://example.test:443/path'),'https://example.test')
        self.assertEqual(secure_origin('https://evil@example.test'),'')
        values=suggestions('nova',{'bookmarks':[{'title':'Nova GitHub','url':'https://github.com/zyko144/Nova'}]})
        self.assertTrue(any(url=='https://github.com/zyko144/Nova' for label,url in values))
        self.assertTrue(any('youtube.com/results' in url for label,url in values))
if __name__=='__main__':unittest.main()
