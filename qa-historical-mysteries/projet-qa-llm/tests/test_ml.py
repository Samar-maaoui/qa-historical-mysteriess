import json
import os
import random
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
from ml import cluster, confidence, intent, linear, nli_cal, pairs, raft, sft, splits, text  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLinear(unittest.TestCase):
    def blobs(self, n=200, sep=2.5, seed=0):
        rng = np.random.default_rng(seed)
        X = np.vstack([rng.normal(0, 1, (n, 3)), rng.normal(sep, 1, (n, 3))])
        y = np.array([0] * n + [1] * n)
        return X, y

    def test_softmax_regression_learns_and_roundtrips(self):
        X, y = self.blobs()
        sc = linear.Standardizer().fit(X)
        m = linear.SoftmaxRegression(2, epochs=300).fit(sc.transform(X), y)
        p = m.predict_proba(sc.transform(X))
        self.assertGreater(linear.accuracy(y, p.argmax(1)), 0.93)
        self.assertGreater(linear.roc_auc(y, p[:, 1]), 0.97)
        m2 = linear.SoftmaxRegression.from_dict(json.loads(json.dumps(m.to_dict())))
        np.testing.assert_allclose(m2.predict_proba(sc.transform(X)), p)
        sc2 = linear.Standardizer.from_dict(json.loads(json.dumps(sc.to_dict())))
        np.testing.assert_allclose(sc2.transform(X), sc.transform(X))

    def test_metrics(self):
        self.assertEqual(linear.roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
        self.assertEqual(linear.roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]), 0.0)
        self.assertEqual(linear.roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]), 0.5)
        self.assertIsNone(linear.roc_auc([1, 1], [0.2, 0.3]))
        self.assertAlmostEqual(linear.expected_calibration_error([1, 1, 0, 0], [1.0, 1.0, 0.0, 0.0]), 0.0)
        self.assertAlmostEqual(linear.expected_calibration_error([1, 0, 1, 0], [0.5, 0.5, 0.5, 0.5]), 0.0)
        self.assertGreater(linear.expected_calibration_error([0, 0, 0, 0], [0.9, 0.9, 0.9, 0.9]), 0.8)
        self.assertAlmostEqual(linear.brier([1, 0], [1.0, 0.0]), 0.0)

    def test_stratified_folds_cover_everything_once(self):
        y = np.array([0] * 20 + [1] * 10)
        seen = []
        for tr, te in linear.stratified_kfold(y, 5):
            self.assertEqual(set(tr) & set(te), set())
            self.assertEqual(int((y[te] == 1).sum()), 2)
            seen += list(te)
        self.assertEqual(sorted(seen), list(range(30)))

    def test_reliability_table(self):
        rows = linear.reliability_table([1, 1, 0, 1, 0, 0], [0.9, 0.8, 0.5, 0.9, 0.1, 0.2])
        by = {r["band"]: r for r in rows}
        self.assertEqual(by["High"]["n"], 3)
        self.assertEqual(by["High"]["observed"], 1.0)
        self.assertEqual(by["Low"]["observed"], 0.0)


class TestSplitsAndCluster(unittest.TestCase):
    def test_split_by_group_has_no_leak(self):
        items = [{"article": f"A{i % 10}", "q": i} for i in range(100)]
        s = splits.split_by_group(items, lambda x: x["article"], seed=3)
        self.assertEqual(sum(len(v) for v in s.values()), 100)
        self.assertTrue(splits.assert_no_leak(s, lambda x: x["article"]))
        self.assertTrue(all(len(v) > 0 for v in s.values()))
        bad = {"train": [items[0]], "test": [items[10]]}  # items 0 and 10 share article A0
        with self.assertRaises(AssertionError):
            splits.assert_no_leak(bad, lambda x: x["article"])

    def test_kmeans_separates_blobs_and_pca_shape(self):
        rng = np.random.default_rng(1)
        X = np.vstack([rng.normal(0, 0.3, (40, 5)), rng.normal(6, 0.3, (40, 5))])
        labels, centers = cluster.kmeans(X, 2, seed=0)
        self.assertEqual(len(set(labels[:40])), 1)
        self.assertEqual(len(set(labels[40:])), 1)
        self.assertNotEqual(labels[0], labels[-1])
        self.assertEqual(cluster.pca2(X).shape, (80, 2))

    def test_tfidf_roundtrip(self):
        t = text.Tfidf(min_df=1).fit(["compare a and b", "timeline of a", "why did a happen"])
        t2 = text.Tfidf.from_dict(json.loads(json.dumps(t.to_dict())))
        np.testing.assert_allclose(t.transform(["compare a and b"]), t2.transform(["compare a and b"]))
        self.assertAlmostEqual(float(np.linalg.norm(t.transform(["timeline of a"])[0])), 1.0)


