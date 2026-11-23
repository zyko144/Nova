import sys,tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_data import read_export,apply_import,password_exports
from vault import Vault
from sessions import snapshot
class ImportTest(unittest.TestCase):
 def test_password_export_discovery_reads_only_metadata(self):
  import os,time
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);recent=root/'Google Passwords.csv';recent.write_text('fixture',encoding='utf-8');other=root/'invoices.csv';other.write_text('fixture',encoding='utf-8');old=root/'Chrome Passwords.csv';old.write_text('fixture',encoding='utf-8');now=time.time();os.utime(old,(now-8*86400,now-8*86400))
   with patch.object(Path,'read_text',side_effect=AssertionError('No contents should be read')):self.assertEqual(password_exports(root,now),[recent])
 def test_csv_and_bookmarks_import_dedup(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);csv=root/'passwords.csv';csv.write_text('url,username,password\nhttps://example.test,person@example.test,fixture-password\nhttp://unsafe.test,u,p\n',encoding='utf-8')
   result=read_export(csv);self.assertEqual(len(result['credentials']),1)
   browser=SimpleNamespace(data={'bookmarks':[],'history':[]},vault=Vault(root/'vault.dat'),save=lambda:None)
   self.assertEqual(apply_import(browser,result)['credentials'],1);self.assertEqual(apply_import(browser,result)['credentials'],0)
   self.assertEqual(browser.vault.for_site('https://example.test')[0]['password'],'fixture-password')
   self.assertNotIn(b'fixture-password',(root/'vault.dat').read_bytes())
   html=root/'bookmarks.html';html.write_text('<a href="https://example.test">Example</a><a href="javascript:alert(1)">Bad</a>',encoding='utf-8');self.assertEqual(len(read_export(html)['bookmarks']),1)
