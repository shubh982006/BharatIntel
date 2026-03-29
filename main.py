"""
BharatGraph - FastAPI Backend (v2.1 with Knowledge Base Integration)
Exposes Neo4j graph data as REST endpoints for the React frontend.

Features:
  - Hybrid KB (verified historical facts) + Live News architecture
  - Natural language queries with evidence tracking
  - Pattern detection and alerts
  - What-If game theory simulations

Run with:
  uvicorn main:app --reload --port 8000

Endpoints:
  GET  /
  GET  /health
  GET  /graph/stats
  GET  /graph/search
  GET  /graph/subgraph
  GET  /graph/timeline
  GET  /graph/node/{node_id}
  POST /query
  POST /whatif
  GET  /alerts
"""

import os
import time
import logging
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

# Import graph utilities
try:
    from neo4j_writer import (
        get_graph_snapshot,
        get_timeline,
        get_driver,
    )
except ImportError as e:
    print(f"Warning: Could not import neo4j_writer: {e}")
    print("Make sure neo4j_writer.py is in the same directory")

load_dotenv()

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(message)s",
    # Just use StreamHandler (logs go to stdout → Render Dashboard)
    handlers=[
    logging.StreamHandler(),  # Remove FileHandler
    ]
)
log = logging.getLogger("bharatgraph")

# ─────────────────────────────────────────────
# RESPONSE CACHE — variable TTL
# ─────────────────────────────────────────────
_cache    = {}
CACHE_TTL = 60

def get_cached(key):
    """Retrieve cached data if not expired"""
    if key in _cache:
        entry = _cache[key]
        data  = entry[0]
        ts    = entry[1]
        ttl   = entry[2] if len(entry) > 2 else CACHE_TTL
        if time.time() - ts < ttl:
            return data
    return None

def set_cached(key, data, ttl=60):
    """Store data in cache with TTL"""
    _cache[key] = (data, time.time(), ttl)

# ─────────────────────────────────────────────
# FASTAPI APP SETUP
# ─────────────────────────────────────────────
app = FastAPI(
    title             = "BharatGraph API",
    description       = "AI-powered strategic intelligence graph for India (KB-Enhanced)",
    version           = "2.1.0",
    redirect_slashes  = False,   # prevents POST /query → 307 → GET /query/ → 405
)

# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

class WhatIfRequest(BaseModel):
    node_id: str


# ─────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────
@app.get("/")
def root():
    """Root endpoint - API info"""
    return {
        "service": "BharatGraph API",
        "version": "2.1.0",
        "status": "active",
        "kb_integrated": True,
        "features": [
            "Knowledge Base (130 verified facts)",
            "Live News Integration",
            "Natural Language Queries",
            "Pattern Detection",
            "What-If Simulations"
        ],
        "docs": "http://127.0.0.1:8000/docs",
        "endpoints": [
            "GET  /health",
            "GET  /graph/stats",
            "GET  /graph/search",
            "GET  /graph/subgraph",
            "GET  /graph/timeline",
            "GET  /graph/node/{node_id}",
            "POST /query",
            "POST /whatif",
            "GET  /alerts",
        ]
    }


# ─────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────
@app.get("/health")
def health():
    """Health check endpoint"""
    log.info("Health check")
    return {
        "status": "ok",
        "service": "BharatGraph API",
        "version": "2.1.0",
        "kb_status": "integrated"
    }


