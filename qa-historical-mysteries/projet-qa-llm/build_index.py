import sys

# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import json
import os

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# The SAME model must embed the passages here and the questions in the API (see EMBED_MODEL in .env).
# After fine-tuning (training/finetune_embeddings.py) set EMBED_MODEL=models/embeddings-ft and run this script again.
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)
print(f"Loading {len(chunks)} chunks...")

print(f"Loading the embedding model: {EMBED_MODEL}")
model = SentenceTransformer(EMBED_MODEL)

# a passage is embedded together with its context ("Carthage > History (Wikipedia (EN))")
textes = [((c.get("contexte") or "") + "\n" + c["texte"]).strip() for c in chunks]
print("Computing the embeddings (a few minutes on a CPU)...")
embeddings = model.encode(textes, show_progress_bar=True, convert_to_numpy=True).astype("float32")
assert len(embeddings) == len(chunks)

index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)
faiss.write_index(index, "index.faiss")

with open("chunks_index.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)
with open("index_meta.json", "w", encoding="utf-8") as f:   # lets the API warn if the models do not match the index
    json.dump({"embedding": EMBED_MODEL, "n": int(index.ntotal), "dim": int(embeddings.shape[1]), "with_context": True}, f, indent=1)

print(f"\n✅ Index built: {index.ntotal} vectors of dimension {embeddings.shape[1]}")
print("Files saved: index.faiss, chunks_index.json, index_meta.json")
print("Next: python init_db.py (it must load the same number of chunks).")
