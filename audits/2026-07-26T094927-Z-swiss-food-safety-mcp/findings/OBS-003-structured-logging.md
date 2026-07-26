## Finding: OBS-003 — Structured Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Logging is configured via stdlib `logging.basicConfig` with a timestamped text format to stderr, using info/warning/debug levels and no `print()` calls. It is not a structured logger and carries no per-call bound context.

### Expected Behavior

A structured logger (structlog/loguru) emitting JSON or logfmt, with per-tool-call bound context (tool name, session_id, correlation_id) and at least four active severity levels.

### Evidence

- `src/swiss_food_safety_mcp/server.py:41-46` — `logging.basicConfig(stream=sys.stderr, format='%(asctime)s %(levelname)s %(name)s: %(message)s')` — plain text, not JSON/logfmt
- `src/swiss_food_safety_mcp/server.py:253-277` — `_step`/`_ctx_log` log free-text messages with no bound tool/session/correlation context

### Risk Description

Log lines are harder to query/correlate in a SIEM or aggregator; without a correlation id it is difficult to trace one tool call across the HTTP client hops. Low operational risk for a single-instance server.

### Remediation

Adopt structlog (or loguru) with a JSON renderer writing to stderr, and bind `tool`, `session_id`, `correlation_id` per tool invocation via the MCP `Context`.

### Effort Estimate

M

### Verification After Fix

- Re-run the `OBS-003` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
