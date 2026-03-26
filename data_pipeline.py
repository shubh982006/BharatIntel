"""
BharatGraph - Data Cleaning & Translation Layer
Input : list of raw article dicts (from fetch_news.py)
Output: list of cleaned + translated article dicts
Does NOT read or write any files — pure pipeline function.
"""

import re
from deep_translator import GoogleTranslator
from deep_translator.exceptions import LanguageNotSupportedException


def clean_text(text):
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r"http\S+|www\.\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\u0900-\u097F\w\s.,!?;:'\-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def translate_text(text):
    if not text:
        return {"translated_text": text, "was_translated": False}
    try:
        translator = GoogleTranslator(source="auto", target="en")
        result     = translator.translate(text)
        if not result:
            return {"translated_text": text, "was_translated": False}
        orig = re.sub(r"\s+", " ", text).strip().lower()
        res  = re.sub(r"\s+", " ", result).strip().lower()
        return {"translated_text": result.strip(), "was_translated": orig != res}
    except LanguageNotSupportedException:
        return {"translated_text": text, "was_translated": False}
    except Exception as e:
        print(f"  [translate] Error: {e}. Keeping original.")
        return {"translated_text": text, "was_translated": False}


def process_article(article):
    title   = article.get("title", "")
    content = article.get("content", "")
    raw_text    = f"{title}. {content}".strip()
    cleaned     = clean_text(raw_text)
    translation = translate_text(cleaned)
    return {
        "title":          clean_text(title),
        "cleaned_text":   translation["translated_text"],
        "was_translated": translation["was_translated"],
        "date":           article.get("date", ""),
        "source":         article.get("source", ""),
        "url":            article.get("url", ""),
        "content_source": article.get("content_source", "unknown"),
    }


def process_data(articles):
    """
    Takes raw article list, returns cleaned list.
    Pure function — no file I/O.
    """
    processed = []
    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article.get('title','')[:60]}...")
        processed.append(process_article(article))
    print(f"  Done. {len(processed)} articles cleaned.")
    return processed
