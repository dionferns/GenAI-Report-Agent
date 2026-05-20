"""Test script for deduplication logic without LLM/embeddings."""

import feedparser
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from reportagent.config import get_settings, SOURCE_MAP
from reportagent.storage.vector import VectorStore

settings = get_settings()

def extract_articles_from_feeds(topic: str, max_articles: int = 10) -> dict:
    """Extract articles from RSS feeds and test deduplication."""

    sources = SOURCE_MAP.get(topic, [])
    if not sources:
        return {"error": f"Topic {topic} not found in SOURCE_MAP"}

    # Get vector store to check what's already processed
    vector_store = VectorStore(topic)

    all_urls = []
    print(f"\n📡 Fetching feeds for topic: {topic}")
    print(f"   Sources: {len(sources)}")

    # Collect all available URLs and their metadata
    all_entries = []
    for source in sources:
        try:
            feed = feedparser.parse(source)
            entries_count = len(feed.entries)
            print(f"   ✓ {source.split('/')[-1]}: {entries_count} articles")
            for entry in feed.entries:
                if hasattr(entry, "link"):
                    all_entries.append(entry)
        except Exception as e:
            print(f"   ✗ Error parsing {source}: {e}")

    print(f"\n📊 Total URLs available: {len(all_entries)}")

    # Simulate deduplication using correct Article ID computation
    new_urls = []
    duplicate_urls = []

    for entry in all_entries:
        url = entry.link

        # Extract published_at date from entry (same logic as cleaner)
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])

        # Compute article ID using same logic as Article schema
        url_str = url
        date_str = str(published_at.date()) if published_at else ""
        content = f"{url_str}{date_str}".encode()
        article_id = sha256(content).hexdigest()

        if vector_store.article_exists(article_id):
            duplicate_urls.append(url)
        else:
            new_urls.append(url)
            if len(new_urls) >= max_articles:
                break

    print(f"✅ New articles found: {len(new_urls)}")
    print(f"⏭️  Duplicates skipped: {len(duplicate_urls)}")

    if len(new_urls) == 0 and len(all_entries) > 0:
        print(f"⚠️  NO NEW ARTICLES FOUND - All {len(all_entries)} available articles have been processed!")
        all_processed = True
    else:
        all_processed = False

    return {
        "topic": topic,
        "total_available": len(all_entries),
        "new_urls": new_urls,
        "duplicate_urls": duplicate_urls,
        "all_processed": all_processed,
    }


def fetch_and_extract_articles(urls: list) -> list:
    """Fetch HTML and extract articles (minimal extraction for testing)."""
    from reportagent.tools.fetcher import fetch_urls
    from reportagent.tools.cleaner import clean_html_to_articles
    import asyncio

    if not urls:
        return []

    print(f"\n🔗 Fetching {len(urls)} URLs...")
    raw_pages = asyncio.run(fetch_urls(urls))
    print(f"   Fetched: {len(raw_pages)}")

    print(f"🧹 Cleaning HTML to articles...")
    articles = clean_html_to_articles(raw_pages, "test_topic")
    print(f"   Cleaned: {len(articles)}")

    return articles


def write_articles_to_md(articles: list, filename: str):
    """Write articles to markdown file."""
    md_content = f"# Deduplication Test Results\n"
    md_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    md_content += f"Total Articles: {len(articles)}\n\n"

    for i, article in enumerate(articles, 1):
        preview = article.cleaned_text[:200] + "..." if len(article.cleaned_text) > 200 else article.cleaned_text
        md_content += f"## Article {i}\n\n"
        md_content += f"**Title:** {article.title}\n\n"
        md_content += f"**URL:** {article.url}\n\n"
        md_content += f"**Source:** {article.source}\n\n"
        md_content += f"**Preview:**\n{preview}\n\n"
        md_content += "---\n\n"

    Path("./data").mkdir(exist_ok=True)
    with open(f"./data/{filename}", "w") as f:
        f.write(md_content)

    print(f"\n📄 Results saved to: ./data/{filename}")


def main():
    """Run deduplication test."""
    print("=" * 60)
    print("🧪 DEDUPLICATION TEST")
    print("=" * 60)

    topic = settings.default_topic
    max_articles = settings.max_urls_per_run

    # Step 1: Check for new articles
    print(f"\n🔍 Step 1: Checking for new articles (max {max_articles})")
    result = extract_articles_from_feeds(topic, max_articles)

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    # Step 2: Print summary
    print(f"\n📋 SUMMARY:")
    print(f"   Total available in RSS: {result['total_available']}")
    print(f"   New articles: {result['new_urls']}")
    print(f"   Already processed: {len(result['duplicate_urls'])}")
    print(f"   All processed: {result['all_processed']}")

    if result['all_processed']:
        print(f"\n⚠️  STATUS: No new articles available")
        print(f"    All {result['total_available']} articles in RSS feeds have been processed")
        status = "NO_NEW_ARTICLES"
    else:
        # Step 3: Fetch and extract articles
        print(f"\n🔍 Step 2: Fetching and extracting articles")
        articles = fetch_and_extract_articles(result['new_urls'])

        # Step 4: Write to markdown
        if articles:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_dedup_{timestamp}.md"
            write_articles_to_md(articles, filename)
            status = "SUCCESS"
            print(f"\n✅ Extracted {len(articles)} new articles")
        else:
            status = "NO_ARTICLES_EXTRACTED"
            print(f"\n⚠️  No articles were extracted")

    print(f"\n{'=' * 60}")
    print(f"Test Status: {status}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
