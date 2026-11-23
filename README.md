# Nova Browser

Navigateur Windows expérimental avec une interface sombre et compacte, des profils locaux, des onglets et un lecteur compatible YouTube/Twitch.

Google est le moteur par défaut depuis la version 3.4.3. L'accueil et les
barres conservent le style Nova ; les résultats s'affichent sur le site Google,
sans Brave API ni serveur nécessaire. Nova Search et son index local restent
disponibles en option dans les paramètres. Le serveur Brave facultatif est
documenté dans [search-server](search-server/README.md).

- Interface native Python/PySide6 et Qt WebEngine.
- Moteur vidéo Edge WebView2 intégré, avec uBlock Origin Lite.
- Paramètres natifs, raccourcis personnalisables et thèmes violet / noir profond.
- Onglets adaptatifs, suggestions locales et coffre de saisie chiffré par Windows DPAPI.
- Connexion Google Desktop via navigateur système et PKCE ; configuration dans `sync-server/GOOGLE-SETUP.txt`.
- Serveur Nova Sync auto-hébergeable pour les favoris, l'historique, les raccourcis, les préférences et les listes d'onglets.
- Mises à jour depuis les GitHub Releases de ce dépôt, vérification SHA-256 et installation après confirmation.

## Construire sous Windows x64

Depuis la version 3.5, les vidéos et l'audio sont mis en pause quand leur onglet
passe en arrière-plan. Désactiver cette fonction dans **Paramètres > Optimiser
le navigateur** pour conserver une lecture en fond. Au retour, Nova tente de
reprendre uniquement les médias qu'il a lui-même interrompus. La première pause
déclenche une notification avec un raccourci vers ce réglage. Les pages classiques
éligibles sont gelées en mémoire ; les lecteurs WebView2 masqués sont suspendus
quand le moteur l'autorise. Les politiques de lecture des sites restent applicables.

Les suggestions de l'accueil et de la barre d'adresse utilisent l'interface Nova
et les données locales (historique, favoris et recherches récentes). La saisie
n'est pas transmise à une API de suggestions externe. Flèches, Entrée et Échap
permettent de naviguer, ouvrir et fermer ces propositions.

Les styles ne s'accumulent plus lors des changements de thème. Les sauvegardes
d'historique sont regroupées sur une fenêtre de 250 ms et vidées à la fermeture ;
les réglages et favoris restent enregistrés immédiatement. Le service de recherche
local démarre uniquement si on utilise l'index Nova, pas avec Google seul.

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

## Importation et fonctions 3.6

La version 3.6.2 conserve le jeton de renouvellement Google chiffré par Windows
dans les données utilisateur, séparément du dossier de l'exécutable. Il est
utilisé au redémarrage et pendant l'utilisation pour renouveler l'identité.
Une reconnexion initiale est nécessaire pour les comptes des versions précédentes
qui n'avaient pas enregistré ce jeton. Une révocation par Google ou par l'utilisateur
peut toujours imposer une nouvelle connexion. Les cookies de session du moteur
classique sont désormais conservés à la fermeture ; les sites peuvent néanmoins
expirer ou révoquer leurs propres sessions. Le compte Nova Google et les connexions
aux sites restent deux mécanismes distincts.

Le premier lancement présente Nova et propose un import explicite. Les favoris
et l'historique peuvent être lus depuis les profils locaux Chrome, Edge, Brave
et Opera. Les exports de favoris HTML / JSON et l'historique Chrome Takeout JSON
sont acceptés. Les mots de passe sont importés via CSV (url,username,password)
après confirmation et stockés dans le coffre Windows chiffré. La source CSV
reste en clair : supprimer ce fichier après vérification de l'importation.
La connexion Google ne donne pas accès aux mots de passe ni aux cookies Chrome.
Les cookies, passkeys, extensions et moyens de paiement ne sont pas importés.
Les identifiants existants ne sont pas écrasés. Le remplissage reste limité
au même site HTTPS ; les changements de domaine nécessitent un nouvel identifiant.

Le lecteur flottant (menu Nova) détache l'onglet actuel dans une petite fenêtre
au-dessus des autres fenêtres, puis le replace avec Revenir à l'onglet. Dans
cette première version, il contient la page du lecteur, pas un flux vidéo extrait.
Les téléchargements du moteur classique disposent d'un panneau Nova avec
progression/pause/reprise/annulation et accès au dossier ; ceux de WebView2
conservent actuellement le dialogue du moteur. La reprise dépend du serveur.
Les fichiers ne s'ouvrent pas automatiquement.

La restauration propose les URL et leur ordre de la dernière session, sans
restaurer formulaires, POST ou positions de lecture. Les URL locales et internes
ne sont pas sauvegardées. La liste est enregistrée après une courte temporisation
et à la fermeture ; une panne peut perdre les toutes dernières modifications.
