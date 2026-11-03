"""Step 5. Train the calibrated confidence model (replaces the hand-set distance thresholds).

    python training/train_confidence.py                                   # label: the right article was retrieved
    python training/train_confidence.py --answers experiments/results/results.json   # label: the answer contained the expected fact

Uses the verified question set (43 in-corpus + 14 out-of-corpus), the unanswerable list, and the VALIDATION and TEST pairs only:
the training pairs are left out because a fine-tuned retriever has seen them, which would inflate the numbers.
Writes models/confidence.json together with the cross-validated report (AUC, calibration error, reliability table)."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, MODELS, ROOT, read_jsonl  # noqa: E402

import core  # noqa: E402
from ml.confidence import CalibratedConfidence, features_from_retrieval  # noqa: E402


def load_items(answers_path=None):
    with open(os.path.join(ROOT, "experiments", "questions_en.json"), encoding="utf8") as f:
        items = [q for q in json.load(f) if not q.get("history")]
    if answers_path:
        with open(answers_path, encoding="utf8") as f:
            rows = {r["question"]: r for r in json.load(f)["results"]["rag_full"]}
        items = [{**q, "answered": bool(rows[q["question"]].get("fact_hit"))} for q in items if q["question"] in rows and q["type"] != "false_premise"]
    else:
        for path in ("val.jsonl", "test.jsonl"):
            items += [{"question": r["question"], "source": r["article"], "type": "in_corpus"} for r in read_jsonl(os.path.join(DATA, path))]
    path = os.path.join(DATA, "unanswerable.txt")
    if os.path.exists(path):
        with open(path, encoding="utf8") as f:
            items += [{"question": line.strip(), "source": None, "type": "out_of_corpus"} for line in f if line.strip()]
    seen, out = set(), []
    for it in items:
        if it["question"] not in seen:
            seen.add(it["question"])
            out.append(it)
    return out


def collect(engine, items):
    X, y = [], []
    for it in items:
        ret = engine.retrieve(it["question"], engine.make_cfg("standard", {}))
        feats = features_from_retrieval(ret["top10"], ret["passages"], len(core.tokenize(it["question"])), engine.intent_router.p_off_topic(it["question"]))
        titles = [p["titre"] for p in ret["passages"]]
        if "answered" in it:
            label = 1 if it["type"] == "in_corpus" and it["answered"] else 0
        else:
            label = 1 if it.get("source") and it["source"] in titles else 0
        X.append(feats)
        y.append(label)
    return X, y


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", help="experiments/results/results.json: use answer correctness as the label")
    args = ap.parse_args(argv)
    import engine

    items = load_items(args.answers)
    print(f"{len(items)} questions")
    X, y = collect(engine, items)
    if min(y.count(0), y.count(1)) < 8:
        sys.exit(f"Not enough examples of both kinds (answerable: {y.count(1)}, not answerable: {y.count(0)}). Create the pairs first (make_pairs.py, split_data.py).")
    model, report = CalibratedConfidence.train(X, y, meta={"embedding": engine.EMBED_MODEL, "reranker": engine.reranker_name,
                                                          "label": "answered" if args.answers else "evidence_found"})
    model.save(os.path.join(MODELS, "confidence.json"))
    print(f"\nAUC {report['auc']:.3f} | calibration error (ECE) {report['ece']:.3f} | Brier {report['brier']:.3f} | base rate {report['base_rate']:.0%}")
    print("\n| Confidence shown | questions | really answerable |\n|---|---|---|")
    for r in report["reliability"][::-1]:
        print(f"| {r['band']} | {r['n']} | {'n/a' if r['observed'] is None else format(r['observed'], '.0%')} |")
    print("\n✅ saved models/confidence.json (restart the API to use it; retrain whenever the embedding or reranker model changes)")


if __name__ == "__main__":
    main()
