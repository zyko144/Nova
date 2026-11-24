"""Nova first-run identity and explicit local data import."""
import os,threading,sqlite3
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl,Signal,QObject,QSize,QRectF,QVariantAnimation
from PySide6.QtGui import QColor,QPainter,QLinearGradient
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QCheckBox,QFileDialog,QGraphicsOpacityEffect,QProgressBar,QScrollArea,QFileIconProvider,QSizePolicy
from PySide6.QtCore import QFileInfo,QStandardPaths
from ui import NovaDialog
from import_data import profiles,read_profile,read_export,apply_import,password_exports
from mascot import Mascot
from motion import enabled
from surfaces import round_popup

STYLE="""QWidget#novaWelcome{background:#101014}QWidget#importPanel{background:transparent}QLabel{background:transparent;color:#b7b5c1;font-family:'Segoe UI';font-size:14px}QPushButton{background:transparent;color:#f0edf5;border:1px solid #76618f;border-radius:17px;padding:8px 15px;font-size:12px}QPushButton:hover{background:#24202f}QPushButton#primary{background:#b596ff;color:#171121;border:0;font-weight:500}QPushButton#primary:hover{background:#c5adff}QPushButton:disabled{color:#777580;border-color:#39343e}QComboBox{background:#151419;color:#eeeaf4;border:1px solid #8e75b0;border-radius:20px;padding:11px 16px;font-size:14px;min-height:22px}QComboBox QAbstractItemView{background:#202025;color:#eee;border:1px solid #68577f;padding:6px;selection-background-color:#383043}QCheckBox{color:#eeeaf4;font-size:14px;spacing:11px;padding:5px 0}QCheckBox::indicator{width:17px;height:17px;border:1px solid #8b769f;border-radius:5px;background:#211b2b}QCheckBox::indicator:checked{background:#b596ff;border:1px solid #c6adff}QCheckBox:disabled{color:#6b6874}QProgressBar{background:#2f2c36;border:0;border-radius:1px}QProgressBar::chunk{background:#b596ff;border-radius:1px}"""

class GradientButton(QPushButton):
    def __init__(self,text='',warm=False):
        super().__init__(text)
        self.warm=warm
        self.phase=0.0
        self.setMinimumHeight(37)
        self.setStyleSheet('QPushButton{padding:7px 17px;font-size:13px;font-weight:600;border:0}')
        self.motion=QVariantAnimation(self)
        self.motion.setDuration(1700)
        self.motion.setStartValue(0.0)
        self.motion.setKeyValueAt(.5,1.0)
        self.motion.setEndValue(0.0)
        self.motion.setLoopCount(-1)
        self.motion.valueChanged.connect(self.shift_gradient)

    def shift_gradient(self,value):
        self.phase=float(value)
        self.update()

    def refresh_motion(self):
        owner=self.window()
        while owner is not None and not isinstance(getattr(owner,'data',None),dict):
            owner=owner.parentWidget()
        if self.isVisible() and self.isEnabled() and (self.underMouse() or self.hasFocus()) and enabled(owner):
            if self.motion.state()!=QVariantAnimation.State.Running:
                self.motion.start()
        else:
            self.motion.stop()
            self.shift_gradient(0)

    def event(self,event):
        result=super().event(event)
        from PySide6.QtCore import QEvent
        if hasattr(self,'motion') and event.type() in (QEvent.Type.Enter,QEvent.Type.Leave,QEvent.Type.FocusIn,QEvent.Type.FocusOut,QEvent.Type.Hide,QEvent.Type.EnabledChange):
            self.refresh_motion()
        return result

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds=QRectF(self.rect()).adjusted(1,1,-1,-1)
        gradient=QLinearGradient(0,0,bounds.width(),bounds.height())
        colors=('#b8572e','#873bc6','#6733a5') if self.warm else ('#6633b4','#7938bb','#b24c28')
        if not self.isEnabled():
            colors=('#332a40','#3a3045','#413039')
        gradient.setColorAt(0,QColor(colors[0]))
        gradient.setColorAt(.39+.25*self.phase,QColor(colors[1]))
        gradient.setColorAt(1,QColor(colors[2]))
        painter.setBrush(gradient)
        painter.setPen(QColor('#ffad70' if self.warm else '#c19aff'))
        radius=bounds.height()/2
        painter.drawRoundedRect(bounds,radius,radius)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor('#f3deff'))
            painter.drawRoundedRect(bounds.adjusted(3,3,-3,-3),radius-3,radius-3)
        painter.setFont(self.font())
        painter.setPen(QColor('#fff6ff' if self.isEnabled() else '#ac9cb4'))
        painter.drawText(bounds,Qt.AlignmentFlag.AlignCenter,self.text())

