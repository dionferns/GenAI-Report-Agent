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
from reportagent.observability.run_logger import RunLogger

log = structlog.get_logger()
settings = get_settings()

# Create run logger (will be initialized in planner_node)
run_logger: RunLogger = None


def planner_node(state: IngestionState) -> IngestionState:
    """Decide which source URLs to fetch, skipping already-processed articles."""
    global run_logger
    run_logger = RunLogger(state.run_id)

    log.info("planner_started", topic=state.topic, run_id=state.run_id)
    run_logger.log("planner_started", topic=state.topic)
    log.debug("source_map_available_topics", topics=list(SOURCE_MAP.keys()))

    sources = SOURCE_MAP.get(state.topic, [])

    if not sources:
        log.error("topic_not_in_source_map", topic=state.topic, available_topics=list(SOURCE_MAP.keys()))
        run_logger.log("error_topic_not_found", topic=state.topic)
        return state

    log.debug("fetching_from_sources", source_count=len(sources), sources=sources)

    # Collect all available URLs from feeds (don't limit yet)
    all_urls = []
    for source in sources:
        try:
            feed = feedparser.parse(source)
            entries_count = len(feed.entries)
            log.debug("feed_parsed", source=source, entries_found=entries_count)
            urls_from_this_feed = 0
            for entry in feed.entries:  # Get ALL entries, not just first 10
                if hasattr(entry, "link"):
                    all_urls.append(entry.link)
                    urls_from_this_feed += 1
            log.debug("urls_extracted_from_feed", source=source, count=urls_from_this_feed)
        except Exception as e:
            log.error("feed_parse_error", source=source, error=str(e))

    log.info("total_urls_available", count=len(all_urls))

    # Skip URLs we've already tried in this run (when retrying after all-duplicates)
    urls_not_tried = [url for url in all_urls if url not in state.urls_tried_in_run]

    if not urls_not_tried:
        # We've tried all available URLs and found no new articles
        log.warning("all_urls_exhausted", total=len(all_urls), tried=len(state.urls_tried_in_run))
        run_logger.log("planner_decision", decision="all_urls_exhausted", total=len(all_urls), tried=len(state.urls_tried_in_run))
        state.urls_to_fetch = []
        state.processed_all_articles = True
    else:
        # Take next batch of URLs to fetch
        urls_to_fetch = urls_not_tried[:settings.max_urls_per_run]
        state.urls_to_fetch = urls_to_fetch
        state.urls_tried_in_run.extend(urls_to_fetch)  # Track which URLs we're trying
        state.processed_all_articles = False
        log.info("urls_selected_for_fetching", count=len(urls_to_fetch), not_tried=len(urls_not_tried))
        run_logger.log_planner(
            all_urls=len(all_urls),
            urls_tried=state.urls_tried_in_run,
            urls_to_fetch=urls_to_fetch,
            processed_all=False,
        )

    log.info("planner_completed", new_urls=len(urls_to_fetch), run_id=state.run_id)
    return state


def fetcher_node(state: IngestionState) -> IngestionState:
    """Fetch raw HTML for each URL."""
    import asyncio

    log.info("fetcher_started", count=len(state.urls_to_fetch), run_id=state.run_id)

    if not state.urls_to_fetch:
        log.warning("no_urls_to_fetch", processed_all=state.processed_all_articles, run_id=state.run_id)
        return state

    log.debug("urls_to_fetch", urls=state.urls_to_fetch[:3])  # Log first 3 URLs

    # Run async function in sync context
    raw_pages = asyncio.run(fetch_urls(state.urls_to_fetch))
    state.raw_pages = raw_pages

    log.info("fetcher_completed", fetched=len(raw_pages), total_requested=len(state.urls_to_fetch), run_id=state.run_id)
    return state


def cleaner_node(state: IngestionState) -> IngestionState:
    """Extract clean article text from raw HTML."""
    log.info("cleaner_started", raw_pages_count=len(state.raw_pages), run_id=state.run_id)

    articles = clean_html_to_articles(state.raw_pages, state.topic)
    state.articles = articles

    log.debug("articles_extracted", count=len(articles), titles=[a.title for a in articles[:3]])
    log.info("cleaner_completed", count=len(articles), run_id=state.run_id)
    return state


