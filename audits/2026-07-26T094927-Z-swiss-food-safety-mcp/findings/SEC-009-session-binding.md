## Finding: SEC-009 — Session-ID Cryptographic Binding

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | accepted-risk |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The server is no-auth by design: there is no OAuth token, user identity or per-user session state to bind. FastMCP's Streamable-HTTP session IDs are unauthenticated. This is documented as an accepted risk in SECURITY.md.

### Expected Behavior

Where an HTTP transport carries user identity, session IDs must be cryptographically bound to a validated user (OAuth `sub`), TTL'd, and server-side invalidated on logout.

### Evidence

- `src/swiss_food_safety_mcp/server.py:54-66` — no auth model; no user identity in the request path
- `SECURITY.md:49-56` — SEC-009 explicitly documented as accepted risk under No-Auth-First, with a re-audit trigger if authentication is added

### Risk Description

There is no authenticated identity to hijack, and no PII or write surface behind a session, so cross-user session compromise has no impact today. The risk becomes real only if an auth model is later added without implementing bound sessions.

### Remediation

Keep the accepted-risk status while the server stays no-auth/read-only/no-PII. If auth is ever introduced, implement cryptographically bound (`user_id`+`session_id`), TTL'd, server-side-invalidated sessions and re-audit before merge.

### Effort Estimate

S

### Verification After Fix

- Re-run the `SEC-009` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
