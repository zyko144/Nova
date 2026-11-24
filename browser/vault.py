"""Local credentials sealed with Windows DPAPI; never part of Nova Sync."""
import ctypes,json,re,sys
from ctypes import wintypes
from urllib.parse import urlsplit

def secure_origin(url):
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username:return ''
        port=parsed.port
        return 'https://'+parsed.hostname.lower()+((':'+str(port)) if port and port!=443 else '')
    except ValueError:return ''

def protect(data,decrypt=False):
    if sys.platform!='win32':raise RuntimeError('Le coffre Nova nécessite la protection Windows DPAPI.')
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    entropy_data=b'NovaBrowser-local-vault-v1';entropy_buffer=ctypes.create_string_buffer(entropy_data);entropy=Blob(len(entropy_data),ctypes.cast(entropy_buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob();crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)];fn.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not fn(ctypes.byref(source),None,ctypes.byref(entropy),None,None,1,ctypes.byref(target)):raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)

class Vault:
    def __init__(self,path):
        self.path=path;self.data={'credentials':[],'emails':[]}
        if path.exists():
            self.data=json.loads(protect(path.read_bytes(),True).decode())
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_suffix('.tmp')
        temporary.write_bytes(protect(json.dumps(self.data,ensure_ascii=False).encode()));temporary.replace(self.path)
    def remember_email(self,email):
        email=email.strip()[:254]
        if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and email not in self.data['emails']:
            self.data['emails']=(self.data['emails']+[email])[-30:];self.save()
    def merge_import(self,credentials=(),emails=()):
        original=self.data;records=list(original.get('credentials',[]));known={(row['origin'],row['username']) for row in records};addresses=list(original.get('emails',[]));added=0;mail_added=0
        for row in list(credentials)[:500]:
            origin=secure_origin(str(row.get('url','')));username=str(row.get('username','')).strip()[:254];password=row.get('password','')
            if not origin or not isinstance(password,str) or not 1<=len(password)<=4096 or (origin,username) in known:continue
            known.add((origin,username));records.append({'origin':origin,'username':username,'password':password});added+=1
            if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',username) and username not in addresses:addresses.append(username)
        for email in list(emails)[:1000]:
            email=str(email).strip()
            if len(email)<=254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and email not in addresses:addresses.append(email);mail_added+=1
        if added or mail_added:
            self.data={**original,'credentials':records[-500:],'emails':addresses[-30:]}
            try:self.save()
            except Exception:self.data=original;raise
        return {'credentials':added,'emails':min(mail_added,30)}
    def put(self,url,username,password):
        origin=secure_origin(url)
        if not origin or not isinstance(password,str) or not 1<=len(password)<=4096:raise ValueError('Identifiant HTTPS invalide')
        username=username.strip()[:254]
        records=[x for x in self.data['credentials'] if not (x['origin']==origin and x['username']==username)]
        self.data['credentials']=(records+[{'origin':origin,'username':username,'password':password}])[-500:]
        self.remember_email(username);self.save()
    def for_site(self,url):
        origin=secure_origin(url)
        return [x for x in self.data['credentials'] if x['origin']==origin] if origin else []
    def delete(self,origin,username):
        self.data['credentials']=[x for x in self.data['credentials'] if (x['origin'],x['username'])!=(origin,username)];self.save()
