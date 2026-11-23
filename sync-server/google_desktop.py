import os,secrets,time

DEFAULT_CLIENT='54433304112-0h0sotfg4l7ql274mk9l5grjg1bhgjj1.apps.googleusercontent.com'
def verify_token(token,nonce):
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request
    transport=Request()
    def limited(url,method='GET',body=None,headers=None,**kwargs):return transport(url,method=method,body=body,headers=headers,timeout=15)
    claims=id_token.verify_oauth2_token(token,limited,os.environ.get('GOOGLE_DESKTOP_CLIENT_ID',DEFAULT_CLIENT))
    if not claims.get('email_verified') or claims.get('nonce')!=nonce or not claims.get('sub'):raise ValueError('Identité Google invalide')
    return claims

def post(handler):
    if handler.path not in ('/v1/oauth/google/desktop/start','/v1/oauth/google/desktop/finish'):return False
    store=handler.server.store
    if not store.permit(handler.client_address[0]):handler.reply(429,{'error':'Trop de tentatives.'});return True
    body=handler.body()
    if handler.path.endswith('/start'):
        login_id=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32)
        with store.oauth_lock:
            store.oauth_desktop={k:v for k,v in store.oauth_desktop.items() if v['expires']>time.time()}
            store.oauth_desktop[login_id]={'nonce':nonce,'link':handler.user(),'expires':time.time()+300}
        handler.reply(200,{'login_id':login_id,'nonce':nonce});return True
    login_id=body.get('login_id','');token=body.get('id_token','')
    if not isinstance(login_id,str) or not isinstance(token,str) or len(token)>20000:handler.reply(400,{'error':'Requête Google invalide.'});return True
    with store.oauth_lock:pending=store.oauth_desktop.pop(login_id,None)
    if not pending or pending['expires']<time.time():handler.reply(401,{'error':'Connexion Google expirée.'});return True
    try:
        claims=verify_token(token,pending['nonce'])
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            identity=db.execute("SELECT user_id FROM identities WHERE provider='google' AND subject=?",(claims['sub'],)).fetchone()
            if identity:
                user_id=identity[0]
                if pending['link'] and pending['link']!=user_id:raise ValueError()
            elif pending['link']:user_id=pending['link']
            else:
                email=claims['email'].strip().lower()
                if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
                    handler.reply(409,{'error':'Connectez-vous d’abord au compte Nova existant puis liez Google.'});return True
                user_id=secrets.token_hex(16);db.execute('INSERT INTO users VALUES(?,?,?,?)',(user_id,email,secrets.token_hex(16),secrets.token_hex(32)))
            if not identity:db.execute('INSERT INTO identities VALUES(?,?,?)',('google',claims['sub'],user_id))
            email=db.execute('SELECT email FROM users WHERE id=?',(user_id,)).fetchone()[0]
        handler.reply(200,{'token':handler.issue_token(user_id),'email':email})
    except Exception:handler.reply(401,{'error':'Identité Google refusée ou vérification indisponible.'})
    return True
