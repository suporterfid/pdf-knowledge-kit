import pytest
from pypdf import PdfWriter

pytest.importorskip("pytesseract")
pytest.importorskip("pdf2image")

import app.ingestion.service as ingest


@pytest.fixture(params=["eng", "por", "spa"])
def pdf_and_lang(tmp_path, request):
    path = tmp_path / f"sample_{request.param}.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as f:
        writer.write(f)
    return path, request.param


def test_read_pdf_text_with_ocr(monkeypatch, pdf_and_lang):
    pdf_path, lang = pdf_and_lang

    def fake_convert_from_path(_):
        return [object()]

    def fake_get_languages(config=""):
        return [lang]

    def fake_image_to_string(_img, lang=None):
        return f"text-{lang}"

    monkeypatch.setattr(ingest, "convert_from_path", fake_convert_from_path)
    monkeypatch.setattr(ingest.pytesseract, "get_languages", fake_get_languages)
    monkeypatch.setattr(ingest.pytesseract, "image_to_string", fake_image_to_string)

    text = ingest.read_pdf_text(pdf_path, use_ocr=True, ocr_lang=lang)
    assert text.strip() != ""
