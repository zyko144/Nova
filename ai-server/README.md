# Nova suggestions

API HTTPS partagée, sans clé dans le navigateur. Déployer ce dossier sur Vercel
(Node 22), définir `GROQ_API_KEY` comme secret de production, puis renseigner
l'URL `/api/suggest` dans `browser/ai_suggestions.py`.

`POST /api/suggest` reçoit uniquement `{"query":"mai"}` et renvoie jusqu'à
trois suggestions. Les requêtes contenant une URL, un e-mail ou une clé sont
refusées. Aucune journalisation applicative du texte. Cache mémoire 15 minutes,
512 entrées maximum ; limitation par IP par instance et quatre appels simultanés.
Ces protections mémoire ne constituent pas un quota global persistant : Groq
applique le quota global du compte. Les clés supplémentaires ne l'augmentent pas.
En cas d'indisponibilité ou de quota atteint, Nova conserve ses suggestions locales.
Les journaux d'accès de l'hébergeur restent soumis à sa politique de rétention.

Le service public anonyme peut être appelé en dehors de Nova. Avant une diffusion
à grande échelle, ajouter une limitation globale persistante et un budget adapté.
Ne pas placer de clé dans les fichiers source, les releases ou une URL.
