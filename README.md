# Nova Browser

Navigateur Windows expérimental avec une interface sombre et compacte, des profils locaux, des onglets et un lecteur compatible YouTube/Twitch.

Nova Search est le moteur par défaut depuis la version 3.4. L'accueil existant
reste inchangé dans son style. Un serveur configurable utilise Brave API pour
la recherche Web ; la clé reste côté serveur. Sans serveur, un petit index
local est disponible. Configuration et limites dans [search-server](search-server/README.md).

- Interface native Python/PySide6 et Qt WebEngine.
- Moteur vidéo Edge WebView2 intégré, avec uBlock Origin Lite.
- Paramètres natifs, raccourcis personnalisables et thèmes violet / noir profond.
- Onglets adaptatifs, suggestions locales et coffre de saisie chiffré par Windows DPAPI.
- Connexion Google Desktop via navigateur système et PKCE ; configuration dans `sync-server/GOOGLE-SETUP.txt`.
- Serveur Nova Sync auto-hébergeable pour les favoris, l'historique, les raccourcis, les préférences et les listes d'onglets.
- Mises à jour depuis les GitHub Releases de ce dépôt, vérification SHA-256 et installation après confirmation.

## Construire sous Windows x64

Installer Python 3.12 et un SDK .NET 10 ou supérieur, puis :

```powershell
cd browser
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
./build.ps1
```

L'exécutable et ses dépendances se trouvent dans `browser/dist/NovaBrowser`. Conserver tout le dossier. Le Runtime Microsoft Edge WebView2 est requis pour le lecteur.

## Publier une version

1. Modifier `browser/version.py` et ajouter les notes dans `CHANGELOG.md`.
2. Valider les sources et les tests.
3. Créer puis pousser un tag identique à la version, par exemple `v3.2.0`.
4. Le workflow Windows compile, teste et publie `NovaBrowser-Windows-x64.zip` dans une GitHub Release.

Nova vérifie la dernière release au démarrage, au retour dans la fenêtre (au plus une fois par minute), et toutes les cinq minutes. Une notification apparaît dès la détection. Il ne s'agit pas d'une notification push instantanée. Le téléchargement et le redémarrage nécessitent une action de l'utilisateur. Une notification confirme l'installation au redémarrage.

Le digest SHA-256 de l'asset, fourni par l'API GitHub, est vérifié avant l'installation. Cela ne remplace pas une signature de code Windows. L'ancienne installation reste dans un dossier de sauvegarde voisin. Les profils sont stockés séparément dans AppLocalData.

## Serveur de synchronisation

Voir `sync-server/DEPLOIEMENT.txt`. Aucun serveur public n'est configuré par défaut. Les cookies et mots de passe des sites ne sont pas synchronisés. Le serveur n'implémente pas encore la récupération de mot de passe ni la MFA.

## Limites et composants tiers

Version de développement non auditée. Aucun service VPN n'est intégré. Les sessions Qt et WebView2 sont distinctes. Le blocage de chaque publicité YouTube n'est pas garanti.

Qt/PySide6, Chromium, WebView2 et uBlock Origin Lite conservent leurs propres licences. Les notices disponibles sont dans `browser/third-party-notices` et `browser/blocker`. uBlock Origin Lite est fourni sans modification depuis la version `2026.1122.1948` du dépôt officiel `uBlockOrigin/uBOL-home`. Son code source et sa licence sont conservés avec l'extension.
