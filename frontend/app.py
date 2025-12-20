"""
Streamlit Frontend for RAG Documentation Assistant - Modern UI

A professional web interface featuring:
- Tabbed navigation (Chat, Analytics, Management)
- Interactive analytics dashboard with charts
- Real-time streaming LLM responses
- Domain management (upload/delete)
- Performance monitoring

Usage:
    streamlit run frontend/app.py
"""

import streamlit as st
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="FlexiRAG - Dynamic Multi-Domain RAG Framework",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Enhanced Custom CSS
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Status indicators */
    .health-ok {
        color: #0f9d58;
        font-weight: bold;
    }

    .health-warn {
        color: #f4b400;
        font-weight: bold;
    }

    .health-error {
        color: #db4437;
        font-weight: bold;
    }

    /* Streaming text */
    .streaming-text {
        font-size: 1.1rem;
        line-height: 1.6;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        color: #1e1e1e;
    }

    /* Chat history */
    .chat-message {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        color: #1e1e1e;
    }

    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        color: #0d47a1;
    }

    .assistant-message {
        background-color: #f1f8e9;
        border-left: 4px solid #8bc34a;
        color: #33691e;
    }

    /* Source boxes */
    .source-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 3px solid #764ba2;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 10px 20px;
        background-color: #f0f2f6;
        border-radius: 8px 8px 0 0;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #888;
        font-size: 0.9rem;
        margin-top: 3rem;
        padding: 1rem;
        border-top: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# API FUNCTIONS
# ============================================================================

