import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google_session import read_session,save_session,restore_session,SessionRenewalError
from version import GOOGLE_DESKTOP_CLIENT_ID

class GoogleSessionTest(unittest.TestCase):
    def test_encrypted_state_survives_version_and_renews(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);claims={'sub':'fixture-sub','email':'person@example.test','email_verified':True}
            save_session(root,claims,'expired-fixture','nonce-fixture','refresh-fixture')
            self.assertNotIn(b'refresh-fixture',(root/'google-account.dat').read_bytes());data=read_session(root)
            response=MagicMock(status_code=200);response.json.return_value={'id_token':'fresh-fixture'}
            def verify(token,nonce):
                if token=='expired-fixture':raise ValueError('expired')
                self.assertIsNone(nonce);return claims.copy()
            with patch('requests.post',return_value=response) as request:
                restored,token,nonce,refresh=restore_session(data,'client-fixture',verify)
                self.assertEqual(token,'fresh-fixture');self.assertEqual(refresh,'refresh-fixture');self.assertEqual(restored['sub'],'fixture-sub')
                self.assertFalse(request.call_args.kwargs['allow_redirects']);self.assertEqual(request.call_args.kwargs['data']['grant_type'],'refresh_token')
            save_session(root,restored,token,nonce,refresh)
            self.assertEqual(read_session(root)['refresh_token'],'refresh-fixture')
    def test_network_failure_keeps_state_and_subject_mismatch_rejected(self):
        data={'id_token':'old','nonce':'n','refresh_token':'r','client_id':GOOGLE_DESKTOP_CLIENT_ID,'claims':{'sub':'expected'}}
        with patch('requests.post',side_effect=OSError('offline')):
            with self.assertRaises(SessionRenewalError):restore_session(data,'s',lambda *args:(_ for _ in ()).throw(ValueError()))
        self.assertEqual(data['refresh_token'],'r')
        response=MagicMock(status_code=200);response.json.return_value={'id_token':'new'}
        def verify(token,nonce):
            if token=='old':raise ValueError()
            return {'sub':'other','email_verified':True}
        with patch('requests.post',return_value=response):
            with self.assertRaises(SessionRenewalError):restore_session(data,'s',verify)
    def test_legacy_session_explains_one_time_reconnection(self):
        with self.assertRaisesRegex(SessionRenewalError,'une fois'):restore_session({'id_token':'old'},'',lambda *args:(_ for _ in ()).throw(ValueError()))
