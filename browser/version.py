import os,re
from pathlib import Path

VERSION='3.6.2'
REPOSITORY='zyko144/Nova'
RELEASE_ASSET='NovaBrowser-Windows-x64.zip'
GOOGLE_DESKTOP_CLIENT_ID='54433304112-0h0sotfg4l7ql274mk9l5grjg1bhgjj1.apps.googleusercontent.com'
try:
    local_id=(Path(os.environ['LOCALAPPDATA'])/'NovaBrowser'/'NovaBrowser'/'google-client-id.txt').read_text(encoding='utf-8').strip()
    if re.fullmatch(r'[0-9]+-[A-Za-z0-9]+\.apps\.googleusercontent\.com',local_id):GOOGLE_DESKTOP_CLIENT_ID=local_id
except (KeyError,OSError,UnicodeError):pass
