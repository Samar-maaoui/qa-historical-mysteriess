import json
import os
import mysql.connector
import faiss
from sentence_transformers import SentenceTransformer, CrossEncoder
from dotenv import load_dotenv
from groq import Groq
import numpy as np
import time
import re


load_dotenv()

# --- Chargement des ressources (comme dans app.py) ---
print("Chargement des ressources...")
conn = mysql.connector.connect(host="localhost", user="root", password="", database="llm")
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT * FROM chunks ORDER BY position")
chunks = cursor.fetchall()
cursor.close()
conn.close()

index = faiss.read_index("index.faiss")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

with open("questions_evaluation.json", "r", encoding="utf-8") as f:
    questions_test = json.load(f)


def rechercher_chunks(question, k=10):
    vecteur = model.encode([question], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(vecteur, k)
    return [chunks[i] for i in indices[0]]


def reranker_chunks(question, chunks_candidats, top_n=6):
    paires = [[question, c["texte"]] for c in chunks_candidats]
    scores = reranker.predict(paires)
    chunks_scores = list(zip(chunks_candidats, scores))
    chunks_scores.sort(key=lambda x: x[1], reverse=True)
    return [c for c, s in chunks_scores[:top_n]]


def repondre(question):
    chunks_candidats = rechercher_chunks(question)
    chunks_trouves = reranker_chunks(question, chunks_candidats)
    contexte = "\n\n".join(f"[Source: {c['titre_article']}]\n{c['texte']}" for c in chunks_trouves)
    prompt = f"""Réponds à la question en te basant UNIQUEMENT sur le contexte fourni.
Si l'information n'est pas dans le contexte, dis que tu ne sais pas.

Contexte :
{contexte}

Question : {question}

Réponse :"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def juger_reponse(question, reponse_attendue, reponse_obtenue):
    """Le LLM compare et note la réponse du système."""
    prompt = f"""Tu es un évaluateur strict. Compare la réponse obtenue à la réponse attendue pour cette question.

Question : {question}
Réponse attendue : {reponse_attendue}
Réponse obtenue du système : {reponse_obtenue}

Note la réponse obtenue de 0 à 10 selon sa justesse factuelle par rapport à la réponse attendue.
Réponds STRICTEMENT dans ce format, sans autre texte :
NOTE: [chiffre de 0 à 10]
JUSTIFICATION: [une phrase courte]"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", max_tokens=1000,  # a reasoning model needs room to think: 150 returned EMPTY judgments for 7 questions
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# --- Évaluation complète ---
resultats = []

for i, item in enumerate(questions_test, 1):
    print(f"\n[{i}/{len(questions_test)}] {item['question']}")
    reponse_systeme = repondre(item["question"])
    jugement = juger_reponse(item["question"], item["reponse_attendue"], reponse_systeme)

    # Extraire la note
    try:
        note = int(re.search(r"NOTE\s*:\s*\**\s*(\d{1,2})", jugement).group(1))
    except:
        note = None

    resultats.append({
        "question": item["question"],
        "source": item["source"],
        "reponse_attendue": item["reponse_attendue"],
        "reponse_systeme": reponse_systeme,
        "jugement": jugement,
        "note": note
    })
    print(f"  → Note : {note}/10")
    time.sleep(1)  # petite pause pour éviter de saturer l'API gratuite

# --- Sauvegarde et calcul du score global ---
with open("resultats_evaluation.json", "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)

notes_valides = [r["note"] for r in resultats if r["note"] is not None]
score_moyen = sum(notes_valides) / len(notes_valides) if notes_valides else 0

print(f"\n{'='*50}")
print(f"ÉVALUATION TERMINÉE")
print(f"Score moyen : {score_moyen:.1f}/10")
print(f"Questions évaluées : {len(notes_valides)}/{len(questions_test)}")
print(f"{'='*50}")