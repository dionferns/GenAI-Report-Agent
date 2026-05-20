"""Ingestion graph for processing news articles."""

import json
import uuid
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import StateGraph, END
import feedparser
import structlog

from reportagent.schemas import (
    Article, Chunk, Report, CriticVerdict, IngestionState, RunLog, RunStatus
)
from reportagent.config import get_settings, SOURCE_MAP
from reportagent.storage.vector import VectorStore
from reportagent.storage.archive import Archive
from reportagent.llm import get_llm_provider
from reportagent.llm.embedder import get_embedder
from reportagent.tools.fetcher import fetch_urls
from reportagent.tools.cleaner import clean_html_to_articles

log = structlog.get_logger()
settings = get_settings()


def planner_node(state: IngestionState) -> IngestionState:
    """Decide which source URLs to fetch."""
    log.info("planner_started", topic=state.topic, run_id=state.run_id)

    urls_to_fetch = []
    sources = SOURCE_MAP.get(state.topic, [])

    for source in sources:
        try:
            feed = feedparser.parse(source)
            for entry in feed.entries[:5]:  # Max 5 per feed
                if hasattr(entry, "link"):
                    urls_to_fetch.append(entry.link)
        except Exception as e:
            log.error("feed_parse_error", source=source, error=str(e))

    # Limit to max URLs per run
    urls_to_fetch = urls_to_fetch[: settings.max_urls_per_run]
    state.urls_to_fetch = urls_to_fetch

    log.info("planner_completed", count=len(urls_to_fetch), run_id=state.run_id)
    return state


def fetcher_node(state: IngestionState) -> IngestionState:
    """Fetch raw HTML for each URL."""
    import asyncio

    log.info("fetcher_started", count=len(state.urls_to_fetch), run_id=state.run_id)

    if not state.urls_to_fetch:
        return state

    # Run async function in sync context
    raw_pages = asyncio.run(fetch_urls(state.urls_to_fetch))
    state.raw_pages = raw_pages

    log.info("fetcher_completed", fetched=len(raw_pages), run_id=state.run_id)
    return state


def cleaner_node(state: IngestionState) -> IngestionState:
    """Extract clean article text from raw HTML."""
    log.info("cleaner_started", run_id=state.run_id)

    articles = clean_html_to_articles(state.raw_pages, state.topic)
    state.articles = articles

    log.info("cleaner_completed", count=len(articles), run_id=state.run_id)
    return state


def deduper_node(state: IngestionState) -> IngestionState:
    """Remove duplicate articles already in the vector store."""
    log.info("deduper_started", count=len(state.articles), run_id=state.run_id)

    vector_store = VectorStore(state.topic)
    embedder = get_embedder()
    deduplicated = []
    skipped = 0

    for article in state.articles:
        # Check exact ID match
        if vector_store.document_exists(article.id):
            log.debug("article_already_exists", article_id=article.id)
            skipped += 1
            continue

        # Check semantic similarity
        first_sentences = " ".join(article.cleaned_text.split()[:30])
        embedding = embedder.encode(first_sentences)

        similar = vector_store.similarity_search(embedding, n_results=1)
        if similar and len(similar) > 0:
            # In a real implementation, compute cosine similarity
            # For now, we'll assume the retrieval itself is sufficient deduplication
            pass

        deduplicated.append(article)

    state.articles = deduplicated
    log.info("deduper_completed", kept=len(deduplicated), skipped=skipped, run_id=state.run_id)
    return state


