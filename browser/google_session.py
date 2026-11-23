"""Encrypted, version-independent Google sign-in state and renewal."""
import json
from vault import protect
from version import GOOGLE_DESKTOP_CLIENT_ID

class SessionRenewalError(Exception):pass

def save_session(root,claims,token,nonce,refresh_token=''):
    path=root/'google-account.dat';temporary=path.with_suffix('.tmp')
    data={'id_token':token,'nonce':nonce,'refresh_token':refresh_token,'client_id':GOOGLE_DESKTOP_CLIENT_ID,'claims':{k:claims.get(k,'') for k in ('sub','email','name','picture','exp')}}
    temporary.write_bytes(protect(json.dumps(data).encode()));temporary.replace(path)

def read_session(root):
    return json.loads(protect((root/'google-account.dat').read_bytes(),True).decode())

def restore_session(data,secret,verify):
    if data.get('client_id',GOOGLE_DESKTOP_CLIENT_ID)!=GOOGLE_DESKTOP_CLIENT_ID:raise SessionRenewalError('Le client Google a changé. Reconnectez votre compte une fois.')
    try:
        claims=verify(data['id_token'],data.get('nonce') or None)
        return claims,data['id_token'],data.get('nonce',''),data.get('refresh_token','')
    except Exception:pass
    refresh=data.get('refresh_token','')
    if not refresh:raise SessionRenewalError('Reconnectez Google une fois pour activer la conservation de session après redémarrage.')
    import requests
    try:
        response=requests.post('https://oauth2.googleapis.com/token',data={'client_id':GOOGLE_DESKTOP_CLIENT_ID,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=15,allow_redirects=False)
        if response.status_code==400:
            error=response.json().get('error')
            if error=='invalid_grant':raise SessionRenewalError('Google a expiré ou révoqué l’autorisation. Reconnectez votre compte.')
        if response.status_code!=200:raise SessionRenewalError('Vérification Google indisponible. Votre session est conservée ; réessayez plus tard.')
        result=response.json();token=result.get('id_token')
        if not token:raise SessionRenewalError('Google n’a pas renvoyé de preuve d’identité. Réessayez plus tard.')
        # A refresh response is authenticated by its refresh token, not a new authorization nonce.
        claims=verify(token,None)
        expected=data.get('claims',{}).get('sub')
        if not expected:
            import base64
            encoded=data['id_token'].split('.')[1];expected=json.loads(base64.urlsafe_b64decode(encoded+'='*((-len(encoded))%4))).get('sub')
        if not expected or claims.get('sub')!=expected:raise SessionRenewalError('L’identité Google renouvelée ne correspond pas au compte enregistré.')
        return claims,token,'',result.get('refresh_token') or refresh
    except SessionRenewalError:raise
    except Exception:raise SessionRenewalError('Connexion Google momentanément indisponible. Votre session reste enregistrée.') from None
