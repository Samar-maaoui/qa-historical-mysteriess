"""Engine: loads the resources once and exposes the RAG building blocks used by api.py
(retrieval, generation, faithfulness, quiz, kids content). No HTTP code lives here."""
import json
import os
import random
import re
import time
from datetime import datetime

import faiss
import mysql.connector
import numpy as np
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import CrossEncoder, SentenceTransformer

import core
import logging_setup
import prompts
from ml.confidence import CalibratedConfidence, features_from_retrieval
from ml.intent import IntentRouter
from ml.nli_cal import NliCalibrator, features as nli_features
from sites_data import meta, nom_en
from store import Store

load_dotenv()

# ------------------------------------------------------------------ configuration
SEUIL_ELEVE = float(os.getenv("SEUIL_ELEVE", 22))
SEUIL_MOYEN = float(os.getenv("SEUIL_MOYEN", 30))
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")          # e.g. a non-reasoning model, used only if the main one keeps returning nothing
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")    # "low" | "medium" | "high" | "off": how much a reasoning model may think before writing
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
RERANKER_NAMES = [os.getenv("RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"), "cross-encoder/ms-marco-MiniLM-L-6-v2"]
NLI_NAMES = [os.getenv("NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"), "cross-encoder/nli-deberta-v3-small"]
TRANSLATE_QUERIES = os.getenv("TRANSLATE_QUERIES", "1") == "1"
STRICT_THRESHOLD = float(os.getenv("STRICT_THRESHOLD", 0.7))
DB_CFG = {"host": os.getenv("DB_HOST", "localhost"), "user": os.getenv("DB_USER", "root"),
          "password": os.getenv("DB_PASSWORD", ""), "database": os.getenv("DB_NAME", "llm")}
