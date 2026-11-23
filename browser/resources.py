"""Windows resident working set, without a polling/background process."""
import ctypes
from ctypes import wintypes

def renderer_memory(browser):
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    k=ctypes.WinDLL('kernel32',use_last_error=True);p=ctypes.WinDLL('psapi',use_last_error=True);k.OpenProcess.restype=wintypes.HANDLE;k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.CloseHandle.argtypes=[wintypes.HANDLE];p.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    result={}
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from media_view import MediaView
    for i in range(browser.tabs.count()):
        v=browser.tabs.widget(i);pid=v.page().renderProcessPid() if isinstance(v,QWebEngineView) else v.process.processId() if isinstance(v,MediaView) else 0
        if not pid:continue
        h=k.OpenProcess(0x410,False,pid)
        if h:
            try:
                c=Counters();c.cb=ctypes.sizeof(c)
                if p.GetProcessMemoryInfo(h,ctypes.byref(c),c.cb):result[pid]=c.WorkingSetSize
            finally:k.CloseHandle(h)
    return result
