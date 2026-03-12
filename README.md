# swiss-food-safety-mcp

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)
![CI](https://github.com/malkreide/swiss-food-safety-mcp/actions/workflows/ci.yml/badge.svg)

> MCP Server for Swiss Federal Food Safety and Veterinary Office (BLV) open data — no authentication required.

[🇩🇪 Deutsche Version](README.de.md)

## Overview

`swiss-food-safety-mcp` connects AI models to the official open data of Switzerland's Federal Food Safety and Veterinary Office (BLV / *Bundesamt für Lebensmittelsicherheit und Veterinärwesen*). It provides 11 tools covering food recalls, animal disease surveillance, food control results, antibiotic usage in veterinary medicine, nutrition surveys for children, and the pesticide register.

All data comes from official Swiss federal sources (opendata.swiss, lindas.admin.ch, news.admin.ch). No API keys or authentication are required.

This server follows the **No-Auth-First** philosophy and is part of a Swiss public sector MCP portfolio.

## Features

- 🚨 **Public warnings & recalls** — Live RSS feed of BLV product recalls and health warnings
- 🐄 **Animal disease surveillance** — Notifiable animal diseases since 1991 (InfoSM) via SPARQL + CSV
- 🐦 **Avian influenza monitoring** — Wild bird surveillance data with geodata
- 🥩 **Food control results** — Cantonal food inspection results and violation rates
- 💊 **Antibiotic usage veterinary** — ISABV data on antibiotic use in animal medicine
- 🧒 **Children's nutrition survey** — menuCH-Kids national nutritional survey data
- 🌿 **Pesticide register** — Swiss approved pesticide products and active ingredients
- 📊 **Dataset discovery** — Browse all 28 BLV datasets on opendata.swiss via CKAN API
- 🔗 **Dual transport** — stdio (Claude Desktop) + Streamable HTTP (cloud/Render.com)
- 🗣️ **Bilingual** — German-first documentation, English secondary

## Prerequisites

- Python 3.11+
- `uv` or `uvx` (recommended) — [install uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

### Using uvx (recommended — no install needed)

```bash
uvx swiss-food-safety-mcp
```

### Using uv

```bash
uv tool install swiss-food-safety-mcp
swiss-food-safety-mcp
```

### From source

```bash
git clone https://github.com/malkreide/swiss-food-safety-mcp
cd swiss-food-safety-mcp
uv sync
uv run swiss-food-safety-mcp
```

## Usage / Quickstart

### Claude Desktop

Add to `claude_desktop_config.json`:

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

### Other MCP Clients (Cursor, Windsurf, VS Code + Continue)

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

### Cloud deployment (Streamable HTTP)

```bash
swiss-food-safety-mcp --http
# Server runs on port 8002
```

For Render.com, set the start command to:

```
swiss-food-safety-mcp --http
```

## Available Tools

| Tool | Description | Data Source |
|---|---|---|
| `blv_get_public_warnings` | Current food recalls & health warnings | news.admin.ch RSS |
| `blv_list_datasets` | Browse all 28 BLV open datasets | opendata.swiss CKAN |
| `blv_get_dataset_info` | Dataset details & resource URLs | opendata.swiss CKAN |
| `blv_search_animal_diseases` | Notifiable animal diseases since 1991 | SPARQL / CSV fallback |
| `blv_get_animal_health_stats` | Annual animal health statistics | opendata.swiss CSV/JSON |
| `blv_get_food_control_results` | Cantonal food inspection results | opendata.swiss CSV |
| `blv_get_antibiotic_usage_vet` | Veterinary antibiotic usage (ISABV) | opendata.swiss CSV |
| `blv_get_avian_influenza` | Wild bird avian influenza surveillance | opendata.swiss JSON/KML |
| `blv_get_nutrition_data_children` | Children's nutrition survey (menuCH-Kids) | opendata.swiss CSV |
| `blv_search_pesticide_products` | Swiss approved pesticide register | opendata.swiss XML |
| `blv_get_meat_inspection_stats` | Slaughterhouse inspection statistics | opendata.swiss CSV/JSON |

## Example Queries

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

## Synergies with Related MCP Servers

| Combination | Use Case |
|---|---|
| `swiss-food-safety-mcp` + `zurich-opendata-mcp` | Geo-mapped animal disease risk near school locations |
| `swiss-food-safety-mcp` + `fedlex-mcp` | Link recalls to food law (Lebensmittelgesetz) |
| `swiss-food-safety-mcp` + `swiss-statistics-mcp` | Nutrition data × socioeconomics by school district |
| `swiss-food-safety-mcp` + `global-education-mcp` | Swiss children's nutrition vs. OECD benchmarks |

## Project Structure

```
swiss-food-safety-mcp/
├── src/
│   └── swiss_food_safety_mcp/
│       ├── __init__.py        # Package metadata
│       └── server.py          # All tools, resources, prompts
├── tests/
│   ├── __init__.py
│   └── test_server.py         # Unit tests (no live API calls)
├── .github/
│   └── workflows/
│       └── ci.yml             # Python 3.11–3.13 matrix
├── pyproject.toml             # hatchling build, uv-compatible
├── README.md                  # English (primary)
├── README.de.md               # Deutsch (secondary)
├── LICENSE                    # MIT
└── CHANGELOG.md
```

## Data Sources

| Source | Description | Format |
|---|---|---|
| [opendata.swiss/BLV](https://opendata.swiss/de/organization/bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv) | 28 open datasets | CSV, JSON, Parquet, SPARQL, XML |
| [lindas.admin.ch/sparql](https://lindas.admin.ch/sparql) | Swiss linked data SPARQL endpoint | RDF/SPARQL |
| [news.admin.ch RSS](https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079) | BLV public warnings & recalls | RSS/XML |
| [blv.admin.ch](https://www.blv.admin.ch) | BLV website (DE/FR/IT/EN) | HTML |

All data is open government data (OGD) under Creative Commons with attribution requirement.

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## License

MIT License — see [LICENSE](LICENSE)

## Author

malkreide · [GitHub](https://github.com/malkreide)

---

*Part of a Swiss public sector MCP server portfolio. Model-agnostic: works with Claude, GPT, Ollama, and any MCP-compatible client.*
