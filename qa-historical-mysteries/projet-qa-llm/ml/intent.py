"""Question-intent router: factual / explain / compare / timeline / off_topic.
TF-IDF + softmax regression in numpy. It is trained on template questions and MEASURED on two things:
templates never seen in training, and 40 hand-written questions with different wording."""
import json
import os
import random
import re

import numpy as np

from ml.linear import SoftmaxRegression, accuracy
from ml.text import Tfidf

INTENTS = ["factual", "explain", "compare", "timeline", "off_topic"]

ENTITIES = ["Carthage", "Hannibal Barca", "the Great Pyramid of Giza", "Machu Picchu", "Pompeii", "Petra", "Kairouan", "Habib Bourguiba",
            "Stonehenge", "Angkor Wat", "the Punic Wars", "the French protectorate of Tunisia", "Dougga", "El Jem", "Easter Island",
            "the Maya civilization", "the Great Mosque of Kairouan", "Atlantis", "the Hafsid dynasty", "the Tunisian revolution",
            "Teotihuacan", "the Colossus of Rhodes", "Utica", "Kerkouane", "Gobekli Tepe"]
OFF_SUBJECTS = ["a chocolate cake", "a python script", "my cover letter", "the weather tomorrow", "a football match", "my laptop",
                "a tomato sauce", "a job interview", "my math homework", "a bitcoin wallet", "a workout plan", "a birthday gift",
                "a pizza dough", "my phone battery", "a holiday in Spain", "a spreadsheet formula"]

TEMPLATES = {
    "factual": ["When was {a} built or founded?", "Where is {a} located?", "Who built {a}?", "In which year did {a} happen?", "What is {a}?",
                "Who was the founder of {a}?", "How big is {a}?", "Which country is {a} in?", "What is the date of {a}?",
                "How old is {a}?", "What is the name of the king linked to {a}?", "How many people lived in {a}?",
                "What year was {a}?", "Which civilization created {a}?", "What material was {a} made of?", "Who discovered {a}?"],
    "explain": ["Why did {a} happen?", "How did {a} work?", "What caused {a}?", "Explain {a} to me.", "Why is {a} important?",
                "How was {a} organised?", "What was the role of {a}?", "What is the significance of {a}?", "Describe {a} in detail.",
                "Tell me about {a}.", "What were the consequences of {a}?", "How did {a} influence history?",
                "What was life like in {a}?", "Can you explain what {a} meant for people at the time?", "What led to {a}?", "In what way did {a} matter?"],
    "compare": ["Compare {a} and {b}.", "What is the difference between {a} and {b}?", "{a} versus {b}", "How are {a} and {b} similar?",
                "{a} or {b}: which is older?", "What do {a} and {b} have in common?", "Contrast {a} with {b}.", "Which is bigger, {a} or {b}?",
                "How does {a} differ from {b}?", "Is {a} older than {b}?", "{a} vs {b}", "Similarities and differences between {a} and {b}"],
    "timeline": ["Give me a timeline of {a}.", "What are the key events in the history of {a}, in order?", "Chronology of {a}.",
                 "What happened to {a} over time?", "List the main dates of {a}.", "How did {a} evolve through the centuries?",
                 "Summarise the history of {a} step by step.", "What is the sequence of events of {a}?", "Show the major milestones of {a}.",
                 "What happened before and after {a}?", "Walk me through the history of {a}.", "Main dates and events of {a}",
                 "What are the key dates of {a}?", "Give me the story of {a} from start to end.", "Order the main events of {a}.", "How did {a} change across the years?"],
    "off_topic": ["How do I make {x}?", "Can you help me with {x}?", "What is the best way to prepare {x}?", "Write {x} for me.",
                  "Give me tips about {x}.", "I need advice on {x}.", "Fix {x}.", "What do you think about {x}?", "Where can I buy {x}?",
                  "How much does {x} cost?", "Recommend something for {x}.", "Show me how to organise {x}.",
                  "Tell me a joke about {x}.", "What is the best {x} to buy?", "Help me choose {x}.", "Is {x} a good idea?", "Can you translate {x} for me?"],
}