def deduper_node(state: IngestionState) -> IngestionState:
    """Remove duplicate articles already in the vector store."""
    global run_logger
    log.info("deduper_started", count=len(state.articles), run_id=state.run_id)

    vector_store = VectorStore(state.topic)
    embedder = get_embedder()
    deduplicated = []
    skipped = 0
    skipped_ids = []
    kept_ids = []

    for article in state.articles:
        # Check exact ID match (using article_id, not chunk id)
        if vector_store.article_exists(article.id):
            log.debug("article_already_exists", article_id=article.id, title=article.title)
            skipped += 1
            skipped_ids.append({"id": article.id, "title": article.title, "url": str(article.url)})
            continue

        # If article is not in store, it's new
        deduplicated.append(article)
        kept_ids.append({"id": article.id, "title": article.title, "url": str(article.url)})

    state.articles = deduplicated

    # Log deduplication results
    run_logger.log_deduper(
        input_articles=len(state.articles) + skipped,
        kept=len(deduplicated),
        skipped=skipped,
        article_ids={"kept": kept_ids, "skipped": skipped_ids},
    )

    # Write markdown file only for articles that passed deduplication
    if deduplicated:
        md_content = f"# Extracted Articles — {state.run_id}\n\n"
        for i, article in enumerate(deduplicated, 1):
            preview = article.cleaned_text[:200] + "..." if len(article.cleaned_text) > 200 else article.cleaned_text
            md_content += f"## Article {i}\n\n"
            md_content += f"**Title:** {article.title}\n\n"
            md_content += f"**Source:** {article.source}\n\n"
            md_content += f"**URL:** {article.url}\n\n"
            md_content += f"**Preview:**\n{preview}\n\n"
            md_content += "---\n\n"

        import pathlib
        pathlib.Path("./data").mkdir(exist_ok=True)
        with open(f"./data/extracted_articles_{state.run_id}.md", "w") as f:
            f.write(md_content)
        log.info("articles_logged_to_file", filename=f"extracted_articles_{state.run_id}.md", article_count=len(deduplicated))

    # If all fetched articles were duplicates, log decision but DON'T set processed_all_articles yet
    # (planner will set it when it exhausts all URLs)
    if len(deduplicated) == 0 and skipped > 0:
        log.warning("all_fetched_articles_were_duplicates", skipped=skipped, duplicates_found=skipped)
        run_logger.log("deduper_decision", decision="all_duplicates", will_retry=True)

    new_titles = [a.title for a in deduplicated[:3]]
    log.info("deduper_completed", kept=len(deduplicated), skipped=skipped, new_articles=new_titles, run_id=state.run_id)
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
    query = f"{state.topic.replace('_', ' ').title()} news summary"
    context_chunks = retriever.retrieve(query, n_results=20)

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

    prompt = f"""You are a professional news analyst producing a briefing report.

Context (source articles):
{context}

{previous_context}

Your task: Write a summary that is EXACTLY 100-150 words. Count every word carefully.

Produce ONLY a JSON object with NO other text:
{{
  "summary": "<Write exactly 100-150 words. This is critical. Count carefully before submitting.>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "organisations_mentioned": ["<org1>", "<org2>"],
  "key_terms": ["<term1>", "<term2>"],
  "delta_notes": "<1-2 sentences on what is new vs the previous report, or null if first report>"
}}

STRICT RULES:
- The summary field MUST contain EXACTLY 100-150 words. NO MORE, NO LESS.
- Count every single word in the summary before you submit it.
- If your summary is less than 100 words, add more details from the context.
- If your summary is more than 150 words, remove less important details.
- key_takeaways MUST be 3-5 items.
- Every claim must be supported by the provided context.
- Do NOT invent organisations or events.
- Respond with ONLY the JSON object. No preamble, no markdown, no explanation."""

    try:
        from pydantic import ValidationError

        max_retries = 3
        retry_count = 0
        report_data = None
        report = None
        last_error = None

        while retry_count < max_retries and report is None:
            try:
                provider = get_llm_provider()
                response = provider.invoke(
                    [{"role": "user", "content": [{"text": prompt}]}],
                    max_tokens=1000,
                )

                log.debug("llm_response_raw", response_len=len(response), response_preview=response[:200], attempt=retry_count+1)

                # Extract JSON from response (handle models that add text around JSON)
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    report_data = json.loads(json_str)

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

                    # Try to create Report object to trigger validation
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
                    log.info("report_generated_successfully", attempt=retry_count+1, report_id=report.id)
                else:
                    raise ValueError("No JSON found in response")

            except (ValueError, json.JSONDecodeError, ValidationError, KeyError) as e:
                last_error = str(e)
                retry_count += 1
                log.warning("report_generation_failed_retrying", error=last_error, attempt=retry_count, max_retries=max_retries)
                if retry_count >= max_retries:
                    raise ValueError(f"Failed to generate valid report after {max_retries} attempts: {last_error}")

        if report:
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

    # Check if all articles have been processed
    if state.processed_all_articles:
        log.warning("all_articles_processed", topic=state.topic, message="No new articles found. All available articles in RSS feeds have already been processed.")
        return state

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


def after_deduper(state: IngestionState) -> str:
    """Decide whether to continue or fetch more articles if all were duplicates."""
    if len(state.articles) == 0 and not state.processed_all_articles:
        # All articles were duplicates, try fetching more
        log.warning("all_articles_duplicate_retrying", run_id=state.run_id)
        return "planner"  # Loop back to planner to fetch more URLs
    else:
        # Continue with chunking/embedding
        return "chunker_embedder"


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
    graph.add_conditional_edges(
        "deduper",
        after_deduper,
        {"chunker_embedder": "chunker_embedder", "planner": "planner"},
    )
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
