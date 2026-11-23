import sys,winreg
from pathlib import Path

def set_startup(enabled):
    if not getattr(sys,'frozen',False):return False
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:winreg.SetValueEx(key,'Nova',0,winreg.REG_SZ,'"'+str(Path(sys.executable).resolve())+'" --startup')
        else:
            try:winreg.DeleteValue(key,'Nova')
            except FileNotFoundError:pass
    return True


def integrate():
    if not getattr(sys,'frozen',False):return
    import subprocess,threading
    def work():
        try:subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).parent/'integrate-windows.ps1'),'-Executable',str(Path(sys.executable).resolve())],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError,subprocess.TimeoutExpired):pass
    threading.Thread(target=work,daemon=True).start()
