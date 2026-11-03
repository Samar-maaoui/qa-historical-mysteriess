# QA Historical Mysteries

A history question-answering assistant built with **retrieval-augmented generation (RAG)**. It answers only from cited sources
(Wikipedia, Wikidata), says how reliable each answer is, and can check its own sentences against the sources.
Internship project, ESPRIT (Tunis), summer 2026.

## What it does

| Section | Purpose |
|---|---|
| **Explorer** | chat with streamed answers, clickable numbered citations, translation, audio, images, map, quiz, faithfulness check, timeline |
| **Compare** | two subjects side by side, built only from the retrieved passages |
| **Map** | places filtered by era and by country |
| **Notebook** | per-user history, spaced-repetition flashcards, progress and badges |
| **Kids** (the only section with emojis) | Hanni the time-travelling elephant: gentle answers, quiz, treasure-map game, true or false, stories, stickers |
| **Admin** | usage, questions the corpus could not answer, user feedback, corpus map |

## Accounts (no password)

- **Sign up:** your name and your email. A confirmation link arrives by email; opening it creates your account and signs you in.
- **Sign in:** your email. A one-time sign-in link arrives by email (valid 15 minutes, usable once). Only emails that have an account can ask for one.
- Nothing secret is stored about you: no password, only your name and email. Someone who signs up with your address only makes you receive an email: without access to your mailbox they can never sign in.

## How it works

```
 question ──► query rewriting (follow-ups) ──► hybrid search ──► reranking ──► prompt (numbered passages) ──► LLM ──► answer + citations
                                                vectors (FAISS)     cross-encoder                                          │
                                                + keywords (BM25)                                                          ▼
                                                                          calibrated confidence · NLI faithfulness check · date verification
```

- **Corpus:** 31 French Wikipedia articles (4,112 passages), extensible to about 80 topics, with English Wikipedia as a second source and Wikidata for structured facts.
- **Models:** multilingual MiniLM embeddings, multilingual cross-encoder reranker, multilingual NLI model, `gpt-oss-20b` through Groq. Every model name is configurable in `.env` and has a fallback.
- **Research-style API (no screen):** strict mode, contradiction search and Wikidata facts remain available through the API for experiments.
- **Learned components (numpy, trained in this repository):** calibrated confidence, NLI calibrator, question-intent router, corpus map. Fine-tuning scripts for the embeddings, the reranker and a small LoRA model are in `projet-qa-llm/training/`.
- **Stack:** FastAPI + MySQL (backend), Next.js (frontend), magic-link authentication.

## Quick start (local, Windows or Linux)

```
# 1. database: start MySQL (XAMPP), then
cd projet-qa-llm
python -m venv venv && venv\Scripts\activate        # Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                              # fill in the keys (see GUIDE_DEMARRAGE.md)
python init_auth.py && python init_db.py
uvicorn api:app --reload

# 2. frontend, in a second terminal
cd frontend-next
npm install
npm run dev                                         # http://localhost:3000
```

With Docker: `docker compose up --build` (see `GUIDE_DEMARRAGE.md`).

## Tests

| Level | Command | What it proves |
|---|---|---|
| Backend, offline | `cd projet-qa-llm && python -m unittest discover -s tests -t .` | the logic and the API flows, with stand-ins for MySQL, FAISS, the models and the LLM (156 tests) |
| Frontend | `cd frontend-next && npm test && npm run lint` | every section renders, the Sign in / Sign up screens work, no emoji appears outside Kids |
| Integration, real services | `RUN_INTEGRATION=1 python -m unittest discover -s tests_integration -v` | your real database, index, models and LLM work together |
| Evaluation | `python experiments/run_experiments.py --judge --fidelity` | the **quality** of the answers (88 questions) |
| Regression and attacks | `python experiments/regression.py`, `python experiments/adversarial.py` | a change did not make it worse; passages cannot give orders to the model |

The offline tests prove the code, not the quality of the answers: quality numbers come from the evaluation.

## Repository layout

```
projet-qa-llm/        FastAPI backend: api.py (routes), engine.py (RAG), core.py, prompts.py, store.py, ml/, training/, experiments/, tests/
frontend-next/        Next.js app: app/ (layout, pages, styles), components/ (every section), lib/, tests/
docker-compose.yml    MySQL + API + web (+ optional HTTPS with Caddy)
GUIDE_DEMARRAGE.md    step-by-step guide in French
docs/PARCOURS_IA.md   how to train, calibrate and measure the AI components
```

## Limits (please read)

- Answers are only as good as the corpus: questions outside it should be refused, and exact figures are the weakest point.
- Confidence estimates "the sources contain the answer", not "the answer is true".
- The offline tests cannot judge answer quality; the learned components must be trained and measured on your own data (see `docs/PARCOURS_IA.md`).
- The Kids section is best-effort (gentle prompts, blocked words, sensitive topics kept out of random content): review it before showing it to children.
- Docker files are provided and syntax-checked but were not built where they were written.

## Credits and licences

Texts come from Wikipedia and Wikidata (CC BY-SA 4.0 and CC0): keep the attribution when you reuse them. Models belong to their authors (sentence-transformers, Hugging Face, OpenAI gpt-oss through Groq).
