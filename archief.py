"""
Archief van briefings in Supabase.

Elke briefing wordt na de analyse opgeslagen (overleg, datum, tekst, bestandsnamen) en vervolgvragen
worden bij dezelfde briefing bewaard. Het archief is beschikbaar op alle apparaten.

Instellen: zet in de Streamlit-secrets (of als omgevingsvariabelen)
    SUPABASE_URL = "https://<project>.supabase.co"
    SUPABASE_KEY = "<service_role of secret key>"
De tabel heet 'briefings' (zie README voor de SQL).
"""

import os
from datetime import datetime
from typing import Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

TABEL = "briefings"
_client = None
_config_fout = ""


def _secret(naam: str) -> str:
    try:
        import streamlit as st

        if naam in st.secrets:
            return str(st.secrets[naam]).strip()
    except Exception:
        pass
    return os.environ.get(naam, "").strip()


def is_beschikbaar() -> bool:
    return _get_client() is not None


def config_fout() -> str:
    _get_client()
    return _config_fout


def _get_client():
    global _client, _config_fout
    if _client is not None:
        return _client
    if create_client is None:
        _config_fout = "Het pakket 'supabase' is niet geïnstalleerd (staat in requirements.txt)."
        return None
    url, key = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    if not url or not key:
        _config_fout = "SUPABASE_URL en SUPABASE_KEY ontbreken in de secrets."
        return None
    try:
        _client = create_client(url, key)
        _config_fout = ""
    except Exception as e:  # noqa: BLE001
        _config_fout = f"Kan geen verbinding maken met Supabase: {e}"
        return None
    return _client


# ---------------------------------------------------------------------------
# Bewerkingen
# ---------------------------------------------------------------------------

def opslaan(
    vergader_type: str,
    vergaderdatum_iso: str,
    briefing: str,
    bestanden: Optional[list] = None,
    titel: str = "",
) -> Optional[str]:
    """Sla een briefing op en geef het id terug (None als het archief niet beschikbaar is)."""
    client = _get_client()
    if client is None:
        return None
    rij = {
        "vergader_type": vergader_type,
        "vergaderdatum": vergaderdatum_iso or None,
        "titel": titel or f"{vergader_type} {vergaderdatum_iso or datetime.now().strftime('%Y-%m-%d')}",
        "briefing": briefing,
        "bestanden": bestanden or [],
        "vervolg": [],
    }
    res = client.table(TABEL).insert(rij).execute()
    data = res.data or []
    return data[0]["id"] if data else None


def update_vervolg(briefing_id: str, vervolg: list) -> None:
    client = _get_client()
    if client is None or not briefing_id:
        return
    client.table(TABEL).update({"vervolg": vervolg}).eq("id", briefing_id).execute()


def lijst(limiet: int = 100) -> list:
    """Overzicht van opgeslagen briefings, nieuwste eerst (zonder de volledige tekst)."""
    client = _get_client()
    if client is None:
        return []
    res = (
        client.table(TABEL)
        .select("id, created_at, vergader_type, vergaderdatum, titel, bestanden")
        .order("created_at", desc=True)
        .limit(limiet)
        .execute()
    )
    return res.data or []


def ophalen(briefing_id: str) -> Optional[dict]:
    client = _get_client()
    if client is None:
        return None
    res = client.table(TABEL).select("*").eq("id", briefing_id).limit(1).execute()
    data = res.data or []
    return data[0] if data else None


def verwijderen(briefing_id: str) -> None:
    client = _get_client()
    if client is None:
        return
    client.table(TABEL).delete().eq("id", briefing_id).execute()


def zoeken(tekst: str, limiet: int = 100) -> list:
    """Zoek in titel en briefingtekst."""
    client = _get_client()
    if client is None:
        return []
    patroon = "*" + tekst.strip().replace(",", " ") + "*"
    res = (
        client.table(TABEL)
        .select("id, created_at, vergader_type, vergaderdatum, titel, bestanden")
        .or_(f"titel.ilike.{patroon},briefing.ilike.{patroon}")
        .order("created_at", desc=True)
        .limit(limiet)
        .execute()
    )
    return res.data or []
