"""
BharatGraph - NLP + Ontology Layer
Uses FREE Groq API (llama-3.3-70b model)
Get free API key: https://console.groq.com → API Keys → Create

Input  : processed_articles.json
Output : nlp_output.json

Groq Free Tier:
  - 30 requests/minute
  - 14,400 requests/day
  - No credit card needed
"""

import json
import os
import time
from groq import Groq
from dotenv import load_dotenv
from wikidata_resolver import resolve_entities_qids
from entity_resolve import resolve_entities, resolve_relationships

# Load environment variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# SECURITY FIX: Never hardcode API keys in code.
# Set your key as an environment variable instead:
#
#   Windows:  set GROQ_API_KEY=gsk_...
#   Mac/Linux: export GROQ_API_KEY=gsk_...
#
# Get free key at: https://console.groq.com
# ─────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

INPUT_FILE  = "processed_articles.json"
OUTPUT_FILE = "nlp_output.json"
MODEL = "llama-3.3-70b-versatile" # Best free model on Groq


# ─────────────────────────────────────────────
# SYSTEM PROMPT — covers all 6 domains
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are BharatGraph — an AI-powered Global Ontology Engine and strategic intelligence analyst.

Your job is to extract structured knowledge from news articles across six domains:
GEOPOLITICS, ECONOMICS, DEFENSE, TECHNOLOGY, CLIMATE, and SOCIETY.

Every extraction must be analyzed through the lens of India's national interest and global strategic advantage.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENTITY TYPES — use exactly these labels
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GEOPOLITICS & DEFENSE:
- Country        : Nation states (India, China, Pakistan, USA, Russia, Iran, Israel)
- Organization   : Strategic bodies (Quad, SCO, NATO, BRICS, UN, PLA, RAW, ISI, IAEA)
- Location       : Strategic places (LAC, Aksai Chin, Doklam, Siliguri Corridor, Indian Ocean)
- Infrastructure : Ports, roads, bases, pipelines (Gwadar Port, Hambantota Port, Chabahar Port)
- Military       : Weapons, operations, forces (Operation Sindoor, Agni-V, INS Vikrant, PLA Navy)
- Treaty         : Agreements, pacts (Simla Agreement, CPEC deal, AUKUS, Indus Waters Treaty)
- Person         : Named individuals (Modi, Xi Jinping, Muizzu, Yunus, Putin)

ECONOMICS:
- TradeRoute     : Shipping lanes, corridors (Strait of Malacca, Hormuz, INSTC, BRI corridor)
- EconomicZone   : Trade blocs, SEZs, economic corridors (ASEAN, EU, RCEP, CPEC zone)
- Resource       : Strategic commodities (Crude Oil, Rare Earth, Semiconductor, Pharmaceutical API, Lithium)
- Corporation    : Strategic companies (Huawei, TSMC, Adani Ports, China Merchants Port)
- SanctionEvent  : Economic sanctions or restrictions (US chip export ban, Russia SWIFT ban)

TECHNOLOGY:
- Technology     : Critical tech domains (5G, AI surveillance, Hypersonic missile, Quantum computing, Satellite)
- CyberEntity    : Cyber threats, attacks, actors (APT41, PLA Unit 61398, cyber espionage)
- SpaceAsset     : Space programs, satellites (ISRO, ASAT weapon, GPS spoofing, BeiDou)

CLIMATE & ENVIRONMENT:
- ClimateEvent   : Disasters, environmental events (Himalayan glacial melt, cyclone, drought, flood)
- ClimatePolicy  : Agreements, targets, policies (Paris Agreement, Net Zero 2070, UNFCCC)
- NaturalResource: Water bodies, forests, disputed ecology (Brahmaputra River, Sundarbans, Tibetan Plateau)
- EnergyAsset    : Power plants, pipelines, energy infrastructure (solar farm, LNG terminal, nuclear plant)

SOCIETY & INTERNAL:
- PopulationGroup: Ethnic, religious, demographic groups (Uyghurs, Rohingya, Kashmiri separatists)
- SocialEvent    : Protests, elections, humanitarian crises (Shaheen Bagh, Myanmar coup, Bangladesh unrest)
- MediaEntity    : Propaganda outlets, disinformation actors (Global Times, CGTN, RT)
- Ideology       : Political movements, doctrines (BRI ideology, Two-Nation Theory, Hindutva, Wahhabism)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RELATIONSHIP TYPES — use exactly these labels
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GEOPOLITICAL:
- invests_in
- conflict_with
- disputes_sovereignty_of
- allied_with
- signs_agreement_with
- encircles
- counters
- claims_territory
- hosts_military_base
- supplies_weapons_to
- controls_port
- builds_infrastructure_in
- threatens
- supports

