"""Step 6a. Build the sheet to annotate by hand: sentences from real answers with the passage that best supports them.

    python training/label_nli.py --n 40         ->  training/data/nli_to_label.csv
Open it in Excel and fill the `label` column: 1 = the passage really supports the sentence, 0 = it does not (wrong number,
invented detail, over-generalisation...). Aim for 150 or more rows with both kinds. Then run train_nli_calibrator.py."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, ROOT  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="number of questions to answer")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args(argv)
    import time

    import engine
    import prompts

    with open(os.path.join(ROOT, "experiments", "questions_en.json"), encoding="utf8") as f:
        qs = [q["question"] for q in json.load(f) if q["type"] == "in_corpus" and not q.get("history")]
    random.Random(0).shuffle(qs)
    rows = []
    for q in qs[:args.n]:
        ret = engine.retrieve(q, engine.make_cfg("standard", {}))
        answer = engine.chat(prompts.standard(q, ret["passages"], []), 700, temperature=0)
        for d in engine.check_fidelity(answer, ret["passages"])["details"]:
            if d.get("heading") or d.get("meta") or not d.get("best"):
                continue
            passage = next(p for p in ret["passages"] if p["n"] == d["best"])
            rows.append({"question": q, "sentence": d["phrase"], "passage": passage["texte"][:900], "model_score": d["score"], "label": ""})
        time.sleep(args.pause)
    path = os.path.join(DATA, "nli_to_label.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["question", "sentence", "passage", "model_score", "label"])
        w.writeheader()
        w.writerows(rows)
    print(f"✅ {len(rows)} sentences written to {path}. Fill the `label` column (1 or 0), then run train_nli_calibrator.py")


if __name__ == "__main__":
    main()
