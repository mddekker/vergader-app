"""
Documentlezer voor de vergader-app.

Leest PDF, Word, PowerPoint, Excel en e-mail (.eml / .msg) en levert per bestand
een gestructureerd resultaat op: tekst met paginamarkeringen, aantal pagina's,
aantal tekens en een eventuele waarschuwing (bijvoorbeeld een scan zonder tekst).

De tekst van meerdere bestanden wordt gebundeld met duidelijke bestandskoppen,
zodat de analyse weet welk stuk bij welk agendapunt hoort en kan verwijzen naar
bestand en pagina.
"""

import io
import email
from dataclasses import dataclass, field
from email import policy
from pathlib import Path

import pdfplumber
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook

try:
    import extract_msg
except ImportError:  # pragma: no cover
    extract_msg = None


MIN_TEKENS_PER_PAGINA = 40  # daaronder beschouwen we een pagina als (vrijwel) leeg


@dataclass
class DocumentResult:
    name: str
    text: str = ""
    pages: int = 0
    chars: int = 0
    warning: str = ""
    kind: str = ""
    error: str = ""
    empty_pages: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Verwijder overbodige witruimte zonder de structuur kapot te maken."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if ln.strip():
            out.append(ln)
            blank = 0
        else:
            blank += 1
            if blank <= 1:
                out.append("")
    return "\n".join(out).strip()


def _table_to_text(table) -> str:
    rows = []
    for row in table or []:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _extract_pdf(source, result: DocumentResult) -> None:
    parts = []
    with pdfplumber.open(source) as pdf:
        result.pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_parts = [f"[Pagina {i}]"]
            if text.strip():
                page_parts.append(text)
            else:
                result.empty_pages.append(i)

            # Tabellen apart meenemen: extract_text verliest vaak de kolomstructuur
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for t_idx, table in enumerate(tables, start=1):
                if len(table) >= 2:
                    ttext = _table_to_text(table)
                    if ttext:
                        page_parts.append(f"[Tabel {t_idx} op pagina {i}]\n{ttext}")

            parts.append("\n".join(page_parts))

    result.text = _clean("\n\n".join(parts))

    if result.pages and len(result.empty_pages) == result.pages:
        result.warning = (
            "Geen leesbare tekst gevonden. Dit is waarschijnlijk een scan; "
            "de inhoud kan niet worden meegenomen in de analyse."
        )
    elif len(result.empty_pages) >= max(3, result.pages // 3):
        result.warning = (
            f"{len(result.empty_pages)} van de {result.pages} pagina's bevatten geen leesbare tekst "
            "(mogelijk gescande pagina's of alleen afbeeldingen)."
        )


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------

def _extract_docx(source, result: DocumentResult) -> None:
    doc = Document(source)
    parts = []
    for p in doc.paragraphs:
        if p.text.strip():
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style.startswith("heading") or style.startswith("kop"):
                parts.append(f"\n## {p.text.strip()}")
            else:
                parts.append(p.text)
    for t_idx, table in enumerate(doc.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            parts.append(f"[Tabel {t_idx}]\n" + "\n".join(rows))
    result.text = _clean("\n\n".join(parts))
    result.pages = max(1, round(len(result.text) / 3000)) if result.text else 0


# ---------------------------------------------------------------------------
# PowerPoint
# ---------------------------------------------------------------------------

def _extract_pptx(source, result: DocumentResult) -> None:
    pres = Presentation(source)
    parts = []
    for i, slide in enumerate(pres.slides, start=1):
        slide_parts = [f"[Slide {i}]"]
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_parts.append(text)
            if getattr(shape, "has_table", False) and shape.has_table:
                rows = []
                for row in shape.table.rows:
                    cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    slide_parts.append("[Tabel]\n" + "\n".join(rows))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                slide_parts.append(f"[Notities: {notes}]")
        parts.append("\n".join(slide_parts))
    result.pages = len(pres.slides)
    result.text = _clean("\n\n".join(parts))


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _fmt_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value).replace("\n", " ").strip()


def _extract_xlsx(source, result: DocumentResult) -> None:
    wb = load_workbook(source, data_only=True, read_only=True)
    parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_parts = [f"[Werkblad: {sheet_name}]"]
        n = 0
        for row in ws.iter_rows(values_only=True):
            cells = [_fmt_cell(c) for c in row]
            if any(cells):
                # Lege kolommen aan het eind weglaten
                while cells and not cells[-1]:
                    cells.pop()
                sheet_parts.append(" | ".join(cells))
                n += 1
                if n >= 500:
                    sheet_parts.append("[... werkblad ingekort na 500 rijen ...]")
                    break
        parts.append("\n".join(sheet_parts))
    result.pages = len(wb.sheetnames)
    result.text = _clean("\n\n".join(parts))


# ---------------------------------------------------------------------------
# E-mail (.eml)
# ---------------------------------------------------------------------------

def _read_bytes(source) -> bytes:
    if hasattr(source, "read"):
        if hasattr(source, "seek"):
            source.seek(0)
        raw = source.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="ignore")
        return raw
    with open(source, "rb") as f:
        return f.read()