ECONOMIC:
- trades_with
- sanctions
- depends_on              (economic dependency)
- controls_resource
- competes_with
- funds
- debt_traps              (predatory lending leading to asset seizure)

TECHNOLOGY:
- develops_technology
- steals_technology
- bans_technology
- deploys_surveillance_in
- launches_cyberattack_on
- cooperates_on_tech_with

CLIMATE & ENVIRONMENT:
- causes_climate_impact_on
- disputes_water_rights_with
- diverts_river_affecting
- pollutes
- signs_climate_agreement_with
- suffers_climate_event

SOCIETY:
- oppresses_population
- spreads_disinformation_in
- funds_ideology_in
- destabilizes_via_social_unrest
- conducts_election_interference_in
- has_refugee_crisis_affecting

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INDIA IMPACT — CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HIGH: China + any buffer state, China controlling any port, 
Pakistan military/nuclear, territory disputes with India,
China controlling rare earths/semiconductors, chokepoint threats.
MEDIUM: US-China tensions, BRI projects, China-Pakistan CPEC,
tech bans near India, debt traps in neighborhood.
LOW: only if zero India connection. DEFAULT TO HIGH OR MEDIUM.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Extract 5-10 entities per article
- Extract 4-8 relationships per article
- Cover ALL relevant domains present in the article — not just military
- Only extract relationships clearly supported by the article text
- Keep context under 15 words
- india_impact must be one of: HIGH / MEDIUM / LOW / NONE
- Respond ONLY with valid JSON — no explanation, no markdown, no code blocks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "entities": [
    {"name": "China",           "type": "Country",      "wikidata_id": null},
    {"name": "Hambantota Port", "type": "Infrastructure","wikidata_id": null},
    {"name": "Brahmaputra",     "type": "NaturalResource","wikidata_id": null},
    {"name": "Huawei",          "type": "Corporation",  "wikidata_id": null}
  ],
  "relationships": [
    {
      "subject":      "China",
      "relation":     "controls_port",
      "object":       "Hambantota Port",
      "context":      "99-year lease after Sri Lanka loan default",
      "domain":       "GEOPOLITICS",
      "india_impact": "HIGH"
    },
    {
      "subject":      "China",
      "relation":     "diverts_river_affecting",
      "object":       "Brahmaputra",
      "context":      "dam construction in Tibet reduces downstream flow",
      "domain":       "CLIMATE",
      "india_impact": "HIGH"
    },
    {
      "subject":      "Huawei",
      "relation":     "deploys_surveillance_in",
      "object":       "Bangladesh",
      "context":      "5G network with embedded backdoors near India",
      "domain":       "TECHNOLOGY",
      "india_impact": "MEDIUM"
    }
  ]
}"""


# ─────────────────────────────────────────────
# EXTRACT FROM ONE ARTICLE
# ─────────────────────────────────────────────
def extract(client: Groq, article: dict) -> dict:
    """Send one article to Groq and extract entities + relationships."""

    title = article.get("title", "")
    text  = article.get("cleaned_text", "")

    prompt = f"""Extract geopolitical entities and relationships from this article:

Title: {title}
Content: {text}

Respond ONLY with valid JSON:"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            max_tokens=800,
        )

        choice = response.choices[0]
        if choice.finish_reason == "length":
            print(f"    [truncated] article too long, skipping")
            return {"entities": [], "relationships": []}

        raw = choice.message.content.strip()

        # Strip markdown code blocks if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"    [JSON Error] {e}")
        return {"entities": [], "relationships": []}
    except Exception as e:
        print(f"    [API Error] {e}")
        return {"entities": [], "relationships": []}


# ─────────────────────────────────────────────
# PROCESS ALL ARTICLES
# ─────────────────────────────────────────────
def _calc_confidence(source: str, rel: dict) -> float:
    # Normalise: lowercase, strip spaces so "The Hindu" matches "thehindu"
    src = source.lower().replace(" ", "").replace("-", "").replace(".", "")
    trusted = [
        "reuters", "bbc", "thehindu", "hindu", "aljazeera", "worldbank",
        "cfr", "unorg", "bloomberg", "ft", "financialtimes", "economist",
        "apnews", "associatedpress", "wsj", "wallstreetjournal", "nyt",
        "newyorktimes", "guardian", "foreignaffairs", "diplomat",
        "indianexpress", "livemint", "mint", "theprint", "scroll",
        "wire", "ndtv", "thewire", "hindustantimes",
    ]
    base = 0.88 if any(t in src for t in trusted) else 0.62
    if len(rel.get("context", "")) < 8:
        base -= 0.15
    if rel.get("india_impact") == "HIGH":
        base += 0.05
    return round(max(0.4, min(0.95, base)), 2)

