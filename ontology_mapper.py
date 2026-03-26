"""
BharatGraph - Bharatiya Ontology Mapper
THE core intellectual contribution of this project.

Maps every entity to India's specific threat taxonomy.
This is what makes every insight automatically India-relevant.

Categories:
  buffer_state      — Nations on India's border where foreign influence = strategic risk
  chokepoint        — Maritime straits and corridors critical to India's trade/energy
  string_of_pearls  — Chinese port/base investments encircling India
  dependency_vector — India's economic vulnerabilities (energy, tech, pharma)
  border_flux_zone  — Active territorial dispute areas with China/Pakistan
  allied_nation     — Nations aligned with India strategically
  adversary         — Nations in active strategic competition with India
  neutral           — Everything else
"""

# ─────────────────────────────────────────────
# THE BHARATIYA ONTOLOGY
# ─────────────────────────────────────────────

ONTOLOGY = {

    # ── BUFFER STATES ────────────────────────────────────────
    # Nations on India's immediate periphery where Chinese influence
    # directly threatens India's strategic depth
    "buffer_state": [
        "Nepal",
        "Bhutan",
        "Sri Lanka",
        "Bangladesh",
        "Maldives",
        "Myanmar",
        "Afghanistan",
    ],

    # ── CHOKEPOINTS ──────────────────────────────────────────
    # Maritime straits and corridors — 90% of India's trade passes through these
    # Control or disruption = economic strangulation of India
    "chokepoint": [
        "Indian Ocean",
        "Strait of Malacca",
        "Strait of Hormuz",
        "Bab-el-Mandeb",
        "Lombok Strait",
        "Siliguri Corridor",      # land chokepoint — India's connection to northeast
        "Chabahar Port",          # India's access to Central Asia bypassing Pakistan
        "Gulf of Oman",
    ],

    # ── STRING OF PEARLS ─────────────────────────────────────
    # Chinese port investments / military access points encircling India
    # Each one is a potential dual-use military node
    "string_of_pearls": [
        "Hambantota Port",        # Sri Lanka — 99-year lease
        "Gwadar Port",            # Pakistan — CPEC anchor
        "String of Pearls",
        "Belt and Road Initiative",
        "CPEC",
        "Kyaukpyu Port",          # Myanmar
        "Chittagong Port",        # Bangladesh
        "Mongla Port",            # Bangladesh
        "Marao Island",           # Maldives
        "Djibouti Base",          # China's first overseas military base
        "China Merchants Port",
    ],

    # ── DEPENDENCY VECTORS ───────────────────────────────────
    # India's economic pressure points — where adversaries can apply leverage
    "dependency_vector": [
        "Crude Oil",
        "Petroleum",
        "Semiconductor",
        "Pharmaceutical API",
        "Rare Earth",
        "Solar Panel",
        "Electronics Import",
        "Urea",                   # India imports fertilizer — food security link
    ],

    # ── BORDER FLUX ZONES ────────────────────────────────────
    # Active territorial dispute areas — where military confrontation is live
    "border_flux_zone": [
        "Line of Actual Control",
        "Line of Control",
        "Aksai Chin",
        "Arunachal Pradesh",
        "Doklam",
        "Galwan Valley",
        "Depsang Plains",
        "Demchok",
        "Siachen",
        "Kashmir",
        "Jammu and Kashmir",
        "Shaksgam Valley",
        "Pangong Lake",
    ],

    # ── ALLIED NATIONS ───────────────────────────────────────
    # Strategic partners — Quad members + key bilateral partners
    "allied_nation": [
        "United States",
        "Japan",
        "Australia",
        "France",
        "Israel",                 # defence tech partner
        "Russia",                 # historical — now complex, keep neutral option
    ],

    # ── ADVERSARY ────────────────────────────────────────────
    # Nations in documented strategic competition with India
    "adversary": [
        "China",
        "Pakistan",
    ],

    # ── KEY MILITARY ACTORS ──────────────────────────────────
    # Not a threat category — just tagging for graph coloring
    "military_actor": [
        "PLA",
        "PLA Navy",
        "Indian Armed Forces",
        "Indian Navy",
        "Operation Sindoor",
        "ISI",                    # Pakistan intelligence
    ],
}

