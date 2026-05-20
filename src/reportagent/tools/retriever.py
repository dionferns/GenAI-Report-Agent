"""Hybrid retrieval tool (BM25 + vector search)."""

from langchain_core.tools import tool
from rank_bm25 import BM25Okapi
from reportagent.schemas import Chunk
from reportagent.storage.vector import VectorStore
from sentence_transformers import SentenceTransformer
import structlog

log = structlog.get_logger()


class HybridRetriever:
    """Hybrid BM25 + vector retrieval."""

    def __init__(self, topic: str = "uk_ai_regulation"):
        self.vector_store = VectorStore(topic)
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._bm25 = None
        self._chunk_texts = None
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        """Rebuild BM25 index from all chunks in the vector store."""
        all_texts = self.vector_store.get_all_chunk_texts()
        if not all_texts:
            log.warning("no_chunks_for_bm25_index")
            self._bm25 = None
            self._chunk_texts = []
            return

        tokenized = [text.split() for text in all_texts]
        self._bm25 = BM25Okapi(tokenized)
        self._chunk_texts = all_texts
        log.info("bm25_index_rebuilt", chunk_count=len(all_texts))

    def retrieve(self, query: str, n_results: int = 8) -> list[Chunk]:
        """
        Hybrid retrieval using BM25 + vector search.
        Returns top chunks after deduplication and re-ranking.
        """
        results_dict = {}  # Use dict to deduplicate by chunk text

        # Vector search
        query_embedding = self.embedder.encode(query).tolist()
        vector_results = self.vector_store.similarity_search(query_embedding, n_results=10)

        for chunk in vector_results:
            results_dict[chunk.text] = {
                "chunk": chunk,
                "vector_score": 0.6,
                "bm25_score": 0.0,
            }

        # BM25 search
        if self._bm25 and self._chunk_texts:
            tokenized_query = query.split()
            bm25_scores = self._bm25.get_scores(tokenized_query)

            # Get top 10 BM25 results
            top_indices = sorted(
                range(len(bm25_scores)),
                key=lambda i: bm25_scores[i],
                reverse=True,
            )[:10]

            for idx in top_indices:
                if idx < len(self._chunk_texts):
                    text = self._chunk_texts[idx]
                    # Find corresponding chunk in vector store
                    if text in results_dict:
                        results_dict[text]["bm25_score"] = 0.4 * (bm25_scores[idx] / (max(bm25_scores) + 1e-9))
                    else:
                        # Create a simple chunk reference
                        results_dict[text] = {
                            "text": text,
                            "vector_score": 0.0,
                            "bm25_score": 0.4 * (bm25_scores[idx] / (max(bm25_scores) + 1e-9)),
                        }

        # Re-rank and return top n_results
        scored_results = [
            (item["chunk"], item["vector_score"] + item["bm25_score"])
            for item in results_dict.values()
            if "chunk" in item
        ]
        scored_results.sort(key=lambda x: x[1], reverse=True)

        final_results = [chunk for chunk, score in scored_results[:n_results]]
        log.info("hybrid_retrieval_completed", query_len=len(query), results=len(final_results))
        return final_results


@tool
def hybrid_search(query: str, topic: str = "uk_ai_regulation", n_results: int = 8) -> list[Chunk]:
    """
    Retrieves the most relevant document chunks using hybrid BM25 and vector search.
    """
    retriever = HybridRetriever(topic)
    return retriever.retrieve(query, n_results)
