import mysql.connector
import os
import faiss
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

print("Connexion à MySQL...")
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="llm"
)
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT * FROM chunks ORDER BY position")
chunks = cursor.fetchall()
cursor.close()
conn.close()

print(f"{len(chunks)} chunks chargés depuis MySQL")

print("Chargement de l'index FAISS...")
index = faiss.read_index("index.faiss")

print("Chargement du modèle d'embeddings...")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def rechercher_chunks(question, k=6):
    vecteur_question = model.encode([question], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(vecteur_question, k)
    return [chunks[i] for i in indices[0]]


def repondre(question):
    chunks_trouves = rechercher_chunks(question)
    contexte = "\n\n".join(
        f"[Source: {c['titre_article']}]\n{c['texte']}" for c in chunks_trouves
    )
    prompt = f"""Réponds à la question en te basant UNIQUEMENT sur le contexte fourni ci-dessous.
Si la réponse ne se trouve pas dans le contexte, dis clairement que tu ne sais pas.

Contexte :
{contexte}

Question : {question}

Réponse :"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content, chunks_trouves


if __name__ == "__main__":
    questions_test = [
        "Comment la Grande Pyramide de Gizeh a-t-elle été construite ?",
        "Qu'est-ce que le Machu Picchu ?",
    ]
    for q in questions_test:
        print(f"\nQUESTION : {q}")
        reponse, sources = repondre(q)
        print(f"RÉPONSE : {reponse}")