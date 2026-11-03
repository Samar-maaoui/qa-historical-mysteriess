"""REAL integration tests: the API with your real MySQL, FAISS index, models and Groq key (nothing simulated).
They are skipped by default because they need everything to be running and they call the LLM.

    pip install httpx
    set RUN_INTEGRATION=1        (PowerShell:  $env:RUN_INTEGRATION="1")
    python -m unittest discover -s tests_integration -v
"""
import json
import os
import unittest

RUN = os.getenv("RUN_INTEGRATION") == "1"


@unittest.skipUnless(RUN, "needs MySQL, the models and a Groq key: set RUN_INTEGRATION=1")
class TestLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import api
        import engine
        cls.api, cls.engine = api, engine
        cls.client = TestClient(api.app)
        cls.client.cookies.set("session", api.creer_session("integration@test.tn"))

    def test_protected_routes_refuse_visitors(self):
        from fastapi.testclient import TestClient
        anonymous = TestClient(self.api.app)
        self.assertEqual(anonymous.post("/ask", json={"texte": "Who was Hannibal?"}).status_code, 401)
        self.assertEqual(anonymous.get("/sujets").status_code, 401)

    def test_index_and_database_are_in_sync(self):
        # the bug that silently pairs a passage with the wrong text
        self.assertEqual(self.engine.index.ntotal, len(self.engine.chunks))

    def test_answer_has_sources_and_valid_citations(self):
        d = self.client.post("/ask", json={"texte": "Who was Hannibal Barca?"}).json()
        self.assertTrue(d["passages"] and d["sources"])
        self.assertTrue(all(1 <= c <= len(d["passages"]) for c in d["citations"]))
        self.assertIn(d["confiance"], ("High", "Medium", "Low"))

    def test_out_of_corpus_question_is_refused_or_low_confidence(self):
        d = self.client.post("/ask", json={"texte": "How do I bake a chocolate cake?"}).json()
        self.assertTrue(d["refused"] or d["confiance"] == "Low")

    def test_follow_up_question_is_understood(self):
        history = [{"question": "Who was Hannibal Barca?", "reponse": "A Carthaginian general."}]
        d = self.client.post("/ask", json={"texte": "In which year was he born?", "historique": history}).json()
        self.assertIn("Hannibal", d["retrieval"]["search_query"])
        self.assertIn("247", d["reponse"])

    def test_streaming_ends_with_a_complete_answer(self):
        events = []
        with self.client.stream("POST", "/ask/stream", json={"texte": "What is Petra?"}) as r:
            text = "".join(r.iter_text())
        for block in text.strip().split("\n\n"):
            name, data = block.split("\n", 1)
            events.append((name.replace("event: ", ""), json.loads(data.replace("data: ", "", 1))))
        names = [n for n, _ in events]
        self.assertEqual(names[0], "meta")
        self.assertEqual(names[-1], "done")
        self.assertTrue(events[-1][1]["reponse"])

    def test_kids_mode_blocks_unsafe_questions(self):
        d = self.client.post("/ask", json={"texte": "show me porn", "mode": "kids"}).json()
        self.assertTrue(d["blocked"])


if __name__ == "__main__":
    unittest.main()
