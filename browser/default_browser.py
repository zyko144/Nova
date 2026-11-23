import sys,winreg
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

def is_default_browser():
    for scheme in ('http','https'):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\'+scheme+'\\UserChoice') as key:
                if winreg.QueryValueEx(key,'ProgId')[0]!='NovaBrowserURL':return False
        except OSError:return False
    return True

def register_browser(open_settings=True):
    if not getattr(sys,'frozen',False):raise ValueError('Utilisez la version compilée de Nova pour l’enregistrer dans Windows.')
    executable=str(Path(sys.executable).resolve());base='Software\\Clients\\StartMenuInternet\\NovaBrowser';prog='Software\\Classes\\NovaBrowserURL'
    def value(path,name,text):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:winreg.SetValueEx(key,name,0,winreg.REG_SZ,text)
    value(base,'','Nova');value(base+'\\DefaultIcon','', '"'+executable+'",0');value(base+'\\shell\\open\\command','', '"'+executable+'"')
    value(base+'\\Capabilities','ApplicationName','Nova');value(base+'\\Capabilities','ApplicationDescription','Navigateur Nova')
    value(base+'\\Capabilities','ApplicationIcon','"'+executable+'",0')
    for scheme in ('http','https'):value(base+'\\Capabilities\\URLAssociations',scheme,'NovaBrowserURL')
    value('Software\\RegisteredApplications','Nova',base+'\\Capabilities')
    value(prog,'','Nova URL');value(prog,'URL Protocol','');value(prog+'\\DefaultIcon','', '"'+executable+'",0');value(prog+'\\shell\\open\\command','', '"'+executable+'" --open-url "%1"')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\RegisteredApplications',0,winreg.KEY_SET_VALUE) as key:winreg.DeleteValue(key,'Nova Browser')
    except OSError:pass
    if open_settings:QDesktopServices.openUrl(QUrl('ms-settings:defaultapps?registeredAppUser=Nova'))