class ImportSignals(QObject):
    done=Signal(object)
    failed=Signal(str)

def clear_import(result):
    for row in result.get('credentials',[]):row.clear()
    result.clear()

def source_icon(label):
    local=Path(os.environ.get('LOCALAPPDATA',''));programs=Path(os.environ.get('PROGRAMFILES','C:/Program Files'));programs86=Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))
    choices={'Chrome':[programs/'Google/Chrome/Application/chrome.exe',local/'Google/Chrome/Application/chrome.exe'],'Edge':[programs86/'Microsoft/Edge/Application/msedge.exe',programs/'Microsoft/Edge/Application/msedge.exe'],'Brave':[programs/'BraveSoftware/Brave-Browser/Application/brave.exe'],'Firefox':[programs/'Mozilla Firefox/firefox.exe'],'Opera':[local/'Programs/Opera/opera.exe']}
    for name,paths in choices.items():
        if label.startswith(name) or name=='Edge' and label.startswith('Microsoft Edge'):
            for path in paths:
                if path.is_file():return QFileIconProvider().icon(QFileInfo(str(path)))
    from menus import menu_icon
    return menu_icon('import',24)

class ImportPanel(QWidget):
    completed=Signal(object)
    busyChanged=Signal(bool)
    finished=Signal(bool)
    def __init__(self,browser,parent=None):
        super().__init__(parent);self.browser=browser;self.imported=False;self.cancelled=threading.Event();self.busy=False;self.password_file=None;self.setObjectName('importPanel');self.setStyleSheet(STYLE);self.sources=profiles();self.directory=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        self.body=QVBoxLayout(self);self.body.setContentsMargins(0,0,0,0);self.body.setSpacing(11)
        self.combo=QComboBox();self.combo.setIconSize(QSize(25,25))
        for label,path in self.sources:self.combo.addItem(source_icon(label),label)
        if not self.sources:self.combo.addItem('Choisir un fichier exporté');self.combo.setEnabled(False)
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.combo.setMinimumContentsLength(18);self.body.addWidget(self.combo);view=self.combo.view();round_popup(view.window() if view.window().windowType()==Qt.WindowType.Popup else view,12)
        self.body.addSpacing(6);label=QLabel('Choisissez les données à importer.');label.setStyleSheet('font-size:12px;color:#aaa5b5');self.body.addWidget(label);self.caption=label
        self.bookmarks=QCheckBox('Favoris');self.passwords=QCheckBox('Mots de passe enregistrés');self.history=QCheckBox('Historique de navigation');self.autofill=QCheckBox('Remplissage automatique')
        for box in (self.bookmarks,self.passwords,self.history,self.autofill):box.setChecked(True);self.body.addWidget(box)
        self.note=QLabel('Mots de passe : depuis un export CSV. Saisie : adresses e-mail compatibles.');self.note.setWordWrap(True);self.note.setStyleSheet('font-size:12px;color:#8f899e');self.body.addWidget(self.note)
        self.file_button=QPushButton('Choisir un export de mots de passe…');self.file_button.setStyleSheet('QPushButton{border:0;padding:0;color:#b596ff;text-align:left;font-size:12px}QPushButton:hover{text-decoration:underline}');self.file_button.clicked.connect(self.choose_passwords);self.body.addWidget(self.file_button,0,Qt.AlignmentFlag.AlignLeft)
        row=QHBoxLayout();self.import_button=GradientButton('Importer');self.import_button.setObjectName('primary');self.import_button.clicked.connect(self.start);row.addWidget(self.import_button);row.addStretch();self.body.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setFixedHeight(3);self.progress.hide();self.body.addWidget(self.progress)
        self.status=QLabel('');self.status.setTextFormat(Qt.TextFormat.PlainText);self.status.setWordWrap(True);self.status.setStyleSheet('font-size:12px;color:#b7a6d5');self.body.addWidget(self.status)
        self.job=ImportSignals(self);self.job.done.connect(self.apply);self.job.failed.connect(self.failed);self.combo.currentIndexChanged.connect(self.update_source);self.passwords.toggled.connect(self.file_button.setVisible);self.update_source()
    def update_source(self,*args):
        path=self.sources[self.combo.currentIndex()][1] if self.sources else None;firefox=path is not None and (path/'places.sqlite').is_file()
        self.bookmarks.setEnabled(bool(path and ((path/'Bookmarks').is_file() or firefox)));self.history.setEnabled(bool(path and ((path/'History').is_file() or firefox)));self.autofill.setEnabled(bool(self.browser.vault is not None and path and ((path/'Web Data').is_file() or (path/'formhistory.sqlite').is_file())));self.passwords.setEnabled(self.browser.vault is not None)
    def choose_passwords(self):
        path,_=QFileDialog.getOpenFileName(self,'Choisir les mots de passe exportés',self.directory,'Mots de passe (*.csv)')
        if path:self.password_file=Path(path);self.file_button.setText(self.password_file.name)
    def set_busy(self,busy):
        self.busy=busy;self.import_button.setEnabled(not busy);self.combo.setEnabled(not busy and bool(self.sources));self.progress.setVisible(busy);self.file_button.setEnabled(not busy)
        for box in (self.bookmarks,self.passwords,self.history,self.autofill):box.setEnabled(not busy)
        if not busy:self.update_source()
        self.busyChanged.emit(busy)
    def available_password_export(self):
        if self.password_file:
            return self.password_file
        if not self.sources:
            return None
        source=self.combo.currentText().split(' · ',1)[0].casefold()
        names={'chrome':('chrome','google'),'microsoft edge':('edge',),'brave':('brave',),'firefox':('firefox',),'opera':('opera',)}
        return next((file for file in password_exports(self.directory)
                     if any(name in file.stem.casefold() for name in names.get(source,()))),None)

    def start(self):
        if self.busy or self.browser.private:
            return
        wants_passwords=self.passwords.isEnabled() and self.passwords.isChecked()
        password_file=self.available_password_export() if wants_passwords else None
        if not self.sources:
            if password_file:
                self.launch(backup=password_file)
            else:
                self.restore()
            return
        path=self.sources[self.combo.currentIndex()][1]
        selection=tuple(box.isEnabled() and box.isChecked() for box in (self.bookmarks,self.history,self.autofill))
        if not any(selection) and password_file is None:
            if wants_passwords:
                self.status.setText('Ajoutez le CSV exporté par le navigateur pour importer les mots de passe.')
            else:
                self.status.setText('Sélectionnez au moins une catégorie.')
            return
        self.launch(path,selection,password_file,missing_passwords=wants_passwords and password_file is None)

    def launch(self,path=None,selection=(False,False,False),password_file=None,backup=None,missing_passwords=False):
        self.cancelled.clear()
        cancelled=self.cancelled
        job=self.job
        self.set_busy(True)
        self.status.setText('Importation en cours…')
        def read():
            result={}
            notices=[]
            try:
                if backup:
                    result=read_export(backup)
                else:
                    categories=('Favoris','Historique','Remplissage')
                    for index,selected in enumerate(selection):
                        if not selected:
                            continue
                        flags=tuple(i==index for i in range(3))
                        key=('bookmarks','history','emails')[index]
                        try:
                            result[key]=read_profile(path,*flags).get(key,[])
                        except (OSError,ValueError,sqlite3.Error):
                            notices.append(categories[index]+' : réessayez après avoir fermé le navigateur source.')
                    if password_file:
                        try:
                            result['credentials']=read_export(password_file)['credentials']
                            if not result['credentials']:
                                notices.append('Le CSV ne contient aucun identifiant compatible.')
                        except (OSError,ValueError,TypeError,KeyError):
                            notices.append('Choisissez un export CSV valide pour les mots de passe.')
                    elif missing_passwords:
                        notices.append('Les mots de passe peuvent être ajoutés avec un export CSV.')
                if cancelled.is_set():
                    clear_import(result)
                    return
                job.done.emit((result,notices))
            except Exception:
                clear_import(result)
                try:
                    job.failed.emit('Vérifiez le fichier choisi ou réessayez après avoir fermé le navigateur source.')
                except RuntimeError:
                    pass
        threading.Thread(target=read,daemon=True).start()

    def apply(self,payload):
        result,notices=payload
        try:
            if self.cancelled.is_set():
                return
            try:
                counts=apply_import(self.browser,result)
            except (OSError,ValueError,RuntimeError):
                if not (result.get('credentials') or result.get('emails')):
                    raise
                counts=apply_import(self.browser,{key:result.get(key,[]) for key in ('bookmarks','history')})
                notices.append('Identifiants et e-mails : vérifiez le coffre Windows.')
            self.browser.refresh_home_tabs()
            self.imported=bool(sum(counts.values()))
            summary=f"{counts['bookmarks']} favoris · {counts['history']} pages · {counts['credentials']} identifiants · {counts.get('emails',0)} e-mails."
            self.status.setText(' '.join([summary,*notices]))
            if self.imported:
                self.completed.emit(counts)
                self.finished.emit(True)
        except (OSError,ValueError,RuntimeError):
            self.status.setText('Vérifiez le fichier et la disponibilité du coffre Windows.')
        finally:
            clear_import(result)
            self.set_busy(False)

    def failed(self,message):self.status.setText(message);self.set_busy(False)
    def restore(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,'Restaurer des données locales',self.directory,'Sauvegardes et exports (*.json *.html *.htm *.csv)')
        if path:self.launch(backup=path)
    def reject(self):self.cancelled.set();self.hide();self.finished.emit(self.imported)

