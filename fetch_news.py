"""
BharatGraph - Real-Time News Fetcher
Source : Google News RSS (trusted, verified, curated)
Content: newspaper3k extracts real article body from source URL
Fallback: Wikipedia summary if article is paywalled/blocked

No API key needed. Fully free. Fully real-time.
"""

import feedparser
import json
import re
import time
import requests
from datetime import datetime

try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False

QUERIES = [
    # ── GEOPOLITICS & DEFENSE ──────────────────────────────
    "India China LAC border",
    "India Pakistan Kashmir conflict",
    "China Sri Lanka Hambantota port",
    "China Pakistan CPEC",
    "India Nepal China",
    "China Maldives India",
    "India Bangladesh China",
    "China PLA Navy Indian Ocean",
    "India Bhutan China Doklam",
    "India Iran Chabahar",
    "Quad alliance India US",
    "China BRI Belt Road India",
    "Operation Sindoor India Pakistan",
    "India China Arunachal Pradesh",
    "China String of Pearls India",
    # ── ECONOMICS ──────────────────────────────────────────
    "India China trade sanctions economy",
    "India semiconductor supply chain",
    "China rare earth minerals India",
    "India energy oil imports dependency",
    "China debt trap developing countries India",
    # ── TECHNOLOGY ─────────────────────────────────────────
    "China 5G surveillance India neighbor",
    "India China cyber attack espionage",
    "China AI technology India competition",
    "ISRO India space China competition",
    "Huawei India ban technology",
    # ── CLIMATE & ENVIRONMENT ──────────────────────────────
    "Brahmaputra river China dam India water",
    "Himalayan glacier melt India China",
    "India climate change food security",
    "China pollution environment South Asia",
    "India renewable energy solar",
    # ── SOCIETY & DISINFORMATION ───────────────────────────
    "China disinformation India propaganda",
    "India minority rights society unrest",
    "Bangladesh Myanmar refugee India",
    "China Uyghur Pakistan India reaction",
    "India social media influence operations",
]

BASE_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

WIKI_TOPICS = {
    "India China LAC border":           "India-China border dispute",
    "India Pakistan Kashmir conflict":  "Kashmir conflict",
    "China Sri Lanka Hambantota port":  "Hambantota Port",
    "China Pakistan CPEC":              "China-Pakistan Economic Corridor",
    "India Nepal China":                "Nepal-China relations",
    "China Maldives India":             "China-Maldives relations",
    "India Bangladesh China":           "Bangladesh-China relations",
    "China PLA Navy Indian Ocean":      "Chinese naval activity in the Indian Ocean",
    "India Bhutan China Doklam":        "Doklam standoff",
    "India Iran Chabahar":              "Chabahar Port",
    "Quad alliance India US":           "Quadrilateral Security Dialogue",
    "China BRI Belt Road India":        "Belt and Road Initiative",
    "Operation Sindoor India Pakistan": "Operation Sindoor",
    "India China Arunachal Pradesh":    "Arunachal Pradesh boundary dispute",
    "China String of Pearls India":     "String of pearls Indian Ocean",
    "India China trade sanctions economy":     "India-China trade relations",
    "India semiconductor supply chain":         "Semiconductor supply chain",
    "China rare earth minerals India":          "Rare earth elements",
    "India energy oil imports dependency":      "Energy security of India",
    "China debt trap developing countries India": "Debt-trap diplomacy",
    "China 5G surveillance India neighbor":     "Huawei 5G controversy",
    "India China cyber attack espionage":       "Cyberwarfare in Asia",
    "China AI technology India competition":    "Artificial intelligence in China",
    "ISRO India space China competition":       "Indian Space Research Organisation",
    "Huawei India ban technology":              "Huawei security concerns",
    "Brahmaputra river China dam India water":  "Brahmaputra River",
    "Himalayan glacier melt India China":       "Himalayan glaciers",
    "India climate change food security":       "Climate change in India",
    "China pollution environment South Asia":   "Environmental issues in China",
    "India renewable energy solar":             "Solar power in India",
    "China disinformation India propaganda":    "Chinese propaganda",
    "India minority rights society unrest":     "Human rights in India",
    "Bangladesh Myanmar refugee India":         "Rohingya refugee crisis",
    "China Uyghur Pakistan India reaction":     "Xinjiang internment camps",
    "India social media influence operations":  "Information warfare",
}

