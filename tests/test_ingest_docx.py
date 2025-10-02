from pathlib import Path

import pytest

from app.ingestion.parsers.documents import read_csv_text, read_docx_text


@pytest.fixture()
def sample_docx(tmp_path: Path) -> Path:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Hello world")
    document.add_paragraph("Second paragraph")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Role"
    table.cell(1, 0).text = "Ada"
    table.cell(1, 1).text = "Engineer"
    path = tmp_path / "sample.docx"
    document.save(path)
    return path


def test_read_docx_text_returns_segments(sample_docx: Path) -> None:
    segments = read_docx_text(sample_docx)
    assert len(segments) == 1
    text, metadata = segments[0]
    assert "Hello world" in text
    assert "Second paragraph" in text
    # Table rows should be joined with separators
    assert "Name | Role" in text
    assert "Ada | Engineer" in text
    assert metadata["mime_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert metadata["page_number"] == 1


def test_read_csv_text_creates_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,text\n1,First row\n,   \n3,Third", encoding="utf-8")

    segments = read_csv_text(csv_path)

    assert len(segments) == 3  # header + rows with content
    header_text, header_meta = segments[0]
    assert header_text == "id, text"
    assert header_meta == {"mime_type": "text/csv", "row_number": 1}

    first_text, first_meta = segments[1]
    assert first_text == "1, First row"
    assert first_meta == {"mime_type": "text/csv", "row_number": 2}

    last_text, last_meta = segments[2]
    assert last_text == "3, Third"
    assert last_meta == {"mime_type": "text/csv", "row_number": 4}
