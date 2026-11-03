"""HTTP layer (FastAPI). All the logic lives in engine.py, core.py, prompts.py and store.py."""
import base64
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional
from urllib.parse import quote

import edge_tts
import requests
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import core
import engine
import logging_setup
import prompts
from logging_setup import log_event
from prompts import PROMPT_VERSION
from engine import MODES, store
from sites_data import ERAS, TOPICS, meta, nom_en

# ------------------------------------------------------------------ configuration
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    print("WARNING: SESSION_SECRET is missing from .env, sessions will be lost at every restart.")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
EMAILS_AUTORISES = {e.strip().lower() for e in os.getenv("EMAILS_AUTORISES", "").split(",") if e.strip()}
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", 30))   # LLM-backed requests per user and minute (0 = unlimited)
limiter = core.RateLimiter(RATE_LIMIT)
logging_setup.setup(fmt=os.getenv("LOG_FORMAT"), level=os.getenv("LOG_LEVEL", "INFO"))
DUREE_SESSION = 7 * 24 * 3600
dernieres_demandes = {}
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

VOIX = {"fr": "fr-FR-DeniseNeural", "en": "en-US-AriaNeural", "ar": "ar-SA-ZariyahNeural", "es": "es-ES-ElviraNeural"}
KIDS_VOICE = "en-US-AnaNeural"
RECHERCHES_FORCEES = {"El Jem": "Amphitheatre of El Jem"}
cache_images = {}

app = FastAPI(title="QA Historical Mysteries - API")
public = APIRouter()


def as_dict(m):
    return m.model_dump() if hasattr(m, "model_dump") else m.dict()


def safe(fn, default=None):
    """Best-effort call: history, logs and stats must never break an answer."""
    try:
        return fn()
    except Exception as e:
        print("non-fatal error:", repr(e))
        return default


# ------------------------------------------------------------------ sessions
def creer_session(email):
    expiration = int(time.time()) + DUREE_SESSION
    payload = base64.urlsafe_b64encode(f"{email}|{expiration}".encode()).decode().rstrip("=")
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def lire_session(jeton):
    try:
        payload, signature = jeton.rsplit(".", 1)
        attendue = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, attendue):
            return None
        brut = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        email, expiration = brut.rsplit("|", 1)
        if int(expiration) < time.time():
            return None
        return email
    except Exception:
        return None


def utilisateur_courant(request: Request):
    email = lire_session(request.cookies.get("session", ""))
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return email


def admin_requis(email: str = Depends(utilisateur_courant)):
    if email.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Administrators only.")
    return email


def throttle(email):
    if not limiter.allow(email):
        raise HTTPException(status_code=429, detail=f"Too many requests: please wait {int(limiter.retry_after(email)) + 1} seconds.")


def user_hash(email):
    return hashlib.sha256((email + SESSION_SECRET).encode()).hexdigest()[:16]


