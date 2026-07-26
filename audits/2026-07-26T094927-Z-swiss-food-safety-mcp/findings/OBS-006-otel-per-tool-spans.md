## Finding: OBS-006 — OpenTelemetry Tracing

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Opt-in OpenTelemetry is wired: `_setup_telemetry` builds a TracerProvider + OTLP/HTTP exporter and enables httpx auto-instrumentation, gated on `BLV_MCP_OTEL_ENDPOINT`, with `service.name` set. Missing: explicit per-tool-call spans and an environment tag.

### Expected Behavior

Each tool call should open a span carrying `mcp.tool.name`, `mcp.user.id` and `mcp.tool.result.is_error`, with backend HTTP calls as child spans, and a deployment/environment tag on the resource.

### Evidence

- `src/swiss_food_safety_mcp/server.py:161-186` — TracerProvider + OTLPSpanExporter + HTTPXClientInstrumentor + `service.name`; GOOD but only HTTP-client spans are produced
- `src/swiss_food_safety_mcp/server.py:161-186` — no `tracer.start_as_current_span(...)` around tool handlers; no `environment` resource attribute

### Risk Description

Traces show upstream HTTP calls but not which MCP tool triggered them or whether it errored, reducing the value of distributed tracing in a cloud deployment. Tracing is off by default so day-to-day risk is low.

### Remediation

Wrap tool handlers (or add a FastMCP middleware) to open a span per call with the required `mcp.*` attributes, and set an `environment`/`deployment.environment` resource attribute from an env var.

### Effort Estimate

M

### Verification After Fix

- Re-run the `OBS-006` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
