"""Step 7. Map of the corpus: every passage is a point (PCA of its embedding), coloured by k-means cluster.
Shown in the Admin section: it makes gaps and neighbouring topics visible.

    python training/build_topic_map.py --clusters 12      ->  models/topic_map.json"""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODELS, load_chunks  # noqa: E402

from ml import cluster  # noqa: E402
from sites_data import nom_en  # noqa: E402


def build(vectors, titles, k=12, max_points=3000, seed=0):
    vectors = np.asarray(vectors, float)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(vectors), size=min(max_points, len(vectors)), replace=False))
    V = vectors[idx]
    xy = cluster.pca2(V)
    span = np.abs(xy).max(axis=0)
    span[span == 0] = 1.0
    xy = xy / span
    labels, _ = cluster.kmeans(V, min(k, len(V)), seed=seed)
    points = [{"x": round(float(xy[i, 0]), 4), "y": round(float(xy[i, 1]), 4), "titre": titles[j], "nom": nom_en(titles[j]), "cluster": int(labels[i])}
              for i, j in enumerate(idx)]
    clusters = []
    for c in sorted(set(labels.tolist())):
        members = [titles[idx[i]] for i in range(len(idx)) if labels[i] == c]
        top = [nom_en(t) for t, _ in Counter(members).most_common(2)]
        clusters.append({"id": int(c), "label": " / ".join(top), "size": len(members)})
    return {"points": points, "clusters": clusters}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clusters", type=int, default=12)
    args = ap.parse_args(argv)
    import faiss

    index = faiss.read_index("index.faiss")
    vectors = index.reconstruct_n(0, index.ntotal)
    titles = [c["titre_article"] for c in load_chunks()]
    assert len(titles) == len(vectors), "chunks.json and index.faiss do not match: run build_index.py"
    data = build(vectors, titles, args.clusters)
    with open(os.path.join(MODELS, "topic_map.json"), "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"✅ {len(data['points'])} points, {len(data['clusters'])} clusters -> models/topic_map.json")


if __name__ == "__main__":
    main()
