## Finding: ARCH-012 — protocolVersion-Pinning

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

`CHANGELOG.md` (Keep-a-Changelog) and `.github/dependabot.yml` are present, but the MCP `protocolVersion` is not pinned in code and there is no 'MCP Protocol Version' section in the README.

### Expected Behavior

The server should pin an explicit, tested `protocolVersion` (not the SDK default / 'latest'), reference spec-version bumps in the CHANGELOG, and document an update policy in the README.

### Evidence

- `src/swiss_food_safety_mcp/server.py:284-295` — `FastMCP(name, version, mask_error_details, lifespan, instructions)` — no `protocol_version` argument
- `grep -rniE 'protocol_version|protocolVersion' src/` — no matches
- `.github/dependabot.yml` — GOOD: dependency-update discipline present

### Risk Description

A future FastMCP/SDK upgrade could silently change the negotiated protocol version and break compatibility with pinned clients, without a documented transition — the failure would surface only at runtime.

### Remediation

Pin `protocol_version="<tested-version>"` on the FastMCP instance (if supported by the installed FastMCP), note the pinned version in the CHANGELOG, and add a short 'MCP Protocol Version' section to the README describing the update policy.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-012` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
