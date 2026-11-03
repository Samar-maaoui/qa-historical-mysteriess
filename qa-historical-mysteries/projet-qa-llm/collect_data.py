

import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import sys

import wikipediaapi
import json

# Configuration de l'API Wikipedia (en français)
wiki = wikipediaapi.Wikipedia(
    user_agent='ProjetQA-LLM/1.0',
    language='fr'
)

# Liste des sujets choisis
sujets = [
    "Grande Pyramide de Gizeh",
    "Machu Picchu",
    "Stonehenge",
    "Pompéi",
    "Civilisation maya",
    "Civilisation minoenne",
    "Île de Pâques",
    "Pétra",
    "Angkor Vat",
    "Atlantide",
    "Nan Madol",
    "Göbekli Tepe",
    "Olmèques",
    "Teotihuacan",
    "Colosse de Rhodes",
      "Carthage",
    "Guerres puniques",
    "Hannibal Barca",
    "Dougga",
    "El Jem",
    "Utique",
    "Kerkouane",
    "Kairouan",
    "Grande Mosquée de Kairouan",
    "Dynastie hafside",
    "Ifriqiya",
    "Protectorat français de Tunisie",
    "Habib Bourguiba",
    "Mouvement national tunisien",
    "Indépendance de la Tunisie",
    "Révolution tunisienne"
]

# python collect_data.py --extended   ->   adds about 50 world-history topics to the 31 core ones
if "--extended" in sys.argv:
    from sites_data import EXTRA_NAMES
    extra = list(EXTRA_NAMES) + ["Empire romain", "Athènes antique", "Sparte", "Empire byzantin", "Grande Muraille de Chine", "Chute du mur de Berlin"]
    sujets += [t for t in dict.fromkeys(extra) if t not in sujets]
    print(f"Extended corpus: {len(sujets)} topics")

corpus = []

for sujet in sujets:
    page = wiki.page(sujet)
    if page.exists():
        corpus.append({
            "titre": sujet,
            "contenu": page.text,
            "source": page.fullurl
        })
        print(f"✅ Récupéré : {sujet} ({len(page.text)} caractères)")
    else:
        print(f"❌ Introuvable : {sujet}")

# Sauvegarde dans un fichier JSON
with open("corpus.json", "w", encoding="utf-8") as f:
    json.dump(corpus, f, ensure_ascii=False, indent=2)

print(f"\n{len(corpus)} articles sauvegardés dans corpus.json")