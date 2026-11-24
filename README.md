# Nova Browser

Navigateur Windows expérimental avec une interface sombre et compacte, des profils locaux, des onglets et un lecteur compatible YouTube/Twitch.

Google est le moteur par défaut depuis la version 3.4.3. L'accueil et les
barres conservent le style Nova ; les résultats s'affichent sur le site Google,
sans Brave API ni serveur nécessaire. Nova Search et son index local restent
disponibles en option dans les paramètres. Le serveur Brave facultatif est
documenté dans [search-server](search-server/README.md).

- Interface native Python/PySide6 et Qt WebEngine.
- Moteur vidéo Edge WebView2 intégré, avec uBlock Origin Lite.
- Menus contextuels Nova au-dessus des pages intégrées et enregistrement des images via le dialogue Nova.
- Panneaux compacts sous les icônes : téléchargements avec progression/débit et gestion des extensions du moteur compatible.
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

Depuis 3.7, la présentation s'affiche dans la fenêtre principale de Nova, avec
transitions courtes et illustration plein cadre. Le menu permet de la revoir.
L'import propose Chrome en priorité et permet d'importer favoris et historique
en un clic. Le parcours des mots de passe guide l'export Google puis détecte
les CSV nommés Passwords / mots de passe, datés de moins de sept jours et situés
dans Téléchargements. Seuls les noms et métadonnées sont examinés avant le clic
Importer. Le fichier n'est ni importé ni supprimé automatiquement. Les profils
et catégories restent modifiables avec Changer le navigateur ou les données.

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

## Suggestions en ligne et navigateur par défaut (3.8)

Le mode de complétion Groq s’active dans Paramètres > Moteur de recherche.
La clé se saisit dans Nova et reste chiffrée par Windows dans les données
utilisateur. Ne jamais inclure une clé dans une distribution. Cette intégration
utilise openai/gpt-oss-20b sur https://api.groq.com/openai/v1/chat/completions.
Seul le texte de recherche est envoyé : aucun historique, favori, formulaire
ou mot de passe. Les adresses Web, e-mails et formats de clés reconnus sont
exclus. Les suggestions peuvent être erronées ; ce ne sont pas des résultats
Web vérifiés. Le texte proposé apparaît simplement dans le menu Nova.

Optimisation : pause de frappe de 700 ms, une requête à la fois, intervalle
minimum de 2,5 secondes, 3 suggestions courtes, cache de 80 entrées en mémoire
pendant 15 minutes, timeout 4 secondes et temporisation après erreur/quota.
Un compteur local plafonne à 900 appels par jour UTC. Les limites réelles du
compte Groq et de tokens s’appliquent également ; le programme ne change pas
le forfait du compte. Les requêtes et réponses ne sont pas enregistrées sur
disque par Nova ; les règles de traitement des données Groq s’appliquent.
L’offre gratuite n’est pas illimitée. https://console.groq.com/docs/rate-limits

Le bouton Définir Nova comme navigateur par défaut enregistre Nova dans les
applications disponibles pour le compte Windows et ouvre les paramètres
Windows pour HTTP/HTTPS. Le choix final appartient à l’utilisateur ; le
programme ne modifie pas UserChoice. Garder le dossier Nova à un emplacement
stable. Si on le déplace, relancer le bouton pour actualiser les chemins.
Les liens externes sont transmis à l’instance Nova déjà ouverte.

Les écritures du presse-papiers du moteur classique sont autorisées pour
faciliter la copie. La lecture silencieuse est refusée. Dans le moteur vidéo,
la lecture du presse-papiers est autorisée seulement sur action utilisateur,
sans mémoriser de permission permanente. Ctrl+V et les commandes explicites
Coller restent disponibles.

### Suggestions partagées (3.9.0)

Le navigateur utilise le service HTTPS Nova hébergé sur Vercel. La clé Groq reste
une variable sensible côté serveur : aucune clé à configurer sur les autres PC.
Seul le texte de recherche admissible est transmis ; désactivation dans les
paramètres de recherche. Le quota est partagé par tous les utilisateurs. Cache
éphémère et limitation par instance ; les protections ne remplacent pas une
limitation globale persistante pour une diffusion à grande échelle.
Voir `ai-server/README.md` pour l'exploitation du service.

## Confidentialité et outils (4.0)