if os.getenv("DB_PORT"):
    DB_CFG["port"] = int(os.getenv("DB_PORT"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(BASE_DIR, "models"))
ABSTAIN_P = float(os.getenv("ABSTAIN_P", 0))   # 0 = never refuse before generating; e.g. 0.15 = refuse when the calibrated probability is below 15%
NOMS_LANGUES = {"en": "English", "fr": "French", "ar": "Arabic", "es": "Spanish"}
MODES = {
    "standard": {"max_tokens": 900, "top_n": 6, "builder": prompts.standard, "cite": True, "temperature": 0, "effort": "low"},
    "kids": {"max_tokens": 700, "top_n": 4, "builder": prompts.kids, "cite": False, "temperature": 0.3, "effort": "low"},
    "researcher": {"max_tokens": 1500, "top_n": 8, "builder": prompts.researcher, "cite": True, "temperature": 0, "effort": "medium"},
}


def connect_db():
    return mysql.connector.connect(**DB_CFG)


# ------------------------------------------------------------------ resources
print("Loading resources...")
_conn = connect_db()
_cur = _conn.cursor(dictionary=True)
_cur.execute("SELECT * FROM chunks ORDER BY position")
chunks = _cur.fetchall()
_cur.close()
_conn.close()
for _c in chunks:
    _c["lang"] = _c.get("lang") or "fr"
    _c["section"] = _c.get("section") or ""
    _c["source_type"] = _c.get("source_type") or ("Wikipedia (EN)" if _c["lang"] == "en" else "Wikipedia (FR)")

sujets = list(dict.fromkeys(c["titre_article"] for c in chunks))
source_types = sorted({c["source_type"] for c in chunks})

index = faiss.read_index("index.faiss")
if index.ntotal != len(chunks):
    print(f"WARNING: the FAISS index has {index.ntotal} vectors but the database has {len(chunks)} chunks. "
          "Run build_index.py then init_db.py again, otherwise some passages will not match their text.")
try:
    with open("index_meta.json", encoding="utf8") as _f:
        _imeta = json.load(_f)
    if _imeta.get("embedding") != EMBED_MODEL:
        print(f"WARNING: the index was built with '{_imeta.get('embedding')}' but EMBED_MODEL is '{EMBED_MODEL}'. "
              "Questions and passages must use the SAME model: rebuild with build_index.py or fix EMBED_MODEL.")
except FileNotFoundError:
    pass
model = SentenceTransformer(EMBED_MODEL)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
store = Store(connect_db)
try:
    store.ensure_tables()
except Exception as e:  # the API still answers questions without the extra tables
    print("WARNING: could not create the extra tables:", repr(e))


def _load_cross_encoder(names, label):
    for name in names:
        if not name:
            continue
        try:
            m = CrossEncoder(name)
            print(f"{label}: {name}")
            return m, name
        except Exception as e:
            print(f"{label}: {name} unavailable ({e!r}), trying the next one")
    raise RuntimeError(f"No {label} model could be loaded")


reranker, reranker_name = _load_cross_encoder(RERANKER_NAMES, "Reranker")
_nli = {"model": None, "name": None}  # loaded on first faithfulness check
_cal = {"loaded": False, "model": None}  # NLI calibrator, loaded together with the NLI model

# learned components (all optional: the system works without them)
intent_router = IntentRouter.load(os.path.join(MODEL_DIR, "intent.json"))
conf_model = None
_cpath = os.path.join(MODEL_DIR, "confidence.json")
if os.path.exists(_cpath):
    try:
        _cm = CalibratedConfidence.load(_cpath)
        if _cm.meta.get("embedding") == EMBED_MODEL and _cm.meta.get("reranker") == reranker_name:
            conf_model = _cm
            print("Calibrated confidence model loaded.")
        else:
            print(f"WARNING: models/confidence.json was trained with other models ({_cm.meta.get('embedding')}, {_cm.meta.get('reranker')}); "
                  "ignored. Retrain it with training/train_confidence.py.")
    except Exception as _e:
        print("WARNING: could not load models/confidence.json:", repr(_e))
facts = {}
try:
    with open("wikidata.json", encoding="utf8") as _f:
        facts = json.load(_f)
except FileNotFoundError:
    pass

# keyword index (BM25) and helpers for query expansion
chunks_by_title = {}
for _i, _c in enumerate(chunks):
    chunks_by_title.setdefault(_c["titre_article"], []).append(_i)
bm25 = core.BM25([core.tokenize(c["texte"] + " " + c["titre_article"] + " " + nom_en(c["titre_article"]) + " " + c["section"]) for c in chunks])
title_index = core.build_title_index({t: nom_en(t) for t in sujets})
_kid_pool = [i for i, c in enumerate(chunks) if not meta(c["titre_article"])["sensitive"] and len(c["texte"]) > 350]
print(f"Ready: {len(chunks)} chunks, {len(sujets)} topics, source types: {', '.join(source_types)}.")


# ------------------------------------------------------------------ LLM helpers
_effort_ok = {}   # model -> False once the API refused the reasoning_effort parameter for it


def _create(model, effort=None, **kw):
    """One API call. A reasoning model is asked to think briefly (otherwise it can use its whole budget thinking and
    return an empty answer); if the API or the SDK does not know the parameter, we stop sending it for that model."""
    effort = effort or LLM_REASONING_EFFORT
    if effort and effort != "off" and _effort_ok.get(model, True):
        try:
            return client.chat.completions.create(model=model, reasoning_effort=effort, **kw)
        except TypeError:
            _effort_ok[model] = False
        except Exception as ex:
            if "reasoning" not in str(ex).lower():
                raise
            _effort_ok[model] = False
    return client.chat.completions.create(model=model, **kw)


def chat(prompt, max_tokens=700, retries=2, temperature=None, effort=None):
    """One completion. If the answer comes back empty, retry with a bigger budget, then with the fallback model (if any).
    Every empty answer is logged with its finish_reason so that the cause is visible in the terminal."""
    extra = {} if temperature is None else {"temperature": temperature}
    messages = [{"role": "user", "content": prompt}]
    for model in [LLM_MODEL] + ([LLM_FALLBACK_MODEL] if LLM_FALLBACK_MODEL else []):
        tokens = max_tokens
        for _ in range(retries + 1):
            r = _create(model, effort, max_tokens=tokens, messages=messages, **extra)
            choice = r.choices[0]
            text = (choice.message.content or "").strip()
            if text:
                return text
            logging_setup.log_event("llm_empty", model=model, finish_reason=getattr(choice, "finish_reason", None), max_tokens=tokens,
                                    completion_tokens=getattr(getattr(r, "usage", None), "completion_tokens", None))
            tokens = min(tokens * 2, 3000)
    return ""


def chat_stream(prompt, max_tokens=700, temperature=None, effort=None):
    extra = {} if temperature is None else {"temperature": temperature}
    stream = _create(LLM_MODEL, effort, max_tokens=max_tokens, stream=True, messages=[{"role": "user", "content": prompt}], **extra)
    for part in stream:
        try:
            delta = part.choices[0].delta.content
        except Exception:
            delta = None
        if delta:
            yield delta


def translate_text(texte, langue, source="auto"):
    try:
        res = GoogleTranslator(source=source, target=langue).translate(texte)
        if res:
            return res, "google"
    except Exception as e:
        print("deep-translator error:", repr(e))
    return chat(prompts.translate(texte, NOMS_LANGUES[langue]), 2000), "llm"


# ------------------------------------------------------------------ retrieval
_fr_cache = {}


def question_in_french(q):
    if not TRANSLATE_QUERIES:
        return ""
    if q in _fr_cache:
        return _fr_cache[q]
    try:
        out = GoogleTranslator(source="auto", target="fr").translate(q) or ""
    except Exception:
        out = ""
    if len(_fr_cache) > 500:
        _fr_cache.clear()
    _fr_cache[q] = out
    return out


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def make_cfg(mode, opts=None):
    opts = opts or {}
    base = MODES.get(mode, MODES["standard"])
    top_n = _clamp(opts.get("top_n") or base["top_n"], 2, 12)
    cfg = {
        "retrieval": opts.get("retrieval") if opts.get("retrieval") in ("hybrid", "vector") else "hybrid",
        "top_n": top_n,
        "k": _clamp(opts.get("k") or 20, top_n, 40),
        "rerank": opts.get("rerank", True) is not False,
        "topics": [t for t in (opts.get("topics") or []) if t in chunks_by_title][:40],
        "source_types": [s for s in (opts.get("source_types") or []) if s in source_types][:5],
        "strict": bool(opts.get("strict")) and mode == "researcher",
    }
    if mode == "kids":  # kids always get the simple, safe configuration
        cfg.update(retrieval="hybrid", rerank=True, topics=[], source_types=[], strict=False)
    return cfg


def confidence(distances):
    d = float(np.mean(distances)) if len(distances) else 99.0
    if d < SEUIL_ELEVE:
        return "High", 0.9, d
    if d < SEUIL_MOYEN:
        return "Medium", 0.6, d
    return "Low", 0.25, d


_ANAPHORA = re.compile(r"\b(he|she|it|they|him|her|his|hers|its|their|theirs|them|that|this|those|these|there|then)\b", re.I)
_rw_cache = {}


def rewrite_query(question, history):
    """Follow-up questions ("and what about his wars?") become standalone before the search."""
    if not history:
        return question
    if core.expand_query(question, title_index) and not _ANAPHORA.search(question):
        return question  # it already names its topic
    if len(core.tokenize(question)) > 5 and not _ANAPHORA.search(question):
        return question
    key = (question, history[-1]["question"])
    if key not in _rw_cache:
        try:
            out = chat(prompts.rewrite(question, history), 120, temperature=0).strip().split("\n")[0].strip(" \"'")
        except Exception:
            out = ""
        _rw_cache[key] = out if 3 <= len(out) <= 300 else core.contextual_query(question, history, title_index)
        if len(_rw_cache) > 300:
            _rw_cache.clear()
    return _rw_cache[key]


def assess(question, ret):
    """Confidence of the retrieval: the distance bands, and the calibrated probability when a model is available."""
    label, score, dist = confidence(ret["top10"])
    intent = intent_router.predict(question)
    out = {"label": label, "score": score, "distance": dist, "p_answerable": None, "calibrated": False, "intent": intent}
    if conf_model is not None:
        feats = features_from_retrieval(ret["top10"], ret["passages"], len(core.tokenize(question)), intent_router.p_off_topic(question))
        p = conf_model.p(feats)
        lab = conf_model.label(p)
        out.update(label=lab, score={"High": 0.9, "Medium": 0.6, "Low": 0.25}[lab], p_answerable=round(p, 3), calibrated=True)
    return out


def retrieve(question, cfg):
    t0 = time.time()
    topics, stypes = set(cfg["topics"]), set(cfg["source_types"])
    filtered = bool(topics or stypes)

    def allowed(i):
        c = chunks[i]
        return (not topics or c["titre_article"] in topics) and (not stypes or c["source_type"] in stypes)

    qv = model.encode([question], convert_to_numpy=True).astype("float32")
    D, I = index.search(qv, min(index.ntotal, 150 if filtered else max(40, cfg["k"] * 2)))
    vec_all = [(int(i), float(d)) for i, d in zip(I[0], D[0]) if i >= 0]
    top10 = [d for _, d in vec_all[:10]]
    vec_hits = [(i, d) for i, d in vec_all if allowed(i)]
    t_vec = time.time()

    bm_hits, bm_tokens = [], []
    if cfg["retrieval"] == "hybrid":
        fr = question_in_french(question)
        extra = core.expand_query(question + " " + fr, title_index)
        bm_tokens = core.tokenize(question) + core.tokenize(fr) + core.tokenize(" ".join(extra))
        bm_hits = [(i, s) for i, s in bm25.top(bm_tokens, 150 if filtered else 60) if allowed(i)][:max(30, cfg["k"])]
    t_bm = time.time()

    vec_rank = {i: r + 1 for r, (i, _) in enumerate(vec_hits)}
    bm_rank = {i: r + 1 for r, (i, _) in enumerate(bm_hits)}
    vec_dist = dict(vec_hits)
    if bm_hits:
        fused = [i for i, _ in core.rrf_fuse([[i for i, _ in vec_hits[:cfg["k"] * 2]], [i for i, _ in bm_hits]], weights=[1.0, 0.8])]
    else:
        fused = [i for i, _ in vec_hits]
    cand = fused[:cfg["k"]]

    rer = {}
    if cfg["rerank"] and cand:
        scores = reranker.predict([[question, chunks[i]["texte"]] for i in cand])
        rer = {i: float(s) for i, s in zip(cand, scores)}
        order = sorted(cand, key=lambda i: rer[i], reverse=True)
    else:
        order = cand
    t_rr = time.time()
    order = core.diversify(order, cfg["top_n"], per_group=3 if cfg["top_n"] <= 8 else 4, key=lambda i: chunks[i]["titre_article"])

    passages = []
    for n, i in enumerate(order, 1):
        c = chunks[i]
        passages.append({
            "n": n, "id": c["id"], "titre": c["titre_article"], "nom": nom_en(c["titre_article"]), "url": c["source"],
            "source_type": c["source_type"], "lang": c["lang"], "section": c["section"], "texte": c["texte"],
            "distance": round(vec_dist[i], 2) if i in vec_dist else None,
            "rerank": round(rer[i], 3) if i in rer else None,
            "vec_rank": vec_rank.get(i), "bm25_rank": bm_rank.get(i),
        })
    return {
        "passages": passages, "top10": top10,
        "counts": {"vector": len(vec_hits), "bm25": len(bm_hits), "candidates": len(cand)},
        "bm25_terms": sorted(set(bm_tokens))[:40],
        "timings_ms": {"vector": round((t_vec - t0) * 1000), "keyword": round((t_bm - t_vec) * 1000),
                       "rerank": round((t_rr - t_bm) * 1000), "total": round((time.time() - t0) * 1000)},
    }


def sources_of(passages):
    """One badge per article (several passages or source types are merged)."""
    out, seen = [], {}
    for p in passages:
        if p["titre"] in seen:
            if p["source_type"] not in seen[p["titre"]]["source_types"]:
                seen[p["titre"]]["source_types"].append(p["source_type"])
            continue
        entry = {"titre": p["titre"], "nom": p["nom"], "url": p["url"], "source_types": [p["source_type"]]}
        seen[p["titre"]] = entry
        out.append(entry)
    return out


def places_of(passages):
    out, seen = [], set()
    for p in passages:
        m = meta(p["titre"])
        if p["titre"] in seen or m["kind"] != "site" or m["lat"] is None:
            continue
        seen.add(p["titre"])
        out.append({"titre": p["titre"], "nom": m["en"], "lat": m["lat"], "lon": m["lon"]})
    return out


# ------------------------------------------------------------------ faithfulness (NLI)
def get_nli():
    if _nli["model"] is None:
        _nli["model"], _nli["name"] = _load_cross_encoder(NLI_NAMES, "NLI")
    return _nli["model"]


def _nli_indices(nli):
    id2 = getattr(getattr(getattr(nli, "model", None), "config", None), "id2label", None) or {}
    ent = con = None
    for i, lab in id2.items():
        low = str(lab).lower()
        if "entail" in low:
            ent = int(i)
        elif "contra" in low:
            con = int(i)
    return (1 if ent is None else ent), (0 if con is None else con)


def _nli_probs(pairs):
    nli = get_nli()
    logits = np.array(nli.predict([[a, b] for a, b in pairs], batch_size=8), dtype=float)
    if logits.ndim == 1:
        logits = logits.reshape(-1, 1)
    probs = np.array(core.softmax_rows(logits.tolist()))
    return probs, _nli_indices(nli)


def _nli_calibrator():
    if not _cal["loaded"]:
        _cal["loaded"] = True
        path = os.path.join(MODEL_DIR, "nli_calibrator.json")
        if os.path.exists(path):
            try:
                c = NliCalibrator.load(path)
                if c.meta.get("nli") == _nli["name"]:
                    _cal["model"] = c
                    print("NLI calibrator loaded.")
                else:
                    print(f"WARNING: nli_calibrator.json was trained for '{c.meta.get('nli')}', not '{_nli['name']}': ignored.")
            except Exception as ex:
                print("WARNING: could not load nli_calibrator.json:", repr(ex))
    return _cal["model"]


def check_fidelity(answer, passages):
    """Sentence-by-sentence support check. Headings and 'Limits' commentary are listed but never scored."""
    parts = core.split_sentences(answer)
    claims = [p for p in parts if not p["heading"] and not p.get("meta")]
    out = {"taux": 1.0, "details": [], "model": _nli["name"], "calibrated": False, "citation_precision": None}
    if not claims or not passages:
        out["details"] = [{"phrase": core.strip_citations(p["text"]), "heading": p["heading"], "meta": bool(p.get("meta"))} for p in parts]
        return out
    texts = [p["texte"][:900] for p in passages]
    sent = [core.strip_citations(c["text"]) for c in claims]
    emb = model.encode(sent + texts, convert_to_numpy=True).astype("float32")
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    sims = emb[:len(sent)] @ emb[len(sent):].T
    pairs, owner = [], []
    for i, c in enumerate(claims):
        picks = set(int(j) for j in np.argsort(-sims[i])[:3])
        picks |= {n - 1 for n in c["cites"] if 1 <= n <= len(passages)}
        for j in sorted(picks):
            pairs.append((texts[j], sent[i]))
            owner.append((i, j))
    probs, (ent, con) = _nli_probs(pairs)
    neu = 3 - ent - con
    cal = _nli_calibrator()
    best = {}
    for (i, j), pr in zip(owner, probs):
        e_p, c_p, n_p = float(pr[ent]), float(pr[con]), float(pr[neu])
        p_sup = cal.p(nli_features((e_p, c_p, n_p), sent[i], texts[j])) if cal else e_p
        b = best.setdefault(i, {"p": -1.0, "entail": 0.0, "passage": None, "contra": 0.0})
        if p_sup > b["p"]:
            b.update(p=p_sup, entail=e_p, passage=j + 1)
        b["contra"] = max(b["contra"], c_p)
    details, ci, n_ok = [], 0, 0
    for p in parts:
        if p["heading"] or p.get("meta"):
            details.append({"phrase": core.strip_citations(p["text"]), "heading": bool(p["heading"]), "meta": bool(p.get("meta"))})
            continue
        b = best[ci]
        ci += 1
        ok = b["p"] > 0.5
        n_ok += int(ok)
        details.append({
            "phrase": core.strip_citations(p["text"]), "heading": False, "soutenue": ok, "score": round(b["entail"], 2),
            "p_supported": round(b["p"], 2) if cal else None, "best": b["passage"], "contradiction": round(b["contra"], 2),
            "cited": p["cites"], "cite_ok": (b["passage"] in p["cites"]) if p["cites"] else None,
        })
    out.update(taux=n_ok / len(claims), details=details, model=_nli["name"], calibrated=cal is not None,
               citation_precision=core.citation_precision(details))
    return out


def facts_for(titres):
    return [{"titre": t, "nom": nom_en(t), **facts[t]} for t in titres if t in facts]


def topic_map():
    path = os.path.join(MODEL_DIR, "topic_map.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf8") as f:
        return json.load(f)


def find_conflicts(passages, threshold=0.6):
    """Pairs of passages about the same topic coming from different sources that contradict each other."""
    pairs, ids = [], []
    for a in range(len(passages)):
        for b in range(a + 1, len(passages)):
            pa, pb = passages[a], passages[b]
            if pa["titre"] == pb["titre"] and pa["source_type"] != pb["source_type"]:
                pairs.append((pa["texte"][:900], pb["texte"][:500]))
                ids.append((pa["n"], pb["n"]))
    pairs, ids = pairs[:15], ids[:15]
    if not pairs:
        return {"checked": 0, "conflicts": []}
    probs, (_, con) = _nli_probs(pairs)
    conflicts = [{"a": a, "b": b, "score": round(float(p[con]), 2)} for (a, b), p in zip(ids, probs) if p[con] >= threshold]
    return {"checked": len(pairs), "conflicts": sorted(conflicts, key=lambda x: -x["score"])}


# ------------------------------------------------------------------ quiz and kids content
def make_quiz(extrait, audience="standard", n_options=4):
    n_options = 3 if n_options == 3 else 4
    text = chat(prompts.quiz(nom_en(extrait["titre"]), extrait["texte"], audience, n_options), 800)
    data = core.extract_json(text)
    if not isinstance(data, dict) or not isinstance(data.get("question"), str):
        raise ValueError("unexpected format")
    options = data.get("options")
    if not isinstance(options, list) or len(options) != n_options or not all(isinstance(o, str) for o in options):
        raise ValueError("unexpected options")
    correct = options[int(data["index_correct"])]
    random.shuffle(options)  # the LLM tends to put the right answer first
    return {"question": data["question"], "options": options, "index_correct": options.index(correct),
            "explication": str(data.get("explication", "")), "source": nom_en(extrait["titre"]),
            "emoji": meta(extrait["titre"])["emoji"]}


def make_quiz_retry(extrait, audience="standard", n_options=4, tries=3):
    for _ in range(tries):
        try:
            return make_quiz(extrait, audience, n_options)
        except Exception:
            continue
    return None


def random_chunk(kids=False):
    if kids and _kid_pool:
        return chunks[random.choice(_kid_pool)]
    return random.choice(chunks)


def true_false():
    for _ in range(3):
        c = random_chunk(kids=True)
        data = core.extract_json(chat(prompts.true_false(nom_en(c["titre_article"]), c["texte"]), 500))
        if isinstance(data, dict) and isinstance(data.get("statement"), str) and isinstance(data.get("answer"), bool):
            return {"statement": data["statement"], "answer": data["answer"], "explanation": str(data.get("explanation", "")),
                    "source": nom_en(c["titre_article"]), "emoji": meta(c["titre_article"])["emoji"]}
    return None


_clue_cache = {}


def site_clue(titre):
    if titre in _clue_cache:
        return _clue_cache[titre]
    m = meta(titre)
    names = [m["en"], titre]
    clue = ""
    pool = [i for i in chunks_by_title.get(titre, []) if len(chunks[i]["texte"]) > 300]
    if pool:
        try:
            clue = chat(prompts.clue(m["en"], m["era"] or "long ago", chunks[random.choice(pool[:6])]["texte"][:700]), 300)
        except Exception:
            clue = ""
    if not clue or core.clue_leaks(clue, names):
        clue = f"I am a special place from the {m['era'] or 'past'}, in {m['region'] or 'the world'}. Can you find me on the map?"
    _clue_cache[titre] = clue
    return clue


def now():
    return datetime.now()
