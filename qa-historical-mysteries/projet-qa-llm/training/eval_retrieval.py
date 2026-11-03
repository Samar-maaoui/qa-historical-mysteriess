"""Step 4. Compare embedding models on the TEST split (questions from articles never used for training).

    python training/eval_retrieval.py --models paraphrase-multilingual-MiniLM-L12-v2,models/embeddings-ft
Prints a Markdown table (Recall@1/5/10 and MRR) ready to paste in the report."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, load_chunks, read_jsonl  # noqa: E402

from ml import pairs  # noqa: E402


def evaluate(encode, chunks, questions):
    """encode(list of str) -> normalised matrix. Returns the retrieval metrics."""
    index_of = {c["id"]: i for i, c in enumerate(chunks)}
    keep = [q for q in questions if q["chunk_id"] in index_of]
    P = encode([pairs.passage_text(c) for c in chunks])
    Q = encode([q["question"] for q in keep])
    return pairs.retrieval_metrics(Q @ P.T, [index_of[q["chunk_id"]] for q in keep]) | {"n": len(keep)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma separated model names or folders")
    ap.add_argument("--split", default="test")
    args = ap.parse_args(argv)
    from sentence_transformers import SentenceTransformer

    chunks = load_chunks()
    questions = read_jsonl(os.path.join(DATA, f"{args.split}.jsonl"))
    if not questions:
        sys.exit(f"No {args.split} questions: run make_pairs.py and split_data.py first.")
    print(f"| Model | Recall@1 | Recall@5 | Recall@10 | MRR | questions |\n|---|---|---|---|---|---|")
    for name in args.models.split(","):
        m = SentenceTransformer(name.strip())
        r = evaluate(lambda texts: m.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False), chunks, questions)
        print(f"| {name.strip()} | {r['recall@1']:.0%} | {r['recall@5']:.0%} | {r['recall@10']:.0%} | {r['mrr']:.3f} | {r['n']} |")


if __name__ == "__main__":
    main()