router = APIRouter(dependencies=[Depends(utilisateur_courant)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ request models
class Echange(BaseModel):
    question: str
    reponse: str


class Options(BaseModel):
    retrieval: str = "hybrid"
    k: int = 0
    top_n: int = 0
    rerank: bool = True
    topics: list[str] = []
    source_types: list[str] = []
    strict: bool = False
    include_prompt: bool = False


class Question(BaseModel):
    texte: str
    historique: list[Echange] = []
    mode: str = "standard"
    options: Options = Options()


class DemandeQuiz(BaseModel):
    extraits: list[dict] = []
    audience: str = "standard"
    n_options: int = 4


class DemandeTraduction(BaseModel):
    texte: str
    langue: str


class DemandeAudio(BaseModel):
    texte: str
    langue: str = "en"
    voix: str = "standard"


class DemandeFidelite(BaseModel):
    reponse: str
    extraits: list[dict] = []
    passages: list[dict] = []


class DemandePassages(BaseModel):
    passages: list[dict] = []
    extraits: list[dict] = []
    audience: str = "standard"


class DemandeComparaison(BaseModel):
    a: str
    b: str
    audience: str = "standard"


class DemandeHistoire(BaseModel):
    topic: str


class DemandeStatQuiz(BaseModel):
    scope: str = "main"
    correct: bool


class DemandeCarte(BaseModel):
    front: str
    back: str
    source: str = ""
    mode: str = "standard"


class DemandeRevue(BaseModel):
    correct: bool


class DemandeEtoile(BaseModel):
    starred: bool = True


class DemandeAvis(BaseModel):
    rating: int
    comment: str = ""
    question: str = ""
    mode: str = "standard"
    history_id: Optional[int] = None


class DemandeLieu(BaseModel):
    site: str
    lat: float
    lon: float


class DemandeLien(BaseModel):
    email: str


class DemandeToken(BaseModel):
    token: str


class DemandeInscription(BaseModel):
    name: str
    email: str


# ------------------------------------------------------------------ authentication (public routes)
def envoyer_email(destinataire, lien, kind="signin"):
    expediteur = os.getenv("SMTP_EMAIL")
    mot_de_passe = os.getenv("SMTP_APP_PASSWORD")
    if not expediteur or not mot_de_passe:
        raise RuntimeError("SMTP_EMAIL or SMTP_APP_PASSWORD is missing in the .env file")
    if kind == "verify":
        corps = ("Hello,\n\nSomeone created an account with this email address on QA Historical Mysteries. To confirm it and sign in, click:\n\n" + lien +
                 "\n\nThis link expires in 15 minutes and can be used only once.\nIf you did not create this account, do NOT click the link: just ignore this email.")
        sujet = "Confirm your email - QA Historical Mysteries"
    else:
        corps = ("Hello,\n\nClick this link to sign in to QA Historical Mysteries:\n\n" + lien +
                 "\n\nThis link expires in 15 minutes and can be used only once.\nIf you did not request it, you can ignore this email.")
        sujet = "Your sign-in link - QA Historical Mysteries"
    msg = MIMEText(corps, "plain", "utf-8")
    msg["Subject"] = sujet
    msg["From"] = expediteur
    msg["To"] = destinataire
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as serveur:
        serveur.login(expediteur, mot_de_passe)
        serveur.send_message(msg)


def creer_lien(email, prefix=""):
    """One-time link valid 15 minutes. Account-confirmation links start with "v_": only those can confirm a membership."""
    jeton = prefix + secrets.token_urlsafe(32)
    expiration = datetime.now() + timedelta(minutes=15)
    try:
        c = engine.connect_db()
        cur = c.cursor()
        cur.execute("INSERT INTO magic_tokens (token, email, date_expiration) VALUES (%s, %s, %s)", (jeton, email, expiration))
        c.commit()
        cur.close()
        c.close()
    except Exception as e:
        print("Database error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Database error: {e}")
    return f"{FRONTEND_URL}/?token={jeton}"


def utilisateur_connu(email):
    """May this e-mail ask for a sign-in link? Yes with a confirmed membership, or if it already signed in with an earlier version."""
    try:
        member = store.get_member(email)
        if member and member["verified"]:
            return True
        c = engine.connect_db()
        cur = c.cursor()
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        found = cur.fetchone() is not None
        cur.close()
        c.close()
        return found
    except Exception as e:
        print("Database error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Database error: {e}")


@public.post("/auth/inscription")
def inscription(d: DemandeInscription):
    """Sign up with a name and an e-mail. Nothing to remember: the link sent by e-mail confirms the address and signs you in."""
    email = d.email.strip().lower()
    name = core.clean_name(d.name)
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not name:
        raise HTTPException(status_code=400, detail="Please enter your name (2 to 60 characters).")
    if EMAILS_AUTORISES and email not in EMAILS_AUTORISES:
        raise HTTPException(status_code=403, detail="This email address is not authorized.")
    member = store.get_member(email)
    if member and member["verified"]:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please sign in.")
    if time.time() - dernieres_demandes.get(email, 0) < 30:
        raise HTTPException(status_code=429, detail="Please wait 30 seconds before trying again.")
    store.save_member(email, name, engine.now())
    lien = creer_lien(email, prefix="v_")
    try:
        envoyer_email(email, lien, "verify")
    except Exception as e:
        print("Email error:", repr(e))
        raise HTTPException(status_code=502, detail=f"The email could not be sent: {e}")
    dernieres_demandes[email] = time.time()
    return {"ok": True, "needs_verification": True}


@public.post("/auth/demande")
def demander_lien(d: DemandeLien):
    email = d.email.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if EMAILS_AUTORISES and email not in EMAILS_AUTORISES:
        raise HTTPException(status_code=403, detail="This email address is not authorized.")
    if time.time() - dernieres_demandes.get(email, 0) < 30:
        raise HTTPException(status_code=429, detail="Please wait 30 seconds before requesting another link.")
    if not utilisateur_connu(email):
        raise HTTPException(status_code=404, detail="No account found for this email address. Please sign up first.")
    jeton = secrets.token_urlsafe(32)
    expiration = datetime.now() + timedelta(minutes=15)
    try:
        c = engine.connect_db()
        cur = c.cursor()
        cur.execute("INSERT INTO magic_tokens (token, email, date_expiration) VALUES (%s, %s, %s)", (jeton, email, expiration))
        c.commit()
        cur.close()
        c.close()
    except Exception as e:
        print("Database error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Database error: {e}")
    try:
        envoyer_email(email, f"{FRONTEND_URL}/?token={jeton}")
    except Exception as e:
        print("Email error:", repr(e))
        raise HTTPException(status_code=502, detail=f"The email could not be sent: {e}")
    dernieres_demandes[email] = time.time()
    return {"ok": True}


@public.post("/auth/verifier")
def verifier_lien(d: DemandeToken, response: Response):
    try:
        c = engine.connect_db()
        cur = c.cursor(dictionary=True)
        cur.execute("UPDATE magic_tokens SET utilise = TRUE WHERE token = %s AND utilise = FALSE AND date_expiration > %s",
                    (d.token, datetime.now()))
        c.commit()
        valide = cur.rowcount == 1
        email = None
        if valide:
            cur.execute("SELECT email FROM magic_tokens WHERE token = %s", (d.token,))
            email = cur.fetchone()["email"]
        cur.close()
        c.close()
    except Exception as e:
        print("Database error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Database error: {e}")
    if not valide:
        raise HTTPException(status_code=400, detail="This link is invalid, expired or already used.")
    try:
        c = engine.connect_db()
        cur = c.cursor()
        cur.execute("INSERT IGNORE INTO users (email) VALUES (%s)", (email,))   # from now on this address may ask for sign-in links
        c.commit()
        cur.close()
        c.close()
        if d.token.startswith("v_"):
            store.confirm_member(email)    # the owner of the mailbox confirmed the membership
        member = store.get_member(email)
    except Exception as e:
        print("Database error:", repr(e))
        member = None
    response.set_cookie("session", creer_session(email), max_age=DUREE_SESSION, httponly=True,
                        samesite="lax", secure=COOKIE_SECURE, path="/")
    return {"email": email, "admin": email.lower() in ADMIN_EMAILS, "name": member["name"] if member and member["verified"] else None}


@public.get("/auth/moi")
def moi(email: str = Depends(utilisateur_courant)):
    try:
        member = store.get_member(email)
    except Exception:
        member = None
    return {"email": email, "admin": email.lower() in ADMIN_EMAILS, "name": member["name"] if member and member["verified"] else None}


@public.post("/auth/deconnexion")
def deconnexion(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@public.get("/health")
def health():
    """Liveness and readiness: the index matches the database and MySQL answers. 503 otherwise (used by Docker)."""
    checks = {"index_matches_database": engine.index.ntotal == len(engine.chunks), "database": False}
    try:
        c = engine.connect_db()
        cur = c.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        c.close()
        checks["database"] = True
    except Exception as e:
        log_event("health_check_failed", error=repr(e)[:200])
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ok", **checks, "chunks": len(engine.chunks)}


@public.get("/")
def accueil():
    return {"message": "QA Historical Mysteries API", "chunks": len(engine.chunks), "sujets": len(engine.sujets),
            "source_types": engine.source_types, "reranker": engine.reranker_name}


# ------------------------------------------------------------------ asking questions
def prepare(q: Question):
    text = (q.texte or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="The question is empty.")
    text = text[:600]
    mode = q.mode if q.mode in MODES else "standard"
    history = [{"question": h.question[:400], "reponse": core.strip_citations(h.reponse[:1200])} for h in q.historique[-3:]]
    if mode == "kids" and core.kid_unsafe(text):
        return {"blocked": True, "mode": mode, "text": text}
    opts = as_dict(q.options)
    cfg = engine.make_cfg(mode, opts)
    search_query = engine.rewrite_query(text, history)
    ret = engine.retrieve(search_query, cfg)
    a = engine.assess(text, ret)
    prompt = MODES[mode]["builder"](text, ret["passages"], history)
    abstain = engine.ABSTAIN_P > 0 and a["calibrated"] and a["p_answerable"] < engine.ABSTAIN_P
    return {"blocked": False, "mode": mode, "text": text, "cfg": cfg, "history": history, "ret": ret, "prompt": prompt,
            "assess": a, "conf": (a["label"], a["score"], a["distance"]), "abstain": abstain, "search_query": search_query,
            "include_prompt": bool(opts.get("include_prompt"))}


def meta_event(prep):
    if prep["blocked"]:
        return {"mode": prep["mode"], "blocked": True}
    label, score, dist = prep["conf"]
    passages = prep["ret"]["passages"]
    return {"mode": prep["mode"], "sources": engine.sources_of(passages), "passages": passages, "lieux": engine.places_of(passages),
            "confiance": label, "score": score, "distance": round(dist, 2), "p_answerable": prep["assess"]["p_answerable"],
            "intent": prep["assess"]["intent"]}


ABSTAIN_REPLY = ("I could not find reliable information about this in my sources, so I prefer not to guess. "
                 "You can rephrase the question, or check the closest sources listed below.")


def badge_info(ids):
    return [{"id": b, **core.BADGES[b]} for b in ids]


def count_question(email, mode):
    scope = "kids" if mode == "kids" else "main"
    before = store.get_stats(email, scope)
    after = store.bump(email, scope, engine.now(), questions=1)
    return sorted(set(core.award_badges(after)) - set(core.award_badges(before)))


def finalize(prep, answer, email):
    mode = prep["mode"]
    if prep["blocked"]:
        return {"reponse": core.KID_SAFE_REPLY, "mode": mode, "sources": [], "passages": [], "citations": [], "lieux": [],
                "extraits": [], "confiance": "High", "score": 0.9, "distance": 0.0, "refused": True, "blocked": True}
    passages = prep["ret"]["passages"]
    n = len(passages)
    if MODES[mode]["cite"]:
        answer = core.keep_valid_citations(answer, n)
        cites = core.used_citations(answer, n)
    else:
        answer, cites = core.strip_citations(answer), []
    fidelity = strict = None
    if prep["cfg"]["strict"] and passages and answer:
        try:
            answer, fidelity, strict = strict_fix(prep, answer)
        except Exception as e:
            print("strict mode skipped:", repr(e))
    refused = core.is_refusal(answer)
    label, score, dist = prep["conf"]
    cfg, ret = prep["cfg"], prep["ret"]
    payload = {
        "reponse": answer, "mode": mode, "sources": engine.sources_of(passages), "passages": passages, "citations": cites,
        "lieux": engine.places_of(passages), "extraits": [{"titre": p["titre"], "texte": p["texte"][:800]} for p in passages],
        "confiance": label, "score": score, "distance": round(dist, 2), "refused": refused,
        "p_answerable": prep["assess"]["p_answerable"], "calibrated": prep["assess"]["calibrated"], "intent": prep["assess"]["intent"],
        "abstained": bool(prep["abstain"]), "prompt_version": PROMPT_VERSION, "temperature": MODES[mode]["temperature"],
        "retrieval": {**cfg, **ret["counts"], "timings_ms": ret["timings_ms"], "bm25_terms": ret["bm25_terms"],
                      "reranker": engine.reranker_name, "llm": engine.LLM_MODEL, "embedding": engine.EMBED_MODEL,
                      "chunks_in_corpus": len(engine.chunks), "corpus_source_types": engine.source_types, "search_query": prep["search_query"],
                      "generated_at": engine.now().isoformat(timespec="seconds")},
    }
    if fidelity:
        payload["fidelity"], payload["strict"] = fidelity, strict
    if prep["include_prompt"] and mode == "researcher":
        payload["prompt"] = prep["prompt"]
    log_event("answer", mode=mode, confidence=label, p_answerable=prep["assess"]["p_answerable"], refused=refused, abstained=bool(prep["abstain"]),
              passages=n, retrieval_ms=ret["timings_ms"]["total"], prompt_version=PROMPT_VERSION)
    now = engine.now()
    payload["history_id"] = safe(lambda: store.add_history(email, mode, prep["text"], answer, payload, label, round(dist, 2), refused, now))
    safe(lambda: store.log_query(mode, prep["text"], label, round(dist, 2), refused, now))
    new_badges = safe(lambda: count_question(email, mode), [])
    if mode == "kids":
        payload["new_badges"] = badge_info(new_badges)
    return payload


def generate_prompt(mode, prompt):
    return engine.chat(prompt, MODES[mode]["max_tokens"], temperature=0, effort=MODES[mode]["effort"])


def strict_fix(prep, answer):
    passages = prep["ret"]["passages"]
    fid = engine.check_fidelity(answer, passages)
    fixes = core.citation_fixes(fid["details"])
    cp = fid.get("citation_precision")
    info = {"initial_rate": round(fid["taux"], 2), "final_rate": round(fid["taux"], 2), "regenerated": False,
            "initial_citation_precision": None if cp is None else round(cp, 2), "final_citation_precision": None if cp is None else round(cp, 2)}
    bad = [d["phrase"] for d in fid["details"] if not d.get("heading") and not d.get("meta") and not d.get("soutenue")][:6]
    needs = fid["taux"] < engine.STRICT_THRESHOLD or (cp is not None and cp < 0.6 and fixes)
    if needs and (bad or fixes):
        text = generate_prompt(prep["mode"], prompts.regenerate(prep["text"], passages, answer, bad, prep["mode"], fixes[:6]))
        if text:
            text = core.keep_valid_citations(text, len(passages))
            fid2 = engine.check_fidelity(text, passages)
            info["regenerated"] = True
            cp2 = fid2.get("citation_precision")
            better = fid2["taux"] > fid["taux"] or (fid2["taux"] == fid["taux"] and (cp2 or 0) >= (cp or 0))
            if better:
                answer, fid = text, fid2
                info["final_rate"] = round(fid2["taux"], 2)
                info["final_citation_precision"] = None if cp2 is None else round(cp2, 2)
    return answer, fid, info


def generate(mode, prompt):
    return engine.chat(prompt, MODES[mode]["max_tokens"], temperature=MODES[mode]["temperature"], effort=MODES[mode]["effort"])


def with_heartbeat(fn, interval=5.0):
    """Run fn() in a thread and yield SSE comments while it works, so that proxies never see a silent connection.
    Use as:  result = yield from with_heartbeat(lambda: slow())"""
    box = {}

    def work():
        try:
            box["value"] = fn()
        except Exception as ex:   # re-raised in the caller
            box["error"] = ex

    th = threading.Thread(target=work, daemon=True)
    th.start()
    while True:
        th.join(timeout=interval)
        if not th.is_alive():
            break
        yield ": keep-alive\n\n"
    if "error" in box:
        raise box["error"]
    return box["value"]


@router.post("/ask")
def poser_question(q: Question, email: str = Depends(utilisateur_courant)):
    throttle(email)
    prep = prepare(q)
    answer = ""
    if not prep["blocked"] and prep["abstain"]:
        answer = ABSTAIN_REPLY
    elif not prep["blocked"]:
        answer = generate(prep["mode"], prep["prompt"])
        if not answer:
            raise HTTPException(status_code=502, detail="The language model returned an empty answer, please try again.")
    return finalize(prep, answer, email)


def sse(name, obj):
    return f"event: {name}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ask/stream")
def poser_question_stream(q: Question, email: str = Depends(utilisateur_courant)):
    throttle(email)
    if not (q.texte or "").strip():
        raise HTTPException(status_code=400, detail="The question is empty.")

    def gen():
        yield ": open\n\n"   # the response starts at once: a slow search must not look like a dead connection
        try:
            prep = yield from with_heartbeat(lambda: prepare(q))
        except HTTPException as ex:
            yield sse("error", {"detail": ex.detail})
            return
        except Exception as ex:
            log_event("prepare_failed", error=repr(ex)[:200])
            yield sse("error", {"detail": "The search failed, please try again."})
            return
        yield sse("meta", meta_event(prep))
        if prep["blocked"]:
            yield sse("done", finalize(prep, "", email))
            return
        if prep["abstain"]:
            yield sse("done", finalize(prep, ABSTAIN_REPLY, email))
            return
        parts = []
        try:
            for tok in engine.chat_stream(prep["prompt"], MODES[prep["mode"]]["max_tokens"], temperature=MODES[prep["mode"]]["temperature"],
                                          effort=MODES[prep["mode"]]["effort"]):
                parts.append(tok)
                yield sse("token", {"t": tok})
        except Exception as ex:
            print("streaming failed, falling back:", repr(ex))
        answer = "".join(parts).strip()
        if not answer:
            answer = yield from with_heartbeat(lambda: generate(prep["mode"], prep["prompt"]))
        if not answer:
            yield sse("error", {"detail": "The language model returned an empty answer, please try again."})
            return
        try:
            payload = yield from with_heartbeat(lambda: finalize(prep, answer, email))   # strict mode can take a while
        except Exception as ex:
            log_event("finalize_failed", error=repr(ex)[:200])
            yield sse("error", {"detail": "The answer could not be completed, please try again."})
            return
        yield sse("done", payload)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ quiz
@router.post("/quiz")
def quiz(d: DemandeQuiz, email: str = Depends(utilisateur_courant)):
    throttle(email)
    if not d.extraits:
        raise HTTPException(status_code=400, detail="No excerpt provided.")
    audience = d.audience if d.audience in ("standard", "kids") else "standard"
    for _ in range(3):
        data = engine.make_quiz_retry(random.choice(d.extraits), audience, d.n_options, tries=1)
        if data:
            return data
    raise HTTPException(status_code=502, detail="The LLM did not return a valid question, please try again.")


@router.get("/quiz/random")
def quiz_random(audience: str = "kids", email: str = Depends(utilisateur_courant)):
    throttle(email)
    kids = audience == "kids"
    for _ in range(3):
        c = engine.random_chunk(kids=kids)
        data = engine.make_quiz_retry({"titre": c["titre_article"], "texte": c["texte"]}, "kids" if kids else "standard", 3 if kids else 4, tries=1)
        if data:
            return data
    raise HTTPException(status_code=502, detail="The LLM did not return a valid question, please try again.")


# ------------------------------------------------------------------ translation, audio, images
@router.post("/traduire")
def traduire(d: DemandeTraduction, email: str = Depends(utilisateur_courant)):
    throttle(email)
    if d.langue not in engine.NOMS_LANGUES:
        raise HTTPException(status_code=400, detail="Unsupported language.")
    try:
        texte, moteur = engine.translate_text(core.strip_citations(d.texte)[:4900], d.langue)
        return {"texte": texte, "moteur": moteur}
    except Exception as e:
        print("Translation error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Translation unavailable: {e}")


@router.post("/audio")
async def audio(d: DemandeAudio):
    texte = core.nettoyer(d.texte)[:3000]
    if not texte:
        raise HTTPException(status_code=400, detail="Empty text.")
    kids = d.voix == "kids" and d.langue == "en"
    voices = [(KIDS_VOICE, "-8%")] if kids else []
    voices.append((VOIX.get(d.langue, VOIX["en"]), "+0%"))
    last = None
    for voix, rate in voices:
        try:
            communicate = edge_tts.Communicate(texte, voix, rate=rate)
            data = b""
            async for morceau in communicate.stream():
                if morceau["type"] == "audio":
                    data += morceau["data"]
            if data:
                return Response(content=data, media_type="audio/mpeg")
        except Exception as e:
            last = e
            print("edge-tts error with", voix, ":", repr(e))
    raise HTTPException(status_code=502, detail=f"Speech synthesis unavailable: {last}")


@router.get("/image")
def image(titre: str):
    if titre in cache_images:
        return {"url": cache_images[titre]}
    headers = {"User-Agent": "ProjetQA-LLM/1.0"}
    url = None

    def depuis_commons(terme):
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params={"action": "query", "format": "json", "prop": "imageinfo", "generator": "search",
                                 "gsrsearch": terme, "gsrlimit": 1, "gsrnamespace": 6, "iiprop": "url"},
                         timeout=5, headers=headers)
        for page in r.json().get("query", {}).get("pages", {}).values():
            info = page.get("imageinfo")
            if info:
                return info[0]["url"]
        return None

    def depuis_wikipedia():
        r = requests.get(f"https://fr.wikipedia.org/api/rest_v1/page/summary/{quote(titre)}", timeout=5, headers=headers)
        return r.json().get("thumbnail", {}).get("source")

    try:
        if titre in RECHERCHES_FORCEES:
            url = depuis_commons(RECHERCHES_FORCEES[titre])
        if not url:
            url = depuis_wikipedia()
        if not url:
            url = depuis_commons(titre)
    except Exception:
        url = None
    if url:
        cache_images[titre] = url
    return {"url": url}


# ------------------------------------------------------------------ research tools
@router.post("/fidelite")
def fidelite(d: DemandeFidelite):
    passages = d.passages or [{"n": i + 1, "titre": e.get("titre", ""), "texte": e.get("texte", "")} for i, e in enumerate(d.extraits)]
    try:
        return engine.check_fidelity(d.reponse, passages)
    except Exception as e:
        print("Faithfulness check error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Faithfulness check unavailable: {e}")


@router.post("/contradictions")
def contradictions(d: DemandePassages):
    try:
        return engine.find_conflicts(d.passages[:12])
    except Exception as e:
        print("Contradiction check error:", repr(e))
        raise HTTPException(status_code=502, detail=f"Contradiction check unavailable: {e}")


@router.post("/timeline")
def timeline(d: DemandePassages, email: str = Depends(utilisateur_courant)):
    throttle(email)
    passages = d.passages or [{"n": i + 1, "nom": nom_en(e.get("titre", "")), "source_type": "Wikipedia", "texte": e.get("texte", "")}
                              for i, e in enumerate(d.extraits)]
    if not passages:
        raise HTTPException(status_code=400, detail="No passage provided.")
    passages = [{"n": p.get("n", i + 1), "nom": p.get("nom") or nom_en(p.get("titre", "")), "source_type": p.get("source_type", "Wikipedia"),
                 "texte": p.get("texte", "")[:900]} for i, p in enumerate(passages[:8])]
    audience = d.audience if d.audience in ("standard", "kids") else "standard"
    raw = core.extract_json(engine.chat(prompts.timeline(passages, audience), 900))
    events = core.clean_events(raw, n_passages=max(p["n"] for p in passages))
    texts = [p["texte"] for p in passages]
    by_n = {p["n"]: p["texte"] for p in passages}
    for ev in events:
        # a date is "verified" when it really appears in the passage it cites (or, failing that, in any passage)
        own = [by_n[ev["source"]]] if ev.get("source") in by_n else []
        ev["verified"] = core.year_in_texts(ev["year"], own or texts) if own else core.year_in_texts(ev["year"], texts)
    return {"events": events}


@router.post("/compare")
def compare(d: DemandeComparaison, email: str = Depends(utilisateur_courant)):
    throttle(email)
    a, b = d.a.strip()[:120], d.b.strip()[:120]
    if not a or not b:
        raise HTTPException(status_code=400, detail="Please give two subjects to compare.")
    audience = d.audience if d.audience in ("standard", "kids") else "standard"
    merged, seen = [], set()
    for subject in (a, b):
        cfg = engine.make_cfg("standard", {"top_n": 4, "k": 12})
        for p in engine.retrieve(f"Tell me about {subject}", cfg)["passages"]:
            if p["id"] not in seen:
                seen.add(p["id"])
                merged.append(p)
    for i, p in enumerate(merged, 1):
        p["n"] = i
    raw = core.extract_json(engine.chat(prompts.compare(a, b, merged, audience), 1200))
    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="The comparison could not be generated, please try again.")
    diffs = [x for x in (raw.get("differences") or []) if isinstance(x, dict) and x.get("aspect")]
    as_list = lambda v: [str(x) for x in v] if isinstance(v, list) else []
    out = {"a": a, "b": b, "summary": str(raw.get("summary", "")), "similarities": as_list(raw.get("similarities")),
           "differences": [{"aspect": str(x["aspect"]), "a": str(x.get("a", "")), "b": str(x.get("b", ""))} for x in diffs],
           "caveats": as_list(raw.get("caveats")), "passages": merged, "sources": engine.sources_of(merged)}
    if audience == "kids":
        for k in ("summary",):
            out[k] = core.strip_citations(out[k])
        out["similarities"] = [core.strip_citations(x) for x in out["similarities"]]
        out["differences"] = [{**x, "a": core.strip_citations(x["a"]), "b": core.strip_citations(x["b"])} for x in out["differences"]]
    return out