`Ctrl+Maj+N` ouvre une fenêtre privée noire/grise avec le logo Nova d’origine.
Qt utilise un profil off-the-record et un cache mémoire ; WebView2 utilise son
mode InPrivate dans un répertoire temporaire propre à la fenêtre. Compte Nova,
coffre, historique, recherches récentes, session récupérable et suggestions en
ligne sont désactivés. Un assistant de nettoyage retire le répertoire temporaire
après la fermeture des processus compatibles. Les fichiers téléchargés et les
captures demandées restent sur disque. Ce mode ne rend pas anonyme auprès des
sites, du fournisseur d’accès ou du réseau ; ce n’est pas un VPN.

Menu Nova > Outils de page : traduction française via Google Traduction, capture
PNG/zone, export PDF de la page complète, notes, activité des onglets, concentration
et présentation. Les notes privées restent en mémoire. Un clic droit sur un onglet
permet de l’épingler et de couper son son. Les aperçus d’onglets restent en mémoire.

Le bouclier près de l’adresse ouvre les contrôles du site. Les choix d’autorisation
sont mémorisés par origine (protocole, domaine et port) en navigation normale,
en mémoire uniquement dans une fenêtre privée. Les contrôles du site permettent
de les réinitialiser. L’arrêt d’urgence quitte le document.
Les indicateurs caméra/micro reposent sur les demandes d’autorisation et les pistes
média instrumentées ; ils ne remplacent pas les indicateurs Windows. Les alertes
anti-hameçonnage sont des heuristiques locales, pas une liste de réputation exhaustive.
La mise à jour doit présenter un manifeste signé Ed25519 par la clé publique
intégrée à Nova, puis réussir le contrôle SHA-256. La clé de signature privée reste
un secret GitHub Actions ; aucune clé privée n’est distribuée.

La traduction envoie le texte sélectionné ou l’URL à Google Traduction et ne
fonctionne pas forcément sur les pages nécessitant une session. Les connexions
Google sur les sites conservent le mécanisme de fenêtre de retour ; un refus OAuth
pour moteur embarqué reste possible. Le compte Google de Nova utilise son parcours
système distinct. Les téléchargements interrompus ne sont repris que si le moteur
et le serveur le permettent ; pas de reprise garantie après fermeture de Nova.

Paramètres > Compte et démarrage : lancement à la connexion Windows et plein écran
(F11 pour quitter). Les intégrations Windows utilisent uniquement le compte courant.
Le nom de stockage NovaBrowser reste stable pour conserver les profils existants.
Une copie de compatibilité de l’exécutable demeure dans l’archive GitHub pour les
anciennes versions de l’assistant de mise à jour ; utiliser Nova.exe.

## Contrôles de confidentialité et code privé (4.1)

Paramètres > Confidentialité > Envois de texte permet de désactiver tous les
services de texte facultatifs de Nova, ou seulement les suggestions / la traduction.
Le réglage général coupe les requêtes futures et annule les suggestions en cours
au mieux ; il ne peut pas retirer une saisie déjà reçue par le fournisseur.
Les recherches validées, les connexions et les messages envoyés aux sites restent
fonctionnels. Les suggestions en ligne sont toujours désactivées en privé.

À la première ouverture privée, Nova demande un code de 6 à 12 chiffres à saisir
deux fois et affiche un code de secours aléatoire. Seuls des dérivés scrypt avec
sels distincts sont conservés, dans un fichier protégé par Windows DPAPI. Les
échecs sont limités et le délai est conservé entre les redémarrages. « Code oublié »
permet de remplacer le code après vérification Windows Hello ou du code de secours.
Le nouveau code invalide l’ancien code et l’ancien secours. Aucun code ne doit
être communiqué dans le chat ni envoyé à Nova : tout ce parcours est local.

Le verrouillage manuel masque cette fenêtre et son lecteur flottant et empêche
les captures depuis Nova ; il ne ferme pas la session. Le code protège l’accès dans
l’application, ce n’est ni une passkey FIDO ni une frontière de sécurité contre une
personne contrôlant votre compte Windows ou une version modifiée du navigateur.
Pour protéger l’ensemble du PC, utiliser le verrouillage de session Windows.
Sans le code, le secours ou Windows Hello disponible, Nova n’offre pas de bouton
permettant de contourner la vérification. Une session privée déjà fermée n’est pas
récupérable. La configuration du code est conservée ; pas l’historique privé.

Des CAPTCHA peuvent rester présents : Nova ne les résout pas et ne contourne pas
les contrôles des sites. Les cookies de session sont conservés en mémoire jusqu’à
la fermeture de la fenêtre privée, sans importer les cookies de navigation normale.
Les nouveaux visuels de référence ont été générés avec imagegen, puis comparés
aux widgets réellement rendus ; les images ne remplacent pas les contrôles natifs.
