"""
Word-export van de briefing.

Zet de Markdown-briefing om in een net Word-document: Arial, blauwe koppen, type-labels,
een opvallend blok bij "BESLUIT VEREIST", spreekteksten als citaat, onzekerheden in oranje,
en een kop- en voettekst met paginanummers.
"""

import re
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm


FONT = "Arial"
KLEUR_H1 = RGBColor(0x1F, 0x38, 0x64)
KLEUR_H2 = RGBColor(0x2E, 0x54, 0x96)
KLEUR_GRIJS = RGBColor(0x6B, 0x72, 0x80)
KLEUR_ORANJE = RGBColor(0xC2, 0x5A, 0x00)
KLEUR_ROOD = RGBColor(0xB4, 0x23, 0x18)
KLEUR_TEKST = RGBColor(0x1F, 0x29, 0x37)

TYPE_KLEUREN = {
    "besluit": RGBColor(0xB4, 0x23, 0x18),
    "bespreking": RGBColor(0x2E, 0x54, 0x96),
    "discussie": RGBColor(0x2E, 0x54, 0x96),
    "informatie": RGBColor(0x37, 0x6E, 0x3A),
    "informatief": RGBColor(0x37, 0x6E, 0x3A),
    "ter kennisname": RGBColor(0x6B, 0x72, 0x80),
    "kennisname": RGBColor(0x6B, 0x72, 0x80),
}

ONZEKERHEID_RE = re.compile(r"(\[(?:Niet geverifieerd|Afleiding|Schatting|Speculatie|Aanname)[^\]]*\])")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⭐⬆✅❌❗️]+"
)


# ---------------------------------------------------------------------------
# Opmaak-hulpjes
# ---------------------------------------------------------------------------

def _schoon(text: str) -> str:
    text = EMOJI_RE.sub("", text)
    text = text.replace(" — ", ": ").replace("—", "-").replace("–", "-")
    return text.strip()


def _zet_font(run, size=None, bold=None, italic=None, color=None):
    run.font.name = FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def _voeg_inline_toe(paragraph, text: str, size=10.5, base_bold=False, base_italic=False, base_color=KLEUR_TEKST):
    """Voeg tekst toe met **vet**, *cursief* en oranje onzekerheidslabels."""
    text = _schoon(text)
    # Eerst splitsen op onzekerheidslabels, daarna op vet/cursief
    for stuk in ONZEKERHEID_RE.split(text):
        if not stuk:
            continue
        if ONZEKERHEID_RE.fullmatch(stuk):
            run = paragraph.add_run(stuk)
            _zet_font(run, size=size, bold=False, italic=True, color=KLEUR_ORANJE)
            continue
        for deel in re.split(r"(\*\*.+?\*\*|\*[^*]+?\*)", stuk):
            if not deel:
                continue
            if deel.startswith("**") and deel.endswith("**") and len(deel) > 4:
                run = paragraph.add_run(deel[2:-2])
                _zet_font(run, size=size, bold=True, italic=base_italic, color=base_color)
            elif deel.startswith("*") and deel.endswith("*") and len(deel) > 2:
                run = paragraph.add_run(deel[1:-1])
                _zet_font(run, size=size, bold=base_bold, italic=True, color=base_color)
            else:
                run = paragraph.add_run(deel)
                _zet_font(run, size=size, bold=base_bold, italic=base_italic, color=base_color)


def _arcering(paragraph, hex_kleur: str):
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_kleur)
    ppr.append(shd)


def _linkerrand(paragraph, hex_kleur: str, dikte: int = 18):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(dikte))
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), hex_kleur)
    pbdr.append(left)
    ppr.append(pbdr)


def _paginanummer(paragraph):
    """Voeg een PAGE-veld toe aan een paragraaf."""
    run = paragraph.add_run()
    _zet_font(run, size=8, color=KLEUR_GRIJS)
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def _stel_stijlen_in(doc):
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = KLEUR_TEKST
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.15

    for naam, size, kleur, before in (("Heading 1", 15, KLEUR_H1, 18), ("Heading 2", 12.5, KLEUR_H2, 14), ("Title", 22, KLEUR_H1, 0)):
        st = doc.styles[naam]
        st.font.name = FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = kleur
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(4)
        st.paragraph_format.keep_with_next = True

    for sectie in doc.sections:
        sectie.top_margin = Cm(2.2)
        sectie.bottom_margin = Cm(2.0)
        sectie.left_margin = Cm(2.3)
        sectie.right_margin = Cm(2.3)


# ---------------------------------------------------------------------------
# Hoofdfunctie
# ---------------------------------------------------------------------------

