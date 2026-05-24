"""OpenSearch Serverless vector store — production replacement for Chroma."""

import boto3
import structlog
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from reportagent.config import get_settings
from reportagent.schemas import Chunk

log = structlog.get_logger()


def _get_opensearch_client() -> OpenSearch:
    """Create authenticated OpenSearch client using AWS credentials."""
    settings = get_settings()

    if not settings.opensearch_endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT not configured")

    # boto3.Session() auto-detects credentials from environment or IAM role
    session = boto3.Session(region_name=settings.aws_default_region)
    credentials = session.get_credentials().get_frozen_credentials()

    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        settings.aws_default_region,
        "aoss",
        session_token=credentials.token,
    )

    host = settings.opensearch_endpoint.replace("https://", "")

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )


class OpenSearchVectorStore:
    """
    OpenSearch Serverless vector store.
    Same interface as VectorStore (Chroma) — drop-in replacement.
    """

    def __init__(self, topic: str = "uk_economy"):
        self.client = _get_opensearch_client()
        self.index_name = f"articles_{topic}"

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        """Upsert chunks to OpenSearch index."""
        if not chunks:
            return

        actions = []
        for chunk in chunks:
            actions.append({"index": {"_index": self.index_name, "_id": chunk.id}})
            actions.append({
                "id": chunk.id,
                "article_id": chunk.article_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
            })

        self.client.bulk(body=actions)
        log.info("chunks_upserted_to_opensearch", count=len(chunks), index=self.index_name)

    def similarity_search(self, query_embedding: list[float], n_results: int = 10) -> list[Chunk]:
        """Search for similar chunks by embedding."""
        response = self.client.search(
            index=self.index_name,
            body={
                "size": n_results,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": n_results,
                        }
                    }
                },
                "_source": ["id", "article_id", "text", "chunk_index", "metadata"],
            },
        )

        chunks = []
        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            chunks.append(Chunk(
                id=src["id"],
                article_id=src["article_id"],
                text=src["text"],
                chunk_index=src.get("chunk_index", 0),
                metadata=src.get("metadata", {}),
            ))
        return chunks

    def article_exists(self, article_id: str) -> bool:
        """Check if any chunk with this article_id exists — used for deduplication."""
        response = self.client.search(
            index=self.index_name,
            body={
                "size": 1,
                "query": {
                    "term": {"article_id": article_id}
                },
                "_source": False,
            },
        )
        return response["hits"]["total"]["value"] > 0

    def get_all_chunk_texts(self) -> list[str]:
        """Get all chunk texts for BM25 index building."""
        response = self.client.search(
            index=self.index_name,
            body={
                "size": 1000,
                "query": {"match_all": {}},
                "_source": ["text"],
            },
        )
        return [hit["_source"]["text"] for hit in response["hits"]["hits"]]

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        stats = self.client.indices.stats(index=self.index_name)
        count = stats["indices"][self.index_name]["total"]["docs"]["count"]
        return {
            "collection_name": self.index_name,
            "document_count": count,
        }

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the collection."""
        return self.client.exists(index=self.index_name, id=doc_id)
