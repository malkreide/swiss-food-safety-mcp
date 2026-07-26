## Finding: OPS-001 — Test-Strategie

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `OPS-001` |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

A `live` marker is registered, CI runs `pytest -m 'not live'`, one live test exists, and ~30 mocked unit tests cover the main paths. Gaps: HTTP mocking uses `unittest.mock.patch` rather than the declared `respx` dev-dependency, coverage is uneven, and there is only one live test and no nightly live workflow.

### Expected Behavior

Per catalogue: >=5 unit tests per tool using respx (Python) for HTTP mocking, >=1 live test per tool marked `@pytest.mark.live`, the marker registered, CI running `-m 'not live'`, and a separate nightly/manual live-test workflow.

### Evidence

- `pyproject.toml:43` — `respx` declared as a dev-dep but unused; `tests/test_server.py` mocks via `patch('...server._get', ...)` instead
- `tests/test_server.py` — no dedicated tests for `blv_get_animal_health_stats`, `blv_get_avian_influenza`, `blv_get_nutrition_data_children`; single `@pytest.mark.live` test at lines 675-683
- `.github/workflows/` — no separate nightly live-test workflow
- `pyproject.toml:64-69` + `.github/workflows/ci.yml:50-55` — GOOD: marker registered, CI excludes live tests

### Risk Description

Untested tools (avian influenza, children's nutrition, animal-health stats) may regress silently on refactors or upstream schema changes; without respx the mocks bypass real request/URL construction, so SSRF-guard and param-encoding regressions on those paths could go uncaught.

### Remediation

Add respx-based unit tests (asserting URLs, params and the SSRF guard) for the three untested tools, raise per-tool coverage toward the >=5 target, add a live test per tool, and add a nightly workflow running `pytest -m live`.

### Effort Estimate

M

### Verification After Fix

- Re-run the `OPS-001` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