def export_to_word(
    analyse_tekst: str,
    vergader_type: str,
    output_path: str,
    vergaderdatum: str = "",
) -> str:
    doc = Document()
    _stel_stijlen_in(doc)

    # --- Kop- en voettekst -------------------------------------------------
    sectie = doc.sections[0]
    kop = sectie.header.paragraphs[0]
    kop.text = ""
    r = kop.add_run(f"Vergadervoorbereiding {vergader_type}" + (f"  |  {vergaderdatum}" if vergaderdatum else ""))
    _zet_font(r, size=8, color=KLEUR_GRIJS)

    voet = sectie.footer.paragraphs[0]
    voet.text = ""
    voet.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = voet.add_run("Vertrouwelijk, alleen voor eigen voorbereiding   |   pagina ")
    _zet_font(r, size=8, color=KLEUR_GRIJS)
    _paginanummer(voet)

    # --- Titel -------------------------------------------------------------
    titel = doc.add_paragraph(style="Title")
    r = titel.add_run(f"Vergadervoorbereiding: {vergader_type}")
    _zet_font(r, size=22, bold=True, color=KLEUR_H1)

    sub = doc.add_paragraph()
    regel = f"Vergadering: {vergaderdatum}   |   " if vergaderdatum else ""
    r = sub.add_run(regel + f"Gegenereerd op {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    _zet_font(r, size=9, color=KLEUR_GRIJS)
    sub.paragraph_format.space_after = Pt(14)

    # --- Inhoud ------------------------------------------------------------
    for raw in analyse_tekst.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "---":
            continue

        # Koppen
        if stripped.startswith("#### "):
            p = doc.add_paragraph()
            _voeg_inline_toe(p, stripped[5:], size=11, base_bold=True, base_color=KLEUR_H2)
            p.paragraph_format.space_before = Pt(8)
            continue
        if stripped.startswith("### "):
            doc.add_heading(_schoon(stripped[4:]), level=2)
            continue
        if stripped.startswith("## "):
            doc.add_heading(_schoon(stripped[3:]), level=1)
            continue
        if stripped.startswith("# "):
            doc.add_heading(_schoon(stripped[2:]), level=1)
            continue

        # Type-regel
        m = re.match(r"^\**Type:?\**\s*:?\s*(.+)$", stripped, flags=re.IGNORECASE)
        if m and len(stripped) < 60:
            waarde = _schoon(m.group(1)).strip("* ")
            kleur = TYPE_KLEUREN.get(waarde.lower(), KLEUR_H2)
            p = doc.add_paragraph()
            r = p.add_run("Type: ")
            _zet_font(r, size=9.5, bold=True, color=KLEUR_GRIJS)
            r = p.add_run(waarde.upper())
            _zet_font(r, size=9.5, bold=True, color=kleur)
            p.paragraph_format.space_after = Pt(1)
            continue

        # Bron-regel
        m = re.match(r"^\**Bron:?\**\s*:?\s*(.+)$", stripped, flags=re.IGNORECASE)
        if m:
            p = doc.add_paragraph()
            r = p.add_run("Bron: " + _schoon(m.group(1)).strip("* "))
            _zet_font(r, size=9, italic=True, color=KLEUR_GRIJS)
            p.paragraph_format.space_after = Pt(6)
            continue

        # Besluit vereist
        m = re.match(r"^[\W_]*\**BESLUIT VEREIST\**[\W_]*:?\s*(.*)$", stripped, flags=re.IGNORECASE)
        if m:
            p = doc.add_paragraph()
            _arcering(p, "FDECEA")
            _linkerrand(p, "B42318", 24)
            p.paragraph_format.left_indent = Cm(0.3)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run("BESLUIT VEREIST  ")
            _zet_font(r, size=10.5, bold=True, color=KLEUR_ROOD)
            _voeg_inline_toe(p, m.group(1))
            continue

        m = re.match(r"^\**Alternatieven:?\**\s*:?\s*(.+)$", stripped, flags=re.IGNORECASE)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.3)
            r = p.add_run("Alternatieven: ")
            _zet_font(r, size=10.5, bold=True)
            _voeg_inline_toe(p, m.group(1))
            continue

        # Citaat / spreektekst
        if stripped.startswith(">"):
            p = doc.add_paragraph()
            _arcering(p, "EEF2FF")
            _linkerrand(p, "2E5496", 18)
            p.paragraph_format.left_indent = Cm(0.5)
            p.paragraph_format.right_indent = Cm(0.5)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(6)
            _voeg_inline_toe(p, stripped.lstrip("> ").strip(), base_italic=True)
            continue

        # Bullets (met inspringing)
        m = re.match(r"^(\s*)[-*•]\s+(.*)$", line)
        if m:
            niveau = min(len(m.group(1)) // 2, 2)
            stijl = "List Bullet" if niveau == 0 else f"List Bullet {niveau + 1}"
            try:
                p = doc.add_paragraph(style=stijl)
            except KeyError:
                p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            _voeg_inline_toe(p, m.group(2))
            continue

        # Genummerde lijst
        m = re.match(r"^\s*(\d+)[.)]\s+(.*)$", stripped)
        if m and not stripped.startswith("#"):
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(2)
            _voeg_inline_toe(p, m.group(2))
            continue

        # Label-regel (**Samenvatting**)
        if re.fullmatch(r"\*\*[^*]+\*\*:?", stripped):
            p = doc.add_paragraph()
            r = p.add_run(_schoon(stripped.strip("*:")))
            _zet_font(r, size=10.5, bold=True, color=KLEUR_H1)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.keep_with_next = True
            continue

        # Gewone alinea
        p = doc.add_paragraph()
        _voeg_inline_toe(p, stripped)

    doc.save(output_path)
    return output_path


def export_to_word_bytes(analyse_tekst: str, vergader_type: str, vergaderdatum: str = "") -> bytes:
    """Zelfde als export_to_word, maar geeft de bytes terug (handig voor een downloadknop)."""
    import io
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        pad = tmp.name
    try:
        export_to_word(analyse_tekst, vergader_type, pad, vergaderdatum=vergaderdatum)
        with open(pad, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(pad)
        except OSError:
            pass
