import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from updater import version_tuple,release_asset

class UpdateTest(unittest.TestCase):
    def test_versions_and_verified_assets(self):
        self.assertGreater(version_tuple('v3.3.0'),version_tuple('3.2.0'))
        self.assertIsNone(version_tuple('../../3.3.0'))
        release={'tag_name':'v3.3.0','assets':[{'name':'NovaBrowser-Windows-x64.zip','size':100,'digest':'sha256:'+'a'*64,'browser_download_url':'https://github.com/zyko144/Nova/releases/download/v3.3.0/NovaBrowser-Windows-x64.zip'}]}
        self.assertIsNotNone(release_asset(release))
        for mutation in [lambda r:r['assets'][0].update(digest=''),lambda r:r['assets'][0].update(browser_download_url='https://evil.example/update.zip'),lambda r:r.update(prerelease=True),lambda r:r['assets'][0].update(size=-1)]:
            bad=copy.deepcopy(release);mutation(bad);self.assertIsNone(release_asset(bad))
if __name__=='__main__':unittest.main()
