"""
BharatGraph - Seen Articles Cache
Persists across pipeline cycles using a local JSON file.
Prevents re-processing articles already sent to Groq.
Saves Groq API quota significantly.
"""

import json
import os
import hashlib
from datetime import datetime, timedelta

CACHE_FILE   = "seen_articles_cache.json"
CACHE_EXPIRY = 7   # days — articles older than this are removed from cache


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _make_key(article: dict) -> str:
    """
    Creates a unique fingerprint for an article.
    Uses title + date so same story on different dates is re-processed.
    """
    raw = f"{article.get('title','').lower().strip()}_{article.get('date','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def filter_new_articles(articles: list) -> tuple:
    """
    Takes a list of fetched articles.
    Returns only the ones not seen before.
    Also marks returned articles as seen.
    Returns: (new_articles, skipped_count)
    """
    cache    = _load_cache()
    today    = datetime.today().strftime("%Y-%m-%d")
    new      = []
    skipped  = 0

    for article in articles:
        key = _make_key(article)
        if key in cache:
            skipped += 1
            continue
        # Mark as seen
        cache[key] = {
            "title":    article.get("title", "")[:80],
            "date":     article.get("date", ""),
            "seen_on":  today,
        }
        new.append(article)

    # Purge expired entries (older than CACHE_EXPIRY days)
    expiry_date = (datetime.today() - timedelta(days=CACHE_EXPIRY)).strftime("%Y-%m-%d")
    cache = {k: v for k, v in cache.items() if v.get("seen_on", "") >= expiry_date}

    _save_cache(cache)

    print(f"  [cache] {len(new)} new articles | {skipped} already seen — skipped")
    return new, skipped


def cache_stats() -> dict:
    cache = _load_cache()
    return {
        "total_cached": len(cache),
        "cache_file":   CACHE_FILE,
        "expiry_days":  CACHE_EXPIRY,
    }