import numpy as np


def kmeans(X, k, seed=0, iters=50):
    """Plain k-means (k-means++ start). Returns (labels, centers)."""
    X = np.asarray(X, float)
    rng = np.random.default_rng(seed)
    centers = [X[rng.integers(len(X))]]
    for _ in range(1, k):
        d2 = np.min([((X - c) ** 2).sum(axis=1) for c in centers], axis=0)
        total = d2.sum()
        centers.append(X[rng.choice(len(X), p=d2 / total)] if total > 0 else X[rng.integers(len(X))])
    centers = np.array(centers)
    labels = np.zeros(len(X), int)
    for _ in range(iters):
        dist = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new = dist.argmin(axis=1)
        if (new == labels).all() and _ > 0:
            break
        labels = new
        for j in range(k):
            if (labels == j).any():
                centers[j] = X[labels == j].mean(axis=0)
    return labels, centers


def pca2(X):
    """Project to 2 dimensions (for the corpus map)."""
    X = np.asarray(X, float)
    Xc = X - X.mean(axis=0)
    _, _, vt = np.linalg.svd(Xc, full_matrices=False)
    return Xc @ vt[:2].T
