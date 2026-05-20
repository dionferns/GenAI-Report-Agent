"""Vector store wrapper around Chroma."""

import chromadb
from reportagent.config import get_settings
from reportagent.schemas import Chunk
import structlog

log = structlog.get_logger()


class VectorStore:
    """Wrapper around Chroma for chunk storage and retrieval."""

    def __init__(self, topic: str = "uk_economy"):
        settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir
        )
        self.collection_name = f"articles_{topic}"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        """Upsert chunks to the vector store."""
        if not chunks:
            return

        ids = [chunk.id for chunk in chunks]
        embeddings = [chunk.embedding for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        documents = [chunk.text for chunk in chunks]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        log.info("chunks_upserted", count=len(chunks), collection=self.collection_name)

    def similarity_search(
        self, query_embedding: list[float], n_results: int = 10
    ) -> list[Chunk]:
        """Search for similar chunks by embedding."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        chunks = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, chunk_id in enumerate(results["ids"][0]):
                chunk = Chunk(
                    id=chunk_id,
                    article_id=results["metadatas"][0][i].get("article_id", ""),
                    text=results["documents"][0][i],
                    chunk_index=results["metadatas"][0][i].get("chunk_index", 0),
                    metadata=results["metadatas"][0][i],
                )
                chunks.append(chunk)

        return chunks

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the collection."""
        try:
            result = self.collection.get(ids=[doc_id])
            return len(result["ids"]) > 0
        except Exception:
            return False

    def article_exists(self, article_id: str) -> bool:
        """Check if an article (by ID) exists in the collection."""
        try:
            result = self.collection.get(where={"article_id": article_id})
            return len(result["ids"]) > 0
        except Exception:
            return False

    def get_all_chunk_texts(self) -> list[str]:
        """Get all chunk texts for BM25 index building."""
        results = self.collection.get()
        return results.get("documents", [])

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "document_count": count,
        }
