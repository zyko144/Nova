"""Local heuristics: explainable warnings, not a malware reputation service."""
import re,unicodedata
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit

BRANDS={'google':'google.com','youtube':'youtube.com','gmail':'gmail.com','discord':'discord.com','paypal':'paypal.com','microsoft':'microsoft.com','amazon':'amazon.fr','netflix':'netflix.com','apple':'apple.com'}
CONFUSABLES=str.maketrans({'а':'a','е':'e','о':'o','р':'p','с':'c','х':'x','у':'y','і':'i','ј':'j','ѕ':'s','ο':'o','Ι':'i','ⅼ':'l'})
SENSITIVE=re.compile(r'(?:^|_)(?:token|access_token|id_token|refresh_token|secret|password|code|auth|signature|sig|reset)(?:$|_)',re.I)
DANGEROUS={'.exe','.msi','.msix','.com','.scr','.bat','.cmd','.ps1','.vbs','.js','.jse','.hta','.lnk','.reg','.iso'}

def host_of(url):
    try:return (urlsplit(url).hostname or '').lower().rstrip('.')
    except ValueError:return ''

def suspicious(url):
    host=host_of(url)
    if not host:return ''
    try:decoded=host.encode('ascii').decode('idna')
    except (UnicodeError,ValueError):decoded=host
    scripts={unicodedata.name(c,'').split(' ')[0] for c in decoded if c.isalpha()}
    skeleton=decoded.translate(CONFUSABLES).casefold()
    if len(scripts.intersection({'LATIN','CYRILLIC','GREEK'}))>1:return 'Cette adresse mélange des alphabets : '+decoded
    for brand,domain in BRANDS.items():
        trusted=(domain,'www.'+domain)
        if host==domain or host.endswith('.'+domain):continue
        # Brand names inside another registrable-looking domain deserve review.
        if brand in skeleton.split('.')[0] or host.startswith(brand+'.'):
            return 'Cette adresse ressemble à '+brand+' mais le domaine est '+decoded
    if urlsplit(url).username:return 'Cette adresse contient un identifiant avant le vrai domaine : '+host
    return ''

def download_warning(name):
    from pathlib import PurePath
    name=PurePath(name).name.lower().rstrip(' .')
    if '\u202e' in name:return 'Le nom contient un caractère qui peut inverser l’affichage de son extension.'
    suffix=PurePath(name).suffix
    if suffix in DANGEROUS:
        if re.search(r'\.(jpg|jpeg|png|pdf|mp4|docx|txt)\.',name):return 'Double extension trompeuse : ce fichier peut exécuter du code.'
        return 'Ce type de fichier peut exécuter du code sur votre appareil.'
    return ''

def sensitive_link(url):
    try:
        p=urlsplit(url)
        return any(SENSITIVE.search(k) for k,v in parse_qsl(p.query)+parse_qsl(p.fragment))
    except ValueError:return True

def without_sensitive(url):
    p=urlsplit(url)
    query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not SENSITIVE.search(k)])
    fragment='' if any(SENSITIVE.search(k) for k,v in parse_qsl(p.fragment)) else p.fragment
    return urlunsplit((p.scheme,p.netloc,p.path,query,fragment))

def upgrade_http(url,exceptions=()):
    p=urlsplit(url)
    if p.scheme=='http' and p.hostname not in ('localhost','127.0.0.1','::1') and p.hostname not in exceptions:
        return urlunsplit(('https',p.netloc,p.path,p.query,p.fragment))
    return url
