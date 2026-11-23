import sys,winreg
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

def register_browser():
    if not getattr(sys,'frozen',False):raise ValueError('Utilisez la version compilée de Nova pour l’enregistrer dans Windows.')
    executable=str(Path(sys.executable).resolve());base='Software\\Clients\\StartMenuInternet\\NovaBrowser';prog='Software\\Classes\\NovaBrowserURL'
    def value(path,name,text):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:winreg.SetValueEx(key,name,0,winreg.REG_SZ,text)
    value(base,'','Nova Browser');value(base+'\\DefaultIcon','', '"'+executable+'",0');value(base+'\\shell\\open\\command','', '"'+executable+'"')
    value(base+'\\Capabilities','ApplicationName','Nova Browser');value(base+'\\Capabilities','ApplicationDescription','Navigateur Nova')
    for scheme in ('http','https'):value(base+'\\Capabilities\\URLAssociations',scheme,'NovaBrowserURL')
    value('Software\\RegisteredApplications','Nova Browser',base+'\\Capabilities')
    value(prog,'','Nova Browser URL');value(prog,'URL Protocol','');value(prog+'\\DefaultIcon','', '"'+executable+'",0');value(prog+'\\shell\\open\\command','', '"'+executable+'" --open-url "%1"')
    QDesktopServices.openUrl(QUrl('ms-settings:defaultapps?registeredAppUser=Nova%20Browser'))
