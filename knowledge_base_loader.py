"""
BharatGraph - Knowledge Base Loader
Loads curated historical + strategic facts from CSV into Neo4j.
Run ONCE at startup to bootstrap the graph with verified knowledge.
Then the scheduler layers live news on top.

No API calls needed — pure data loading.
"""

import csv
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI      = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "bharatgraph")

KB_FILE = "bharatgraph_knowledge_base.csv"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def load_knowledge_base():
    """
    Loads all rows from knowledge_base.csv into Neo4j.
    Each row becomes:
      - Two Entity nodes (subject, object)
      - One RELATION edge with all metadata
    
    This is separate from live news data — they coexist in the graph.
    """
    driver = get_driver()
    node_count = 0
    edge_count = 0

    print("=" * 70)
    print("BharatGraph — Knowledge Base Loader")
    print("=" * 70)

    if not os.path.exists(KB_FILE):
        print(f"\n[ERROR] '{KB_FILE}' not found!")
        print("  Make sure knowledge base CSV is in the working directory.")
        return {"nodes": 0, "edges": 0}

    with open(KB_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n[load] {len(rows)} edges to load from knowledge base")

    with driver.session() as session:
        for i, row in enumerate(rows):
            subject = row.get("subject", "").strip()
            obj = row.get("object", "").strip()
            relation = row.get("relation", "").strip()
            context = row.get("context", "")
            domain = row.get("domain", "GEOPOLITICS")
            india_impact = row.get("india_impact", "LOW")
            confidence = float(row.get("confidence", 0.75))
            valid_from = row.get("valid_from", "2020-01-01")
            valid_to = row.get("valid_to", None)
            source = row.get("source", "Knowledge Base")

            if not subject or not obj or not relation:
                print(f"  [skip] Row {i+1}: incomplete data")
                continue

            # Mark edges from knowledge base with a special flag
            kb_flag = True

            # Step 1: Ensure subject node exists
            session.run("""
                MERGE (a:Entity {name: $name})
                ON CREATE SET a.type       = 'Unknown',
                              a.first_seen = $date,
                              a.last_seen  = $date,
                              a.from_kb    = true
                SET a.last_seen = $date
            """, name=subject, date=valid_from)

            # Step 2: Ensure object node exists
            session.run("""
                MERGE (b:Entity {name: $name})
                ON CREATE SET b.type       = 'Unknown',
                              b.first_seen = $date,
                              b.last_seen  = $date,
                              b.from_kb    = true
                SET b.last_seen = $date
            """, name=obj, date=valid_from)

            # Step 3: Create or update the relationship
            session.run("""
                MATCH (a:Entity {name: $subject})
                MATCH (b:Entity {name: $object})
                MERGE (a)-[r:RELATION {type: $relation}]->(b)
                ON CREATE SET r.valid_from = $valid_from,
                              r.from_kb    = true
                SET r.context       = $context,
                    r.confidence    = $confidence,
                    r.valid_to      = $valid_to,
                    r.source        = $source,
                    r.domain        = $domain,
                    r.india_impact  = $india_impact,
                    r.conflict_flag = false,
                    r.from_kb       = true
            """, subject=subject, object=obj, relation=relation,
                 context=context, confidence=confidence,
                 valid_from=valid_from, valid_to=valid_to,
                 source=source, domain=domain,
                 india_impact=india_impact)

            edge_count += 1
            node_count += 2  # rough count

            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(rows)}] edges loaded...")

    driver.close()

    print(f"\n[done] Knowledge base loaded")
    print(f"  Nodes created/updated: ~{node_count}")
    print(f"  Edges created/updated: {edge_count}")
    print(f"\n[info] Graph now contains both:")
    print(f"    - {edge_count} verified historical + strategic facts (from KB)")
    print(f"    - Live news edges (from scheduler)")
    print(f"\n  All queries automatically search both sources.\n")

    return {"nodes": node_count, "edges": edge_count}


def count_kb_edges():
    """
    Returns count of edges already loaded from knowledge base.
    Useful for checking if bootstrap already happened.
    """
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH ()-[r:RELATION {from_kb: true}]->()
                RETURN count(r) AS n
            """)
            count = result.single()["n"]
        driver.close()
        return count
    except Exception as e:
        print(f"[error] Could not count KB edges: {e}")
        return 0


def test_kb_queries():
    """
    Smoke test — verify knowledge base loaded correctly.
    """
    driver = get_driver()

    print("\n" + "=" * 70)
    print("Knowledge Base Verification — Sample Queries")
    print("=" * 70)

    test_queries = [
        ("India → China relationships", """
            MATCH (a:Entity {name: 'India'})-[r:RELATION]->(b:Entity {name: 'China'})
            RETURN r.type AS relation, r.india_impact AS impact, r.confidence AS confidence
            LIMIT 3
        """),
        ("India vulnerabilities (dependencies)", """
            MATCH (india:Entity {name: 'India'})-[r:RELATION]->(resource)
            WHERE r.type IN ['depends_on', 'vulnerable_to']
            RETURN resource.name AS resource, r.india_impact AS impact
        """),
        ("Strategic ports near India", """
            MATCH (port:Entity)-[r:RELATION]-(b:Entity)
            WHERE port.name IN ['Gwadar Port', 'Hambantota Port', 'Chabahar Port']
            RETURN DISTINCT port.name, r.type, b.name
            LIMIT 5
        """),
        ("Border dispute zones", """
            MATCH (zone:Entity)
            WHERE zone.name IN ['Line of Actual Control', 'Aksai Chin', 'Arunachal Pradesh', 'Doklam', 'Kashmir']
            MATCH (zone)-[r:RELATION]-(neighbor)
            RETURN zone.name AS zone, r.type AS action, neighbor.name AS actor
            LIMIT 5
        """),
    ]

    with driver.session() as session:
        for title, query in test_queries:
            print(f"\n{title}:")
            print("-" * 70)
            try:
                result = session.run(query)
                rows = list(result)
                if rows:
                    for row in rows:
                        print(f"  {dict(row)}")
                else:
                    print("  (no results)")
            except Exception as e:
                print(f"  [error] {e}")

    driver.close()
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    # Load knowledge base
    result = load_knowledge_base()

    # Verify it worked
    kb_count = count_kb_edges()
    print(f"[check] Currently {kb_count} KB edges in graph\n")

    if kb_count > 50:
        print("[✓] Knowledge base successfully loaded!")
        test_kb_queries()
    else:
        print("[!] Knowledge base may not have loaded. Check errors above.")
