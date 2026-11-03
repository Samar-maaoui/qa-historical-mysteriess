import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sources_parse as sp  # noqa: E402

ENTITY = {"labels": {"en": {"language": "en", "value": "Carthage"}}, "claims": {
    "P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 36.853, "longitude": 10.323, "precision": 0.0001}, "type": "globecoordinate"}}}],
    "P571": [{"mainsnak": {"datavalue": {"value": {"time": "-0814-00-00T00:00:00Z", "precision": 9}, "type": "time"}}}],
    "P576": [{"mainsnak": {"datavalue": {"value": {"time": "+0698-00-00T00:00:00Z", "precision": 7}, "type": "time"}}}],
    "P17": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q948"}, "type": "wikibase-entityid"}}}],
    "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q35127"}}}}, {"mainsnak": {"snaktype": "novalue"}}],
    "P757": [{"mainsnak": {"datavalue": {"value": "37", "type": "string"}}}]}}


class TestWikidataParsing(unittest.TestCase):
    def test_entity(self):
        f = sp.parse_entity(ENTITY)
        self.assertEqual(f["label"], "Carthage")
        self.assertEqual(f["coordinates"], {"lat": 36.853, "lon": 10.323})
        self.assertEqual(f["inception"], {"year": -814, "label": "814 BC", "precision": 9})
        self.assertEqual(f["dissolved"]["label"], "c. 698 AD")        # precision 7 = century: approximate
        self.assertEqual(f["country_ids"], ["Q948"])
        self.assertEqual(f["instance_ids"] if "instance_ids" in f else f["instance_of_ids"], ["Q35127"])
        self.assertEqual(f["unesco_id"], "37")

    def test_labels_are_resolved(self):
        f = sp.resolve_labels(sp.parse_entity(ENTITY), {"Q948": "Tunisia", "Q35127": "website"})
        self.assertEqual(f["country"], ["Tunisia"])
        self.assertNotIn("country_ids", f)
        resp = {"entities": {"Q948": {"labels": {"en": {"value": "Tunisia"}}}, "Q1": {"labels": {}}}}
        self.assertEqual(sp.labels_from_entities(resp), {"Q948": "Tunisia", "Q1": "Q1"})

    def test_time_edge_cases(self):
        self.assertIsNone(sp.parse_time({}))
        self.assertEqual(sp.parse_time({"time": "+1881-00-00T00:00:00Z", "precision": 9})["label"], "1881")

    def test_missing_properties_are_skipped(self):
        self.assertEqual(sp.parse_entity({"claims": {}}), {"label": None})


class TestMediaWikiParsing(unittest.TestCase):
    def test_pageprops_search_and_extracts(self):
        self.assertEqual(sp.qid_from_pageprops({"query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q6343"}}}}}), "Q6343")
        self.assertIsNone(sp.qid_from_pageprops({"query": {"pages": {"-1": {"missing": ""}}}}))
        self.assertEqual(sp.search_titles({"query": {"search": [{"title": "Histoire de Carthage"}, {"title": "Carthage"}]}}), ["Histoire de Carthage", "Carthage"])
        self.assertEqual(sp.extract_from_query({"query": {"pages": {"9": {"title": "T", "extract": "Texte"}}}}), ("T", "Texte"))
        self.assertEqual(sp.extract_from_query({"query": {"pages": {"9": {"title": "T"}}}}), (None, ""))

    def test_html_to_text(self):
        html = "<p>Un&nbsp;texte <b>gras</b> &amp; plus.</p><script>x()</script><p>Fin</p>"
        self.assertEqual(sp.html_to_text(html), "Un texte gras & plus.\nFin")


if __name__ == "__main__":
    unittest.main()
