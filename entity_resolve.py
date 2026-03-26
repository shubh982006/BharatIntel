"""
BharatGraph - Entity Resolver
Normalizes messy entity names into clean canonical forms.
"PM Modi" / "Modi" / "Narendra Modi" → "Narendra Modi"
"PRC" / "People's Republic of China" / "China" → "China"
No SPARQL needed for MVP — manual normalization dictionary.
"""

# ─────────────────────────────────────────────
# ALIAS MAP
# Key   = any variant that might appear in NLP output
# Value = the canonical name we want in the graph
# ─────────────────────────────────────────────
ALIAS_MAP = {

    # ── COUNTRIES ────────────────────────────────────────────
    "prc": "China",
    "people's republic of china": "China",
    "peoples republic of china": "China",
    "chinese": "China",
    "beijing": "China",                      # when used as country stand-in

    "india": "India",
    "indian": "India",
    "new delhi": "India",                    # when used as country stand-in
    "delhi": "India",
    "bharat": "India",
    "hindustan": "India",
    "british india": "India",                # historical — map to India for graph purposes

    "pak": "Pakistan",
    "pakistan army": "Pakistan",
    "islamabad": "Pakistan",

    "us": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "america": "United States",
    "washington": "United States",
    "us intelligence": "United States",
    "us senate": "United States",

    "sri lanka": "Sri Lanka",
    "ceylon": "Sri Lanka",
    "colombo": "Sri Lanka",                  # when used as country stand-in

    "nepal": "Nepal",
    "kathmandu": "Nepal",

    "bangladesh": "Bangladesh",
    "dhaka": "Bangladesh",

    "maldives": "Maldives",
    "malé": "Maldives",
    "male": "Maldives",

    "bhutan": "Bhutan",
    "thimphu": "Bhutan",

    "myanmar": "Myanmar",
    "burma": "Myanmar",
    "naypyidaw": "Myanmar",

    "iran": "Iran",
    "tehran": "Iran",
    "persia": "Iran",

    "japan": "Japan",
    "tokyo": "Japan",

    "australia": "Australia",
    "canberra": "Australia",

    # ── PEOPLE ──────────────────────────────────────────────
    "pm modi": "Narendra Modi",
    "modi": "Narendra Modi",
    "narendra modi": "Narendra Modi",
    "prime minister modi": "Narendra Modi",

    "xi": "Xi Jinping",
    "president xi": "Xi Jinping",
    "xi jinping": "Xi Jinping",

    "muizzu": "Mohamed Muizzu",
    "president muizzu": "Mohamed Muizzu",

    "yunus": "Muhammad Yunus",
    "dr yunus": "Muhammad Yunus",

    "gen naravane": "General Naravane",
    "navy vice-chief": "Vice Admiral Sameer Saxena",
    "vice admiral sameer saxena": "Vice Admiral Sameer Saxena",

    "tarique rahman": "Tarique Rahman",

    # ── MILITARY ORGS ────────────────────────────────────────
    "pla": "PLA",
    "people's liberation army": "PLA",
    "peoples liberation army": "PLA",
    "pla navy": "PLA Navy",
    "plan": "PLA Navy",
    "chinese military": "PLA",
    "indian armed forces": "Indian Armed Forces",
    "indian army": "Indian Armed Forces",
    "indian navy": "Indian Navy",

    # ── ORGANIZATIONS ────────────────────────────────────────
    "bri": "Belt and Road Initiative",
    "belt and road initiative": "Belt and Road Initiative",
    "one belt one road": "Belt and Road Initiative",
    "obor": "Belt and Road Initiative",
    "new silk road": "Belt and Road Initiative",

    "cpec": "CPEC",
    "china pakistan economic corridor": "CPEC",

    "quad": "Quad",
    "quadrilateral security dialogue": "Quad",

    "bcim forum": "BCIM Forum",
    "bcim": "BCIM Forum",

    "china merchant ports": "China Merchants Port",
    "china merchants port holdings": "China Merchants Port",

    "un": "United Nations",
    "united nations": "United Nations",

    "nato": "NATO",

    # ── INFRASTRUCTURE / PORTS ──────────────────────────────
    "hambantota": "Hambantota Port",
    "hambantota international port": "Hambantota Port",
    "hambantota port": "Hambantota Port",

    "gwadar": "Gwadar Port",
    "gwadar port": "Gwadar Port",

    "chabahar": "Chabahar Port",
    "chabahar port": "Chabahar Port",

    "string of pearls": "String of Pearls",

    "arunachal highway": "Arunachal Frontier Highway",
    "arunachal frontier highway": "Arunachal Frontier Highway",

    # ── LOCATIONS / ZONES ────────────────────────────────────
    "lac": "Line of Actual Control",
    "line of actual control": "Line of Actual Control",

    "loc": "Line of Control",
    "line of control": "Line of Control",

    "aksai chin": "Aksai Chin",
    "arunachal pradesh": "Arunachal Pradesh",
    "doklam": "Doklam",
    "galwan": "Galwan Valley",
    "galwan valley": "Galwan Valley",
    "siliguri corridor": "Siliguri Corridor",
    "chicken's neck": "Siliguri Corridor",

    "indian ocean": "Indian Ocean",
    "indian ocean region": "Indian Ocean",
    "ior": "Indian Ocean",

    "kashmir": "Kashmir",
    "jammu and kashmir": "Jammu and Kashmir",
    "jammu": "Jammu and Kashmir",

    "sino indian border": "Line of Actual Control",

    # ── TREATIES / AGREEMENTS ───────────────────────────────
    "mcmahon line": "McMahon Line",
    "simla convention": "Simla Agreement",
    "simla agreement": "Simla Agreement",
    "sino nepal boundary agreement": "Sino-Nepal Boundary Agreement",
    "sino-nepalese treaty of peace and friendship": "Sino-Nepal Treaty",

    # ── OPERATIONS ──────────────────────────────────────────
    "operation sindoor": "Operation Sindoor",
    "sindoor": "Operation Sindoor",
}