@router.get("/facts")
def facts(titres: str = ""):
    """Structured facts (Wikidata) for the topics of an answer. Empty until collect_sources.py wikidata has been run."""
    wanted = [t for t in titres.split("|") if t][:12]
    return {"facts": engine.facts_for(wanted), "available": bool(engine.facts)}


@router.get("/corpus/map")
def corpus_map():
    data = engine.topic_map()
    if data is None:
        raise HTTPException(status_code=404, detail="The corpus map has not been built yet (python training/build_topic_map.py).")
    return data


# ------------------------------------------------------------------ topics, map, anecdote
@router.get("/sujets")
def liste_sujets():
    out = []
    for t in engine.sujets:
        m = meta(t)
        out.append({"titre": t, "nom": m["en"], "emoji": m["emoji"], "era": m["era"], "year": m["year"],
                    "tunisia": m["tunisia"], "region": m["region"], "has_map": m["lat"] is not None, "kids_ok": not m["sensitive"]})
    return {"sujets": out, "eras": ERAS, "source_types": engine.source_types}


@router.get("/sites")
def sites():
    out = []
    for t in engine.sujets:
        m = meta(t)
        if m["lat"] is not None:
            out.append({"titre": t, "nom": m["en"], "emoji": m["emoji"], "era": m["era"], "year": m["year"], "region": m["region"],
                        "tunisia": m["tunisia"], "kind": m["kind"], "lat": m["lat"], "lon": m["lon"]})
    return {"sites": out, "eras": ERAS}


