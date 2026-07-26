## Finding: ARCH-011 — Standardisierte Repo-Struktur

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-011` |
| **PDF-Reference** | Anhang A8 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

All mandatory top-level files (README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml) and directories (src/, tests/, .github/workflows/) are present, the src-layout is correct, and the two READMEs have section parity. The one deviation: all 11 tools live in a single 1078-line `server.py`.

### Expected Behavior

For servers with more than 5 tools the catalogue expects a `tools/` sub-package with one file per tool group and a `server.py` reduced to registry + lifecycle (< ~200 lines).

### Evidence

- `src/swiss_food_safety_mcp/server.py` — 1078 lines containing all 11 tools, 2 resources, 2 prompts, the HTTP client and the entry point
- `pyproject.toml:61-62` — GOOD: correct src-layout packaging

### Risk Description

Purely maintainability/auditability: a single large module makes code review and per-tool test isolation harder as the server grows. No security impact.

### Remediation

Split tools into `src/swiss_food_safety_mcp/tools/` modules grouped by domain (recalls, datasets, animal_health, food_control, pesticides) and keep `server.py` for the FastMCP instance, lifespan and registration. Alternatively, document the single-file choice in the README as an intentional deviation.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-011` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