# ─────────────────────────────────────────────
# REVERSE LOOKUP — entity name → category
# Built automatically from ONTOLOGY dict above
# ─────────────────────────────────────────────
_REVERSE_MAP = {}
for category, entities in ONTOLOGY.items():
    for entity in entities:
        _REVERSE_MAP[entity.lower()] = category


def get_ontology_category(entity_name: str) -> str:
    """
    Returns the Bharatiya Ontology category for an entity.
    Returns 'neutral' if not found.

    Usage:
        get_ontology_category("Hambantota Port")  → "string_of_pearls"
        get_ontology_category("Nepal")             → "buffer_state"
        get_ontology_category("Aksai Chin")        → "border_flux_zone"
        get_ontology_category("China")             → "adversary"
        get_ontology_category("Quad")              → "neutral"
    """
    if not entity_name:
        return "neutral"

    return _REVERSE_MAP.get(entity_name.lower().strip(), "neutral")


def tag_entities(entities: list) -> list:
    """
    Takes a list of resolved entity dicts,
    adds ontology_category to each one.

    Input:
        [{"name": "Hambantota Port", "type": "Infrastructure"}, ...]

    Output:
        [{"name": "Hambantota Port", "type": "Infrastructure",
          "ontology_category": "string_of_pearls"}, ...]
    """
    tagged = []
    for entity in entities:
        category = get_ontology_category(entity["name"])
        tagged.append({
            **entity,
            "ontology_category": category,
        })
    return tagged


def get_india_impact_score(entities: list, relationships: list) -> dict:
    """
    Calculates India Impact Score (0-100) for a single article/event.
    Returns score + breakdown of which factors fired.

    Scoring weights:
      buffer_state involved      → +25
      string_of_pearls involved  → +25
      border_flux_zone involved  → +20
      dependency_vector involved → +15
      chokepoint involved        → +10
      adversary involved         → +5
    """
    score = 0
    breakdown = []
    triggered = set()

    category_weights = {
        "buffer_state":      (25, "Buffer state involved"),
        "string_of_pearls":  (25, "String of Pearls node detected"),
        "border_flux_zone":  (20, "Active border dispute zone"),
        "dependency_vector": (15, "India dependency vector affected"),
        "chokepoint":        (10, "Strategic chokepoint involved"),
        "adversary":         (5,  "Adversary nation involved"),
    }

    for entity in entities:
        category = entity.get("ontology_category", "neutral")
        if category in category_weights and category not in triggered:
            weight, reason = category_weights[category]
            score += weight
            breakdown.append(f"+{weight}: {reason} ({entity['name']})")
            triggered.add(category)

    score = min(score, 100)  # cap at 100

    # Determine threat level
    if score >= 70:
        threat_level = "HIGH"
    elif score >= 40:
        threat_level = "MEDIUM"
    else:
        threat_level = "LOW"

    return {
        "score":        score,
        "threat_level": threat_level,
        "breakdown":    breakdown,
    }


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Bharatiya Ontology — Category Lookup Test")
    print("=" * 50)

    test_entities = [
        "Hambantota Port",
        "Nepal",
        "Aksai Chin",
        "China",
        "India",
        "United States",
        "Line of Actual Control",
        "Belt and Road Initiative",
        "Indian Ocean",
        "Gwadar Port",
        "Quad",
        "Operation Sindoor",
        "PLA",
        "Arunachal Pradesh",
        "Siliguri Corridor",
    ]

    for name in test_entities:
        category = get_ontology_category(name)
        print(f"  {name:<35} → {category}")

    print("\n\nIndia Impact Score Test")
    print("=" * 50)

    # Scenario: China invests in Hambantota (near India)
    test_entities_scored = [
        {"name": "China",            "type": "Country",        "ontology_category": "adversary"},
        {"name": "Hambantota Port",  "type": "Infrastructure", "ontology_category": "string_of_pearls"},
        {"name": "Sri Lanka",        "type": "Country",        "ontology_category": "buffer_state"},
        {"name": "Indian Ocean",     "type": "Location",       "ontology_category": "chokepoint"},
    ]

    result = get_india_impact_score(test_entities_scored, [])
    print(f"\n  Scenario: China invests in Hambantota Port (Sri Lanka)")
    print(f"  India Impact Score : {result['score']}/100")
    print(f"  Threat Level       : {result['threat_level']}")
    print(f"  Breakdown:")
    for line in result["breakdown"]:
        print(f"    {line}")