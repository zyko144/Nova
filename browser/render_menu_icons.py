"""Render the same vector glyphs for the native compatible-engine menus."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from menus import menu_icon
from design import ICONS
app=QApplication([])
folder=Path('build/menu-icons');folder.mkdir(parents=True,exist_ok=True)
for name in ICONS:
    if not menu_icon(name,22).pixmap(22,22).save(str(folder/(name+'.png'))):raise RuntimeError('Icon render failed: '+name)