def process_all(articles: list, client: Groq) -> list:
    results = []

    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article.get('title','')[:60]}...")

        extracted = extract(client, article)
        if not extracted or not isinstance(extracted, dict):
            extracted = {"entities": [], "relationships": []}

        n_ent = len(extracted.get("entities") or [])
        n_rel = len(extracted.get("relationships") or [])
        print(f"    → {n_ent} entities, {n_rel} relationships")

        # Enrich relationships with temporal + confidence fields
        article_date   = article.get("date", "")
        article_source = article.get("source", "")
        article_url    = article.get("url", "")

        enriched_relationships = []
        for rel in extracted.get("relationships", []):
            enriched_relationships.append({
                "subject":      rel.get("subject", ""),
                "relation":     rel.get("relation", ""),
                "object":       rel.get("object", ""),
                "context":      rel.get("context", ""),
                "domain":       rel.get("domain", "GEOPOLITICS"),
                "india_impact": rel.get("india_impact", "LOW"),
                "confidence":   _calc_confidence(article_source, rel),
                "valid_from":   article_date,
                "valid_to":     None,
                "source_url":   article_url,
            })

        # Step A: build raw entity list
        raw_entities = []
        for ent in (extracted.get("entities") or []):
            raw_entities.append({
                "name":        ent.get("name", ""),
                "type":        ent.get("type", ""),
                "wikidata_id": ent.get("wikidata_id", None),
            })

        # Step B: canonicalise names FIRST (PM Modi → Modi, PRC → China)
        raw_entities = resolve_entities(raw_entities)
        enriched_relationships = resolve_relationships(enriched_relationships)

        # Step C: NOW resolve Wikidata QIDs on canonical names
        enriched_entities = resolve_entities_qids(raw_entities)

        results.append({
            "title":         article.get("title", ""),
            "date":          article_date,
            "source":        article_source,
            "url":           article_url,
            "cleaned_text":  article.get("cleaned_text", ""),
            "entities":      enriched_entities,
            "relationships": enriched_relationships,
        })

        # Groq free: 30 req/min → 2 sec delay is enough
        time.sleep(4)

    return results


# ─────────────────────────────────────────────
# SUMMARY STATS
# ─────────────────────────────────────────────
def print_summary(results: list):
    total_ent  = sum(len(r["entities"]) for r in results)
    total_rel  = sum(len(r["relationships"]) for r in results)
    unique_ent = set(e["name"] for r in results for e in r["entities"])
    rel_counts = {}
    for r in results:
        for rel in r["relationships"]:
            t = rel.get("relation", "?")
            rel_counts[t] = rel_counts.get(t, 0) + 1

    print(f"\n{'='*60}")
    print("NLP EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"  Articles processed  : {len(results)}")
    print(f"  Total entities      : {total_ent}")
    print(f"  Unique entities     : {len(unique_ent)}")
    print(f"  Total relationships : {total_rel}")
    print(f"\n  Unique entities found:")
    for name in sorted(unique_ent)[:20]:
        print(f"    - {name}")
    print(f"\n  Relationship type counts:")
    for rtype, cnt in sorted(rel_counts.items(), key=lambda x: -x[1]):
        print(f"    {rtype:<35}: {cnt}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("BharatGraph — NLP + Entity Extraction Layer (Groq)")
    print("=" * 60)

    if not GROQ_API_KEY:
        print("\n[ERROR] GROQ_API_KEY environment variable not set!")
        print("  1. Go to: https://console.groq.com")
        print("  2. Sign up (free, no credit card)")
        print("  3. API Keys → Create → copy the key (starts with gsk_)")
        print("  4. Set in your terminal:")
        print("       Windows : set GROQ_API_KEY=gsk_...")
        print("       Mac/Linux: export GROQ_API_KEY=gsk_...")
        print("  5. Keep the terminal open — run again")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"\n[ERROR] '{INPUT_FILE}' not found!")
        print("  Run data_pipeline.py first.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        articles = json.load(f)
    print(f"\n[load] {len(articles)} articles loaded from '{INPUT_FILE}'")

    client = Groq(api_key=GROQ_API_KEY)
    print(f"[model] Using {MODEL} (Groq free tier)")
    print(f"[info] ~{len(articles) * 2} seconds total\n")

    results = process_all(articles, client)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[save] Saved to '{OUTPUT_FILE}'")

    print_summary(results)

    # Preview first article
    print(f"\n[Preview] First article:\n")
    first = results[0]
    print(f"  Title: {first['title']}")
    print(f"  Entities:")
    for e in first["entities"]:
        print(f"    - {e.get('name'):<28} [{e.get('type')}]")
    print(f"  Relationships:")
    for r in first["relationships"]:
        print(f"    {r.get('subject')} --{r.get('relation')}--> {r.get('object')}")
        print(f"    context: {r.get('context','')}")
        print()


if __name__ == "__main__":
    main()