def get_health_status() -> Dict[str, Any]:
    """Get system health status from API."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": "API unreachable"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_domains() -> List[Dict[str, Any]]:
    """Get available domains from API."""
    try:
        response = requests.get(f"{API_BASE_URL}/domains", timeout=5)
        if response.status_code == 200:
            return response.json()["domains"]
        return []
    except:
        return []


def query_documents_streaming(question: str, domain: str = None, n_results: int = 3):
    """Query documents with streaming response."""
    payload = {
        "question": question,
        "domain": domain if domain != "All" else None,
        "n_results": n_results,
        "stream": True,
        "use_reranking": True,
        "use_cache": True
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json=payload,
            stream=True,
            timeout=60
        )

        if response.status_code == 200:
            return response
        else:
            return None

    except Exception as e:
        st.error(f"Error querying API: {e}")
        return None


def query_documents_non_streaming(question: str, domain: str = None, n_results: int = 3):
    """Query documents without streaming (fallback)."""
    payload = {
        "question": question,
        "domain": domain if domain != "All" else None,
        "n_results": n_results,
        "stream": False,
        "use_reranking": True,
        "use_cache": True
    }

    try:
        response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error querying API: {e}")
        return None


def display_sources(sources: List[Dict[str, Any]]):
    """Display source documents with metadata."""
    st.subheader("📄 Sources")

    for i, source in enumerate(sources, 1):
        with st.expander(f"Source {i}: {source.get('source', 'Unknown')}"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**Type:** {source.get('source_type', 'N/A').upper()}")
                if source.get('source_type') == 'pdf':
                    st.markdown(f"**Page:** {source.get('page', 'N/A')}")
                else:
                    st.markdown(f"**Row ID:** {source.get('row_id', 'N/A')}")

            with col2:
                if source.get('source_type') == 'csv':
                    st.markdown(f"**Category:** {source.get('category', 'N/A')}")

            st.markdown("**Preview:**")
            st.text(source.get('chunk_preview', 'No preview available'))


# ============================================================================
# TAB 1: CHAT INTERFACE
# ============================================================================

def render_chat_tab(health: Dict, domains_data: List[Dict]):
    """Render the main chat interface."""

    # Initialize chat history in session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Domain selection in chat
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("### 💬 Ask a Question")

    with col2:
        if domains_data:
            domain_options = ["All"] + [d["name"] for d in domains_data]
            selected_domain = st.selectbox(
                "Domain",
                domain_options,
                key="chat_domain"
            )
        else:
            selected_domain = "All"

    with col3:
        n_results = st.slider("Results", 1, 10, 3, key="chat_results")

    # Chat History Display
    if st.session_state.chat_history:
        with st.expander(f"📜 Chat History ({len(st.session_state.chat_history)} messages)", expanded=False):
            for i, chat in enumerate(reversed(st.session_state.chat_history)):
                st.markdown(f'<div class="chat-message user-message"><strong>You ({chat["timestamp"]}):</strong> {chat["question"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="chat-message assistant-message"><strong>FlexiRAG:</strong> {chat["answer"][:200]}{"..." if len(chat["answer"]) > 200 else ""}</div>', unsafe_allow_html=True)
                if i < len(st.session_state.chat_history) - 1:
                    st.divider()

    # Example questions
    with st.expander("💡 Example Questions"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Automotive:**")
            if st.button("What is CAN protocol?", use_container_width=True):
                st.session_state.question = "What is CAN protocol?"
            if st.button("How does OBD-II work?", use_container_width=True):
                st.session_state.question = "How does OBD-II work?"

        with col2:
            st.markdown("**Fashion:**")
            if st.button("Show dresses under $50", use_container_width=True):
                st.session_state.question = "Show me dresses under $50"
            if st.button("Athletic wear brands?", use_container_width=True):
                st.session_state.question = "What brands sell athletic wear?"

        with col3:
            st.markdown("**Medical:**")
            if st.button("What is Aspirin for?", use_container_width=True):
                st.session_state.question = "What is Aspirin used for?"
            if st.button("Ibuprofen dosage?", use_container_width=True):
                st.session_state.question = "What is the dosage of Ibuprofen?"

    # Question Input
    question = st.text_input(
        "Enter your question:",
        value=st.session_state.get('question', ''),
        placeholder="e.g., What is CAN protocol?",
        help="Ask any question about the indexed documents",
        key="question_input"
    )

    # Clear the session state after using it
    if 'question' in st.session_state and st.session_state.question == question:
        del st.session_state.question

    # Query Button & Clear History
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    with col2:
        use_streaming = st.checkbox("Stream", value=True)
    with col3:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    if search_button:
        if not question.strip():
            st.warning("Please enter a question!")
            return

        # Show loading state
        with st.spinner("Searching documents..."):
            if use_streaming:
                # Streaming mode
                response = query_documents_streaming(
                    question,
                    domain=selected_domain if selected_domain != "All" else None,
                    n_results=n_results
                )

                if response:
                    st.subheader("💡 Answer")

                    # Create placeholder for streaming text
                    answer_placeholder = st.empty()
                    answer_text = ""

                    sources = None

                    # Process streaming response
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            try:
                                data = json.loads(line)

                                if data.get("type") == "metadata":
                                    st.info(f"Retrieved {data['chunks_retrieved']} chunks in {data['search_time']:.2f}s")

                                elif data.get("type") == "token":
                                    token = data.get("token", "")
                                    answer_text += token
                                    answer_placeholder.markdown(f'<div class="streaming-text">{answer_text}</div>', unsafe_allow_html=True)

                                elif data.get("type") == "done":
                                    sources = data.get("sources", [])
                                    total_time = data.get("total_time", 0)
                                    st.success(f"✅ Answer generated in {total_time:.2f}s")

                            except json.JSONDecodeError:
                                continue

                    # Save to chat history
                    if answer_text:
                        st.session_state.chat_history.append({
                            "question": question,
                            "answer": answer_text,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "domain": selected_domain
                        })

                    # Display sources
                    if sources:
                        st.divider()
                        display_sources(sources)

            else:
                # Non-streaming mode
                result = query_documents_non_streaming(
                    question,
                    domain=selected_domain if selected_domain != "All" else None,
                    n_results=n_results
                )

                if result:
                    st.subheader("💡 Answer")
                    st.markdown(f'<div class="streaming-text">{result["answer"]}</div>', unsafe_allow_html=True)

                    # Save to chat history
                    st.session_state.chat_history.append({
                        "question": question,
                        "answer": result["answer"],
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "domain": selected_domain
                    })

                    if "sources" in result:
                        st.divider()
                        display_sources(result["sources"])


# ============================================================================
# TAB 2: ANALYTICS DASHBOARD
# ============================================================================

def render_analytics_tab(health: Dict, domains_data: List[Dict]):
    """Render analytics dashboard with charts."""

    st.markdown("### 📊 Analytics Dashboard")

    # Top metrics in cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_docs = health.get('documents_indexed', 0)
        st.metric("📚 Total Documents", f"{total_docs:,}")

    with col2:
        domain_count = len(domains_data)
        st.metric("🗂️ Active Domains", domain_count)

    with col3:
        cache_size = health.get('cache_size', 0)
        st.metric("💾 Cache Size", cache_size)

    with col4:
        status = health.get('status', 'unknown')
        status_emoji = "✅" if status == "healthy" else "⚠️"
        st.metric("🏥 System Status", f"{status_emoji} {status.title()}")

    st.divider()

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        # Domain Distribution Pie Chart
        st.markdown("#### 📈 Domain Distribution")

        if domains_data:
            domain_names = [d['name'] for d in domains_data]
            domain_counts = [d['document_count'] for d in domains_data]

            fig = px.pie(
                values=domain_counts,
                names=domain_names,
                title="Documents by Domain",
                color_discrete_sequence=px.colors.sequential.Purples_r
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(
                showlegend=True,
                height=400,
                font=dict(size=12)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No domains available yet. Upload documents to see analytics.")

    with col2:
        # Domain Document Counts Bar Chart
        st.markdown("#### 📊 Document Counts by Domain")

        if domains_data:
            domain_names = [d['name'] for d in domains_data]
            domain_counts = [d['document_count'] for d in domains_data]
            
            fig = go.Figure(data=[
                go.Bar(
                    x=domain_names,
                    y=domain_counts,
                    marker=dict(
                        color=domain_counts,
                        colorscale='Purples',
                        showscale=False
                    ),
                    text=domain_counts,
                    textposition='outside'
                )
            ])

            fig.update_layout(
                title="Documents per Domain",
                xaxis_title="Domain",
                yaxis_title="Document Count",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No domains available yet.")

    # Performance Stats
    if "performance_stats" in health:
        stats = health["performance_stats"]

        if stats.get("queries_count", 0) > 0:
            st.divider()
            st.markdown("#### ⚡ Performance Metrics")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Queries",
                    f"{stats.get('queries_count', 0):,}"
                )

            with col2:
                st.metric(
                    "Avg Total Time",
                    f"{stats.get('avg_total_time', 0):.2f}s"
                )

            with col3:
                st.metric(
                    "Avg Search Time",
                    f"{stats.get('avg_search_time', 0):.2f}s"
                )

            with col4:
                st.metric(
                    "Avg Generation Time",
                    f"{stats.get('avg_generation_time', 0):.2f}s"
                )
        else:
            st.info("No queries executed yet. Try asking some questions to see performance metrics!")

    # System Information
    st.divider()
    st.markdown("#### 🖥️ System Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Database Status**")
        db_status = "✅ Ready" if health.get('database_ready') else "❌ Not Ready"
        st.write(db_status)

    with col2:
        st.markdown("**Ollama LLM**")
        ollama_status = "✅ Running" if health.get('ollama_running') else "❌ Not Running"
        st.write(ollama_status)

    with col3:
        st.markdown("**API Status**")
        api_status = health.get('status', 'unknown').title()
        st.write(f"{'✅' if api_status == 'Healthy' else '⚠️'} {api_status}")


# ============================================================================
# TAB 3: MANAGEMENT (Upload & Delete)
# ============================================================================

def render_management_tab(domains_data: List[Dict]):
    """Render document management interface."""

    st.markdown("### 🗂️ Document Management")

    col1, col2 = st.columns(2)

    # Upload Section
    with col1:
        st.markdown("#### 📤 Upload Documents")

        with st.container():
            upload_domain = st.text_input(
                "Domain Name",
                placeholder="e.g., medical, legal, tech",
                help="Enter existing domain or create new one",
                key="upload_domain"
            )

            uploaded_file = st.file_uploader(
                "Choose a file",
                type=['pdf', 'csv'],
                help="Upload PDF or CSV files",
                key="file_uploader"
            )

            if st.button("Upload & Index", type="primary", disabled=not (uploaded_file and upload_domain), use_container_width=True):
                with st.spinner("Uploading and indexing..."):
                    try:
                        # Prepare multipart form data
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {"domain": upload_domain}

                        # Upload to API
                        response = requests.post(
                            f"{API_BASE_URL}/upload",
                            files=files,
                            data=data,
                            timeout=300
                        )

                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ {result['message']}")
                            st.info(f"📊 Total documents: {result['total_documents']:,}")
                            st.balloons()
                            st.rerun()
                        else:
                            error_detail = response.json().get('detail', 'Unknown error')
                            st.error(f"❌ Upload failed: {error_detail}")

                    except requests.exceptions.Timeout:
                        st.error("⏱️ Upload timeout (>5 minutes). File might be too large.")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

    # Delete Section
    with col2:
        st.markdown("#### 🗑️ Delete Domain")

        with st.container():
            if domains_data:
                domain_to_delete = st.selectbox(
                    "Select domain to delete",
                    [d["name"] for d in domains_data],
                    help="This will delete all documents in the domain",
                    key="delete_domain_select"
                )

                st.warning("⚠️ This action cannot be undone!")

                if st.button("Delete Domain", type="secondary", use_container_width=True):
                    if st.session_state.get('confirm_delete') != domain_to_delete:
                        st.session_state.confirm_delete = domain_to_delete
                        st.warning(f"⚠️ Click again to confirm deletion of '{domain_to_delete}'")
                    else:
                        with st.spinner(f"Deleting domain '{domain_to_delete}'..."):
                            try:
                                response = requests.delete(
                                    f"{API_BASE_URL}/domain/{domain_to_delete}",
                                    timeout=30
                                )

                                if response.status_code == 200:
                                    result = response.json()
                                    st.success(f"✅ {result['message']}")
                                    st.info(f"📊 Deleted {result['documents_deleted']:,} documents")
                                    st.info(f"📊 Remaining: {result['total_documents_remaining']:,} documents")
                                    st.session_state.confirm_delete = None
                                    st.rerun()
                                else:
                                    error_detail = response.json().get('detail', 'Unknown error')
                                    st.error(f"❌ Delete failed: {error_detail}")
                                    st.session_state.confirm_delete = None
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                st.session_state.confirm_delete = None
            else:
                st.info("No domains available to delete")

    # Domain List
    st.divider()
    st.markdown("#### 📋 Current Domains")

    if domains_data:
        for domain in domains_data:
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{domain['name'].title()}**")
            with col2:
                st.write(f"{domain['document_count']:,} documents")
            with col3:
                st.write(f"📊")
    else:
        st.info("No domains available. Upload documents to get started!")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""

    # Header
    st.markdown('<h1 class="main-header">🚀 FlexiRAG</h1>', unsafe_allow_html=True)
    st.markdown("**Dynamic Multi-Domain RAG Framework** | Zero-code document intelligence for any domain")

    # Get system data
    health = get_health_status()
    domains_data = get_domains()

    # System status indicator
    status = health.get('status', 'unknown')
    if status == "healthy":
        st.success("✅ System Healthy | All services running")
    elif status == "degraded":
        st.warning("⚠️ System Degraded | Some services may be unavailable")
    else:
        st.error("❌ System Error | Please check services")

    st.divider()

    # Tabs Navigation
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Analytics", "🗂️ Management"])

    with tab1:
        render_chat_tab(health, domains_data)

    with tab2:
        render_analytics_tab(health, domains_data)

    with tab3:
        render_management_tab(domains_data)

    # Footer
    st.markdown("""
    <div class="footer">
        FlexiRAG - Dynamic Multi-Domain RAG Framework | Powered by FastAPI, Streamlit & Ollama<br>
        Built with ❤️ using Python, ChromaDB, and Llama 3.2 | 100% Free & Local
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
