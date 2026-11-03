import random


def split_by_group(items, key, fractions=(0.7, 0.15, 0.15), seed=0):
    """Split so that every group (e.g. every article) lands in ONE split only: no leakage between train and test."""
    groups = sorted({key(x) for x in items})
    random.Random(seed).shuffle(groups)
    n = len(groups)
    n_train = max(1, round(n * fractions[0]))
    n_val = max(1, round(n * fractions[1])) if n >= 3 else 0
    where = {}
    for i, g in enumerate(groups):
        where[g] = "train" if i < n_train else "val" if i < n_train + n_val else "test"
    out = {"train": [], "val": [], "test": []}
    for x in items:
        out[where[key(x)]].append(x)
    return out


def assert_no_leak(splits, key):
    seen = {}
    for name, items in splits.items():
        for x in items:
            g = key(x)
            if g in seen and seen[g] != name:
                raise AssertionError(f"group {g!r} appears in both {seen[g]} and {name}")
            seen[g] = name
    return True