@router.get("/anecdote")
def anecdote(audience: str = "standard"):
    kids = audience == "kids"
    c = engine.random_chunk(kids=kids)
    titre = nom_en(c["titre_article"])
    raw = c["texte"][:280].rsplit(" ", 1)[0] + "..."
    if kids:
        text = safe(lambda: engine.chat(prompts.kids_anecdote(titre, c["texte"][:700]), 300), "")
        return {"titre": titre, "emoji": meta(c["titre_article"])["emoji"], "extrait": text or raw}
    if c["lang"] != "en":
        raw = safe(lambda: engine.translate_text(raw, "en", source="fr")[0], raw)
    return {"titre": titre, "extrait": raw}


# ------------------------------------------------------------------ notebook: history, cards, stats, feedback
@router.get("/history")
def history(mode: str = "", starred: bool = False, limit: int = 50, email: str = Depends(utilisateur_courant)):
    return {"items": store.list_history(email, mode or None, starred, max(1, min(limit, 200)))}


@router.get("/history/{hid}")
def history_item(hid: int, email: str = Depends(utilisateur_courant)):
    item = store.get_history(email, hid)
    if not item:
        raise HTTPException(status_code=404, detail="Not found.")
    return item


@router.post("/history/{hid}/star")
def history_star(hid: int, d: DemandeEtoile, email: str = Depends(utilisateur_courant)):
    if not store.star_history(email, hid, d.starred):
        raise HTTPException(status_code=404, detail="Not found.")
    return {"ok": True}


