# Guide de démarrage (projet complet)

Ce dossier contient **tout** : backend, frontend, données, tests, Docker. Il ne contient **pas** ton `.env` (secrets) ni `node_modules`.

## 0. Prérequis
Python 3.11, Node.js 20 ou plus, XAMPP (MySQL démarré, voyant vert). Deux terminaux PowerShell.

## 1. Backend
```
cd C:\chemin\vers\qa-historical-mysteries\projet-qa-llm
python -m venv venv
venv\Scripts\activate                # (venv) doit s'afficher
pip install -r requirements.txt
copy .env.example .env
```
Ouvre `.env` et remplis (reprends les valeurs de ton ancien `.env`) :
```
GROQ_API_KEY=...
SMTP_EMAIL=...
SMTP_APP_PASSWORD=...
SESSION_SECRET=...        # python -c "import secrets; print(secrets.token_hex(32))"  (64 caractères)
FRONTEND_URL=http://localhost:3000
ADMIN_EMAILS=ton@mail.com
```
Le `.env.example` du backend détaille aussi les réglages facultatifs.

## 2. Base de données
Avec MySQL démarré (XAMPP), dans le terminal du backend :
```
python init_auth.py
python init_db.py
```
`init_db.py` recharge les passages depuis `chunks.json` : il doit afficher le **même nombre** que `index.faiss` (4112).

## 3. Tests hors ligne (aucun modèle, aucun réseau)
```
python -m unittest discover -s tests -t .
```
Attendu : `Ran 156 tests ... OK`. Si un module manque : `pip install numpy python-dotenv requests`.

## 4. Lancer l'API
```
uvicorn api:app --reload
```
Premier démarrage : téléchargement du reranker (≈ 0,5 Go), c'est long. Attendu : `Ready: 4112 chunks, 31 topics ...`.
Contrôle : `http://127.0.0.1:8000/health` doit répondre `{"status":"ok", ...}`.

## 5. Frontend
```
cd ..\frontend-next
npm install
npm test
npm run lint
npm run dev
```
Ouvre `http://localhost:3000`. Deux onglets, **sans mot de passe** :
- **Première fois : Sign up.** Ton nom et ton e-mail. Un e-mail de confirmation arrive : clique sur le lien, ton compte est créé et tu es connectée.
- **Ensuite : Sign in.** Ton e-mail seulement : tu reçois un lien de connexion à usage unique (valable 15 minutes). Seuls les e-mails qui ont déjà un compte peuvent en demander un.
- Les anciens utilisateurs (qui se connectaient déjà par lien) peuvent faire Sign in directement.
- Les comptes sont créés automatiquement dans la table `members` (rien à lancer).
Si tu avais déjà un `node_modules` ailleurs, tu peux le copier ici pour éviter l'installation.

## 6. Tester chaque section
| Section | Action | Attendu |
|---|---|---|
| Explorer | « Who was Hannibal Barca? » | réponse mot par mot, numéros [1] cliquables, confiance, sources |
| | « and his wars? » | il comprend qu'il s'agit d'Hannibal |
| | « How do I bake a chocolate cake? » | « I do not know » ou confiance Low |
| | 🔎 Check faithfulness, 📅 Timeline | liste ✅/⚠️ ; frise avec ✓ ou ⚠ unverified (lent au premier appel) |
| Compare | Carthage et Kairouan | résumé et tableau |
| Map | filtrer par époque | les points changent |
| Notebook | History, Flashcards, Progress | tes questions s'y trouvent |
| Kids | une question à Hanni, puis chaque jeu | réponses douces avec des emojis (seule section qui en a) ; « how to build a bomb » est refusé gentiment |
| Admin | seulement si ton e-mail est dans `ADMIN_EMAILS` | statistiques |

## 6 bis. Test d'intégration réel (facultatif)
```
pip install httpx
$env:RUN_INTEGRATION="1"
python -m unittest discover -s tests_integration -v
```

## 7. Docker (facultatif)
À la racine du projet :
```
copy .env.example .env               # un fichier .env pour docker-compose (mot de passe MySQL...)
docker compose up --build
```
Il lance MySQL, charge le corpus tout seul, puis l'API et le site sur `http://localhost:3000`. Tes secrets restent dans `projet-qa-llm\.env`.
Le premier démarrage télécharge les modèles dans un volume (plusieurs minutes), puis ils sont conservés.
HTTPS avec un nom de domaine : `DOMAIN=ton-domaine.org` dans `.env`, puis `docker compose --profile prod up -d`.
**Ces fichiers Docker n'ont pas été construits là où ils ont été écrits** : si `docker compose build` échoue, copie-moi l'erreur.

## 8. Mesurer la qualité (le plus important pour le rapport)
Tout est décrit dans `docs/PARCOURS_IA.md`. L'essentiel :
```
python experiments\run_experiments.py --judge --fidelity --pause 1.5
python experiments\regression.py --save-baseline
python experiments\adversarial.py
```
Résultat : `experiments\results\summary.md`.

## 9. Dépannage
| Symptôme | Cause probable |
|---|---|
| `Module not found: Can't resolve './globals.css'` | tu lances le frontend depuis le mauvais dossier ; utilise celui-ci |
| `No module named 'dotenv'` | venv non activé ou `pip install -r requirements.txt` oublié |
| `WARNING: the FAISS index has N vectors but the database has M chunks` | relancer `python build_index.py` puis `python init_db.py` |
| 401 partout après connexion | session perdue : se reconnecter avec un nouveau lien |
| Pas d'onglet Admin | `ADMIN_EMAILS` absent du `.env` ; redémarrer l'API |
| « The language model returned an empty answer » | le modèle a dépensé tout son budget à réfléchir. Regarde le terminal de l'API : une ligne `llm_empty finish_reason=...` donne la cause. Réglages : `LLM_REASONING_EFFORT=low` (défaut), ou `LLM_FALLBACK_MODEL` dans `.env` |
| Pas d'e-mail de confirmation ni de lien de connexion | vérifie `SMTP_EMAIL` et `SMTP_APP_PASSWORD` dans `.env`, puis le dossier spam ; attends 30 secondes avant de recommencer |
| « No account found for this email address » | tu n'as pas encore de compte avec cet e-mail : onglet **Sign up** (ou l'e-mail est mal écrit) |
| « An account with this email already exists » | onglet **Sign in** : le compte existe déjà |
| Le lien de confirmation « is invalid, expired or already used » | un lien ne marche qu'une fois pendant 15 minutes : refais Sign up (ou Sign in) pour en recevoir un nouveau, après 30 secondes |
| Réponse non affichée mot par mot | le proxy a tamponné le flux ; le chat marche quand même |

Sécurité : ne partage jamais `projet-qa-llm\.env`. Si une clé a fuité, régénère-la (Groq, mot de passe d'application Gmail, `SESSION_SECRET`).
