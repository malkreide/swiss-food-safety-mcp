# swiss-food-safety-mcp

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Keine Authentifizierung](https://img.shields.io/badge/auth-keine%20erforderlich-brightgreen)

> MCP-Server für Open Data des Bundesamts für Lebensmittelsicherheit und Veterinärwesen (BLV) — keine Authentifizierung erforderlich.

[🇬🇧 English Version](README.md)

## Übersicht

`swiss-food-safety-mcp` verbindet KI-Modelle mit den offiziellen Open-Data-Quellen des Bundesamts für Lebensmittelsicherheit und Veterinärwesen (BLV). Er bietet 11 Tools für Lebensmittelrückrufe, Tierseuchenüberwachung, Lebensmittelkontrolle, Antibiotikaverbrauch in der Veterinärmedizin, Ernährungserhebungen bei Kindern und das Pflanzenschutzmittelverzeichnis.

Alle Daten stammen aus offiziellen Schweizer Bundesquellen (opendata.swiss, lindas.admin.ch, news.admin.ch). Es sind keine API-Keys oder Zugangsdaten erforderlich.

Dieser Server folgt der **No-Auth-First-Philosophie** und ist Teil eines MCP-Server-Portfolios für den öffentlichen Sektor der Schweiz.

## Anwendungsfälle nach Kontext

### 🏫 Schulen & Schulamt
- **Schulkantinen-Sicherheit**: Automatisches Monitoring aktueller Rückrufe für Kantinen-Verantwortliche
- **Ernährungsbildung**: Echtzeitdaten zur Ernährung von Schweizer Kindern (menuCH-Kids) für den Unterricht
- **Schulausflüge Bauernhöfe**: Risikobeurteilung bei aktiven Tierseuchen in der Zielregion
- **Beschaffung**: Pflanzenschutzmittelrückstände in Lebensmitteln für nachhaltige Beschaffungsstandards

### 🏛️ Stadtverwaltung
- **Krisenfrüherkennung**: Push-Alerts bei Rückrufen, die städtische Einrichtungen betreffen
- **Compliance**: Verknüpfung von Kontrollergebnissen mit Massnahmenempfehlungen
- **Jahresberichte**: Automatische Integration von BLV-Statistiken

### 🤖 KI-Fachgruppe
- **Pilot-Demo**: KI-Zugriff auf föderale Gesundheitsdaten ohne DSGVO-Risiko (alles Open Data)
- **Demo-Frage**: *«Welche Tierseuchen gab es 2024 in Zürich?»* → Antwort in Sekunden

### 🏠 Privat
- **Produktrückrufe**: *«Ist mein Joghurt betroffen?»* — Live-Abfrage gegen aktuelle Warnungen
- **Reisen mit Haustieren**: Einreisebestimmungen und Tiergesundheitslage
- **Ernährung**: Evidenzbasierte Schweizer Empfehlungen nach Altersgruppe

## Voraussetzungen

- Python 3.11 oder neuer
- `uv` oder `uvx` (empfohlen) — [uv installieren](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

### Mit uvx (empfohlen — keine Installation nötig)

```bash
uvx swiss-food-safety-mcp
```

### Mit uv

```bash
uv tool install swiss-food-safety-mcp
swiss-food-safety-mcp
```

### Aus dem Quellcode

```bash
git clone https://github.com/malkreide/swiss-food-safety-mcp
cd swiss-food-safety-mcp
uv sync
uv run swiss-food-safety-mcp
```

## Verwendung / Schnellstart

### Claude Desktop

In `claude_desktop_config.json` eintragen:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "swiss-food-safety": {
      "command": "uvx",
      "args": ["swiss-food-safety-mcp"]
    }
  }
}
```

### Weitere MCP-Clients (Cursor, Windsurf, VS Code + Continue, LibreChat/Cline)

```json
{
  "mcpServers": {
    "swiss-food-safety": {
      "command": "uvx",
      "args": ["swiss-food-safety-mcp"]
    }
  }
}
```

### Cloud-Deployment (Streamable HTTP)

```bash
swiss-food-safety-mcp --http
# Server läuft auf Port 8002
```

## Verfügbare Tools

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `blv_get_public_warnings` | Aktuelle Lebensmittelwarnungen & Rückrufe | news.admin.ch RSS |
| `blv_list_datasets` | Alle 28 BLV Open-Data-Datensätze durchsuchen | opendata.swiss CKAN |
| `blv_get_dataset_info` | Datensatz-Details & Ressource-URLs | opendata.swiss CKAN |
| `blv_search_animal_diseases` | Meldepflichtige Tierseuchen seit 1991 | SPARQL / CSV |
| `blv_get_animal_health_stats` | Jährliche Tiergesundheitsstatistik | opendata.swiss CSV/JSON |
| `blv_get_food_control_results` | Kantonale Lebensmittelkontroll-Ergebnisse | opendata.swiss CSV |
| `blv_get_antibiotic_usage_vet` | Antibiotikaverbrauch Veterinärmedizin (ISABV) | opendata.swiss CSV |
| `blv_get_avian_influenza` | Vogelgrippe-Überwachung Wildvögel | opendata.swiss JSON/KML |
| `blv_get_nutrition_data_children` | Ernährungserhebung Kinder & Jugendliche (menuCH-Kids) | opendata.swiss CSV |
| `blv_search_pesticide_products` | Schweizer Pflanzenschutzmittelverzeichnis | opendata.swiss XML |
| `blv_get_meat_inspection_stats` | Fleischkontrollstatistik Schlachthöfe | opendata.swiss CSV/JSON |

## Beispiel-Anfragen

```
"Welche Lebensmittelwarnungen hat das BLV aktuell?"
→ blv_get_public_warnings()