@router.delete("/history/{hid}")
def history_delete(hid: int, email: str = Depends(utilisateur_courant)):
    if not store.delete_history(email, hid):
        raise HTTPException(status_code=404, detail="Not found.")
    return {"ok": True}


@router.get("/cards")
def cards(due: bool = False, email: str = Depends(utilisateur_courant)):
    return {"cards": store.list_cards(email, due_only=due, now=engine.now())}


@router.post("/cards")
def card_add(d: DemandeCarte, email: str = Depends(utilisateur_courant)):
    front, back = d.front.strip()[:500], d.back.strip()[:2000]
    if not front or not back:
        raise HTTPException(status_code=400, detail="A card needs a front and a back.")
    cid, created = store.add_card(email, front, back, d.source[:250], d.mode[:20], engine.now())
    return {"id": cid, "created": created}


@router.post("/cards/{cid}/review")
def card_review(cid: int, d: DemandeRevue, email: str = Depends(utilisateur_courant)):
    r = store.review_card(email, cid, d.correct, engine.now())
    if not r:
        raise HTTPException(status_code=404, detail="Not found.")
    return r


@router.delete("/cards/{cid}")
def card_delete(cid: int, email: str = Depends(utilisateur_courant)):
    if not store.delete_card(email, cid):
        raise HTTPException(status_code=404, detail="Not found.")
    return {"ok": True}


