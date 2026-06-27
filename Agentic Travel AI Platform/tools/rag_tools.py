"""
RAG Tools (FAISS + HuggingFace Embeddings)
==========================================
Document ingestion and retrieval tools for the RAG agent.
Supports PDF and text files with FAISS vector storage.
"""

import base64
import hashlib
import mimetypes
import re
import shutil
import threading
from contextvars import ContextVar
from pathlib import Path

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    EXTRACTED_ASSETS_DIR,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    RAG_ENABLE_OCR,
    RAG_ENABLE_TABLE_EXTRACTION,
    RAG_ENABLE_VISION_CAPTIONS,
    RAG_MAX_IMAGES_PER_PAGE,
    VECTORSTORE_PATH,
    get_embeddings,
)
from guardrails import detect_prompt_injection, format_untrusted_content

# ── Module-level FAISS store ──────────────────────────────────────
_rag_namespace: ContextVar[str] = ContextVar("rag_namespace", default="default")
_vectorstores: dict[str, object] = {}
_vectorstore_lock = threading.Lock()


def _sanitize_namespace(namespace: str | None) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(namespace or "default")).strip("_")
    return clean or "default"


def set_rag_namespace(namespace: str | None) -> None:
    """Set the active RAG namespace for the current agent execution context."""
    _rag_namespace.set(_sanitize_namespace(namespace))


def _current_namespace(namespace: str | None = None) -> str:
    return _sanitize_namespace(namespace or _rag_namespace.get())


def _vectorstore_path(namespace: str | None = None) -> Path:
    namespace_key = _current_namespace(namespace)
    base_path = Path(VECTORSTORE_PATH)
    if namespace_key == "default":
        return base_path
    return base_path.parent / namespace_key / base_path.name


def get_rag_index_path(namespace: str | None = None) -> Path:
    """Return the FAISS index path for a namespace."""
    return _vectorstore_path(namespace)


def clear_rag_namespace(namespace: str | None) -> None:
    """Delete cached and persisted RAG data for a namespace."""
    namespace_key = _current_namespace(namespace)
    with _vectorstore_lock:
        _vectorstores.pop(namespace_key, None)

        for path in [
            _vectorstore_path(namespace_key),
            EXTRACTED_ASSETS_DIR / namespace_key,
        ]:
            if path.exists():
                shutil.rmtree(path)


def _get_vectorstore(namespace: str | None = None):
    """Lazy-load or initialize the FAISS vector store."""
    namespace_key = _current_namespace(namespace)
    if namespace_key in _vectorstores:
        return _vectorstores[namespace_key]

    index_path = _vectorstore_path(namespace_key)
    if index_path.exists() and (index_path / "index.faiss").exists():
        from langchain_community.vectorstores import FAISS
        _vectorstores[namespace_key] = FAISS.load_local(
            str(index_path),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
    return _vectorstores.get(namespace_key)


def _save_vectorstore(namespace: str | None = None):
    """Persist the FAISS index to disk."""
    namespace_key = _current_namespace(namespace)
    vectorstore = _vectorstores.get(namespace_key)
    if vectorstore is not None:
        index_path = _vectorstore_path(namespace_key)
        index_path.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(index_path))


def _document_id(path: Path) -> str:
    """Create a stable id for a source file without storing its full content."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _asset_dir(document_id: str, namespace: str | None = None) -> Path:
    path = EXTRACTED_ASSETS_DIR / _current_namespace(namespace) / document_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _add_section(
    texts: list[str],
    metadatas: list[dict],
    content: str,
    *,
    source: str,
    file_path: str,
    document_id: str,
    modality: str,
    page: int | None = None,
    asset_path: str | None = None,
) -> None:
    """Add one searchable multimodal section with consistent metadata."""
    clean_content = (content or "").strip()
    if not clean_content:
        return

    injection_detected = detect_prompt_injection(clean_content)
    header = f"[{modality.upper()}]"
    if page:
        header += f" Page {page}"
    if injection_detected:
        header += " [PROMPT_INJECTION_LIKE_TEXT_DETECTED]"
    texts.append(f"{header}\n{clean_content}")
    metadatas.append({
        "source": source,
        "file_path": file_path,
        "page": page,
        "document_id": document_id,
        "modality": modality,
        "asset_path": asset_path,
        "prompt_injection_detected": injection_detected,
    })


def _table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table into simple Markdown for retrieval."""
    rows = [[str(cell or "").strip() for cell in row] for row in table if row]
    rows = [row for row in rows if any(row)]
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    separator = ["---"] * width
    body = rows[1:]

    def render_row(row: list[str]) -> str:
        return "| " + " | ".join(row) + " |"

    rendered = [render_row(header), render_row(separator)]
    rendered.extend(render_row(row) for row in body)
    return "\n".join(rendered)


