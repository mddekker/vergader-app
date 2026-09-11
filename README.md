# Vergadervoorbereiding

Streamlit-app die vergaderstukken (PDF, Word, PowerPoint, Excel, e-mail) leest en per agendapunt een
briefing maakt, afgestemd op de rol van Martin in het overleg (RBT, LMT, RvC iPractice, RvC Sportbedrijf
Deventer, Stuurgroep DigiV, Portfolioboard HCC).

## Wat de app doet

1. Leest alle geüploade stukken en toont per bestand het aantal pagina's, de hoeveelheid tekst en een
   waarschuwing bij scans zonder leesbare tekst.
2. Maakt met Claude een briefing: inventaris van agendapunten en stukken, per agendapunt het type, de bron,
   een besluitblok waar een besluit wordt gevraagd, spreektekst (bij voorzittersrollen), samenvatting, cijfers
   met bronverwijzing, vragen en aandachtspunten. Sluit af met een totaaloverzicht en een lijst van wat
   ontbreekt of onduidelijk is.
3. Biedt een Word- en tekstexport en de mogelijkheid om vervolgvragen te stellen over dezelfde stukken.
4. Bewaart elke briefing (met vervolgvragen) in een archief in Supabase, terug te vinden op elk apparaat.

## Bestanden

| Bestand | Functie |
|---|---|
| `app.py` | Interface (Streamlit) |
| `config.py` | Overlegtypen, rollen, model en limieten |
| `analyzer.py` | Prompt en aanroep van Claude (streaming, vervolgvragen, prompt caching) |
| `pdf_reader.py` | Documentlezer voor PDF, Word, PowerPoint, Excel, .eml en .msg |
| `word_exporter.py` | Word-export van de briefing |
| `archief.py` | Archief van briefings in Supabase |
| `.streamlit/config.toml` | Thema en serverinstellingen |

## Lokaal draaien

```
pip install -r requirements.txt
streamlit run app.py
```

Of dubbelklik op `start.bat` (Windows). De API key gaat in het zijpaneel of in `.streamlit/secrets.toml`:

```
ANTHROPIC_API_KEY = "sk-ant-..."
```

## Online (Streamlit Community Cloud)

De app draait vanaf de branch `master` van deze repo. Een `git push` is genoeg om een nieuwe versie live te
zetten. De API key staat in de Secrets van de app op share.streamlit.io.

## Archief (Supabase)

De briefings staan in de tabel `briefings` van het Supabase-project. In de secrets van de app horen:

```
SUPABASE_URL = "https://<project>.supabase.co"
SUPABASE_KEY = "<service_role key, te vinden onder Project Settings > API Keys>"
```

Zonder deze twee regels werkt de app gewoon, alleen zonder archief. De tabel is aangemaakt met:

```sql
create table if not exists public.briefings (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  vergader_type text not null,
  vergaderdatum date,
  titel text,
  briefing text not null,
  vervolg jsonb not null default '[]'::jsonb,
  bestanden jsonb not null default '[]'::jsonb
);
alter table public.briefings enable row level security;
```

RLS staat aan zonder policies: alleen de service_role key (server-side, in de secrets) kan erbij.

## Een overlegtype toevoegen

Voeg in `config.py` een blok toe aan `VERGADER_TYPES` met `label`, `rol`, `is_voorzitter`, `logo`, `context`
en `vraag_focus`. Zet het logo in `assets/`.
