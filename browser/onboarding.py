from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap,QPainter,QColor,QLinearGradient
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QComboBox,QCheckBox,QFileDialog
from ui import NovaDialog,NovaMessage
from import_data import profiles,read_profile,read_export,apply_import

class ImportDialog(NovaDialog):
    def __init__(self,browser):
        super().__init__(browser,'Retrouvez vos données','Choisissez ce que vous souhaitez apporter dans Nova.');self.browser=browser;self.setMinimumWidth(610)
        self.sources=profiles();self.combo=QComboBox()
        for label,path in self.sources:self.combo.addItem(label)
        if not self.sources:self.combo.addItem('Aucun profil local détecté');self.combo.setEnabled(False)
        self.body.addWidget(self.combo);self.bookmarks=QCheckBox('Favoris');self.bookmarks.setChecked(True);self.history=QCheckBox('Historique');self.history.setChecked(True);self.body.addWidget(self.bookmarks);self.body.addWidget(self.history)
        button=QPushButton('Importer le profil sélectionné');button.setEnabled(bool(self.sources));button.clicked.connect(self.profile);self.body.addWidget(button)
        button=QPushButton('Importer un fichier HTML, JSON ou CSV de mots de passe…');button.clicked.connect(self.export);self.body.addWidget(button)
        label=QLabel('Google : exportez les favoris ou l’historique via Chrome / Takeout, et les mots de passe en CSV depuis Google Password Manager. Les cookies de connexion, passkeys, cartes bancaires et extensions ne sont pas transférés.');label.setWordWrap(True);self.body.addWidget(label)
        self.status=QLabel('Les données ne sont lues qu’après votre choix.');self.status.setWordWrap(True);self.body.addWidget(self.status);self.buttons('Terminer','Fermer')
    def apply(self,result):
        try:
            counts=apply_import(self.browser,result);self.status.setText(str(counts['bookmarks'])+' favoris · '+str(counts['history'])+' pages · '+str(counts['credentials'])+' identifiants importés.');self.browser.refresh_home_tabs()
        except (OSError,ValueError):self.status.setText('Import impossible. Vérifiez le fichier et le coffre Windows.')
        finally:
            for row in result.get('credentials',[]):row.clear()
            result.clear()
    def profile(self):
        try:self.apply(read_profile(self.sources[self.combo.currentIndex()][1],self.bookmarks.isChecked(),self.history.isChecked()))
        except Exception:self.status.setText('Lecture impossible. Fermez le navigateur source puis réessayez, ou utilisez un fichier exporté.')
    def export(self):
        path,_=QFileDialog.getOpenFileName(self,'Choisir un export','','Exports (*.html *.htm *.json *.csv)')
        if not path:return
        if Path(path).suffix.lower()=='.csv' and NovaMessage.question(self,'Importer les mots de passe ?','Les mots de passe du CSV seront chiffrés dans le coffre Nova. Le fichier source reste en clair : supprimez-le vous-même après vérification. Continuer ?')!=NovaMessage.StandardButton.Yes:return
        try:self.apply(read_export(path))
        except Exception:self.status.setText('Format non reconnu ou fichier indisponible.')

