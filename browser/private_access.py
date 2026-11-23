"""Local private-window access gate. PIN/recovery hashes are sealed with DPAPI."""
import hashlib,hmac,json,re,secrets,time
from pathlib import Path
from vault import protect
from PySide6.QtCore import Qt,QStandardPaths
from PySide6.QtWidgets import QLabel,QLineEdit,QPushButton,QHBoxLayout,QCheckBox,QApplication
from ui import NovaDialog,NovaMessage,neutral_style

def recovery_normalize(value):return re.sub(r'[\s-]','',value).upper()
def derive(value,salt):return hashlib.scrypt(value.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()

class PrivateStore:
    def __init__(self,path):self.path=Path(path);self.data=None;self.corrupt=False;self.load()
    def load(self):
        self.data=None;self.corrupt=False
        if not self.path.exists():return
        try:
            if self.path.stat().st_size>16384:raise ValueError()
            data=json.loads(protect(self.path.read_bytes(),True).decode())
            if not isinstance(data,dict) or data.get('v')!=1 or not all(re.fullmatch(r'[0-9a-f]{'+str(n)+'}',data.get(k,'')) for k,n in [('salt',32),('pin',64),('recovery_salt',32),('recovery',64)]):raise ValueError()
            import math
            if type(data.get('failures')) is not int or not 0<=data['failures']<=30 or not isinstance(data.get('blocked_until'),(int,float)) or not math.isfinite(data['blocked_until']):raise ValueError()
            self.data=data
        except (OSError,ValueError,UnicodeError,TypeError):self.corrupt=True
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);p=self.path.with_suffix('.tmp');p.write_bytes(protect(json.dumps(self.data).encode()));p.replace(self.path)
    def configure(self,pin,confirmation):
        if not re.fullmatch(r'[0-9]{6,12}',pin) or not re.fullmatch(r'[0-9]{6,12}',confirmation) or not hmac.compare_digest(pin,confirmation):raise ValueError('Choisissez un code de 6 à 12 chiffres et confirmez-le à l’identique.')
        recovery=secrets.token_hex(16).upper();salt=secrets.token_hex(16);rsalt=secrets.token_hex(16)
        self.data={'v':1,'salt':salt,'pin':derive(pin,salt),'recovery_salt':rsalt,'recovery':derive(recovery,rsalt),'failures':0,'blocked_until':0};self.corrupt=False;self.save()
        return '-'.join(recovery[i:i+4] for i in range(0,len(recovery),4))
    def remaining(self):return max(0,int(float(self.data.get('blocked_until',0))-time.time()+.999)) if self.data else 0
    def verify(self,value,recovery=False):
        self.load()
        if not self.data or self.corrupt or self.remaining():return False
        prefix='recovery' if recovery else 'pin';salt='recovery_salt' if recovery else 'salt';candidate=recovery_normalize(value) if recovery else value
        valid=(bool(re.fullmatch(r'[A-F0-9]{32}',candidate)) if recovery else bool(re.fullmatch(r'[0-9]{6,12}',candidate)))
        ok=valid and hmac.compare_digest(derive(candidate,self.data[salt]),self.data[prefix])
        if ok:self.data.update(failures=0,blocked_until=0)
        else:
            failures=min(30,int(self.data.get('failures',0))+1);self.data['failures']=failures
            if failures>=5:self.data['blocked_until']=time.time()+min(900,30*2**min(5,failures-5))
        self.save();return bool(ok)

