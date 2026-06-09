import anthropic
from config import VERGADER_TYPES


SYSTEM_PROMPT = """Je bent een ervaren bestuurssecretaris die vergaderingen voorbereidt voor Martin Dekker,
een drukbezette bestuurder. Je schrijft altijd in het Nederlands. Je bent bondig maar volledig.
Je output is direct bruikbaar — geen inleidingen, geen herhaling van de opdracht.

OVER MARTIN'S STIJL (belangrijk voor spreekteksten):
- Direct en no-nonsense. Geen omhaal, geen "goedemorgen allemaal, we beginnen met..."
- Komt snel ter zake. Eerste zin = de kern.
- Concreet en zakelijk. Korte zinnen.
- Geen geleerde of gewichtige woorden — gewone, krachtige taal.
- Soms een lichte kwinkslag of een scherpe observatie.
- Sluit af met een duidelijke vraag of richting voor het gesprek."""


def analyseer_vergadering(
    api_key: str,
    vergader_type: str,
    agenda_tekst: str,
    notulen_tekst: str = "",
    rbt_tekst: str = "",
) -> str:
    config = VERGADER_TYPES[vergader_type]
    is_voorzitter = config.get("is_voorzitter", False)

    notulen_sectie = ""
    if notulen_tekst.strip():
        notulen_sectie = f"""
## Vorige notulen (ter context)
{notulen_tekst}

---
"""

    # Bij LMT: optionele RBT-context voor de mededeling
    rbt_sectie = ""
    rbt_instructie = ""
    if vergader_type == "LMT" and rbt_tekst.strip():
        rbt_sectie = f"""
## RBT-stukken (voor de mededeling tijdens LMT)
{rbt_tekst}

---
"""
        rbt_instructie = """

⚠️ EXTRA INSTRUCTIE — MEDEDELING RBT:
Martin geeft tijdens het LMT bij de mededelingen altijd een korte stand van zaken van wat er in het RBT
is besproken. Maak hiervoor een aparte sectie HELEMAAL BOVENAAN de briefing, vóór de gewone agendapunten:

### 📢 Mededeling — Stand van zaken RBT

**🎤 Spreektekst (voor de mededelingen):**
> [5-8 zinnen in Martins directe stijl. Eerste zin direct ter zake: "Even kort de stand van zaken vanuit
> het RBT." Dan per onderwerp 1-2 zinnen: wat speelt er, waar staan we, wat betekent het voor ons.
> Sluit af met waar input of vervolg op verwacht wordt. Geen omhaal, geen geleerde woorden.]

**Behandelde onderwerpen (overzicht voor jezelf):**
- [Korte bullet per RBT-onderwerp — een paar woorden, geen zinnen]

**Eventuele aandachtspunten voor HCC:**
- [Punten waar HCC iets mee moet of waar Martin alert op moet zijn]

---
"""

    # Spreektekst sectie alleen voor voorzitters
    spreektekst_instructie = ""
    spreektekst_template = ""
    if is_voorzitter:
        spreektekst_instructie = """

⚠️ EXTRA INSTRUCTIE — SPREEKTEKST:
Omdat Martin dit agendapunt zelf gaat openen als voorzitter, schrijf je voor ELK inhoudelijk agendapunt
een korte SPREEKTEKST (3-6 zinnen) die hij letterlijk kan voorlezen of als basis kan gebruiken.

Eisen aan de spreektekst:
- Eerste zin = direct de kern (geen inleidingen)
- Geen herhaling van wat al in de stukken staat — wel duiding: waarom dit nu, wat is het verhaal
- Eindigt met een concrete vraag of richting voor de bespreking
- Tone of voice: direct, zakelijk, kort, geen geleerd woordgebruik
- Lengte: 3-6 zinnen, zo'n 40-80 woorden — alsof Martin het zelf zou zeggen
"""
        spreektekst_template = """

**🎤 Spreektekst (opening door Martin):**
> [3-6 zinnen in Martins directe stijl waarmee hij dit agendapunt opent — direct ter zake, eindigend met een concrete vraag of richting]
"""

    user_prompt = f"""
{notulen_sectie}
{rbt_sectie}
## Vergaderstukken / agenda
{agenda_tekst}

---

**Jouw taak:**
Bereid Martin voor op deze vergadering. Hij is {config['rol']}.

{config['context']}
{rbt_instructie}
{spreektekst_instructie}

⚠️ KRITISCH — BESLUITVORMING:
Maak GLASHELDER waar besluitvorming wordt gevraagd. Bij agendapunten van het type "Besluit":
- Markeer ze prominent met "🔴 **BESLUIT VEREIST**" bovenaan
- Beschrijf in één duidelijke zin WAT er precies besloten moet worden
- Vermeld als er alternatieven zijn waar uit gekozen kan worden

---

Geef per agendapunt de volgende analyse. Behandel procedurele punten zoals "opening", "mededelingen" en
"rondvraag" zeer kort (max 2 regels). Behandel inhoudelijke punten uitgebreid.

### [Nummer]. [Naam agendapunt]

**Type:** Informatie / Besluit / Ter kennisname / Discussie

[INDIEN type = "Besluit", voeg dit blok DIRECT toe:]
🔴 **BESLUIT VEREIST**
**Wat moet er besloten worden:** [één heldere zin]
**Alternatieven:** [indien aanwezig: A vs B vs C, anders weglaten]
{spreektekst_template}

**Samenvatting (5-10 regels):**
Wat staat er in de stukken? Wat is de kern?

**Vragen voor Martin:**
- [2-4 concrete, scherpe vragen die Martin kan stellen vanuit zijn rol als {config['rol']}]

**Aandachtspunten / acties:**
- [Wat moet Martin weten, beslissen, of doen naar aanleiding van dit punt?]

---

Sluit af met een **📋 Totaaloverzicht** met daarin:

**🔴 Te nemen besluiten** *(alleen agendapunten met type Besluit)*
- [Punt nr] [Onderwerp] — [wat besloten moet worden]

**✅ Actiepunten voor Martin persoonlijk**
- [Wat moet hij voorbereiden, meebrengen, vooraf afstemmen, etc.]

**⚠️ Aandachtspunten / rode vlaggen**
- [Punten die extra alertheid vragen]
"""

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text
