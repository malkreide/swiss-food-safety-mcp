# MCP-Server Audit-Report — `swiss-food-safety-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-food-safety-mcp` wurde gegen 40 anwendbare Best-Practice-Checks geprüft. 25 bestanden, 15 Findings dokumentiert (2 critical, 6 high, 7 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-food-safety-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 7 | 0 | 4 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 3 | 0 | 2 | 0 | 0 |
| OPS | 2 | 0 | 1 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SEC | 9 | 0 | 6 | 0 | 0 |
| **Total** | **25** | **0** | **15** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-009 | SEC | critical | partial |
| OPS-001 | OPS | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-011 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | partial |
| OBS-006 | OBS | medium | partial |
| SEC-014 | SEC | medium | partial |
| SEC-015 | SEC | medium | partial |

**Gesamt:** 15 Findings

---

## 5. Detail-Findings

### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Not-found paths on dataset-resolution tools return a structured `_error()` record with a stable `code` and an actionable `note` (server.py:151-153, 456-461, 562-575). However, search tools have no fuzzy/heuristic fallback and no `match_type` field, and empty keyword searches (`blv_list_datasets` -> `[]`) or empty SPARQL result sets return a bare empty list with no explanatory note.

### Expected Behavior

Non-sensitive search tools should, on an empty exact match, return partial/fuzzy results or suggestions plus a `match_type` (exact/fuzzy/none) field and an actionable note so the model can refine the query rather than hallucinate or dead-end.

### Evidence

- `src/swiss_food_safety_mcp/server.py:418-430` — `blv_list_datasets` returns `results` directly; an empty upstream result yields `[]` with no note/match_type
- `src/swiss_food_safety_mcp/server.py:544-555` — SPARQL path returns `cases` (possibly empty) with no note
- `src/swiss_food_safety_mcp/server.py:456-461` — GOOD counter-example: `_error(..., note=...)` on dataset-not-found

### Risk Description

For public open data the impact is low, but on a zero-result search the model may fabricate food-safety facts (recalls, disease cases) instead of signalling 'no data', which is particularly undesirable in a health/safety context.

### Remediation

Add a small envelope helper returning `{results, match_type, count, note}` for the search-style tools; on empty exact matches, attempt a broadened `q=` search and, failing that, emit `match_type: none` with a suggestion note. Keep exact-only behaviour where a heuristic could mislead.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-003` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

The server uses no authentication and stores no secrets; a grep of `src/` for api_key/password/token/secret is clean and `Settings` holds only non-secret config (server.py:54-70). The ARCH-005 *hygiene* controls, though, are absent: the repository has no `.gitignore` (only `.dockerignore` is tracked), no `.env.example`, and no CI secret-scanning workflow.

### Expected Behavior

Even for a no-secret server the catalogue expects secret-hygiene guardrails: a `.gitignore` ignoring `.env`/`.env.*`, a committed `.env.example` with placeholders, and a gitleaks/trufflehog CI scan on every PR — so that a future secret cannot be committed accidentally.

### Evidence

- Repo root — no `.gitignore` tracked (`git ls-files` shows only `.dockerignore`)
- `.github/workflows/` — `ci.yml` and `publish.yml` contain no gitleaks/trufflehog step
- `src/swiss_food_safety_mcp/server.py:54-70` — GOOD: no secrets loaded; `SECURITY.md:31` documents the no-secret posture

### Risk Description

Residual risk today is near-zero because the server genuinely uses no secrets. The exposure is future-facing: if a contributor ever adds an API key or a local `.env`, the missing `.gitignore` and missing CI scan mean it could be committed and pushed to a public repo before anyone notices.

### Remediation

Add a `.gitignore` (ignore `.env`, `.env.*` except `.env.example`, `__pycache__`, build artifacts), commit a placeholder `.env.example`, and add a gitleaks GitHub Action to the CI workflow on push/pull_request.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-005` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### ARCH-011

## Finding: ARCH-011 — Standardisierte Repo-Struktur

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `ARCH-011` |
| **PDF-Reference** | Anhang A8 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

All mandatory top-level files (README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml) and directories (src/, tests/, .github/workflows/) are present, the src-layout is correct, and the two READMEs have section parity. The one deviation: all 11 tools live in a single 1078-line `server.py`.

### Expected Behavior

For servers with more than 5 tools the catalogue expects a `tools/` sub-package with one file per tool group and a `server.py` reduced to registry + lifecycle (< ~200 lines).

### Evidence

- `src/swiss_food_safety_mcp/server.py` — 1078 lines containing all 11 tools, 2 resources, 2 prompts, the HTTP client and the entry point
- `pyproject.toml:61-62` — GOOD: correct src-layout packaging

### Risk Description

Purely maintainability/auditability: a single large module makes code review and per-tool test isolation harder as the server grows. No security impact.

### Remediation

Split tools into `src/swiss_food_safety_mcp/tools/` modules grouped by domain (recalls, datasets, animal_health, food_control, pesticides) and keep `server.py` for the FastMCP instance, lifespan and registration. Alternatively, document the single-file choice in the README as an intentional deviation.

### Effort Estimate

S

### Verification After Fix

- Re-run the `ARCH-011` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### ARCH-012

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


### OBS-003

## Finding: OBS-003 — Structured Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Logging is configured via stdlib `logging.basicConfig` with a timestamped text format to stderr, using info/warning/debug levels and no `print()` calls. It is not a structured logger and carries no per-call bound context.

### Expected Behavior

A structured logger (structlog/loguru) emitting JSON or logfmt, with per-tool-call bound context (tool name, session_id, correlation_id) and at least four active severity levels.

### Evidence

