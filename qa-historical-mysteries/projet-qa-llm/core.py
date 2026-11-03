"""Pure helpers (standard library only): hybrid search, citations, timeline,
study tools, games and child-safety checks. No model, database or network is
needed here, so everything in this file is unit-tested (tests/test_core.py)."""
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import timedelta

# ------------------------------------------------------------------ text normalisation
STOPWORDS = set("""
a an the of and or to in on at by for with from as is are was were be been being it its this that these those
who whom whose what which when where why how do does did can could should would will shall may might must
i you he she we they me him her us them my your his their our not no yes if then than so such into about over
under between during after before also very more most many much any some each other
le la les un une des du de d l et ou à au aux en dans sur par pour avec sans sous est sont était étaient être
a eu ce cet cette ces qui que quoi dont où comment pourquoi quand il elle ils elles nous vous je tu mon ma mes
son sa ses leur leurs ne pas plus très aussi
""".split())


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def tokenize(text):
    """Lower-case, accent-free word tokens without stop words (keeps numbers)."""
    text = strip_accents((text or "").lower())
    return [t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 1 and t not in STOPWORDS]


# ------------------------------------------------------------------ BM25 and rank fusion
class BM25:
    """Small BM25 index (Okapi) over pre-tokenised documents."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avg = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.post = defaultdict(list)
        for i, d in enumerate(docs):
            for term, tf in Counter(d).items():
                self.post[term].append((i, tf))
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def scores(self, q_tokens):
        acc = defaultdict(float)
        for t in set(q_tokens):
            plist = self.post.get(t)
            if not plist:
                continue
            idf = self.idf[t]
            for i, tf in plist:
                norm = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / (self.avg or 1.0))
                acc[i] += idf * tf * (self.k1 + 1) / norm
        return acc

    def top(self, q_tokens, k=30):
        sc = self.scores(q_tokens)
        return sorted(sc.items(), key=lambda x: x[1], reverse=True)[:k]


def rrf_fuse(rankings, k=60, weights=None):
    """Reciprocal Rank Fusion. rankings: list of lists of ids (best first).
    Returns [(id, score)] best first."""
    weights = weights or [1.0] * len(rankings)
    score = defaultdict(float)
    for w, ranking in zip(weights, rankings):
        for rank, item in enumerate(ranking):
            score[item] += w / (k + rank + 1)
    return sorted(score.items(), key=lambda x: x[1], reverse=True)


def build_title_index(topics):
    """topics: {french_title: english_name}. Returns entries used to expand queries
    with the French article title when the question names a topic in English."""
    entries = []
    token_owner = Counter()
    for fr, en in topics.items():
        toks = set(tokenize(en)) | set(tokenize(fr))
        entries.append((fr, en, toks))
        for t in toks:
            token_owner[t] += 1
    out = []
    for fr, en, toks in entries:
        distinctive = {t for t in toks if token_owner[t] == 1 and len(t) > 3}
        out.append((fr, en, distinctive))
    return out


def expand_query(question, title_index):
    """French titles of the topics that the question seems to mention."""
    q_low = strip_accents(question.lower())
    q_tokens = set(tokenize(question))
    found = []
    for fr, en, distinctive in title_index:
        if strip_accents(en.lower()) in q_low or strip_accents(fr.lower()) in q_low or (distinctive & q_tokens):
            found.append(fr)
    return found


def diversify(items, top_n, per_group=3, key=lambda x: x):
    """Keep the order but allow at most `per_group` items per group (e.g. per article)."""
    count, out = Counter(), []
    for it in items:
        g = key(it)
        if count[g] >= per_group:
            continue
        count[g] += 1
        out.append(it)
        if len(out) >= top_n:
            break
    return out


def contextual_query(text, history, title_index):
    """Short follow-up questions ("and his wars?") borrow the previous question for retrieval,
    unless they already name a known topic."""
    if history and len(tokenize(text)) <= 4 and not expand_query(text, title_index):
        return (history[-1].get("question", "") + " " + text).strip()
    return text


# ------------------------------------------------------------------ citations and sentences
CITE_GROUP = re.compile(r"\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]")


def extract_citations(text):
    nums = []
    for m in CITE_GROUP.finditer(text or ""):
        nums += [int(x) for x in re.findall(r"\d+", m.group(1))]
    return nums


def strip_citations(text):
    return re.sub(r"\s*" + CITE_GROUP.pattern, "", text or "")


def keep_valid_citations(text, n):
    """Remove citation numbers that do not exist among the n passages."""
    def fix(m):
        keep = [x for x in re.findall(r"\d+", m.group(1)) if 1 <= int(x) <= n]
        return "" if not keep else "[" + ", ".join(keep) + "]"
    out = CITE_GROUP.sub(fix, text or "")
    return re.sub(r"[ \t]+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", out))


def used_citations(text, n):
    return sorted({c for c in extract_citations(text) if 1 <= c <= n})


def _plain(line):
    line = re.sub(r"^\s*(#{1,6}\s*|[-*•]\s+|\d+[.)]\s+)", "", line)
    return re.sub(r"[*_`]+", "", line).strip()


def is_heading_line(line):
    raw = line.strip()
    if not raw:
        return False
    if raw.startswith("#"):
        return True
    if re.match(r"^\s*([-*•]|\d+[.)])\s+", raw):
        return False
    plain = _plain(raw)
    words = len(plain.split())
    if re.fullmatch(r"\*\*[^*]+\*\*:?", raw) and words <= 10:
        return True
    if plain.endswith(":") and words <= 10:
        return True
    if words <= 6 and not re.search(r"[.!?)\"”»\]]$", plain):
        return True
    return False


META_HEADING = re.compile(r"\b(limits?|limitations?|open questions?|caveats?)\b", re.I)


def split_sentences(text):
    """Split an answer into sentences. Returns [{"text", "heading", "meta", "cites"}].
    `meta` marks commentary under a "Limits / open questions" heading: it talks about the
    sources instead of stating facts, so it is displayed but never scored."""
    out = []
    meta_section = False
    for line in (text or "").replace("\r", "").split("\n"):
        raw = line.strip()
        if not raw:
            continue
        heading = is_heading_line(raw)
        clean = _plain(raw)
        # move citations that follow the full stop in front of it:  "... 247 BC. [1]" -> "... 247 BC [1]."
        clean = re.sub(r"([.!?])\s*((?:\[\d{1,2}(?:\s*[,;]\s*\d{1,2})*\]\s*)+)", lambda m: " " + m.group(2).strip() + m.group(1) + " ", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        if heading:
            meta_section = bool(META_HEADING.search(clean))
            if clean:
                out.append({"text": clean, "heading": True, "meta": False, "cites": extract_citations(clean)})
            continue
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])", clean):
            part = part.strip()
            if len(strip_citations(part)) >= 3:
                out.append({"text": part, "heading": False, "meta": meta_section, "cites": extract_citations(part)})
    return out


# ------------------------------------------------------------------ LLM output helpers
def extract_json(text):
    """Parse the first JSON object/array found in an LLM answer (fences allowed)."""
    if not text:
        return None
    t = text.strip().replace("```json", "").replace("```", "").strip()
    pairs = [("{", "}"), ("[", "]")]
    pairs.sort(key=lambda p: t.find(p[0]) if t.find(p[0]) != -1 else 10 ** 9)  # whichever opens first
    for opener, closer in pairs:
        a, b = t.find(opener), t.rfind(closer)
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                continue
    return None


REFUSAL_PATTERNS = [
    r"\bi (do not|don't|dont|cannot|can't|could not|couldn't) (really )?(know|answer|find|say)\b",
    r"\bnot (mentioned|provided|covered|stated|specified|available|included) in (the |these )?(context|passages?|sources?|text)",
    r"\b(context|passages?|sources?|text) (do(es)? not|don't|doesn't|did not) (contain|mention|provide|include|say|cover|specify)",
    r"\bno (information|mention|details?|data) (is |are )?(available |provided |given )?(about|on|regarding|for|in)\b",
    r"\bi'?m not sure\b",
    r"\bdon'?t know that one\b",
    r"\bunable to (find|answer)\b",
]


def is_refusal(text):
    t = (text or "").lower()
    return any(re.search(p, t) for p in REFUSAL_PATTERNS)


# ------------------------------------------------------------------ years and timelines
def parse_year(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if not isinstance(v, str):
        return None
    m = re.match(r"^\s*(?:c\.|ca\.?|circa|about|around|~)?\s*(-?\d{1,5})\s*(BCE|BC|B\.C\.E?\.?|CE|AD|A\.D\.)?\b", v.strip(), re.I)
    if not m:
        return None
    y = int(m.group(1))
    era = (m.group(2) or "").upper().replace(".", "")
    if era in ("BC", "BCE") and y > 0:
        y = -y
    return y


def format_year(y):
    if y < 0:
        return f"{-y} BC"
    if y < 1000:
        return f"{y} AD"
    return str(y)


def clean_events(raw, n_passages=0, max_events=10):
    """Validate the LLM timeline: [{year, label, source}] -> sorted, de-duplicated list."""
    if isinstance(raw, dict):
        raw = raw.get("events") or raw.get("timeline") or []
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for e in raw:
        if not isinstance(e, dict):
            continue
        y = parse_year(e.get("year"))
        label = strip_citations(str(e.get("label") or e.get("event") or "")).strip()
        if y is None or not label or abs(y) > 20000:
            continue
        src = e.get("source")
        src = src if isinstance(src, int) and 1 <= src <= n_passages else None
        key = (y, label.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"year": y, "year_label": format_year(y), "label": label, "source": src})
    out.sort(key=lambda x: x["year"])
    return out[:max_events]


# ------------------------------------------------------------------ geography and games
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def stars_for_distance(km):
    """Kids always get at least one star for trying."""
    if km <= 250:
        return 3
    if km <= 1500:
        return 2
    return 1


def hot_or_cold(km):
    if km <= 250:
        return "🔥 Boiling hot! You found it!"
    if km <= 1500:
        return "😎 Warm! You are close."
    if km <= 4000:
        return "🌤️ A bit far. Try the next one!"
    return "🧊 Brrr, very far away! Let's try again."


def clue_leaks(clue, names):
    """True if the riddle contains a distinctive word of the place's name."""
    clue_t = set(tokenize(clue))
    for name in names:
        for t in tokenize(name):
            if len(t) > 3 and t in clue_t:
                return True
    return False


