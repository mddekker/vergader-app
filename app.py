import base64
import hashlib
import html
import io
import re
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from config import VERGADER_TYPES, APP_VERSIE, WAARSCHUW_TEKENS, MAX_TEKENS
from pdf_reader import extract_document, combine_documents, SUPPORTED_EXTENSIONS
from analyzer import analyseer_vergadering, stel_vervolgvraag
from word_exporter import export_to_word_bytes
import archief


# ---------------------------------------------------------------------------
# Pagina-instellingen en stijl
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Vergadervoorbereiding",
    page_icon="assets/favicon.png" if Path("assets/favicon.png").exists() else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

STYLES = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    #MainMenu, footer, header, .stDeployButton { display: none !important; }

    :root {
        --navy: #1F3864;
        --navy-2: #2E5496;
        --ink: #1F2937;
        --muted: #6B7280;
        --line: #E5E7EB;
        --soft: #F3F5F9;
        --red: #B42318;
        --red-soft: #FDECEA;
        --green: #376E3A;
        --orange: #C25A00;
        --blue-soft: #EEF2FF;
    }

    html, body, [data-testid="stAppViewContainer"], .stMarkdown, .stButton, .stSelectbox, .stTextArea {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--ink);
        -webkit-font-smoothing: antialiased;
    }
    [data-testid="stAppViewContainer"] { background: #FFFFFF; }
    .block-container { padding-top: 1.4rem !important; padding-bottom: 3rem !important; max-width: 1280px !important; }

    /* Kopregel */
    .topbar {
        display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
        padding: 14px 0 18px 0; border-bottom: 1px solid var(--line); margin-bottom: 22px;
    }
    .topbar .title { display: flex; flex-direction: column; gap: 2px; }
    .topbar .eyebrow { font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); font-weight: 600; }
    .topbar h1 { font-size: 26px; font-weight: 700; margin: 0; color: var(--navy); letter-spacing: -0.4px; line-height: 1.2; }
    .topbar .sub { font-size: 14px; color: var(--muted); margin: 0; }
    .topbar .logo { height: 54px; max-width: 220px; display: flex; align-items: center; }
    .topbar .logo img { max-height: 54px; max-width: 220px; object-fit: contain; }

    /* Stappen */
    .step { font-size: 12px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--navy); margin: 6px 0 8px 0; display: flex; align-items: center; gap: 8px; }
    .step .n { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--navy); color: white; font-size: 11px; font-weight: 700; }
    .step .opt { font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--muted); font-size: 12px; }
    .hint { font-size: 13px; color: var(--muted); margin: -2px 0 8px 0; line-height: 1.45; }

    /* Rolkaart */
    .rol { background: var(--soft); border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; font-size: 13.5px; color: var(--ink); margin: 6px 0 14px 0; line-height: 1.45; }
    .rol b { color: var(--navy); }

    /* Bestandenoverzicht */
    .files { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; margin: 8px 0 12px 0; font-size: 13px; }
    .files .row { display: flex; justify-content: space-between; gap: 10px; padding: 8px 12px; border-top: 1px solid var(--line); align-items: baseline; }
    .files .row:first-child { border-top: none; }
    .files .name { font-weight: 500; overflow-wrap: anywhere; }
    .files .meta { color: var(--muted); white-space: nowrap; font-size: 12px; }
    .files .warn { display: block; color: var(--orange); font-size: 12px; margin-top: 2px; }
    .files .err { display: block; color: var(--red); font-size: 12px; margin-top: 2px; }
    .files .total { background: var(--soft); color: var(--muted); font-size: 12px; padding: 7px 12px; border-top: 1px solid var(--line); }

    /* Knoppen */
    .stButton > button[kind="primary"] {
        background: var(--navy) !important; color: white !important; border: none !important;
        border-radius: 8px !important; padding: 12px 20px !important; font-weight: 600 !important; font-size: 15px !important;
        box-shadow: none !important; transition: background 0.15s ease !important;
    }
    .stButton > button[kind="primary"]:hover { background: var(--navy-2) !important; }
    .stButton > button:not([kind="primary"]), .stDownloadButton > button {
        background: white !important; color: var(--navy) !important; border: 1px solid #C7CFDC !important;
        border-radius: 8px !important; padding: 9px 16px !important; font-weight: 600 !important; font-size: 14px !important; box-shadow: none !important;
    }
    .stButton > button:not([kind="primary"]):hover, .stDownloadButton > button:hover { border-color: var(--navy) !important; background: var(--soft) !important; }

    /* Invoervelden */
    [data-testid="stFileUploader"] section { background: var(--soft) !important; border: 1.5px dashed #C7CFDC !important; border-radius: 10px !important; padding: 14px !important; }
    [data-testid="stFileUploader"] section:hover { border-color: var(--navy) !important; }
    [data-testid="stTextArea"] textarea { border: 1px solid #C7CFDC !important; border-radius: 8px !important; font-size: 14px !important; }
    [data-testid="stTextArea"] textarea:focus { border-color: var(--navy) !important; box-shadow: 0 0 0 2px rgba(31,56,100,0.15) !important; }
    [data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: 10px !important; }
    [data-testid="stExpander"] summary { font-size: 13.5px; font-weight: 600; color: var(--navy); }

    /* Resultaat (bordered container) */
    [data-testid="stVerticalBlockBorderWrapper"] { border: 1px solid var(--line) !important; border-radius: 12px !important; padding: 22px 26px !important; background: white; }
    .block-container .stMarkdown h2 { font-size: 19px; font-weight: 700; color: var(--navy); margin: 26px 0 10px 0; padding: 18px 0 0 0; border-top: 1px solid var(--line); }
    .block-container .stMarkdown h3 { font-size: 16px; font-weight: 700; color: var(--navy-2); margin: 22px 0 6px 0; padding: 0; }
    .block-container .stMarkdown p, .block-container .stMarkdown li { font-size: 14.5px; line-height: 1.6; }
    .block-container .stMarkdown blockquote { border-left: 3px solid var(--navy-2); background: var(--blue-soft); padding: 10px 16px; border-radius: 0 8px 8px 0; margin: 8px 0 12px 0; color: #1E1B4B; }
    .block-container .stMarkdown blockquote p { font-style: italic; margin: 0; }
    .badge { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; padding: 3px 9px; border-radius: 999px; margin: 2px 0 4px 0; }
    .badge-besluit { background: var(--red-soft); color: var(--red); }
    .badge-bespreking { background: var(--blue-soft); color: var(--navy-2); }
    .badge-informatie { background: #EAF4EA; color: var(--green); }
    .badge-kennisname { background: var(--soft); color: var(--muted); }
    .bron { font-size: 12.5px; color: var(--muted); font-style: italic; margin: 0 0 8px 0; }
    .besluit { background: var(--red-soft); border-left: 4px solid var(--red); padding: 10px 14px; border-radius: 0 8px 8px 0; margin: 8px 0 10px 0; font-size: 14.5px; line-height: 1.5; }
    .besluit b { color: var(--red); letter-spacing: 0.5px; margin-right: 6px; }
    .onzeker { color: var(--orange); font-style: italic; }

    /* Lege staat */
    .empty { border: 1px dashed #C7CFDC; border-radius: 12px; padding: 64px 32px; text-align: center; color: var(--muted); background: var(--soft); }
    .empty .t { font-size: 17px; font-weight: 600; color: var(--navy); margin-bottom: 6px; }
    .empty .s { font-size: 14px; max-width: 360px; margin: 0 auto; line-height: 1.5; }

    /* Vervolgvragen */
    .vraag { background: var(--soft); border-radius: 10px; padding: 10px 14px; margin: 10px 0 4px 0; font-size: 14px; font-weight: 600; color: var(--navy); }

    .arch { font-size: 14px; padding: 6px 0; line-height: 1.4; }
    .arch b { color: var(--navy); }
    .arch .meta { display: block; font-size: 12px; color: var(--muted); }

    .footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--line); }

    [data-testid="stSidebar"] { background: var(--soft) !important; border-right: 1px solid var(--line); }

    @media (max-width: 640px) {
        [data-testid="stVerticalBlockBorderWrapper"] { padding: 14px 14px !important; }
        .topbar h1 { font-size: 22px; }
    }
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def logo_as_data_uri(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return ""
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}.get(
            p.suffix.lower().lstrip("."), "image/png"
        )
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"
    except Exception:
        return ""


KEY_FILE = Path.home() / ".vergader_app_key"


def load_api_key() -> str:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return ""


def save_api_key(key: str):
    KEY_FILE.write_text(key.strip())


@st.cache_data(show_spinner=False, max_entries=64)
def _lees_bestand(data: bytes, naam: str, _hash: str):
    buf = io.BytesIO(data)
    buf.name = naam
    return extract_document(buf, name=naam)


def lees_bestanden(files) -> list:
    docs = []
    for f in files or []:
        data = f.getvalue()
        digest = hashlib.sha1(data).hexdigest()
        docs.append(_lees_bestand(data, f.name, digest))
    return docs


@st.cache_data(show_spinner=False, ttl=60)
def laad_archief(zoek: str = "") -> list:
    return archief.zoeken(zoek) if zoek else archief.lijst()


def toon_bestanden(docs: list):
    if not docs:
        return
    rows = []
    totaal = 0
    for d in docs:
        meta = d.kind
        eenheid = {"PDF": "pag.", "PowerPoint": "slides", "Excel": "werkbl."}.get(d.kind)
        if d.pages and eenheid:
            meta += f" · {d.pages} {eenheid}"
        if d.chars:
            meta += f" · {d.chars // 1000}k tekens"
        totaal += d.chars
        extra = ""
        if d.error:
            extra = f'<span class="err">{html.escape(d.error)}</span>'
        elif d.warning:
            extra = f'<span class="warn">{html.escape(d.warning)}</span>'
        rows.append(
            f'<div class="row"><div class="name">{html.escape(d.name)}{extra}</div><div class="meta">{html.escape(meta)}</div></div>'
        )
    st.markdown(
        f'<div class="files">{"".join(rows)}<div class="total">{len(docs)} bestand(en), {totaal // 1000}k tekens leesbaar</div></div>',
        unsafe_allow_html=True,
    )


def verfraai(md: str) -> str:
    """Maak van de Markdown-briefing nette HTML-accenten (badges, bron, besluitblok, onzekerheden)."""
    out = []
    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"^\**Type:?\**\s*:?\s*(.+)$", s, flags=re.IGNORECASE)
        if m and len(s) < 60:
            waarde = m.group(1).strip("* ").strip()
            key = waarde.lower()
            cls = "badge-kennisname"
            if "besluit" in key:
                cls = "badge-besluit"
            elif "bespreking" in key or "discussie" in key:
                cls = "badge-bespreking"
            elif "informatie" in key:
                cls = "badge-informatie"
            out.extend(["", f'<span class="badge {cls}">{html.escape(waarde)}</span>', ""])
            continue
        m = re.match(r"^\**Bron:?\**\s*:?\s*(.+)$", s, flags=re.IGNORECASE)
        if m:
            out.extend(["", f'<div class="bron">Bron: {html.escape(m.group(1).strip("* "))}</div>', ""])
            continue
        m = re.match(r"^[\W_]*\**BESLUIT VEREIST\**[\W_]*:?\s*(.*)$", s, flags=re.IGNORECASE)
        if m:
            out.extend(["", f'<div class="besluit"><b>BESLUIT VEREIST</b>{html.escape(m.group(1))}</div>', ""])
            continue
        line = re.sub(
            r"\[(Niet geverifieerd|Afleiding|Schatting|Speculatie|Aanname)([^\]]*)\]",
            r'<span class="onzeker">[\1\2]</span>',
            line,
        )
        out.append(line)
    return "\n".join(out)


def bestandsnaam(vt: str, datum_iso: str, ext: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", vt.lower()).strip("_")
    d = datum_iso or datetime.now().strftime("%Y-%m-%d")
    return f"vergadervoorbereiding_{slug}_{d}.{ext}"


def datum_tekst(d) -> str:
    if not d:
        return ""
    maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
    return f"{d.day} {maanden[d.month - 1]} {d.year}"


def reset_resultaat():
    for k in ("resultaat", "vervolg", "docx_bytes", "archief_id", "agenda_tekst", "notulen_tekst", "rbt_tekst"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("**Instellingen**")
    api_key = st.text_input("Anthropic API key", value=load_api_key(), type="password", help="Van console.anthropic.com")
    if st.button("Opslaan", use_container_width=True):
        save_api_key(api_key)
        st.success("API key opgeslagen.")
    st.divider()
    st.caption(f"Vergadervoorbereiding v{APP_VERSIE}")


# ---------------------------------------------------------------------------
# Kopregel
# ---------------------------------------------------------------------------

current_type = st.session_state.get("vergader_select", list(VERGADER_TYPES.keys())[0])
logo_uri = logo_as_data_uri(VERGADER_TYPES[current_type].get("logo", ""))
logo_html = f'<div class="logo"><img src="{logo_uri}" alt="logo"></div>' if logo_uri else ""
st.markdown(
    f"""
<div class="topbar">
  <div class="title">
    <div class="eyebrow">Executive briefing</div>
    <h1>Vergadervoorbereiding</h1>
    <p class="sub">Upload de stukken en ontvang per agendapunt een briefing, afgestemd op jouw rol.</p>
  </div>
  {logo_html}
</div>
""",
    unsafe_allow_html=True,
)

col_in, col_out = st.columns([5, 7], gap="large")

# ---------------------------------------------------------------------------
# Linkerkolom: invoer
# ---------------------------------------------------------------------------

with col_in:
    st.markdown('<div class="step"><span class="n">1</span>Vergadering</div>', unsafe_allow_html=True)
    vergader_type = st.selectbox(
        "Vergadertype",
        options=list(VERGADER_TYPES.keys()),
        format_func=lambda x: VERGADER_TYPES[x]["label"],
        label_visibility="collapsed",
        key="vergader_select",
    )
    st.markdown(f'<div class="rol"><b>Jouw rol:</b> {html.escape(VERGADER_TYPES[vergader_type]["rol"])}</div>', unsafe_allow_html=True)
    vergaderdatum = st.date_input("Datum van de vergadering", value=date.today(), format="DD-MM-YYYY", key="datum_input")

    st.markdown('<div class="step" style="margin-top:14px"><span class="n">2</span>Vergaderstukken</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">Agenda en onderliggende stukken. PDF, Word, PowerPoint, Excel of e-mail (.eml, .msg).</div>', unsafe_allow_html=True)
    agenda_files = st.file_uploader(
        "Vergaderstukken",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="agenda_files",
    )
    agenda_docs = lees_bestanden(agenda_files)
    toon_bestanden(agenda_docs)

    st.markdown('<div class="step" style="margin-top:14px"><span class="n">3</span>Context <span class="opt">(optioneel)</span></div>', unsafe_allow_html=True)
    with st.expander("Vorige notulen"):
        st.markdown('<div class="hint">De briefing checkt dan of openstaande acties uit de vorige vergadering terugkomen.</div>', unsafe_allow_html=True)
        notulen_files = st.file_uploader("Vorige notulen", type=SUPPORTED_EXTENSIONS, accept_multiple_files=True, key="notulen_files", label_visibility="collapsed")
        notulen_docs = lees_bestanden(notulen_files)
        toon_bestanden(notulen_docs)

    rbt_docs = []
    if vergader_type == "LMT":
        with st.expander("RBT-stukken voor je mededeling"):
            st.markdown('<div class="hint">Upload de stukken van het laatste RBT. De briefing begint dan met een spreektekst voor je mededelingen.</div>', unsafe_allow_html=True)
            rbt_files = st.file_uploader("RBT-stukken", type=SUPPORTED_EXTENSIONS, accept_multiple_files=True, key="rbt_files", label_visibility="collapsed")
            rbt_docs = lees_bestanden(rbt_files)
            toon_bestanden(rbt_docs)

    st.markdown('<div class="step" style="margin-top:14px"><span class="n">4</span>Jouw opmerkingen <span class="opt">(optioneel)</span></div>', unsafe_allow_html=True)
    opmerkingen = st.text_area(
        "Opmerkingen",
        placeholder="Bijv.: 'Even aandacht voor het budget Q3', 'Mededeling: nieuwe HR-functionaris start 1 oktober', 'Ik wil het scherp krijgen op de planning van project X'",
        height=110,
        key="opmerkingen",
        label_visibility="collapsed",
    )

    # Omvang en waarschuwingen
    leesbare_docs = [d for d in agenda_docs if d.ok and d.text]
    totaal_tekens = sum(d.chars for d in leesbare_docs) + sum(d.chars for d in notulen_docs if d.ok) + sum(d.chars for d in rbt_docs if d.ok)
    te_groot = totaal_tekens > MAX_TEKENS

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    analyseer_btn = st.button(
        "Analyseer vergadering",
        type="primary",
        disabled=not leesbare_docs or not api_key or te_groot,
        use_container_width=True,
    )

    if not api_key:
        st.warning("Vul eerst je API key in via het zijpaneel (pijltje linksboven).")
    elif agenda_files and not leesbare_docs:
        st.error("Geen van de bestanden bevat leesbare tekst. Controleer of het geen scans zijn.")
    elif not agenda_files:
        st.caption("Upload minimaal één vergaderstuk om te beginnen.")
    elif te_groot:
        st.error(f"De stukken zijn te omvangrijk ({totaal_tekens // 1000}k tekens). Splits de bundel of laat bijlagen weg.")
    elif totaal_tekens > WAARSCHUW_TEKENS:
        st.warning(f"Grote bundel ({totaal_tekens // 1000}k tekens). De analyse kan enkele minuten duren.")


# ---------------------------------------------------------------------------
# Rechterkolom: resultaat
# ---------------------------------------------------------------------------

with col_out:
    if analyseer_btn and leesbare_docs and api_key and not te_groot:
        reset_resultaat()
        agenda_tekst = combine_documents(agenda_docs, "Vergaderstukken")
        notulen_tekst = combine_documents(notulen_docs, "Vorige notulen")
        rbt_tekst = combine_documents(rbt_docs, "RBT-stukken")
        datum_str = datum_tekst(vergaderdatum)

        st.session_state.update(
            {
                "agenda_tekst": agenda_tekst,
                "notulen_tekst": notulen_tekst,
                "rbt_tekst": rbt_tekst,
                "vergader_type": vergader_type,
                "briefing_datum": datum_str,
                "briefing_datum_iso": vergaderdatum.isoformat() if vergaderdatum else "",
                "vervolg": [],
            }
        )

        st.markdown('<div class="step">Briefing</div>', unsafe_allow_html=True)
        st.caption("De briefing verschijnt terwijl hij wordt geschreven. Dit duurt meestal één tot enkele minuten.")
        klaar = False
        try:
            with st.container(border=True):
                resultaat = st.write_stream(
                    analyseer_vergadering(
                        api_key=api_key,
                        vergader_type=vergader_type,
                        agenda_tekst=agenda_tekst,
                        notulen_tekst=notulen_tekst,
                        rbt_tekst=rbt_tekst,
                        opmerkingen=opmerkingen,
                        vergaderdatum=datum_str,
                    )
                )
            st.session_state["resultaat"] = resultaat if isinstance(resultaat, str) else "".join(map(str, resultaat))
            st.session_state.setdefault("eerdere", []).insert(
                0,
                {
                    "titel": f"{vergader_type} · {datum_str} · {datetime.now().strftime('%H:%M')}",
                    "resultaat": st.session_state["resultaat"],
                    "vergader_type": vergader_type,
                    "briefing_datum": datum_str,
                    "briefing_datum_iso": st.session_state.get("briefing_datum_iso", ""),
                },
            )
            if archief.is_beschikbaar():
                try:
                    st.session_state["archief_id"] = archief.opslaan(
                        vergader_type=vergader_type,
                        vergaderdatum_iso=st.session_state.get("briefing_datum_iso", ""),
                        briefing=st.session_state["resultaat"],
                        bestanden=[d.name for d in leesbare_docs],
                        titel=f"{vergader_type} {datum_str}".strip(),
                    )
                    laad_archief.clear()
                except Exception as e:  # noqa: BLE001
                    st.warning(f"Briefing is gemaakt, maar opslaan in het archief lukte niet: {e}")
            klaar = True
        except Exception as e:  # noqa: BLE001
            fout = str(e)
            if "authentication" in fout.lower() or "api key" in fout.lower() or "401" in fout:
                st.error("De API key wordt niet geaccepteerd. Controleer de key in het zijpaneel.")
            elif "overloaded" in fout.lower() or "529" in fout:
                st.error("Claude is op dit moment overbelast. Probeer het over een minuut opnieuw.")
            elif "rate" in fout.lower() and "limit" in fout.lower():
                st.error("Te veel verzoeken in korte tijd. Wacht even en probeer opnieuw.")
            else:
                st.error(f"Fout bij analyse: {fout}")
        if klaar:
            st.rerun()

    elif "resultaat" in st.session_state:
        resultaat = st.session_state["resultaat"]
        vt = st.session_state.get("vergader_type", vergader_type)
        datum_str = st.session_state.get("briefing_datum", "")
        datum_iso = st.session_state.get("briefing_datum_iso", "")

        # Actiebalk
        if "docx_bytes" not in st.session_state:
            try:
                st.session_state["docx_bytes"] = export_to_word_bytes(resultaat, vt, vergaderdatum=datum_str)
            except Exception as e:  # noqa: BLE001
                st.session_state["docx_bytes"] = None
                st.warning(f"Word-export mislukt: {e}")

        kop_l, kop_r = st.columns([6, 6])
        with kop_l:
            st.markdown(f'<div class="step">Briefing {html.escape(vt)}<span class="opt">{html.escape(datum_str)}</span></div>', unsafe_allow_html=True)
        with kop_r:
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.session_state.get("docx_bytes"):
                    st.download_button(
                        "Word",
                        data=st.session_state["docx_bytes"],
                        file_name=bestandsnaam(vt, datum_iso, "docx"),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
            with b2:
                st.download_button(
                    "Tekst",
                    data=resultaat,
                    file_name=bestandsnaam(vt, datum_iso, "md"),
                    mime="text/markdown",
                    use_container_width=True,
                )
            with b3:
                if st.button("Nieuw", use_container_width=True, help="Resultaat wissen en opnieuw beginnen"):
                    reset_resultaat()
                    st.rerun()

        with st.container(border=True):
            st.markdown(verfraai(resultaat), unsafe_allow_html=True)

        # Vervolgvragen
        st.markdown('<div class="step" style="margin-top:22px">Vervolgvraag</div>', unsafe_allow_html=True)
        st.markdown('<div class="hint">Vraag door op de stukken of de briefing. Bijvoorbeeld: "Wat staat er precies over de personeelskosten?" of "Maak de spreektekst bij punt 4 scherper."</div>', unsafe_allow_html=True)

        if not st.session_state.get("agenda_tekst"):
            st.caption("Deze briefing komt uit het archief. Vervolgvragen gaan dan alleen over de briefing zelf; de originele stukken zijn niet meer beschikbaar.")

        for beurt in st.session_state.get("vervolg", []):
            st.markdown(f'<div class="vraag">{html.escape(beurt["vraag"])}</div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(verfraai(beurt["antwoord"]), unsafe_allow_html=True)

        with st.form("vervolg_form", clear_on_submit=True):
            vraag = st.text_input("Vervolgvraag", placeholder="Typ je vraag en druk op Enter", label_visibility="collapsed")
            verstuur = st.form_submit_button("Vraag stellen")

        if verstuur and vraag.strip():
            geschiedenis = []
            for beurt in st.session_state.get("vervolg", []):
                geschiedenis.append({"role": "user", "content": beurt["vraag"]})
                geschiedenis.append({"role": "assistant", "content": beurt["antwoord"]})
            st.markdown(f'<div class="vraag">{html.escape(vraag)}</div>', unsafe_allow_html=True)
            beantwoord = False
            try:
                with st.container(border=True):
                    antwoord = st.write_stream(
                        stel_vervolgvraag(
                            api_key=api_key,
                            agenda_tekst=st.session_state.get("agenda_tekst", ""),
                            briefing=resultaat,
                            geschiedenis=geschiedenis,
                            vraag=vraag.strip(),
                            notulen_tekst=st.session_state.get("notulen_tekst", ""),
                            rbt_tekst=st.session_state.get("rbt_tekst", ""),
                        )
                    )
                antwoord = antwoord if isinstance(antwoord, str) else "".join(map(str, antwoord))
                st.session_state.setdefault("vervolg", []).append({"vraag": vraag.strip(), "antwoord": antwoord})
                if st.session_state.get("archief_id"):
                    try:
                        archief.update_vervolg(st.session_state["archief_id"], st.session_state["vervolg"])
                    except Exception:  # noqa: BLE001
                        pass
                beantwoord = True
            except Exception as e:  # noqa: BLE001
                st.error(f"Fout bij vervolgvraag: {e}")
            if beantwoord:
                st.rerun()

    else:
        st.markdown(
            """
<div class="empty">
  <div class="t">Klaar voor je briefing</div>
  <div class="s">Kies de vergadering, upload de stukken en klik op Analyseer. De briefing verschijnt hier, met daarna een Word-export en ruimte voor vervolgvragen.</div>
</div>
""",
            unsafe_allow_html=True,
        )

    # Archief
    st.markdown('<div class="step" style="margin-top:28px">Archief</div>', unsafe_allow_html=True)
    if archief.is_beschikbaar():
        zoek = st.text_input("Zoeken in archief", placeholder="Zoek op overleg, datum of tekst", label_visibility="collapsed", key="archief_zoek")
        try:
            items = laad_archief(zoek.strip())
        except Exception as e:  # noqa: BLE001
            items = []
            st.warning(f"Archief kon niet worden geladen: {e}")
        if not items:
            st.caption("Nog geen opgeslagen briefingen." if not zoek else "Niets gevonden.")
        for item in items:
            c1, c2, c3 = st.columns([7, 2, 2])
            aangemaakt = (item.get("created_at") or "")[:16].replace("T", " ")
            datum = item.get("vergaderdatum") or ""
            if datum:
                try:
                    datum = datetime.fromisoformat(datum).strftime("%d-%m-%Y")
                except ValueError:
                    pass
            bestanden = item.get("bestanden") or []
            c1.markdown(
                f'<div class="arch"><b>{html.escape(item.get("vergader_type", ""))}</b> · {html.escape(datum)}'
                f'<span class="meta">gemaakt {html.escape(aangemaakt)}'
                + (f' · {len(bestanden)} bestand(en): {html.escape(", ".join(bestanden)[:120])}' if bestanden else "")
                + "</span></div>",
                unsafe_allow_html=True,
            )
            if c2.button("Openen", key=f"open_{item['id']}", use_container_width=True):
                rij = archief.ophalen(item["id"])
                if rij:
                    reset_resultaat()
                    d_iso = rij.get("vergaderdatum") or ""
                    try:
                        d_str = datum_tekst(datetime.fromisoformat(d_iso).date()) if d_iso else ""
                    except ValueError:
                        d_str = d_iso
                    st.session_state.update(
                        {
                            "resultaat": rij["briefing"],
                            "vergader_type": rij["vergader_type"],
                            "briefing_datum": d_str,
                            "briefing_datum_iso": d_iso,
                            "vervolg": rij.get("vervolg") or [],
                            "archief_id": rij["id"],
                        }
                    )
                    st.rerun()
            if c3.button("Verwijder", key=f"del_{item['id']}", use_container_width=True):
                try:
                    archief.verwijderen(item["id"])
                    laad_archief.clear()
                    if st.session_state.get("archief_id") == item["id"]:
                        reset_resultaat()
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Verwijderen mislukt: {e}")
    else:
        st.caption("Archief niet ingesteld: " + archief.config_fout() + " Zie README voor de instructie.")
        eerdere = st.session_state.get("eerdere", [])
        if eerdere:
            with st.expander(f"Briefingen in deze sessie ({len(eerdere)})"):
                for i, item in enumerate(eerdere):
                    c1, c2 = st.columns([8, 3])
                    c1.markdown(f"**{html.escape(item['titel'])}**")
                    if c2.button("Openen", key=f"sessie_open_{i}", use_container_width=True):
                        reset_resultaat()
                        st.session_state.update(
                            {
                                "resultaat": item["resultaat"],
                                "vergader_type": item["vergader_type"],
                                "briefing_datum": item["briefing_datum"],
                                "briefing_datum_iso": item.get("briefing_datum_iso", ""),
                                "vervolg": [],
                            }
                        )
                        st.rerun()


# ---------------------------------------------------------------------------
# Voettekst
# ---------------------------------------------------------------------------

st.markdown(
    f'<div class="footer">Vergadervoorbereiding v{APP_VERSIE} · Martin Dekker · {datetime.now().year}</div>',
    unsafe_allow_html=True,
)
