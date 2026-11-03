"""Calibrated confidence: a small logistic model that turns retrieval signals into the probability that the
sources really contain the answer. It replaces the two hand-set distance thresholds (22 / 30)."""
import json
import os

import numpy as np

from ml.linear import SoftmaxRegression, Standardizer, brier, cross_val_proba, expected_calibration_error, reliability_table, roc_auc

FEATURES = ["mean_distance", "top1_distance", "distance_gap", "rerank_top1", "rerank_top3_mean", "agreement", "same_article_top3",
            "question_tokens", "p_off_topic"]


def features_from_retrieval(top10, passages, n_tokens, p_off_topic=0.0):
    d = [float(x) for x in top10] or [99.0]
    mean_d, top1 = sum(d) / len(d), d[0]
    rr = [p["rerank"] for p in passages if p.get("rerank") is not None]
    top5 = passages[:5]
    agree = (sum(1 for p in top5 if p.get("vec_rank") is not None and p.get("bm25_rank") is not None) / len(top5)) if top5 else 0.0
    top3 = [p["titre"] for p in passages[:3]]
    same = (max(top3.count(t) for t in top3) / len(top3)) if top3 else 0.0
    return [mean_d, top1, mean_d - top1, rr[0] if rr else 0.0, (sum(rr[:3]) / len(rr[:3])) if rr else 0.0,
            agree, same, float(n_tokens), float(p_off_topic)]


class CalibratedConfidence:
    def __init__(self, scaler, model, meta=None, bands=(0.4, 0.75)):
        self.scaler, self.model, self.meta, self.bands = scaler, model, meta or {}, tuple(bands)

    def p(self, feats):
        return float(self.model.predict_proba(self.scaler.transform([feats]))[0, 1])

    def label(self, p):
        return "High" if p >= self.bands[1] else "Medium" if p >= self.bands[0] else "Low"

    @classmethod
    def train(cls, X, y, meta=None, folds=5, seed=0, l2=1e-2):
        X, y = np.asarray(X, float), np.asarray(y, int)

        def fit_predict(Xtr, ytr, Xte):
            sc = Standardizer().fit(Xtr)
            m = SoftmaxRegression(2, l2=l2, lr=0.1, epochs=400, seed=seed).fit(sc.transform(Xtr), ytr)
            return m.predict_proba(sc.transform(Xte))[:, 1]

        oof = cross_val_proba(X, y, fit_predict, k=min(folds, max(2, int(min((y == 0).sum(), (y == 1).sum())))), seed=seed)
        scaler = Standardizer().fit(X)
        model = SoftmaxRegression(2, l2=l2, lr=0.1, epochs=400, seed=seed).fit(scaler.transform(X), y)
        report = {"n": int(len(y)), "base_rate": float(y.mean()), "auc": roc_auc(y, oof), "ece": expected_calibration_error(y, oof),
                  "brier": brier(y, oof), "reliability": reliability_table(y, oof)}
        meta = {**(meta or {}), "features": FEATURES, "cv_report": report}
        return cls(scaler, model, meta), report

    def to_dict(self):
        return {"scaler": self.scaler.to_dict(), "model": self.model.to_dict(), "meta": self.meta, "bands": list(self.bands)}

    @classmethod
    def from_dict(cls, d):
        return cls(Standardizer.from_dict(d["scaler"]), SoftmaxRegression.from_dict(d["model"]), d.get("meta"), d.get("bands", (0.4, 0.75)))

    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf8") as f:
            return cls.from_dict(json.load(f))