# ------------------------------------------------------------------ study tools
LEITNER_DAYS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}


def next_box(box, correct):
    box = max(1, min(5, int(box or 1)))
    return min(5, box + 1) if correct else 1


def due_date(now, box):
    return now + timedelta(days=LEITNER_DAYS[max(1, min(5, int(box)))])


def update_streak(streak, best, correct):
    streak = (streak + 1) if correct else 0
    return streak, max(best, streak)


BADGES = {
    "first_question": {"name": "First Question", "emoji": "❓", "desc": "Ask your first question"},
    "curious_cat": {"name": "Curious Explorer", "emoji": "🧭", "desc": "Ask 10 questions"},
    "quiz_rookie": {"name": "Quiz Rookie", "emoji": "🎯", "desc": "Get 5 quiz answers right"},
    "quiz_champion": {"name": "Quiz Champion", "emoji": "🏆", "desc": "Get 25 quiz answers right"},
    "streak_5": {"name": "On Fire!", "emoji": "🔥", "desc": "Answer 5 quiz questions in a row"},
    "star_collector": {"name": "Star Collector", "emoji": "⭐", "desc": "Collect 20 stars"},
    "map_explorer": {"name": "Map Explorer", "emoji": "🗺️", "desc": "Play 5 treasure-map rounds"},
    "story_lover": {"name": "Story Lover", "emoji": "📖", "desc": "Listen to 3 stories"},
}


