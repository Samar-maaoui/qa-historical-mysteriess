"""Offline stand-ins for FastAPI, pydantic, MySQL, FAISS, sentence-transformers, Groq... so that the
whole API can be exercised without any model, database server or network (used by test_api_flow.py)."""
import copy
import json
import os
import sys
import types
import typing
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fakedb  # noqa: E402

STATE = {"llm_calls": [], "empty_first": 0, "chunk_texts": [], "no_mmarco": False, "llm_override": None}


def _module(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


# ---------------------------------------------------------------- pydantic
class BaseModel:
    def __init__(self, **kw):
        hints = typing.get_type_hints(type(self))
        for name, hint in hints.items():
            if name in kw:
                val = kw[name]
            elif hasattr(type(self), name):
                val = copy.deepcopy(getattr(type(self), name))
            else:
                raise TypeError(f"missing field {name}")
            setattr(self, name, self._coerce(hint, val))

    @staticmethod
    def _coerce(hint, val):
        if isinstance(hint, type) and issubclass(hint, BaseModel) and isinstance(val, dict):
            return hint(**val)
        if typing.get_origin(hint) is list and val:
            arg = typing.get_args(hint)[0]
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                return [arg(**v) if isinstance(v, dict) else v for v in val]
        return val

    def model_dump(self):
        out = {}
        for name in typing.get_type_hints(type(self)):
            v = getattr(self, name)
            out[name] = v.model_dump() if isinstance(v, BaseModel) else ([x.model_dump() if isinstance(x, BaseModel) else x for x in v] if isinstance(v, list) else v)
        return out


# ---------------------------------------------------------------- fastapi
class HTTPException(Exception):
    def __init__(self, status_code=500, detail=""):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


class Response:
    def __init__(self, content=b"", media_type=None):
        self.content, self.media_type, self.cookies, self.deleted = content, media_type, {}, []

    def set_cookie(self, key, value, **kw):
        self.cookies[key] = (value, kw)

    def delete_cookie(self, key, **kw):
        self.deleted.append(key)


class StreamingResponse:
    def __init__(self, gen, media_type=None, headers=None):
        self.body_iterator, self.media_type, self.headers = gen, media_type, headers or {}


class Request:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


class Dep:
    def __init__(self, fn):
        self.fn = fn


class APIRouter:
    def __init__(self, dependencies=None):
        self.routes, self.dependencies = [], dependencies or []

    def _reg(self, method, path):
        def deco(fn):
            self.routes.append((method, path, fn))
            return fn
        return deco

    def get(self, path, **kw):
        return self._reg("GET", path)

    def post(self, path, **kw):
        return self._reg("POST", path)

    def delete(self, path, **kw):
        return self._reg("DELETE", path)


class FastAPI:
    def __init__(self, **kw):
        self.included = []

    def add_middleware(self, *a, **kw):
        pass

    def include_router(self, router, prefix="", **kw):
        self.included.append((prefix, router))


# ---------------------------------------------------------------- numpy-based "ML" stand-ins
def _tokens(text):
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


class SentenceTransformer:
    def __init__(self, name):
        self.name = name

    def encode(self, texts, convert_to_numpy=True, **kw):
        single = isinstance(texts, str)
        texts = [texts] if single else texts
        out = np.zeros((len(texts), 64), dtype="float32")
        for i, t in enumerate(texts):
            for tok in _tokens(t):
                out[i, zlib.crc32(tok.encode()) % 64] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] = out[i] / n * 6.0
        return out[0] if single else out


