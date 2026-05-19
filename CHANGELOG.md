# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-23

### Added
- Initial release
- 11 tools covering BLV food safety open data
- Dual transport: stdio + Streamable HTTP
- Bilingual documentation (EN/DE)

## [Unreleased]

### Security
- HTTP transport now binds to `127.0.0.1` by default instead of `0.0.0.0`;
  external exposure requires an explicit `--host 0.0.0.0` (audit finding SEC-016).
- `blv_search_animal_diseases` escapes caller-supplied `canton`/`disease` values
  before SPARQL interpolation, preventing query injection (SEC-018).
- XML feeds are parsed with `defusedxml` instead of the standard library,
  mitigating XML entity-expansion attacks (SEC-018).
- Result-limit parameters are clamped to documented maximums (SEC-018).
- Error details are masked toward the model via `mask_error_details` (OBS-002).
- Outbound requests are SSRF-guarded: HTTPS-only, restricted to an immutable
  egress allow-list of Swiss federal hosts, with public-IP and redirect-target
  validation (audit findings SEC-004, SEC-005, SEC-021).

### Added
- CORS configuration for the HTTP transport exposing the `Mcp-Session-Id`
  header, with an explicit `BLV_MCP_ALLOWED_ORIGINS` env var (SDK-004).
- All tools now carry MCP annotations (`readOnlyHint`, `idempotentHint`,
  `openWorldHint`) (audit finding ARCH-009).
- Multi-stage, non-root `Dockerfile` with a healthcheck (SEC-007, SCALE-004).

### Changed
- Configuration moved to a `pydantic-settings` `Settings` object; all settings
  are overridable via `BLV_MCP_*` environment variables (audit finding ARCH-004).
- The HTTP client is now created once via a FastMCP lifespan and pooled across
  requests instead of being recreated per call (audit finding SDK-001).

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
