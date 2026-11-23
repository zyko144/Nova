import base64,hashlib,hmac,json,secrets,threading,os
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlsplit,parse_qs,urlencode
from PySide6.QtCore import QObject,Signal,QTimer,QUrl,QByteArray
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkRequest
from version import GOOGLE_DESKTOP_CLIENT_ID
from vault import protect

def desktop_secret(browser):
    value=os.environ.get('NOVA_GOOGLE_CLIENT_SECRET','').strip()
    if value:return value
    try:return protect((browser.root/'google-client.dat').read_bytes(),True).decode().strip()
    except (OSError,UnicodeError,ValueError):return ''

def verify_identity(token,nonce):
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request
    transport=Request()
    def limited(url,method='GET',body=None,headers=None,**kwargs):return transport(url,method=method,body=body,headers=headers,timeout=15)
    claims=id_token.verify_oauth2_token(token,limited,GOOGLE_DESKTOP_CLIENT_ID)
    if not claims.get('email_verified') or claims.get('nonce')!=nonce or not claims.get('sub'):raise ValueError('Identité Google invalide')
    return claims

class GoogleFlow(QObject):
    completed=Signal(int,str,str)
    verified=Signal(int,object,str)
    failed=Signal(int,str)
    def __init__(self,client):
        super().__init__(client);self.client=client;self.server=None;self.login_id='';self.in_progress=False;self.generation=0
        self.completed.connect(self.finish);self.verified.connect(self.accept);self.failed.connect(self.validation_error)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.cancel)
    def start(self,endpoint):
        if self.in_progress:self.client.statusChanged.emit('Une connexion Google est déjà en cours.');return
        if not desktop_secret(self.client.browser):
            self.client.statusChanged.emit('Google nécessite une configuration sur ce PC. Lancez Configurer-Google.cmd dans le dossier Nova, puis réessayez.');return
        self.in_progress=True
        self.generation+=1
        generation=self.generation
        self.client.endpoint=endpoint.strip().rstrip('/');self.login_id=''
        if self.client.endpoint:
            def prepared(data):
                if generation!=self.generation or not self.in_progress:return
                self.login_id=data['login_id'];self.begin(data['nonce'])
            self.client.request('/v1/oauth/google/desktop/start',{},prepared,self.cancel)
        else:self.begin(secrets.token_urlsafe(32))
    def begin(self,nonce):
        self.nonce=nonce;self.state=secrets.token_urlsafe(32);self.verifier=secrets.token_urlsafe(48)
        flow=self;generation=self.generation;expected_state=self.state
        class Callback(BaseHTTPRequestHandler):
            def setup(self):super().setup();self.connection.settimeout(10)
            def log_message(self,*args):pass
            def do_GET(self):
                parsed=urlsplit(self.path);query=parse_qs(parsed.query)
                if parsed.path!='/' or not hmac.compare_digest(query.get('state',[''])[0],expected_state):self.send_error(400);return
                content='Autorisation reçue. Nova vérifie encore votre identité. Revenez dans Nova pour voir le résultat de la connexion.'.encode()
                self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
                flow.completed.emit(generation,query.get('code',[''])[0],query.get('error',[''])[0])
        self.server=HTTPServer(('127.0.0.1',0),Callback);server=self.server
        threading.Thread(target=lambda:server.serve_forever(poll_interval=.1),daemon=True).start()
        self.return_uri=f'http://127.0.0.1:{server.server_port}/'
        challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':GOOGLE_DESKTOP_CLIENT_ID,'redirect_uri':self.return_uri,'response_type':'code','scope':'openid email profile','state':self.state,'nonce':nonce,'code_challenge':challenge,'code_challenge_method':'S256'})
        QDesktopServices.openUrl(QUrl(url));self.client.statusChanged.emit('Terminez la connexion Google dans votre navigateur système.');self.timer.start(300000)
    def finish(self,generation,code,error):
        if generation!=self.generation or not self.in_progress:return
        self.cancel(keep_active=True)
        self.client.statusChanged.emit('Autorisation reçue. Vérification du compte Google…')
        if error or not code:self.error('Connexion Google annulée ou refusée.');return
        request=QNetworkRequest(QUrl('https://oauth2.googleapis.com/token'));request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/x-www-form-urlencoded');request.setTransferTimeout(20000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        fields={'client_id':GOOGLE_DESKTOP_CLIENT_ID,'redirect_uri':self.return_uri,'code':code,'code_verifier':self.verifier,'grant_type':'authorization_code'}
        secret=desktop_secret(self.client.browser)
        if secret:fields['client_secret']=secret
        data=urlencode(fields).encode()
        reply=self.client.network.post(request,QByteArray(data))
        nonce=self.nonce
        def done():
            try:
                if generation!=self.generation or not self.in_progress:return
                value=json.loads(bytes(reply.readAll()).decode());token=value.get('id_token')
                if not token:
                    reason=str(value.get('error','échange refusé'))[:80]
                    self.error('Connexion Google non terminée : '+reason+'. Vérifiez la configuration OAuth du client de bureau.');return
                def validate():
                    try:self.verified.emit(generation,verify_identity(token,nonce),token)
                    except Exception:self.failed.emit(generation,'Vérification Google impossible. Réessayez sans fermer Nova.')
                threading.Thread(target=validate,daemon=True).start()
            except (ValueError,UnicodeError,TypeError):self.error('Google a refusé l’échange. Vérifiez le client de bureau et les utilisateurs de test Google Cloud.')
            finally:reply.deleteLater()
        reply.finished.connect(done)
    def accept(self,generation,claims,token):
        if generation!=self.generation or not self.in_progress:return
        self.in_progress=False
        self.client.set_google_identity(claims,token,self.nonce)
        if self.client.endpoint:
            self.client.request('/v1/oauth/google/desktop/finish',{'login_id':self.login_id,'id_token':token},self.client.accept_session)
        else:
            self.client.token='';self.client.auth_endpoint='';self.client.timer.stop()
            browser=self.client.browser
            if browser.vault is not None:
                try:browser.vault.remember_email(claims['email'])
                except OSError:pass
            self.client.statusChanged.emit('Connecté avec Google : '+claims.get('name',claims['email'])+'.')
    def error(self,message):self.client.statusChanged.emit(message);self.cancel()
    def validation_error(self,generation,message):
        if generation==self.generation:self.error(message)
    def cancel(self,keep_active=False):
        if not keep_active:self.in_progress=False;self.generation+=1
        self.timer.stop()
        if self.server:
            server=self.server;self.server=None
            def close():server.shutdown();server.server_close()
            threading.Thread(target=close,daemon=True).start()
