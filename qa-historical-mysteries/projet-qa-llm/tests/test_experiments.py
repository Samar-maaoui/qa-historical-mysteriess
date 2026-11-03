import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "experiments"))
import metrics  # noqa: E402


class TestMetrics(unittest.TestCase):
    def test_fact_hit_text_and_accents(self):
        self.assertTrue(metrics.fact_hit("It was built for Khufu (Cheops).", ["Khéops", "Khufu"]))
        self.assertTrue(metrics.fact_hit("Les Nabatéens", ["Nabatéen"]))
        self.assertFalse(metrics.fact_hit("It was built by workers.", ["Khufu"]))

    def test_fact_hit_numbers_are_whole_numbers(self):
        self.assertTrue(metrics.fact_hit("Eruption in AD 79.", ["79"]))
        self.assertFalse(metrics.fact_hit("It happened in 1979.", ["79"]))
        self.assertFalse(metrics.fact_hit("It measured 79.5 metres.", ["79"]))
        self.assertTrue(metrics.fact_hit("About 146,58 m tall", ["146.58"]))
        self.assertTrue(metrics.fact_hit("a record until 1 311", ["1311"]))
        self.assertFalse(metrics.fact_hit("146.58 m", ["146"]))

    def test_retrieval_metrics(self):
        titles = ["Carthage", "Hannibal Barca", "Pompéi"]
        self.assertTrue(metrics.hit_at_k(titles, "Hannibal Barca", 3))
        self.assertFalse(metrics.hit_at_k(titles, "Hannibal Barca", 1))
        self.assertEqual(metrics.reciprocal_rank(titles, "Hannibal Barca"), 0.5)
        self.assertEqual(metrics.reciprocal_rank(titles, "Dougga"), 0.0)

    def test_misc(self):
        self.assertEqual(metrics.parse_note("NOTE: 8\nJUSTIFICATION: ok"), 8)
        self.assertEqual(metrics.parse_note("**NOTE:** 10/10"), 10)
        self.assertIsNone(metrics.parse_note(""))
        self.assertEqual(metrics.mean([1, None, 3]), 2)
        self.assertIsNone(metrics.mean([]))
        self.assertEqual(metrics.pct(0.756), "76%")

    def test_regression_compare(self):
        import regression
        base = {"fact_accuracy": 0.9, "refusal_out_of_corpus": 0.8, "premise_rejection": 0.6, "false_refusal_in_corpus": 0.02}
        self.assertEqual(regression.compare(dict(base), base), [])
        self.assertEqual(regression.compare({**base, "fact_accuracy": 0.86}, base), [])                     # within tolerance
        bad = regression.compare({**base, "fact_accuracy": 0.7, "false_refusal_in_corpus": 0.2}, base)
        self.assertEqual({b["metric"] for b in bad}, {"fact_accuracy", "false_refusal_in_corpus"})
        self.assertEqual(regression.compare({"fact_accuracy": None}, base), [])

    def test_adversarial_helpers(self):
        import adversarial
        ps = [{"n": 1, "texte": "Hannibal crossed the Alps."}]
        planted = adversarial.plant(ps, adversarial.ATTACKS[0])
        self.assertIn("PWNED", planted[0]["texte"])
        self.assertNotIn("PWNED", ps[0]["texte"])                       # the original passage is untouched
        self.assertTrue(adversarial.violates("PWNED", adversarial.ATTACKS[0]))
        self.assertFalse(adversarial.violates("Hannibal was a general [1].", adversarial.ATTACKS[0]))

    def test_question_set_is_well_formed(self):
        with open(os.path.join(os.path.dirname(HERE), "experiments", "questions_en.json"), encoding="utf8") as f:
            qs = json.load(f)
        self.assertEqual(len(qs), 88)
        self.assertEqual(len({q["id"] for q in qs}), 88)
        cats = {c: sum(1 for q in qs if q["category"] == c) for c in {q["category"] for q in qs}}
        self.assertEqual(cats, {"factual": 43, "french": 10, "arabic": 5, "followup": 8, "false_premise": 8, "out_of_corpus": 14})
        ins = [q for q in qs if q["type"] == "in_corpus"]
        self.assertEqual(len(ins), 66)
        self.assertTrue(all(q["keys"] and q["source"] and q["expected"] for q in ins))
        self.assertEqual(len({q["source"] for q in ins}), 31)  # every article of the corpus is covered
        self.assertTrue(all(q["history"] for q in qs if q["category"] == "followup"))
        self.assertTrue(all(q["keys"] for q in qs if q["category"] == "false_premise"))
        self.assertEqual(sum(1 for q in qs if q["core"]), 32)
        # every expected answer is recognised by its own key facts
        self.assertTrue(all(metrics.fact_hit(q["expected"], q["keys"]) for q in ins))


if __name__ == "__main__":
    unittest.main()
