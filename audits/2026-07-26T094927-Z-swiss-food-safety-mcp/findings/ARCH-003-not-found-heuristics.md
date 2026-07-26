## Finding: ARCH-003 — «Not Found» Anti-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Not-found paths on dataset-resolution tools return a structured `_error()` record with a stable `code` and an actionable `note` (server.py:151-153, 456-461, 562-575). However, search tools have no fuzzy/heuristic fallback and no `match_type` field, and empty keyword searches (`blv_list_datasets` -> `[]`) or empty SPARQL result sets return a bare empty list with no explanatory note.

### Expected Behavior

Non-sensitive search tools should, on an empty exact match, return partial/fuzzy results or suggestions plus a `match_type` (exact/fuzzy/none) field and an actionable note so the model can refine the query rather than hallucinate or dead-end.

### Evidence

- `src/swiss_food_safety_mcp/server.py:418-430` — `blv_list_datasets` returns `results` directly; an empty upstream result yields `[]` with no note/match_type
- `src/swiss_food_safety_mcp/server.py:544-555` — SPARQL path returns `cases` (possibly empty) with no note
- `src/swiss_food_safety_mcp/server.py:456-461` — GOOD counter-example: `_error(..., note=...)` on dataset-not-found

### Risk Description

For public open data the impact is low, but on a zero-result search the model may fabricate food-safety facts (recalls, disease cases) instead of signalling 'no data', which is particularly undesirable in a health/safety context.

### Remediation

Add a small envelope helper returning `{results, match_type, count, note}` for the search-style tools; on empty exact matches, attempt a broadened `q=` search and, failing that, emit `match_type: none` with a suggestion note. Keep exact-only behaviour where a heuristic could mislead.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-003` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