# ─────────────────────────────────────────────
# GET /graph/stats
# Dashboard summary numbers — cached 60s
# ─────────────────────────────────────────────
@app.get("/graph/stats")
def graph_stats():
    """Get graph statistics (KB + Live edges combined)"""
    cached = get_cached("stats")
    if cached:
        return cached
    try:
        driver = get_driver()
        stats  = {}
        with driver.session() as session:
            # Total nodes and edges
            stats["total_nodes"] = session.run(
                "MATCH (e:Entity) RETURN count(e) AS n"
            ).single()["n"]

            stats["total_edges"] = session.run(
                "MATCH ()-[r:RELATION]->() RETURN count(r) AS n"
            ).single()["n"]

            # KB vs Live breakdown
            stats["kb_edges"] = session.run(
                "MATCH ()-[r:RELATION {from_kb: true}]->() RETURN count(r) AS n"
            ).single()["n"]

            stats["live_edges"] = session.run(
                "MATCH ()-[r:RELATION]->() WHERE r.from_kb IS NULL RETURN count(r) AS n"
            ).single()["n"]

            # High impact edges
            stats["high_impact_edges"] = session.run(
                "MATCH ()-[r:RELATION {india_impact:'HIGH'}]->() RETURN count(r) AS n"
            ).single()["n"]

            # Domain breakdown
            r = session.run("""
                MATCH ()-[r:RELATION]->()
                WHERE r.domain IS NOT NULL
                RETURN r.domain AS domain, count(r) AS count
                ORDER BY count DESC
            """)
            stats["domain_breakdown"] = {row["domain"]: row["count"] for row in r}

            # Ontology breakdown
            r = session.run("""
                MATCH (e:Entity)
                WHERE e.ontology_category IS NOT NULL
                RETURN e.ontology_category AS cat, count(e) AS count
                ORDER BY count DESC
            """)
            stats["ontology_breakdown"] = {row["cat"]: row["count"] for row in r}

            # Latest update
            r = session.run(
                "MATCH ()-[r:RELATION]->() RETURN max(r.valid_from) AS latest"
            )
            stats["last_updated"] = r.single()["latest"]

            # Confidence distribution
            r = session.run("""
                MATCH ()-[r:RELATION]->()
                WHERE r.confidence IS NOT NULL
                RETURN
                  sum(CASE WHEN r.confidence >= 0.8 THEN 1 ELSE 0 END) AS high,
                  sum(CASE WHEN r.confidence >= 0.6 AND r.confidence < 0.8 THEN 1 ELSE 0 END) AS med,
                  sum(CASE WHEN r.confidence < 0.6 THEN 1 ELSE 0 END) AS low
            """)
            row = r.single()
            stats["confidence_distribution"] = {
                "high": row["high"] if row["high"] else 0,
                "med":  row["med"]  if row["med"]  else 0,
                "low":  row["low"]  if row["low"]  else 0,
            }

        
        set_cached("stats", stats, ttl=60)
        log.info("Stats fetched")
        return stats
    except Exception as e:
        log.error(f"graph_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# GET /graph/search
# ─────────────────────────────────────────────
@app.get("/graph/search")
def search_graph(
    q:     str = Query(..., description="Search keyword e.g. China"),
    limit: int = Query(20,  description="Max results"),
):
    """Search graph for nodes and edges matching keyword"""
    try:
        driver  = get_driver()
        results = {"nodes": [], "edges": []}
        with driver.session() as session:
            # Search nodes
            r = session.run("""
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($q)
                RETURN e.name AS id, e.type AS type,
                       e.ontology_category AS ontology_category,
                       e.wikidata_id AS wikidata_id
                LIMIT $limit
            """, q=q, limit=limit)
            results["nodes"] = [dict(row) for row in r]

            # Search edges
            r = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE toLower(r.context) CONTAINS toLower($q)
                   OR toLower(r.type)    CONTAINS toLower($q)
                RETURN a.name AS source, b.name AS target,
                       r.type AS relation, r.context AS context,
                       r.india_impact AS india_impact, r.domain AS domain,
                       r.from_kb AS from_kb
                LIMIT $limit
            """, q=q, limit=limit)
            results["edges"] = [dict(row) for row in r]

       
        results["total"] = len(results["nodes"]) + len(results["edges"])
        log.info(f"Search '{q}' -> {results['total']} results")
        return results
    except Exception as e:
        log.error(f"search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# GET /graph/subgraph
# ─────────────────────────────────────────────
@app.get("/graph/subgraph")
def get_subgraph(
    domain:       str = Query(None),
    india_impact: str = Query(None),
    limit:        int = Query(300),
    offset:       int = Query(0),
):
    """Get filtered subgraph (KB + Live combined)"""
    cache_key = f"subgraph_{domain}_{india_impact}_{limit}_{offset}"
    cached    = get_cached(cache_key)
    if cached:
        log.info(f"Cache hit: {cache_key}")
        return cached

    try:
        data  = get_graph_snapshot()
        links = data["links"]

        if domain:
            links = [l for l in links if l.get("domain", "").upper() == domain.upper()]
        if india_impact:
            links = [l for l in links if l.get("india_impact", "").upper() == india_impact.upper()]

        total_edges = len(links)
        links       = links[offset: offset + limit]

        if domain or india_impact:
            active = {l["source"] for l in links} | {l["target"] for l in links}
            nodes  = [n for n in data["nodes"] if n["id"] in active]
        else:
            nodes = data["nodes"]

        result = {
            "nodes":       nodes,
            "links":       links,
            "total_nodes": len(nodes),
            "total_edges": total_edges,
            "returned":    len(links),
            "offset":      offset,
            "has_more":    (offset + limit) < total_edges,
        }
        set_cached(cache_key, result, ttl=60)
        log.info(f"Subgraph: {len(nodes)} nodes, {len(links)} edges")
        return result

    except Exception as e:
        log.error(f"get_subgraph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# GET /graph/timeline
# ─────────────────────────────────────────────
@app.get("/graph/timeline")
def timeline(
    node1:     str,
    node2:     str,
    from_date: str = None,
    to_date:   str = None,
):
    """Get edge timeline between two nodes"""
    try:
        edges = get_timeline(node1, node2, from_date, to_date)
        log.info(f"Timeline {node1}<->{node2}: {len(edges)} edges")
        return {
            "node1":     node1,
            "node2":     node2,
            "from_date": from_date,
            "to_date":   to_date,
            "total":     len(edges),
            "edges":     edges,
        }
    except Exception as e:
        log.error(f"timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# All known KB entities (used for fuzzy matching)
# ─────────────────────────────────────────────
_KB_ENTITIES = [
    "Aksai Chin", "Andaman and Nicobar", "Arunachal Pradesh", "Assam",
    "Australia", "BRICS", "Bangladesh", "Belt and Road Initiative",
    "Brahmaputra", "CNSA", "CPEC", "Chabahar Port", "China",
    "Climate Change", "Crude Oil imports", "Depsang Plains", "Djibouti",
    "Doklam", "France", "G20", "Galwan Valley", "Gwadar Port",
    "Hambantota Port", "Himalayan Glaciers", "Huawei", "ISRO", "India",
    "Indian Ocean", "Indonesia", "Indus Waters Treaty", "Iran", "Israel",
    "Japan", "Kashmir", "Kazakhstan", "Lakshadweep", "Line of Actual Control",
    "Line of Control", "Maldives", "Mongolia", "Myanmar", "Narendra Modi",
    "Nepal", "Operation Sandstone", "Operation Sindoor", "PLA", "PLA Navy",
    "Pakistan", "Pangong Lake", "Pharmaceutical APIs", "Quad",
    "Rare Earth Elements", "Rohingya Crisis", "Semiconductor imports",
    "Shaksgam Valley", "Shanghai Cooperation Organization", "Siliguri Corridor",
    "Simla Agreement", "Singapore", "Sri Lanka", "Strait of Hormuz",
    "Strait of Malacca", "Thailand", "Tibetan Plateau", "United States",
    "Uranium", "Vietnam", "WTO", "Xi Jinping",
    # aliases
    "US", "Modi", "Trump", "Putin", "LAC", "LOC", "BRI", "ASEAN",
    "South China Sea", "SCO",
]

# ─────────────────────────────────────────────
# POST /query
# ─────────────────────────────────────────────
@app.post("/query")
def natural_language_query(req: QueryRequest):
    """
    Query endpoint: searches KB + live graph, then calls LLM with structured prompt.
    Returns a rich structured response for the frontend to render.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    log.info(f"Query: {req.question[:80]}")

    try:
        driver = get_driver()
        kb_edges: list = []
        live_edges: list = []

        # ── 1. Entity extraction: match against full KB entity list ──────────
        question_lower = req.question.lower()
        entities_in_q = [
            e for e in _KB_ENTITIES
            if e.lower() in question_lower
        ]
        # Also try splitting question words against entity tokens for partial matches
        if not entities_in_q:
            q_words = set(w.strip("'\".?,!") for w in question_lower.split() if len(w) > 3)
            entities_in_q = [
                e for e in _KB_ENTITIES
                if any(w in e.lower() for w in q_words)
            ]

        log.info(f"  Entities matched: {entities_in_q}")

        with driver.session() as session:
            if entities_in_q:
                # KB: verified historical facts
                r = session.run("""
                    MATCH (a:Entity)-[r:RELATION {from_kb: true}]->(b:Entity)
                    WHERE (a.name IN $entities OR b.name IN $entities)
                    RETURN a.name AS subject, r.type AS relation, b.name AS object,
                           r.context AS context, r.domain AS domain,
                           r.india_impact AS india_impact, r.confidence AS confidence,
                           r.valid_from AS date, r.source AS source, 'KB' AS edge_source
                    LIMIT 40
                """, entities=entities_in_q)
                kb_edges = [dict(row) for row in r]
                log.info(f"  KB edges: {len(kb_edges)}")

                # Live news: recent ingested articles
                r2 = session.run("""
                    MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                    WHERE (a.name IN $entities OR b.name IN $entities)
                      AND r.from_kb IS NULL
                      AND r.india_impact IN ['HIGH', 'MEDIUM']
                    RETURN a.name AS subject, r.type AS relation, b.name AS object,
                           r.context AS context, r.domain AS domain,
                           r.india_impact AS india_impact, r.confidence AS confidence,
                           r.valid_from AS date, r.source AS source,
                           'LIVE_NEWS' AS edge_source
                    ORDER BY r.valid_from DESC
                    LIMIT 20
                """, entities=entities_in_q)
                live_edges = [dict(row) for row in r2]
                log.info(f"  Live edges: {len(live_edges)}")

        all_edges = kb_edges + live_edges

        # ── 2. Keyword fallback if entity match found nothing ─────────────────
        if not all_edges:
            with driver.session() as s2:
                words = [w for w in question_lower.split() if len(w) > 3]
                seen_keys: set = set()
                for word in words[:5]:
                    r = s2.run("""
                        MATCH (a:Entity)-[rel:RELATION]->(b:Entity)
                        WHERE toLower(a.name) CONTAINS $w
                           OR toLower(b.name) CONTAINS $w
                           OR toLower(rel.context) CONTAINS $w
                        RETURN a.name AS subject, rel.type AS relation,
                               b.name AS object, rel.context AS context,
                               rel.domain AS domain, rel.india_impact AS india_impact,
                               rel.confidence AS confidence, rel.valid_from AS date,
                               rel.source AS source, 'KB' AS edge_source
                        LIMIT 10
                    """, w=word)
                    for row in r:
                        d = dict(row)
                        k = f"{d['subject']}_{d['relation']}_{d['object']}"
                        if k not in seen_keys:
                            seen_keys.add(k)
                            kb_edges.append(d)
                all_edges = kb_edges[:25]
                log.info(f"  Keyword fallback: {len(all_edges)} edges")

        graph_coverage = "RICH" if len(all_edges) >= 10 else "PARTIAL" if len(all_edges) >= 3 else "SPARSE"

        # ── 3. Build structured context block for LLM ─────────────────────────
        def fmt_edge(e: dict, prefix: str) -> str:
            conf = f"{float(e.get('confidence') or 0)*100:.0f}%" if e.get('confidence') else "?"
            impact = e.get('india_impact', '')
            return (
                f"  [{prefix}] {e['subject']} --[{e['relation']}]--> {e['object']} "
                f"| {e.get('context','')} | impact={impact} conf={conf} date={e.get('date','')} "
                f"src={e.get('source','')}"
            )

        kb_block  = "\n".join(fmt_edge(e, "KB")   for e in kb_edges[:20])
        live_block = "\n".join(fmt_edge(e, "LIVE") for e in live_edges[:10])

        graph_block = ""
        if kb_block:
            graph_block += "VERIFIED KNOWLEDGE BASE:\n" + kb_block + "\n\n"
        if live_block:
            graph_block += "LIVE NEWS FEED:\n" + live_block + "\n\n"

        # ── 4. Structured LLM prompt ──────────────────────────────────────────
        system_prompt = """You are BharatGraph — India's premier strategic intelligence terminal.
Your job: answer the analyst's query with maximum signal and zero noise.

OUTPUT FORMAT (always return valid JSON, no markdown fences):
{
  "headline": "One crisp sentence — the single most important takeaway (max 15 words)",
  "assessment": "2-3 paragraph strategic assessment. Lead with what matters most to India.",
  "key_facts": [
    {"claim": "...", "source": "KB|LIVE|EXPERT", "confidence": 0.0-1.0, "impact": "HIGH|MEDIUM|LOW"}
  ],
  "graph_gaps": "One sentence on what the graph does NOT have on this topic (or null if coverage is good)",
  "watch_signals": ["signal1", "signal2"],
  "data_sources": {"kb_edges": N, "live_edges": N, "coverage": "RICH|PARTIAL|SPARSE"}
}

RULES:
- key_facts: extract 3-6 specific verifiable claims from the graph edges. If graph is sparse, supplement with your strategic knowledge but mark source as "EXPERT" and confidence <= 0.7.
- assessment: when graph coverage is SPARSE or PARTIAL, draw on your expert geopolitical knowledge. Label those insights clearly with "(analyst assessment)" vs "(graph-verified)".
- watch_signals: 2-3 concrete things to monitor going forward (e.g. specific ports, treaties, military movements).
- Never refuse to answer due to sparse data — a good analyst gives their best assessment and states confidence.
- Be crisp. Total assessment should be under 300 words."""

        user_prompt = f"""Graph Coverage: {graph_coverage} ({len(kb_edges)} KB + {len(live_edges)} live edges)
Entities matched: {entities_in_q or 'none — keyword fallback used'}

{graph_block if graph_block else "No direct graph hits. Use your strategic knowledge."}

ANALYST QUERY: {req.question}

Respond only with the JSON object."""

        # ── 5. Call LLM ───────────────────────────────────────────────────────
        client = Groq(api_key=GROQ_API_KEY)
        llm_resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=900,
        )

        raw = llm_resp.choices[0].message.content.strip()
        # strip markdown fences if model wraps anyway
        raw = raw.strip("```json").strip("```").strip()

        # ── 6. Parse + enrich ─────────────────────────────────────────────────
        try:
            structured = json.loads(raw)
        except Exception:
            # graceful fallback — wrap raw text so frontend always gets structure
            structured = {
                "headline": req.question[:80],
                "assessment": raw,
                "key_facts": [],
                "graph_gaps": None,
                "watch_signals": [],
                "data_sources": {"kb_edges": len(kb_edges), "live_edges": len(live_edges), "coverage": graph_coverage},
            }

        structured["data_sources"] = {
            "kb_edges":   len(kb_edges),
            "live_edges": len(live_edges),
            "coverage":   graph_coverage,
        }

        log.info(f"Query answered | coverage={graph_coverage} | kb={len(kb_edges)} live={len(live_edges)}")

        return {
            # ── structured fields (new) ──────────────────────────────
            "headline":      structured.get("headline", ""),
            "assessment":    structured.get("assessment", ""),
            "key_facts":     structured.get("key_facts", []),
            "graph_gaps":    structured.get("graph_gaps"),
            "watch_signals": structured.get("watch_signals", []),
            "data_sources":  structured.get("data_sources", {}),
            # ── backward-compat flat answer ──────────────────────────
            "answer":        structured.get("assessment", raw),
            "question":      req.question,
            "kb_edges":      kb_edges,
            "live_edges":    live_edges,
            "total_evidence": len(all_edges),
            "evidence_summary": f"{len(kb_edges)} KB + {len(live_edges)} live ({graph_coverage} coverage)",
            "entities_matched": entities_in_q,
            "evidence":      all_edges,
            "sources_used":  len(all_edges),
        }

    except Exception as e:
        log.error(f"query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# POST /whatif
# What-If Engine + Game Theory
# ─────────────────────────────────────────────
@app.post("/whatif")
def whatif(req: WhatIfRequest):
    """What-If analysis: simulate removing a node and analyze impact"""
    # Input validation
    node_id = (req.node_id or "").strip()
    if not node_id or len(node_id) < 2 or len(node_id) > 120:
        raise HTTPException(status_code=400, detail="node_id must be 2-120 characters")
    if not any(c.isalpha() for c in node_id):
        raise HTTPException(status_code=400, detail="node_id must contain at least one letter")

    log.info(f"What-If: {node_id}")
    try:
        driver = get_driver()

        with driver.session() as session:

            # ── Affected edges ────────────────────────────────
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE a.name = $node_id OR b.name = $node_id
                RETURN a.name AS subject,
                       r.type AS relation,
                       b.name AS object,
                       r.india_impact AS india_impact,
                       r.domain AS domain,
                       r.context AS context,
                       r.confidence AS confidence
            """, node_id=node_id)
            affected_edges = [dict(r) for r in result]

            # ── Impact score ──────────────────────────────────
            impact_map   = {"HIGH": 75, "MEDIUM": 45, "LOW": 15, "NONE": 0}
            total_impact = sum(
                impact_map.get(e.get("india_impact", "LOW"), 0)
                for e in affected_edges
            )

            # ── Isolated nodes ────────────────────────────────
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]-(target:Entity {name: $node_id})
                WITH a
                MATCH (a)-[r2:RELATION]-(other:Entity)
                WHERE other.name <> $node_id
                WITH a, count(r2) AS other_connections
                WHERE other_connections = 0
                RETURN a.name AS isolated_node
            """, node_id=node_id)
            isolated = [r["isolated_node"] for r in result]

            # ── Game Theory: node count for Shapley ──────────
            all_nodes = session.run(
                "MATCH (e:Entity) RETURN count(e) AS n"
            ).single()["n"]

            # ── Game Theory: India counter-edges ─────────────
            india_counters = session.run("""
                MATCH (india:Entity {name: 'India'})-[r:RELATION]->(b:Entity)
                WHERE r.type IN [
                    'allied_with', 'counters', 'hosts_military_base',
                    'signs_agreement_with', 'supported_by', 'cooperates_on_tech_with'
                ]
                RETURN count(r) AS n
            """).single()["n"]

     

        # ── Domain breakdown ──────────────────────────────────
        domain_breakdown = {}
        for e in affected_edges:
            d = e.get("domain", "UNKNOWN")
            domain_breakdown[d] = domain_breakdown.get(d, 0) + 1

        # ── Shapley centrality approximation ─────────────────
        # Node's marginal contribution relative to graph size
        shapley_centrality = round(
            (total_impact / max(all_nodes, 1)) * 10, 1
        )

        # ── Deterrence index ──────────────────────────────────
        # exposed HIGH-impact threats / (threats + India's counters)
        exposed = len([
            e for e in affected_edges
            if e.get("india_impact") == "HIGH"
        ])
        deterrence_index = round(
            exposed / max(exposed + india_counters, 1), 2
        )

        # ── Nash equilibrium string ───────────────────────────
        if deterrence_index >= 0.7:
            nash = (
                f"Adversary dominant strategy maintained after "
                f"'{node_id}' removal — India significantly exposed"
            )
        elif deterrence_index <= 0.3:
            nash = (
                f"India deterrence intact — equilibrium stable "
                f"post '{node_id}' removal"
            )
        else:
            nash = (
                f"Unstable equilibrium — partial deterrence gap "
                f"exposed by '{node_id}' removal"
            )

        # ── Deterrence gaps ───────────────────────────────────
        deterrence_gaps = [
            (
                f"{e.get('subject', '?')} → {e.get('object', '?')} "
                f"[{e.get('relation', '?')}] has no Indian counter-move"
            )
            for e in affected_edges
            if e.get("india_impact") == "HIGH"
        ][:4]

        return {
            "removed_node":       node_id,
            "affected_edges":     affected_edges,
            "total_edges_lost":   len(affected_edges),
            "impact_score_lost":  total_impact,
            "isolated_nodes":     isolated,
            "domain_breakdown":   domain_breakdown,
            "summary": (
                f"Removing '{node_id}' would eliminate "
                f"{len(affected_edges)} relationships and "
                f"{total_impact} points of India impact score."
            ),
            # ── Game theory fields ────────────────────────────
            "shapley_centrality": shapley_centrality,
            "deterrence_index":   deterrence_index,
            "nash_equilibrium":   nash,
            "deterrence_gaps":    deterrence_gaps,
        }

    except Exception as e:
        log.error(f"whatif: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# GET /alerts
# Pattern detection — cached 30s (faster refresh)
# ─────────────────────────────────────────────
@app.get("/alerts")
def get_alerts():
    """Detect strategic patterns and threats in KB + Live data"""
    cached = get_cached("alerts")
    if cached:
        log.info("Alerts cache hit")
        return cached

    try:
        driver = get_driver()
        alerts = []

        with driver.session() as session:

            # Pattern 1: String of Pearls
            result = session.run("""
                MATCH (china:Entity {name: 'China'})-[r:RELATION]->(port:Entity)
                WHERE r.type IN ['invests_in','controls_port','builds_infrastructure_in']
                  AND port.ontology_category IN ['string_of_pearls','chokepoint']
                RETURN port.name AS asset,
                       r.context AS context,
                       r.valid_from AS date,
                       r.india_impact AS impact
                ORDER BY r.valid_from DESC
                LIMIT 5
            """)
            pearls = [dict(r) for r in result]
            if pearls:
                alerts.append({
                    "pattern":      "String of Pearls Expansion",
                    "threat_level": "HIGH",
                    "domain":       "GEOPOLITICS",
                    "description":  "China is expanding port/infrastructure control near India's maritime perimeter.",
                    "nodes":        [p["asset"] for p in pearls],
                    "evidence":     pearls,
                    "watch_for":    "Naval access agreements following infrastructure investments",
                })

            # Pattern 2: Economic Dependency Trap
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(india:Entity {name: 'India'})
                WHERE r.type IN ['debt_traps','sanctions','controls_resource']
                RETURN a.name AS actor,
                       r.type AS relation,
                       r.context AS context,
                       r.valid_from AS date
                LIMIT 5
            """)
            econ_threats = [dict(r) for r in result]
            if econ_threats:
                alerts.append({
                    "pattern":      "Economic Pressure on India",
                    "threat_level": "MEDIUM",
                    "domain":       "ECONOMICS",
                    "description":  "Foreign actors applying economic leverage targeting India.",
                    "nodes":        [e["actor"] for e in econ_threats],
                    "evidence":     econ_threats,
                    "watch_for":    "Escalation to supply chain disruption or currency pressure",
                })

            # Pattern 3: Border Pressure
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(loc:Entity)
                WHERE r.type IN ['conflict_with','threatens','disputes_sovereignty_of','claims_territory']
                  AND loc.ontology_category = 'border_flux_zone'
                  AND r.india_impact IN ['HIGH','MEDIUM']
                RETURN a.name AS actor,
                       loc.name AS zone,
                       r.type AS action,
                       r.context AS context,
                       r.valid_from AS date
                ORDER BY r.valid_from DESC
                LIMIT 5
            """)
            border = [dict(r) for r in result]
            if border:
                alerts.append({
                    "pattern":      "Border Flux Zone Activity",
                    "threat_level": "HIGH",
                    "domain":       "DEFENSE",
                    "description":  "Active pressure being applied on India's border dispute zones.",
                    "nodes":        list({b["zone"] for b in border}),
                    "evidence":     border,
                    "watch_for":    "Military infrastructure buildup following territorial claims",
                })

            # Pattern 4: Tech Surveillance
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE r.type IN ['deploys_surveillance_in','launches_cyberattack_on',
                                  'bans_technology','steals_technology']
                  AND r.domain = 'TECHNOLOGY'
                RETURN a.name AS actor,
                       b.name AS target,
                       r.type AS action,
                       r.context AS context,
                       r.india_impact AS impact
                LIMIT 5
            """)
            tech = [dict(r) for r in result]
            if tech:
                alerts.append({
                    "pattern":      "Technology Surveillance / Cyber Threat",
                    "threat_level": "MEDIUM",
                    "domain":       "TECHNOLOGY",
                    "description":  "Technology-based surveillance or cyber activity near India detected.",
                    "nodes":        [t["actor"] for t in tech],
                    "evidence":     tech,
                    "watch_for":    "5G infrastructure deployment in buffer states near India",
                })

            # Pattern 5: Climate / Water Risk
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE r.type IN ['diverts_river_affecting','disputes_water_rights_with',
                                  'causes_climate_impact_on']
                  AND r.domain = 'CLIMATE'
                RETURN a.name AS actor,
                       b.name AS target,
                       r.context AS context,
                       r.india_impact AS impact,
                       r.valid_from AS date
                LIMIT 5
            """)
            climate = [dict(r) for r in result]
            if climate:
                alerts.append({
                    "pattern":      "Water / Climate Security Threat",
                    "threat_level": "HIGH",
                    "domain":       "CLIMATE",
                    "description":  "River diversion or climate events threatening India's water security.",
                    "nodes":        [c["actor"] for c in climate],
                    "evidence":     climate,
                    "watch_for":    "Dam construction upstream of Brahmaputra or Indus tributaries",
                })

        

        result = {"total_alerts": len(alerts), "alerts": alerts}
        set_cached("alerts", result, ttl=30)   # 30s — faster refresh than other endpoints
        log.info(f"Alerts: {len(alerts)} patterns detected")
        return result

    except Exception as e:
        log.error(f"alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# GET /graph/node/{node_id}
# ─────────────────────────────────────────────
@app.get("/graph/node/{node_id}")
def get_node_detail(node_id: str):
    """Get detailed information about a specific node"""
    try:
        driver = get_driver()

        with driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {name: $name})
                RETURN e.name AS name,
                       e.type AS type,
                       e.ontology_category AS ontology_category,
                       e.wikidata_id AS wikidata_id,
                       e.first_seen AS first_seen,
                       e.last_seen AS last_seen
            """, name=node_id)
            node = result.single()
            if not node:
                raise HTTPException(status_code=404,
                                    detail=f"Node '{node_id}' not found")
            node_data = dict(node)

            # Outgoing edges
            result = session.run("""
                MATCH (a:Entity {name: $name})-[r:RELATION]->(b:Entity)
                RETURN b.name AS target, r.type AS relation,
                       r.context AS context, r.domain AS domain,
                       r.india_impact AS india_impact,
                       r.confidence AS confidence,
                       r.source_url AS source_url,
                       r.valid_from AS date,
                       r.from_kb AS from_kb
                ORDER BY r.valid_from DESC
            """, name=node_id)
            outgoing = [dict(r) for r in result]

            # Incoming edges
            result = session.run("""
                MATCH (a:Entity)-[r:RELATION]->(b:Entity {name: $name})
                RETURN a.name AS source, r.type AS relation,
                       r.context AS context, r.domain AS domain,
                       r.india_impact AS india_impact,
                       r.confidence AS confidence,
                       r.source_url AS source_url,
                       r.valid_from AS date,
                       r.from_kb AS from_kb
                ORDER BY r.valid_from DESC
            """, name=node_id)
            incoming = [dict(r) for r in result]

       
        log.info(f"Node detail: {node_id}")

        return {
            **node_data,
            "outgoing_edges":    outgoing,
            "incoming_edges":    incoming,
            "total_connections": len(outgoing) + len(incoming),
            "wikidata_url": (
                f"https://www.wikidata.org/wiki/{node_data['wikidata_id']}"
                if node_data.get("wikidata_id") else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"node_detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return {
        "error": "Not found",
        "message": str(exc.detail) if hasattr(exc, 'detail') else "Resource not found",
        "status": 404
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors"""
    log.error(f"Internal error: {exc}")
    return {
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "status": 500
    }


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    log.info("🚀 Starting BharatGraph API v2.1 (KB-Enhanced)")
    log.info("📊 Hybrid KB + Live News architecture active")
    log.info("🗄️  Knowledge Base: 130 verified facts pre-loaded")
    uvicorn.run(app, host="0.0.0.0", port=8000)