# hand-written, differently worded questions: the fair estimate of real-life accuracy
REAL_STYLE = [
    ("When was Machu Picchu built?", "factual"), ("Where is Petra located?", "factual"), ("Who founded Kairouan?", "factual"),
    ("How tall is the Great Pyramid?", "factual"), ("What year did Tunisia become independent?", "factual"),
    ("Which king ordered the building of Angkor Wat?", "factual"), ("What is the capital of the Hafsid dynasty?", "factual"),
    ("Why did Carthage lose the Punic Wars?", "explain"), ("How did the pyramids get built?", "explain"),
    ("What caused the Tunisian revolution?", "explain"), ("Explain the importance of Kairouan.", "explain"),
    ("How did Hannibal manage to cross the Alps?", "explain"), ("Tell me about the Maya.", "explain"),
    ("What was life like in Pompeii?", "explain"),
    ("What is the difference between Dougga and El Jem?", "compare"), ("Carthage versus Utica", "compare"),
    ("Compare Hannibal and Bourguiba", "compare"), ("How are Petra and Machu Picchu similar?", "compare"),
    ("Which is older, Stonehenge or the Great Pyramid?", "compare"), ("Are Kairouan and Carthage alike in any way?", "compare"),
    ("Pompeii or Petra, which one is bigger?", "compare"),
    ("Give me a timeline of Carthage", "timeline"), ("What happened in Tunisia between 1881 and 1956?", "timeline"),
    ("List the main events of the Punic Wars in order", "timeline"), ("Chronology of the French protectorate", "timeline"),
    ("What is the history of Kairouan from its foundation?", "timeline"), ("Walk me through the key dates of Hannibal's life", "timeline"),
    ("How did Easter Island change over the centuries?", "timeline"),
    ("What's a good recipe for couscous?", "off_topic"), ("How do I fix a Python error?", "off_topic"),
    ("Who won the football match yesterday?", "off_topic"), ("What is the weather in Tunis?", "off_topic"),
    ("Can you help me write a cover letter?", "off_topic"), ("What is the best smartphone to buy?", "off_topic"),
    ("How do I lose weight quickly?", "off_topic"), ("Tell me a joke", "off_topic"), ("Translate this sentence into Spanish for me", "off_topic"),
]

_RULES = [
    ("compare", re.compile(r"\b(vs\.?|versus|compare|comparison|differences?|differ|similar|similarities|in common|contrast)\b", re.I)),
    ("timeline", re.compile(r"\b(timeline|chronolog\w*|key events|main events|milestones|in order|sequence of events|over time|centuries)\b", re.I)),
]


def _fill(template, rng):
    a, b = rng.sample(ENTITIES, 2)
    return template.format(a=a, b=b, x=rng.choice(OFF_SUBJECTS))


def make_dataset(templates, seed=0, per_template=14):
    rng = random.Random(seed)
    texts, labels = [], []
    for intent, ts in templates.items():
        for t in ts:
            for _ in range(per_template):
                texts.append(_fill(t, rng))
                labels.append(INTENTS.index(intent))
    return texts, np.array(labels)


def split_templates(seed=0, test_fraction=0.25):
    rng = random.Random(seed)
    train, test = {}, {}
    for intent, ts in TEMPLATES.items():
        ts = list(ts)
        rng.shuffle(ts)
        n_test = max(1, round(len(ts) * test_fraction))
        test[intent], train[intent] = ts[:n_test], ts[n_test:]
    return train, test


def _fit(texts, labels):
    tfidf = Tfidf(min_df=2).fit(texts)
    model = SoftmaxRegression(len(INTENTS), l2=2e-3, lr=0.2, epochs=500).fit(tfidf.transform(texts), labels)
    return tfidf, model


def train(seed=0):
    """Returns (model dict, metrics). The metrics come from templates the model never saw plus the hand-written set."""
    tr_t, te_t = split_templates(seed)
    Xtr, ytr = make_dataset(tr_t, seed)
    Xte, yte = make_dataset(te_t, seed + 1)
    tfidf, model = _fit(Xtr, ytr)
    held_out = accuracy(yte, model.predict(tfidf.transform(Xte)))
    # deployed model: all templates
    Xall, yall = make_dataset(TEMPLATES, seed + 2)
    tfidf, model = _fit(Xall, yall)
    texts = [t for t, _ in REAL_STYLE]
    truth = np.array([INTENTS.index(l) for _, l in REAL_STYLE])
    pred = model.predict(tfidf.transform(texts))
    per_class = {i: float(np.mean(pred[truth == k] == k)) for k, i in enumerate(INTENTS)}
    metrics = {"held_out_templates_accuracy": held_out, "hand_written_accuracy": accuracy(truth, pred),
               "hand_written_per_class": per_class, "n_train": len(Xall), "n_hand_written": len(REAL_STYLE)}
    return {"intents": INTENTS, "tfidf": tfidf.to_dict(), "model": model.to_dict(), "metrics": metrics}, metrics


class IntentRouter:
    def __init__(self, tfidf=None, model=None, metrics=None):
        self.tfidf, self.model, self.metrics = tfidf, model, metrics or {}

    @classmethod
    def load(cls, path):
        try:
            with open(path, encoding="utf8") as f:
                d = json.load(f)
            return cls(Tfidf.from_dict(d["tfidf"]), SoftmaxRegression.from_dict(d["model"]), d.get("metrics"))
        except Exception:
            return cls()  # keyword rules only

    def predict(self, text):
        text = (text or "").strip()
        if self.model is not None and text:
            probs = self.model.predict_proba(self.tfidf.transform([text]))[0]
            k = int(probs.argmax())
            return {"label": INTENTS[k], "p": round(float(probs[k]), 3), "source": "model"}
        for label, rule in _RULES:
            if rule.search(text):
                return {"label": label, "p": 0.6, "source": "rules"}
        return {"label": "factual", "p": 0.4, "source": "rules"}

    def p_off_topic(self, text):
        if self.model is None:
            return 0.0
        return float(self.model.predict_proba(self.tfidf.transform([text or ""]))[0][INTENTS.index("off_topic")])


def save(d, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf8") as f:
        json.dump(d, f)
