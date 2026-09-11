"""
Analyse van vergaderstukken met Claude.

Twee publieke functies:
- analyseer_vergadering(...)  : streamt de briefing als tekstfragmenten
- stel_vervolgvraag(...)      : streamt een antwoord op een vervolgvraag over dezelfde stukken

De vergaderstukken gaan in het system-blok met prompt caching, zodat vervolgvragen
binnen enkele minuten na de analyse goedkoper en sneller zijn.
"""

from typing import Iterator, Optional

import anthropic

from config import VERGADER_TYPES, MODEL, MAX_OUTPUT_TOKENS


SYSTEM_PROMPT = """Je bent een ervaren bestuurssecretaris die vergaderingen voorbereidt voor Martin Dekker,
een drukbezette bestuurder en toezichthouder. Je schrijft altijd in het Nederlands. Je bent bondig maar volledig
en je output is direct bruikbaar: geen inleiding, geen herhaling van de opdracht, geen afsluitende beleefdheden.

WERKWIJZE
- Lees alle stukken volledig voordat je begint. Elk bestand begint met een kop "===== ... BESTAND n: naam =====" en
  bevat markeringen zoals [Pagina 3], [Slide 2] of [Werkblad: X]. Gebruik die om bronnen te noemen.
- Verwijs bij kernpunten, cijfers en besluiten naar de bron, kort tussen haakjes: (begroting.pdf, p. 4).
- Neem cijfers letterlijk over uit de stukken. Reken niets zelf uit tenzij je dat expliciet meldt.
- Als stukken elkaar tegenspreken (bijvoorbeeld verschillende cijfers voor hetzelfde), benoem dat expliciet.
- Als iets niet uit de stukken blijkt, zeg dat dan. Vul geen gaten met aannames.

REALITY FILTER (verplicht)
- Presenteer nooit gespeculeerde inhoud als feit.
- Markeer met [Niet geverifieerd] wat niet uit de stukken blijkt, met [Afleiding] wat je zelf concludeert
  en met [Schatting] wat een ruwe inschatting is.
- Label absolute claims uit de stukken ("garandeert", "voorkomt") als ze niet onderbouwd zijn.

STIJL
- Direct en zakelijk. Korte zinnen. Gewone, krachtige taal; geen jargon en geen gewichtige woorden.
- Geen emoji's. Geen em dashes (gebruik een komma, punt of dubbele punt).
- Gebruik Markdown zoals in de gevraagde structuur: koppen met ## en ###, bullets met -, en vet alleen voor labels.

MARTINS STIJL VOOR SPREEKTEKSTEN
- Eerste zin is de kern. Geen "goedemorgen allemaal, we beginnen met".
- Concreet, kort, soms een lichte kwinkslag of scherpe observatie.
- Sluit af met een duidelijke vraag of richting voor het gesprek.
"""


def _documenten_blok(agenda_tekst: str, notulen_tekst: str = "", rbt_tekst: str = "") -> str:
    delen = ["# VERGADERSTUKKEN\n\n" + (agenda_tekst.strip() or "(geen stukken aangeleverd)")]
    if notulen_tekst.strip():
        delen.append("# VORIGE NOTULEN (ter context)\n\n" + notulen_tekst.strip())
    if rbt_tekst.strip():
        delen.append("# RBT-STUKKEN (voor de mededeling tijdens het LMT)\n\n" + rbt_tekst.strip())
    return "\n\n\n".join(delen)


