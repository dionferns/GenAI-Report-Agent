"""Chat graph for conversational question answering."""

import json
import re
from datetime import datetime
from langgraph.graph import StateGraph, END
import structlog

from reportagent.schemas import ChatState, ChatMessage, MessageRole, Citation
from reportagent.storage.archive import Archive
from reportagent.guardrails import injection, pii
from reportagent.tools.retriever import HybridRetriever
from reportagent.llm import get_llm_provider

log = structlog.get_logger()


def guardrail_node(state: ChatState) -> ChatState:
    """Sanitise user input before any LLM call."""
    log.info("guardrail_started", session_id=state.session_id)

    query = state.current_query

    # Check for injection
    is_safe, reason = injection.check(query)
    if not is_safe:
        log.warning("injection_detected", session_id=state.session_id, reason=reason)
        state.guardrail_triggered = True
        state.response = ChatMessage(
            role=MessageRole.ASSISTANT,
            content="I can't process that request. Please ask a legitimate question about the news content.",
        )
        return state

    # Scrub PII
    sanitised = pii.scrub(query)
    state.sanitised_query = sanitised

    log.info("guardrail_passed", session_id=state.session_id)
    return state


def query_router_node(state: ChatState) -> ChatState:
    """Classify the query to determine retrieval strategy."""
    log.info("query_router_started", session_id=state.session_id)

    query = state.sanitised_query

    # Rule-based classification
    latest_keywords = ["latest", "today", "now", "recent", "this week", "latest news"]
    historical_keywords = ["when", "previous", "before", "2024", "2023", "regulation"]
    vague_keywords = ["what", "how", "why", "explain", "tell me"]

    query_lower = query.lower()

    if any(kw in query_lower for kw in latest_keywords):
        state.query_type = "latest"
    elif any(kw in query_lower for kw in historical_keywords):
        state.query_type = "historical"
    elif len(query.split()) < 5:
        state.query_type = "vague"
    elif "did" in query_lower and "?" in query:
        state.query_type = "adversarial"
    else:
        state.query_type = "vague"

    log.info("query_classified", session_id=state.session_id, query_type=state.query_type)
    return state


def retriever_node(state: ChatState) -> ChatState:
    """Retrieve relevant chunks using hybrid search."""
    log.info("retriever_started", session_id=state.session_id, query_type=state.query_type, topic=state.topic)

    retriever = HybridRetriever(topic=state.topic)
    chunks = retriever.retrieve(state.sanitised_query, n_results=8)
    state.retrieved_chunks = chunks

    # If latest query, fetch the latest report
    if state.query_type == "latest":
        archive = Archive()
        latest_report = archive.get_latest_report(state.topic)
        state.latest_report = latest_report

    log.info("retriever_completed", session_id=state.session_id, chunks=len(chunks))
    return state


def responder_node(state: ChatState) -> ChatState:
    """Generate the final answer with inline citations."""
    log.info("responder_started", session_id=state.session_id)

    # Build context - store chunks with their indices for citation mapping
    context_parts = []
    chunk_sources = {}  # Map index to source URL
    for i, chunk in enumerate(state.retrieved_chunks, 1):
        context_parts.append(f"[{i}] {chunk.text}")
        url = chunk.metadata.get("url", "") if chunk.metadata else ""
        if url:
            chunk_sources[i] = url

    if state.latest_report:
        context_parts.append(f"\nLatest Report Summary:\n{state.latest_report.summary}")

    context = "\n\n".join(context_parts)

    # Build instructions based on query type
    instructions = ""
    topic_display = state.topic.replace("_", " ").title()
    if state.query_type == "vague":
        instructions = f"Provide a general summary of the current state of {topic_display} based on the context."
    elif state.query_type == "adversarial":
        instructions = "Only state facts that are directly present in the context. If the context does not confirm the claim in the question, say so explicitly."
    else:
        instructions = "Answer the user's question based on the provided context."

    prompt = f"""{instructions}

Context:
{context}

Question: {state.sanitised_query}

Provide a clear, factual answer. Reference sources using [1], [2] etc. where [N] corresponds to the Nth piece of context above.
Respond with the answer text only. Start with the answer, not with "Based on the context" or similar."""

    try:
        provider = get_llm_provider()
        response_text = provider.invoke(
            [{"role": "user", "content": prompt}],
            max_tokens=500,
        )

        # Extract citations from response
        citations = []
        citation_pattern = r"\[(\d+)\]"
        seen_indices = set()
        for match in re.finditer(citation_pattern, response_text):
            idx = int(match.group(1))
            if idx in chunk_sources and idx not in seen_indices:
                url = chunk_sources[idx]
                chunk = state.retrieved_chunks[idx - 1]
                citation = Citation(
                    index=idx,
                    url=url,
                    title=url.split("/")[-1] if url else "Source",
                    retrieved_at=datetime.utcnow(),
                    chunk_id=chunk.id,
                )
                citations.append(citation)
                seen_indices.add(idx)

        response = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response_text,
            citations=citations,
        )
        state.response = response

        log.info("responder_completed", session_id=state.session_id, citations=len(citations))

    except Exception as e:
        log.error("responder_failed", error=str(e), session_id=state.session_id)
        state.response = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=f"I encountered an error processing your question: {str(e)}",
        )

    return state


def should_check_faithfulness(state: ChatState) -> str:
    """Decide if we should run faithfulness check."""
    if state.query_type == "adversarial":
        return "faithfulness_check"

    # Check for uncertainty phrases
    if state.response and any(
        phrase in state.response.content.lower()
        for phrase in ["i believe", "i think", "probably", "likely", "may", "might"]
    ):
        return "faithfulness_check"

    return END


def faithfulness_check_node(state: ChatState) -> ChatState:
    """Optional secondary grounding check for low-confidence answers."""
    log.info("faithfulness_check_started", session_id=state.session_id)

    if not state.response:
        return state

    # Build context from retrieved chunks
    context = "\n\n".join([chunk.text for chunk in state.retrieved_chunks])

    prompt = f"""Given this context and this response, does the response make any claims not supported by the context?
Answer YES or NO and list any unsupported claims.

Context:
{context}

Response:
{state.response.content}

Respond with JSON only: {{"has_unsupported_claims": true/false, "unsupported_claims": []}}"""

    try:
        provider = get_llm_provider()
        response_text = provider.invoke(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
        )

        result = json.loads(response_text)
        if result.get("has_unsupported_claims"):
            state.response.content += (
                "\n\n⚠️ Some claims in this response could not be fully verified against the source corpus."
            )

        log.info("faithfulness_check_completed", session_id=state.session_id)

    except Exception as e:
        log.error("faithfulness_check_failed", error=str(e), session_id=state.session_id)

    return state


def route_after_guardrail(state: ChatState) -> str:
    """Route after guardrail check."""
    if state.guardrail_triggered:
        return END
    return "query_router"


def build_chat_graph():
    """Build the chat StateGraph."""
    graph = StateGraph(ChatState)

    graph.add_node("guardrail", guardrail_node)
    graph.add_node("query_router", query_router_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("responder", responder_node)
    graph.add_node("faithfulness_check", faithfulness_check_node)

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"query_router": "query_router", END: END},
    )
    graph.add_edge("query_router", "retriever")
    graph.add_edge("retriever", "responder")
    graph.add_conditional_edges(
        "responder",
        should_check_faithfulness,
        {"faithfulness_check": "faithfulness_check", END: END},
    )
    graph.add_edge("faithfulness_check", END)

    return graph.compile()


chat_graph = build_chat_graph()