def resolve(name: str, entity_type: str = "") -> str:
    """
    Resolve an entity name to its canonical form.
    Returns the canonical name, or the original if no alias found.
    """
    if not name:
        return name

    lookup = name.lower().strip()
    canonical = ALIAS_MAP.get(lookup)

    if canonical:
        return canonical

    # Title-case the original as a fallback cleanup
    return name.strip()


def resolve_entities(entities: list) -> list:
    """
    Takes a list of entity dicts from nlp_output.json,
    returns them with resolved canonical names.
    Deduplicates after resolution.
    """
    resolved = []
    seen = set()

    for entity in entities:
        canonical_name = resolve(entity["name"], entity.get("type", ""))
        key = (canonical_name.lower(), entity.get("type", ""))

        if key not in seen:
            seen.add(key)
            resolved.append({
                "name": canonical_name,
                "type": entity.get("type", "Unknown"),
            })

    return resolved


def resolve_relationships(relationships: list) -> list:
    """
    Takes a list of relationship dicts from nlp_output.json,
    resolves subject and object names to canonical forms.
    """
    resolved = []

    for rel in relationships:
        resolved.append({
            "subject":  resolve(rel.get("subject", "")),
            "relation": rel.get("relation", ""),
            "object":   resolve(rel.get("object", "")),
            "context":  rel.get("context", ""),
        })

    return resolved


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    test_entities = [
        {"name": "Modi",          "type": "Person"},
        {"name": "PM Modi",       "type": "Person"},
        {"name": "Narendra Modi", "type": "Person"},
        {"name": "PLA",           "type": "Organization"},
        {"name": "People's Liberation Army", "type": "Military"},
        {"name": "Hambantota",    "type": "Location"},
        {"name": "BRI",           "type": "Organization"},
        {"name": "Belt and Road Initiative", "type": "Organization"},
        {"name": "LAC",           "type": "Location"},
        {"name": "US",            "type": "Country"},
        {"name": "United States", "type": "Country"},
    ]

    print("Entity Resolution Test:")
    print("-" * 40)
    resolved = resolve_entities(test_entities)
    for e in resolved:
        print(f"  {e['name']:<35} [{e['type']}]")

    print("\nRelationship Resolution Test:")
    print("-" * 40)
    test_rels = [
        {"subject": "Modi",      "relation": "allied_with", "object": "US",   "context": "Quad summit"},
        {"subject": "PLA",       "relation": "threatens",   "object": "India", "context": "LAC transgression"},
        {"subject": "BRI",       "relation": "invests_in",  "object": "Hambantota", "context": "port deal"},
    ]
    resolved_rels = resolve_relationships(test_rels)
    for r in resolved_rels:
        print(f"  {r['subject']} --{r['relation']}--> {r['object']}")
        print(f"  context: {r['context']}\n")