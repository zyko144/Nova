## 4.3.0 — Téléchargements et notifications

- Panneau Téléchargements compact inspiré de la référence : icônes de fichiers Windows, lien d’ouverture, recherche et commandes légères.
- Transferts natifs sans limite ajoutée par Nova, fréquence des mises à jour de progression réduite, et maintien du moteur jusqu’à la fin du transfert lorsqu’un onglet est fermé.
- Mise à jour des filtres uBlock Origin Lite (2026.1124.1811), vérification des scripts YouTube et activation du mode optimal pour ce domaine. Filtrage complémentaire de domaines publicitaires dans le moteur compatible, désactivé avec le bloqueur.
- Focus automatique dans la barre d’adresse des nouveaux onglets, conservé après chargement de l’accueil.
- Autorisations mémorisées par origine en navigation normale, en mémoire uniquement en navigation privée, réinitialisables depuis le bouclier. Suppression des choix temporisés.
- Notifications Nova et des sites autorisés dans des cartes réellement arrondies, animées, avec un son d’eau local désactivable dans Apparence.

## 4.2.0 — Menus, images et téléchargements

- Menus Nova et clic droit organisés par catégories, avec des icônes homogènes.
- Clic droit du moteur compatible affiché par Nova au-dessus des pages intégrées. Choix du dossier dans Nova et enregistrement des images chargées, y compris les adresses temporaires.
- Téléchargements sous leur icône : progression, débit en Mo/s, pause/reprise lorsque disponible, annulation et retrait de la liste sans effacer le fichier.
- Liste des extensions installées dans le profil compatible, activation/désactivation, suppression et restauration du bloqueur. Les composants internes PDF/presse-papiers du moteur ne sont pas présentés comme des extensions utilisateur.
- Retour du plein écran vidéo vers l’état précédent du navigateur.
- Fondus discrets, sans attendre pour fermer un onglet, désactivables dans Apparence.

## 4.1.0 — Confidentialité et accès privé

- Réglage général « Services de texte en ligne » et contrôles séparés pour les suggestions et la traduction. Arrêt des requêtes de suggestions en cours à la désactivation ; recherches validées et messages des sites inchangés.
- Paramètres réorganisés en lignes compactes, avec descriptions et interrupteurs synchronisés. Panneau de protection simplifié avec les options avancées dans un menu secondaire.
- Code privé de 6 à 12 chiffres, confirmation à la création et code de secours affiché une seule fois. Empreintes scrypt protégées par Windows DPAPI, limitation des essais et récupération via Windows Hello ou code de secours.
- Verrouillage manuel d’une fenêtre privée : contenu, lecteur flottant, aperçus et téléchargements masqués, autorisations temporaires retirées ; capture depuis Nova bloquée jusqu’au déverrouillage.
- Les CAPTCHA légitimes des sites restent actifs. Les cookies privés restent en mémoire pendant la session et disparaissent à la fermeture.

## 4.0.0 — Nova

- Navigation privée dans une fenêtre noire et grise, vrai logo Nova en argent, profil séparé en mémoire, sans historique, recherches récentes, coffre, compte Nova ni suggestions en ligne. Nettoyage des fichiers temporaires à la fermeture.
- Onglets épinglés, son par onglet, aperçu au survol, état de consommation, bloc-notes, mode concentration et mode présentation.
- Avertissement pour les formulaires non envoyés. Restauration de session avec état épinglé/muet.
- Traduction française de la page ou de la sélection depuis le clic droit (Google Traduction). Captures PNG avec sélection de zone et export de page complète en PDF.
- Panneau compact de protection par site : autorisations temporaires, arrêt de l’activité, suppression des données du site et ouverture en session isolée.
- Alertes locales de domaines suspects et fichiers exécutables/doubles extensions, HTTPS prioritaire sans retour automatique en HTTP, protection des liens sensibles et du presse-papiers, journal en mémoire.
- Windows Hello optionnel pour le remplissage du coffre, mises à jour signées Ed25519, téléchargements classiques et compatibles regroupés avec reprise lorsque le moteur/serveur la permet.
- Fenêtres de connexion conservant le lien avec le site appelant, y compris les fenêtres initialement vides ; moteur compatible pour Pinterest. Les refus de Google concernant les navigateurs embarqués ne sont pas contournés.
- Nom affiché Nova, exécutable Nova.exe, intégration au menu Démarrer, démarrage Windows et plein écran réglables.

## 3.9.0

- Suggestions en ligne via le service Nova partagé : aucune clé à saisir ni secret distribué dans le navigateur.
- Cache serveur, requêtes regroupées et protection contre les rafales ; propositions locales en cas de quota ou de panne.
- Réglage pour désactiver les suggestions en ligne ; seul le texte de recherche admissible est transmis.

# Historique

## 3.8.2

- Nettoyage explicite des profils WebEngine entre les tests pour fiabiliser la validation Windows complète.

## 3.8.1

- Carte d'accueil pour choisir Nova comme navigateur par défaut dans les paramètres Windows.
- Proposition affichée une seule fois, après la présentation, et masquée si Nova gère déjà HTTP et HTTPS.

## 3.8.0

- Complétions de recherche par Groq, avec clé locale chiffrée et activation dans les paramètres.
- Appels après pause de frappe, réponses courtes, cache mémoire borné, rejet des réponses périmées et repli local.
- Suggestions affichées sans badge ni libellé technique.
- Définition de Nova comme navigateur par défaut via les paramètres Windows et ouverture des liens dans l’instance active.
- Copie sans demandes répétées et collage explicite ; lecture du presse-papiers non autorisée en arrière-plan.


## 3.7.1

- Panneau d'importation défilant pour conserver toutes les actions accessibles dans une fenêtre compacte.

## 3.7.0

