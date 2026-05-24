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
            # OpenSearch Serverless does NOT support explicit document IDs
            # Must let AOSS generate IDs automatically
            actions.append({"index": {"_index": self.index_name}})
            actions.append({
                "id": chunk.id,
                "article_id": chunk.article_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
            })

        response = self.client.bulk(body=actions)

        # Check for partial failures in bulk operation
        if response.get("errors"):
            error_items = [item for item in response["items"] if "error" in item.get("index", {})]
            log.error("bulk_upsert_had_errors", error_count=len(error_items), total=len(chunks), index=self.index_name)
            for error_item in error_items[:5]:  # Log first 5 errors
                log.error("bulk_error_detail", error=error_item.get("index", {}).get("error"))
        else:
            log.info("chunks_upserted_to_opensearch", count=len(chunks), index=self.index_name)

    def similarity_search(self, query_embedding: list[float], n_results: int = 10) -> list[Chunk]:
        """Search for similar chunks by embedding."""
        try:
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
                # Defensive: use .get() for all fields to handle incomplete docs
                chunk = Chunk(
                    id=src.get("id", ""),
                    article_id=src.get("article_id", ""),
                    text=src.get("text", ""),
                    chunk_index=src.get("chunk_index", 0),
                    metadata=src.get("metadata", {}),
                )
                chunks.append(chunk)
            return chunks
        except Exception as e:
            log.error("similarity_search_failed", error=str(e), index=self.index_name)
            return []

    def article_exists(self, article_id: str) -> bool:
        """Check if any chunk with this article_id exists — used for deduplication."""
        try:
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
        except Exception as e:
            log.error("article_exists_check_failed", error=str(e), article_id=article_id)
            return False

    def get_all_chunk_texts(self) -> list[str]:
        """Get all chunk texts for BM25 index building. Uses pagination for >1000 chunks."""
        try:
            all_texts = []
            from_offset = 0
            page_size = 1000
            max_iterations = 1000  # Safety limit: max 1M chunks (1000 * 1000)

            iterations = 0
            while iterations < max_iterations:
                iterations += 1
                response = self.client.search(
                    index=self.index_name,
                    body={
                        "size": page_size,
                        "from": from_offset,
                        "query": {"match_all": {}},
                        "_source": ["text"],
                    },
                )

                hits = response["hits"]["hits"]
                if not hits:
                    break

                all_texts.extend([hit["_source"]["text"] for hit in hits])
                from_offset += page_size

                if len(hits) < page_size:
                    break

            if iterations >= max_iterations:
                log.warning("get_all_chunk_texts_hit_max_iterations", max=max_iterations, index=self.index_name)

            log.info("all_chunk_texts_retrieved", total_texts=len(all_texts), iterations=iterations, index=self.index_name)
            return all_texts
        except Exception as e:
            log.error("get_all_chunk_texts_failed", error=str(e), index=self.index_name)
            return []

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        try:
            stats = self.client.indices.stats(index=self.index_name)
            count = stats["indices"][self.index_name]["total"]["docs"]["count"]
            return {
                "collection_name": self.index_name,
                "document_count": count,
            }
        except Exception as e:
            log.error("get_collection_stats_failed", error=str(e), index=self.index_name)
            return {
                "collection_name": self.index_name,
                "document_count": 0,
            }

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the collection."""
        try:
            return self.client.exists(index=self.index_name, id=doc_id)
        except Exception as e:
            log.error("document_exists_check_failed", error=str(e), doc_id=doc_id)
            return False
