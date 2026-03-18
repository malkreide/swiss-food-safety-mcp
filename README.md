> 🇨🇭 **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# swiss-food-safety-mcp

![Version](https://img.shields.io/badge/version-1.0.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Data Source](https://img.shields.io/badge/Data-opendata.swiss%20%2F%20BLV-red)](https://opendata.swiss/de/organization/bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv)
![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)
![CI](https://github.com/malkreide/swiss-food-safety-mcp/actions/workflows/ci.yml/badge.svg)

> MCP server connecting AI models to Swiss Federal Food Safety and Veterinary Office (BLV) open data — food recalls, animal disease surveillance, food control results, antibiotic usage, children's nutrition surveys and the pesticide register. No authentication required.

[🇩🇪 Deutsche Version](README.de.md)

---

## Overview

**swiss-food-safety-mcp** gives AI assistants like Claude direct access to official Swiss food safety and veterinary data from the Federal Food Safety and Veterinary Office (BLV / *Bundesamt für Lebensmittelsicherheit und Veterinärwesen*). It provides 11 tools covering food recalls, animal disease surveillance, food control results, antibiotic usage in veterinary medicine, nutrition surveys for children, and the pesticide register.

All data comes from official Swiss federal sources (opendata.swiss, lindas.admin.ch, news.admin.ch). No API keys or authentication are required.

This server follows the **No-Auth-First** philosophy and is part of a Swiss public sector MCP portfolio.

**Anchor demo query:** *"Are there any current BLV food warnings relevant to Zurich school canteens — and which notifiable animal diseases are currently reported in the canton?"*

---

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

---

## Prerequisites

- Python 3.11+
- `uv` or `uvx` (recommended) — [install uv](https://docs.astral.sh/uv/getting-started/installation/)

---

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

---

## Quickstart

Add to `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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

Try it immediately in Claude Desktop:

> *"Which BLV food warnings are currently active?"*  
> *"Are there any notifiable animal diseases reported in Zurich canton this year?"*

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

### Cloud Deployment (Streamable HTTP)

For use via **claude.ai in the browser** (e.g. on managed workstations without local software):

```bash
swiss-food-safety-mcp --http
# Server runs on port 8002
```

**Render.com (recommended):**
1. Push/fork the repository to GitHub
2. On [render.com](https://render.com): New Web Service → connect GitHub repo
3. Set the start command to: `swiss-food-safety-mcp --http`
4. In claude.ai under Settings → MCP Servers, add: `https://your-app.onrender.com/mcp`

> 💡 *"stdio for the developer laptop, Streamable HTTP for the browser."*

---

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

### Example Queries

| Query | Tool |
|---|---|
| *"Which BLV food warnings are currently active?"* | `blv_get_public_warnings` |
| *"Are there animal diseases in Zurich canton in 2024?"* | `blv_search_animal_diseases` |
| *"What is the avian influenza situation in Switzerland 2024?"* | `blv_get_avian_influenza` |
| *"What do Swiss children actually eat?"* | `blv_get_nutrition_data_children` |
| *"Which copper-based pesticides are approved in Switzerland?"* | `blv_search_pesticide_products` |

---

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────┐     ┌──────────────────────────────┐
│   Claude / AI   │────▶│   Swiss Food Safety MCP     │────▶│  Swiss Federal Open Data     │
│   (MCP Host)    │◀────│   (MCP Server)              │◀────│                              │
└─────────────────┘     │                             │     │  opendata.swiss (CKAN/CSV)   │
                        │  11 Tools · No Auth         │     │  lindas.admin.ch (SPARQL)    │
                        │  Stdio | Streamable HTTP    │     │  news.admin.ch (RSS/XML)     │
                        └─────────────────────────────┘     └──────────────────────────────┘
```

---

## Synergies with Related MCP Servers

| Combination | Use Case |
|---|---|
| `swiss-food-safety-mcp` + `zurich-opendata-mcp` | Geo-mapped animal disease risk near school locations |
| `swiss-food-safety-mcp` + `fedlex-mcp` | Link recalls to food law (Lebensmittelgesetz) |
| `swiss-food-safety-mcp` + `swiss-statistics-mcp` | Nutrition data × socioeconomics by school district |
| `swiss-food-safety-mcp` + `global-education-mcp` | Swiss children's nutrition vs. OECD benchmarks |

---

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
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                    # MIT
├── README.md                  # This file (English)
└── README.de.md               # German version
```

---

## Data Sources

| Source | Description | Format |
|---|---|---|
| [opendata.swiss/BLV](https://opendata.swiss/de/organization/bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv) | 28 open datasets | CSV, JSON, Parquet, SPARQL, XML |
| [lindas.admin.ch/sparql](https://lindas.admin.ch/sparql) | Swiss linked data SPARQL endpoint | RDF/SPARQL |
| [news.admin.ch RSS](https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079) | BLV public warnings & recalls | RSS/XML |
| [blv.admin.ch](https://www.blv.admin.ch) | BLV website (DE/FR/IT/EN) | HTML |

All data is open government data (OGD) under Creative Commons with attribution requirement.

---

## Known Limitations

- **SPARQL endpoint:** Automatic fallback to CSV if the lindas.admin.ch SPARQL endpoint is unavailable
- **RSS feed:** Limited to the most recent BLV publications; no historical archive
- **Pesticide register:** XML parsing may be slow for queries returning large result sets
- **CKAN datasets:** Opendata.swiss rate limits apply under heavy usage
- **Animal disease data:** Canton-level filtering depends on data completeness in the source

---

## Testing

```bash
# Unit tests (no API access required)
PYTHONPATH=src pytest tests/ -m "not live"

# All tests including live API checks
PYTHONPATH=src pytest tests/
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Author

Hayal Oezkan · [github.com/malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **Data:** [opendata.swiss / BLV](https://opendata.swiss/de/organization/bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv) – Federal Food Safety and Veterinary Office (BLV)
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Related:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) – MCP server for Zurich city open data
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
