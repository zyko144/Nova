"""Shared, keyboard-accessible menus with consistent icon sizing and sections."""
from PySide6.QtCore import Qt,QByteArray,QSize,QUrl
from PySide6.QtGui import QIcon,QPixmap,QPainter,QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QMenu,QProxyStyle,QStyle,QStyleFactory,QApplication,QWidgetAction,QLabel
from design import svg_icon

_icons={}

def native_context_menu(browser,view,data):
    """Own popups in the Qt top-level window, above embedded native surfaces."""
    import json
    from PySide6.QtCore import QPoint
    result={'id':str(data.get('id','')),'command':-1}
    if browser._private_locked:
        view.send('context-result',json.dumps(result));return
    menu=NovaMenu(browser)
    items={item['name']:item for item in data.get('items',[]) if isinstance(item,dict) and isinstance(item.get('command'),int)}
    def native(title,symbol,name):
        item=items.get(name)
        if item:
            callback=(lambda:result.update(image=True)) if name=='saveImageAs' and data.get('source') else (lambda:result.update(command=item['command']))
            menu.entry(title,symbol,callback,enabled=bool(item.get('enabled')))
    try:
        if data.get('source') or any(name in items for name in ('saveImageAs','copyImage','copyImageLocation')):
            menu.section('Image')
            if data.get('source') and 'saveImageAs' not in items:menu.entry('Enregistrer l’image sous…','download',lambda:result.update(image=True))
            else:native('Enregistrer l’image sous…','download','saveImageAs')
            native('Copier l’image','copy','copyImage')
            native('Copier l’adresse de l’image','copy','copyImageLocation')
            source=QUrl(str(data.get('source','')))
            if 'copyImageLocation' not in items and data.get('source'):menu.entry('Copier l’adresse de l’image','copy',lambda:browser.copy_link(str(data['source'])))
            if source.scheme() in ('http','https'):menu.entry('Ouvrir l’image dans un nouvel onglet','plus',lambda:browser.new_tab(source))
        link=QUrl(str(data.get('link','')))
        if link.scheme() in ('http','https'):
            menu.section('Lien');menu.entry('Ouvrir dans un nouvel onglet','plus',lambda:browser.new_tab(link));native('Enregistrer le lien sous…','download','saveLinkAs');menu.entry('Copier l’adresse du lien','copy',lambda:browser.copy_link(link.toString()))
        if data.get('selection') or data.get('editable'):
            menu.section('Texte')
            for title,symbol,name in [('Couper','copy','cut'),('Copier','copy','copy'),('Coller','paste','paste'),('Tout sélectionner','page','selectAll')]:native(title,symbol,name)
        menu.section('Navigation')
        menu.entry('Retour','back',browser.go_back);menu.entry('Suivant','forward',browser.go_forward);menu.entry('Actualiser','reload',view.reload)
        menu.section('Outils')
        menu.entry('Traduire en français','translate',lambda:browser.translate_french(str(data.get('selection',''))));menu.entry('Capture de la page','capture',browser.capture_page);menu.entry('Protection du site','shield',browser.site_panel);menu.entry('Paramètres Nova','settings',browser.open_settings)
        menu.exec(view.mapToGlobal(QPoint(int(data.get('x',0)),int(data.get('y',0)))))
    finally:
        view.send('context-result',json.dumps(result));menu.deleteLater()
    if result.get('image'):save_context_image(browser,view,str(data.get('source','')))

def save_context_image(browser,view,url):
    import json,uuid
    from pathlib import Path
    from urllib.parse import urlsplit,unquote
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QFileDialog
    from downloads import NativeDownload
    if browser._private_locked:return
    name=Path(unquote(urlsplit(url).path)).name if url.startswith(('https://','http://')) else 'image.png'
    if not name or len(name)>180:name='image.png'
    folder=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation) or str(Path.home())
    path,_=QFileDialog.getSaveFileName(browser,'Enregistrer l’image sous…',str(Path(folder)/name),'Images (*);;Tous les fichiers (*)')
    if not path:return
    ident=uuid.uuid4().hex;item=NativeDownload(view,ident,path);item.data['supportsPause']=False
    view._downloads=getattr(view,'_downloads',{});view._downloads[ident]=item;browser.download_panel.add(item,path)
    view.send('save-image',json.dumps({'id':ident,'path':path,'url':url}));browser.downloads_menu()
def menu_icon(name,size=22):
    key=(name,size)
    if key not in _icons:
        p=QPixmap(size,size);p.fill(Qt.GlobalColor.transparent);r=QSvgRenderer(QByteArray(svg_icon(name,'#c9c9d2').encode()));paint=QPainter(p);r.render(paint);paint.end();_icons[key]=QIcon(p)
    return _icons[key]

class MenuStyle(QProxyStyle):
    def pixelMetric(self,metric,option=None,widget=None):
        if metric==QStyle.PixelMetric.PM_SmallIconSize:return 22
        return super().pixelMetric(metric,option,widget)

