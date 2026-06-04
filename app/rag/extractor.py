"""
Per-format text extraction. Routes to the best extractor for each file type.
Falls back to unstructured for anything exotic.
"""
import io
from typing import Optional

from app.rag.detector import InputMeta


async def extract_text(file_bytes: bytes, meta: InputMeta, filename: str) -> str:
    """Route file to correct extractor. Returns raw extracted text."""
    ft = meta.file_type

    if ft == "pdf":
        return _extract_pdf(file_bytes, meta.is_scanned_pdf)
    if ft == "docx":
        return _extract_docx(file_bytes)
    if ft in ("doc",):
        return _extract_unstructured(file_bytes, filename)
    if ft == "xlsx":
        return _extract_xlsx(file_bytes)
    if ft == "csv":
        return _extract_csv(file_bytes)
    if ft == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    if ft == "html":
        return _extract_html(file_bytes)
    if ft == "image":
        return _extract_image_ocr(file_bytes)

    # Unknown — try unstructured as catch-all
    return _extract_unstructured(file_bytes, filename)


def _extract_pdf(file_bytes: bytes, is_scanned: bool) -> str:
    if is_scanned:
        return _pdf_ocr(file_bytes)
    return _pdf_text(file_bytes)


def _pdf_text(file_bytes: bytes) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
            # Extract tables as text too
            for table in page.extract_tables():
                rows = ["\t".join(str(c or "") for c in row) for row in table]
                text_parts.append("\n".join(rows))
    return "\n\n".join(text_parts)


def _pdf_ocr(file_bytes: bytes) -> str:
    from pdf2image import convert_from_bytes
    import pytesseract
    images = convert_from_bytes(file_bytes, dpi=200)
    pages = [pytesseract.image_to_string(img) for img in images]
    return "\n\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = "\t".join(cell.text for cell in row.cells)
            parts.append(row_text)
    return "\n".join(parts)


def _extract_xlsx(file_bytes: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            row_text = "\t".join(str(v) if v is not None else "" for v in row)
            if row_text.strip():
                parts.append(row_text)
    return "\n".join(parts)


def _extract_csv(file_bytes: bytes) -> str:
    import pandas as pd
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_string(index=False)


def _extract_html(file_bytes: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(file_bytes, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _extract_image_ocr(file_bytes: bytes) -> str:
    import pytesseract
    from PIL import Image
    img = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(img)


def _extract_unstructured(file_bytes: bytes, filename: str) -> str:
    try:
        from unstructured.partition.auto import partition
        elements = partition(file=io.BytesIO(file_bytes), metadata_filename=filename)
        return "\n\n".join(str(el) for el in elements if str(el).strip())
    except Exception as e:
        return f"[Extraction failed: {e}]"
