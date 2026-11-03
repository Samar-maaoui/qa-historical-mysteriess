"""Step 1. Synthetic (question, passage) pairs: the LLM writes questions that a passage answers.

    python training/make_pairs.py --per-article 15 --pause 1.0          # about 500 pairs, 10-20 minutes
It can be stopped and restarted: passages that already have questions are skipped."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, PAIR_PROMPT, groq, llm, load_chunks, read_jsonl  # noqa: E402

import core  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-article", type=int, default=15)
    ap.add_argument("--questions", type=int, default=2, help="questions per passage")
    ap.add_argument("--languages", default="English", help='e.g. "English" or "English,French"')
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    chunks = load_chunks()
    out_path = os.path.join(DATA, "pairs.jsonl")
    done = {r["chunk_id"] for r in read_jsonl(out_path)}
    rng = random.Random(args.seed)
    by_article = {}
    for c in chunks:
        if len(c["texte"]) > 350:
            by_article.setdefault(c["titre_article"], []).append(c)
    client = groq()
    langs = [l.strip() for l in args.languages.split(",") if l.strip()]
    n = 0
    with open(out_path, "a", encoding="utf8") as f:
        for article, items in by_article.items():
            rng.shuffle(items)
            for c in [x for x in items if x["id"] not in done][:args.per_article]:
                lang = langs[n % len(langs)]
                data = core.extract_json(llm(client, PAIR_PROMPT.format(n=args.questions, language=lang, title=article, text=c["texte"][:900])))
                if isinstance(data, list):
                    for q in [x for x in data if isinstance(x, str) and 10 < len(x) < 250][:args.questions]:
                        f.write(json.dumps({"question": q, "chunk_id": c["id"], "article": article, "language": lang}, ensure_ascii=False) + "\n")
                    f.flush()
                    n += 1
                time.sleep(args.pause)
            print(f"{article}: done")
    print(f"✅ pairs written to {out_path}")


if __name__ == "__main__":
    main()
