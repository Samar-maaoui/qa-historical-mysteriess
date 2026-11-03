"""Step 3b. Fine-tune the cross-encoder reranker: each question with its right passage (1) and hard negatives (0).

    python training/finetune_reranker.py --epochs 2
Use it with RERANKER_MODEL=models/reranker-ft (then retrain the confidence model: its inputs change)."""


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
    ap.add_argument("--base", default="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    ap.add_argument("--out", default=os.path.join(MODELS, "reranker-ft"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--negatives", type=int, default=3)
    args = ap.parse_args(argv)

    from sentence_transformers import InputExample
    from sentence_transformers.cross_encoder import CrossEncoder
    from torch.utils.data import DataLoader

    chunks = load_chunks()
    bm25 = core.BM25([core.tokenize(c["texte"]) for c in chunks])
    train = read_jsonl(os.path.join(DATA, "train.jsonl"))
    if not train:
        sys.exit("No training data: run make_pairs.py and split_data.py first.")
    examples = []
    for t in pairs.build_triplets(train, chunks, bm25, random.Random(0), n_neg=args.negatives):
        examples.append(InputExample(texts=[t["question"], t["positive"]], label=1.0))
        examples += [InputExample(texts=[t["question"], n], label=0.0) for n in t["negatives"]]
    print(f"{len(examples)} training pairs")
    model = CrossEncoder(args.base, num_labels=1, max_length=384)
    loader = DataLoader(examples, shuffle=True, batch_size=16)
    model.fit(train_dataloader=loader, epochs=args.epochs, warmup_steps=max(1, int(0.1 * len(loader) * args.epochs)), output_path=args.out)
    print("✅ saved to", args.out)


if __name__ == "__main__":
    main()
