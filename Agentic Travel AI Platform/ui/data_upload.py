"""
Data Upload Component
======================
File upload interface for CSV and document ingestion.
"""

import streamlit as st
import re
from pathlib import Path
from uuid import uuid4


ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
}


def _safe_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving the extension."""
    original = Path(filename or "upload")
    suffix = original.suffix.lower()
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", original.stem).strip("._")
    return f"{stem or 'upload'}_{uuid4().hex[:8]}{suffix}"


def _safe_session_folder(session_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", session_id or "session").strip("_") or "session"


def render_upload_section():
    """Render document upload section in the sidebar."""
    if not st.session_state.user_name:
        return

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📤 Upload Documents")
        st.caption("Upload PDFs, text files, or images for multimodal RAG Q&A")

        uploaded_file = st.file_uploader(
            "Choose a file",
            type=[ext.lstrip(".") for ext in sorted(ALLOWED_UPLOAD_EXTENSIONS)],
            key="doc_uploader",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            if st.button("Ingest Document", type="primary", use_container_width=True):
                _ingest_uploaded_file(uploaded_file)


def _ingest_uploaded_file(uploaded_file):
    """Save uploaded file and ingest into the RAG vector store."""
    try:
        from config import DATA_DIR, MAX_UPLOAD_MB

        original_name = uploaded_file.name or "upload"
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            st.error(f"Unsupported file type: {extension or '(none)'}")
            return

        if uploaded_file.type and uploaded_file.type not in ALLOWED_UPLOAD_MIME_TYPES:
            st.error(f"Unsupported MIME type: {uploaded_file.type}")
            return

        max_bytes = MAX_UPLOAD_MB * 1024 * 1024
        if uploaded_file.size and uploaded_file.size > max_bytes:
            st.error(f"File is too large. Maximum allowed size is {MAX_UPLOAD_MB} MB.")
            return

        session_id = st.session_state.session_id
        save_dir = DATA_DIR / "sample_guides" / _safe_session_folder(session_id)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / _safe_filename(original_name)

        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Ingest via RAG tool
        from tools.rag_tools import ingest_document

        with st.spinner(f"Ingesting '{uploaded_file.name}'..."):
            result = ingest_document.invoke({
                "file_path": str(save_path),
                "namespace": session_id,
            })

        st.success(result)

    except Exception as e:
        st.error(f"Error: {e}")