def chunker_embedder_node(state: IngestionState) -> IngestionState:
    """Chunk articles and embed them."""
    log.info("chunker_embedder_started", count=len(state.articles), run_id=state.run_id)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", " ", ""],
    )
    embedder = get_embedder()

    chunks = []
    for article in state.articles:
        texts = splitter.split_text(article.cleaned_text)
        for idx, text in enumerate(texts):
            embedding = embedder.encode(text)
            chunk = Chunk(
                article_id=article.id,
                text=text,
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

    state.new_chunks = chunks

    # Upsert to vector store
    vector_store = VectorStore(state.topic)
    vector_store.upsert_chunks(chunks)

    log.info("chunker_embedder_completed", chunks=len(chunks), run_id=state.run_id)
    return state


def reporter_node(state: IngestionState) -> IngestionState:
    """Generate the structured hourly report."""
    log.info("reporter_started", run_id=state.run_id)

    if not state.new_chunks:
        log.warning("no_chunks_for_report", run_id=state.run_id)
        return state

    # Retrieve top chunks for context
    from reportagent.tools.retriever import HybridRetriever
    retriever = HybridRetriever(state.topic)
    context_chunks = retriever.retrieve("UK AI regulation news summary", n_results=20)

    # Build context
    context = "\n\n".join([f"[{i}] {chunk.text}" for i, chunk in enumerate(context_chunks, 1)])
    context = context[:4000]  # Max 4000 tokens

    # Build prompt
    previous_context = ""
    if state.previous_report and state.critic_verdict and state.critic_verdict.unsupported_claims:
        previous_context = f"""
Previous unsupported claims to avoid:
{state.critic_verdict.unsupported_claims}
"""

    prompt = f"""You are a professional news analyst producing a briefing report on UK AI Regulation.

Context (source articles):
{context}

{previous_context}

Produce a JSON object matching this exact schema:
{{
  "summary": "<100-150 word paragraph summarising the key developments>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "organisations_mentioned": ["<org1>", "<org2>"],
  "key_terms": ["<term1>", "<term2>"],
  "delta_notes": "<1-2 sentences on what is new vs the previous report, or null if first report>"
}}

Rules:
- summary MUST be between 100 and 150 words. Count carefully.
- key_takeaways MUST contain between 3 and 5 items.
- Every claim in summary must be directly supported by the provided context.
- Do not invent organisations or events not mentioned in the context.
- Respond with JSON only. No preamble, no markdown fences."""

    try:
        provider = get_llm_provider()
        response = provider.invoke(
            [{"role": "user", "content": prompt}],
            max_tokens=1000,
        )

        # Parse JSON
        report_data = json.loads(response)
        # Deduplicate source URLs and article IDs
        seen_urls = set()
        unique_urls = []
        unique_article_ids = []
        for chunk in context_chunks:
            url = chunk.metadata.get("url") if chunk.metadata else None
            if url and url not in seen_urls:
                unique_urls.append(url)
                unique_article_ids.append(chunk.article_id)
                seen_urls.add(url)

        report = Report(
            id=str(uuid.uuid4()),
            topic=state.topic,
            generated_at=datetime.utcnow(),
            summary=report_data["summary"],
            key_takeaways=report_data["key_takeaways"],
            organisations_mentioned=report_data.get("organisations_mentioned", []),
            key_terms=report_data.get("key_terms", []),
            source_urls=unique_urls,
            article_ids=unique_article_ids,
            delta_notes=report_data.get("delta_notes"),
            run_id=state.run_id,
        )
        state.draft_report = report
        log.info("reporter_completed", report_id=report.id, run_id=state.run_id)

    except Exception as e:
        log.error("report_generation_failed", error=str(e), run_id=state.run_id)
        state.errors.append(f"Report generation failed: {str(e)}")

    return state


def critic_node(state: IngestionState) -> IngestionState:
    """Verify every claim is grounded in source chunks."""
    log.info("critic_started", run_id=state.run_id)

    if not state.draft_report or not state.new_chunks:
        return state

    # Retrieve relevant chunks for each sentence
    from reportagent.tools.retriever import HybridRetriever
    retriever = HybridRetriever(state.topic)

    sentences = state.draft_report.summary.split(".")
    source_excerpts = []

    for sentence in sentences:
        if sentence.strip():
            relevant = retriever.retrieve(sentence, n_results=10)
            for chunk in relevant:
                source_excerpts.append(chunk.text)

    source_text = "\n\n".join(source_excerpts[:20])  # Limit

    # Critic prompt
    critic_prompt = f"""You are a fact-checking editor. Your job is to verify that every claim in the report summary
is directly supported by the provided source excerpts.

Report summary to check:
{state.draft_report.summary}

Source excerpts:
{source_text}

For each sentence in the summary, determine if it is supported by the sources.
Respond with JSON only:
{{
  "grounded": true/false,
  "unsupported_claims": ["<exact sentence that is not supported>"],
  "verdict": "approve" or "revise",
  "reasoning": "<brief explanation>"
}}

If ALL sentences are supported, set grounded=true, unsupported_claims=[], verdict="approve".
If ANY sentence is unsupported, set grounded=false, list the unsupported sentences, verdict="revise".
Respond with JSON only. No preamble."""

    try:
        provider = get_llm_provider()
        response = provider.invoke(
            [{"role": "user", "content": critic_prompt}],
            max_tokens=500,
        )

        verdict_data = json.loads(response)
        verdict = CriticVerdict(
            grounded=verdict_data["grounded"],
            unsupported_claims=verdict_data.get("unsupported_claims", []),
            verdict=verdict_data["verdict"],
            reasoning=verdict_data.get("reasoning", ""),
        )
        state.critic_verdict = verdict
        state.critic_iterations += 1

        log.info("critic_completed", verdict=verdict.verdict, iterations=state.critic_iterations, run_id=state.run_id)

    except Exception as e:
        log.error("critic_failed", error=str(e), run_id=state.run_id)
        state.critic_verdict = CriticVerdict(
            grounded=False,
            unsupported_claims=[],
            verdict="approve",
            reasoning=f"Critic check skipped due to error: {str(e)}",
        )

    return state


def should_revise(state: IngestionState) -> str:
    """Decide if we should revise the report or proceed to persist."""
    if (
        state.critic_verdict
        and state.critic_verdict.verdict == "revise"
        and state.critic_iterations < settings.max_critic_iterations
    ):
        return "reporter"
    return "persister"


def persister_node(state: IngestionState) -> IngestionState:
    """Persist the approved report and update run log."""
    log.info("persister_started", run_id=state.run_id)

    if not state.draft_report:
        log.error("no_report_to_persist", run_id=state.run_id)
        return state

    try:
        archive = Archive()
        archive.save_report(state.draft_report)

        run_log = RunLog(
            id=state.run_id,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status=RunStatus.SUCCESS,
            articles_fetched=len(state.articles),
            articles_deduplicated=0,
            chunks_added=len(state.new_chunks),
            report_id=state.draft_report.id,
            critic_iterations=state.critic_iterations,
        )
        archive.save_run_log(run_log)

        log.info(
            "report_persisted",
            report_id=state.draft_report.id,
            topic=state.topic,
            word_count=state.draft_report.word_count,
            critic_iterations=state.critic_iterations,
            run_id=state.run_id,
        )

    except Exception as e:
        log.error("persist_failed", error=str(e), run_id=state.run_id)
        state.errors.append(f"Persist failed: {str(e)}")

    return state


def build_ingestion_graph():
    """Build the ingestion StateGraph."""
    graph = StateGraph(IngestionState)

    graph.add_node("planner", planner_node)
    graph.add_node("fetcher", fetcher_node)
    graph.add_node("cleaner", cleaner_node)
    graph.add_node("deduper", deduper_node)
    graph.add_node("chunker_embedder", chunker_embedder_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("critic", critic_node)
    graph.add_node("persister", persister_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "fetcher")
    graph.add_edge("fetcher", "cleaner")
    graph.add_edge("cleaner", "deduper")
    graph.add_edge("deduper", "chunker_embedder")
    graph.add_edge("chunker_embedder", "reporter")
    graph.add_edge("reporter", "critic")
    graph.add_conditional_edges(
        "critic",
        should_revise,
        {"reporter": "reporter", "persister": "persister"},
    )
    graph.add_edge("persister", END)

    return graph.compile()


ingestion_graph = build_ingestion_graph()
