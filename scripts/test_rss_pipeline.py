"""
Test script to verify RSS fetching, article extraction, ID generation, and deduplication logic.
Run with: python scripts/test_rss_pipeline.py
"""

import asyncio
import hashlib
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import feedparser
from reportagent.config import SOURCE_MAP, get_settings
from reportagent.tools.fetcher import fetch_urls
from reportagent.tools.cleaner import clean_html_to_articles
from reportagent.storage.vector import VectorStore

TOPIC = "uk_economy"
MAX_URLS = 5  # Keep small for testing


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Stage 1: RSS Feed Parsing ────────────────────────────────

separator("STAGE 1: RSS Feed Parsing")

sources = SOURCE_MAP.get(TOPIC, [])
print(f"Topic: {TOPIC}")
print(f"Sources configured: {len(sources)}")

all_urls = []
for source in sources:
    print(f"\nParsing: {source}")
    feed = feedparser.parse(source)
    urls = [e.link for e in feed.entries if hasattr(e, "link")]
    all_urls.extend(urls)
    print(f"  Entries found: {len(feed.entries)}")
    print(f"  URLs extracted: {len(urls)}")
    for url in urls[:3]:
        print(f"    - {url}")
    if len(urls) > 3:
        print(f"    ... and {len(urls) - 3} more")

print(f"\nTotal URLs across all feeds: {len(all_urls)}")

if not all_urls:
    print("ERROR: No URLs found. Check network connection or RSS feed URLs.")
    sys.exit(1)


# ── Stage 2: Fetch HTML ───────────────────────────────────────

separator("STAGE 2: Fetching HTML")

urls_to_fetch = all_urls[:MAX_URLS]
print(f"Fetching {len(urls_to_fetch)} URLs...")

raw_pages = asyncio.run(fetch_urls(urls_to_fetch))
print(f"Successfully fetched: {len(raw_pages)} / {len(urls_to_fetch)}")

for url, html, fetched_at in raw_pages:
    print(f"  ✅ {url[:80]}... ({len(html)} chars)")

failed = set(urls_to_fetch) - {url for url, _, _ in raw_pages}
for url in failed:
    print(f"  ❌ FAILED: {url}")


# ── Stage 3: Clean & Extract Articles ────────────────────────

separator("STAGE 3: Cleaning HTML → Articles")

articles = clean_html_to_articles(raw_pages, topic=TOPIC)
print(f"Articles extracted: {len(articles)} / {len(raw_pages)}")

for article in articles:
    print(f"\n  Article:")
    print(f"    ID:           {article.id}")
    print(f"    Title:        {article.title[:70]}")
    print(f"    URL:          {str(article.url)[:70]}")
    print(f"    Source:       {article.source}")
    print(f"    Published:    {article.published_at}")
    print(f"    Fetched at:   {article.fetched_at}")
    print(f"    Word count:   {article.word_count}")
    print(f"    Text preview: {article.cleaned_text[:100].strip()}...")


# ── Stage 4: ID Generation Verification ──────────────────────

separator("STAGE 4: Article ID Verification (SHA256)")

print("Verifying IDs are deterministic and unique...\n")

ids_seen = set()
all_unique = True

for article in articles:
    # Recompute expected ID
    url_str = str(article.url)
    date_str = str(article.published_at.date()) if article.published_at else ""
    expected_id = hashlib.sha256(f"{url_str}{date_str}".encode()).hexdigest()

    id_match = article.id == expected_id
    is_duplicate = article.id in ids_seen

    status = "✅" if id_match and not is_duplicate else "❌"
    print(f"  {status} {article.title[:50]}")
    print(f"     ID:       {article.id[:16]}...")
    print(f"     Expected: {expected_id[:16]}...")
    print(f"     ID match: {id_match} | Duplicate: {is_duplicate}")

    if not id_match:
        all_unique = False
    ids_seen.add(article.id)

print(f"\nAll IDs correct:  {all_unique}")
print(f"All IDs unique:   {len(ids_seen) == len(articles)}")


# ── Stage 5: Deduplication Check Against Vector Store ────────

separator("STAGE 5: Deduplication Check (Vector Store)")

try:
    vector_store = VectorStore(topic=TOPIC)
    stats = vector_store.get_collection_stats()
    print(f"Vector store collection: {stats['collection_name']}")
    print(f"Existing chunks in store: {stats['document_count']}\n")

    new_articles = []
    duplicate_articles = []

    for article in articles:
        exists = vector_store.article_exists(article.id)
        if exists:
            duplicate_articles.append(article)
            print(f"  🔁 DUPLICATE: {article.title[:60]}")
            print(f"              ID: {article.id[:16]}...")
        else:
            new_articles.append(article)
            print(f"  🆕 NEW:       {article.title[:60]}")
            print(f"              ID: {article.id[:16]}...")

    print(f"\nSummary:")
    print(f"  New articles:       {len(new_articles)}")
    print(f"  Duplicate articles: {len(duplicate_articles)}")

except Exception as e:
    print(f"  ⚠️  Could not connect to vector store: {e}")
    print("  (This is fine if no ingestion has been run yet)")


# ── Summary ───────────────────────────────────────────────────

separator("SUMMARY")

print(f"  RSS feeds parsed:      {len(sources)}")
print(f"  Total URLs found:      {len(all_urls)}")
print(f"  URLs fetched:          {len(raw_pages)}")
print(f"  Articles extracted:    {len(articles)}")
print(f"  IDs verified:          {'✅ All correct' if all_unique else '❌ Mismatch found'}")
print(f"  ID uniqueness:         {'✅ All unique' if len(ids_seen) == len(articles) else '❌ Duplicates found'}")
print()
