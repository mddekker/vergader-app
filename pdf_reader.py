import pdfplumber
from docx import Document
from pathlib import Path


def _extract_docx(uploaded_file) -> str:
    doc = Document(uploaded_file)
    parts = []
    # Paragrafen
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    # Tabellen
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                parts.append(row_text)
    return "\n\n".join(parts).strip()


def _extract_pdf(uploaded_file) -> str:
    with pdfplumber.open(uploaded_file) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages).strip()


def extract_text(uploaded_file) -> str:
    """Extract text from an uploaded Streamlit file object (PDF of Word)."""
    name = getattr(uploaded_file, "name", "")
    suffix = Path(name).suffix.lower()

    if suffix == ".docx":
        return _extract_docx(uploaded_file)
    if suffix == ".pdf":
        return _extract_pdf(uploaded_file)

    # Fallback: probeer PDF, dan docx
    try:
        return _extract_pdf(uploaded_file)
    except Exception:
        uploaded_file.seek(0)
        return _extract_docx(uploaded_file)


def extract_text_from_path(path: str) -> str:
    """Extract text from a PDF or Word file on disk."""
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return _extract_docx(path)
    return _extract_pdf(path)
