"""
Multi-Agent AI Platform
========================
Main Streamlit entry point.
Combines the supervisor agent with a polished chat UI and token tracking.

Run: streamlit run app.py
"""

import sys
import io

# Fix Windows charmap codec errors for LangGraph/LangChain logging
if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if isinstance(sys.stderr, io.TextIOWrapper) and sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import streamlit as st

# ── Page Configuration (must be first Streamlit call) ─────────────
st.set_page_config(
    page_title="Multi-Agent AI Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for polished look ──────────────────────────────────
st.markdown(
    """
    <style>
    /* Main container */
    .stMainBlockContainer {
        max-width: 960px;
        padding-top: 1.5rem;
    }

    /* Chat messages */
    .stChatMessage {
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        width: 320px !important;
    }

    section[data-testid="stSidebar"] .stMetric {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 0.5rem;
    }

    /* Status/expander styling */
    .stExpander {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }

    /* Code blocks in thinking panels */
    .stExpander pre {
        background: #1e1e2e;
        border-radius: 6px;
        padding: 0.8rem;
        font-size: 0.85rem;
    }

    /* Hide Streamlit default branding but keep header for sidebar toggle */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Initialize Session State ─────────────────────────────────────
from ui.sidebar import init_session_state, render_sidebar
from ui.chat import render_chat
from ui.data_upload import render_upload_section

init_session_state()

# ── Render Components ─────────────────────────────────────────────
render_sidebar()
render_upload_section()
render_chat()
