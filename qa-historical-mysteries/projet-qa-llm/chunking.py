import sys

# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import json
import os

from langchain_text_splitters import RecursiveCharacterTextSplitter

import core
from sites_data import nom_en

# French corpus (always) + English corpus (if collect_extra_sources.py was run)
sources = [("corpus.json", "fr", "Wikipedia (FR)")]
if os.path.exists("corpus_en.json"):
    sources.append(("corpus_en.json", "en", "Wikipedia (EN)"))
if os.path.exists("corpus_ws.json"):   # optional: python collect_sources.py wikisource
    sources.append(("corpus_ws.json", "fr", "Wikisource (FR)"))

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # approximate size of each chunk (characters)
    chunk_overlap=100,   # overlap between chunks to keep the context
    separators=["\n\n", "\n", ". ", " ", ""],
)

chunks = []
for path, lang, source_type in sources:
    with open(path, "r", encoding="utf-8") as f:
        corpus = json.load(f)
    before = len(chunks)
    for article in corpus:
        text = article["contenu"]
        offsets = core.section_offsets(text)
        cursor = 0
        for i, morceau in enumerate(splitter.split_text(text)):
            pos = text.find(morceau[:60], cursor)
            if pos == -1:
                pos = text.find(morceau[:60])
            pos = cursor if pos == -1 else pos
            cursor = max(cursor, pos)
            section = core.section_at(offsets, pos)
            # the context (topic > section) is added to the text that gets embedded, so a passage knows where it comes from
            contexte = nom_en(article["titre"]) + (f" > {section}" if section else "") + f" ({source_type})"
            # French ids keep their historical format; other ids carry the source
            suffix = "" if source_type == "Wikipedia (FR)" else ("_en" if lang == "en" else "_" + source_type.split()[0].lower())
            chunk_id = f"{article['titre']}{suffix}_{i}"
            chunks.append({
                "id": chunk_id,
                "texte": morceau,
                "titre_article": article["titre"],   # the French title stays the technical key
                "source": article["source"],
                "lang": lang,
                "source_type": source_type,
                "section": section,
                "contexte": contexte,
            })
    print(f"{path}: {len(corpus)} articles -> {len(chunks) - before} chunks")

with open("chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print(f"Total: {len(chunks)} chunks saved in chunks.json")
print("Example chunk:", chunks[0])
