# BharatIntel — Backend

FastAPI + Neo4j intelligence graph API for India's strategic neighborhood. Serves verified historical facts from a curated knowledge base alongside live news ingested by a continuous pipeline, all queryable via natural language.

---

## Architecture

```
scheduler.py  (run locally — see note below)
     │
     ▼
fetch_news → data_pipeline → nlp_extractor
          → wikidata_resolver → neo4j_writer
                                     │
                                     ▼
                               Neo4j AuraDB
                               ├─ KB layer    (from_kb: true)
                               └─ Live layer  (pipeline-ingested)
                                     │
                                     ▼
                               main.py  ←  FastAPI web service (Render)
                               └─ REST API consumed by frontend
```

---

## API routes

| Method | Route | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/graph/stats` | Node/edge counts, domain breakdown |
| GET | `/graph/subgraph` | Paginated graph for visualisation |
| GET | `/graph/search` | Keyword search across nodes + edge contexts |
| GET | `/graph/timeline` | Edge timeline between two nodes |
| GET | `/graph/node/{id}` | Full node detail with all edges |
| POST | `/query` | Natural language query → structured LLM response |
| POST | `/whatif` | Remove a node, compute knock-on impact |
| GET | `/alerts` | Pattern-matched early warning feed |

Full interactive docs available at `/docs` (Swagger UI) when the server is running.

---

## Query response shape

`POST /query` returns structured JSON — not a prose blob:

```json
{
  "headline":      "Single most important takeaway (≤15 words)",
  "assessment":    "2–3 paragraph strategic analysis",
  "key_facts": [
    {
      "claim":      "India --[cooperates_on_tech_with]--> Israel",
      "source":     "KB",
      "confidence": 0.89,
      "impact":     "HIGH"
    }
  ],
  "graph_gaps":    "No live news edges on Israel in the current graph",
  "watch_signals": ["Monitor Israeli drone transfer approvals", "..."],
  "data_sources":  { "kb_edges": 8, "live_edges": 0, "coverage": "PARTIAL" }
}
```

`source` on each fact: `KB` = verified knowledge base, `LIVE` = pipeline-ingested news, `EXPERT` = LLM general knowledge (used when coverage is `SPARSE`, confidence ≤ 0.7). The `coverage` field (`RICH` / `PARTIAL` / `SPARSE`) tells the frontend how much to trust the response and drives the coloured badge in the terminal UI.

---

## Environment variables

| Variable | Default | Required |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Yes (prod) |
| `NEO4J_USER` | `neo4j` | Yes (prod) |
| `NEO4J_PASSWORD` | `bharatgraph` | Yes (prod) |
| `GROQ_API_KEY` | — | Yes |

Create a `.env` file locally — `python-dotenv` loads it automatically. In production, set these in Render's **Environment** tab.

---

## Local development

```bash
# 1. install
pip install -r requirements.txt

# 2. configure
cp .env.example .env    # fill in NEO4J_* and GROQ_API_KEY

# 3. seed the knowledge base (one-time)
python knowledge_base_loader.py