def _caption_image_with_openai(
    image_path: Path,
    source: str,
    page: int | None = None,
) -> str:
    """Caption an extracted image/chart using OpenAI vision when configured."""
    api_key = (OPENAI_API_KEY or "").strip()
    model = (OPENAI_MODEL or "").strip()
    if not (RAG_ENABLE_VISION_CAPTIONS and api_key and model):
        return ""

    try:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI

        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime_type};base64,{data}"

        page_label = f", page {page}" if page else ""
        prompt = (
            "Describe this image for retrieval in a document Q&A system. "
            "If it is a chart, table, diagram, map, screenshot, or figure, capture "
            "the title, labels, visible values, trends, and the main insight. "
            f"Source document: {source}{page_label}."
        )
        llm = ChatOpenAI(model=model, temperature=0, api_key=api_key)
        response = llm.invoke([
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ])
        ])
        return str(response.content).strip()
    except Exception as e:
        return f"Vision caption unavailable for extracted image: {e}"


def _ocr_page(page, page_index: int, assets_dir: Path) -> tuple[str, str | None]:
    """Render a PDF page and run OCR if pytesseract and Pillow are available."""
    if not RAG_ENABLE_OCR:
        return "", None

    try:
        from PIL import Image
        import pytesseract
        import fitz

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image_path = assets_dir / f"page_{page_index:04d}_ocr.png"
        pix.save(str(image_path))
        text = pytesseract.image_to_string(Image.open(image_path)).strip()
        return text, str(image_path)
    except Exception as e:
        return f"OCR unavailable for page {page_index}: {e}", None


def _ocr_image(image_path: Path) -> str:
    """Run OCR on an image file if pytesseract and Pillow are available."""
    if not RAG_ENABLE_OCR:
        return ""

    try:
        from PIL import Image
        import pytesseract

        return pytesseract.image_to_string(Image.open(image_path)).strip()
    except Exception as e:
        return f"OCR unavailable for image: {e}"


def _extract_tables(path: Path, document_id: str) -> tuple[list[str], list[dict], str]:
    """Extract PDF tables with pdfplumber when available."""
    if not RAG_ENABLE_TABLE_EXTRACTION or path.suffix.lower() != ".pdf":
        return [], [], ""

    try:
        import pdfplumber
    except ImportError:
        return [], [], "Table extraction skipped: pdfplumber is not installed."

    texts: list[str] = []
    metadatas: list[dict] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_index, page in enumerate(pdf.pages, 1):
                for table_index, table in enumerate(page.extract_tables() or [], 1):
                    markdown = _table_to_markdown(table)
                    _add_section(
                        texts,
                        metadatas,
                        f"Table {table_index}\n{markdown}",
                        source=path.name,
                        file_path=str(path),
                        document_id=document_id,
                        modality="table",
                        page=page_index,
                    )
    except Exception as e:
        return texts, metadatas, f"Table extraction warning: {e}"

    return texts, metadatas, ""


def _extract_page_images(
    doc,
    page,
    page_index: int,
    path: Path,
    document_id: str,
    assets_dir: Path,
) -> tuple[list[str], list[dict], list[str]]:
    """Extract embedded page images and optionally caption them with a vision model."""
    texts: list[str] = []
    metadatas: list[dict] = []
    warnings: list[str] = []

    images = page.get_images(full=True)[:max(0, RAG_MAX_IMAGES_PER_PAGE)]
    for image_index, image_info in enumerate(images, 1):
        try:
            xref = image_info[0]
            image_data = doc.extract_image(xref)
            image_bytes = image_data.get("image")
            image_ext = image_data.get("ext", "png")
            if not image_bytes:
                continue

            image_path = assets_dir / f"page_{page_index:04d}_image_{image_index}.{image_ext}"
            image_path.write_bytes(image_bytes)

            caption = _caption_image_with_openai(
                image_path,
                path.name,
                page_index,
            )
            if not caption:
                caption = (
                    f"Extracted image {image_index} from {path.name}, page {page_index}. "
                    "No vision caption was generated because OpenAI vision captioning is not configured."
                )

            _add_section(
                texts,
                metadatas,
                f"Image {image_index}\n{caption}",
                source=path.name,
                file_path=str(path),
                document_id=document_id,
                modality="image",
                page=page_index,
                asset_path=str(image_path),
            )
        except Exception as e:
            warnings.append(f"Image extraction warning on page {page_index}: {e}")

    return texts, metadatas, warnings