class NovaMenu(QMenu):
    def __init__(self,parent=None,title=''):
        super().__init__(title,parent);self.setMinimumWidth(286);self.setFont(QFont('Segoe UI',10));self.setCursor(Qt.CursorShape.ArrowCursor)
        self._menu_style=MenuStyle(QStyleFactory.create(QApplication.style().objectName()));self._menu_style.setParent(self);self.setStyle(self._menu_style)
        self.setStyleSheet('QMenu{background:#19191d;color:#dedee5;border:1px solid #393940;border-radius:11px;padding:6px}QMenu::item{padding:9px 13px;margin:1px 2px;border-radius:6px}QMenu::item:selected{background:#303037;color:#f1f1f4}QMenu::item:disabled{color:#71717c}QMenu::separator{height:1px;background:#33333b;margin:6px 10px}QMenu::icon{padding:0;margin-left:5px}QMenu::right-arrow{width:7px;height:10px}')
    def showEvent(self,event):
        super().showEvent(event)
        from motion import fade_popup
        owner=self.parentWidget()
        while owner is not None and not hasattr(owner,'data'):owner=owner.parentWidget()
        fade_popup(self,owner)
    def section(self,title):
        label=QLabel(title);label.setTextFormat(Qt.TextFormat.PlainText);label.setStyleSheet('QLabel{background:transparent;color:#92929f;font-size:11px;font-weight:500;padding:10px 12px 4px}');action=QWidgetAction(self);action.setDefaultWidget(label);action.setEnabled(False);self.addAction(action);return action
    def entry(self,title,symbol,callback=None,shortcut='',enabled=True):
        label=' '.join(title.split()).replace('&','&&')+('\t'+shortcut if shortcut else '')
        action=self.addAction(menu_icon(symbol),label);action.setEnabled(enabled);action.setIconVisibleInMenu(True)
        if callback:action.triggered.connect(lambda checked=False:callback())
        return action
    def submenu(self,title,symbol):
        menu=NovaMenu(self,title);menu.setIcon(menu_icon(symbol));self.addMenu(menu);return menu

def build_main_menu(browser):
    b=browser;menu=NovaMenu(b);menu.setMinimumWidth(326)
    menu.section('Navigation')
    menu.entry('Nouvel onglet','plus',lambda:b.new_tab(),'Ctrl+T')
    menu.entry('Nouvelle fenêtre privée','private',b.private_window,'Ctrl+Maj+N')
    if b.private:menu.entry('Verrouiller cette fenêtre','lock',b.lock_private_window)
    if not b.presentation:
        for title,data_key,symbol in [('Favoris','bookmarks','star'),('Historique','history','history')]:
            sub=menu.submenu(title,symbol)
            for item in b.data[data_key][:40]:sub.entry(item['title'][:55] or item['url'],'page',lambda url=item['url']:b.new_tab(QUrl(url)))
            if not b.data[data_key]:sub.entry('Aucun élément','page',enabled=False)
    menu.section('Outils')
    page=menu.submenu('Outils de la page','page')
    for title,symbol,callback,shortcut in [('Traduire en français','translate',b.translate_french,''),('Capturer la page','capture',b.capture_page,'Ctrl+Maj+S'),('Bloc-notes','notes',b.notes,''),('Lecteur flottant','video',b.floating_player,''),('Couper / réactiver le son','sound',b.toggle_mute,'Ctrl+Maj+M')]:page.entry(title,symbol,callback,shortcut)
    display=menu.submenu('Affichage','display')
    display.entry('Quitter le mode concentration' if b.focus_mode else 'Mode concentration','focus',b.toggle_focus,'Ctrl+Maj+F')
    display.entry('Quitter le mode présentation' if b.presentation else 'Mode présentation','display',b.toggle_presentation,'Ctrl+Maj+P')
    display.entry('Quitter le plein écran' if b.isFullScreen() else 'Plein écran','max',b.toggle_browser_fullscreen,'F11')
    menu.entry('Activité des onglets','performance',b.resource_panel)
    if not b.private and not b.presentation:
        menu.section('Compte et données')
        menu.entry('Compte Google','profile',b.open_account)
        data=menu.submenu('Données et session','folder')
        data.entry('Importer mes données…','import',b.open_import)
        data.entry('Restaurer la dernière session','history',b.restore_session,enabled=bool(b.previous_session.get('tabs')))
        data.entry('Effacer historique et cache…','trash',b.clear)
        profiles=menu.submenu('Profils locaux','profile')
        for ident,name in b.data['profiles'].items():profiles.entry(name+(' · Actif' if ident==b.data['active'] else ''),'profile',lambda ident=ident:b.switch_profile(ident))
        profiles.addSeparator();profiles.entry('Créer un profil…','plus',b.create_profile)
    menu.section('Nova')
    menu.entry('Protection du site','shield',b.site_panel)
    menu.entry('Paramètres','settings',b.open_settings)
    more=menu.submenu('Plus d’options','menu')
    more.entry('Ajouter une application…','plus',b.add_shortcut)
    more.entry('Navigateur par défaut','home',b.make_default)
    compatibility=more.submenu('Compatibilité et extensions','extensions')
    compatibility.entry('Moteur vidéo compatible','video',b.compatible_video)
    compatibility.entry('Moteur classique','page',b.classic_mode)
    compatibility.entry('Réglages du bloqueur','shield',b.extensions_info)
    more.entry('Revoir la présentation','display',b.show_welcome)
    more.entry('À propos et mises à jour','info',lambda:b.open_settings(9))
    return menu
