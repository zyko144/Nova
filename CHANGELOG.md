# Historique

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
