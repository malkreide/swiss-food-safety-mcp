# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-03-12

### Added
- Initial release
- `blv_get_public_warnings` — Live BLV food recalls and health warnings via RSS
- `blv_list_datasets` — Browse all 28 BLV datasets on opendata.swiss via CKAN API
- `blv_get_dataset_info` — Dataset metadata and resource download URLs
- `blv_search_animal_diseases` — Notifiable animal diseases since 1991 (SPARQL + CSV fallback)
- `blv_get_animal_health_stats` — Annual Swiss animal health statistics (CSV/JSON)
- `blv_get_food_control_results` — Cantonal food inspection results (CSV)
- `blv_get_antibiotic_usage_vet` — Veterinary antibiotic usage ISABV data (CSV)
- `blv_get_avian_influenza` — Wild bird avian influenza surveillance (JSON/KML)
- `blv_get_nutrition_data_children` — menuCH-Kids national nutrition survey (CSV)
- `blv_search_pesticide_products` — Swiss pesticide register search (XML)
- `blv_get_meat_inspection_stats` — Slaughterhouse inspection statistics (CSV/JSON)
- MCP Resources: `blv://datasets/overview`, `blv://info/server`
- MCP Prompts: `food_safety_brief`, `animal_disease_risk_assessment`
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud/Render.com)
- SPARQL → CSV graceful fallback for animal disease data
- Bilingual documentation: English (README.md) + German (README.de.md)
- GitHub Actions CI: Python 3.11–3.13 matrix
- Unit tests covering helpers, input validation, and server structure
