"""Pure parsers for the Wikidata / Wikisource / Wikipedia API answers (unit-tested with sample responses)."""
import re

import core

WD_PROPS = {"P31": "instance_of", "P17": "country", "P625": "coordinates", "P571": "inception", "P576": "dissolved",
            "P569": "born", "P570": "died", "P580": "start", "P582": "end", "P757": "unesco_id", "P18": "image"}
_ENTITY_KEYS = {"instance_of", "country"}
_TIME_KEYS = {"inception", "dissolved", "born", "died", "start", "end"}


def qid_from_pageprops(resp):
    for page in (resp.get("query", {}).get("pages", {}) or {}).values():
        q = (page.get("pageprops") or {}).get("wikibase_item")
        if q:
            return q
    return None


def parse_time(value):
    """{"time": "-0247-00-00T00:00:00Z", "precision": 9} -> {"year": -247, "label": "247 BC", "precision": 9}"""
    m = re.match(r"^([+-])(\d+)-", (value or {}).get("time", ""))
    if not m:
        return None
    year = int(m.group(2)) * (-1 if m.group(1) == "-" else 1)
    precision = int(value.get("precision", 9))
    label = core.format_year(year)
    if precision < 9:
        label = "c. " + label
    return {"year": year, "label": label, "precision": precision}


def parse_entity(entity):
    """Facts of one Wikidata entity. Entity-valued claims keep their ids (resolved to labels by resolve_labels)."""
    claims = entity.get("claims", {}) or {}
    out = {"label": ((entity.get("labels") or {}).get("en") or {}).get("value")}
    for pid, key in WD_PROPS.items():
        values = [c.get("mainsnak", {}).get("datavalue", {}).get("value") for c in claims.get(pid, []) if c.get("mainsnak", {}).get("datavalue")]
        values = [v for v in values if v is not None]
        if not values:
            continue
        if key == "coordinates" and isinstance(values[0], dict) and "latitude" in values[0]:
            out["coordinates"] = {"lat": values[0]["latitude"], "lon": values[0]["longitude"]}
        elif key in _TIME_KEYS:
            t = parse_time(values[0])
            if t:
                out[key] = t
        elif key in _ENTITY_KEYS:
            out[key + "_ids"] = [v["id"] for v in values if isinstance(v, dict) and "id" in v][:4]
        elif isinstance(values[0], str):
            out[key] = values[0]
    return out


def resolve_labels(facts, labels):
    """Replace the *_ids lists by readable names, using {Qid: label}."""
    out = dict(facts)
    for key in ("instance_of", "country"):
        ids = out.pop(key + "_ids", None)
        if ids:
            out[key] = [labels.get(i, i) for i in ids]
    return out


def labels_from_entities(resp):
    return {q: ((e.get("labels") or {}).get("en") or {}).get("value", q) for q, e in (resp.get("entities") or {}).items()}


def extract_from_query(resp):
    """Plain text of the first page of a MediaWiki prop=extracts answer: (title, text)."""
    for page in (resp.get("query", {}).get("pages", {}) or {}).values():
        if page.get("extract"):
            return page.get("title", ""), page["extract"]
    return None, ""


def search_titles(resp):
    return [h["title"] for h in resp.get("query", {}).get("search", [])]


def html_to_text(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html or "", flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"&amp;", "&", t)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()