# ── Input Schemas ─────────────────────────────────────────────────

class SearchInput(BaseModel):
    query: str = Field(description="The question or topic to search for in the documents")
    k: str = Field(description="Number of results to return (default '4')", default="4")
    namespace: str = Field(description="Optional RAG namespace. Leave empty to use the active session.", default="")
    dummy: str = Field(description="Leave this empty string always.", default="")


class IngestInput(BaseModel):
    file_path: str = Field(description="Absolute path to the PDF or text file to ingest")
    namespace: str = Field(description="Optional RAG namespace. Leave empty to use the active session.", default="")
    dummy: str = Field(description="Leave this empty string always.", default="")


# ── Tools ─────────────────────────────────────────────────────────

@tool
def get_rag_status() -> str:
    """Check the status of the RAG document store.
    Returns the number of indexed documents and chunks."""
    vs = _get_vectorstore()
    if vs is None:
        return "RAG Store: Empty (no documents indexed yet). Upload documents via the sidebar to get started."

    num_docs = vs.index.ntotal
    return f"RAG Store: {num_docs} chunks indexed and ready for search."


@tool(args_schema=IngestInput)
def ingest_document(
    file_path: str,
    namespace: str = "",
    dummy: str = "",
) -> str:
    """Ingest a document (PDF or text file) into the RAG vector store.
    The document will be chunked, embedded, and indexed for later retrieval."""
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found at '{file_path}'"

    try:
        namespace_key = _current_namespace(namespace)
        document_id = _document_id(path)
        assets_dir = _asset_dir(document_id, namespace_key)
        texts = []
        metadatas = []
        warnings = []
        # ── Load document based on type ───────────────────────────
        if path.suffix.lower() == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(str(path))
                for page_index, page in enumerate(doc, 1):
                    page_text = page.get_text().strip()
                    if page_text:
                        _add_section(
                            texts,
                            metadatas,
                            page_text,
                            source=path.name,
                            file_path=str(path),
                            document_id=document_id,
                            modality="text",
                            page=page_index,
                        )

                    if len(page_text) < 100:
                        ocr_text, ocr_asset_path = _ocr_page(page, page_index, assets_dir)
                        if ocr_text and not ocr_text.lower().startswith("ocr unavailable"):
                            _add_section(
                                texts,
                                metadatas,
                                ocr_text,
                                source=path.name,
                                file_path=str(path),
                                document_id=document_id,
                                modality="ocr",
                                page=page_index,
                                asset_path=ocr_asset_path,
                            )
                        elif ocr_text:
                            warnings.append(ocr_text)

                    image_texts, image_metadatas, image_warnings = _extract_page_images(
                        doc,
                        page,
                        page_index,
                        path,
                        document_id,
                        assets_dir,
                    )
                    texts.extend(image_texts)
                    metadatas.extend(image_metadatas)
                    warnings.extend(image_warnings)
                doc.close()
            except ImportError:
                return "Error: PyMuPDF (fitz) is not installed. Run: pip install pymupdf"
        elif path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            image_path = assets_dir / path.name
            if path.resolve() != image_path.resolve():
                image_path.write_bytes(path.read_bytes())

            ocr_text = _ocr_image(image_path)
            if ocr_text and not ocr_text.lower().startswith("ocr unavailable"):
                _add_section(
                    texts,
                    metadatas,
                    ocr_text,
                    source=path.name,
                    file_path=str(path),
                    document_id=document_id,
                    modality="ocr",
                    asset_path=str(image_path),
                )
            elif ocr_text:
                warnings.append(ocr_text)

            caption = _caption_image_with_openai(
                image_path,
                path.name,
            )
            if caption:
                _add_section(
                    texts,
                    metadatas,
                    caption,
                    source=path.name,
                    file_path=str(path),
                    document_id=document_id,
                    modality="image",
                    asset_path=str(image_path),
                )
            elif not ocr_text or ocr_text.lower().startswith("ocr unavailable"):
                _add_section(
                    texts,
                    metadatas,
                    "Uploaded image. No OCR text or vision caption was generated.",
                    source=path.name,
                    file_path=str(path),
                    document_id=document_id,
                    modality="image",
                    asset_path=str(image_path),
                )
        elif path.suffix.lower() in (".txt", ".md", ".csv"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            if text:
                _add_section(
                    texts,
                    metadatas,
                    text,
                    source=path.name,
                    file_path=str(path),
                    document_id=document_id,
                    modality="text",
                )
        else:
            return f"Unsupported file type: '{path.suffix}'. Supported: .pdf, .txt, .md, .png, .jpg, .jpeg"

        table_texts, table_metadatas, table_warning = _extract_tables(path, document_id)
        texts.extend(table_texts)
        metadatas.extend(table_metadatas)
        if table_warning:
            warnings.append(table_warning)

        if not texts:
            return (
                f"Error: No text, OCR, table, or image content extracted from '{path.name}'. "
                "If this is a scanned PDF, install Tesseract OCR or configure OpenAI vision captioning."
            )

        # ── Chunk the text ────────────────────────────────────────
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        chunks = splitter.create_documents(
            texts=texts,
            metadatas=metadatas,
        )

        # ── Embed and store ───────────────────────────────────────
        from langchain_community.vectorstores import FAISS

        embeddings = get_embeddings()

        with _vectorstore_lock:
            vectorstore = _get_vectorstore(namespace_key)
            if vectorstore is None:
                _vectorstores[namespace_key] = FAISS.from_documents(chunks, embeddings)
            else:
                vectorstore.add_documents(chunks)

            _save_vectorstore(namespace_key)
            vectorstore = _vectorstores[namespace_key]

        return (
            f"Successfully ingested '{path.name}': "
            f"{len(texts)} text sections processed, "
            f"{len(chunks)} chunks created and indexed. "
            f"Total chunks in store: {vectorstore.index.ntotal}"
            + (f"\nWarnings: {' | '.join(warnings[:3])}" if warnings else "")
        )

    except Exception as e:
        return f"Error ingesting document: {e}"


@tool(args_schema=SearchInput)
def search_documents(query: str, k: str = "4", namespace: str = "", dummy: str = "") -> str:
    """Search the document store for information relevant to a query.
    Returns the most relevant document chunks with source citations.
    Use this when the user asks questions about uploaded documents."""
    try:
        k_int = int(str(k).strip())
        k_int = max(1, min(10, k_int))
    except (ValueError, TypeError):
        k_int = 4

    vs = _get_vectorstore(namespace)
    if vs is None:
        return "No documents have been indexed yet. Please upload documents first."

    try:
        results = vs.similarity_search_with_score(query, k=k_int)

        if not results:
            return f"No relevant results found for: '{query}'"

        output_lines = [f"Search results for: '{query}'", f"Found {len(results)} relevant chunks:", ""]

        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page")
            modality = doc.metadata.get("modality", "text")
            asset_path = doc.metadata.get("asset_path")
            injection_detected = bool(doc.metadata.get("prompt_injection_detected"))
            source_label = f"{source}, page {page}" if page else source
            content_preview = doc.page_content[:800]
            wrapped_content = format_untrusted_content(
                content_preview,
                source_label=source_label,
                content_type=f"{modality} chunk",
            )

            output_lines.append(f"--- Result {i} (Distance: {score:.4f}; lower is more similar) ---")
            output_lines.append(f"Source: {source_label}")
            output_lines.append(f"Modality: {modality}")
            if injection_detected:
                output_lines.append("Security: prompt-injection-like text detected in this chunk")
            if asset_path:
                output_lines.append(f"Asset: {asset_path}")
            output_lines.append(wrapped_content)
            output_lines.append("")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error searching documents: {e}"
