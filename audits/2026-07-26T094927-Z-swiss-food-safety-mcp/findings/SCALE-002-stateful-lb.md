## Finding: SCALE-002 — Stateful Load Balancing

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The Streamable HTTP transport keeps per-session state, and the repo explicitly documents a deliberate single-instance deployment. No sticky-session LB affinity and no shared session store are implemented.

### Expected Behavior

For horizontally scaled HTTP/SSE, at least one of: `Mcp-Session-Id` sticky sessions at the edge LB, or a shared-state session manager (Redis/Durable Objects), with an explicit session TTL and a tested failover path.

### Evidence

- `README.md:282-296` + `ROADMAP.md:28-40` — single-instance design documented; sticky routing + shared store called out as required-for-scaling but not implemented
- `render.yaml:1-12` — single free-plan web service, no session-affinity config

### Risk Description

If the service were ever scaled to multiple instances without adding affinity/shared state, Streamable-HTTP sessions would break on any request routed to a different instance. At the documented single-instance scope the risk does not materialise.

### Remediation

Keep single-instance and treat this as an accepted, documented scoping decision; OR, before scaling, add `Mcp-Session-Id` sticky routing at the LB (or a Redis-backed session store) with an explicit TTL and a failover test.

### Effort Estimate

M

### Verification After Fix

- Re-run the `SCALE-002` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
