"""Streamlit UI application."""

import streamlit as st
from datetime import datetime
from uuid import uuid4

from reportagent.schemas import ChatState, MessageRole
from reportagent.graphs.chat import chat_graph
from reportagent.storage.archive import Archive
from reportagent.observability.logging import setup_logging
from reportagent.observability.tracing import setup_tracing

# Setup
setup_logging()
setup_tracing()

from reportagent.config import get_settings

settings = get_settings()
topic_name = settings.default_topic.replace("_", " ").title()

st.set_page_config(
    page_title=f"{topic_name} Intelligence Agent",
    page_icon="📰",
    layout="wide",
)

# Header
st.title(f"📰 {topic_name} Intelligence Agent")
st.markdown("Powered by LangGraph + Llama 3 (AWS Bedrock)")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.header("📊 System Status")

    # Get archive stats
    try:
        from reportagent.config import get_settings

        archive = Archive()
        settings = get_settings()
        latest_report = archive.get_latest_report(settings.default_topic)
        latest_run = archive.get_latest_run_log()

        if latest_report:
            st.subheader("📄 Latest Report")
            st.markdown(f"**Topic:** {latest_report.topic}")
            st.markdown(f"**Generated:** {latest_report.generated_at.strftime('%Y-%m-%d %H:%M')}")
            st.markdown(f"**Summary:**\n{latest_report.summary}")

            with st.expander("📌 Key Takeaways"):
                for takeaway in latest_report.key_takeaways:
                    st.markdown(f"• {takeaway}")

            with st.expander("🏢 Organisations Mentioned"):
                for org in latest_report.organisations_mentioned:
                    st.markdown(f"• {org}")

        if latest_run:
            st.markdown("---")
            st.markdown(f"**Last Run Status:** {'✅ Success' if latest_run.status.value == 'success' else '❌ Failed'}")
            st.markdown(f"**Articles Fetched:** {latest_run.articles_fetched}")
            st.markdown(f"**Chunks Added:** {latest_run.chunks_added}")

    except Exception as e:
        st.error(f"Error loading system status: {str(e)}")

    # Trigger button
    if st.button("🚀 Trigger Ingestion Now", key="trigger_ingestion"):
        with st.spinner("Running ingestion (this may take 1-2 minutes)..."):
            try:
                from reportagent.schemas import IngestionState
                from reportagent.graphs.ingestion import ingestion_graph
                from reportagent.config import get_settings
                import sys
                import io

                settings = get_settings()
                state = IngestionState(
                    run_id=str(uuid4()),
                    topic=settings.default_topic,
                )

                # Capture logs
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    result = ingestion_graph.invoke(state.model_dump())
                    sys.stdout = old_stdout

                    st.success("✅ Ingestion completed successfully!")
                    st.toast("New report generated!", icon="📄")
                    # Clear cache to force reload of latest report
                    st.cache_data.clear()
                    # Rerun to refresh sidebar with new report
                    st.rerun()

                except Exception as e:
                    sys.stdout = old_stdout
                    raise e

            except Exception as e:
                st.error(f"❌ Ingestion failed: {str(e)}")
                import traceback
                st.write(traceback.format_exc())

# Main chat area
st.header("💬 Ask a Question")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message.role.value):
        st.write(message.content)
        if message.citations:
            with st.expander("📚 Sources"):
                for citation in message.citations:
                    st.markdown(f"[[{citation.index}] {citation.url}]({citation.url})")

# Chat input
user_input = st.chat_input(f"Ask a question about {topic_name.lower()}...")

if user_input:
    # Add user message to history
    from reportagent.schemas import ChatMessage
    user_message = ChatMessage(
        role=MessageRole.USER,
        content=user_input,
    )
    st.session_state.messages.append(user_message)

    # Display user message
    with st.chat_message("user"):
        st.write(user_input)

    # Generate response
    with st.spinner("Thinking..."):
        try:
            chat_state = ChatState(
                session_id=st.session_state.session_id,
                topic=settings.default_topic,
                current_query=user_input,
            )

            result = chat_graph.invoke(chat_state.model_dump())

            if result.get("response"):
                response_msg = ChatMessage.model_validate(result["response"])
                st.session_state.messages.append(response_msg)

                # Display assistant response
                with st.chat_message("assistant"):
                    st.write(response_msg.content)

                    if response_msg.citations:
                        with st.expander("📚 Sources"):
                            for citation in response_msg.citations:
                                st.markdown(f"[[{citation.index}] {citation.url}]({citation.url})")

        except Exception as e:
            st.error(f"Error generating response: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: gray; font-size: 0.8em;">
    Generated by Data Reply GenAI Agent • Session: {}</div>
    """.format(st.session_state.session_id[:8]),
    unsafe_allow_html=True,
)
