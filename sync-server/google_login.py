"""Google web OAuth with server-side secrets and a one-time PKCE desktop handoff."""
import base64,hashlib,hmac,json,os,secrets,time
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.request import Request,urlopen

def configuration():
    client=os.environ.get('GOOGLE_CLIENT_ID','');secret=os.environ.get('GOOGLE_CLIENT_SECRET','');origin=os.environ.get('NOVA_PUBLIC_ORIGIN','').rstrip('/')
    parsed=urlsplit(origin)
    if not client or not secret or parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.path:return None
    return client,secret,origin+'/v1/oauth/google/callback'

def challenge(verifier):return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')

def exchange_google(code,verifier,nonce,config):
    client,secret,redirect=config
    data=urlencode({'code':code,'client_id':client,'client_secret':secret,'redirect_uri':redirect,'grant_type':'authorization_code','code_verifier':verifier}).encode()
    with urlopen(Request('https://oauth2.googleapis.com/token',data=data),timeout=15) as response:token=json.load(response)
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request as GoogleRequest
    claims=id_token.verify_oauth2_token(token['id_token'],GoogleRequest(),client)
    if claims.get('nonce')!=nonce or not claims.get('email_verified') or not claims.get('sub'):raise ValueError('Identité Google non vérifiée')
    return claims

def post(handler):
    if handler.path not in ('/v1/oauth/google/start','/v1/oauth/google/exchange'):return False
    store=handler.server.store
    if not store.permit(handler.client_address[0]):handler.reply(429,{'error':'Trop de tentatives.'});return True
    body=handler.body()
    if handler.path.endswith('/start'):
        config=configuration()
        if not config:handler.reply(503,{'error':'Connexion Google à configurer sur le serveur Nova : GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET et NOVA_PUBLIC_ORIGIN.'});return True
        return_uri=body.get('return_uri','');app_state=body.get('state','');app_challenge=body.get('challenge','')
        parsed=urlsplit(return_uri)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path!='/nova-google-callback' or not parsed.port or parsed.query or parsed.fragment or parsed.username or not isinstance(app_state,str) or not 32<=len(app_state)<=128 or not isinstance(app_challenge,str) or len(app_challenge)!=43:
            handler.reply(400,{'error':'Retour OAuth invalide.'});return True
        state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        with store.oauth_lock:
            now=time.time()
            store.oauth_states={k:v for k,v in store.oauth_states.items() if v['expires']>now}
            store.oauth_states[state]={'return':return_uri,'app_state':app_state,'challenge':app_challenge,'nonce':nonce,'verifier':verifier,'link':handler.user(),'expires':now+300}
        url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':config[0],'redirect_uri':config[2],'response_type':'code','scope':'openid email profile','state':state,'nonce':nonce,'code_challenge':challenge(verifier),'code_challenge_method':'S256'})
        handler.reply(200,{'authorization_url':url});return True
    code=body.get('code','');verifier=body.get('verifier','')
    if not isinstance(code,str) or not isinstance(verifier,str) or not 43<=len(verifier)<=128:handler.reply(400,{'error':'Échange OAuth invalide.'});return True
    with store.oauth_lock:pending=store.oauth_codes.pop(code,None)
    if not pending or pending['expires']<time.time() or not hmac.compare_digest(challenge(verifier),pending['challenge']):handler.reply(401,{'error':'Code OAuth expiré ou invalide.'});return True
    with store.connect() as db:row=db.execute('SELECT email FROM users WHERE id=?',(pending['user'],)).fetchone()
    handler.reply(200,{'token':handler.issue_token(pending['user']),'email':row[0]});return True

def callback(handler):
    if urlsplit(handler.path).path!='/v1/oauth/google/callback':return False
    store=handler.server.store;query=parse_qs(urlsplit(handler.path).query)
    state=query.get('state',[''])[0]
    with store.oauth_lock:pending=store.oauth_states.pop(state,None)
    if not pending or pending['expires']<time.time():handler.reply(400,{'error':'Session Google expirée ou invalide.'});return True
    try:
        if query.get('error'):raise ValueError('Connexion Google annulée.')
        config=configuration()
        if not config:raise ValueError()
        claims=exchange_google(query.get('code',[''])[0],pending['verifier'],pending['nonce'],config)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            identity=db.execute("SELECT user_id FROM identities WHERE provider='google' AND subject=?",(claims['sub'],)).fetchone()
            if identity:
                user_id=identity[0]
                if pending['link'] and pending['link']!=user_id:raise ValueError('Ce compte Google est déjà lié à un autre compte Nova.')
            elif pending['link']:user_id=pending['link']
            else:
                email=claims['email'].strip().lower()
                if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():raise ValueError('Connectez-vous d’abord au compte Nova existant puis liez Google.')
                user_id=secrets.token_hex(16)
                # Google-only account has an unusable random local password hash.
                db.execute('INSERT INTO users VALUES(?,?,?,?)',(user_id,email,secrets.token_hex(16),secrets.token_hex(32)))
            if not identity:db.execute('INSERT INTO identities VALUES(?,?,?)',('google',claims['sub'],user_id))
        code=secrets.token_urlsafe(48)
        with store.oauth_lock:
            store.oauth_codes={k:v for k,v in store.oauth_codes.items() if v['expires']>time.time()}
            store.oauth_codes[code]={'user':user_id,'challenge':pending['challenge'],'expires':time.time()+60}
        location=pending['return']+'?'+urlencode({'code':code,'state':pending['app_state']})
    except Exception:
        location=pending['return']+'?'+urlencode({'error':'google_login_failed','state':pending['app_state']})
    handler.send_response(302);handler.send_header('Location',location);handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer');handler.end_headers();return True