def bouw_opdracht(
    vergader_type: str,
    heeft_notulen: bool = False,
    heeft_rbt: bool = False,
    opmerkingen: str = "",
    vergaderdatum: str = "",
) -> str:
    """Bouw de opdracht (user-bericht) voor de analyse."""
    config = VERGADER_TYPES[vergader_type]
    is_voorzitter = config.get("is_voorzitter", False)
    focus = "\n".join(f"- {v}" for v in config.get("vraag_focus", []))

    datum_regel = f"Datum van de vergadering: {vergaderdatum}.\n" if vergaderdatum else ""

    # --- Optionele blokken -------------------------------------------------
    rbt_blok = ""
    if vergader_type == "LMT" and heeft_rbt:
        rbt_blok = """
## Mededeling: stand van zaken RBT
Martin geeft tijdens het LMT bij de mededelingen een korte stand van zaken van het RBT. Zet deze sectie
HELEMAAL BOVENAAN, voor de inventaris.

**Spreektekst**
> 5 tot 8 zinnen in Martins stijl. Begin direct: "Even kort de stand van zaken vanuit het RBT." Dan per onderwerp
> 1 of 2 zinnen: wat speelt er, waar staan we, wat betekent het voor ons. Sluit af met waar input of vervolg op
> verwacht wordt.

**Behandelde onderwerpen** (voor jezelf, een paar woorden per bullet)
**Aandachtspunten voor HCC**
"""

    opmerkingen_blok = ""
    if opmerkingen.strip():
        opmerkingen_blok = f"""
## Op verzoek van Martin
Martin gaf zelf deze opmerkingen mee. Die wegen zwaar: werk ze nadrukkelijk uit, niet alleen noemen.
Bij onderwerpen waar hij extra aandacht voor wil: uitgebreidere analyse en scherpere vragen.
Bij mededelingen die hij wil doen: schrijf een spreektekst in zijn stijl.
Zet deze sectie direct na de inventaris (of na de RBT-mededeling als die er is).

Zijn opmerkingen:
\"\"\"
{opmerkingen.strip()}
\"\"\"
"""

    spreektekst_blok = ""
    if is_voorzitter:
        spreektekst_blok = """
**Spreektekst**
> 3 tot 6 zinnen (40 tot 80 woorden) waarmee Martin dit punt als voorzitter opent. Eerste zin is de kern.
> Geen herhaling van de stukken, wel duiding: waarom dit nu, wat is het verhaal. Eindig met een concrete vraag
> of richting voor de bespreking.
"""

    notulen_blok = ""
    if heeft_notulen:
        notulen_blok = """
## Openstaande acties uit de vorige notulen
Loop de actie- en besluitenlijst uit de vorige notulen langs. Per actie: wat was afgesproken, wie, en of het
in de huidige stukken terugkomt (afgerond, loopt, niet terug te vinden [Niet geverifieerd]).
Alleen opnemen als er vorige notulen zijn aangeleverd.
"""

    return f"""Bereid Martin voor op deze vergadering. Hij is {config['rol']}.
{datum_regel}
{config['context'].strip()}

Waar Martin vanuit zijn rol op let:
{focus}

Lever de briefing in precies deze structuur en volgorde:
{rbt_blok}
## Inventaris
Kort en feitelijk, zodat niets wordt gemist:
- **Agendapunten** die je in de stukken vindt, genummerd zoals in de agenda.
- **Stukken per agendapunt**: welk bestand (en pagina's) hoort bij welk punt.
- **Niet gekoppeld**: stukken die bij geen agendapunt horen, en agendapunten zonder onderliggend stuk.
- **Niet leesbaar of ontbrekend**: bestanden zonder tekst, verwijzingen naar bijlagen die niet zijn aangeleverd.
{opmerkingen_blok}
## Agendapunten

Behandel procedurele punten (opening, vaststellen agenda, mededelingen, rondvraag, sluiting) in maximaal 2 regels.
Behandel inhoudelijke punten volledig, per punt exact zo:

### [nummer]. [titel zoals in de agenda]
Type: Besluit | Bespreking | Informatie | Ter kennisname
Bron: [bestand(en), pagina's]

[Alleen bij type Besluit, direct onder Bron:]
BESLUIT VEREIST: [in één heldere zin wat er precies besloten moet worden]
Alternatieven: [A, B, C als die er zijn; anders deze regel weglaten]
{spreektekst_blok}
**Samenvatting**
5 tot 10 regels lopende tekst. Wat staat er, wat is de kern, wat valt op, wat wordt van Martin verwacht.

**Cijfers en feiten die ertoe doen**
- Alleen bij punten met cijfers, data of harde afspraken: de 3 tot 6 belangrijkste, letterlijk uit de stukken, met bron.
- Deze kop weglaten als er niets relevants is.

**Vragen voor Martin**
- 2 tot 4 scherpe, concrete vragen die hij letterlijk kan stellen, vanuit zijn rol.

**Aandachtspunten en acties**
- Wat moet Martin weten, beslissen of doen. Risico's en rode vlaggen hier benoemen.
{notulen_blok}
## Totaaloverzicht

**Te nemen besluiten**
- [nr] [onderwerp]: [wat besloten moet worden]. Schrijf "Geen" als er geen besluitpunten zijn.

**Acties voor Martin persoonlijk**
- Wat hij moet voorbereiden, meenemen of vooraf afstemmen.

**Rode vlaggen**
- Punten die extra alertheid vragen. Schrijf "Geen" als die er niet zijn.

**Wat ontbreekt of is onduidelijk**
- Informatie die je zou verwachten maar niet in de stukken zit, en tegenstrijdigheden tussen stukken.
  Markeer met [Niet geverifieerd] waar van toepassing.
"""


