# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-03-12

### Added
- Initial release
- 11 tools covering all major BLV open data domains:
  - `blv_get_public_warnings` — Live RSS feed for food recalls & health warnings
  - `blv_list_datasets` — Browse all 28 BLV datasets on opendata.swiss
  - `blv_get_dataset_info` — Dataset metadata and resource URLs
  - `blv_search_animal_diseases` — Notifiable animal diseases since 1991 (SPARQL + CSV fallback)
  - `blv_get_animal_health_stats` — Annual animal health statistics
  - `blv_get_food_control_results` — Cantonal food inspection results
  - `blv_get_antibiotic_usage_vet` — Veterinary antibiotic usage (ISABV)
  - `blv_get_avian_influenza` — Wild bird avian influenza surveillance with geodata
  - `blv_get_nutrition_data_children` — Children's nutrition survey (menuCH-Kids)
  - `blv_search_pesticide_products` — Swiss approved pesticide register (XML + CSV)
  - `blv_get_meat_inspection_stats` — Slaughterhouse inspection statistics
- 2 resources: `blv://datasets/overview`, `blv://warnings/current`
- 2 prompts: `prompt_food_safety_analysis`, `prompt_animal_disease_report`
- Dual transport: stdio (default) + Streamable HTTP (`--http`, port 8002)
- No authentication required (No-Auth-First philosophy)
- Bilingual documentation (English primary, German secondary)
- GitHub Actions CI: Python 3.11–3.13 matrix
