"""Step 3a. Fine-tune the embedding model on the training pairs (MultipleNegativesRankingLoss + one hard negative per question).

    python training/finetune_embeddings.py --epochs 2
Then:  python training/eval_retrieval.py --models paraphrase-multilingual-MiniLM-L12-v2,models/embeddings-ft
If it is better on the TEST split:  set EMBED_MODEL=models/embeddings-ft in .env and run build_index.py + init_db.py again.
A GPU (Google Colab is enough) makes this 20x faster, but a CPU can do a few hundred pairs."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, MODELS, load_chunks, read_jsonl  # noqa: E402

import core  # noqa: E402
from ml import pairs  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
    ap.add_argument("--out", default=os.path.join(MODELS, "embeddings-ft"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args(argv)

    from sentence_transformers import InputExample, SentenceTransformer, losses
    from torch.utils.data import DataLoader

    chunks = load_chunks()
    bm25 = core.BM25([core.tokenize(c["texte"]) for c in chunks])
    train = read_jsonl(os.path.join(DATA, "train.jsonl"))
    if not train:
        sys.exit("No training data: run make_pairs.py and split_data.py first.")
    triplets = pairs.build_triplets(train, chunks, bm25, random.Random(0))
    examples = [InputExample(texts=[t["question"], t["positive"], t["negatives"][0]]) for t in triplets]
    print(f"{len(examples)} training triplets from {len({t['article'] for t in triplets})} articles")

    model = SentenceTransformer(args.base)
    loader = DataLoader(examples, shuffle=True, batch_size=args.batch)
    loss = losses.MultipleNegativesRankingLoss(model)
    model.fit(train_objectives=[(loader, loss)], epochs=args.epochs, warmup_steps=max(1, int(0.1 * len(loader) * args.epochs)),
              output_path=args.out, show_progress_bar=True)
    print("✅ saved to", args.out)


if __name__ == "__main__":
    main()
