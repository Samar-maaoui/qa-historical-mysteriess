import sys

# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import json
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# Connection (XAMPP defaults; override with DB_HOST, DB_USER, DB_PASSWORD, DB_NAME in .env)
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "llm"),
)
cursor = conn.cursor()

# The two tables are rebuilt from the JSON files every time (users and magic_tokens are left untouched)
cursor.execute("DROP TABLE IF EXISTS chunks")
cursor.execute("DROP TABLE IF EXISTS articles")

cursor.execute("""
CREATE TABLE articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titre VARCHAR(255) NOT NULL,
    contenu LONGTEXT NOT NULL,
    source VARCHAR(500) NOT NULL,
    lang VARCHAR(5) NOT NULL DEFAULT 'fr',
    source_type VARCHAR(40) NOT NULL DEFAULT 'Wikipedia (FR)'
)
""")

cursor.execute("""
CREATE TABLE chunks (
    id VARCHAR(255) PRIMARY KEY,
    texte TEXT NOT NULL,
    titre_article VARCHAR(255) NOT NULL,
    source VARCHAR(500) NOT NULL,
    position INT NOT NULL,
    lang VARCHAR(5) NOT NULL DEFAULT 'fr',
    source_type VARCHAR(40) NOT NULL DEFAULT 'Wikipedia (FR)',
    section VARCHAR(255) NOT NULL DEFAULT ''
)
""")

# --- articles ---
for path, lang, source_type in (("corpus.json", "fr", "Wikipedia (FR)"), ("corpus_en.json", "en", "Wikipedia (EN)"), ("corpus_ws.json", "fr", "Wikisource (FR)")):
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        for article in json.load(f):
            cursor.execute(
                "INSERT INTO articles (titre, contenu, source, lang, source_type) VALUES (%s, %s, %s, %s, %s)",
                (article["titre"], article["contenu"], article["source"], lang, source_type),
            )

# --- chunks (position = rank of the vector in index.faiss) ---
with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

for i, chunk in enumerate(chunks):
    cursor.execute(
        "INSERT INTO chunks (id, texte, titre_article, source, position, lang, source_type, section) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (chunk["id"], chunk["texte"], chunk["titre_article"], chunk["source"], i,
         chunk.get("lang", "fr"), chunk.get("source_type", "Wikipedia (FR)"), chunk.get("section", "")[:255]),
    )

conn.commit()

cursor.execute("SELECT COUNT(*) FROM articles")
nb_articles = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM chunks")
nb_chunks = cursor.fetchone()[0]
cursor.execute("SELECT lang, COUNT(*) FROM chunks GROUP BY lang")
by_lang = cursor.fetchall()

print("✅ MySQL database loaded")
print(f"   - {nb_articles} articles")
print(f"   - {nb_chunks} chunks " + ", ".join(f"({lang}: {n})" for lang, n in by_lang))
print("   Check that this number equals the vectors in index.faiss (python build_index.py prints it).")

cursor.close()
conn.close()
