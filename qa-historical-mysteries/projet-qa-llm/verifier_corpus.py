import json

with open("corpus.json", "r", encoding="utf-8") as f:
    corpus = json.load(f)

for article in corpus:
    print(f"{article['titre']} — {len(article['contenu'])} caractères — {article['source']}")