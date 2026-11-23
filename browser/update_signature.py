import base64,json,re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from update_public_key import UPDATE_PUBLIC_KEY

def canonical(data):
    return json.dumps({k:data[k] for k in ('version','size','sha256')},sort_keys=True,separators=(',',':')).encode()

def verify_manifest(data,asset,tag):
    try:
        if not isinstance(data,dict) or data.get('version')!=tag.lstrip('v') or data.get('size')!=asset['size'] or data.get('sha256')!=asset['digest'].split(':')[1].lower():return False
        if not re.fullmatch(r'[0-9a-f]{64}',data['sha256']):return False
        Ed25519PublicKey.from_public_bytes(base64.b64decode(UPDATE_PUBLIC_KEY,validate=True)).verify(base64.b64decode(data['signature'],validate=True),canonical(data));return True
    except (ValueError,TypeError,KeyError,InvalidSignature):return False
