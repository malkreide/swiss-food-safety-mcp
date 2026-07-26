## Finding: ARCH-005 — Keine Hardcoded Secrets

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The server uses no authentication and stores no secrets; a grep of `src/` for api_key/password/token/secret is clean and `Settings` holds only non-secret config (server.py:54-70). The ARCH-005 *hygiene* controls, though, are absent: the repository has no `.gitignore` (only `.dockerignore` is tracked), no `.env.example`, and no CI secret-scanning workflow.

### Expected Behavior

Even for a no-secret server the catalogue expects secret-hygiene guardrails: a `.gitignore` ignoring `.env`/`.env.*`, a committed `.env.example` with placeholders, and a gitleaks/trufflehog CI scan on every PR — so that a future secret cannot be committed accidentally.

### Evidence

- Repo root — no `.gitignore` tracked (`git ls-files` shows only `.dockerignore`)
- `.github/workflows/` — `ci.yml` and `publish.yml` contain no gitleaks/trufflehog step
- `src/swiss_food_safety_mcp/server.py:54-70` — GOOD: no secrets loaded; `SECURITY.md:31` documents the no-secret posture

### Risk Description

Residual risk today is near-zero because the server genuinely uses no secrets. The exposure is future-facing: if a contributor ever adds an API key or a local `.env`, the missing `.gitignore` and missing CI scan mean it could be committed and pushed to a public repo before anyone notices.

### Remediation

Add a `.gitignore` (ignore `.env`, `.env.*` except `.env.example`, `__pycache__`, build artifacts), commit a placeholder `.env.example`, and add a gitleaks GitHub Action to the CI workflow on push/pull_request.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-005` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
