# Parcours IA : un système mesuré, calibré et reproductible

Ce document décrit les composants d'IA du projet et comment les mesurer et les entraîner :
mesure sérieuse, recherche et citations plus fiables, confiance calibrée, modèles ML entraînables, corpus élargi.

## 1. Ce qui est nouveau

| Domaine | Ajouts |
|---|---|
| **Mesure** | 88 questions (français, arabe, suivis de conversation, fausses prémisses, hors corpus), précision des citations, `experiments/regression.py` (32 questions de référence, alerte si une métrique baisse), `experiments/adversarial.py` (injection de prompt) |
| **Recherche** | passages **contextualisés** (sujet › section › source) pour les embeddings et les mots-clés, **réécriture** des questions de suivi par le LLM, reranker multilingue |
| **Génération** | température 0, prompts versionnés (`PROMPT_VERSION` enregistré avec chaque réponse), passages traités comme données non fiables (défense contre l'injection), réessai si réponse vide |
| **Fiabilité** | **précision des citations** (le passage cité est-il celui qui soutient la phrase ?), mode strict qui corrige aussi les mauvaises citations, **dates de la frise vérifiées** dans les sources (✓ / ⚠ unverified) |
| **ML entraîné (numpy)** | **confiance calibrée** (`ml/confidence.py`) qui remplace les seuils 22/30, **calibrage NLI** sur tes annotations (`ml/nli_cal.py`), **routeur d'intention** déjà entraîné (`models/intent.json`), carte du corpus (PCA + k-means) |
| **ML à entraîner (GPU conseillé)** | fine-tuning des embeddings et du reranker sur des paires synthétiques, **découpage par article** (sans fuite), RAFT + LoRA pour un petit LLM local |
| **Connaissances** | `collect_data.py --extended` (≈ 80 sujets), seconde source EN, **Wikidata** (dates, coordonnées, pays), Wikisource (expérimental) |
| **Interface** | probabilité calibrée affichée, aide « ceci ressemble à une comparaison / frise », précision des citations dans la vérification, carte du corpus dans Admin (les faits Wikidata restent disponibles par l'API) |
| **Qualité** | 156 tests Python hors ligne, 19 contrôles React, tests d'intégration réels (`tests_integration/`), CI, sonde `/health`, limitation de débit, journaux JSON |

## 2. Installation

Voir `GUIDE_DEMARRAGE.md`. Tout ce qui est « appris » est **facultatif** : l'API le charge seulement s'il existe **et** s'il correspond à tes modèles actuels.

## 3. Parcours conseillé (dans cet ordre)

**A. Contrôle** : `python -m unittest discover -s tests -t .` (dans `projet-qa-llm`) puis `npm test` (dans `frontend-next`).

**B. Élargir et reconstruire le corpus** (une fois)
```
python collect_data.py --extended          # ou sans --extended pour garder les 31 sujets
python collect_extra_sources.py            # Wikipedia EN
python collect_sources.py wikidata         # faits structurés (lus directement par l'API)
python chunking.py
python build_index.py
python init_db.py
```
Les nombres de `build_index.py` et `init_db.py` doivent être identiques. Redémarre l'API. Les distances changent : les seuils 22/30 ne sont plus fiables, c'est la raison d'être de l'étape E.

**C. Mesure de départ** (conserve ces chiffres : ils servent de « avant »)
```
python experiments\run_experiments.py --judge --fidelity --pause 1.5
python experiments\regression.py --save-baseline
python experiments\adversarial.py
```

**D. Entraîner la recherche** (GPU conseillé : Google Colab)
```
python training\make_pairs.py --per-article 15
python training\split_data.py
python training\finetune_embeddings.py --epochs 2
python training\eval_retrieval.py --models paraphrase-multilingual-MiniLM-L12-v2,models\embeddings-ft
```
Si le modèle affiné est meilleur **sur le split test** : `EMBED_MODEL=models/embeddings-ft` dans `.env`, puis `build_index.py` et `init_db.py`. Même démarche pour `finetune_reranker.py` (`RERANKER_MODEL`). Refais ensuite l'étape C et compare avec `regression.py`.

**E. Calibrer la confiance**
```
python training\train_confidence.py
```
Lis le tableau « Confidence shown / really answerable » : c'est la phrase du rapport (« quand le système dit *High*, les sources contiennent la réponse dans X % des cas »). Redémarre l'API. Si le tableau est bon, tu peux activer `ABSTAIN_P=0.15` : l'API refuse alors **sans appeler le LLM** quand la probabilité est trop basse. **À refaire après tout changement de modèle d'embeddings ou de reranker.**

**F. Calibrer la vérification de fidélité** (demande ~1 heure d'annotation)
```
python training\label_nli.py --n 40
```
Ouvre `training\data\nli_to_label.csv` dans Excel, remplis la colonne `label` (1 = le passage soutient la phrase, 0 = non) pour au moins 150 lignes, puis `python training\train_nli_calibrator.py`. Le script affiche l'accord avec toi avant/après.

**G. Carte du corpus** : `python training\build_topic_map.py` (visible dans Admin).

**H. Avancé et facultatif** : `python training\lora_raft.py prepare` puis `train` sur un GPU : un petit LLM local qui apprend à citer et à refuser. Non testé sur GPU : point de départ.

## 4. Le test d'intégration

- `tests/` : 156 tests **hors ligne** avec de fausses dépendances. Ils vérifient que le code s'enchaîne, pas que tes vrais services répondent.
- `tests_integration/test_live.py` : de **vrais** tests d'intégration (vraie base, vrais modèles, vrai LLM). `pip install httpx`, `$env:RUN_INTEGRATION="1"`, `python -m unittest discover -s tests_integration -v`. Ils vérifient notamment que l'index FAISS et la base ont le même nombre de passages, que les routes refusent les visiteurs, que les citations sont valides et que le suivi de conversation est compris.

## 5. Ce qu'il faut écrire honnêtement dans le rapport

- **Rien n'a été exécuté avec les vrais modèles ici** : les 129 tests prouvent la logique, pas la qualité des réponses. Tous les chiffres du rapport doivent venir de **tes** exécutions.
- Le routeur d'intention donne deux chiffres : questions à formulation inédite (pessimiste, ≈ 60-65 %) et 37 questions écrites à la main (optimiste, ≈ 95 %, car j'ai conçu les modèles en les connaissant). C'est un indice d'aide, pas un classifieur de production.
- Les paires d'entraînement sont écrites par un LLM : plus faciles que de vraies questions. Seule la **différence** entre modèles compte, mesurée sur des articles jamais vus à l'entraînement.
- La confiance calibrée estime « les sources contiennent la réponse » (ou « la réponse contient le fait attendu » avec `--answers`), pas « la réponse est vraie ».
- Wikisource est expérimental (résultats de recherche parfois hors sujet : relis `corpus_ws.json`). UNESCO n'est pas intégré.
- Le fine-tuning enseigne un **comportement** (citer, refuser), pas des faits.

## 6. Variables ajoutées

| Variable | Rôle |
|---|---|
| `MODEL_DIR` | dossier des modèles appris (défaut `models/`) |
| `ABSTAIN_P` | seuil de refus avant génération (0 = désactivé) |
| `TRAINING_DATA` | dossier des données d'entraînement (défaut `training/data/`) |
| `EMBED_MODEL` / `RERANKER_MODEL` / `NLI_MODEL` | modèles utilisés (déjà existants ; `build_index.py` lit aussi `EMBED_MODEL`) |

## 7. Dépannage

| Symptôme | Cause probable |
|---|---|
| `WARNING: the index was built with ... but EMBED_MODEL is ...` | l'index et le modèle de questions diffèrent : relancer `build_index.py` ou corriger `EMBED_MODEL` |
| `models/confidence.json was trained with other models ... ignored` | relancer `training/train_confidence.py` |
| `nli_calibrator.json was trained for another NLI model` | relancer `training/train_nli_calibrator.py` |
| Les dates de la frise sont toutes « ⚠ unverified » | l'article source n'écrit pas l'année sous une forme reconnue (« en l'an 79 », « 247 av. J.-C. », « 1881 »), ou le LLM a donné une date approchée |
| `train_confidence.py` : « Not enough examples of both kinds » | lancer d'abord `make_pairs.py` et `split_data.py` |
| La carte du corpus est introuvable (404) | `python training/build_topic_map.py` puis redémarrer l'API |