def stats_payload(stats, new=()):
    earned = set(core.award_badges(stats))
    total = stats["quiz_total"]
    return {"stats": {**stats, "accuracy": round(100 * stats["quiz_correct"] / total) if total else None},
            "badges": [{"id": b, **info, "earned": b in earned} for b, info in core.BADGES.items()],
            "new_badges": badge_info(new)}


def valid_scope(scope):
    return scope if scope in ("kids", "main") else "main"


@router.get("/stats")
def stats(scope: str = "main", email: str = Depends(utilisateur_courant)):
    return stats_payload(store.get_stats(email, valid_scope(scope)))


@router.post("/stats/quiz")
def stats_quiz(d: DemandeStatQuiz, email: str = Depends(utilisateur_courant)):
    scope = valid_scope(d.scope)
    before = set(core.award_badges(store.get_stats(email, scope)))
    after = store.record_quiz(email, scope, d.correct, engine.now())
    return stats_payload(after, sorted(set(core.award_badges(after)) - before))


@router.post("/feedback")
def feedback(d: DemandeAvis, email: str = Depends(utilisateur_courant)):
    if d.rating == 0:
        raise HTTPException(status_code=400, detail="The rating must be positive or negative.")
    fid = store.add_feedback(user_hash(email), d.history_id, d.rating, d.comment, d.question, d.mode[:20], engine.now())
    return {"id": fid}


