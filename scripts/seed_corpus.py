"""Seed the vector store with sample articles."""

from datetime import datetime
from reportagent.schemas import Article, Chunk
from reportagent.storage.vector import VectorStore
from sentence_transformers import SentenceTransformer

# Sample articles for seeding
SAMPLE_ARTICLES = [
    {
        "title": "UK announces new AI safety standards",
        "text": "The UK government has announced comprehensive AI safety standards to regulate high-risk AI systems. These standards focus on transparency, accountability, and ethical deployment. The Office for AI will oversee compliance and provide guidance to organizations implementing AI systems.",
        "url": "https://example.com/article1",
        "source": "gov_uk",
    },
    {
        "title": "BBC reports on AI regulation progress",
        "text": "Recent BBC reporting highlights the progress in UK AI regulation. The government's principles-based approach differs from the EU's prescriptive AI Act. Industry experts discuss the implications for innovation and safety.",
        "url": "https://example.com/article2",
        "source": "bbc_news",
    },
    {
        "title": "AI in healthcare: regulatory framework",
        "text": "Healthcare organizations are preparing for new AI regulations. The framework addresses high-risk applications including diagnostic AI systems. Compliance requirements include extensive testing and documentation.",
        "url": "https://example.com/article3",
        "source": "gov_uk",
    },
]


def seed_corpus():
    """Seed the vector store with sample articles."""
    vector_store = VectorStore("uk_ai_regulation")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    print("Seeding vector store with sample articles...")

    for article_data in SAMPLE_ARTICLES:
        # Create article
        article = Article(
            url=article_data["url"],
            title=article_data["title"],
            raw_text=article_data["text"][:500],
            cleaned_text=article_data["text"],
            source=article_data["source"],
            topic="uk_ai_regulation",
            fetched_at=datetime.utcnow(),
        )

        # Create chunks
        chunks = []
        sentences = article_data["text"].split(".")
        for idx, sentence in enumerate(sentences):
            if sentence.strip():
                embedding = embedder.encode(sentence.strip()).tolist()
                chunk = Chunk(
                    article_id=article.id,
                    text=sentence.strip(),
                    chunk_index=idx,
                    embedding=embedding,
                    metadata={
                        "url": str(article.url),
                        "source": article.source,
                        "topic": article.topic,
                        "fetched_at": article.fetched_at.isoformat(),
                        "article_id": article.id,
                    },
                )
                chunks.append(chunk)

        # Upsert chunks
        vector_store.upsert_chunks(chunks)
        print(f"✓ Seeded article: {article.title} ({len(chunks)} chunks)")

    print(f"\n✅ Seeding complete! {len(SAMPLE_ARTICLES)} articles added.")


if __name__ == "__main__":
    seed_corpus()
