"""Calibrating the NLI verdict with your own annotations. Raw 'entailment > 0.5' is replaced by a small model that also
looks at word overlap and whether the numbers of the sentence appear in the passage (cheap, effective, and measurable)."""
import json
import os

import numpy as np

import core
from ml.linear import SoftmaxRegression, Standardizer, accuracy, cross_val_proba, roc_auc

FEATURES = ["entail", "contra", "neutral", "overlap", "number_match", "length_ratio"]


def features(probs, sentence, passage):
    """probs = (entailment, contradiction, neutral)."""
    s_tok, p_tok = set(core.tokenize(sentence)), set(core.tokenize(passage))
    overlap = len(s_tok & p_tok) / len(s_tok) if s_tok else 0.0
    nums = core.numbers_in(sentence)
    number_match = (len(nums & core.numbers_in(passage)) / len(nums)) if nums else 1.0
    return [float(probs[0]), float(probs[1]), float(probs[2]), overlap, number_match, min(2.0, len(sentence) / max(1, len(passage)))]


class NliCalibrator:
    def __init__(self, scaler, model, meta=None):
        self.scaler, self.model, self.meta = scaler, model, meta or {}

    def p(self, feats):
        return float(self.model.predict_proba(self.scaler.transform([feats]))[0, 1])

    @classmethod
    def train(cls, X, y, folds=5, seed=0, l2=1e-2):
        X, y = np.asarray(X, float), np.asarray(y, int)

        def fit_predict(Xtr, ytr, Xte):
            sc = Standardizer().fit(Xtr)
            return SoftmaxRegression(2, l2=l2, lr=0.1, epochs=400, seed=seed).fit(sc.transform(Xtr), ytr).predict_proba(sc.transform(Xte))[:, 1]

        oof = cross_val_proba(X, y, fit_predict, k=min(folds, max(2, int(min((y == 0).sum(), (y == 1).sum())))), seed=seed)
        scaler = Standardizer().fit(X)
        model = SoftmaxRegression(2, l2=l2, lr=0.1, epochs=400, seed=seed).fit(scaler.transform(X), y)
        report = {"n": int(len(y)), "calibrated_accuracy": accuracy(y, (oof >= 0.5).astype(int)), "calibrated_auc": roc_auc(y, oof),
                  "raw_threshold_accuracy": accuracy(y, (X[:, 0] > 0.5).astype(int)), "raw_auc": roc_auc(y, X[:, 0])}
        return cls(scaler, model, {"features": FEATURES, "cv_report": report}), report

    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            json.dump({"scaler": self.scaler.to_dict(), "model": self.model.to_dict(), "meta": self.meta}, f)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf8") as f:
            d = json.load(f)
        return cls(Standardizer.from_dict(d["scaler"]), SoftmaxRegression.from_dict(d["model"]), d.get("meta"))
