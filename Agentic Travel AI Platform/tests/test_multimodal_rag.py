from pathlib import Path

from tools.rag_tools import _add_section, _table_to_markdown


def test_table_to_markdown_renders_rows():
    table = [["Metric", "Value"], ["Visitors", "1200"], ["Growth", "14%"]]

    markdown = _table_to_markdown(table)

    assert "| Metric | Value |" in markdown
    assert "| Visitors | 1200 |" in markdown


def test_add_section_preserves_modality_metadata(tmp_path: Path):
    texts = []
    metadatas = []

    _add_section(
        texts,
        metadatas,
        "A chart shows visitor growth.",
        source="report.pdf",
        file_path=str(tmp_path / "report.pdf"),
        document_id="doc123",
        modality="image",
        page=4,
        asset_path=str(tmp_path / "chart.png"),
    )

    assert texts[0].startswith("[IMAGE] Page 4")
    assert metadatas[0]["modality"] == "image"
    assert metadatas[0]["page"] == 4
