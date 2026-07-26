## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-014` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

No per-team/role tool allow-list or default-deny `tools/list` filtering is implemented in the server. It is documented as a portfolio/gateway-level accepted risk.

### Expected Behavior

In enterprise/cloud contexts, a default-deny tool allow-list per team/role, server-side role checks for sensitive tools, and auditing of denied calls.

### Evidence

- `SECURITY.md:58-65` — SEC-014 documented as a portfolio/gateway accepted risk; all tools are read-only and constrained to fixed federal endpoints
- `src/swiss_food_safety_mcp/server.py:348-949` — every tool is exposed unconditionally (no role/allow-list gating)

### Risk Description

For a fixed, read-only, public-data tool set the impact is low. If aggregated behind a shared gateway with other servers, absence of per-role allow-listing could over-expose tools to teams that should not see them.

### Remediation

Keep as accepted risk for the standalone server; enable tool allow-listing at the MCP gateway when/if one is introduced for the portfolio.

### Effort Estimate

S

### Verification After Fix

- Re-run the `SEC-014` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
