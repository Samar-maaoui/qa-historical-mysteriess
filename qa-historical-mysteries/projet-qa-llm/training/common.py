import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.getenv("TRAINING_DATA", os.path.join(ROOT, "training", "data"))
MODELS = os.getenv("MODEL_DIR", os.path.join(ROOT, "models"))   # same variable as the API
os.makedirs(DATA, exist_ok=True)
os.makedirs(MODELS, exist_ok=True)

PAIR_PROMPT = """Write {n} different questions that the passage below answers completely. Rules:
- the questions must be understandable WITHOUT the passage (name the subject, never say "the passage" or "the text");
- vary the type: a fact (who/when/where/how many), a reason (why/how), a comparison with something else;
- write them in {language}.

Passage about "{title}":
{text}

Reply STRICTLY as a JSON list of strings, with no text around it."""


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_chunks(path="chunks.json"):
    with open(os.path.join(ROOT, path), encoding="utf8") as f:
        return json.load(f)


def groq():
    from dotenv import load_dotenv
    from groq import Groq
    load_dotenv(os.path.join(ROOT, ".env"))
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def llm(client, prompt, max_tokens=600, temperature=0.4, model=None):
    """A reasoning model may spend the whole budget thinking: retry with a bigger one when the answer is empty."""
    for tokens in (max_tokens, max_tokens * 2, max_tokens * 4):
        r = client.chat.completions.create(model=model or os.getenv("LLM_MODEL", "openai/gpt-oss-20b"), max_tokens=tokens, temperature=temperature,
                                           messages=[{"role": "user", "content": prompt}])
        text = (r.choices[0].message.content or "").strip()
        if text:
            return text
    return ""