class Welcome(QDialog):
    def __init__(self,browser):
        super().__init__(browser);self.browser=browser;self.step=0;self.confirm_skip=False;self.setWindowTitle('Bienvenue dans Nova');self.resize(1180,740);self.setMinimumSize(840,600);self.art=QPixmap(str(Path(__file__).parent/'assets/welcome-nova.png'))
        self.setStyleSheet('QDialog{background:#08060f}QLabel{color:#b7a8c8;font:14px "Segoe UI"}QPushButton{background:#21132f;color:#eee4fa;border:1px solid #422558;border-radius:10px;padding:11px 20px}QPushButton#primary{background:#8c35e6;border:0}QPushButton:hover{background:#382047}')
        root=QVBoxLayout(self);root.setContentsMargins(62,45,62,40);self.progress=QLabel();root.addWidget(self.progress);row=QHBoxLayout();copy=QVBoxLayout();self.title=QLabel();self.title.setWordWrap(True);self.title.setTextFormat(Qt.TextFormat.RichText);self.title.setStyleSheet('font-size:60px;font-weight:650;color:#f4eefb');copy.addWidget(self.title);self.title.setMaximumWidth(720);self.description=QLabel();self.description.setMaximumWidth(610);self.description.setStyleSheet('font-size:19px;line-height:1.6;color:#d5c8e5');self.description.setWordWrap(True);copy.addWidget(self.description);self.action=QPushButton();self.action.setObjectName('primary');self.action.clicked.connect(self.perform);copy.addWidget(self.action,0,Qt.AlignmentFlag.AlignLeft);copy.addStretch();row.addLayout(copy,1)
        art=QLabel();art.setMinimumWidth(280);art.setMaximumWidth(410);art.setAlignment(Qt.AlignmentFlag.AlignCenter);pix=QPixmap(str(Path(__file__).parent/'assets/welcome-nova.png'));art.setPixmap(pix.scaled(400,350,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));art.hide();root.addLayout(row,1)
        self.note=QLabel();self.note.setWordWrap(True);root.addWidget(self.note);footer=QHBoxLayout();self.skip=QPushButton('Passer');self.skip.clicked.connect(self.skip_step);footer.addWidget(self.skip);footer.addStretch();self.next=QPushButton('Continuer');self.next.setObjectName('primary');self.next.clicked.connect(self.advance);footer.addWidget(self.next);root.addLayout(footer);self.render()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#07050d'))
        if not self.art.isNull():
            pix=self.art.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation);painter.drawPixmap((self.width()-pix.width())//2,(self.height()-pix.height())//2,pix)
        shade=QLinearGradient(0,0,self.width(),0);shade.setColorAt(0,QColor(6,4,12,245));shade.setColorAt(.5,QColor(6,4,12,205));shade.setColorAt(1,QColor(6,4,12,35));painter.fillRect(self.rect(),shade);painter.fillRect(self.rect(),QColor(5,3,10,30));painter.end()
    def render(self):
        rows=[('Votre espace.<br><span style="color:#ad70ff">Votre Nova.</span>','Un navigateur sombre, simple et rapide. Vos recherches Google, vos raccourcis et vos sites, dans une interface à vous.','Découvrir Nova'),('Gardez <span style="color:#ad70ff">l’essentiel.</span>','Retrouvez vos favoris, votre historique et vos identifiants compatibles. Choisissez un profil local ou un export Google.','Choisir les données à importer'),('Un compte.<br><span style="color:#ad70ff">Votre identité.</span>','Connectez Google pour afficher votre nom et votre photo dans Nova. La connexion ne donne pas accès aux mots de passe Google : ils s’importent séparément.','Continuer avec Google'),('Moins de bruit.<br><span style="color:#ad70ff">Plus de contrôle.</span>','Pause des onglets en arrière-plan, suggestions locales et réglages compacts. Tout reste modifiable dans les paramètres.','Ouvrir les paramètres')]
        title,desc,action=rows[self.step];self.progress.setText('NOVA  /  '+str(self.step+1)+' sur 4');self.title.setText(title);self.description.setText(desc);self.action.setText(action);self.action.setVisible(self.step>0);self.next.setText('Entrer dans Nova' if self.step==3 else 'Continuer');self.skip.setText('Passer quand même' if self.confirm_skip else 'Passer');self.note.setText('Vous pourrez importer plus tard dans Paramètres > Compte. Cliquez encore sur Passer pour continuer sans importer.' if self.confirm_skip else '')
    def perform(self):
        if self.step==1:ImportDialog(self.browser).exec();self.confirm_skip=False;self.render()
        elif self.step==2:self.browser.open_account();self.browser.sync_client.google.start('')
        elif self.step==3:self.browser.open_settings(7)
    def advance(self):
        if self.step==1 and not self.confirm_skip:
            self.confirm_skip=True;self.render();return
        if self.step==3:self.finish();return
        self.step+=1;self.confirm_skip=False;self.render()
    def skip_step(self):
        if self.step==1 and not self.confirm_skip:self.confirm_skip=True;self.render();return
        self.advance()
    def finish(self):self.browser.data['welcome_completed']=True;self.browser.save();self.accept()
    def reject(self):
        if self.step==1 and not self.confirm_skip:self.confirm_skip=True;self.render();return
        if self.step<1:self.step=1;self.confirm_skip=False;self.render();return
        self.finish()
