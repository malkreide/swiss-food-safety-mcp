## Finding: SEC-005 — DNS-Rebinding-Prevention (DNS-Pinning)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-005` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

`_guard_url` resolves the host once via `getaddrinfo` and validates every returned address is global, but the subsequent `_client.get(url)` performs its own independent DNS resolution — the validated IP is not reused, leaving a TOCTOU window.

### Expected Behavior

DNS should be resolved once and the resolved IP reused for the actual TCP connection (pinned URL or custom resolver), preserving the original hostname for SNI/Host and cert validation; a test should assert a single DNS resolution per request.

### Evidence

- `src/swiss_food_safety_mcp/server.py:214-217` — validation resolves via `socket.getaddrinfo(host, None)` and checks `is_global`
- `src/swiss_food_safety_mcp/server.py:245-250` — `_client.get(url, ...)` re-resolves the hostname independently; no IP pinning between check and connect
- `src/swiss_food_safety_mcp/server.py:83-85,196-199` — MITIGATION: immutable frozenset allow-list + subdomain-safe `_host_allowed` prevents rebinding to a host the attacker does not control

### Risk Description

In theory a hostname could resolve to a public IP during validation and to a private/metadata IP at connect time (DNS rebinding / TOCTOU). In practice the egress allow-list restricts targets to Swiss federal domains the attacker cannot rebind, so exploitability is very low — but the specific DNS-pinning control is absent.

### Remediation

Resolve the host once, pick a validated global IP, and connect to that IP while setting the `Host` header + TLS `server_hostname` to the original host (e.g. an httpx transport that pins the resolved address), or route all egress through a validating proxy. Add a test asserting a single DNS lookup per request.

### Effort Estimate

M

### Verification After Fix

- Re-run the `SEC-005` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.
