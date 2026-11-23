from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QPropertyAnimation,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QPixmap,QPainter,QColor,QLinearGradient
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QComboBox,QCheckBox,QFileDialog,QWidget,QGraphicsOpacityEffect,QScrollArea
from ui import NovaDialog,NovaMessage
from import_data import profiles,read_profile,read_export,apply_import

class ImportDialog(NovaDialog):
    def __init__(self,browser):
        super().__init__(browser,'Retrouvez vos données','Deux étapes simples. Nova s’occupe du rangement.');self.browser=browser;self.setMinimumWidth(610);self.imported=False;self.detected=None
        from PySide6.QtCore import QTimer,QStandardPaths
        from PySide6.QtGui import QDesktopServices
        self.sources=profiles();self.combo=QComboBox()
        for label,path in self.sources:self.combo.addItem(label)
        if not self.sources:self.combo.addItem('Aucun profil local détecté');self.combo.setEnabled(False)
        self.body.addWidget(QLabel('1 · Favoris et historique'))
        self.profile_button=QPushButton('Importer de '+self.sources[0][0] if self.sources else 'Choisir un export de favoris…');self.profile_button.setObjectName('primary');self.profile_button.clicked.connect(self.profile if self.sources else self.export);self.body.addWidget(self.profile_button)
        more=QPushButton('Changer le navigateur ou les données');more.clicked.connect(self.toggle_options);self.body.addWidget(more)
        self.options=QWidget();options=QVBoxLayout(self.options);options.setContentsMargins(0,0,0,0);options.addWidget(self.combo);self.bookmarks=QCheckBox('Favoris');self.bookmarks.setChecked(True);self.history=QCheckBox('Historique');self.history.setChecked(True);options.addWidget(self.bookmarks);options.addWidget(self.history);self.options.hide();self.body.addWidget(self.options);self.combo.currentIndexChanged.connect(self.update_profile)
        self.body.addWidget(QLabel('2 · Mots de passe Google'))
        guide=QLabel('Ouvrez Google Password Manager → Paramètres → Exporter les mots de passe. Enregistrez le CSV dans Téléchargements, puis revenez ici.');guide.setWordWrap(True);self.body.addWidget(guide)
        button=QPushButton('Ouvrir Google Password Manager');button.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://passwords.google.com/options')));self.body.addWidget(button)
        self.file_label=QLabel('En attente du fichier exporté dans Téléchargements…');self.file_label.setTextFormat(Qt.TextFormat.PlainText);self.file_label.setWordWrap(True);self.body.addWidget(self.file_label)
        self.password_button=QPushButton('Importer les mots de passe détectés');self.password_button.setObjectName('primary');self.password_button.setEnabled(False);self.password_button.clicked.connect(self.import_detected);self.body.addWidget(self.password_button)
        self.password_button.setStyleSheet('QPushButton:disabled{background:#21182c;color:#81728f;border:1px solid #35263f}')
        button=QPushButton('Choisir un autre fichier…');button.clicked.connect(self.export);self.body.addWidget(button)
        note=QLabel('L’import reste local et ne copie pas les connexions déjà ouvertes. Les mots de passe sont chiffrés dans Nova ; le CSV source reste en clair, à supprimer après vérification.');note.setWordWrap(True);self.body.addWidget(note)
        self.status=QLabel('Aucune donnée n’est importée avant votre clic.');self.status.setWordWrap(True);self.body.addWidget(self.status);self.buttons('Terminer','Fermer')
        self.download_directory=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation);self.scan=QTimer(self);self.scan.setInterval(2000);self.scan.timeout.connect(self.find_export);self.scan.start();self.finished.connect(self.scan.stop);self.find_export()
        outer=self.body;content=QWidget();inner=QVBoxLayout(content);inner.setContentsMargins(8,8,8,8);inner.setSpacing(12)
        while outer.count():inner.addItem(outer.takeAt(0))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setStyleSheet('QScrollArea{border:0;background:transparent}QScrollArea>QWidget>QWidget{background:#0b0811}');scroll.setWidget(content);outer.setContentsMargins(16,16,16,16);outer.addWidget(scroll);self.resize(650,680)
    def toggle_options(self):self.options.setVisible(not self.options.isVisible())
    def update_profile(self):
        if self.sources:self.profile_button.setText('Importer de '+self.sources[self.combo.currentIndex()][0])
    def find_export(self):
        from import_data import password_exports
        found=password_exports(self.download_directory);self.detected=found[0] if found else None;self.password_button.setEnabled(self.detected is not None)
        self.file_label.setText('Fichier trouvé : '+self.detected.name if self.detected else 'En attente du fichier exporté dans Téléchargements…')
    def apply(self,result):
        try:
            counts=apply_import(self.browser,result);self.imported=True;self.status.setText(str(counts['bookmarks'])+' favoris · '+str(counts['history'])+' pages · '+str(counts['credentials'])+' identifiants importés.');self.browser.refresh_home_tabs()
        except (OSError,ValueError):self.status.setText('Import impossible. Vérifiez le fichier et le coffre Windows.')
        finally:
            for row in result.get('credentials',[]):row.clear()
            result.clear()
    def profile(self):
        try:self.apply(read_profile(self.sources[self.combo.currentIndex()][1],self.bookmarks.isChecked(),self.history.isChecked()))
        except Exception:self.status.setText('Lecture impossible. Fermez le navigateur source puis réessayez, ou utilisez un fichier exporté.')
    def import_detected(self):
        self.find_export()
        if self.detected:self.import_file(str(self.detected))
    def import_file(self,path):
        try:self.apply(read_export(path))
        except Exception:self.status.setText('Format non reconnu ou fichier indisponible.')
    def export(self):
        path,_=QFileDialog.getOpenFileName(self,'Choisir un export',self.download_directory,'Exports (*.html *.htm *.json *.csv)')
        if path:self.import_file(path)

