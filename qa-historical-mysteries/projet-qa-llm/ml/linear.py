"""Small, dependency-light ML toolkit (numpy only): standardisation, softmax regression, metrics, cross-validation."""
import math

import numpy as np


class Standardizer:
    def fit(self, X):
        X = np.asarray(X, float)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std < 1e-9] = 1.0
        return self

    def transform(self, X):
        return (np.asarray(X, float) - self.mean) / self.std

    def to_dict(self):
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.mean, s.std = np.array(d["mean"], float), np.array(d["std"], float)
        return s


def softmax(Z):
    Z = Z - Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(axis=1, keepdims=True)


class SoftmaxRegression:
    """Multinomial logistic regression trained with Adam (binary case: n_classes=2)."""

    def __init__(self, n_classes, l2=1e-3, lr=0.1, epochs=500, seed=0):
        self.K, self.l2, self.lr, self.epochs, self.seed = n_classes, l2, lr, epochs, seed

    def fit(self, X, y, sample_weight=None):
        X, y = np.asarray(X, float), np.asarray(y, int)
        n, d = X.shape
        rng = np.random.default_rng(self.seed)
        W, b = rng.normal(0, 0.01, (d, self.K)), np.zeros(self.K)
        Y = np.eye(self.K)[y]
        w = np.ones(n) if sample_weight is None else np.asarray(sample_weight, float)
        w = w / w.mean()
        mW, vW, mb, vb = np.zeros_like(W), np.zeros_like(W), np.zeros_like(b), np.zeros_like(b)
        b1, b2, eps = 0.9, 0.999, 1e-8
        for t in range(1, self.epochs + 1):
            G = (softmax(X @ W + b) - Y) * w[:, None] / n
            gW, gb = X.T @ G + self.l2 * W, G.sum(axis=0)
            mW, vW = b1 * mW + (1 - b1) * gW, b2 * vW + (1 - b2) * gW ** 2
            mb, vb = b1 * mb + (1 - b1) * gb, b2 * vb + (1 - b2) * gb ** 2
            W -= self.lr * (mW / (1 - b1 ** t)) / (np.sqrt(vW / (1 - b2 ** t)) + eps)
            b -= self.lr * (mb / (1 - b1 ** t)) / (np.sqrt(vb / (1 - b2 ** t)) + eps)
        self.W, self.b = W, b
        return self

    def predict_proba(self, X):
        return softmax(np.asarray(X, float) @ self.W + self.b)

    def predict(self, X):
        return self.predict_proba(X).argmax(axis=1)

    def to_dict(self):
        return {"K": self.K, "W": self.W.tolist(), "b": self.b.tolist()}

    @classmethod
    def from_dict(cls, d):
        m = cls(d["K"])
        m.W, m.b = np.array(d["W"], float), np.array(d["b"], float)
        return m


# ------------------------------------------------------------------ metrics
def roc_auc(y_true, scores):
    """Area under the ROC curve (rank based, ties averaged). None if one class is missing."""
    y, s = np.asarray(y_true, int), np.asarray(scores, float)
    pos, neg = int((y == 1).sum()), int((y == 0).sum())
    if pos == 0 or neg == 0:
        return None
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    i = 0
    sorted_s = s[order]
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def expected_calibration_error(y_true, p, bins=10):
    """Average gap between the predicted probability and the observed frequency, weighted by bin size."""
    y, p = np.asarray(y_true, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if mask.any():
            ece += mask.mean() * abs(y[mask].mean() - p[mask].mean())
    return float(ece)


def brier(y_true, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y_true, float)) ** 2))


def accuracy(y_true, y_pred):
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def stratified_kfold(y, k=5, seed=0):
    """Yields (train_idx, test_idx); every class is spread over the folds."""
    y = np.asarray(y, int)
    rng = np.random.default_rng(seed)
    folds = [[] for _ in range(k)]
    for cls in np.unique(y):
        idx = rng.permutation(np.where(y == cls)[0])
        for i, j in enumerate(idx):
            folds[i % k].append(int(j))
    for i in range(k):
        test = np.array(sorted(folds[i]), int)
        train = np.array(sorted(j for f in range(k) if f != i for j in folds[f]), int)
        yield train, test


def cross_val_proba(X, y, fit_predict, k=5, seed=0):
    """Out-of-fold probabilities of the positive class. fit_predict(Xtr, ytr, Xte) -> probabilities."""
    X, y = np.asarray(X, float), np.asarray(y, int)
    out = np.zeros(len(y))
    for tr, te in stratified_kfold(y, k, seed):
        out[te] = fit_predict(X[tr], y[tr], X[te])
    return out


def reliability_table(y_true, p, edges=(0.0, 0.4, 0.75, 1.0001), names=("Low", "Medium", "High")):
    """Observed success rate inside each confidence band: the 'when the system says High, it is right X% of the time' table."""
    y, p = np.asarray(y_true, float), np.asarray(p, float)
    rows = []
    for name, lo, hi in zip(names, edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi)
        rows.append({"band": name, "n": int(mask.sum()), "observed": float(y[mask].mean()) if mask.any() else None,
                     "mean_predicted": float(p[mask].mean()) if mask.any() else None})
    return rows


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))
