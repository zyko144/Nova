"""Nova first-run identity and explicit local data import."""
import os,threading
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl,Signal,QObject,QSize,QRectF
from PySide6.QtGui import QPixmap,QPainter,QColor,QIcon,QDesktopServices
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QComboBox,QCheckBox,QFileDialog,QGraphicsOpacityEffect,QProgressBar,QScrollArea,QFileIconProvider
from PySide6.QtCore import QFileInfo,QStandardPaths
from ui import NovaDialog,NovaMessage
from import_data import profiles,read_profile,read_export,apply_import,password_exports
from mascot import Mascot
from motion import enabled
from surfaces import round_popup

STYLE="""QWidget#novaWelcome{background:#101014}QWidget#importPanel{background:transparent}QLabel{background:transparent;color:#b7b5c1;font-family:'Segoe UI';font-size:14px}QPushButton{background:transparent;color:#f0edf5;border:1px solid #76618f;border-radius:17px;padding:8px 15px;font-size:12px}QPushButton:hover{background:#24202f}QPushButton#primary{background:#b596ff;color:#171121;border:0;font-weight:500}QPushButton#primary:hover{background:#c5adff}QPushButton:disabled{color:#777580;border-color:#39343e}QComboBox{background:#151419;color:#eeeaf4;border:1px solid #8e75b0;border-radius:20px;padding:11px 16px;font-size:14px;min-height:22px}QComboBox QAbstractItemView{background:#202025;color:#eee;border:1px solid #68577f;padding:6px;selection-background-color:#383043}QCheckBox{color:#eeeaf4;font-size:14px;spacing:11px;padding:5px 0}QCheckBox::indicator{width:17px;height:17px;border:1px solid #8b769f;border-radius:5px;background:#211b2b}QCheckBox::indicator:checked{background:#b596ff;border:1px solid #c6adff}QCheckBox:disabled{color:#6b6874}QProgressBar{background:#2f2c36;border:0;border-radius:1px}QProgressBar::chunk{background:#b596ff;border-radius:1px}"""

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
        row=QHBoxLayout();self.import_button=QPushButton('Importer');self.import_button.setObjectName('primary');self.import_button.clicked.connect(self.start);row.addWidget(self.import_button);row.addStretch();self.body.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setFixedHeight(3);self.progress.hide();self.body.addWidget(self.progress)
        self.status=QLabel('');self.status.setTextFormat(Qt.TextFormat.PlainText);self.status.setWordWrap(True);self.status.setStyleSheet('font-size:12px;color:#b7a6d5');self.body.addWidget(self.status)
        self.job=ImportSignals(self);self.job.done.connect(self.apply);self.job.failed.connect(self.failed);self.combo.currentIndexChanged.connect(self.update_source);self.passwords.toggled.connect(self.file_button.setVisible);self.update_source()
        detected=password_exports(self.directory)
        if detected:self.directory=str(detected[0])
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
    def start(self):
        if self.busy or self.browser.private:return
        password_file=None
        if self.passwords.isEnabled() and self.passwords.isChecked():
            password_file=self.password_file
            if password_file is None:self.choose_passwords();password_file=self.password_file
            if password_file is None:self.status.setText('Choisissez le CSV du navigateur ou décochez les mots de passe.');return
        if not self.sources:
            if password_file:self.launch(backup=str(password_file))
            else:self.restore()
            return
        path=self.sources[self.combo.currentIndex()][1];selection=(self.bookmarks.isEnabled() and self.bookmarks.isChecked(),self.history.isEnabled() and self.history.isChecked(),self.autofill.isEnabled() and self.autofill.isChecked())
        if not any(selection) and password_file is None:self.status.setText('Sélectionnez au moins une catégorie.');return
        self.launch(path,selection,password_file)
    def launch(self,path=None,selection=(False,False,False),password_file=None,backup=None):
        self.cancelled.clear();cancelled=self.cancelled;job=self.job;self.set_busy(True);self.status.setText('Importation en cours…')
        def read():
            result={}
            try:
                result=read_export(backup) if backup else read_profile(path,selection[0],selection[1],selection[2])
                if password_file:result['credentials']=read_export(password_file)['credentials']
                if cancelled.is_set():clear_import(result);return
                job.done.emit(result)
            except Exception:
                clear_import(result)
                try:job.failed.emit('Lecture impossible. Fermez le navigateur source puis réessayez, ou choisissez un fichier exporté.')
                except RuntimeError:pass
        threading.Thread(target=read,daemon=True).start()
    def apply(self,result):
        try:
            if self.cancelled.is_set():return
            counts=apply_import(self.browser,result);self.imported=True;self.browser.refresh_home_tabs();self.status.setText(f"{counts['bookmarks']} favoris · {counts['history']} pages · {counts['credentials']} identifiants · {counts.get('emails',0)} adresses e-mail importés.");self.completed.emit(counts);self.finished.emit(True)
        except (OSError,ValueError,RuntimeError):self.status.setText('Import impossible. Vérifiez le fichier et la disponibilité du coffre Windows.')
        finally:clear_import(result);self.set_busy(False)
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
    """Full-bleed generated plate with actual Qt controls and animated sprites."""
    def __init__(self,browser):
        super().__init__(browser);self.setObjectName('novaWelcome');self.browser=browser;self.step=0;self.confirm_skip=False;self.setStyleSheet(STYLE);self.setMinimumSize(760,420);self.plate=QPixmap(str(Path(__file__).parent/'assets/welcome-import-plate.png'));self.reference=(1586,992);self.reference_art=QPixmap(str(Path(__file__).parent/'assets/welcome-import-reference.png'));self._scale=1.;self._vertical_scale=1.
        from main import icon
        self.logo=QLabel(self);self.logo.setPixmap(icon('logo',64).pixmap(64,64));self.logo.setScaledContents(True);self.brand=QLabel('Nova',self)
        self.restore_button=QPushButton('Restaurer une sauvegarde',self);self.restore_button.clicked.connect(self.restore_backup);self.login_button=QPushButton('Connexion',self);self.login_button.clicked.connect(self.sign_in)
        self.title=QLabel(self);self.title.setWordWrap(True);self.title.setTextFormat(Qt.TextFormat.RichText);self.description=QLabel(self);self.description.setWordWrap(True)
        self.action=QPushButton(self);self.action.setObjectName('primary');self.action.clicked.connect(self.perform)
        self.import_panel=ImportPanel(browser,self);self.import_panel.body.setEnabled(False);self.import_panel.completed.connect(self.import_done);self.import_panel.busyChanged.connect(self.refresh_reference_controls)
        self.mascot=Mascot(browser,self);self.mascot.setMaximumSize(1000,700)
        self.note=QLabel(self);self.note.setWordWrap(True);self.note.setTextFormat(Qt.TextFormat.PlainText);self.progress=QLabel(self);self.skip=QPushButton('Ignorer cette étape →',self);self.skip.clicked.connect(self.skip_step);self.next=QPushButton('Continuer',self);self.next.setObjectName('primary');self.next.clicked.connect(self.advance);self.progress_bar=QProgressBar(self);self.progress_bar.setRange(0,4);self.progress_bar.setTextVisible(False)
        self.mascot.stateChanged.connect(self.update)
        self.reference_controls=(self.logo,self.brand,self.restore_button,self.login_button,self.progress,self.skip,self.progress_bar,self.mascot)
        self.import_panel.file_button.hide()
        self.import_panel.combo.currentIndexChanged.connect(self.refresh_reference_controls)
        self.import_panel.passwords.toggled.connect(self.import_panel.file_button.hide)
        for box in self.checkboxes():
            box.toggled.connect(self.update)
        self.render()
    def checkboxes(self):
        panel=self.import_panel
        return (panel.bookmarks,panel.passwords,panel.history,panel.autofill)

    def uses_reference_profile(self):
        return self.import_panel.combo.currentText()=='Microsoft Edge · Profil par défaut'

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor('#0d0d13'))
        if self.step!=1 or self.reference_art.isNull():
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(self._scale,self._vertical_scale)
        painter.drawPixmap(0,0,self.reference_art)
        if not self.uses_reference_profile():
            self.restore_background(painter,QRectF(152,319,605,72))
        if self.confirm_skip or self.import_panel.imported:
            self.restore_background(painter,QRectF(1303,878,244,50))
        if self.login_button.text()!='Connexion':
            self.restore_background(painter,QRectF(1407,22,139,50))
        if self.import_panel.busy:
            self.restore_background(painter,QRectF(156,692,146,56))
        for box,y in zip(self.checkboxes(),(461,505,548,595)):
            if box.isChecked() and box.isEnabled():
                continue
            square=QRectF(160,y,28,28)
            self.restore_background(painter,square)
            painter.setPen(QColor('#675879' if box.isEnabled() else '#48414e'))
            painter.setBrush(QColor('#211b2b'))
            painter.drawRoundedRect(square.adjusted(1,1,-1,-1),6,6)
        if self.mascot.state:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            if self.mascot.state==1:
                # Only repaint the eyes. The exact reference silhouette and glow stay in place.
                from PySide6.QtGui import QLinearGradient,QPainterPath,QPen
                for x,y,w,h in ((1195,437,46,58),(1289,422,37,51)):
                    eye=QRectF(x,y,w,h)
                    shade=QLinearGradient(eye.topLeft(),eye.bottomRight())
                    shade.setColorAt(0,QColor('#9250bb'))
                    shade.setColorAt(1,QColor('#d195f5'))
                    painter.setBrush(shade)
                    painter.drawEllipse(eye)
                    lid=QPainterPath()
                    lid.moveTo(x+4,y+h*.57)
                    lid.quadTo(x+w*.52,y+h*.22,x+w-5,y+h*.52)
                    painter.setPen(QPen(QColor('#2a1143'),3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(lid)
                    painter.setPen(Qt.PenStyle.NoPen)
            else:
                from PySide6.QtGui import QPainterPath
                for x,y,w,h in ((1197,439,40,54),(1291,425,33,46)):
                    eye=QRectF(x,y,w,h)
                    painter.save()
                    clip=QPainterPath()
                    clip.addEllipse(eye)
                    painter.setClipPath(clip)
                    painter.setBrush(QColor('#f8e9e8'))
                    painter.drawRect(eye)
                    pupil=QRectF(x+2,y+8,w*.53,h*.61)
                    painter.setBrush(QColor('#271039'))
                    painter.drawEllipse(pupil)
                    painter.setBrush(QColor('#fff8ff'))
                    painter.drawEllipse(QRectF(x+5,y+11,6,6))
                    painter.restore()

    def restore_background(self,painter,rect):
        painter.drawPixmap(rect,self.plate,rect)

    def refresh_reference_controls(self,*args):
        using_reference=self.step==1 and not self.reference_art.isNull()
        panel=self.import_panel
        hidden_art={
            panel.combo:self.uses_reference_profile(),
            panel.import_button:not panel.busy,
            panel.caption:True,
            panel.note:True,
            **{box:True for box in self.checkboxes()},
            **{widget:True for widget in self.reference_controls},
        }
        hidden_art[self.skip]=not self.confirm_skip
        hidden_art[self.login_button]=self.login_button.text()=='Connexion'
        for widget,covered in hidden_art.items():
            effect=widget.graphicsEffect()
            if effect is None:
                effect=QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
            effect.setOpacity(0 if using_reference and covered else 1)
        self.update()

    def place(self,widget,x,y,w,h):
        sx,sy=self._scale,self._vertical_scale
        widget.setGeometry(round(x*sx),round(y*sy),max(1,round(w*sx)),max(1,round(h*sy)))
    def resizeEvent(self,event):super().resizeEvent(event);self.position_controls()
    def position_controls(self):
        if not hasattr(self,'import_panel'):return
        rw,rh=self.reference
        self._scale=self.width()/rw
        self._vertical_scale=self.height()/rh
        s=min(self._scale,self._vertical_scale)
        self.place(self.logo,49,21,48,48);self.place(self.brand,108,23,150,46);self.brand.setStyleSheet(f'font-size:{max(18,round(28*s))}px;font-weight:600;color:#f4f0fa')
        self.place(self.restore_button,1124,24,262,46);self.place(self.login_button,1409,24,133,46)
        self.place(self.title,155,205,650,135);self.title.setStyleSheet(f'font-size:{max(27,round(48*s))}px;font-weight:600;color:#f5f1fa');self.place(self.description,155,350,620,80);self.description.setStyleSheet(f'font-size:{max(13,round(20*s))}px;color:#cbc5d3')
        self.place(self.action,155,455,210,50);self.place(self.mascot,770,178,750,520)
        self.place(self.progress,48,901,250,30);self.progress.setStyleSheet(f'font-size:{max(11,round(17*s))}px;color:#b1aaba');self.place(self.skip,1305,880,238,46);self.place(self.next,1105 if self.step!=3 else 1305,880,175 if self.step!=3 else 238,46);self.place(self.progress_bar,45,948,1494,5);self.place(self.note,155,815,1050,48);self.note.setStyleSheet(f'font-size:{max(11,round(15*s))}px;color:#bfaed7')
        radius=max(12,round(23*s));font=max(11,round(16*s));buttons=f'QPushButton{{background:transparent;color:#f0edf5;border:1px solid #a28ac4;font-size:{font}px;border-radius:{radius}px;padding:0 10px}}QPushButton:hover{{background:#24202f}}QPushButton#primary{{background:#b596ff;color:#21152f;border:0}}'
        for button in (self.restore_button,self.login_button,self.skip,self.next,self.action):button.setStyleSheet(buttons)
        self.position_import()
        self.refresh_reference_controls()
    def position_import(self):
        panel=self.import_panel;s=min(self._scale,self._vertical_scale);self.place(panel,155,320,710,475)
        def put(widget,x,y,w,h):widget.setGeometry(round(x*self._scale),round(y*self._vertical_scale),max(1,round(w*self._scale)),max(1,round(h*self._vertical_scale)))
        put(panel.combo,0,2,598,66);put(panel.caption,0,91,660,28)
        for index,box in enumerate((panel.bookmarks,panel.passwords,panel.history,panel.autofill)):put(box,0,133+44*index,660,38)
        put(panel.note,0,326,710,36);put(panel.file_button,0,352,650,22);put(panel.import_button,3,375,142,50);put(panel.progress,0,430,596,3);put(panel.status,0,440,710,35)
        assets=Path(__file__).parent/'assets';check=(assets/'import-check.svg').as_posix();chevron=(assets/'import-chevron.svg').as_posix();font=max(12,round(20*s));small=max(10,round(16*s));indicator=max(13,round(25*s));radius=max(4,round(6*s))
        panel.setStyleSheet(STYLE+f'QComboBox{{font-size:{font}px;padding:0 {round(17*s)}px;border-radius:{round(32*s)}px}}QComboBox::drop-down{{border:0;background:transparent;width:{round(50*s)}px}}QComboBox::down-arrow{{image:url("{chevron}");width:{max(10,round(18*s))}px;height:{max(10,round(18*s))}px}}QCheckBox{{font-size:{font}px;padding:0;spacing:{round(14*s)}px}}QCheckBox::indicator{{width:{indicator}px;height:{indicator}px;border-radius:{radius}px}}QCheckBox::indicator:checked{{image:url("{check}");background:#b596ff}}')
        panel.caption.setStyleSheet(f'font-size:{small}px;color:#aaa5b5');panel.note.setStyleSheet(f'font-size:{small}px;color:#8f899e');panel.file_button.setStyleSheet(f'QPushButton{{font-size:{max(10,round(14*s))}px;border:0;padding:0;color:#b596ff;text-align:left}}QPushButton:hover{{text-decoration:underline}}');panel.import_button.setStyleSheet(f'QPushButton{{font-size:{max(12,round(19*s))}px;color:#20142f;background:#b596ff;border:0;border-radius:{round(24*s)}px;padding:0}}');panel.status.setStyleSheet(f'font-size:{max(11,round(14*s))}px;color:#b7a6d5');panel.combo.setIconSize(QSize(max(18,round(36*s)),max(18,round(36*s))))
    def render(self):
        rows=[('Bienvenue dans <span style="color:#b596ff">Nova.</span>','Vos sites, vos habitudes. Un navigateur sombre et simple, avec les outils utiles à portée de main.','Commencer'),('Vos données, <span style="color:#b596ff">votre Nova.</span>','Retrouvez vos favoris, votre historique et vos identifiants.','Importer'),('Votre compte.<br><span style="color:#b596ff">Votre identité.</span>','Connectez Google pour retrouver votre nom et votre photo dans Nova. Les identifiants des sites s’importent séparément.','Continuer avec Google'),('Prêt pour<br><span style="color:#b596ff">la suite.</span>','Onglets en pause, téléchargements suivis et réglages compacts. Tout reste accessible depuis le menu Nova.','Personnaliser Nova')]
        title,description,action=rows[self.step];self.setAccessibleName(('Bienvenue dans Nova','Vos données, votre Nova','Votre compte Google','Nova est prêt')[self.step]);self.setAccessibleDescription(description);self.title.setText(title);self.description.setText(description);self.title.setVisible(self.step!=1);self.description.setVisible(self.step!=1);self.action.setText(action);self.action.setVisible(self.step!=1);self.import_panel.setVisible(self.step==1);self.progress.setText(f'Étape {self.step+1} sur 4');self.progress_bar.setValue(self.step+1);self.next.setText('Entrer dans Nova' if self.step==3 else 'Continuer');self.next.setVisible(self.step in (2,3) or self.step==1 and self.import_panel.imported);self.skip.setVisible(self.step<3 and not (self.step==1 and self.import_panel.imported));self.skip.setText('Continuer sans importer →' if self.step==1 and self.confirm_skip else 'Ignorer cette étape →');self.note.setText(('Import possible plus tard. Cliquez encore pour continuer sans importer.' if self.width()<1100 else 'Vous pourrez importer plus tard dans les paramètres. Cliquez encore pour continuer sans importer.') if self.step==1 and self.confirm_skip and not self.import_panel.imported else '');self.note.setVisible(bool(self.note.text()));self.position_controls()
    def perform(self):
        if self.step==0:self.advance()
        elif self.step==1:self.import_panel.show()
        elif self.step==2:self.sign_in()
        else:self.finish();self.browser.open_settings(0)
    def import_done(self,counts):self.confirm_skip=True;self.note.setText('Vos données ont été importées. Vous pouvez continuer.');self.note.show();self.next.show();self.skip.hide();self.refresh_reference_controls()
    def restore_backup(self):self.step=1;self.confirm_skip=False;self.render();self.import_panel.restore()
    def sign_in(self):self.note.setText('Ouverture de Google…');self.note.show();self.browser.sync_client.google.start('')
    def sign_in_failed(self,message):self.note.setText(str(message));self.note.show()
    def signed_in(self,email):
        if email:self.login_button.setText('Connecté');self.note.setText('Connecté à Google · '+email);self.note.show();self.refresh_reference_controls()
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
