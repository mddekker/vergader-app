import streamlit as st
import tempfile
import os
from pathlib import Path

from config import VERGADER_TYPES
from pdf_reader import extract_text
from analyzer import analyseer_vergadering
from word_exporter import export_to_word

st.set_page_config(
    page_title="Vergadervoorbereiding",
    page_icon="📋",
    layout="wide",
)

# --- API Key opslag (lokaal of via Streamlit Cloud secrets) ---
KEY_FILE = Path.home() / ".vergader_app_key"


def load_api_key() -> str:
    # Streamlit Cloud: secrets.toml heeft prioriteit
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
    st.title("⚙️ Instellingen")
    api_key = st.text_input(
        "Anthropic API Key",
        value=load_api_key(),
        type="password",
        help="Je API key van console.anthropic.com",
    )
    if st.button("Opslaan"):
        save_api_key(api_key)
        st.success("API key opgeslagen!")

    st.divider()
    st.caption("Vergadervoorbereiding v1.0")


# --- Hoofdscherm ---
st.title("📋 Vergadervoorbereiding")
st.write("Upload de vergaderstukken en ontvang een volledige voorbereiding per agendapunt.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Selecteer vergadering")
    vergader_type = st.selectbox(
        "Vergadertype",
        options=list(VERGADER_TYPES.keys()),
        format_func=lambda x: VERGADER_TYPES[x]["label"],
    )

    rol_info = VERGADER_TYPES[vergader_type]["rol"]
    st.info(f"**Jouw rol:** {rol_info}")

    st.subheader("2. Upload vergaderstukken")
    agenda_files = st.file_uploader(
        "Agenda / vergaderstukken (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Je kunt meerdere PDF-bestanden tegelijk uploaden",
    )

    st.subheader("3. Vorige notulen (optioneel)")
    notulen_files = st.file_uploader(
        "Vorige notulen (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        key="notulen",
    )

    analyseer_btn = st.button(
        "🔍 Analyseer vergadering",
        type="primary",
        disabled=not agenda_files or not api_key,
        use_container_width=True,
    )

    if not api_key:
        st.warning("Vul eerst je API key in via de instellingen (linkerkolom).")
    elif not agenda_files:
        st.info("Upload minimaal één vergaderstuk om te beginnen.")


with col2:
    st.subheader("Voorbereiding")

    if analyseer_btn and agenda_files and api_key:
        with st.spinner("Stukken worden gelezen en geanalyseerd… (dit duurt ~30 seconden)"):
            # PDF tekst extraheren
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

            agenda_tekst = "\n\n---\n\n".join(agenda_teksten)
            notulen_tekst = "\n\n---\n\n".join(notulen_teksten)

            try:
                resultaat = analyseer_vergadering(
                    api_key=api_key,
                    vergader_type=vergader_type,
                    agenda_tekst=agenda_tekst,
                    notulen_tekst=notulen_tekst,
                )
                st.session_state["resultaat"] = resultaat
                st.session_state["vergader_type"] = vergader_type
            except Exception as e:
                st.error(f"Fout bij analyse: {e}")

    if "resultaat" in st.session_state:
        resultaat = st.session_state["resultaat"]
        vt = st.session_state["vergader_type"]

        st.markdown(resultaat)

        st.divider()
        st.subheader("📥 Exporteren")
        ecol1, ecol2 = st.columns(2)

        with ecol1:
            if st.button("⬇️ Download als Word (.docx)", use_container_width=True):
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    export_to_word(resultaat, vt, tmp.name)
                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            label="Klik hier om te downloaden",
                            data=f.read(),
                            file_name=f"vergadervoorbereiding_{vt.lower().replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    os.unlink(tmp.name)

        with ecol2:
            st.download_button(
                label="⬇️ Download als tekst (.txt)",
                data=resultaat,
                file_name=f"vergadervoorbereiding_{vt.lower().replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
    else:
        st.info("De voorbereiding verschijnt hier na de analyse.")
