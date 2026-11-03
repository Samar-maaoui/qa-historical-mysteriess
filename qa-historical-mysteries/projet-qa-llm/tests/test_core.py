import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


class TestSearch(unittest.TestCase):
    def test_tokenize_accents_and_stopwords(self):
        self.assertEqual(core.tokenize("Who built the Pyramide de Gizeh in 2560?"), ["built", "pyramide", "gizeh", "2560"])

    def test_bm25_prefers_matching_document(self):
        docs = [core.tokenize(t) for t in ["Hannibal crossed the Alps with elephants", "Pompeii was buried by Vesuvius", "Carthage was a Phoenician city"]]
        bm = core.BM25(docs)
        self.assertEqual(bm.top(core.tokenize("elephants Alps"), 3)[0][0], 0)
        self.assertEqual(bm.top(core.tokenize("vesuvius"), 1)[0][0], 1)
        self.assertEqual(bm.top(["unknownword"], 3), [])

    def test_rrf_rewards_agreement(self):
        fused = core.rrf_fuse([[1, 2, 3], [3, 1, 4]])
        self.assertEqual([i for i, _ in fused][:2], [1, 3])
        self.assertEqual({i for i, _ in fused}, {1, 2, 3, 4})

    def test_rrf_weights(self):
        fused = core.rrf_fuse([[1, 2], [2, 1]], weights=[1.0, 3.0])
        self.assertEqual(fused[0][0], 2)

    def test_query_expansion(self):
        idx = core.build_title_index({"Grande Pyramide de Gizeh": "Great Pyramid of Giza", "Hannibal Barca": "Hannibal Barca",
                                      "Grande Mosquée de Kairouan": "Great Mosque of Kairouan", "Kairouan": "Kairouan"})
        self.assertIn("Grande Pyramide de Gizeh", core.expand_query("How tall is the pyramid?", idx))
        self.assertIn("Hannibal Barca", core.expand_query("what did hannibal do", idx))
        self.assertEqual(core.expand_query("What is the weather like?", idx), [])
        self.assertIn("Kairouan", core.expand_query("Tell me about Kairouan", idx))

    def test_contextual_query(self):
        idx = core.build_title_index({"Hannibal Barca": "Hannibal Barca", "Machu Picchu": "Machu Picchu"})
        hist = [{"question": "Who was Hannibal?", "reponse": "..."}]
        self.assertEqual(core.contextual_query("and his wars?", hist, idx), "Who was Hannibal? and his wars?")
        self.assertEqual(core.contextual_query("What about Machu Picchu?", hist, idx), "What about Machu Picchu?")
        self.assertEqual(core.contextual_query("and his wars?", [], idx), "and his wars?")
        self.assertEqual(core.contextual_query("Explain the full history of the Punic wars in detail please", hist, idx),
                         "Explain the full history of the Punic wars in detail please")

    def test_diversify_limits_per_group(self):
        items = [("a", 1), ("a", 2), ("a", 3), ("a", 4), ("b", 5)]
        out = core.diversify(items, 5, per_group=2, key=lambda x: x[0])
        self.assertEqual(out, [("a", 1), ("a", 2), ("b", 5)])


class TestCitations(unittest.TestCase):
    def test_extract_and_strip(self):
        t = "Hannibal was born in 247 BC [1]. He crossed the Alps [2][3] and [1, 4]."
        self.assertEqual(core.extract_citations(t), [1, 2, 3, 1, 4])
        self.assertNotIn("[", core.strip_citations(t))

    def test_keep_valid(self):
        t = "A fact [1]. Another [9]. Mixed [2, 8]."
        out = core.keep_valid_citations(t, 3)
        self.assertEqual(core.extract_citations(out), [1, 2])
        self.assertNotIn("9", out)
        self.assertEqual(core.used_citations(t, 3), [1, 2])

    def test_split_sentences_marks_headings(self):
        text = "## Summary\nCarthage was founded in 814 BC [1]. It became a major power [2].\n\n**Evidence**\n- Hannibal was born there [1]\n- It fell in 146 BC [3].\n## Limits and open questions\nDates are approximate."
        parts = core.split_sentences(text)
        heads = [p["text"] for p in parts if p["heading"]]
        sents = [p["text"] for p in parts if not p["heading"]]
        self.assertEqual(heads, ["Summary", "Evidence", "Limits and open questions"])
        self.assertEqual(len(sents), 5)
        self.assertEqual(parts[1]["cites"], [1])
        self.assertEqual([p["text"] for p in parts if p["meta"]], ["Dates are approximate."])  # commentary is never scored

    def test_citation_after_full_stop_is_reattached(self):
        parts = core.split_sentences("Carthage fell in 146 BC. [3] Rome won the war.")
        self.assertEqual(parts[0]["cites"], [3])
        self.assertEqual(parts[1]["cites"], [])

    def test_short_plain_line_is_heading(self):
        self.assertTrue(core.is_heading_line("Key facts"))
        self.assertFalse(core.is_heading_line("- Key facts"))
        self.assertFalse(core.is_heading_line("The pyramid was built around 2560 BC."))


