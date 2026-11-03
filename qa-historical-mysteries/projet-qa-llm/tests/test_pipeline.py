"""Runs chunking.py and init_db.py on a tiny two-language corpus with offline stand-ins."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DRIVER = """
import runpy, sys, types, sqlite3
sys.path[:0] = [{root!r}, {tests!r}]
import fakedb

class Splitter:
    def __init__(self, **kw): pass
    def split_text(self, text): return [p for p in text.split("\\n\\n") if p.strip()]
sys.modules["langchain_text_splitters"] = types.SimpleNamespace(RecursiveCharacterTextSplitter=Splitter)

connect = fakedb.make_connect()
mysql = types.ModuleType("mysql"); connector = types.ModuleType("mysql.connector")
connector.connect = lambda **kw: connect()
mysql.connector = connector
sys.modules["mysql"], sys.modules["mysql.connector"] = mysql, connector

runpy.run_path({chunking!r}, run_name="__main__")
runpy.run_path({init_db!r}, run_name="__main__")
rows = connect().cursor(dictionary=True).execute("SELECT id, lang, source_type, position, section FROM chunks ORDER BY position").fetchall()
import json; print("ROWS=" + json.dumps(rows))
"""


def write_json(path, data):
    with open(path, "w", encoding="utf8") as fh:
        json.dump(data, fh)


class TestPipeline(unittest.TestCase):
    def test_two_language_corpus_is_chunked_and_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            fr = [{"titre": "Carthage", "contenu": "Paragraphe un assez long pour etre un paragraphe.\n\nHistoire\nParagraphe deux assez long aussi pour le test.", "source": "https://fr.wikipedia.org/wiki/Carthage"}]
            en = [{"titre": "Carthage", "titre_en": "Carthage", "contenu": "Paragraph one.\n\nParagraph two.\n\nParagraph three.",
                   "source": "https://en.wikipedia.org/wiki/Carthage", "lang": "en", "source_type": "Wikipedia (EN)"}]
            write_json(os.path.join(d, "corpus.json"), fr)
            write_json(os.path.join(d, "corpus_en.json"), en)
            code = DRIVER.format(root=ROOT, tests=HERE, chunking=os.path.join(ROOT, "chunking.py"), init_db=os.path.join(ROOT, "init_db.py"))
            r = subprocess.run([sys.executable, "-c", code], cwd=d, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            rows = json.loads(r.stdout.split("ROWS=")[1])
            self.assertEqual([x["id"] for x in rows], ["Carthage_0", "Carthage_1", "Carthage_en_0", "Carthage_en_1", "Carthage_en_2"])
            self.assertEqual([x["lang"] for x in rows], ["fr", "fr", "en", "en", "en"])
            self.assertEqual(rows[2]["source_type"], "Wikipedia (EN)")
            self.assertEqual([x["position"] for x in rows], [0, 1, 2, 3, 4])
            self.assertEqual([x["section"] for x in rows[:2]], ["", "Histoire"])      # the section is found for each passage
            with open(os.path.join(d, "chunks.json"), encoding="utf8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved[1]["contexte"], "Carthage > Histoire (Wikipedia (FR))")
            with open(os.path.join(d, "chunks.json"), encoding="utf8") as fh:
                chunks = json.load(fh)
            self.assertEqual(len(chunks), 5)

    def test_french_only_corpus_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "corpus.json"), [{"titre": "Pompéi", "contenu": "Un.\n\nDeux.", "source": "u"}])
            code = DRIVER.format(root=ROOT, tests=HERE, chunking=os.path.join(ROOT, "chunking.py"), init_db=os.path.join(ROOT, "init_db.py"))
            r = subprocess.run([sys.executable, "-c", code], cwd=d, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            rows = json.loads(r.stdout.split("ROWS=")[1])
            self.assertEqual([x["id"] for x in rows], ["Pompéi_0", "Pompéi_1"])


if __name__ == "__main__":
    unittest.main()
