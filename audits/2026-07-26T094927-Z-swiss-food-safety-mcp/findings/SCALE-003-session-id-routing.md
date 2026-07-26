## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

There is no edge-LB `Mcp-Session-Id` routing / stick-table configuration; the cloud deployment (render.yaml) is a single instance. The need is documented in the roadmap as a scaling prerequisite.

### Expected Behavior

An edge LB that reads the `Mcp-Session-Id` header and routes via a stick-table/hash with adequate capacity and TTL, with tested failover behaviour.

### Evidence

- `ROADMAP.md:28-40` — documents that `Mcp-Session-Id` sticky routing would be required for horizontal scaling (explicitly tagged 'audit finding SCALE-003')
- `render.yaml` — no load-balancer/stick-table configuration (single instance)

### Risk Description

Same class of risk as SCALE-002: multi-instance routing without session affinity would drop Streamable-HTTP sessions. Not triggered at single-instance scope.

### Remediation

Defer while single-instance (accepted/documented); when scaling, configure the edge LB (HAProxy stick-table / K8s Ingress affinity) on `Mcp-Session-Id` with a TTL matching the session lifetime and test backend-failover routing.

### Effort Estimate

M

### Verification After Fix

- Re-run the `SCALE-003` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
