"""Second source for every topic: the English Wikipedia article (linked to the French one by
Wikipedia's own interlanguage links). Run once, then chunking.py, build_index.py and init_db.py again.

    python collect_extra_sources.py

Why: the answers are written in English, so English passages give better retrieval and a more
reliable faithfulness check, and having two independent articles per topic lets the Research
section compare sources and flag contradictions."""
import sys

# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import json

import requests
import wikipediaapi

from sites_data import nom_en

UA = "ProjetQA-LLM/1.0"
fr = wikipediaapi.Wikipedia(user_agent=UA, language="fr")
en = wikipediaapi.Wikipedia(user_agent=UA, language="en")
MIN_CHARS = 1200


def usable(page):
    if not page or not page.exists():
        return False
    text = page.text or ""
    head = text[:400].lower()
    return len(text) >= MIN_CHARS and "may refer to" not in head and "disambiguation" not in head


def search_title(query):
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", timeout=10, headers={"User-Agent": UA},
                         params={"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"})
        hits = r.json().get("query", {}).get("search", [])
        return hits[0]["title"] if hits else None
    except Exception:
        return None


def english_page(titre_fr):
    # 1) the interlanguage link of the French article (most reliable)
    try:
        fr_page = fr.page(titre_fr)
        link = fr_page.langlinks.get("en") if fr_page.exists() else None
        if link and usable(link):
            return link, "interlanguage link"
    except Exception as e:
        print("   langlinks failed:", repr(e))
    # 2) the English name of the topic, then a search
    for name in (nom_en(titre_fr), titre_fr):
        page = en.page(name)
        if usable(page):
            return page, "title"
    found = search_title(nom_en(titre_fr))
    if found and usable(en.page(found)):
        return en.page(found), "search"
    return None, None


def main():
    with open("corpus.json", "r", encoding="utf-8") as f:
        topics = [a["titre"] for a in json.load(f)]
    out = []
    for titre in topics:
        page, how = english_page(titre)
        if page:
            out.append({"titre": titre, "titre_en": page.title, "contenu": page.text, "source": page.fullurl,
                        "lang": "en", "source_type": "Wikipedia (EN)"})
            print(f"✅ {titre} -> {page.title} ({len(page.text)} characters, via {how})")
        else:
            print(f"❌ no English article found for: {titre}")
    with open("corpus_en.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n{len(out)}/{len(topics)} English articles saved in corpus_en.json")
    print("Next: python chunking.py && python build_index.py && python init_db.py")


if __name__ == "__main__":
    main()
