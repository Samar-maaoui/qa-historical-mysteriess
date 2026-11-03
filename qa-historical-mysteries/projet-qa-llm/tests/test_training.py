import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import types
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, os.path.join(ROOT, "training")]

import build_topic_map  # noqa: E402
import eval_retrieval  # noqa: E402
import lora_raft  # noqa: E402
import make_pairs  # noqa: E402
import split_data  # noqa: E402
import common  # noqa: E402


def write(path, rows):
    with open(path, "w", encoding="utf8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


CHUNKS = [{"id": f"c{i}", "titre_article": f"Article {i % 6}", "texte": f"Passage number {i} about topic {i % 6}. " + "Long enough text for training. " * 15,
           "contexte": f"Article {i % 6} (EN)", "source_type": "Wikipedia (EN)"} for i in range(24)]


class FakeGroq:
    def __init__(self):
        self.calls = 0
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kw):
        self.calls += 1
        msg = types.SimpleNamespace(content='["What is the topic of the passage number?", "Why does the passage discuss this topic at length?"]')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class TestPairsAndSplits(unittest.TestCase):
    def test_make_pairs_writes_pairs_and_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeGroq()
            make_pairs.DATA, make_pairs.groq, make_pairs.load_chunks = d, lambda: fake, lambda: CHUNKS
            make_pairs.main(["--per-article", "4", "--pause", "0"])          # every passage of every article
            rows = common.read_jsonl(os.path.join(d, "pairs.jsonl"))
            self.assertEqual(len(rows), 24 * 2)                                 # 24 passages x 2 questions
            self.assertEqual({r["article"] for r in rows}, {f"Article {i}" for i in range(6)})
            calls = fake.calls
            make_pairs.main(["--per-article", "4", "--pause", "0"])          # restart: everything is already done
            self.assertEqual(fake.calls, calls)
            self.assertEqual(len(common.read_jsonl(os.path.join(d, "pairs.jsonl"))), 24 * 2)

    def test_split_data_has_no_leak(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [{"question": f"q{i}", "chunk_id": f"c{i}", "article": f"A{i % 10}"} for i in range(60)]
            write(os.path.join(d, "pairs.jsonl"), rows)
            split_data.DATA = d
            split_data.main()
            seen = {}
            for name in ("train", "val", "test"):
                for r in common.read_jsonl(os.path.join(d, f"{name}.jsonl")):
                    self.assertNotIn(seen.setdefault(r["article"], name), [n for n in ("train", "val", "test") if n != name])
            self.assertEqual(sum(len(common.read_jsonl(os.path.join(d, f"{n}.jsonl"))) for n in ("train", "val", "test")), 60)


class TestEvalAndMap(unittest.TestCase):
    def test_eval_retrieval_with_a_toy_encoder(self):
        def encode(texts):
            out = np.zeros((len(texts), 64))
            for i, t in enumerate(texts):
                for w in t.lower().replace(".", " ").split():
                    out[i, hash(w) % 64] += 1
            return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-9)
        qs = [{"question": f"Passage number {i} about topic {i % 6}", "chunk_id": f"c{i}"} for i in range(0, 24, 3)] + [{"question": "x", "chunk_id": "missing"}]
        r = eval_retrieval.evaluate(encode, CHUNKS, qs)
        self.assertEqual(r["n"], 8)
        self.assertGreater(r["recall@5"], 0.7)

    def test_topic_map(self):
        rng = np.random.default_rng(0)
        V = np.vstack([rng.normal(0, 0.2, (30, 8)), rng.normal(5, 0.2, (30, 8))])
        titles = ["Carthage"] * 30 + ["Pompéi"] * 30
        m = build_topic_map.build(V, titles, k=2)
        self.assertEqual(len(m["points"]), 60)
        self.assertEqual({c["label"] for c in m["clusters"]}, {"Carthage", "Pompeii"})
        self.assertTrue(all(-1.0001 <= p["x"] <= 1.0001 for p in m["points"]))
        self.assertEqual({c["size"] for c in m["clusters"]}, {30})

    def test_raft_rows(self):
        pairs_ = [{"question": "What is topic 1?", "chunk_id": "c1"}, {"question": "gone", "chunk_id": "missing"}]
        rows = lora_raft.prepare_rows(pairs_, CHUNKS, random.Random(0), lambda p: "An answer [1].", n_distractors=3, p_gold=1.0)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["has_gold"])
        self.assertIn("Passage number 1 about topic 1", rows[0]["prompt"])
        self.assertEqual(rows[0]["prompt"].count("(Source:"), 4)   # the right passage + 3 distractors
        rows = lora_raft.prepare_rows(pairs_[:1], CHUNKS, random.Random(0), lambda p: "never", p_gold=0.0)
        self.assertEqual(rows[0]["completion"], "I do not know based on these sources.")


