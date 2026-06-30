import streamlit as st
import tempfile
import os
import base64
from datetime import datetime
from pathlib import Path

from config import VERGADER_TYPES
from pdf_reader import extract_text
from analyzer import analyseer_vergadering
from word_exporter import export_to_word


def logo_as_data_uri(path: str) -> str:
    """Lees logo en geef terug als base64 data URI."""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        data = p.read_bytes()
        ext = p.suffix.lower().lstrip(".")
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "svg": "image/svg+xml",
        }.get(ext, "image/png")
        # Altijd base64 — voorkomt HTML/CSS escaping problemen bij SVG
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""

st.set_page_config(
    page_title="Vergadervoorbereiding",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Professional styling ---
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">

<style>
    /* Streamlit-elementen verbergen */
    #MainMenu, footer, header, .stDeployButton { display: none !important; }

    /* Custom scrollbar */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(30, 64, 175, 0.2);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(30, 64, 175, 0.4); }

    /* Typografie */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        color: #0F172A;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Subtiele fade-in op page load */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .block-container > div { animation: fadeInUp 0.6s ease-out; }

    /* Zakelijke achtergrondfoto met overlay */
    [data-testid="stAppViewContainer"] {
        background-image:
            linear-gradient(180deg, rgba(247, 248, 251, 0.92) 0%, rgba(247, 248, 251, 0.96) 100%),
            url('https://images.unsplash.com/photo-1497366216548-37526070297c?w=2400&q=80&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-repeat: no-repeat;
    }

    /* Subtiele textuur bovenop voor diepte */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        inset: 0;
        background:
            radial-gradient(ellipse at top right, rgba(30, 64, 175, 0.05) 0%, transparent 50%),
            radial-gradient(ellipse at bottom left, rgba(55, 48, 163, 0.04) 0%, transparent 50%);
        pointer-events: none;
        z-index: 0;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 4rem !important;
        max-width: 1240px !important;
        position: relative;
        z-index: 1;
    }

    /* Hero header — premium glas-look met mesh gradient */
    .hero {
        background:
            radial-gradient(ellipse at 80% 20%, rgba(99, 102, 241, 0.4) 0%, transparent 50%),
            radial-gradient(ellipse at 20% 80%, rgba(168, 85, 247, 0.25) 0%, transparent 50%),
            linear-gradient(135deg, rgba(15, 23, 42, 0.92) 0%, rgba(30, 41, 130, 0.88) 50%, rgba(49, 46, 129, 0.92) 100%),
            url('https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1600&q=80&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        color: white;
        padding: 56px 56px;
        border-radius: 28px;
        margin-bottom: 40px;
        box-shadow:
            0 1px 0 rgba(255,255,255,0.08) inset,
            0 24px 80px rgba(15, 23, 42, 0.45),
            0 8px 24px rgba(30, 64, 175, 0.25);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.06);
    }

    /* Subtiele lichtschijn van bovenaf */
    .hero::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, transparent 30%);
        pointer-events: none;
    }

    /* Gloeiende rand boven */
    .hero-glow {
        position: absolute;
        top: -2px;
        left: 20%;
        right: 20%;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(147, 197, 253, 0.6), transparent);
    }

    /* Logo van geselecteerde organisatie in de hero */
    .org-logo {
        position: absolute;
        right: 32px;
        top: 50%;
        transform: translateY(-50%);
        width: 240px;
        height: 96px;
        background: rgba(255, 255, 255, 0.96);
        padding: 14px 18px;
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
    }
    .org-logo img {
        max-width: 100%;
        max-height: 100%;
        width: auto;
        height: auto;
        object-fit: contain;
    }

    /* Op smalle schermen: logo onder de tekst zetten ipv naast */
    @media (max-width: 900px) {
        .hero { padding: 28px 24px 110px 24px; }
        .org-logo {
            right: 24px;
            top: auto;
            bottom: 20px;
            transform: none;
            width: 180px;
            height: 72px;
        }
    }

    /* Subtiel watermerk op het hele scherm (grote, vage versie achter de cards) */
    .org-watermark {
        position: fixed;
        bottom: 5%;
        right: 4%;
        width: 320px;
        height: 320px;
        background-size: contain;
        background-position: bottom right;
        background-repeat: no-repeat;
        opacity: 0.05;
        z-index: 0;
        pointer-events: none;
    }
    .hero::after {
        content: "";
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero h1 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 44px;
        font-weight: 700;
        margin: 12px 0 10px 0;
        letter-spacing: -1px;
        color: white;
        line-height: 1.1;
        position: relative;
        z-index: 2;
    }
    .hero p {
        font-size: 16px;
        margin: 0;
        opacity: 0.78;
        font-weight: 400;
        line-height: 1.5;
        max-width: 580px;
        position: relative;
        z-index: 2;
    }
    .hero .brand-mark {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 3px;
        opacity: 0.85;
        font-weight: 600;
        padding: 6px 12px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 999px;
        backdrop-filter: blur(10px);
        position: relative;
        z-index: 2;
    }
    .hero .brand-mark::before {
        content: "";
        width: 6px;
        height: 6px;
        background: #22D3EE;
        border-radius: 50%;
        box-shadow: 0 0 8px rgba(34, 211, 238, 0.8);
    }

    /* Card-stijl voor secties — met glas-effect */
    .card {
        background: rgba(255, 255, 255, 0.92);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 8px 32px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.6);
    }

    /* Section headers */
    h2, h3 {
        color: #0F172A !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px !important;
    }
    .stMarkdown h3 {
        font-size: 18px !important;
        margin-top: 0 !important;
    }

    /* Step-nummering — premium ring */
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #312E81 0%, #1E40AF 100%);
        color: white;
        border-radius: 50%;
        font-size: 13px;
        font-weight: 700;
        margin-right: 12px;
        vertical-align: middle;
        box-shadow:
            0 0 0 4px rgba(99, 102, 241, 0.1),
            0 4px 12px rgba(30, 64, 175, 0.35);
        font-family: 'Inter', sans-serif;
    }
    .step-title {
        font-size: 13px;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 14px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Primary knop — premium met glow */
    .stButton > button[kind="primary"],
    .stDownloadButton > button {
        background: linear-gradient(135deg, #312E81 0%, #1E40AF 50%, #1E3A8A 100%) !important;
        color: white !important;
        border: 1px solid rgba(147, 197, 253, 0.2) !important;
        border-radius: 14px !important;
        padding: 16px 28px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        letter-spacing: -0.2px !important;
        box-shadow:
            0 1px 0 rgba(255,255,255,0.15) inset,
            0 8px 24px rgba(30, 64, 175, 0.35),
            0 2px 6px rgba(30, 64, 175, 0.2) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative;
        overflow: hidden;
    }
    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow:
            0 1px 0 rgba(255,255,255,0.2) inset,
            0 14px 36px rgba(30, 64, 175, 0.5),
            0 4px 10px rgba(30, 64, 175, 0.3) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(0) !important;
    }

    /* Secundaire knop */
    .stButton > button:not([kind="primary"]) {
        background: white !important;
        color: #1E293B !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
        padding: 10px 18px !important;
        font-weight: 500 !important;
    }

    /* File uploader — glas-effect */
    [data-testid="stFileUploader"] section {
        background: rgba(248, 250, 252, 0.85) !important;
        backdrop-filter: blur(10px) !important;
        border: 2px dashed #CBD5E1 !important;
        border-radius: 14px !important;
        padding: 22px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #3B82F6 !important;
        background: rgba(239, 246, 255, 0.9) !important;
        transform: translateY(-1px);
    }

    /* Selectbox */
    [data-testid="stSelectbox"] > div > div {
        background: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
    }

    /* Tekstvak (opmerkingen) */
    [data-testid="stTextArea"] textarea {
        background: rgba(255, 255, 255, 0.92) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 12px !important;
        font-size: 14px !important;
        padding: 14px !important;
        font-family: inherit !important;
    }
    [data-testid="stTextArea"] textarea:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
    }

    /* Info-box (rol) */
    [data-testid="stAlert"] {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        border: 1px solid #BFDBFE !important;
        border-radius: 12px !important;
        color: #1E3A8A !important;
        padding: 14px 18px !important;
    }
    [data-testid="stAlert"] svg { color: #2563EB !important; }

    /* Resultaat-container — premium magazine-look */
    .result-container {
        background: rgba(255, 255, 255, 0.97);
        backdrop-filter: blur(28px);
        -webkit-backdrop-filter: blur(28px);
        border-radius: 24px;
        padding: 44px 48px;
        box-shadow:
            0 1px 0 rgba(255,255,255,1) inset,
            0 1px 3px rgba(15, 23, 42, 0.04),
            0 16px 48px rgba(15, 23, 42, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.8);
        margin-bottom: 16px;
        position: relative;
    }
    .result-container::before {
        content: "";
        position: absolute;
        top: 0;
        left: 24px;
        right: 24px;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.4), transparent);
    }
    .result-container h3 {
        color: #312E81 !important;
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 22px !important;
        font-weight: 700 !important;
        margin-top: 32px !important;
        padding-top: 20px !important;
        border-top: 1px solid #E2E8F0;
        letter-spacing: -0.4px !important;
    }
    .result-container h3:first-child { border-top: none; padding-top: 0; margin-top: 0 !important; }
    .result-container p {
        line-height: 1.7;
        color: #334155;
    }
    .result-container blockquote {
        border-left: 3px solid #6366F1;
        background: linear-gradient(135deg, rgba(238, 242, 255, 0.6), rgba(243, 232, 255, 0.4));
        padding: 16px 20px;
        border-radius: 0 12px 12px 0;
        margin: 16px 0;
        font-style: italic;
        color: #1E1B4B;
    }
    .result-container strong { color: #1E1B4B; }

    /* Spinner kleuren */
    .stSpinner > div { border-color: #1E40AF !important; }

    /* Footer — elegant signature */
    .footer {
        text-align: center;
        padding: 40px 0 20px 0;
        margin-top: 64px;
        position: relative;
        font-size: 12px;
        color: #64748B;
        letter-spacing: 0.8px;
        line-height: 1.8;
    }
    .footer::before {
        content: "";
        position: absolute;
        top: 0;
        left: 30%;
        right: 30%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.4), transparent);
    }
    .footer strong {
        color: #312E81;
        font-weight: 700;
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 13px;
        letter-spacing: 0.3px;
    }
    .footer .signature {
        font-style: italic;
        opacity: 0.7;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #0F172A !important;
    }
    [data-testid="stSidebar"] * { color: #E2E8F0 !important; }
    [data-testid="stSidebar"] input { color: #0F172A !important; }
</style>
""",
    unsafe_allow_html=True,
)

# --- API Key opslag ---
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


# --- Sidebar: instellingen ---
with st.sidebar:
    st.markdown("### ⚙️ Instellingen")
    api_key = st.text_input(
        "Anthropic API Key",
        value=load_api_key(),
        type="password",
        help="Je API key van console.anthropic.com",
    )
    if st.button("Opslaan", use_container_width=True):
        save_api_key(api_key)
        st.success("API key opgeslagen!")

    st.divider()
    st.caption("v1.1 — door Martin Dekker")


# Lees huidige keuze uit session state (uit vorige run), default = eerste optie
current_type = st.session_state.get("vergader_select", list(VERGADER_TYPES.keys())[0])
current_logo_uri = logo_as_data_uri(VERGADER_TYPES[current_type].get("logo", ""))

# --- Hero header met dynamisch logo ---
logo_html = (
    f'<div class="org-logo"><img src="{current_logo_uri}" alt="logo" /></div>'
    if current_logo_uri
    else ""
)
st.markdown(
    f"""
<div class="hero">
  <div class="hero-glow"></div>
  <div class="brand-mark">Executive Briefing</div>
  <h1>Vergadervoorbereiding</h1>
  <p>Upload de vergaderstukken — ontvang een volledige briefing per agendapunt, fijn afgestemd op jouw rol als bestuurder.</p>
  {logo_html}
</div>
""",
    unsafe_allow_html=True,
)

# Subtiel watermerk op achtergrond
if current_logo_uri:
    st.markdown(
        f'<div class="org-watermark" style="background-image: url(\'{current_logo_uri}\');"></div>',
        unsafe_allow_html=True,
    )

col1, col2 = st.columns([1, 2], gap="large")

with col1:
    with st.container():
        st.markdown(
            '<div class="step-title"><span class="step-number">1</span>Selecteer vergadering</div>',
            unsafe_allow_html=True,
        )
        vergader_type = st.selectbox(
            "Vergadertype",
            options=list(VERGADER_TYPES.keys()),
            format_func=lambda x: VERGADER_TYPES[x]["label"],
            label_visibility="collapsed",
            key="vergader_select",
        )
        rol_info = VERGADER_TYPES[vergader_type]["rol"]
        st.info(f"**Jouw rol:** {rol_info}")

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="step-title"><span class="step-number">2</span>Upload vergaderstukken</div>',
        unsafe_allow_html=True,
    )
    agenda_files = st.file_uploader(
        "Agenda / vergaderstukken",
        type=["pdf", "docx", "pptx", "xlsx", "eml", "msg"],
        accept_multiple_files=True,
        help="PDF, Word, PowerPoint, Excel of e-mail (.eml / .msg)",
        label_visibility="collapsed",
    )

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="step-title"><span class="step-number">3</span>Vorige notulen <span style="text-transform:none;font-weight:400;color:#94A3B8;font-size:13px;">(optioneel)</span></div>',
        unsafe_allow_html=True,
    )
    notulen_files = st.file_uploader(
        "Vorige notulen (PDF of Word)",
        type=["pdf", "docx", "pptx", "xlsx", "eml", "msg"],
        accept_multiple_files=True,
        key="notulen",
        label_visibility="collapsed",
    )

    # Extra: alleen bij LMT — upload RBT-stukken voor de mededeling
    rbt_files = []
    if vergader_type == "LMT":
        st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="step-title"><span class="step-number">4</span>RBT-stukken <span style="text-transform:none;font-weight:400;color:#94A3B8;font-size:13px;">(voor mededeling, optioneel)</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Upload hier de stukken van het laatste RBT — de app schrijft hier automatisch een spreektekst van voor je mededelingen.")
        rbt_files = st.file_uploader(
            "RBT-stukken (PDF of Word)",
            type=["pdf", "docx", "pptx", "xlsx", "eml", "msg"],
            accept_multiple_files=True,
            key="rbt",
            label_visibility="collapsed",
        )

    # Stap-nummer voor opmerkingen-veld dynamisch bepalen
    opmerkingen_stap = 5 if vergader_type == "LMT" else 4

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="step-title"><span class="step-number">{opmerkingen_stap}</span>Jouw opmerkingen <span style="text-transform:none;font-weight:400;color:#94A3B8;font-size:13px;">(optioneel)</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Voeg mededelingen toe, vraag extra aandacht voor onderwerpen, of geef andere wensen mee — de briefing wordt hierop aangepast.")
    opmerkingen = st.text_area(
        "Opmerkingen",
        placeholder="Bijv.: 'Even aandacht voor het budget Q3' • 'Mededeling: nieuwe HR-functionaris start 1 september' • 'Ik wil het scherp krijgen op de planning van project X'",
        height=120,
        key="opmerkingen",
        label_visibility="collapsed",
    )

    st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)

    analyseer_btn = st.button(
        "🔍  Analyseer vergadering",
        type="primary",
        disabled=not agenda_files or not api_key,
        use_container_width=True,
    )

    if not api_key:
        st.warning("Vul eerst je API key in via het zijpaneel.")
    elif not agenda_files:
        st.caption("Upload minimaal één vergaderstuk om te beginnen.")


with col2:
    if analyseer_btn and agenda_files and api_key:
        with st.spinner("📖  Stukken worden gelezen en geanalyseerd… (~30 seconden)"):
            agenda_teksten = []
            for f in agenda_files:
                try:
                    tekst = extract_text(f)
                    agenda_teksten.append(tekst)
                except Exception as e:
                    st.error(f"Fout bij lezen van {f.name}: {e}")

            notulen_teksten = []
            for f in notulen_files:
                try:
                    tekst = extract_text(f)
                    notulen_teksten.append(tekst)
                except Exception as e:
                    st.error(f"Fout bij lezen van {f.name}: {e}")

            rbt_teksten = []
            for f in rbt_files:
                try:
                    tekst = extract_text(f)
                    rbt_teksten.append(tekst)
                except Exception as e:
                    st.error(f"Fout bij lezen van {f.name}: {e}")

            agenda_tekst = "\n\n---\n\n".join(agenda_teksten)
            notulen_tekst = "\n\n---\n\n".join(notulen_teksten)
            rbt_tekst = "\n\n---\n\n".join(rbt_teksten)

            try:
                resultaat = analyseer_vergadering(
                    api_key=api_key,
                    vergader_type=vergader_type,
                    agenda_tekst=agenda_tekst,
                    notulen_tekst=notulen_tekst,
                    rbt_tekst=rbt_tekst,
                    opmerkingen=opmerkingen,
                )
                st.session_state["resultaat"] = resultaat
                st.session_state["vergader_type"] = vergader_type
            except Exception as e:
                st.error(f"Fout bij analyse: {e}")

    if "resultaat" in st.session_state:
        resultaat = st.session_state["resultaat"]
        vt = st.session_state["vergader_type"]

        st.markdown(
            f'<div class="result-container">',
            unsafe_allow_html=True,
        )
        st.markdown(resultaat)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="step-title" style="margin-top:24px;">📥 Exporteren</div>',
            unsafe_allow_html=True,
        )
        ecol1, ecol2 = st.columns(2)

        with ecol1:
            if st.button("⬇️  Word-document (.docx)", use_container_width=True):
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    export_to_word(resultaat, vt, tmp.name)
                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            label="✓  Klik om te downloaden",
                            data=f.read(),
                            file_name=f"vergadervoorbereiding_{vt.lower().replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    os.unlink(tmp.name)

        with ecol2:
            st.download_button(
                label="⬇️  Plain text (.txt)",
                data=resultaat,
                file_name=f"vergadervoorbereiding_{vt.lower().replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
    else:
        st.markdown(
            """
<style>
  @keyframes float-icon {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }
  .empty-state {
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255,255,255,0.7);
    border-radius: 24px;
    padding: 88px 40px;
    text-align: center;
    color: #64748B;
    box-shadow: 0 12px 48px rgba(15,23,42,0.06);
    position: relative;
    overflow: hidden;
  }
  .empty-state::before {
    content: "";
    position: absolute;
    top: 0; left: 24px; right: 24px; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(99,102,241,0.4), transparent);
  }
  .empty-icon {
    font-size: 72px;
    margin-bottom: 24px;
    opacity: 0.5;
    display: inline-block;
    animation: float-icon 3.5s ease-in-out infinite;
    filter: drop-shadow(0 8px 16px rgba(30, 64, 175, 0.15));
  }
  .empty-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 22px;
    font-weight: 700;
    color: #1E1B4B;
    margin-bottom: 8px;
    letter-spacing: -0.4px;
  }
  .empty-sub {
    font-size: 14px;
    color: #64748B;
    max-width: 320px;
    margin: 0 auto;
    line-height: 1.5;
  }
</style>
<div class="empty-state">
  <div class="empty-icon">✨</div>
  <div class="empty-title">Klaar voor jouw briefing</div>
  <div class="empty-sub">Selecteer een vergadering, upload de stukken, en je voorbereiding verschijnt hier.</div>
</div>
""",
            unsafe_allow_html=True,
        )

# --- Footer ---
year = datetime.now().year
st.markdown(
    f"""
<div class="footer">
  <strong>Vergadervoorbereiding</strong> · Gebouwd voor <em>Martin Dekker</em><br>
  <span class="signature">© {year} · Met aandacht ontworpen ✦ Powered by Claude</span>
</div>
""",
    unsafe_allow_html=True,
)
