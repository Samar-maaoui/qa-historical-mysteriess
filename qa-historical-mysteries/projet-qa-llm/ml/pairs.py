"""Training-pair helpers: hard negatives and retrieval metrics (numpy only)."""
import numpy as np

import core


def hard_negative(question, bm25, chunks, gold_article, rng, top=30, pool=10):
    """A passage that looks relevant to the question (BM25) but belongs to ANOTHER article: the most useful kind of negative."""
    cands = [i for i, _ in bm25.top(core.tokenize(question), top) if chunks[i]["titre_article"] != gold_article]
    if not cands:
        cands = [i for i, c in enumerate(chunks) if c["titre_article"] != gold_article]
    return rng.choice(cands[:pool])


def build_triplets(pairs, chunks, bm25, rng, n_neg=1):
    by_id = {c["id"]: c for c in chunks}
    out = []
    for p in pairs:
        gold = by_id.get(p["chunk_id"])
        if gold is None:
            continue
        negs = [hard_negative(p["question"], bm25, chunks, gold["titre_article"], rng) for _ in range(n_neg)]
        out.append({"question": p["question"], "positive": passage_text(gold), "negatives": [passage_text(chunks[i]) for i in negs],
                    "article": gold["titre_article"], "chunk_id": gold["id"]})
    return out


def passage_text(chunk):
    """The text that is embedded: context first, then the passage (same as build_index.py)."""
    return ((chunk.get("contexte") or "") + "\n" + chunk["texte"]).strip()


def retrieval_metrics(sim, gold, ks=(1, 5, 10)):
    """sim: (n_questions, n_passages) similarity matrix; gold: set (or int) of correct passage indices per question."""
    sim = np.asarray(sim, float)
    ranks = []
    for row, g in zip(sim, gold):
        g = {g} if isinstance(g, (int, np.integer)) else set(g)
        order = np.argsort(-row)
        pos = [i for i, j in enumerate(order, 1) if int(j) in g]
        ranks.append(pos[0] if pos else len(row) + 1)
    ranks = np.array(ranks)
    out = {f"recall@{k}": float((ranks <= k).mean()) for k in ks}
    out["mrr"] = float((1.0 / ranks).mean())
    return out
