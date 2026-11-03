import mysql.connector
import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Récupérer les articles depuis MySQL
conn = mysql.connector.connect(
    host="localhost", user="root", password="", database="llm"
)
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT * FROM articles")
articles = cursor.fetchall()
cursor.close()
conn.close()

questions_generees = []

for article in articles:
    # On limite le texte envoyé pour économiser des tokens
    extrait = article["contenu"][:3000]
    
    prompt = f"""À partir de cet extrait d'article sur "{article['titre']}", génère exactement 2 questions factuelles précises avec leurs réponses correctes (courtes, 1-2 phrases).

Extrait :
{extrait}

Réponds STRICTEMENT dans ce format JSON, sans texte autour :
[
  {{"question": "...", "reponse_attendue": "..."}},
  {{"question": "...", "reponse_attendue": "..."}}
]"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    try:
        texte_reponse = response.choices[0].message.content.strip()
        # Nettoyer si le modèle ajoute des ```json autour
        texte_reponse = texte_reponse.replace("```json", "").replace("```", "").strip()
        qa_generees = json.loads(texte_reponse)
        for qa in qa_generees:
            qa["source"] = article["titre"]
            questions_generees.append(qa)
        print(f"✅ {article['titre']} : {len(qa_generees)} questions générées")
    except Exception as e:
        print(f"❌ Erreur sur {article['titre']} : {e}")

# Sauvegarder
with open("questions_evaluation.json", "w", encoding="utf-8") as f:
    json.dump(questions_generees, f, ensure_ascii=False, indent=2)

print(f"\n{len(questions_generees)} questions de test générées et sauvegardées dans questions_evaluation.json")