def award_badges(stats):
    g = lambda k: int(stats.get(k) or 0)
    rules = {
        "first_question": g("questions") >= 1,
        "curious_cat": g("questions") >= 10,
        "quiz_rookie": g("quiz_correct") >= 5,
        "quiz_champion": g("quiz_correct") >= 25,
        "streak_5": g("best_streak") >= 5,
        "star_collector": g("stars") >= 20,
        "map_explorer": g("games") >= 5,
        "story_lover": g("stories") >= 3,
    }
    return [b for b, ok in rules.items() if ok]


# ------------------------------------------------------------------ child safety
_UNSAFE = [
    "porn", "porno", "pornography", "sexual", "sexy", "erotic", "rape", "suicide", "kill myself", "self harm",
    "cocaine", "heroin", "meth", "how to make a bomb", "how to build a bomb", "how to make a weapon",
]
KID_SAFE_REPLY = ("Oops! 🙈 That is not something I can talk about. I love stories about pyramids, "
                  "elephants, treasure and brave explorers. Want to ask me about one of them?")


def kid_unsafe(text):
    t = " " + re.sub(r"[^a-z0-9' ]+", " ", (text or "").lower()) + " "
    return any(f" {w} " in t for w in _UNSAFE)


# ------------------------------------------------------------------ misc
def nettoyer(texte):
    """Markdown/citation-free text for text-to-speech."""
    t = strip_citations(texte or "")
    t = re.sub(r"[*_`#]", "", t)
    t = re.sub(r"(?m)^\s*[-•]\s+", "", t)
    return t.strip()


