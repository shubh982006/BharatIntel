"""
BharatGraph - Master Pipeline Scheduler
Runs the full pipeline automatically every 30 minutes.

Flow:
  fetch_news → data_pipeline → nlp_extractor → neo4j_writer → done
  (repeat every 30 min)

Run this once and leave it running:
  python scheduler.py

Environment variables loaded from .env file.
"""

import os
import time
import schedule
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

from fetch_news        import fetch_all
from data_pipeline     import process_data
from nlp_extractor     import process_all
from neo4j_writer      import push_to_neo4j, test_connection
from seen_cache        import filter_new_articles, cache_stats
from wikidata_resolver import resolve_entities_qids
from entity_resolve    import resolve_entities, resolve_relationships
from ontology_mapper   import tag_entities, get_india_impact_score

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
PIPELINE_INTERVAL = 30   # minutes between each full cycle


# ─────────────────────────────────────────────
# SAFE HELPERS
# ─────────────────────────────────────────────
def safe_list(val):
    """Return val if it's a list, else empty list."""
    return val if isinstance(val, list) else []

def safe_entities(article):
    return safe_list(article.get("entities"))

def safe_relationships(article):
    return safe_list(article.get("relationships"))


# ─────────────────────────────────────────────
# PIPELINE CYCLE
# ─────────────────────────────────────────────
def run_pipeline():
    cycle_start = datetime.now()
    print("\n" + "=" * 60)
    print(f"PIPELINE CYCLE — {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # ── Step 1: Fetch live news ───────────────────────────
        print("\n[STEP 1] Fetching live news from Google RSS...")
        raw_articles = fetch_all(max_per_query=2)

        if not raw_articles:
            print("  [warn] No articles fetched. Skipping cycle.")
            return

        print(f"  Fetched: {len(raw_articles)} articles")

        # ── Step 1b: Deduplicate ──────────────────────────────
        raw_articles, skipped = filter_new_articles(raw_articles)
        stats = cache_stats()
        print(f"  New: {len(raw_articles)} | Skipped (cached): {skipped} | Total cached: {stats['total_cached']}")

        if not raw_articles:
            print("  [info] All articles already processed. Skipping.")
            return

        # ── Step 2: Clean + translate ─────────────────────────
        print("\n[STEP 2] Cleaning and translating...")
        cleaned_articles = process_data(raw_articles)

        if not cleaned_articles:
            print("  [warn] No articles after cleaning. Skipping.")
            return

        # ── Step 3: NLP extraction via Groq ──────────────────
        print("\n[STEP 3] Extracting entities and relationships...")
        client    = Groq(api_key=GROQ_API_KEY)
        extracted = process_all(cleaned_articles, client)

        # Guard: process_all can return None or empty on total failure
        if not extracted or not isinstance(extracted, list):
            print("  [warn] NLP extraction returned nothing. Skipping push.")
            return

        # Filter out any None entries in the list
        extracted = [a for a in extracted if a and isinstance(a, dict)]

        if not extracted:
            print("  [warn] All articles failed extraction. Skipping push.")
            return

        total_entities  = sum(len(safe_entities(a))      for a in extracted)
        total_relations = sum(len(safe_relationships(a))  for a in extracted)
        print(f"  Extracted: {total_entities} entities, {total_relations} relationships")

        # ── Step 4: Resolve Wikidata QIDs ───────────────────
        print("\n[STEP 4] Resolving Wikidata QIDs...")
        for article in extracted:
            entities = safe_entities(article)
            if entities:
                article["entities"] = resolve_entities_qids(entities)

        total_qids = sum(
            1 for a in extracted
            for e in safe_entities(a)
            if e.get("wikidata_id")
        )
        print(f"  QIDs resolved: {total_qids}")

        # ── Step 4b: Apply Bharatiya Ontology tagging ────────
        print("\n[STEP 4b] Applying Bharatiya Ontology...")
        for article in extracted:
            entities      = safe_entities(article)
            relationships = safe_relationships(article)

            if entities:
                article["entities"] = resolve_entities(entities)
                article["entities"] = tag_entities(article["entities"])

            if relationships:
                article["relationships"] = resolve_relationships(relationships)

            # India Impact Score per article
            try:
                impact = get_india_impact_score(
                    safe_entities(article),
                    safe_relationships(article),
                )
                article["india_impact_score"] = impact["score"]
                article["india_threat_level"] = impact["threat_level"]
                article["impact_breakdown"]   = impact["breakdown"]
            except Exception as ie:
                article["india_impact_score"] = 0
                article["india_threat_level"] = "LOW"
                article["impact_breakdown"]   = []

        tagged_count = sum(
            1 for a in extracted
            for e in safe_entities(a)
            if e.get("ontology_category", "neutral") != "neutral"
        )
        print(f"  Ontology tagged: {tagged_count} entities with strategic categories")

        # ── Step 5: Push to Neo4j ────────────────────────────
        print("\n[STEP 5] Pushing to Neo4j...")
        result = push_to_neo4j(extracted)

        # ── Done ─────────────────────────────────────────────
        elapsed = (datetime.now() - cycle_start).seconds
        print(f"\n[DONE] Cycle complete in {elapsed}s")
        print(f"       Nodes: {result['nodes']} | Edges: {result['edges']}")
        print(f"       New articles: {len(raw_articles)} | Skipped: {skipped}")
        print(f"       Next cycle in {PIPELINE_INTERVAL} minutes")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Pipeline cycle failed: {e}")
        import traceback
        traceback.print_exc()
        print("  Will retry next cycle.")


# ─────────────────────────────────────────────
# STARTUP CHECKS
# ─────────────────────────────────────────────
def startup_checks():
    print("=" * 60)
    print("BharatGraph — Real-Time Pipeline Scheduler")
    print("=" * 60)

    if not GROQ_API_KEY:
        print("\n[ERROR] GROQ_API_KEY not set!")
        print("  Mac/Linux: export GROQ_API_KEY=gsk_...")
        return False

    print(f"\n[✓] Groq API key found")

    print("[?] Checking Neo4j connection...")
    if not test_connection():
        print("\n[ERROR] Cannot connect to Neo4j.")
        print("  1. Open Neo4j Desktop")
        print("  2. Start your database")
        print("  3. Set NEO4J_PASSWORD env var to match your DB password")
        return False

    print("[✓] Neo4j connected")
    print(f"\n[✓] Pipeline will run every {PIPELINE_INTERVAL} minutes")
    print("[✓] Starting first cycle now...\n")
    return True


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not startup_checks():
        exit(1)

    run_pipeline()

    schedule.every(PIPELINE_INTERVAL).minutes.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(10)