- `src/swiss_food_safety_mcp/server.py:41-46` — `logging.basicConfig(stream=sys.stderr, format='%(asctime)s %(levelname)s %(name)s: %(message)s')` — plain text, not JSON/logfmt
- `src/swiss_food_safety_mcp/server.py:253-277` — `_step`/`_ctx_log` log free-text messages with no bound tool/session/correlation context

### Risk Description

Log lines are harder to query/correlate in a SIEM or aggregator; without a correlation id it is difficult to trace one tool call across the HTTP client hops. Low operational risk for a single-instance server.

### Remediation

Adopt structlog (or loguru) with a JSON renderer writing to stderr, and bind `tool`, `session_id`, `correlation_id` per tool invocation via the MCP `Context`.

### Effort Estimate

M

### Verification After Fix

- Re-run the `OBS-003` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### OBS-006

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


### OPS-001

## Finding: OPS-001 — Test-Strategie

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `OPS-001` |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

A `live` marker is registered, CI runs `pytest -m 'not live'`, one live test exists, and ~30 mocked unit tests cover the main paths. Gaps: HTTP mocking uses `unittest.mock.patch` rather than the declared `respx` dev-dependency, coverage is uneven, and there is only one live test and no nightly live workflow.

### Expected Behavior

Per catalogue: >=5 unit tests per tool using respx (Python) for HTTP mocking, >=1 live test per tool marked `@pytest.mark.live`, the marker registered, CI running `-m 'not live'`, and a separate nightly/manual live-test workflow.

### Evidence

- `pyproject.toml:43` — `respx` declared as a dev-dep but unused; `tests/test_server.py` mocks via `patch('...server._get', ...)` instead
- `tests/test_server.py` — no dedicated tests for `blv_get_animal_health_stats`, `blv_get_avian_influenza`, `blv_get_nutrition_data_children`; single `@pytest.mark.live` test at lines 675-683
- `.github/workflows/` — no separate nightly live-test workflow
- `pyproject.toml:64-69` + `.github/workflows/ci.yml:50-55` — GOOD: marker registered, CI excludes live tests

### Risk Description

Untested tools (avian influenza, children's nutrition, animal-health stats) may regress silently on refactors or upstream schema changes; without respx the mocks bypass real request/URL construction, so SSRF-guard and param-encoding regressions on those paths could go uncaught.

### Remediation

Add respx-based unit tests (asserting URLs, params and the SSRF guard) for the three untested tools, raise per-tool coverage toward the >=5 target, add a live test per tool, and add a nightly workflow running `pytest -m live`.

### Effort Estimate

M

### Verification After Fix

- Re-run the `OPS-001` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### SCALE-002

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


### SCALE-003

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


### SEC-005

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


### SEC-009

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


### SEC-014

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


### SEC-015

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


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-food-safety-mcp` |
| **Check-Reference** | `SEC-018` |
| **PDF-Reference** | Sec 3 / Sec 4 (Defense-in-Depth) |
| **Audit-Datum** | 2026-07-26 |
| **Auditor** | mcp-audit skill v1.0.0 (Claude) |

### Observed Behavior

Tool parameters are type-hinted so FastMCP/Pydantic generates and enforces an input schema and coerces types, and handlers clamp limits in-body and escape SPARQL. But there are no schema-level constraints (ge/le, min/max_length, pattern), no `strict=True`/`extra='forbid'`, and no explicit input models. Notably, SECURITY.md overstates this control.

### Expected Behavior

All tool arguments validated with schema constraints: numeric `ge`/`le`, string `min_length`/`max_length`/whitelist `pattern`, Pydantic `strict=True` + `extra='forbid'`, with validation errors surfaced as tool-result errors and edge-case tests.

### Evidence

- `src/swiss_food_safety_mcp/server.py:349,387-405,489-497` — params typed as plain `int`/`str`/`int|None`; no `Field(ge=..., le=..., max_length=...)` constraints
- `src/swiss_food_safety_mcp/server.py:57` — only `Settings` has `model_config` (env_prefix); no `extra='forbid'`/`strict=True`; no tool input `BaseModel`s exist
- `SECURITY.md:29` — INACCURATE claim: 'Pydantic v2 strict validation (extra="forbid", whitespace stripping) on every tool input model'
- MITIGATION: `server.py:362,405,514` in-body clamping; `:322-331` `_sparql_escape` (tested at `tests/test_server.py:516-534`)

### Risk Description

Unbounded/loosely-typed inputs could pass oversized strings or out-of-range integers into upstream query construction; the in-body clamps cover the known numeric cases but new parameters are unprotected by default. The inaccurate SECURITY.md claim could give reviewers false assurance.

### Remediation

Introduce Pydantic-constrained parameters (or `Annotated[int, Field(ge=1, le=...)]`, `Annotated[str, Field(max_length=...)]`) on every tool, set `strict=True`/`extra='forbid'` where models are used, add out-of-range/oversized/unknown-field tests, and correct the SECURITY.md wording to match the implementation.

### Effort Estimate

M

### Verification After Fix

- Re-run the `SEC-018` check in a follow-up audit against this repository.
- Confirm the remediation with a targeted test or code review sign-off.


### SEC-021

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


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-009** (critical, partial)
3. **OPS-001** (high, partial)
4. **SCALE-002** (high, partial)
5. **SCALE-003** (high, partial)
6. **SEC-005** (high, partial)
7. **SEC-018** (high, partial)
8. **SEC-021** (high, partial)
9. **ARCH-003** (medium, partial)
10. **ARCH-011** (medium, partial)
11. **ARCH-012** (medium, partial)
12. **OBS-003** (medium, partial)
13. **OBS-006** (medium, partial)
14. **SEC-014** (medium, partial)
15. **SEC-015** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| policy | `fail-or-partial` |


_Generated by tools/build_report.py — do not edit by hand._
