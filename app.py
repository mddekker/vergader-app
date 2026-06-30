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
<style>
    /* Streamlit-elementen verbergen */
    #MainMenu, footer, header, .stDeployButton { display: none !important; }

    /* Typografie */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
        color: #0F172A;
    }

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

    /* Hero header met foto achtergrond */
    .hero {
        background:
            linear-gradient(135deg, rgba(15, 23, 42, 0.88) 0%, rgba(30, 64, 175, 0.85) 50%, rgba(55, 48, 163, 0.88) 100%),
            url('https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1600&q=80&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        color: white;
        padding: 44px 48px;
        border-radius: 24px;
        margin-bottom: 32px;
        box-shadow: 0 20px 60px rgba(15, 23, 42, 0.35), inset 0 1px 0 rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
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
        font-size: 32px;
        font-weight: 700;
        margin: 0 0 6px 0;
        letter-spacing: -0.6px;
        color: white;
    }
    .hero p {
        font-size: 15px;
        margin: 0;
        opacity: 0.85;
        font-weight: 400;
    }
    .hero .brand-mark {
        position: absolute;
        top: 28px;
        right: 32px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 2px;
        opacity: 0.7;
        font-weight: 500;
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

    /* Step-nummering */
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        background: linear-gradient(135deg, #3B82F6, #2563EB);
        color: white;
        border-radius: 50%;
        font-size: 13px;
        font-weight: 600;
        margin-right: 10px;
        vertical-align: middle;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
    }
    .step-title {
        font-size: 15px;
        font-weight: 600;
        color: #1E293B;
        margin-bottom: 14px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Primary knop */
    .stButton > button[kind="primary"],
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 24px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        letter-spacing: -0.2px !important;
        box-shadow: 0 4px 14px rgba(30, 64, 175, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(30, 64, 175, 0.4) !important;
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

    /* Resultaat-container — premium card */
    .result-container {
        background: rgba(255, 255, 255, 0.96);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border-radius: 20px;
        padding: 36px 40px;
        box-shadow:
            0 1px 3px rgba(15, 23, 42, 0.04),
            0 12px 40px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.7);
        margin-bottom: 16px;
    }
    .result-container h3 {
        color: #1E3A8A !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        margin-top: 24px !important;
        padding-top: 16px !important;
        border-top: 1px solid #E2E8F0;
    }
    .result-container h3:first-child { border-top: none; padding-top: 0; }

    /* Spinner kleuren */
    .stSpinner > div { border-color: #1E40AF !important; }

    /* Footer */
    .footer {
        text-align: center;
        padding: 32px 0 16px 0;
        margin-top: 48px;
        border-top: 1px solid #E2E8F0;
        font-size: 12px;
        color: #64748B;
        letter-spacing: 0.5px;
    }
    .footer strong {
        color: #1E3A8A;
        font-weight: 600;
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
  <div class="brand-mark">Executive Briefing Tool</div>
  <h1>📋 Vergadervoorbereiding</h1>
  <p>Upload de vergaderstukken — ontvang een volledige briefing per agendapunt, afgestemd op jouw rol.</p>
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
<div style="background:rgba(255,255,255,0.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.7);border-radius:20px;padding:64px 40px;text-align:center;color:#64748B;box-shadow:0 8px 32px rgba(15,23,42,0.06);">
  <div style="font-size:56px;margin-bottom:16px;opacity:0.4;">📄</div>
  <div style="font-size:16px;font-weight:600;color:#1E293B;margin-bottom:4px;">De briefing verschijnt hier</div>
  <div style="font-size:13px;color:#64748B;">Selecteer een vergadering, upload de stukken, klik op analyseren.</div>
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