def truncate(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def softmax_rows(rows):
    out = []
    for r in rows:
        m = max(r)
        e = [math.exp(x - m) for x in r]
        s = sum(e)
        out.append([x / s for x in e])
    return out


# ------------------------------------------------------------------ dates found in a text (to check generated timelines)
_BC = re.compile(r"(?<![\d.,])(\d{1,4})(?![\d]|[.,]\d)\s*(?:av\.?\s*J\.?-?C\.?|avant\s+J[ée]sus-Christ|B\.?C\.?E?\.?)", re.I)
_AD = re.compile(r"(?:\b(?:AD|A\.D\.|CE)\s*|\b(?:apr[eè]s|apr\.)\s+J\.?-?C\.?\s*|\b(?:l['’]\s*an|in the year|en l['’]an|year)\s+)(\d{1,4})(?![\d]|[.,]\d)", re.I)
_AD_AFTER = re.compile(r"(?<![\d.,])(\d{1,4})(?![\d]|[.,]\d)\s*(?:AD|A\.D\.|CE|apr[eè]s J\.?-?C\.?|de notre [eè]re)\b", re.I)
_PLAIN = re.compile(r"(?<![\d.,])(1\d{3}|20\d{2}|[5-9]\d{2})(?![\d]|[.,]\d)")


def years_in_text(text):
    """Years mentioned in a passage: negative for BC. Used to check that a generated date really appears in the sources."""
    text = text or ""
    years = {-int(m.group(1)) for m in _BC.finditer(text)}
    years |= {int(m.group(1)) for m in _AD.finditer(text)}
    years |= {int(m.group(1)) for m in _AD_AFTER.finditer(text)}
    bc_spans = [m.span(1) for m in _BC.finditer(text)]
    for m in _PLAIN.finditer(text):
        if m.span(1) not in bc_spans:
            years.add(int(m.group(1)))
    return years


def year_in_texts(year, texts, tolerance=0):
    found = set()
    for t in texts:
        found |= years_in_text(t)
    return any(abs(y - year) <= tolerance for y in found)


def numbers_in(text):
    """Numbers of a text, normalised (146,58 -> 146.58; 1 311 -> 1311)."""
    t = re.sub(r"(?<=\d)[\s\u202f\u00a0](?=\d{3}(?!\d))", "", text or "")
    return {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", t)}


# ------------------------------------------------------------------ sections of a plain-text article
def section_offsets(text):
    """[(offset, heading)] for lines that look like section titles: short, no final punctuation, after a blank line."""
    lines = (text or "").split("\n")
    out, pos = [], 0
    for i, line in enumerate(lines):
        s = line.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        prev_blank = i == 0 or not lines[i - 1].strip()
        if (s and prev_blank and nxt and len(s) <= 70 and len(s.split()) <= 9 and not re.search(r"[.!?:;,)]$", s)
                and len(nxt) > len(s)):
            out.append((pos, s))
        pos += len(line) + 1
    return out


def section_at(offsets, pos):
    heading = ""
    for off, h in offsets:
        if off <= pos:
            heading = h
        else:
            break
    return heading


# ------------------------------------------------------------------ citation quality
def citation_precision(details):
    """Share of cited statements whose cited passage is the one that supports them best (None if nothing is cited)."""
    cited = [d for d in details if d.get("cited") and d.get("cite_ok") is not None]
    if not cited:
        return None
    return sum(1 for d in cited if d["cite_ok"]) / len(cited)


def citation_fixes(details):
    """(sentence, cited, best passage) for every statement cited with a passage that does not support it."""
    return [(d["phrase"], d["cited"], d["best"]) for d in details
            if d.get("cited") and d.get("cite_ok") is False and d.get("best") and d.get("soutenue")]


# ------------------------------------------------------------------ protection against abuse and runaway API costs
class RateLimiter:
    """Sliding window: at most `limit` calls per `window` seconds for each key (0 = no limit)."""

    def __init__(self, limit, window=60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = int(limit), float(window), clock
        self.hits = defaultdict(deque)

    def allow(self, key):
        if self.limit <= 0:
            return True
        now, q = self.clock(), self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def exhausted(self, key):
        """True when the key has used its whole budget (does not record anything)."""
        if self.limit <= 0:
            return False
        now, q = self.clock(), self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        return len(q) >= self.limit

    def reset(self, key):
        self.hits.pop(key, None)

    def retry_after(self, key):
        q = self.hits.get(key)
        return max(0.0, self.window - (self.clock() - q[0])) if q else 0.0


# ------------------------------------------------------------------ accounts: names
def clean_name(name):
    n = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f<>]", " ", name or "")).strip()
    return n if 2 <= len(n) <= 60 else None