class TestIntent(unittest.TestCase):
    def test_training_reports_honest_numbers(self):
        _, m = intent.train()
        self.assertGreater(m["hand_written_accuracy"], 0.8)
        self.assertGreater(m["held_out_templates_accuracy"], 0.5)  # unseen phrasing is much harder: reported as such
        self.assertGreaterEqual(m["n_hand_written"], 30)

    def test_shipped_model_and_rule_fallback(self):
        r = intent.IntentRouter.load(os.path.join(ROOT, "models", "intent.json"))
        self.assertEqual(r.predict("Compare Carthage and Utica")["label"], "compare")
        self.assertEqual(r.predict("Give me a timeline of the Punic Wars")["label"], "timeline")
        self.assertEqual(r.predict("What is a good recipe for pizza dough?")["label"], "off_topic")
        self.assertGreater(r.p_off_topic("How do I fix my laptop?"), 0.5)
        self.assertLess(r.p_off_topic("Who was Hannibal Barca?"), 0.3)
        rules = intent.IntentRouter.load("/nonexistent/path.json")
        self.assertEqual(rules.predict("Pyramid vs Stonehenge")["label"], "compare")
        self.assertEqual(rules.predict("chronology of Carthage")["label"], "timeline")
        self.assertEqual(rules.predict("who built it")["source"], "rules")