SCRIPT = """
import sys
sys.path[:0] = [{root!r}, {tests!r}, {train!r}]
import stubs
from test_api_flow import ROWS
stubs.install(ROWS)
import {module} as script
script.main({argv!r})
"""


def run_script(module, argv, env):
    code = SCRIPT.format(root=ROOT, tests=HERE, train=os.path.join(ROOT, "training"), module=module, argv=argv)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180, env={**os.environ, **env}, cwd=ROOT)


class TestTrainingScriptsEndToEnd(unittest.TestCase):
    def test_confidence_model_is_trained_saved_and_picked_up_by_the_engine(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as models:
            env = {"TRAINING_DATA": data, "MODEL_DIR": models}
            with open(os.path.join(ROOT, "training", "data", "unanswerable.txt"), encoding="utf8") as f:
                with open(os.path.join(data, "unanswerable.txt"), "w", encoding="utf8") as g:
                    g.write(f.read())
            r = run_script("train_confidence", [], env)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:] + r.stdout[-800:])
            self.assertIn("AUC", r.stdout)
            self.assertIn("| High |", r.stdout)
            path = os.path.join(models, "confidence.json")
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf8") as f:
                meta = json.load(f)["meta"]
            self.assertEqual(meta["label"], "evidence_found")
            self.assertEqual(meta["embedding"], "paraphrase-multilingual-MiniLM-L12-v2")
            check = SCRIPT.format(root=ROOT, tests=HERE, train=os.path.join(ROOT, "training"), module="engine", argv=None).replace("script.main(None)", "print('LOADED', script.conf_model is not None)")
            r2 = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True, timeout=120, env={**os.environ, **env}, cwd=ROOT)
            self.assertIn("LOADED True", r2.stdout, r2.stderr[-800:])

    def test_nli_sheet_then_calibrator(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as models:
            env = {"TRAINING_DATA": data, "MODEL_DIR": models}
            r = run_script("label_nli", ["--n", "6", "--pause", "0"], env)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            with open(os.path.join(data, "nli_to_label.csv"), newline="", encoding="utf-8-sig") as f:
                self.assertGreaterEqual(len(list(csv.DictReader(f))), 1)
            # the student fills the sheet: supported sentences copy the passage, unsupported ones change the number
            rows = []
            for i in range(60):
                passage = f"Hannibal was born in {200 + i} BC in Carthage and led armies for decades."
                ok = i % 2 == 0
                sentence = f"Hannibal was born in {200 + i if ok else 900 + i} BC in Carthage."
                rows.append({"question": "q", "sentence": sentence, "passage": passage, "model_score": 0.8, "label": "1" if ok else "0"})
            with open(os.path.join(data, "nli_to_label.csv"), "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=["question", "sentence", "passage", "model_score", "label"])
                w.writeheader()
                w.writerows(rows)
            r = run_script("train_nli_calibrator", [], env)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:] + r.stdout[-500:])
            self.assertIn("calibrated", r.stdout)
            with open(os.path.join(models, "nli_calibrator.json"), encoding="utf8") as f:
                self.assertIn("mDeBERTa", json.load(f)["meta"]["nli"])

    def test_calibrator_refuses_to_train_on_too_few_labels(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as models:
            with open(os.path.join(data, "nli_to_label.csv"), "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=["question", "sentence", "passage", "model_score", "label"])
                w.writeheader()
                w.writerow({"question": "q", "sentence": "s", "passage": "p", "model_score": 0.5, "label": "1"})
            r = run_script("train_nli_calibrator", [], {"TRAINING_DATA": data, "MODEL_DIR": models})
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("label at least 40", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