- Présentation intégrée dans la fenêtre principale, avec fond illustré, fondu du texte et transition de l'illustration.
- Importation simplifiée : profil Chrome proposé directement pour les favoris et l'historique.
- Parcours guidé Google Password Manager et détection des exports CSV récents dans Téléchargements, sans lecture avant validation.
- Après un import réussi, la présentation continue sans confirmation de passage supplémentaire.
- Accès « Revoir la présentation » dans le menu Nova.

## 3.6.3

- Zone cliquable des onglets étendue jusqu'au bord supérieur de la fenêtre, sans changer leur silhouette arrondie.

## 3.6.2

- Conservation chiffrée du jeton de renouvellement Google et renouvellement au redémarrage / pendant l'utilisation.
- Une erreur réseau ne supprime plus silencieusement la session enregistrée ; message explicite si une reconnexion est nécessaire.
- Conservation des cookies de session du moteur classique après fermeture et mise à jour.
- Une reconnexion Google initiale est nécessaire pour les comptes enregistrés avant ce correctif sans jeton de renouvellement.

## 3.6.1

- Présentation immersive : illustration plein cadre, grands titres au premier plan et mots-clés violets.

## 3.6.0

- Présentation au premier lancement, illustration Nova et confirmation supplémentaire pour passer l'importation.
- Import choisi des favoris et de l'historique de profils locaux, exports HTML/JSON et mots de passe CSV.
- Remplissage du mot de passe pendant la saisie de l'e-mail sur le même site HTTPS.
- Lecteur flottant toujours au-dessus, accessible depuis le menu Nova, avec retour dans l'onglet.
- Panneau de téléchargements du moteur classique : progression, pause/reprise, annulation et dossier.
- Sauvegarde de la liste d'onglets et proposition de restauration au lancement.
- Indicateurs compacts pour l'audio, la pause et la fenêtre flottante.

## 3.5.0

- Pause des vidéos et de l'audio en quittant un onglet, désactivable dans Optimiser le navigateur.
- Reprise au retour uniquement pour les médias interrompus par Nova ; protection des changements rapides d'onglets.
- Première pause expliquée par une notification Nova avec accès direct aux paramètres.
- Suggestions Nova aérées sur l'accueil et la barre d'adresse, avec icônes, titres, adresses et navigation au clavier.
- Correction d'une double navigation possible en validant une suggestion avec Entrée.
- Moteur de recherche local démarré à la demande ; aucun serveur local inutilisé au démarrage avec Google.
- Styles réappliqués sans accumulation, historique dédoublonné et sauvegardes regroupées.
- Espace de 12 pixels ajouté entre le logo et les onglets.

## 3.4.5

- Premier onglet décalé de 4 pixels vers la gauche, avec un espace conservé autour du logo compact.

## 3.4.4

- Correction de l'identifiant client Google pour correspondre au secret configuré localement.
- Possibilité de surcharger l'identifiant public sur le PC, sans publier de secret.

## 3.4.3

- Recherche Google par défaut, sans Brave ni serveur requis, avec l'accueil Nova conservé.
- Le raccourci Nova Search ouvre le moteur sélectionné au lieu du catalogue local.
- Saisie masquée du réglage Google directement dans Nova lorsqu'il manque, avec stockage Windows DPAPI.

## 3.4.2

- Configuration locale du client Google via un outil de saisie masquée et Windows DPAPI.
- Le secret du client de bureau n'est ni intégré aux sources ni inclus dans la distribution.
- La connexion n'est lancée qu'après configuration, pour éviter une autorisation qui ne peut pas aboutir.

## 3.4.1

- Quand le plafond quotidien Nova ou le quota Brave est atteint, Google prend automatiquement le relais avec les mêmes mots-clés.
- Bascule explicitée dans les paramètres et dans le pied de page Nova Search.

## 3.4.0

- Nova Search intégré à l'accueil existant : recherche Web via serveur Brave API configurable, index local de secours.
- Clé Brave côté serveur, plafond quotidien d'appels et aucun compteur de résultats inventé.
- NovaBot et serveur autonome pour étendre l'index sans API de recherche tierce.
- Compte simplifié : Google uniquement, nom et photo de profil, restauration d'une session encore valide.
- État OAuth explicite après le retour Google ; aucun succès affiché avant vérification de l'identité.
- Retour et avance conservés entre le moteur classique et le moteur vidéo ; lecteur masqué mis en veille.
- Notification de mise à jour avec icône en bas à droite.
- VPN retiré de l'interface, paramètres directs et menu à trois traits séparé.

## 3.3.0

- Correction du focus clavier YouTube et des champs WebView2.
- Onglets adaptatifs, fermeture sans fond blanc, icônes de fenêtre réduites et curseur standard.
- Coffre local chiffré par Windows, enregistrement sur confirmation et remplissage par site HTTPS.
- Suggestions locales et recherche YouTube avec « yt recherche ».
- Connexion Google Desktop avec PKCE ; serveur Nova Sync facultatif.
- Prévention des ouvertures simultanées du même profil.

## 3.2.1

- Correction de la lecture des en-têtes GitHub avec Qt 6.12.
- Conservation de la version disponible lors d'une réponse de cache HTTP 304.
- Tests de non-régression du vérificateur de mises à jour.

## 3.2.0

- Correction du bouton Accueil et du retour depuis le moteur vidéo.
- Préservation de la saisie d'adresse pendant les chargements en arrière-plan.
- Commandes et raccourcis transmis au lecteur ; fermeture rapide et relance après arrêt.
- Réutilisation du bloqueur déjà installé et réduction des redimensionnements inutiles.
- Paramètres plus étroits, boutons compacts et actions regroupées.
- Mises à jour depuis GitHub, contrôle d'intégrité et notifications de disponibilité / installation.