class TestConfidence(unittest.TestCase):
    def synthetic(self, n=400, seed=0):
        rng = np.random.default_rng(seed)
        y = rng.integers(0, 2, n)
        d = np.where(y == 1, rng.normal(16, 3, n), rng.normal(27, 3, n))      # closer passages when the answer exists
        rr = np.where(y == 1, rng.normal(2.5, 1.0, n), rng.normal(-1.5, 1.0, n))
        X = np.column_stack([d, d - 2, np.full(n, 2.0), rr, rr - 0.2, rng.uniform(0, 1, n), rng.uniform(0.3, 1, n), rng.integers(3, 10, n), rng.uniform(0, 0.2, n)])
        return X, y

    def test_features_from_retrieval(self):
        passages = [{"titre": "A", "rerank": 3.0, "vec_rank": 1, "bm25_rank": 2}, {"titre": "A", "rerank": 2.0, "vec_rank": 2, "bm25_rank": None},
                    {"titre": "B", "rerank": 1.0, "vec_rank": None, "bm25_rank": 1}]
        f = confidence.features_from_retrieval([10, 12, 14], passages, 5, 0.1)
        self.assertEqual(len(f), len(confidence.FEATURES))
        self.assertEqual(f[0], 12.0)
        self.assertEqual(f[3], 3.0)
        self.assertAlmostEqual(f[5], 1 / 3)
        self.assertAlmostEqual(f[6], 2 / 3)
        empty = confidence.features_from_retrieval([], [], 0)
        self.assertEqual(len(empty), len(confidence.FEATURES))

    def test_calibration_on_known_signal(self):
        X, y = self.synthetic()
        model, report = confidence.CalibratedConfidence.train(X, y, meta={"embedding": "e", "reranker": "r"})
        self.assertGreater(report["auc"], 0.95)
        self.assertLess(report["ece"], 0.08)
        rel = {r["band"]: r for r in report["reliability"]}
        self.assertGreater(rel["High"]["observed"], 0.85)
        self.assertLess(rel["Low"]["observed"], 0.15)
        p_good = model.p(X[y == 1][0])
        p_bad = model.p(X[y == 0][0])
        self.assertGreater(p_good, p_bad)
        self.assertEqual(model.label(0.9), "High")
        self.assertEqual(model.label(0.5), "Medium")
        self.assertEqual(model.label(0.1), "Low")

    def test_save_and_load(self):
        import tempfile
        X, y = self.synthetic(200)
        model, _ = confidence.CalibratedConfidence.train(X, y, meta={"embedding": "e", "reranker": "r"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "conf.json")
            model.save(path)
            again = confidence.CalibratedConfidence.load(path)
        self.assertAlmostEqual(again.p(X[0]), model.p(X[0]))
        self.assertEqual(again.meta["embedding"], "e")


class TestNliCalibrator(unittest.TestCase):
    def test_numbers_and_overlap_features(self):
        f = nli_cal.features((0.9, 0.05, 0.05), "Hannibal was born in 247 BC.", "Hannibal est né en 247 av. J.-C. à Carthage.")
        self.assertEqual(f[4], 1.0)
        f2 = nli_cal.features((0.9, 0.05, 0.05), "Hannibal was born in 250 BC.", "Hannibal est né en 247 av. J.-C. à Carthage.")
        self.assertEqual(f2[4], 0.0)

    def test_calibrator_beats_the_raw_threshold_when_numbers_matter(self):
        rng = np.random.default_rng(0)
        n = 300
        number_ok = rng.integers(0, 2, n)
        ent = np.clip(rng.normal(0.8, 0.12, n), 0, 1)             # the raw NLI is confident even when a number is wrong
        y = number_ok.copy()                                        # truth: supported only when the number matches
        X = np.column_stack([ent, 1 - ent, np.zeros(n), rng.uniform(0.3, 0.9, n), number_ok, np.full(n, 0.5)])
        model, report = nli_cal.NliCalibrator.train(X, y)
        self.assertGreater(report["calibrated_accuracy"], report["raw_threshold_accuracy"] + 0.2)
        self.assertGreater(model.p(X[number_ok == 1][0]), 0.5)
        self.assertLess(model.p(X[number_ok == 0][0]), 0.5)


class TestRaft(unittest.TestCase):
    def test_gold_present_or_taught_to_refuse(self):
        gold = {"nom": "Hannibal", "texte": "Hannibal crossed the Alps."}
        distract = [{"nom": "Pompeii", "texte": "Vesuvius erupted."}, {"nom": "Petra", "texte": "Petra is in Jordan."}]
        with_gold = raft.build_raft_example("Who crossed the Alps?", gold, distract, random.Random(0), lambda p: "Hannibal [1].", p_gold=1.0)
        self.assertTrue(with_gold["has_gold"])
        self.assertIn("Hannibal crossed the Alps.", with_gold["prompt"])
        self.assertEqual(with_gold["completion"], "Hannibal [1].")
        self.assertIn(with_gold["gold_n"], (1, 2, 3))
        without = raft.build_raft_example("Who crossed the Alps?", gold, distract, random.Random(0), lambda p: "never called", p_gold=0.0)
        self.assertFalse(without["has_gold"])
        self.assertEqual(without["completion"], raft.REFUSAL)
        self.assertNotIn("Hannibal crossed the Alps.", without["prompt"])


class TestPairsAndSft(unittest.TestCase):
    CH = [{"id": "c0", "titre_article": "Carthage", "texte": "Carthage was founded by Phoenician settlers from Tyre.", "contexte": "Carthage (EN)"},
          {"id": "c1", "titre_article": "Pompéi", "texte": "Pompeii was buried by Vesuvius.", "contexte": "Pompeii (EN)"},
          {"id": "c2", "titre_article": "Tyr", "texte": "Tyre was a Phoenician city that founded colonies.", "contexte": "Tyre (EN)"}]

    def test_hard_negative_comes_from_another_article_and_looks_relevant(self):
        bm = core.BM25([core.tokenize(c["texte"]) for c in self.CH])
        rng = random.Random(0)
        for _ in range(10):
            i = pairs.hard_negative("Who founded Carthage? Phoenician settlers", bm, self.CH, "Carthage", rng)
            self.assertNotEqual(self.CH[i]["titre_article"], "Carthage")
        self.assertEqual(pairs.hard_negative("Phoenician colonies", bm, self.CH, "Carthage", random.Random(1)), 2)

    def test_triplets_keep_the_context_prefix(self):
        bm = core.BM25([core.tokenize(c["texte"]) for c in self.CH])
        tr = pairs.build_triplets([{"question": "Who founded Carthage?", "chunk_id": "c0"}, {"question": "x", "chunk_id": "missing"}], self.CH, bm, random.Random(0))
        self.assertEqual(len(tr), 1)
        self.assertTrue(tr[0]["positive"].startswith("Carthage (EN)\nCarthage was founded"))
        self.assertNotIn("Carthage was founded", tr[0]["negatives"][0])

    def test_retrieval_metrics(self):
        sim = np.array([[0.9, 0.1, 0.2], [0.1, 0.2, 0.9], [0.5, 0.4, 0.3]])
        m = pairs.retrieval_metrics(sim, [0, 1, {2}], ks=(1, 2))
        self.assertAlmostEqual(m["recall@1"], 1 / 3)
        self.assertAlmostEqual(m["recall@2"], 2 / 3)
        self.assertAlmostEqual(m["mrr"], (1 + 1 / 2 + 1 / 3) / 3)

    def test_sft_masks_the_prompt_and_pads(self):
        class Tok:
            eos_token = "</s>"

            def __call__(self, text, add_special_tokens=False):
                return {"input_ids": [ord(c) % 50 + 1 for c in text.replace("</s>", "#")]}
        ex = sft.tokenize_example(Tok(), "Q:", "AB")
        self.assertEqual(ex["labels"][:2], [-100, -100])
        self.assertEqual(len(ex["labels"]), len(ex["input_ids"]))
        self.assertNotIn(-100, ex["labels"][2:])
        self.assertEqual(len(sft.tokenize_example(Tok(), "x" * 10, "y" * 10, max_len=12)["input_ids"]), 12)
        batch = sft.pad_batch([ex, sft.tokenize_example(Tok(), "Q:", "ABCDE")], pad_id=0)
        self.assertEqual(len({len(r) for r in batch["input_ids"]}), 1)
        self.assertEqual(batch["attention_mask"][0][-1], 0)
        self.assertEqual(batch["labels"][0][-1], -100)


class TestRateLimiter(unittest.TestCase):
    def test_sliding_window(self):
        now = [0.0]
        rl = core.RateLimiter(2, window=60, clock=lambda: now[0])
        self.assertTrue(rl.allow("a") and rl.allow("a"))
        self.assertFalse(rl.allow("a"))
        self.assertTrue(rl.allow("b"))                       # each key has its own budget
        now[0] = 30
        self.assertFalse(rl.allow("a"))
        self.assertAlmostEqual(rl.retry_after("a"), 30)
        now[0] = 61
        self.assertTrue(rl.allow("a"))                       # the oldest hit left the window
        self.assertTrue(core.RateLimiter(0).allow("x"))      # 0 = unlimited


class TestNamesAndLimiter(unittest.TestCase):
    def test_names(self):
        self.assertEqual(core.clean_name("  Samar   Maaoui "), "Samar Maaoui")
        self.assertEqual(core.clean_name("<b>Sam</b>"), "b Sam /b")           # markup characters never survive
        self.assertIsNone(core.clean_name("S"))
        self.assertIsNone(core.clean_name("x" * 61))
        self.assertIsNone(core.clean_name(None))

    def test_limiter_helpers(self):
        now = [0.0]
        rl = core.RateLimiter(2, window=10, clock=lambda: now[0])
        self.assertFalse(rl.exhausted("k"))
        rl.allow("k"); rl.allow("k")
        self.assertTrue(rl.exhausted("k"))
        now[0] = 11
        self.assertFalse(rl.exhausted("k"))                                  # the window moved on
        rl.allow("k"); rl.allow("k")
        rl.reset("k")
        self.assertFalse(rl.exhausted("k"))


class TestCoreAdditions(unittest.TestCase):
    def test_years_in_text(self):
        self.assertEqual(core.years_in_text("Hannibal est né en 247 av. J.-C. à Carthage."), {-247})
        self.assertIn(-146, core.years_in_text("destroyed in 146 BC"))
        self.assertIn(79, core.years_in_text("l'éruption de l'an 79 de notre ère"))
        self.assertIn(79, core.years_in_text("in the year 79 AD"))
        self.assertIn(1881, core.years_in_text("le protectorat de 1881"))
        self.assertNotIn(146, core.years_in_text("une hauteur de 146,58 m"))
        self.assertNotIn(247, core.years_in_text("247 av. J.-C."))   # BC years are stored as negatives only
        self.assertTrue(core.year_in_texts(-247, ["né en 247 av. J.-C."]))
        self.assertFalse(core.year_in_texts(-250, ["né en 247 av. J.-C."]))
        self.assertTrue(core.year_in_texts(-250, ["né en 247 av. J.-C."], tolerance=5))

    def test_numbers_in(self):
        self.assertEqual(core.numbers_in("146,58 m et 1 311 ans, soit 79"), {"146.58", "1311", "79"})

    def test_sections(self):
        text = "Intro text that is long enough to be a paragraph.\n\nHistoire\nHannibal fut un général carthaginois très célèbre.\n\nVoir aussi\nListe des guerres.\n"
        offs = core.section_offsets(text)
        self.assertEqual([h for _, h in offs], ["Histoire", "Voir aussi"])
        self.assertEqual(core.section_at(offs, 0), "")
        self.assertEqual(core.section_at(offs, text.index("Hannibal fut")), "Histoire")
        self.assertEqual(core.section_at(offs, text.index("Liste")), "Voir aussi")

    def test_citation_precision_and_fixes(self):
        details = [{"phrase": "A", "cited": [1], "cite_ok": True, "best": 1, "soutenue": True},
                   {"phrase": "B", "cited": [3], "cite_ok": False, "best": 1, "soutenue": True},
                   {"phrase": "C", "cited": [], "cite_ok": None, "best": 2, "soutenue": True}, {"phrase": "H", "heading": True}]
        self.assertEqual(core.citation_precision(details), 0.5)
        self.assertEqual(core.citation_fixes(details), [("B", [3], 1)])
        self.assertIsNone(core.citation_precision([{"phrase": "C", "cited": [], "cite_ok": None}]))


if __name__ == "__main__":
    unittest.main()