"Gibt es aktuell Tierseuchen im Kanton Zürich?"
→ blv_search_animal_diseases(canton="ZH", year_from=2024)

"Wie ernähren sich Schweizer Kinder im Vergleich zu den Empfehlungen?"
→ blv_get_nutrition_data_children()

"Welche Kantone hatten 2023 die meisten Lebensmittelbeanstandungen?"
→ blv_get_food_control_results(year=2023)

"Ist Glyphosat in der Schweiz noch zugelassen?"
→ blv_search_pesticide_products(active_ingredient="Glyphosat")
```

## Synergien mit anderen MCP-Servern

| Kombination | Anwendungsfall |
|---|---|
| + `zurich-opendata-mcp` | Tierseuchen-Risikokarte für Schulstandorte (Geodaten) |
| + `fedlex-mcp` | Rückrufe verknüpft mit Lebensmittelgesetz-Artikeln |
| + `swiss-statistics-mcp` | Ernährungsdaten × Soziodemographie nach Schulkreis |
| + `global-education-mcp` | Schweizer Kinderernährung vs. OECD-Benchmarks |
| + `srgssr-mcp` | Medienresonanz auf Lebensmittelskandale (Kommunikationssteuerung) |

## Projektstruktur

```
swiss-food-safety-mcp/
├── src/
│   └── swiss_food_safety_mcp/
│       ├── __init__.py
│       └── server.py          # Alle Tools, Ressourcen, Prompts
├── tests/
│   └── test_server.py         # Unit-Tests (keine Live-API-Aufrufe)
├── .github/
│   └── workflows/
│       └── ci.yml             # Python 3.11–3.13 Matrix
├── pyproject.toml             # hatchling Build, uv-kompatibel
├── README.md                  # Englisch (primär)
├── README.de.md               # Deutsch (sekundär)
├── LICENSE                    # MIT
└── CHANGELOG.md
```

## Datenquellen

| Quelle | Beschreibung | Format |
|---|---|---|
| [opendata.swiss/BLV](https://opendata.swiss/de/organization/bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv) | 28 offene Datensätze | CSV, JSON, Parquet, SPARQL, XML |
| [lindas.admin.ch/sparql](https://lindas.admin.ch/sparql) | Schweizer Linked Data SPARQL-Endpoint | RDF/SPARQL |
| [news.admin.ch RSS](https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079) | BLV Warnungen & Rückrufe | RSS/XML |

Alle Daten sind Open Government Data (OGD) unter Creative Commons mit Quellenangabepflicht.

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Lizenz

MIT-Lizenz — siehe [LICENSE](LICENSE)

## Autor

malkreide · [GitHub](https://github.com/malkreide)

---

*Teil eines MCP-Server-Portfolios für den öffentlichen Sektor der Schweiz. Modell-agnostisch: funktioniert mit Claude, GPT, Ollama und jedem MCP-kompatiblen Client.*