# ------------------------------------------------------------------ kids corner
def kids_sites():
    return [t for t in engine.sujets if meta(t)["kind"] == "site" and meta(t)["lat"] is not None and not meta(t)["sensitive"]]


@router.get("/kids/where")
def kids_where(exclude: str = ""):
    skip = {s for s in exclude.split("|") if s}
    pool = [t for t in kids_sites() if t not in skip] or kids_sites()
    if not pool:
        raise HTTPException(status_code=404, detail="No place available.")
    titre = random.choice(pool)
    m = meta(titre)
    return {"site": titre, "clue": engine.site_clue(titre), "era": m["era"], "region": m["region"]}


@router.post("/kids/where/score")
def kids_where_score(d: DemandeLieu, email: str = Depends(utilisateur_courant)):
    m = meta(d.site)
    if m["lat"] is None:
        raise HTTPException(status_code=404, detail="Unknown place.")
    km = core.haversine_km(d.lat, d.lon, m["lat"], m["lon"])
    stars = core.stars_for_distance(km)
    before = store.get_stats(email, "kids")
    after = safe(lambda: store.bump(email, "kids", engine.now(), games=1, stars=stars), before)
    new = sorted(set(core.award_badges(after)) - set(core.award_badges(before)))
    return {"distance_km": round(km), "stars": stars, "message": core.hot_or_cold(km),
            "answer": {"nom": m["en"], "emoji": m["emoji"], "lat": m["lat"], "lon": m["lon"], "year": m["year"]},
            **stats_payload(after, new)}