# 4. start the API
uvicorn main:app --reload --port 8000
```

---

## Render deployment

The API is deployed as a **Web Service** on Render.

- **Runtime:** Python 3.10 (pinned in `runtime.txt`)
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
  (also in `Procfile` as `web:`)
- **Environment:** add the four variables above

> **Free tier cold starts:** Render free web services spin down after 15 minutes of inactivity. First request after a cold start takes ~30s. Upgrade to a paid instance for always-on latency.

---

## Pipeline scheduler

`scheduler.py` runs the live news pipeline on a 30-minute loop:

```
fetch_news       Google News RSS across ~30 India-focused queries
data_pipeline    clean text, auto-translate non-English articles
nlp_extractor    Groq (llama-3.3-70b) extracts entities + relations
wikidata_resolver  resolves Wikidata QIDs, caches results
entity_resolve   deduplication + normalisation
ontology_mapper  applies Bharatiya ontology tags + India impact scores
neo4j_writer     upserts everything into Neo4j
```

Articles are deduplicated via `seen_articles_cache.json` so nothing is processed twice.

**Why it's not running on Render:** `Procfile` has a `worker: python scheduler.py` entry, but Render's worker process type is a paid feature. Until then, run it locally:

```bash
# separate terminal, same .env
python scheduler.py
```

If the scheduler isn't running the API still works — it serves the static knowledge base and whatever was last ingested.

---

## Knowledge base

`bharatgraph_knowledge_base.csv` — 84 hand-curated edges covering India's core strategic environment: LAC/LOC disputes, String of Pearls ports, Quad alliances, chokepoint dependencies, rare earth and pharma API vulnerabilities, key bilateral treaties.

Loaded into Neo4j with `from_kb: true` so the query endpoint distinguishes verified facts from live news.

**To expand coverage:** add rows to the CSV then re-run:

```bash
python knowledge_base_loader.py
```

CSV schema: `subject, relation, object, context, domain, india_impact, confidence, valid_from, valid_to, source`

`india_impact` values: `HIGH` / `MEDIUM` / `LOW` / `NONE`

---

## Entity matching

The `/query` endpoint matches question text against `_KB_ENTITIES` in `main.py` — a list of all entity names and common aliases (e.g. `"US"` → `"United States"`, `"LAC"` → `"Line of Actual Control"`). If no entities match, it falls back to keyword search across node names and edge context fields.

To add new aliases: append to the `_KB_ENTITIES` list in `main.py`. No restart required on Render — just redeploy.

---

## Project structure

```
bharatIntel/
├── main.py                      API routes + query endpoint
├── scheduler.py                 Pipeline orchestrator (30-min loop)
├── fetch_news.py                Google News RSS + article body extraction
├── data_pipeline.py             Clean + translate
├── nlp_extractor.py             Groq entity/relation extraction
├── entity_resolve.py            Deduplication + normalisation
├── ontology_mapper.py           Bharatiya ontology tagging + impact scores
├── wikidata_resolver.py         QID lookup + caching
├── neo4j_writer.py              Graph upsert
├── knowledge_base_loader.py     One-time CSV seed loader
├── seen_cache.py                Article dedup cache
├── bharatgraph_knowledge_base.csv
├── requirements.txt
├── runtime.txt                  python-3.10.13
└── Procfile                     web: uvicorn | worker: scheduler (paid)
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.104.1 | API framework |
| uvicorn[standard] | 0.24.0 | ASGI server |
| pydantic | 2.5.0 | Request/response models |
| neo4j | ≥5.20 | Graph DB driver |
| groq | ≥0.9.0 | LLM inference |
| feedparser | 6.0.10 | RSS parsing |
| newspaper3k | 0.2.8 | Article body extraction |
| beautifulsoup4 | 4.12.2 | HTML parsing |
| deep-translator | 1.11.4 | Auto-translate |
| requests | 2.31.0 | HTTP client |
| schedule | 1.2.0 | Cron-style scheduling |
| python-dotenv | 1.0.0 | Local env loading |
| lxml | 4.9.3 | XML/HTML parsing |
| pillow | 10.1.0 | Image handling |

---

## Known issues

- **`groq<0.9.0` crashes** with `Client.__init__() got an unexpected keyword argument 'proxies'` — this is a breaking change in `httpx>=0.28`. The fix is already in `requirements.txt` (`groq>=0.9.0`). If you have an older install, run `pip install "groq>=0.9.0"`.
- **Entity aliases not exhaustive** — shorthand like `PRC`, `PAK`, `GoI` won't match until added to `_KB_ENTITIES`.
- **Scheduler dedup cache is local** — `seen_articles_cache.json` lives on disk. If the machine running the scheduler changes, the cache resets and articles may be re-ingested.