def _extract_eml(source, result: DocumentResult) -> None:
    raw = _read_bytes(source)
    msg = email.message_from_bytes(raw, policy=policy.default)
    headers = [
        f"Van: {msg.get('From', '')}",
        f"Aan: {msg.get('To', '')}",
        f"Cc: {msg.get('Cc', '')}",
        f"Datum: {msg.get('Date', '')}",
        f"Onderwerp: {msg.get('Subject', '')}",
    ]
    headers = [h for h in headers if h.split(":", 1)[1].strip()]

    body = ""
    bijlagen = []
    if msg.is_multipart():
        for part in msg.walk():
            fn = part.get_filename()
            if fn:
                bijlagen.append(fn)
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    body = part.get_content()
                    break
                except Exception:
                    pass
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html" and not part.get_filename():
                    try:
                        body = _strip_html(part.get_content())
                        break
                    except Exception:
                        pass
    else:
        try:
            body = msg.get_content()
            if msg.get_content_type() == "text/html":
                body = _strip_html(body)
        except Exception:
            body = ""

    text = "\n".join(headers) + "\n\n" + (body or "").strip()
    if bijlagen:
        text += "\n\n[Bijlagen bij deze e-mail (niet uitgelezen): " + ", ".join(bijlagen) + "]"
        result.warning = "Deze e-mail bevat bijlagen. Upload die apart als je ze in de analyse wilt."
    result.text = _clean(text)
    result.pages = 1


def _strip_html(html: str) -> str:
    import re

    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|tr|li|h\d)>", "\n", html)
    text = re.sub(r"<[^>]+>", "", html)
    import html as html_lib

    return html_lib.unescape(text)


# ---------------------------------------------------------------------------
# Outlook (.msg)
# ---------------------------------------------------------------------------

def _extract_msg(source, result: DocumentResult) -> None:
    if extract_msg is None:
        raise RuntimeError("extract-msg is niet geïnstalleerd")
    if hasattr(source, "read"):
        msg = extract_msg.Message(io.BytesIO(_read_bytes(source)))
    else:
        msg = extract_msg.Message(source)

    headers = [
        f"Van: {msg.sender or ''}",
        f"Aan: {msg.to or ''}",
        f"Cc: {msg.cc or ''}",
        f"Datum: {msg.date or ''}",
        f"Onderwerp: {msg.subject or ''}",
    ]
    headers = [h for h in headers if h.split(":", 1)[1].strip()]
    body = (msg.body or "").strip()

    bijlagen = []
    try:
        bijlagen = [a.longFilename or a.shortFilename for a in msg.attachments if (a.longFilename or a.shortFilename)]
    except Exception:
        pass

    text = "\n".join(headers) + "\n\n" + body
    if bijlagen:
        text += "\n\n[Bijlagen bij deze e-mail (niet uitgelezen): " + ", ".join(bijlagen) + "]"
        result.warning = "Deze e-mail bevat bijlagen. Upload die apart als je ze in de analyse wilt."
    result.text = _clean(text)
    result.pages = 1


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_HANDLERS = {
    ".pdf": (_extract_pdf, "PDF"),
    ".docx": (_extract_docx, "Word"),
    ".pptx": (_extract_pptx, "PowerPoint"),
    ".xlsx": (_extract_xlsx, "Excel"),
    ".eml": (_extract_eml, "E-mail"),
    ".msg": (_extract_msg, "E-mail"),
}

SUPPORTED_EXTENSIONS = [ext.lstrip(".") for ext in _HANDLERS]


def extract_document(source, name: str = "") -> DocumentResult:
    """Lees een bestand (Streamlit UploadedFile of pad) en geef een DocumentResult terug."""
    if not name:
        name = getattr(source, "name", "") or str(source)
    name = Path(name).name
    result = DocumentResult(name=name)
    suffix = Path(name).suffix.lower()

    handler, kind = _HANDLERS.get(suffix, (None, ""))
    result.kind = kind or suffix.lstrip(".").upper()

    if handler is None:
        result.error = f"Bestandstype '{suffix}' wordt niet ondersteund."
        return result

    try:
        if hasattr(source, "seek"):
            source.seek(0)
        handler(source, result)
    except Exception as e:  # noqa: BLE001
        result.error = f"Kon bestand niet lezen: {e}"
        return result

    result.chars = len(result.text)
    if not result.text and not result.warning:
        result.warning = "Bestand is leeg of bevat geen leesbare tekst."
    return result


def combine_documents(docs: list, sectie: str = "Vergaderstukken") -> str:
    """Bundel de tekst van meerdere DocumentResults met duidelijke bestandskoppen."""
    blocks = []
    for i, d in enumerate([d for d in docs if d.ok and d.text], start=1):
        meta = f"{d.kind}"
        eenheid = {"PowerPoint": "slides", "Excel": "werkbladen", "PDF": "pagina's"}.get(d.kind)
        if d.pages and eenheid:
            meta += f", {d.pages} {eenheid}"
        header = f"===== {sectie.upper()} | BESTAND {i}: {d.name} ({meta}) ====="
        blocks.append(f"{header}\n\n{d.text}\n\n===== EINDE BESTAND {i}: {d.name} =====")
    return "\n\n\n".join(blocks)


# --- Backwards compatible helpers -------------------------------------------

def extract_text(uploaded_file) -> str:
    """Oude API: alleen de tekst."""
    r = extract_document(uploaded_file)
    if r.error:
        raise RuntimeError(r.error)
    return r.text


def extract_text_from_path(path: str) -> str:
    r = extract_document(path, name=path)
    if r.error:
        raise RuntimeError(r.error)
    return r.text