@router.get("/kids/truefalse")
def kids_truefalse(email: str = Depends(utilisateur_courant)):
    throttle(email)
    data = engine.true_false()
    if not data:
        raise HTTPException(status_code=502, detail="Hanni could not think of a statement, please try again.")
    return data


@router.post("/kids/story")
def kids_story(d: DemandeHistoire, email: str = Depends(utilisateur_courant)):
    throttle(email)
    topic = d.topic.strip()[:120]
    if not topic or core.kid_unsafe(topic):
        raise HTTPException(status_code=400, detail="Please choose a topic for the story.")
    cfg = engine.make_cfg("kids", {})
    passages = engine.retrieve(topic, cfg)["passages"]
    raw = engine.chat(prompts.story(topic, passages), 900)
    data = core.extract_json(raw)
    if isinstance(data, dict) and isinstance(data.get("story"), str):
        title, story = str(data.get("title") or topic), data["story"]
    else:
        title, story = topic, raw
    if not story:
        raise HTTPException(status_code=502, detail="Hanni lost the story, please try again.")
    before = store.get_stats(email, "kids")
    after = safe(lambda: store.bump(email, "kids", engine.now(), stories=1), before)
    new = sorted(set(core.award_badges(after)) - set(core.award_badges(before)))
    return {"title": title, "story": story, "sources": engine.sources_of(passages), "new_badges": badge_info(new)}


# ------------------------------------------------------------------ administration
@router.get("/admin/summary")
def admin_summary(days: int = 30, email: str = Depends(admin_requis)):
    return store.admin_summary(engine.now(), max(1, min(days, 365)))


# Routes are served with and without the /api prefix (used by the Next.js rewrite)
for prefixe in ("", "/api"):
    app.include_router(public, prefix=prefixe, include_in_schema=(prefixe == ""))
    app.include_router(router, prefix=prefixe, include_in_schema=(prefixe == ""))