class TestLLMOutput(unittest.TestCase):
    def test_extract_json(self):
        self.assertEqual(core.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(core.extract_json('Sure! [{"x": 2}] hope it helps'), [{"x": 2}])
        self.assertIsNone(core.extract_json("no json here"))
        self.assertIsNone(core.extract_json(""))

    def test_refusal(self):
        for t in ["I do not know.", "I don't know the answer.", "The context does not mention this.", "Hmm, I don't know that one yet! 🤔",
                  "This is not mentioned in the passages.", "No information about Gandhi is available."]:
            self.assertTrue(core.is_refusal(t), t)
        for t in ["Hannibal was a Carthaginian general [1].", "The pyramid is 146 m tall."]:
            self.assertFalse(core.is_refusal(t), t)


class TestTimeline(unittest.TestCase):
    def test_parse_year(self):
        cases = {247: 247, "247 BC": -247, "c. 1200": 1200, "79 AD": 79, "-146": -146, "146 BCE": -146, "1881": 1881, 2.0: 2}
        for raw, want in cases.items():
            self.assertEqual(core.parse_year(raw), want, raw)
        self.assertIsNone(core.parse_year("unknown"))
        self.assertIsNone(core.parse_year(None))

    def test_format_year(self):
        self.assertEqual(core.format_year(-247), "247 BC")
        self.assertEqual(core.format_year(79), "79 AD")
        self.assertEqual(core.format_year(1881), "1881")

    def test_clean_events(self):
        raw = [{"year": "146 BC", "label": "Carthage destroyed [3]", "source": 3},
               {"year": -247, "label": "Hannibal born", "source": 1},
               {"year": -247, "label": "Hannibal born", "source": 1},
               {"year": "soon", "label": "bad year"}, {"year": 1881, "label": ""}, "junk",
               {"year": 814, "label": "Late event", "source": 99}]
        ev = core.clean_events(raw, n_passages=4)
        self.assertEqual([e["year"] for e in ev], [-247, -146, 814])
        self.assertEqual(ev[1]["label"], "Carthage destroyed")
        self.assertEqual(ev[1]["source"], 3)
        self.assertIsNone(ev[2]["source"])
        self.assertEqual(core.clean_events({"events": raw[:1]}, 4)[0]["year_label"], "146 BC")
        self.assertEqual(core.clean_events("nonsense"), [])


class TestGames(unittest.TestCase):
    def test_haversine(self):
        self.assertAlmostEqual(core.haversine_km(36.8531, 10.3233, 36.8531, 10.3233), 0, places=3)
        d = core.haversine_km(36.8531, 10.3233, 41.9028, 12.4964)  # Carthage - Rome
        self.assertTrue(550 < d < 650, d)

    def test_stars_always_at_least_one(self):
        self.assertEqual(core.stars_for_distance(10), 3)
        self.assertEqual(core.stars_for_distance(800), 2)
        self.assertEqual(core.stars_for_distance(12000), 1)
        self.assertIn("hot", core.hot_or_cold(10).lower())

    def test_clue_leak_detection(self):
        self.assertTrue(core.clue_leaks("I am the Great Pyramid of Giza!", ["Great Pyramid of Giza"]))
        self.assertFalse(core.clue_leaks("I am a huge stone mountain made by pharaoh workers.", ["Great Pyramid of Giza", "Grande Pyramide de Gizeh"]))


class TestStudyTools(unittest.TestCase):
    def test_leitner(self):
        self.assertEqual(core.next_box(1, True), 2)
        self.assertEqual(core.next_box(5, True), 5)
        self.assertEqual(core.next_box(4, False), 1)
        now = datetime(2026, 10, 31, 12, 0)
        self.assertEqual(core.due_date(now, 3).day, 3)  # 3 days later -> Nov 3
        self.assertEqual(core.due_date(now, 1), now)

    def test_streak(self):
        self.assertEqual(core.update_streak(2, 5, True), (3, 5))
        self.assertEqual(core.update_streak(5, 5, True), (6, 6))
        self.assertEqual(core.update_streak(4, 5, False), (0, 5))

    def test_badges(self):
        self.assertEqual(core.award_badges({}), [])
        got = core.award_badges({"questions": 10, "quiz_correct": 5, "best_streak": 5, "stars": 20, "games": 5, "stories": 3})
        self.assertEqual(set(got), {"first_question", "curious_cat", "quiz_rookie", "streak_5", "star_collector", "map_explorer", "story_lover"})
        self.assertTrue(all(b in core.BADGES for b in got))


class TestSafetyAndMisc(unittest.TestCase):
    def test_kid_unsafe(self):
        self.assertTrue(core.kid_unsafe("show me porn"))
        self.assertTrue(core.kid_unsafe("How to build a bomb?"))
        self.assertFalse(core.kid_unsafe("How did Hannibal's elephants cross the Alps?"))
        self.assertFalse(core.kid_unsafe("Tell me about the Sphinx"))  # no false positive on substrings

    def test_nettoyer_and_truncate(self):
        self.assertEqual(core.nettoyer("## Title\n- **Bold** fact [1]."), "Title\nBold fact.")
        self.assertEqual(core.truncate("one two three four", 9), "one two…")
        self.assertEqual(core.truncate("short", 20), "short")

    def test_softmax(self):
        r = core.softmax_rows([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        self.assertAlmostEqual(sum(r[0]), 1.0)
        self.assertAlmostEqual(r[0][0], 1 / 3)
        self.assertGreater(r[1][0], 0.99)


if __name__ == "__main__":
    unittest.main()
