# Security Policy & Posture

🌐 **English** | **[Deutsch](SECURITY.de.md)**

`swiss-food-safety-mcp` was hardened against the internal MCP best-practice audit
catalogue. This document summarises the security posture and records the
**accepted-risk** decisions for controls that are deliberately handled at the
portfolio/gateway layer rather than inside this single server.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in `README.md`. Do not file public issues for exploitable
vulnerabilities.

## Posture summary

This is a **read-only**, **no-PII**, **public-open-data** MCP server. All 11
tools only issue HTTP GET / SPARQL `SELECT` requests against a fixed set of
Swiss federal open-data endpoints (opendata.swiss CKAN, lindas.admin.ch SPARQL,
news.admin.ch RSS — see `README.md`). Hardening already in place:

| Area | Control |
|---|---|
| Egress | HTTPS to a fixed allow-list of Swiss federal hosts (`*.admin.ch`, `opendata.swiss`); no user-controlled URLs are constructed (SEC-004/021) |
| TLS | Certificate verification on by default (httpx default); never disabled (SEC-005) |
| Binding | stdio transport by default; the optional `--http` transport binds to `127.0.0.1` unless `--host 0.0.0.0` is explicitly passed (SEC-016 / SDK-004) |
| Origins | `BLV_MCP_ALLOWED_ORIGINS` (comma-separated, no wildcard) gates browser clients; defaults to `https://claude.ai` |
| Input | Pydantic v2 strict validation (`extra="forbid"`, whitespace stripping) on every tool input model (SEC-008/018) |
| Tools | Every tool sets `readOnlyHint: True`; no write, mutate, or delete paths exist (ARCH) |
| Secrets | None required — the server uses no API key or credentials; nothing secret is stored or logged (ARCH-005/SEC-013) |
| Errors | Upstream error bodies are logged to stderr only; the model receives a generic, non-leaking message (OBS-002) |
| Stdout | Reserved for the JSON-RPC stream; all logging pinned to stderr (OBS-004) |
| Resilience | A 30s per-request timeout (`BLV_MCP_TIMEOUT`) bounds every upstream call (SCALE-002/003) |

The audit and its reruns (see `docs/audit/`) reduced the findings from 31
(3 Critical, 16 High, 12 Medium) at the initial run to 5 at the second reaudit,
with **26 findings resolved**. The remaining items are either accepted risks
(below) or inherent to the intentional no-auth, read-only, public-data design.
See `CHANGELOG.md` for the hardening history.

## Accepted risks (portfolio-level controls)

The following audit checks are **not** implemented inside this server by design.
They are portfolio-wide concerns best enforced at an MCP gateway / host layer,
and the residual risk here is low because the server is read-only and only
reaches a small set of trusted Swiss federal open-data providers.

### SEC-009 — No authentication on the HTTP transport

**Status:** accepted risk — inherent to the no-auth design.
This server intentionally follows a **No-Auth-First** philosophy: it exposes
only read-only queries against public open data and stores no secrets or PII.
There is therefore no authentication model to bypass and no practical impact.
If an authentication model is ever added, bound, TTL'd, server-side-invalidated
session IDs must be implemented and the server re-audited before merge.

### SEC-014 — Tool allow-listing via an MCP gateway

**Status:** accepted risk (portfolio-level).
A per-tool allow-list belongs to the MCP host/gateway that aggregates multiple
servers, not to an individual server that exposes a fixed, read-only tool set.
If/when a central gateway is introduced for the portfolio, tool allow-listing
should be configured there. Until then, the risk is bounded: every tool is
read-only and constrained to the fixed endpoints above.

### SEC-015 — Pre-flight tool-poisoning detection

**Status:** accepted risk (portfolio-level) — with a local guard in place.
Tool-poisoning (malicious tool descriptions / rug-pulls) is a supply-chain and
host-side concern. This server's tool definitions are version-controlled,
authored in-repo, and reviewed via PR; there is no dynamic or remote tool
registration, and tool hashes are pinned in `tools/tool-hashes.json`.
Cross-server poisoning detection remains a gateway/host responsibility tracked
at the portfolio level.

## Re-evaluation triggers

These acceptances should be revisited if the server ever:

- gains **write** capability or starts processing **PII**, or
- adds an **authentication** model (then implement bound, TTL'd,
  server-side-invalidated session IDs and re-audit before merge), or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then enable the gateway's tool
  allow-listing and tool-poisoning detection).
