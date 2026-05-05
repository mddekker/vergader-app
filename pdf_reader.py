import pdfplumber
from pathlib import Path


def extract_text(uploaded_file) -> str:
    """Extract text from an uploaded Streamlit file object (PDF)."""
    with pdfplumber.open(uploaded_file) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages).strip()


def extract_text_from_path(path: str) -> str:
    """Extract text from a PDF file on disk."""
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages).strip()