class CrossEncoder:
    def __init__(self, name):
        if STATE["no_mmarco"] and "mmarco" in name:
            raise OSError("model not found")
        self.name = name
        if "nli" in name.lower():
            labels = {0: "entailment", 1: "neutral", 2: "contradiction"} if "mdeberta" in name.lower() else {0: "contradiction", 1: "entailment", 2: "neutral"}
            self.model = types.SimpleNamespace(config=types.SimpleNamespace(id2label=labels))
            self.labels = labels
        else:
            self.model, self.labels = None, None

    def predict(self, pairs, batch_size=8):
        if self.labels is None:
            return [float(len(set(_tokens(a)) & set(_tokens(b)))) for a, b in pairs]
        out = []
        for premise, hyp in pairs:
            ht = set(_tokens(hyp)) - {"the", "a", "of", "in", "was", "is"}
            overlap = len(ht & set(_tokens(premise))) / max(1, len(ht))
            vals = {"entailment": 6 * overlap - 3, "contradiction": (3.0 if " never " in f" {hyp.lower()} " else -2.0) - 2 * overlap, "neutral": 0.5}
            out.append([vals[self.labels[i]] for i in range(3)])
        return out


class FakeIndex:
    def __init__(self, vecs):
        self.vecs, self.ntotal = vecs, len(vecs)

    def search(self, qv, k):
        d = ((self.vecs - qv[0]) ** 2).sum(axis=1)
        order = np.argsort(d)[:k]
        return np.array([d[order]]), np.array([order])


def read_index(path):
    return FakeIndex(SentenceTransformer("stub").encode(STATE["chunk_texts"]))


# ---------------------------------------------------------------- Groq (scripted LLM)
def llm_reply(prompt):
    ov = STATE["llm_override"]
    if ov:
        return ov(prompt)
    if "Standalone question:" in prompt:
        return "Who was Hannibal Barca and what were his wars?"
    if "Hanni says:" in prompt:
        return "Hannibal was a brave general from Carthage! 🐘 He crossed the big mountains with elephants.\n🌟 Wow fact: He used elephants in his army. Do you want to hear about the Alps?"
    if "Research question:" in prompt:
        if "first draft of this answer" in prompt:
            return "## Summary\nHannibal Barca was born in 247 BC [1].\n## Evidence\n- He was born in Carthage [1].\n## Limits and open questions\nDates are approximate."
        return ("## Summary\nHannibal Barca was a Carthaginian general [1].\n## Evidence\n- He was born in 247 BC [1].\n"
                "- He crossed the Alps with war elephants [2][3].\n- He never lost a battle in Africa [9].\n- He founded the city of Rome in 500 BC [1].\n## Limits and open questions\nSome dates are approximate.")
    if "multiple-choice" in prompt:
        n = prompt.count('"..."') - 2  # options placeholders in the JSON template
        opts = [f"Option {i}" for i in range(max(3, min(4, n)))]
        return json.dumps({"question": "Which city did Hannibal come from?", "options": ["Carthage"] + opts[:len(opts) - 1], "index_correct": 0, "explication": "He was born in Carthage."})
    if "clearly TRUE or clearly FALSE" in prompt:
        return '{"statement": "Hannibal used elephants.", "answer": true, "explanation": "Yes, he did!"}'
    if "Extract the dated events" in prompt:
        return '```json\n[{"year": -247, "label": "Hannibal is born", "source": 1}, {"year": -218, "label": "He crosses the Alps", "source": 2}, {"year": "x", "label": "bad"}]\n```'
    if prompt.startswith("Compare "):
        return json.dumps({"summary": "Both were great powers [1].", "similarities": ["Both were cities [1]"],
                           "differences": [{"aspect": "Place", "a": "Africa [1]", "b": "Europe [2]"}], "caveats": ["Limited data"]})
    if "Write a short, warm and funny story" in prompt:
        return '{"title": "Hanni in Carthage", "story": "Hanni walked to Carthage. It was sunny!\\n🌟 Real fact: Carthage was founded long ago."}'
    if "riddle-style clue" in prompt:
        return "I am a place with a huge stone mountain made by pharaoh workers."
    if "Did you know?" in prompt:
        return "Did you know? Hannibal had elephants! 🐘"
    if prompt.startswith("Translate this text"):
        return "[translated] " + prompt.split("\n\n", 1)[-1]
    if "You are a strict evaluator" in prompt:
        return "NOTE: 8\nJUSTIFICATION: Good."
    return "Hannibal was a general [1]. He crossed the Alps [2]. Nothing else is known [9]."


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content=None, delta=None):
        self.message = _Msg(content)
        self.delta = types.SimpleNamespace(content=delta)


