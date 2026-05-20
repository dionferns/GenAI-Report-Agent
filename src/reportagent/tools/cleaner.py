"""HTML to article cleaner tool."""

import trafilatura
from trafilatura.metadata import extract_metadata
from datetime import datetime
from reportagent.schemas import Article
import structlog

log = structlog.get_logger()


def clean_html_to_articles(
    raw_pages: list[tuple[str, str, datetime]], topic: str = "uk_economy"
) -> list[Article]:
    """
    Extracts clean article text from raw HTML using trafilatura,
    removing navigation, ads, and boilerplate.
    Returns list of Article objects.
    """
    articles = []

    for url, html, fetched_at in raw_pages:
        try:
            log.debug("cleaning_url", url=url, html_length=len(html))

            # Extract clean text
            extracted_text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            )

            if not extracted_text:
                log.warning("extraction_failed", url=url, html_length=len(html))
                continue

            # Extract metadata
            metadata = extract_metadata(html)
            title = metadata.title if metadata and hasattr(metadata, 'title') else ""
            author = metadata.author if metadata and hasattr(metadata, 'author') else ""
            date = metadata.date if metadata and hasattr(metadata, 'date') else None

            # Parse published date
            published_at = None
            if date:
                try:
                    from dateutil import parser
                    published_at = parser.parse(date)
                except Exception:
                    pass

            # Determine source
            source = "unknown"
            if "bbc" in url.lower():
                source = "bbc_news"
            elif "gov.uk" in url.lower():
                source = "gov_uk"

            article = Article(
                url=url,
                title=title or url,
                raw_text=html[:1000],  # Store first 1000 chars of raw HTML
                cleaned_text=extracted_text,
                source=source,
                topic=topic,
                fetched_at=fetched_at,
                published_at=published_at,
            )
            articles.append(article)
            log.debug("article_cleaned", url=url, source=source)

        except Exception as e:
            log.error("cleaning_error", url=url, error=str(e))

    log.info("articles_cleaned", count=len(articles))
    return articles