class ImportDialog(NovaDialog):
    def __init__(self,browser):
        super().__init__(browser,'Vos données, dans Nova.','Choisissez le profil source et les catégories à récupérer.',symbol='import');self.setMinimumWidth(560);self.imported=False;self.panel=ImportPanel(browser,self);self.body.addWidget(self.panel);self.panel.completed.connect(self.import_done);self.finished.connect(lambda *args:self.panel.cancelled.set());self.buttons('Terminer','Fermer')
    def import_done(self,counts):self.imported=True

class Welcome(QWidget):
    """Responsive first-run pages built from native, interactive controls."""
    def __init__(self,browser):
        super().__init__(browser)
        self.setObjectName('novaWelcome')
        self.browser=browser
        self.step=0
        self.confirm_skip=False
        check=(Path(__file__).parent/'assets/import-check.svg').as_posix()
        chevron=(Path(__file__).parent/'assets/import-chevron.svg').as_posix()
        self.setStyleSheet(STYLE+f'QCheckBox{{font-size:16px}}QCheckBox::indicator:checked{{image:url("{check}")}}QComboBox{{font-size:16px}}QComboBox::drop-down{{border:0;width:36px}}QComboBox::down-arrow{{image:url("{chevron}");width:16px;height:16px}}')
        root=QVBoxLayout(self)
        root.setContentsMargins(36,22,36,22)
        root.setSpacing(16)
        header=QHBoxLayout()
        from main import icon
        logo=QLabel()
        logo.setPixmap(icon('logo',40).pixmap(40,40))
        header.addWidget(logo)
        brand=QLabel('Nova')
        brand.setStyleSheet('font-size:24px;font-weight:600;color:#f4eefb')
        header.addWidget(brand)
        header.addStretch()
        self.restore_button=QPushButton('Restaurer une sauvegarde')
        self.restore_button.clicked.connect(self.restore_backup)
        self.login_button=QPushButton('Connexion')
        self.login_button.clicked.connect(self.sign_in)
        header.addWidget(self.restore_button)
        header.addWidget(self.login_button)
        root.addLayout(header)

        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea{border:0;background:transparent}QScrollArea>QWidget>QWidget{background:#101014}')
        content=QWidget()
        self.columns=QHBoxLayout(content)
        self.columns.setContentsMargins(0,0,0,0)
        self.columns.setSpacing(30)
        self.columns.addStretch(1)
        copy=QWidget()
        copy.setMaximumWidth(650)
        left=QVBoxLayout(copy)
        left.setContentsMargins(0,8,0,8)
        left.setSpacing(12)
        left.addStretch()
        self.title=QLabel()
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.description=QLabel()
        self.description.setWordWrap(True)
        self.description.setStyleSheet('font-size:16px;color:#cbc5d3')
        left.addWidget(self.title)
        left.addWidget(self.description)
        self.import_panel=ImportPanel(browser,copy)
        self.import_panel.completed.connect(self.import_done)
        self.import_panel.body.setSpacing(6)
        self.import_panel.setStyleSheet('')
        left.addWidget(self.import_panel)
        self.action=GradientButton()
        self.action.clicked.connect(self.perform)
        left.addWidget(self.action,0,Qt.AlignmentFlag.AlignLeft)
        left.addStretch()
        self.columns.addWidget(copy,6)
        self.mascot=Mascot(browser,content)
        self.mascot.setMaximumSize(680,520)
        self.mascot.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.columns.addWidget(self.mascot,5)
        self.columns.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll,1)

        self.note=QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self.note)
        footer=QHBoxLayout()
        self.progress=QLabel()
        footer.addWidget(self.progress)
        footer.addStretch()
        self.skip=GradientButton('Ignorer cette étape →',warm=True)
        self.skip.clicked.connect(self.skip_step)
        self.next=GradientButton('Continuer')
        self.next.clicked.connect(self.advance)
        footer.addWidget(self.skip)
        footer.addWidget(self.next)
        root.addLayout(footer)
        self.progress_bar=QProgressBar()
        self.progress_bar.setRange(0,4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        root.addWidget(self.progress_bar)
        browser.sync_client.signedIn.connect(self.signed_in)
        browser.sync_client.google.failed.connect(self.sign_in_failed)
        self.render()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.update_title_size()

    def update_title_size(self):
        large=self.width()>=1100
        size=(47 if large else 34) if self.step==0 else (38 if large else 30)
        self.title.setStyleSheet(f'color:#f5f1fa;font-weight:600;font-size:{size}px')

    def render(self):
        rows=[('Bienvenue dans <span style="color:#b596ff">Nova.</span>','Vos sites, vos habitudes. Un navigateur sombre et simple, avec les outils utiles à portée de main.','Commencer'),('Vos données, <span style="color:#b596ff">votre Nova.</span>','Retrouvez vos favoris, votre historique et vos identifiants.','Importer'),('Votre compte.<br><span style="color:#b596ff">Votre identité.</span>','Connectez Google pour retrouver votre nom et votre photo dans Nova. Les identifiants des sites s’importent séparément.','Continuer avec Google'),('Prêt pour<br><span style="color:#b596ff">la suite.</span>','Onglets en pause, téléchargements suivis et réglages compacts. Tout reste accessible depuis le menu Nova.','Personnaliser Nova')]
        title,description,action=rows[self.step];self.setAccessibleName(('Bienvenue dans Nova','Vos données, votre Nova','Votre compte Google','Nova est prêt')[self.step]);self.setAccessibleDescription(description);self.title.setText(title);self.description.setText(description);self.action.setText(action);self.action.setVisible(self.step!=1);self.import_panel.setVisible(self.step==1);self.progress.setText(f'Étape {self.step+1} sur 4');self.progress_bar.setValue(self.step+1);self.next.setText('Entrer dans Nova' if self.step==3 else 'Continuer');self.next.setVisible(self.step in (2,3) or self.step==1 and self.import_panel.imported);self.skip.setVisible(self.step<3 and not (self.step==1 and self.import_panel.imported));self.skip.setText('Continuer sans importer →' if self.step==1 and self.confirm_skip else 'Ignorer cette étape →');self.note.setText(('Import possible plus tard. Cliquez encore pour continuer sans importer.' if self.width()<1100 else 'Vous pourrez importer plus tard dans les paramètres. Cliquez encore pour continuer sans importer.') if self.step==1 and self.confirm_skip and not self.import_panel.imported else '');self.note.setVisible(bool(self.note.text()));self.update_title_size()
    def perform(self):
        if self.step==0:self.advance()
        elif self.step==1:self.import_panel.show()
        elif self.step==2:self.sign_in()
        else:self.finish();self.browser.open_settings(0)
    def import_done(self,counts):self.confirm_skip=True;self.note.setText('Vos données ont été importées. Vous pouvez continuer.');self.note.show();self.next.show();self.skip.hide()
    def restore_backup(self):self.step=1;self.confirm_skip=False;self.render();self.import_panel.restore()
    def sign_in(self):self.note.setText('Ouverture de Google…');self.note.show();self.browser.sync_client.google.start('')
    def sign_in_failed(self,message):self.note.setText(str(message));self.note.show()
    def signed_in(self,email):
        if email:self.login_button.setText('Connecté');self.note.setText('Connecté à Google · '+email);self.note.show()
    def advance(self):
        if self.step==1 and not self.confirm_skip and not self.import_panel.imported:self.confirm_skip=True;self.render();return
        if self.step==3:self.finish();return
        if self.step==1 and not self.import_panel.imported:self.import_panel.cancelled.set()
        self.step+=1;self.confirm_skip=False;self.render()
    def skip_step(self):
        if self.step==1 and not self.confirm_skip and not self.import_panel.imported:self.confirm_skip=True;self.render();return
        self.advance()
    def finish(self):self.import_panel.cancelled.set();self.browser.data['welcome_completed']=True;self.browser.data['welcome_identity_seen']=True;self.browser.save();self.hide();self.browser.welcome=None;QTimer.singleShot(500,self.browser.offer_default_browser);self.deleteLater()
    def reject(self):self.skip_step() if self.step<3 else self.finish()