def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=600.0)


def _system_blokken(documenten: str) -> list:
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": "Hieronder staan de aangeleverde stukken.\n\n" + documenten,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def analyseer_vergadering(
    api_key: str,
    vergader_type: str,
    agenda_tekst: str,
    notulen_tekst: str = "",
    rbt_tekst: str = "",
    opmerkingen: str = "",
    vergaderdatum: str = "",
    model: Optional[str] = None,
) -> Iterator[str]:
    """Streamt de briefing als tekstfragmenten. Gebruik ''.join(...) voor het geheel."""
    documenten = _documenten_blok(agenda_tekst, notulen_tekst, rbt_tekst)
    opdracht = bouw_opdracht(
        vergader_type=vergader_type,
        heeft_notulen=bool(notulen_tekst.strip()),
        heeft_rbt=bool(rbt_tekst.strip()) and vergader_type == "LMT",
        opmerkingen=opmerkingen,
        vergaderdatum=vergaderdatum,
    )

    client = _client(api_key)
    with client.messages.stream(
        model=model or MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=_system_blokken(documenten),
        messages=[{"role": "user", "content": opdracht}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def analyseer_vergadering_volledig(*args, **kwargs) -> str:
    """Zelfde als analyseer_vergadering, maar geeft de complete tekst terug."""
    return "".join(analyseer_vergadering(*args, **kwargs))


def stel_vervolgvraag(
    api_key: str,
    agenda_tekst: str,
    briefing: str,
    geschiedenis: list,
    vraag: str,
    notulen_tekst: str = "",
    rbt_tekst: str = "",
    model: Optional[str] = None,
) -> Iterator[str]:
    """
    Streamt een antwoord op een vervolgvraag over de stukken en de briefing.

    geschiedenis: lijst van {"role": "user"|"assistant", "content": str} met eerdere vervolgvragen
    en antwoorden (zonder de huidige vraag).
    """
    documenten = _documenten_blok(agenda_tekst, notulen_tekst, rbt_tekst)

    eerste_bericht = f"""Hieronder de briefing die je eerder over deze stukken hebt gemaakt. Martin stelt daarna
vervolgvragen. Antwoord kort en concreet, met bronverwijzing (bestand, pagina) waar dat kan. Zeg het eerlijk
als iets niet in de stukken staat. Zelfde stijl en reality filter als in de briefing.

# EERDERE BRIEFING
{briefing}
"""

    messages = [{"role": "user", "content": eerste_bericht}, {"role": "assistant", "content": "Begrepen. Stel je vraag."}]
    for m in geschiedenis:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": vraag})

    client = _client(api_key)
    with client.messages.stream(
        model=model or MODEL,
        max_tokens=4000,
        system=_system_blokken(documenten),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
