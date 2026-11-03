"""Metrics for the experiments (pure Python, unit-tested)."""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


def _norm(text):
    t = core.strip_accents((text or "").lower())
    t = re.sub(r"(?<=\d)[\s\u202f\u00a0](?=\d{3}(?!\d))", "", t)   # "1 311" -> "1311"
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)                          # "146,58" -> "146.58"
    return t


def fact_hit(answer, keys):
    """True if the answer contains at least one of the expected key facts.
    Numbers must match as whole numbers (79 does not match 1979 or 79.5)."""
    a = _norm(answer)
    for key in keys:
        k = _norm(key)
        if re.fullmatch(r"[\d.]+", k):
            if re.search(r"(?<![\d.])" + re.escape(k) + r"(?!\d|[.,]\d)", a):
                return True
        elif k in a:
            return True
    return False


def hit_at_k(titles, expected, k):
    return expected in titles[:k]


def reciprocal_rank(titles, expected):
    for i, t in enumerate(titles, 1):
        if t == expected:
            return 1.0 / i
    return 0.0


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def parse_note(text):
    m = re.search(r"NOTE\s*:\s*\**\s*(\d{1,2})", text or "", re.I)
    return int(m.group(1)) if m else None


def pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"
