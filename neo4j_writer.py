"""
BharatGraph - Neo4j Writer
Fixed for Neo4j 5.x — ON CREATE SET must come before SET in MERGE statements.
Singleton driver — no driver.close() calls anywhere.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# SINGLETON DRIVER — one connection for process lifetime
# Never call driver.close() — Aura/TLS connections are expensive to reopen
# ─────────────────────────────────────────────
_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "bharatgraph"),
            ),
            max_connection_pool_size=10,
        )
    return _driver


def push_to_neo4j(extracted_articles):
    """
    Pushes all entities and relationships into Neo4j.
    MERGE ensures no duplicates across pipeline cycles.
    ON CREATE SET must come BEFORE SET — required in Neo4j 5.x
    """
    driver     = get_driver()
    node_count = 0
    edge_count = 0

    with driver.session() as session:
        for article in extracted_articles:
            date       = article.get("date", "")
            source     = article.get("source", "")
            source_url = article.get("url", "")

            # ── Write entity nodes ────────────────────────────
            for entity in article.get("entities", []):
                name     = entity.get("name", "").strip()
                etype    = entity.get("type", "Unknown")
                wiki_id  = entity.get("wikidata_id", None)
                category = entity.get("ontology_category", "neutral")

                if not name:
                    continue

                session.run("""
                    MERGE (e:Entity {name: $name})
                    ON CREATE SET e.first_seen        = $date
                    ON MATCH SET  e.last_seen         = $date
                    SET           e.type              = $type,
                                  e.ontology_category = $category,
                                  e.wikidata_id       = $wiki_id
                """, name=name, type=etype, category=category,
                     wiki_id=wiki_id, date=date)
                node_count += 1

            # ── Write relationship edges ──────────────────────
            for rel in article.get("relationships", []):
                subject    = rel.get("subject", "").strip()
                obj        = rel.get("object", "").strip()
                relation   = rel.get("relation", "").strip()
                context    = rel.get("context", "")
                confidence = rel.get("confidence", 0.75)
                valid_from = rel.get("valid_from", date)
                valid_to   = rel.get("valid_to", None)

                if not subject or not obj or not relation:
                    continue

                domain       = rel.get("domain", "GEOPOLITICS")
                india_impact = rel.get("india_impact", "LOW")

                # conflict_flag: HIGH impact but low confidence source
                # renders as dashed edge on the frontend graph
                conflict_flag = (
                    india_impact == "HIGH" and
                    float(confidence) < 0.65
                )

                # Step 1: ensure subject node exists
                session.run("""
                    MERGE (a:Entity {name: $name})
                    ON CREATE SET a.type       = 'Unknown',
                                  a.first_seen = $date,
                                  a.last_seen  = $date
                """, name=subject, date=date)

                # Step 2: ensure object node exists
                session.run("""
                    MERGE (b:Entity {name: $name})
                    ON CREATE SET b.type       = 'Unknown',
                                  b.first_seen = $date,
                                  b.last_seen  = $date
                """, name=obj, date=date)

                # Step 3: create or update the relationship
                session.run("""
                    MATCH (a:Entity {name: $subject})
                    MATCH (b:Entity {name: $object})
                    MERGE (a)-[r:RELATION {type: $relation}]->(b)
                    ON CREATE SET r.valid_from = $valid_from
                    SET r.context       = $context,
                        r.confidence    = $confidence,
                        r.valid_to      = $valid_to,
                        r.source        = $source,
                        r.source_url    = $source_url,
                        r.domain        = $domain,
                        r.india_impact  = $india_impact,
                        r.conflict_flag = $conflict_flag
                """, subject=subject, object=obj, relation=relation,
                     context=context, confidence=confidence,
                     valid_from=valid_from, valid_to=valid_to,
                     source=source, source_url=source_url,
                     domain=domain, india_impact=india_impact,
                     conflict_flag=conflict_flag)
                edge_count += 1

    print(f"  [neo4j] Pushed {node_count} nodes, {edge_count} edges")
    return {"nodes": node_count, "edges": edge_count}


def test_connection():
    try:
        driver = get_driver()
        with driver.session() as session:
            session.run("RETURN 1 AS ok").single()
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        print(f"  [neo4j] Connected to {uri}")
        return True
    except Exception as e:
        print(f"  [neo4j] Connection failed: {e}")
        print("  Set NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD env vars")
        return False


def get_graph_snapshot():
    """
    Returns current graph as nodes + links JSON.
    Called by FastAPI /graph/subgraph endpoint.
    conflict_flag included so frontend can render dashed edges.
    """
    driver = get_driver()
    nodes  = []
    links  = []

    with driver.session() as session:
        result = session.run("""
            MATCH (e:Entity)
            RETURN e.name AS id,
                   e.type AS type,
                   e.ontology_category AS ontology_category,
                   e.wikidata_id  AS wikidata_id,
                   e.first_seen   AS first_seen,
                   e.last_seen    AS last_seen
        """)
        for record in result:
            nodes.append(dict(record))

        result = session.run("""
            MATCH (a:Entity)-[r:RELATION]->(b:Entity)
            RETURN a.name AS source,
                   b.name AS target,
                   r.type AS relation,
                   r.context       AS context,
                   r.confidence    AS confidence,
                   r.valid_from    AS valid_from,
                   r.valid_to      AS valid_to,
                   r.source        AS source_name,
                   r.source_url    AS source_url,
                   r.domain        AS domain,
                   r.india_impact  AS india_impact,
                   r.conflict_flag AS conflict_flag
        """)
        for record in result:
            links.append(dict(record))

    return {
        "nodes":       nodes,
        "links":       links,
        "total_nodes": len(nodes),
        "total_edges": len(links),
    }


def get_timeline(node1, node2, from_date=None, to_date=None):
    """
    Returns edge history between two nodes filtered by date range.
    Powers the Time Machine slider on the frontend.
    """
    driver = get_driver()
    edges  = []

    with driver.session() as session:
        result = session.run("""
            MATCH (a:Entity {name: $node1})-[r:RELATION]->(b:Entity {name: $node2})
            WHERE ($from_date IS NULL OR r.valid_from >= $from_date)
              AND ($to_date   IS NULL OR r.valid_from <= $to_date)
            RETURN r.type        AS relation,
                   r.context     AS context,
                   r.valid_from  AS valid_from,
                   r.confidence  AS confidence,
                   r.source      AS source_name,
                   r.source_url  AS source_url,
                   r.conflict_flag AS conflict_flag
            ORDER BY r.valid_from ASC
        """, node1=node1, node2=node2,
             from_date=from_date, to_date=to_date)
        for record in result:
            edges.append(dict(record))

    return edges