class PrivateAccess:
    def __init__(self,browser):
        self.browser=browser;root=Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation));self.store=PrivateStore(root/'private-access.dat')
    def dialog(self,title,subtitle):
        d=NovaDialog(self.browser,title,subtitle);d.setStyleSheet(neutral_style(d.styleSheet())+'QLabel#heading{font-size:21px}QLineEdit{border-radius:8px;padding:11px}QPushButton#primary{background:#ececec;color:#151515;border-radius:8px}');d.setFixedWidth(440);return d
    def setup(self):
        d=self.dialog('Créer votre code privé','Ce code sera demandé à chaque ouverture d’une fenêtre privée. Il protège l’accès dans Nova sur cet appareil.');pin=QLineEdit();confirm=QLineEdit()
        for field,placeholder in [(pin,'Code · 6 à 12 chiffres'),(confirm,'Confirmer le code')]:field.setEchoMode(QLineEdit.EchoMode.Password);field.setMaxLength(12);field.setPlaceholderText(placeholder);field.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly|Qt.InputMethodHint.ImhNoPredictiveText|Qt.InputMethodHint.ImhSensitiveData);d.body.addWidget(field)
        error=QLabel();error.setWordWrap(True);d.body.addWidget(error);row=QHBoxLayout();row.addStretch();button=QPushButton('Créer le code');button.setObjectName('primary');row.addWidget(button);d.body.addLayout(row);created=[]
        def create():
            if created:return
            try:recovery=self.store.configure(pin.text(),confirm.text())
            except (ValueError,OSError) as e:error.setText(str(e) if isinstance(e,ValueError) else 'Enregistrement impossible.');return
            pin.clear();confirm.clear();created.append(recovery);d.accept()
        button.clicked.connect(create);confirm.returnPressed.connect(create);pin.setFocus()
        result=d.exec();pin.clear();confirm.clear();d.deleteLater()
        if result!=d.DialogCode.Accepted:return False
        recovery=created.pop();r=self.dialog('Conservez votre code de secours','Il permet de remplacer un code privé oublié si Windows Hello n’est pas disponible. Il ne sera plus affiché après cette étape.');label=QLabel(recovery);label.setTextFormat(Qt.TextFormat.PlainText);label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);label.setWordWrap(True);label.setStyleSheet('font:14px Consolas;color:#eee;padding:12px;background:#191919;border-radius:8px');r.body.addWidget(label)
        copy=QPushButton('Copier le code de secours');copy.clicked.connect(lambda:QApplication.clipboard().setText(recovery));r.body.addWidget(copy,0,Qt.AlignmentFlag.AlignLeft);ack=QCheckBox('J’ai conservé ce code dans un endroit sûr.');r.body.addWidget(ack);ok=QPushButton('Continuer');ok.setObjectName('primary');ok.setEnabled(False);ack.toggled.connect(ok.setEnabled);ok.clicked.connect(r.accept);r.body.addWidget(ok,0,Qt.AlignmentFlag.AlignRight)
        accepted=r.exec()==r.DialogCode.Accepted
        label.clear();copy.clicked.disconnect();r.deleteLater()
        if not accepted:NovaMessage.information(self.browser,'Code créé','Votre code est créé. Si vous avez perdu le code de secours, Windows Hello peut permettre une réinitialisation, ou vous pourrez générer un nouveau code après déverrouillage.');return False
        return True
    def request(self,changing=False):
        if not self.store.data and not self.store.corrupt:return self.setup()
        d=self.dialog('Navigation privée','Entrez votre code d’accès.' if not changing else 'Confirmez votre code actuel avant de le remplacer.');field=QLineEdit();field.setEchoMode(QLineEdit.EchoMode.Password);field.setMaxLength(12);field.setPlaceholderText('Code d’accès');d.body.addWidget(field);error=QLabel();error.setWordWrap(True);d.body.addWidget(error)
        row=QHBoxLayout();forgot=QPushButton('Code oublié ?');forgot.setObjectName('quiet');row.addWidget(forgot);row.addStretch();ok=QPushButton('Déverrouiller');ok.setObjectName('primary');row.addWidget(ok);d.body.addLayout(row)
        def unlock():
            if self.store.remaining():error.setText('Réessayez dans '+str(self.store.remaining())+' secondes.');return
            try:accepted=self.store.verify(field.text())
            except OSError:error.setText('Le code n’a pas pu être vérifié.');return
            field.clear()
            if accepted:
                if not changing or self.setup():d.accept()
            else:error.setText(('Trop d’essais. Réessayez dans '+str(self.store.remaining())+' secondes.') if self.store.remaining() else 'Configuration illisible. Utilisez la récupération protégée.' if self.store.corrupt else 'Code incorrect.')
        ok.clicked.connect(unlock);field.returnPressed.connect(unlock)
        def recovery():
            r=self.dialog('Récupérer l’accès privé','Remplacez le code après vérification de votre identité Windows ou de votre code de secours.');entry=QLineEdit();entry.setEchoMode(QLineEdit.EchoMode.Password);entry.setMaxLength(80);entry.setPlaceholderText('Code de secours');r.body.addWidget(entry);message=QLabel();message.setWordWrap(True);r.body.addWidget(message);buttons=QHBoxLayout();hello=QPushButton('Windows Hello');recover=QPushButton('Vérifier le code');buttons.addWidget(hello);buttons.addWidget(recover);r.body.addLayout(buttons)
            active=[True]
            def reset():
                if not active[0] or not r.isVisible() or not d.isVisible():return
                if self.setup():r.accept();d.accept()
            def code():
                try:valid=self.store.verify(entry.text(),True)
                except OSError:valid=False
                entry.clear()
                if valid:reset()
                else:message.setText('Code de secours incorrect.' if not self.store.remaining() else 'Réessayez dans '+str(self.store.remaining())+' secondes.')
            def verified(valid):
                if not active[0]:return
                if valid:reset()
                else:message.setText('Windows Hello n’a pas validé la vérification. Vous pouvez utiliser le code de secours.')
            recover.clicked.connect(code);entry.returnPressed.connect(code);hello.clicked.connect(lambda:self.browser.hello.verify(verified,purpose='private',notify_failure=False));r.exec();active[0]=False;entry.clear();r.deleteLater()
        forgot.clicked.connect(recovery);field.setFocus();result=d.exec();field.clear();d.deleteLater();return result==d.DialogCode.Accepted
