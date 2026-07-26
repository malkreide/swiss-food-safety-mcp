## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-015` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The server pins its tool-definition hashes and enforces them in CI (a local anti-rug-pull guard) but implements no pre-flight tool-poisoning detection; that is documented as a portfolio/gateway accepted risk.

### Expected Behavior

A gateway pre-flight layer detecting at least four poisoning pattern classes (system-prompt injection, override phrases, invisible characters, homoglyphs), filtering high-risk tools default-deny and auditing to a SIEM.

### Evidence

- `tools/tool_manifest.py:26-40` + `tools/tool-hashes.json` — GOOD local guard: SHA-256 pinning of tool defs, enforced at `.github/workflows/ci.yml:44-48`
- `SECURITY.md:67-76` — cross-server pre-flight poisoning detection documented as portfolio/gateway accepted risk

### Risk Description

Tool definitions are in-repo, PR-reviewed and hash-pinned, so a silent rug-pull is already hard. Cross-server poisoning detection remains a host/gateway responsibility and is not provided here.

### Remediation

Keep the local hash-pin guard; implement pre-flight poisoning detection at the MCP gateway/host when the portfolio introduces one.

### Effort Estimate

S

### Verification After Fix

- Re-run the `SEC-015` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
