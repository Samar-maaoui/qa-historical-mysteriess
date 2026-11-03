"""Step 6b. Learn, from YOUR annotations, when to trust the NLI verdict (word overlap and number matching are added to its scores).

    python training/train_nli_calibrator.py
Prints how often the calibrated verdict agrees with you, compared with the raw 'entailment > 0.5' rule.
Writes models/nli_calibrator.json (used automatically by the faithfulness check)."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, MODELS  # noqa: E402

from ml import nli_cal  # noqa: E402


def read_labeled(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r.get("label", "").strip() in ("0", "1")]


def main(argv=None):
    path = os.path.join(DATA, "nli_to_label.csv")
    rows = read_labeled(path)
    labels = [int(r["label"]) for r in rows]
    if len(rows) < 40 or min(labels.count(0), labels.count(1)) < 10:
        sys.exit(f"{len(rows)} labelled rows ({labels.count(1)} supported, {labels.count(0)} not): label at least 40 rows with 10 of each kind in {path}.")
    import engine

    X = []
    for r in rows:
        probs, (ent, con) = engine._nli_probs([(r["passage"][:900], r["sentence"])])
        p = probs[0]
        X.append(nli_cal.features((float(p[ent]), float(p[con]), float(p[3 - ent - con])), r["sentence"], r["passage"]))
    model, report = nli_cal.NliCalibrator.train(X, labels)
    model.meta["nli"] = engine._nli["name"]
    model.save(os.path.join(MODELS, "nli_calibrator.json"))
    print(f"{report['n']} annotated sentences")
    print(f"agreement with you: raw rule {report['raw_threshold_accuracy']:.0%}  ->  calibrated {report['calibrated_accuracy']:.0%} (cross-validated)")
    print(f"AUC: raw {report['raw_auc']:.3f}  ->  calibrated {report['calibrated_auc']:.3f}")
    print("✅ saved models/nli_calibrator.json")


if __name__ == "__main__":
    main()
