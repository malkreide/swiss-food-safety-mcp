[🇬🇧 English Version](README.md)

# swiss-food-safety-mcp

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Lizenz](https://img.shields.io/badge/lizenz-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Keine Authentifizierung](https://img.shields.io/badge/auth-keine%20erforderlich-brightgreen)
![CI](https://github.com/malkreide/swiss-food-safety-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server für offene Daten des Bundesamts für Lebensmittelsicherheit und Veterinärwesen (BLV) — keine Authentifizierung erforderlich.

## Übersicht

`swiss-food-safety-mcp` verbindet KI-Modelle mit den offiziellen Open-Data-Quellen des Bundesamts für Lebensmittelsicherheit und Veterinärwesen (BLV). Der Server stellt 11 Werkzeuge bereit, die Lebensmittelrückrufe, Tierseuchenüberwachung, Lebensmittelkontrollergebnisse, Antibiotikaeinsatz in der Veterinärmedizin, Ernährungserhebungen bei Kindern sowie das Pflanzenschutzmittelverzeichnis abdecken.

Alle Daten stammen aus offiziellen Schweizer Bundesquellen (opendata.swiss, lindas.admin.ch, news.admin.ch). Es sind keine API-Schlüssel oder Authentifizierung erforderlich.

Dieser Server folgt der **No-Auth-First**-Philosophie und ist Teil eines MCP-Server-Portfolios für den öffentlichen Sektor der Schweiz.

## Funktionen

- 🚨 **Öffentliche Warnungen & Rückrufe** — Aktueller RSS-Feed mit BLV-Produktrückrufen und Gesundheitswarnungen
- 🐄 **Tierseuchenüberwachung** — Meldepflichtige Tierseuchen seit 1991 (InfoSM) via SPARQL + CSV
- 🐦 **Vogelgrippe-Monitoring** — Wildvogel-Überwachungsdaten mit Geodaten
- 🥩 **Lebensmittelkontrollergebnisse** — Kantonale Inspektionsergebnisse und Beanstandungsquoten
- 💊 **Antibiotikaeinsatz Veterinär** — ISABV-Daten zum Antibiotikaeinsatz in der Tiermedizin
- 🧒 **Kinderernährungserhebung** — Nationale Ernährungsstudie menuCH-Kids
- 🌿 **Pflanzenschutzmittelverzeichnis** — Bewilligte Produkte und Wirkstoffe der Schweiz
- 📊 **Datensatz-Entdeckung** — Alle 28 BLV-Datensätze auf opendata.swiss via CKAN-API
- 🔗 **Dualer Transport** — stdio (Claude Desktop) + Streamable HTTP (Cloud/Render.com)
- 🗣️ **Zweisprachig** — Deutsch als Primärdokumentation, Englisch sekundär

## Voraussetzungen

- Python 3.11+
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

### Weitere MCP-Clients (Cursor, Windsurf, VS Code + Continue)

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

Für Render.com als Startbefehl eintragen:

```
swiss-food-safety-mcp --http
```

## Verfügbare Werkzeuge

| Werkzeug | Beschreibung | Datenquelle |
|---|---|---|
| `blv_get_public_warnings` | Aktuelle Lebensmittelrückrufe & Warnungen | news.admin.ch RSS |
| `blv_list_datasets` | Alle 28 BLV-Datensätze durchsuchen | opendata.swiss CKAN |
| `blv_get_dataset_info` | Datensatz-Details & Ressourcen-URLs | opendata.swiss CKAN |
| `blv_search_animal_diseases` | Meldepflichtige Tierseuchen seit 1991 | SPARQL / CSV-Fallback |
| `blv_get_animal_health_stats` | Jährliche Tiergesundheitsstatistiken | opendata.swiss CSV/JSON |
| `blv_get_food_control_results` | Kantonale Lebensmittelkontrollergebnisse | opendata.swiss CSV |
| `blv_get_antibiotic_usage_vet` | Veterinärer Antibiotikaeinsatz (ISABV) | opendata.swiss CSV |
| `blv_get_avian_influenza` | Vogelgrippe-Überwachung Wildvögel | opendata.swiss JSON/KML |
| `blv_get_nutrition_data_children` | Kinderernährungserhebung (menuCH-Kids) | opendata.swiss CSV |
| `blv_search_pesticide_products` | Schweizer Pflanzenschutzmittelverzeichnis | opendata.swiss XML |
| `blv_get_meat_inspection_stats` | Schlachttier-Inspektionsstatistiken | opendata.swiss CSV/JSON |

## Beispielanfragen

```
"Welche Lebensmittelwarnungen hat das BLV aktuell?"
→ blv_get_public_warnings()

"Gibt es aktuell Tierseuchen in Zürich?"
→ blv_search_animal_diseases(canton="ZH", year_from=2024)

"Wie ist die Vogelgrippe-Situation in der Schweiz 2024?"
→ blv_get_avian_influenza(year=2024)

"Was essen Schweizer Kinder wirklich?"
→ blv_get_nutrition_data_children()

"Welche Pflanzenschutzmittel mit Kupfer sind in der Schweiz zugelassen?"
→ blv_search_pesticide_products(active_ingredient="Kupfer")
```

## Synergien mit verwandten MCP-Servern

| Kombination | Anwendungsfall |
|---|---|
| `swiss-food-safety-mcp` + `zurich-opendata-mcp` | Georeferenzierte Tierseuchenrisiken in Schulhausnähe |
| `swiss-food-safety-mcp` + `fedlex-mcp` | Rückrufe mit Lebensmittelgesetz verknüpfen |
| `swiss-food-safety-mcp` + `swiss-statistics-mcp` | Ernährungsdaten × Sozioökonomie nach Schulkreis |
| `swiss-food-safety-mcp` + `global-education-mcp` | Schweizer Kinderernährung vs. OECD-Benchmarks |

## Projektstruktur

```
swiss-food-safety-mcp/
├── src/
│   └── swiss_food_safety_mcp/
│       ├── __init__.py        # Paket-Metadaten
│       └── server.py          # Alle Werkzeuge, Ressourcen, Prompts
├── tests/
│   ├── __init__.py
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
| [lindas.admin.ch/sparql](https://lindas.admin.ch/sparql) | Schweizer Linked Data SPARQL-Endpunkt | RDF/SPARQL |
| [news.admin.ch RSS](https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079) | BLV-Warnungen & Rückrufe | RSS/XML |
| [blv.admin.ch](https://www.blv.admin.ch) | BLV-Website (DE/FR/IT/EN) | HTML |

Alle Daten sind Open Government Data (OGD) unter Creative Commons mit Quellenangabepflicht.

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Lizenz

MIT-Lizenz — siehe [LICENSE](LICENSE)

## Autor

malkreide · [GitHub](https://github.com/malkreide)

---

*Teil eines MCP-Server-Portfolios für den öffentlichen Sektor der Schweiz. Modell-agnostisch: funktioniert mit Claude, GPT, Ollama und jedem MCP-kompatiblen Client.*
