# Nova Search

L'interface Nova est intégrée au navigateur, dans le style de son accueil
actuel. Deux modes sont fournis : recherche Web via Brave API sur un serveur,
ou petit index Nova local. Le mode local n'offre pas la couverture de Google.

## Activer la recherche Web

1. Créer un compte sur https://api-dashboard.search.brave.com/ et générer une
   clé pour Web Search. Vérifier les conditions et tarifs du fournisseur.
2. Sur le serveur uniquement, copier `.env.example` vers `.env` dans ce
   dossier. Compléter BRAVE_API_KEY. Ne pas publier ce fichier ni cette clé.
3. Fixer BRAVE_DAILY_LIMIT, par défaut 200 appels maximum par jour UTC.
   Les tentatives réservées comptent aussi en cas d'erreur du fournisseur.
4. Depuis ce dossier : `docker compose up -d --build`.
5. Placer un reverse proxy HTTPS devant le port local 8787 et, pour un usage
   privé, protéger cet accès au niveau du proxy. Le service limite aussi
   chaque adresse directe à 30 recherches par minute. Derrière un proxy,
   cette limite s'applique au proxy ; les en-têtes IP clients ne sont pas
   utilisés aveuglément. Adapter la protection et la capacité à votre usage.
6. Dans Nova > Paramètres > Moteur de recherche > Configurer le serveur de
   recherche Web, renseigner l'adresse HTTPS de ce serveur. Ne pas saisir
   la clé Brave dans le navigateur. Le style d'accueil Nova est conservé.

Aucun compte Brave, abonnement, domaine ou hébergement n'est créé par le code.
Aucune clé réelle n'est fournie. Sans ces éléments, la couverture Web n'est
pas active ; le navigateur utilise son index local clairement identifié.

Brave reçoit les requêtes lancées et fournit les résultats. Nova ne stocke
pas ces résultats dans l'index et ne journalise pas les requêtes. Seul le
nombre d'appels est conservé pour plafonner les dépenses. Aucun appel payant
n'est lancé au fil de la saisie. Une panne produit un message explicite. Au plafond quotidien Nova ou au
quota Brave, le navigateur est redirigé vers Google avec les mêmes mots-clés ;
Google reçoit alors cette recherche et applique sa propre politique. Cette
bascule est indiquée dans les paramètres et le pied de page de recherche. Vérifier séparément les
journaux et règles du reverse proxy et du fournisseur.

L'API ne donne pas un compteur global garanti de résultats : Nova n'affiche
pas de millions de correspondances inventées. L'accès à un index de milliards
de pages ne signifie pas autant de résultats pour chaque requête. La pagination
suit les limites réelles de Brave (10 pages de 10 résultats dans ce client).
Le plafond de 200 appels/jour représente au plus 1 USD/jour au tarif publié
le 23 novembre 2026 de 5 USD/1000 appels, hors crédits et taxes. Vérifier le
tarif courant avant activation : https://brave.com/search/api/

## Organisation

- `browser/nova_search/brave.py` : adaptateur serveur, clé et budget.
- `browser/nova_search/server.py` : HTML, API JSON et contrôle du débit.
- `browser/nova_search/web.py` : interface noire et violette, sans script tiers.
- `browser/nova_search/index.py` : index local SQLite FTS5 et classement BM25.
- `browser/nova_search/catalog.py` : catalogue initial, descriptions originales.
- `browser/nova_search/crawler.py` : NovaBot, exploration HTTPS bornée.
- `design/nova-search-concept.png` : maquette générée, compteurs illustratifs.
  Les captures réelles et le produit utilisent exclusivement leurs vraies données.

## Utilisation Python autonome

Depuis `browser`, avec Python 3.12, sans dépendance supplémentaire :

```powershell
python -m nova_search --db data/index.sqlite3 serve --provider brave
python -m nova_search --db data/index.sqlite3 serve --provider local
python -m nova_search --db data/index.sqlite3 crawl https://docs.python.org/fr/3/ --limit 30
python -m nova_search --db data/index.sqlite3 stats
python -m nova_search --db data/index.sqlite3 remove https://exemple.fr/page
```

Le serveur de développement écoute par défaut sur 127.0.0.1:8787. Docker lie
également ce port à la boucle locale de l'hôte ; le reverse proxy doit être
sur cet hôte ou relié explicitement par un réseau Docker adapté. La base est
persistée dans le volume nova-index. L'image tourne sans privilèges root.

## Index local et NovaBot

Le navigateur démarre son service local sur 127.0.0.1, port et chemin aléatoires.
La base locale est distincte des profils, cookies et mots de passe. Le catalogue
initial contient 16 entrées éditoriales. Ajouter des sites depuis les paramètres
lance une exploration en arrière-plan de 20 pages maximum sur le site demandé.

NovaBot ne lit aucun cookie du navigateur. Il reste sur les domaines fournis,
vérifie les IP publiques à chaque redirection, fixe l'IP validée pour la
connexion TLS, vérifie robots.txt et noindex/nofollow. Limites : 1 Mio/page,
12 secondes/connexion, au moins une seconde entre deux accès au même domaine,
file et nombre de pages bornés. Les pages JavaScript ne sont pas rendues.
L'administration de l'index passe par le navigateur local ou la CLI, jamais
par une API d'exploration publique. Ce robot de première version ne constitue
pas encore une infrastructure d'indexation mondiale.

Références : https://api-dashboard.search.brave.com/documentation/services/web-search
https://www.sqlite.org/fts5.html
https://www.rfc-editor.org/rfc/rfc9309.html