class _Completions:
    def create(self, model=None, max_tokens=None, messages=None, stream=False, temperature=None, seed=None, reasoning_effort=None):
        if reasoning_effort is not None and STATE.get("reject_effort"):
            raise TypeError("unexpected keyword argument 'reasoning_effort'")
        prompt = messages[0]["content"]
        STATE["llm_calls"].append({"prompt": prompt, "max_tokens": max_tokens, "stream": stream, "temperature": temperature, "effort": reasoning_effort, "model": model})
        if STATE["empty_first"] > 0 and not stream:
            STATE["empty_first"] -= 1
            return types.SimpleNamespace(choices=[_Choice("")])
        text = llm_reply(prompt)
        if stream:
            third = max(1, len(text) // 3)
            parts = [text[:third], text[third:2 * third], text[2 * third:]]
            return iter([types.SimpleNamespace(choices=[_Choice(delta=p)]) for p in parts])
        return types.SimpleNamespace(choices=[_Choice(text)])


class Groq:
    def __init__(self, api_key=None):
        self.chat = types.SimpleNamespace(completions=_Completions())


class GoogleTranslator:
    def __init__(self, source="auto", target="en"):
        self.target = target

    def translate(self, text):
        return f"({self.target}) {text}"


class Communicate:
    def __init__(self, text, voice, rate="+0%"):
        STATE.setdefault("tts", []).append((voice, rate))
        if voice == "en-US-AnaNeural" and STATE.get("tts_kids_fails"):
            raise RuntimeError("voice unavailable")

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"ID3-fake-mp3"}


def install(chunk_rows):
    """chunk_rows: list of dicts for the chunks table. Must be called before importing engine/api."""
    path = fakedb.make_connect()
    conn = path()
    cur = conn.cursor()
    cur.execute("CREATE TABLE chunks (id VARCHAR(255) PRIMARY KEY, texte TEXT, titre_article VARCHAR(255), source VARCHAR(500), position INT, lang VARCHAR(5), source_type VARCHAR(40))")
    cur.execute("CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, date_creation DATETIME DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE magic_tokens (token VARCHAR(255) PRIMARY KEY, email VARCHAR(255), date_expiration DATETIME, utilise BOOLEAN DEFAULT FALSE)")
    for i, r in enumerate(chunk_rows):
        cur.execute("INSERT INTO chunks (id, texte, titre_article, source, position, lang, source_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (r["id"], r["texte"], r["titre"], r["source"], i, r["lang"], r["source_type"]))
    conn.commit()
    conn.close()
    STATE["chunk_texts"] = [r["texte"] for r in chunk_rows]

    connector = _module("mysql.connector", connect=lambda **kw: path())
    _module("mysql", connector=connector)
    _module("faiss", read_index=read_index)
    _module("sentence_transformers", SentenceTransformer=SentenceTransformer, CrossEncoder=CrossEncoder)
    _module("groq", Groq=Groq)
    _module("deep_translator", GoogleTranslator=GoogleTranslator)
    _module("edge_tts", Communicate=Communicate)
    _module("pydantic", BaseModel=BaseModel)
    _module("fastapi", APIRouter=APIRouter, Depends=lambda fn: Dep(fn), FastAPI=FastAPI, HTTPException=HTTPException, Request=Request, Response=Response)
    _module("fastapi.middleware", )
    _module("fastapi.middleware.cors", CORSMiddleware=object)
    _module("fastapi.responses", StreamingResponse=StreamingResponse)
    return path