class Welcome(QWidget):
    def __init__(self,browser):
        super().__init__(browser);self.setObjectName('novaWelcome');self.browser=browser;self.step=0;self.confirm_skip=False;self.setWindowTitle('Bienvenue dans Nova');self.resize(1180,740);self.setMinimumSize(840,600);self.art=QPixmap(str(Path(__file__).parent/'assets/welcome-nova.png'))
        self.setStyleSheet('QWidget#novaWelcome{background:#08060f}QLabel{color:#b7a8c8;font:14px "Segoe UI"}QPushButton{background:#21132f;color:#eee4fa;border:1px solid #422558;border-radius:10px;padding:11px 20px}QPushButton#primary{background:#8c35e6;border:0}QPushButton:hover{background:#382047}')
        root=QVBoxLayout(self);root.setContentsMargins(62,45,62,40);self.progress=QLabel();root.addWidget(self.progress);row=QHBoxLayout();self.copy=QWidget();copy=QVBoxLayout(self.copy);copy.setContentsMargins(0,0,0,0);self.title=QLabel();self.title.setWordWrap(True);self.title.setTextFormat(Qt.TextFormat.RichText);self.title.setStyleSheet('font-size:60px;font-weight:650;color:#f4eefb');copy.addWidget(self.title);self.title.setMaximumWidth(720);self.description=QLabel();self.description.setMaximumWidth(610);self.description.setStyleSheet('font-size:19px;line-height:1.6;color:#d5c8e5');self.description.setWordWrap(True);copy.addWidget(self.description);self.action=QPushButton();self.action.setObjectName('primary');self.action.clicked.connect(self.perform);copy.addWidget(self.action,0,Qt.AlignmentFlag.AlignLeft);copy.addStretch();row.addWidget(self.copy,1)
        art=QLabel();art.setMinimumWidth(280);art.setMaximumWidth(410);art.setAlignment(Qt.AlignmentFlag.AlignCenter);pix=QPixmap(str(Path(__file__).parent/'assets/welcome-nova.png'));art.setPixmap(pix.scaled(400,350,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));art.hide();root.addLayout(row,1)
        self.note=QLabel();self.note.setWordWrap(True);root.addWidget(self.note);footer=QHBoxLayout();self.skip=QPushButton('Passer');self.skip.clicked.connect(self.skip_step);footer.addWidget(self.skip);footer.addStretch();self.next=QPushButton('Continuer');self.next.setObjectName('primary');self.next.clicked.connect(self.advance);footer.addWidget(self.next);root.addLayout(footer)
        self.fade=QGraphicsOpacityEffect(self.copy);self.copy.setGraphicsEffect(self.fade);self.fade_animation=QPropertyAnimation(self.fade,b'opacity',self);self.fade_animation.setDuration(180);self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.zoom=1.;self.art_animation=QVariantAnimation(self);self.art_animation.setDuration(240);self.art_animation.setStartValue(1.025);self.art_animation.setEndValue(1.);self.art_animation.setEasingCurve(QEasingCurve.Type.OutCubic);self.art_animation.valueChanged.connect(self.animate_art)
        self.render()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#07050d'))
        if not self.art.isNull():
            pix=self.art.scaled(self.size()*self.zoom,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation);painter.drawPixmap((self.width()-pix.width())//2,(self.height()-pix.height())//2,pix)
        shade=QLinearGradient(0,0,self.width(),0);shade.setColorAt(0,QColor(6,4,12,245));shade.setColorAt(.5,QColor(6,4,12,205));shade.setColorAt(1,QColor(6,4,12,35));painter.fillRect(self.rect(),shade);painter.fillRect(self.rect(),QColor(5,3,10,30));painter.end()
    def animate_art(self,value):self.zoom=float(value);self.update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.title.setStyleSheet('font-size:'+str(60 if self.width()>=1100 else 44)+'px;font-weight:650;color:#f4eefb')
        if hasattr(self,'import_panel') and self.import_panel is not None:self.position_import()
    def position_import(self):
        panel=self.import_panel;panel.setGeometry(max(12,(self.width()-650)//2),18,min(650,self.width()-24),max(400,self.height()-36))
    def render(self):
        rows=[('Votre espace.<br><span style="color:#ad70ff">Votre Nova.</span>','Un navigateur sombre, simple et rapide. Vos recherches Google, vos raccourcis et vos sites, dans une interface à vous.','Découvrir Nova'),('Gardez <span style="color:#ad70ff">l’essentiel.</span>','Retrouvez vos favoris, votre historique et vos identifiants compatibles. Choisissez un profil local ou un export Google.','Choisir les données à importer'),('Un compte.<br><span style="color:#ad70ff">Votre identité.</span>','Connectez Google pour afficher votre nom et votre photo dans Nova. La connexion ne donne pas accès aux mots de passe Google : ils s’importent séparément.','Continuer avec Google'),('Moins de bruit.<br><span style="color:#ad70ff">Plus de contrôle.</span>','Pause des onglets en arrière-plan, suggestions locales et réglages compacts. Tout reste modifiable dans les paramètres.','Ouvrir les paramètres')]
        self.fade_animation.stop();self.fade_animation.setStartValue(.25);self.fade_animation.setEndValue(1.);self.fade_animation.start();self.art_animation.stop();self.art_animation.start();title,desc,action=rows[self.step];self.progress.setText('NOVA  /  '+str(self.step+1)+' sur 4');self.title.setText(title);self.description.setText(desc);self.action.setText(action);self.action.setVisible(self.step>0);self.next.setText('Entrer dans Nova' if self.step==3 else 'Continuer');self.skip.setText('Passer quand même' if self.confirm_skip else 'Passer');self.note.setText('Vous pourrez importer plus tard dans Paramètres > Compte. Cliquez encore sur Passer pour continuer sans importer.' if self.confirm_skip else '')
    def perform(self):
        if self.step==1:
            if getattr(self,'import_panel',None):return
            self.import_panel=ImportDialog(self.browser);self.import_panel.setParent(self);self.import_panel.setWindowFlags(Qt.WindowType.Widget);self.position_import();self.import_panel.show();self.import_panel.raise_()
            def imported(*args):
                dialog=self.import_panel;self.import_panel=None;self.confirm_skip=dialog.imported;dialog.deleteLater()
                if self.confirm_skip:self.advance()
                else:self.render()
            self.import_panel.finished.connect(imported)
        elif self.step==2:self.browser.open_account();self.browser.sync_client.google.start('')
        elif self.step==3:self.browser.open_settings(7);self.finish()
    def advance(self):
        if self.step==1 and not self.confirm_skip:
            self.confirm_skip=True;self.render();return
        if self.step==3:self.finish();return
        self.step+=1;self.confirm_skip=False;self.render()
    def skip_step(self):
        if self.step==1 and not self.confirm_skip:self.confirm_skip=True;self.render();return
        self.advance()
    def finish(self):self.browser.data['welcome_completed']=True;self.browser.save();self.hide();self.deleteLater()
    def reject(self):
        if self.step==1 and not self.confirm_skip:self.confirm_skip=True;self.render();return
        if self.step<1:self.step=1;self.confirm_skip=False;self.render();return
        self.finish()
