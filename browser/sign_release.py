"""CI only. The signing key is injected as a GitHub Actions secret."""
import os,sys,json,hashlib,base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from update_signature import canonical

archive=Path(sys.argv[1]);version=sys.argv[2].lstrip('v')
digest=hashlib.sha256()
with archive.open('rb') as stream:
    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
data={'version':version,'size':archive.stat().st_size,'sha256':digest.hexdigest()}
key=Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ['NOVA_UPDATE_SIGNING_KEY'],validate=True))
data['signature']=base64.b64encode(key.sign(canonical(data))).decode()
Path('NOVA-UPDATE.json').write_text(json.dumps(data),encoding='utf-8')