MUST_HAVE = ["india", "indian", "modi", "new delhi", "delhi", "bharat"]
TOPICS = [
    # geopolitics & defense
    "china", "pakistan", "nepal", "bangladesh", "maldives", "bhutan",
    "sri lanka", "myanmar", "iran", "border", "military", "navy",
    "army", "missile", "defense", "defence", "cpec", "bri", "belt road",
    "quad", "strategic", "kashmir", "arunachal", "doklam", "galwan",
    "lac", "port", "sanctions", "geopolit", "conflict", "tension",
    "nuclear", "troops", "sovereignty", "sindoor", "indo-pacific",
    # economics
    "trade", "economy", "semiconductor", "supply chain", "rare earth",
    "debt", "energy", "oil", "import", "export", "inflation", "currency",
    "sanction", "tariff", "investment", "infrastructure",
    # technology
    "5g", "cyber", "surveillance", "artificial intelligence", "ai",
    "space", "satellite", "isro", "espionage", "hack", "huawei",
    "technology", "drone", "hypersonic",
    # climate
    "climate", "glacier", "river", "water", "flood", "drought",
    "environment", "pollution", "renewable", "solar", "emissions",
    "brahmaputra", "himalaya", "cyclone",
    # society
    "refugee", "minority", "protest", "disinformation", "propaganda",
    "election", "unrest", "humanitarian", "diaspora",
]
SKIP_KEYWORDS = [
    "upsc", "exam", "cricket", "ipl", "bollywood", "film", "movie",
    "recipe", "weather", "stock market", "nifty", "sensex",
    "fashion", "diet", "horoscope", "entertainment", "tourist", "travel",
]


def is_relevant(title):
    text = title.lower()
    if any(kw in text for kw in SKIP_KEYWORDS):
        return False
    return any(kw in text for kw in MUST_HAVE) and any(kw in text for kw in TOPICS)


def clean_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"&nbsp;|&amp;|&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(entry):
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:3]).strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.today().strftime("%Y-%m-%d")


def fetch_article_content(url):
    if not NEWSPAPER_AVAILABLE or not url:
        return ""
    try:
        article = Article(url, language="en")
        article.download()
        article.parse()
        text = article.text.strip()
        if text and len(text) > 150:
            return text[:1500]
    except Exception:
        pass
    return ""


def fetch_wikipedia_fallback(topic):
    if not topic:
        return ""
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(topic)
        resp = requests.get(url, timeout=8, headers={"User-Agent": "BharatGraph/1.0"})
        if resp.status_code == 200:
            extract = resp.json().get("extract", "")
            return extract[:800] if extract else ""
    except Exception:
        pass
    return ""


def fetch_all(max_per_query=4):
    """
    Fetches fresh articles from Google News RSS.
    Returns list — does NOT save to any file.
    Data flows directly into pipeline.
    """
    print("=" * 60)
    print("BharatGraph — Fetching Live News")
    print("=" * 60)

    print("\n[1] Loading Wikipedia fallback cache...")
    wiki_cache = {}
    for query, wiki_topic in WIKI_TOPICS.items():
        wiki_cache[query] = fetch_wikipedia_fallback(wiki_topic)

    print("\n[2] Fetching Google News RSS...")
    all_articles = []
    seen_titles  = set()

    for query in QUERIES:
        url = BASE_URL.format(query=query.replace(" ", "+"))
        print(f"\n  '{query}'...")
        try:
            feed  = feedparser.parse(url)
            count = 0
            for entry in feed.entries[:max_per_query]:
                raw_title   = clean_html(entry.get("title", ""))
                article_url = entry.get("link", "")
                date        = parse_date(entry)

                source = "Google News"
                title  = raw_title
                if " - " in raw_title:
                    parts  = raw_title.rsplit(" - ", 1)
                    title  = parts[0].strip()
                    source = parts[1].strip()

                if not title or not is_relevant(title):
                    continue

                key = title.lower().strip()
                if key in seen_titles:
                    continue
                seen_titles.add(key)

                # Try real article content
                content        = fetch_article_content(article_url)
                content_source = "article"

                # Fallback to Wikipedia
                if not content:
                    content        = wiki_cache.get(query, "")
                    content_source = "wikipedia_fallback"

                # Last resort
                if not content:
                    content        = title
                    content_source = "title_only"

                all_articles.append({
                    "title":          title,
                    "content":        content,
                    "date":           date,
                    "source":         source,
                    "url":            article_url,
                    "content_source": content_source,
                })
                count += 1
                time.sleep(0.5)

            print(f"    -> {count} articles")
        except Exception as e:
            print(f"    [ERROR] {e}")

    print(f"\nTotal: {len(all_articles)} articles fetched")
    return all_articles


if __name__ == "__main__":
    articles = fetch_all()
    if articles:
        for a in articles[:2]:
            print(f"\n  Title  : {a['title']}")
            print(f"  Source : {a['source']} | {a['date']}")
            print(f"  Type   : {a['content_source']}")
            print(f"  Content: {a['content'][:200]}...")