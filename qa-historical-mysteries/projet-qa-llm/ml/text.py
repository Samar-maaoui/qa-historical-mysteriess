import math
import re
from collections import Counter

import numpy as np

_WORD = re.compile(r"[a-z0-9']+")


def words(text):
    return _WORD.findall((text or "").lower())


def ngrams(text):
    """Unigrams and bigrams. Stop words are kept on purpose: for intent ('versus', 'why', 'when') they carry the signal."""
    w = words(text)
    return w + [f"{a}_{b}" for a, b in zip(w, w[1:])]


class Tfidf:
    def __init__(self, min_df=2, max_features=4000):
        self.min_df, self.max_features = min_df, max_features

    def fit(self, texts):
        df = Counter()
        for t in texts:
            df.update(set(ngrams(t)))
        keep = [t for t, c in df.most_common() if c >= self.min_df][:self.max_features]
        self.vocab = {t: i for i, t in enumerate(sorted(keep))}
        n = len(texts)
        self.idf = np.zeros(len(self.vocab))
        for t, i in self.vocab.items():
            self.idf[i] = math.log((1 + n) / (1 + df[t])) + 1
        return self

    def transform(self, texts):
        X = np.zeros((len(texts), len(self.vocab)))
        for r, t in enumerate(texts):
            for term, c in Counter(ngrams(t)).items():
                j = self.vocab.get(term)
                if j is not None:
                    X[r, j] = (1 + math.log(c)) * self.idf[j]
        norm = np.linalg.norm(X, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        return X / norm

    def to_dict(self):
        return {"vocab": self.vocab, "idf": self.idf.tolist()}

    @classmethod
    def from_dict(cls, d):
        t = cls()
        t.vocab, t.idf = d["vocab"], np.array(d["idf"], float)
        return t
