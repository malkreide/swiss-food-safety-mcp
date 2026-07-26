## Finding: SEC-021 — Egress-Allow-List (Code + Network Layer)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The code-layer egress allow-list is exemplary: an immutable frozenset checked pre-request in `_guard_url` with redirect re-validation. Missing: a network-layer egress control as defense-in-depth, a `docs/network-egress.md`, and a documented allow-list update procedure.

### Expected Behavior

Egress restricted at both the code layer (frozenset, pre-request check) and the network layer (NetworkPolicy/Security Group/WARP), with the allow-list and its update procedure documented.

### Evidence

- `src/swiss_food_safety_mcp/server.py:83-85` — GOOD: `ALLOWED_EGRESS_SUFFIXES` immutable frozenset (not config-mutable)
- `src/swiss_food_safety_mcp/server.py:202-223,245-250` — GOOD: `_guard_url` pre-request check + `_on_response` redirect re-validation
- `render.yaml` / `docker-compose.yml` — no network-layer egress restriction; no `docs/network-egress.md`

### Risk Description

If the process were compromised or a code path bypassed `_guard_url`, there would be no second-layer network control to stop arbitrary egress. For a read-only server with no shell/eval this is a low-likelihood, defense-in-depth gap.

### Remediation

Add a network-layer egress restriction to the deployment (e.g. Render/K8s egress policy or a WARP/proxy allow-list) matching the code allow-list, and document the hosts + update procedure in `docs/network-egress.md`.

### Effort Estimate

M

### Verification After Fix

- Re-run the `SEC-021` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
