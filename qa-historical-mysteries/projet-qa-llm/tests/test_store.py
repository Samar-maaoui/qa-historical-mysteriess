import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fakedb  # noqa: E402
from store import Store  # noqa: E402

NOW = datetime(2026, 10, 31, 12, 0, 0)


class TestStore(unittest.TestCase):
    def setUp(self):
        self.s = Store(fakedb.make_connect())
        self.s.ensure_tables()
        self.s.ensure_tables()  # idempotent

    def test_history_roundtrip_and_ownership(self):
        hid = self.s.add_history("a@x.tn", "kids", "Who was Hannibal?", "An elephant general! " * 50, {"passages": [1, 2]}, "High", 18.3, False, NOW)
        self.assertEqual(self.s.add_history("b@x.tn", "standard", "q", "a", {}, "Low", 40.0, True, NOW) > hid, True)
        rows = self.s.list_history("a@x.tn")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mode"], "kids")
        self.assertLessEqual(len(rows[0]["answer"]), 601)
        self.assertEqual(self.s.get_history("a@x.tn", hid)["payload"], {"passages": [1, 2]})
        self.assertIsNone(self.s.get_history("b@x.tn", hid))  # not someone else's
        self.assertFalse(self.s.delete_history("b@x.tn", hid))
        self.assertTrue(self.s.star_history("a@x.tn", hid, True))
        self.assertEqual(len(self.s.list_history("a@x.tn", starred=True)), 1)
        self.assertEqual(len(self.s.list_history("a@x.tn", mode="standard")), 0)
        self.assertTrue(self.s.delete_history("a@x.tn", hid))
        self.assertEqual(self.s.list_history("a@x.tn"), [])

    def test_stats_and_streak(self):
        self.assertEqual(self.s.get_stats("a@x.tn", "kids")["stars"], 0)
        self.s.bump("a@x.tn", "kids", NOW, questions=2, stars=3)
        s = self.s.bump("a@x.tn", "kids", NOW, stars=2, games=1)
        self.assertEqual((s["questions"], s["stars"], s["games"]), (2, 5, 1))
        for ok in (True, True, False, True):
            s = self.s.record_quiz("a@x.tn", "kids", ok, NOW)
        self.assertEqual((s["quiz_total"], s["quiz_correct"], s["streak"], s["best_streak"]), (4, 3, 1, 2))
        self.assertEqual(self.s.get_stats("a@x.tn", "main")["quiz_total"], 0)  # scopes are separate

    def test_cards_leitner(self):
        cid, new = self.s.add_card("a@x.tn", "Who is Hanni?", "An elephant", "Hannibal Barca", "kids", NOW)
        self.assertTrue(new)
        self.assertEqual(self.s.add_card("a@x.tn", "Who is Hanni?", "x", "y", "kids", NOW), (cid, False))
        self.assertEqual(len(self.s.list_cards("a@x.tn", due_only=True, now=NOW)), 1)
        r = self.s.review_card("a@x.tn", cid, True, NOW)
        self.assertEqual(r["box"], 2)
        self.assertEqual(len(self.s.list_cards("a@x.tn", due_only=True, now=NOW)), 0)       # due tomorrow
        self.assertEqual(len(self.s.list_cards("a@x.tn", due_only=True, now=NOW + timedelta(days=1, minutes=1))), 1)
        self.assertEqual(self.s.review_card("a@x.tn", cid, False, NOW)["box"], 1)
        self.assertIsNone(self.s.review_card("b@x.tn", cid, True, NOW))
        self.assertTrue(self.s.delete_card("a@x.tn", cid))

    def test_admin_summary(self):
        self.s.log_query("standard", "Who was Gandhi?", "Low", 41.0, True, NOW)
        self.s.log_query("standard", "Who was Gandhi?", "Low", 40.0, True, NOW)
        self.s.log_query("kids", "Tell me about pyramids", "High", 14.0, False, NOW)
        self.s.log_query("standard", "old question", "Low", 50.0, True, NOW - timedelta(days=90))
        self.s.add_feedback("h1", None, 1, "great", "q", "kids", NOW)
        self.s.add_feedback("h2", None, -1, "wrong date", "q2", "standard", NOW)
        sm = self.s.admin_summary(NOW)
        self.assertEqual(sm["total"], 3)
        self.assertEqual(sm["by_mode"], {"standard": 2, "kids": 1})
        self.assertEqual(sm["refused"], 2)
        self.assertEqual(sm["unanswered"][0], {"question": "Who was Gandhi?", "count": 2})
        self.assertEqual(sm["feedback"], {"up": 1, "down": 1})
        self.assertEqual(len(sm["comments"]), 2)
        self.assertAlmostEqual(sm["avg_distance"], 31.67, places=2)


if __name__ == "__main__":
    unittest.main()
