"""Extra sources, each one optional:

    python collect_sources.py wikidata     ->  wikidata.json   structured facts (dates, coordinates, country, UNESCO id)
    python collect_sources.py wikisource   ->  corpus_ws.json  period texts found on French Wikisource (experimental)

Run chunking.py, build_index.py and init_db.py afterwards for Wikisource. wikidata.json is read directly by the API."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import json
import sys
import time

import requests

import sources_parse as sp
from sites_data import nom_en

UA = {"User-Agent": "ProjetQA-LLM/1.0 (student project)"}


def get(url, **params):
    r = requests.get(url, params={**params, "format": "json"}, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def titles():
    with open("corpus.json", encoding="utf-8") as f:
        return [a["titre"] for a in json.load(f)]


def wikidata():
    qids = {}
    for t in titles():
        try:
            q = sp.qid_from_pageprops(get("https://fr.wikipedia.org/w/api.php", action="query", prop="pageprops", ppprop="wikibase_item", titles=t, redirects=1))
        except Exception as e:
            print("❌", t, repr(e))
            continue
        if q:
            qids[t] = q
        else:
            print("❌ no Wikidata item for", t)
        time.sleep(0.2)
    facts, wanted = {}, set()
    ids = list(qids.values())
    for i in range(0, len(ids), 40):
        resp = get("https://www.wikidata.org/w/api.php", action="wbgetentities", ids="|".join(ids[i:i + 40]), props="claims|labels", languages="en")
        for q, ent in resp.get("entities", {}).items():
            facts[q] = sp.parse_entity(ent)
            wanted |= set(facts[q].get("instance_of_ids", []) + facts[q].get("country_ids", []))
    labels = {}
    wanted = list(wanted)
    for i in range(0, len(wanted), 40):
        labels.update(sp.labels_from_entities(get("https://www.wikidata.org/w/api.php", action="wbgetentities", ids="|".join(wanted[i:i + 40]), props="labels", languages="en")))
    out = {t: {**sp.resolve_labels(facts[q], labels), "qid": q, "wikidata_url": f"https://www.wikidata.org/wiki/{q}"} for t, q in qids.items() if q in facts}
    with open("wikidata.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"✅ {len(out)}/{len(qids)} topics saved in wikidata.json")


def wikisource(max_per_topic=2, min_chars=2000):
    api = "https://fr.wikisource.org/w/api.php"
    corpus = []
    for t in titles():
        try:
            found = sp.search_titles(get(api, action="query", list="search", srsearch=t, srlimit=5))
        except Exception as e:
            print("❌", t, repr(e))
            continue
        kept = 0
        for title in found:
            if kept >= max_per_topic:
                break
            try:
                _, text = sp.extract_from_query(get(api, action="query", prop="extracts", explaintext=1, titles=title))
                if not text:   # no TextExtracts on this wiki: fall back to the rendered page
                    html = get(api, action="parse", page=title, prop="text").get("parse", {}).get("text", {}).get("*", "")
                    text = sp.html_to_text(html)
            except Exception:
                continue
            if len(text) >= min_chars:
                corpus.append({"titre": t, "titre_ws": title, "contenu": text, "source": "https://fr.wikisource.org/wiki/" + title.replace(" ", "_"),
                               "lang": "fr", "source_type": "Wikisource (FR)"})
                kept += 1
                print(f"✅ {t} <- {title} ({len(text)} characters)")
            time.sleep(0.3)
    with open("corpus_ws.json", "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    print(f"\n{len(corpus)} Wikisource texts saved. Review them before indexing: search results can be off-topic.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "wikidata":
        wikidata()
    elif cmd == "wikisource":
        wikisource()
    else:
        print(__doc__)
