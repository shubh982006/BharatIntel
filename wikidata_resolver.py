"""
BharatGraph - Wikidata QID Resolver
Resolves entity names to their canonical Wikidata QIDs.
Uses Wikidata's free public API — no key needed.

Examples:
  "China"          → Q148
  "India"          → Q668
  "Narendra Modi"  → Q1059955
  "Hambantota Port"→ Q1061
"""

import requests
import json
import os
import time

# Local cache file so we don't hit Wikidata API for same entity twice
QID_CACHE_FILE = "wikidata_qid_cache.json"

# Pre-built manual QID map for the most common entities in our graph
# These are 100% accurate and never need an API call
MANUAL_QID_MAP = {
    # Countries
    "india":             "Q668",
    "china":             "Q148",
    "pakistan":          "Q843",
    "united states":     "Q30",
    "usa":               "Q30",
    "us":                "Q30",
    "russia":            "Q159",
    "iran":              "Q794",
    "israel":            "Q801",
    "japan":             "Q17",
    "australia":         "Q408",
    "bangladesh":        "Q902",
    "sri lanka":         "Q854",
    "nepal":             "Q837",
    "maldives":          "Q766",
    "bhutan":            "Q917",
    "myanmar":           "Q836",
    "afghanistan":       "Q889",

    # People
    "narendra modi":     "Q1059955",
    "modi":              "Q1059955",
    "xi jinping":        "Q53558763",
    "vladimir putin":    "Q7747",
    "putin":             "Q7747",
    "mohamed muizzu":    "Q96669029",
    "muizzu":            "Q96669029",
    "muhammad yunus":    "Q466442",
    "yunus":             "Q466442",

    # Organizations
    "quad":              "Q4649774",
    "nato":              "Q7184",
    "united nations":    "Q1065",
    "un":                "Q1065",
    "brics":             "Q170881",
    "sco":               "Q233240",
    "asean":             "Q4927",
    "iaea":              "Q8784",
    "pla":               "Q390349",
    "isro":              "Q336529",
    "cia":               "Q37230",
    "raw":               "Q907827",

    # Infrastructure / Ports
    "hambantota port":   "Q3481357",
    "gwadar port":       "Q1345536",
    "chabahar port":     "Q726413",
    "strait of malacca": "Q131172",
    "strait of hormuz":  "Q165314",

    # Locations
    "line of actual control": "Q1585862",
    "lac":               "Q1585862",
    "aksai chin":        "Q193800",
    "arunachal pradesh": "Q1162",
    "doklam":            "Q16878884",
    "kashmir":           "Q43452",
    "indian ocean":      "Q1239",
    "siliguri corridor": "Q7516574",
    "brahmaputra":       "Q131426",
    "galwan valley":     "Q66653",

    # Treaties / Agreements
    "belt and road initiative": "Q907571",
    "bri":               "Q907571",
    "cpec":              "Q18373012",
    "paris agreement":   "Q324694",

    # Misc strategic entities
    "huawei":            "Q281600",
    "tsmc":              "Q713740",
    "string of pearls":  "Q7624461",
    "operation sindoor": "Q131372961",
}


def _load_qid_cache() -> dict:
    if os.path.exists(QID_CACHE_FILE):
        try:
            with open(QID_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_qid_cache(cache: dict):
    with open(QID_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _query_wikidata_api(entity_name: str) -> str:
    """
    Queries the Wikidata search API to find the QID for an entity.
    Returns QID string like "Q148" or None if not found.
    """
    try:
        url    = "https://www.wikidata.org/w/api.php"
        params = {
            "action":   "wbsearchentities",
            "search":   entity_name,
            "language": "en",
            "limit":    1,
            "format":   "json",
        }
        resp = requests.get(url, params=params, timeout=6,
                            headers={"User-Agent": "BharatGraph/1.0"})
        if resp.status_code == 200:
            data    = resp.json()
            results = data.get("search", [])
            if results:
                return results[0].get("id", None)
    except Exception:
        pass
    return None


def resolve_qid(entity_name: str) -> str:
    """
    Main function. Returns Wikidata QID for an entity name.

    Priority:
      1. Manual map (instant, 100% accurate for common entities)
      2. Local file cache (instant, previously resolved)
      3. Wikidata API call (live, ~1 second)
      4. Returns None if all fail
    """
    if not entity_name:
        return None

    lookup = entity_name.lower().strip()

    # 1. Check manual map first
    if lookup in MANUAL_QID_MAP:
        return MANUAL_QID_MAP[lookup]

    # 2. Check file cache
    cache = _load_qid_cache()
    if lookup in cache:
        return cache[lookup]

    # 3. Hit Wikidata API
    qid = _query_wikidata_api(entity_name)

    # 4. Cache result (even None) to avoid repeat API calls
    cache[lookup] = qid
    _save_qid_cache(cache)

    # Small delay to be respectful to Wikidata
    time.sleep(0.3)

    return qid


def resolve_entities_qids(entities: list) -> list:
    """
    Takes a list of entity dicts from nlp_extractor output.
    Fills in wikidata_id for each entity.
    Returns updated list.
    """
    resolved = []
    for entity in entities:
        name = entity.get("name", "")
        qid  = resolve_qid(name)
        resolved.append({
            **entity,
            "wikidata_id": qid,
        })
    return resolved


if __name__ == "__main__":
    test_entities = [
        "India", "China", "Pakistan", "Narendra Modi", "Xi Jinping",
        "Hambantota Port", "Gwadar Port", "Belt and Road Initiative",
        "Line of Actual Control", "Brahmaputra", "Quad", "ISRO",
        "Operation Sindoor", "Huawei", "Strait of Malacca",
    ]

    print("Wikidata QID Resolution Test")
    print("=" * 50)
    for name in test_entities:
        qid = resolve_qid(name)
        print(f"  {name:<35} → {qid}")