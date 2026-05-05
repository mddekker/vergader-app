import anthropic
from config import VERGADER_TYPES


SYSTEM_PROMPT = """Je bent een ervaren bestuurssecretaris die vergaderingen voorbereidt voor Martin,
een drukbezette bestuurder. Je schrijft altijd in het Nederlands. Je bent bondig maar volledig.
Je output is direct bruikbaar — geen inleidingen, geen herhaling van de opdracht."""


def analyseer_vergadering(
    api_key: str,
    vergader_type: str,
    agenda_tekst: str,
    notulen_tekst: str = "",
) -> str:
    config = VERGADER_TYPES[vergader_type]

    notulen_sectie = ""
    if notulen_tekst.strip():
        notulen_sectie = f"""
## Vorige notulen (ter context)
{notulen_tekst}

---
"""

    user_prompt = f"""
{notulen_sectie}
## Vergaderstukken / agenda
{agenda_tekst}

---

**Jouw taak:**
Bereid Martin voor op deze vergadering. Hij is {config['rol']}.

{config['context']}

Geef per agendapunt de volgende analyse (sla lege of procedurele punten zoals "opening" en "rondvraag" over, of behandel ze kort):

### [Nummer]. [Naam agendapunt]
**Type:** Informatie / Besluit / Ter kennisname / Discussie

**Samenvatting (5-10 regels):**
Wat staat er in de stukken? Wat is de kern?

**Vragen voor Martin:**
- [2-4 concrete, scherpe vragen die Martin kan stellen vanuit zijn rol als {config['rol']}]

**Aandachtspunten / acties:**
- [Wat moet Martin weten, beslissen, of doen naar aanleiding van dit punt?]

---

Sluit af met een **Totaaloverzicht** met:
- Lijst van beslissingen die genomen moeten worden
- Lijst van actiepunten voor Martin persoonlijk
- Eventuele rode vlaggen of punten die extra aandacht vragen
"""

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text
