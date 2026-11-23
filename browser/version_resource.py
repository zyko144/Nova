from pathlib import Path
from version import VERSION
numbers=tuple(map(int,VERSION.split('.')))+(0,)
path=Path('build/Nova-version.txt');path.parent.mkdir(exist_ok=True)
path.write_text(f'''VSVersionInfo(ffi=FixedFileInfo(filevers={numbers!r},prodvers={numbers!r},mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('040c04b0',[StringStruct('CompanyName','Nova'),StringStruct('FileDescription','Nova'),StringStruct('FileVersion','{VERSION}'),StringStruct('InternalName','Nova'),StringStruct('OriginalFilename','Nova.exe'),StringStruct('ProductName','Nova'),StringStruct('ProductVersion','{VERSION}')])]),VarFileInfo([VarStruct('Translation',[1036,1200])])])''',encoding='utf-8')
