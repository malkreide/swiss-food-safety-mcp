# MCP Audit Report — swiss-food-safety-mcp

| | |
|---|---|
| **Run-ID** | `2026-05-19T143000+0200-swiss-food-safety-mcp` |
| **Audit date** | 2026-05-19 |
| **Skill** | `malkreide/mcp-audit-skill` (catalog `main`, 68 checks) |
| **Audited revision** | branch `claude/audit-mcp-skill-FeqNh` (= `main`) |
| **Server version** | 1.0.0 |

---

## Executive Summary

swiss-food-safety-mcp is a well-structured read-only MCP server exposing 11 tools
over official Swiss Federal Food Safety (BLV) open data, and it passes the
high-risk security checks that matter most for this profile — no command
injection, no lethal trifecta, no hardcoded secrets, clean stdout for stdio.
The audit ran 44 of 68 checks (24 filtered out as not applicable) and produced
**31 findings: 3 critical, 16 high, 12 medium**.

**Production-ready: NO.** One hard critical failure (SEC-016 — the HTTP transport
binds to `0.0.0.0` by default) blocks production for any networked deployment,
and two further critical checks are only partially met. The stdio (local
desktop) deployment path is in considerably better shape than the Streamable
HTTP path.

---

## Step 1 — Profile Snapshot

| Field | Value | Source |
|---|---|---|
| Transport | dual (stdio default, Streamable HTTP via `--http`) | `server.py:635-650` |
| Auth-Model | none | `FastMCP(...)` has no auth; README "No Auth" |
| Data Class | Public Open Data | all sources are opendata.swiss / admin.ch |
| Write Access | read-only (`write_capable = false`) | all 11 tools are HTTP GET |
| Deployment | local-stdio + Render.com (cloud) | `README.md:120-135` |
| Repo URL | github.com/malkreide/swiss-food-safety-mcp | `pyproject.toml:48` |
| SDK language | Python (fastmcp ≥ 2.0) | `pyproject.toml:31` |
| External requests | yes (`tools_make_external_requests = true`) | `_get`, `_fetch_csv` |
| Cloud-deployed | yes (`is_cloud_deployed = true`) | Render.com target |
| Sampling / sequential-thinking / filesystem | none | no `ctx.sample`, no file tools |
| Swiss-context flags | `data_source.is_swiss_open_data = true`; no enterprise / Stadt Zürich / Schulamt / Volksschule context | — |

Profile is complete — no placeholder values, all six mandatory fields resolved.

---

## Step 3 — Applicability Overview

| Category | Total | Applicable | Filtered out |
|---|---|---|---|
| ARCH | 12 | 11 | 1 (ARCH-010 — write-only) |
| SDK | 5 | 4 | 1 (SDK-005 — TypeScript) |
| SEC | 23 | 15 | 8 (OAuth/API-key/filesystem/DLP checks) |
| SCALE | 6 | 5 | 1 (SCALE-005 — enterprise gateway) |
| OBS | 6 | 5 | 1 (OBS-005 — non-public data) |
| HITL | 5 | 0 | 5 (no sampling, no writes) |
| CH | 8 | 1 | 7 (non-public / PII / context-specific) |
| OPS | 3 | 3 | 0 |
| **Total** | **68** | **44** | **24** |

Result breakdown of the 44 executed checks: **13 pass · 19 fail · 12 partial**.

---

## Step 4 — Findings Table

Findings are generated for `fail` and `partial` checks only. Severity is the
catalog severity of the check.

### Critical (3)

| ID | Check | Status | Effort |
|---|---|---|---|
| SEC-016 | 0.0.0.0-Binding-Prevention (NeighborJack) | fail | S |
| SEC-004 | SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting | partial | M |
| SEC-009 | Session-ID Cryptographic Binding | partial | M |

### High (16)

| ID | Check | Status | Effort |
|---|---|---|---|
| ARCH-004 | Inversion of Control: transport-agnostic logic | partial | M |
| ARCH-009 | Tool Annotations (readOnlyHint / openWorldHint) | fail | S |
| SDK-001 | FastMCP Lifespan via `@asynccontextmanager` | fail | S |
| SDK-004 | CORS `Mcp-Session-Id` exposure for HTTP/SSE | fail | S |
| SEC-005 | DNS-Rebinding-Prevention (DNS pinning) | fail | M |
| SEC-007 | Container-Sandboxing (Docker, least privilege) | fail | M |
| SEC-018 | Input-Validation at tool boundaries | fail | M |
| SEC-021 | Egress-Allow-List (code + network layer) | fail | M |
| SEC-022 | Tool-Hash-Pinning + Namespace-Prefix | partial | S |
| SCALE-001 | Streamable HTTP for cloud deployments | partial | S |
| SCALE-002 | Stateful Load Balancing for HTTP/SSE | fail | M |
| SCALE-003 | `Mcp-Session-Id` routing via edge LB | fail | M |
| OBS-001 | Protocol vs. Execution errors separation | partial | M |
| OBS-002 | Mask Error Details (no stacktraces to LLM) | fail | S |
| OPS-001 | Test strategy (mocked unit + marked live) | partial | S |
| OPS-003 | Phase architecture (read-only first) | partial | S |

### Medium (12)

| ID | Check | Status | Effort |
|---|---|---|---|
| ARCH-002 | Tool descriptions with use-case tags | partial | M |
| ARCH-003 | "Not Found" anti-pattern (heuristics) | partial | M |
| ARCH-012 | protocolVersion pinning + CHANGELOG hygiene | fail | S |
| SDK-002 | Pydantic v2 / TypedDict tool returns | partial | M |
| SDK-003 | Context injection for progress + logging | fail | M |
| SEC-014 | Tool allow-listing via MCP gateway | fail | L |
| SEC-015 | Pre-flight tool-poisoning detection | fail | L |
| SCALE-004 | Containerization with multi-stage builds | fail | M |
| SCALE-006 | Resource limits per container | fail | S |
| OBS-003 | Structured logging (RFC 5424) | fail | M |
| OBS-006 | OpenTelemetry distributed tracing | fail | M |
| CH-004 | OGD-CH license / CC BY attribution | partial | M |

### Passing checks (13)

ARCH-001, ARCH-005, ARCH-006, ARCH-007, ARCH-008, ARCH-011, SEC-006,
SEC-008, SEC-013, SEC-019, SEC-020, OBS-004, OPS-002.

---

## Step 5 — Detailed Findings

### Critical

#### SEC-016 — HTTP transport binds to `0.0.0.0` by default — `fail`

**Observed.** The `--host` CLI argument defaults to `0.0.0.0`, and that value is
passed straight into `mcp.run(transport="streamable-http", ...)`.

```
server.py:644   parser.add_argument("--host", type=str, default="0.0.0.0", ...)
server.py:648   mcp.run(transport="streamable-http", host=args.host, port=args.port)
```

**Risk.** Starting the server with `--http` exposes an **unauthenticated** MCP
endpoint on every network interface — the local network, and inside a container
the whole pod/host network. The catalog calls this "NeighborJack": any neighbour
on the network can drive the server. Combined with `auth_model = none`, there is
no second line of defence. This is the single hard blocker for production.

**Remediation.** Default the bind address in code to `127.0.0.1`. Only widen to
`0.0.0.0` via an explicit container `ENV` / start-command override when the
deployment intends external exposure (Render terminates TLS in front of the
service, so the documented Render start command should set the host
deliberately). Effort: **S**.

#### SEC-004 — No SSRF controls on dynamically-resolved URLs — `partial`

**Observed.** Base endpoints are hardcoded HTTPS constants (`CKAN_BASE`,
`SPARQL_ENDPOINT`, `BLV_RSS`) — good. However, CKAN dataset *resource* URLs are
read out of API responses and fetched directly, with redirects followed and no
scheme or IP validation:

```
server.py:56    httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
server.py:263   rows = await _fetch_csv(csv_url)        # csv_url from CKAN response
server.py:407   r = await _get(data_url)                # data_url from CKAN response
server.py:494   r = await _get(xml_url)                 # xml_url from CKAN response
```

**Risk.** A resource URL served by opendata.swiss that pointed at an `http://`
target or an internal/metadata IP (`169.254.169.254`, RFC1918) would be fetched
without challenge; `follow_redirects=True` widens this to redirect-based SSRF.
Practical likelihood is low (opendata.swiss is a trusted federal source), which
is why this is scored `partial` rather than `fail` — but there are zero
defensive controls.

**Remediation.** Enforce `https://` on every dynamically-obtained URL, reject
URLs that resolve to private/link-local/loopback ranges before the request, and
either disable `follow_redirects` or re-validate the redirect target. Effort: **M**.

#### SEC-009 — Session IDs not bound to a validated user identity — `partial`

**Observed.** `Mcp-Session-Id` handling is delegated entirely to FastMCP's
Streamable HTTP implementation; the server adds no session logic of its own.
Because `auth_model = none`, there is no authenticated `user_id` to bind a
session to.

**Risk.** For an authenticated server this would be a critical hijacking gap.
Here it is scored `partial`: the data is public and read-only, so a hijacked
session grants no privilege and exposes no confidential data — the residual
confidentiality/integrity impact is effectively nil. It remains listed because
the no-auth design is itself the reason the control cannot exist.

**Remediation.** No change required while the server stays read-only and
public. If any authenticated or write capability is ever added, sessions must be
generated with a CSPRNG and bound to a validated `user_id` before that feature
ships. Effort: **M** (only if scope changes).

### High

#### ARCH-009 — Tools carry no annotations — `fail`

**Observed.** All 11 `@mcp.tool()` decorators (`server.py:81, 114, 159, 198,
272, 303, 343, 381, 425, 463, 539`) are bare — no `annotations=` / hint
metadata. Every tool is read-only and talks to an external API.

**Risk.** MCP hosts cannot tell that these tools are safe, non-destructive and
open-world; clients may gate or warn unnecessarily, and a future
write/destructive tool added without annotations would be indistinguishable
from the safe ones.

**Remediation.** Set `readOnlyHint=True` and `openWorldHint=True` on all 11
tools (`idempotentHint=True` is also accurate here). Add a CI assertion that
tools whose names start with `create`/`update`/`delete` are never
`readOnlyHint`. Effort: **S**.

#### ARCH-004 — Logic is transport-agnostic but config is hardcoded — `partial`

**Observed.** Tool handlers correctly avoid transport internals (no `request.`,
`stdin`, `websocket`) and stdio/HTTP produce identical results. But all
configuration — endpoints, org ID, timeout, port — lives as module-level
constants (`server.py:28-32`) instead of a settings object.

**Remediation.** Introduce a pydantic-settings `Settings` (`BaseSettings`) class
for endpoints, timeout, host, port and transport, loaded from environment
variables. Effort: **M**.

#### SDK-001 — No lifespan; a new HTTP client per request — `fail`

**Observed.** `_get` opens a fresh `httpx.AsyncClient` for every call
(`server.py:54-57`). There is no `@asynccontextmanager` lifespan.

**Risk.** No connection pooling or keep-alive reuse — every tool call pays full
TCP+TLS handshake cost, and there is no managed place to hold shared resources.

**Remediation.** Add a FastMCP lifespan that constructs one shared
`httpx.AsyncClient` and yields it; have `_get` use the shared client. Effort: **S**.

#### SDK-004 — No CORS configuration for the HTTP transport — `fail`

**Observed.** `mcp.run(transport="streamable-http", ...)` (`server.py:648`) is
started with no CORS middleware and no `ALLOWED_ORIGINS`.

**Risk.** Browser-based MCP clients (the documented claude.ai use case) need the
`Mcp-Session-Id` response header exposed via CORS; without it, browser sessions
break. An unconfigured default also risks an over-permissive origin policy.

**Remediation.** Configure CORS middleware on the HTTP app to expose
`Mcp-Session-Id`, with an explicit `ALLOWED_ORIGINS` env var (no wildcard).
Effort: **S**.

#### SEC-005 — No DNS-rebinding protection — `fail`

**Observed.** Outbound requests use a plain `httpx.AsyncClient` with no
resolve-once / IP-pinning transport (`server.py:54-57`).

**Risk.** A hostname could resolve to a benign IP at validation time and an
internal IP at request time (TOCTOU). Practical risk is low given trusted
hosts, but the control is absent.

**Remediation.** Use a custom httpx transport that resolves DNS once and pins
the IP for the connection while preserving TLS SNI / certificate validation.
Best implemented together with SEC-004. Effort: **M**.

#### SEC-007 — No container hardening artifacts — `fail`

**Observed.** The repo contains no `Dockerfile`, `docker-compose.yml` or Render
manifest. The documented Render deployment relies on an implicit buildpack with
no declared non-root user or least-privilege configuration.

**Remediation.** Add a hardened `Dockerfile` (non-root `USER`, minimal base
image, `HEALTHCHECK`) and, where applicable, a Kubernetes `securityContext`.
Effort: **M**. (Shared remediation with SCALE-004.)

#### SEC-018 — Input not validated/escaped at tool boundaries — `fail`

**Observed.** Three concrete gaps:

1. **SPARQL injection.** `blv_search_animal_diseases` builds its SPARQL query by
   f-string interpolation of caller-supplied `canton` and `disease` strings
   directly into string literals:

   ```
   server.py:230   "FILTER(CONTAINS(STR(?canton), '" + canton + "'))" if canton else ""
   server.py:231   "FILTER(CONTAINS(LCASE(STR(?disease)), LCASE('" + disease + "')))" if disease else ""
   ```

   A value containing a single quote breaks out of the literal and alters the
   query. The endpoint is a public read-only triplestore so impact is bounded,
   but it is a genuine query-injection flaw.

2. **Unbounded `limit`.** Only `blv_get_public_warnings` caps its limit
   (`server.py:92`, max 50). `blv_list_datasets`, `blv_search_animal_diseases`,
   `blv_search_pesticide_products` etc. pass `limit` through unbounded — large
   values can be forwarded to upstream APIs or used to slice very large result
   sets.

3. **Untrusted XML parsed with the stdlib parser.** `xml.etree.ElementTree.
   fromstring` is used on remote feeds (`server.py:95` RSS, `server.py:494`
   pesticide XML). Stdlib ElementTree is exposed to entity-expansion / quadratic
   blow-up denial-of-service.

**Remediation.** (1) Escape SPARQL string literals or use parameterised query
construction; reject quote characters in `canton`/`disease`. (2) Clamp every
`limit` to a documented maximum. (3) Switch XML parsing to `defusedxml`.
Validate `canton` against the set of valid two-letter codes. Effort: **M**.

#### SEC-021 — No egress allow-list — `fail`

**Observed.** There is no code-layer allow-list of permitted outbound hosts;
`_get` will fetch any URL it is handed (see SEC-004).

**Remediation.** Define an immutable `FrozenSet` of permitted hostnames
(`opendata.swiss`, `lindas.admin.ch`, `*.admin.ch`, the resource CDN hosts) and
reject any request outside it; back it with a network-layer egress policy in the
Render/container environment. Effort: **M**.

#### SEC-022 — Namespace prefix present, no tool-definition hashing — `partial`

**Observed.** All tools share a consistent `blv_` snake_case namespace prefix
(pass). There is no tool-definition hash check in CI, so a silent change to a
tool's schema/description ("rug pull") would go unnoticed.

**Remediation.** Hash the serialized tool definitions in CI and fail the build
on unexplained changes; record intentional tool-definition changes in the
CHANGELOG. Effort: **S**.

#### SCALE-001 — Streamable HTTP supported, no deployment manifest — `partial`

**Observed.** The server supports `streamable-http` via `--http` (pass), but the
repo ships no Render manifest (`render.yaml`) or `Procfile` — the deployment is
configured only through README prose.

**Remediation.** Add a `render.yaml` (or `Procfile`) pinning the start command,
host, port and transport so cloud deployment is reproducible. Effort: **S**.

#### SCALE-002 / SCALE-003 — No stateful load-balancing / session affinity — `fail`

**Observed.** No sticky-session configuration, shared session store, or
`Mcp-Session-Id`-based LB affinity is defined. Streamable HTTP sessions are
stateful, so a multi-instance deployment would break on cross-instance routing.

**Risk.** Limited while the server runs as a single Render instance; becomes a
correctness bug the moment it is scaled horizontally.

**Remediation.** Document single-instance as a constraint now; when scaling,
add `Mcp-Session-Id` sticky routing (HAProxy stick-tables / cookie affinity) and
a shared session store. Effort: **M** each.

#### OBS-001 — Protocol vs. execution errors handled inconsistently — `partial`

**Observed.** Some tools return execution errors inside the result
(`[{"error": "..."}]` — good), but `r.raise_for_status()` calls let httpx
exceptions propagate as uncaught protocol errors, and
`blv_search_animal_diseases` swallows everything in a bare
`except Exception:` (`server.py:254`). No shared error-code constants.

**Remediation.** Adopt one convention: protocol errors raised, execution errors
returned in the result with defined error-code constants; replace the bare
`except Exception` with targeted handling. Effort: **M**.

#### OBS-002 — Error details not masked toward the LLM — `fail`

**Observed.** `FastMCP(...)` (`server.py:38`) is constructed without
`mask_error_details`. Uncaught `raise_for_status()` / parser exceptions surface
their messages (URLs, status codes, stack context) to the model.

**Remediation.** Enable `mask_error_details=True` on the FastMCP app; log full
detail server-side only. Effort: **S**.

#### OPS-001 — Solid mocked tests, no live-test marker — `partial`

**Observed.** `tests/test_server.py` mocks all HTTP (via `unittest.mock`) and 17
tests pass; CI runs them. The catalog asks specifically for `respx` mocking and
a registered `live` pytest marker for separately-gated live API tests — neither
is present, and the README's "live API checks" command (`README.md:256`) has no
corresponding marked tests.

**Remediation.** Register a `live` marker in `pyproject.toml`, add a small set
of live-API tests behind it, and exclude them from CI. Optionally migrate
mocking to `respx`. Effort: **S**.

#### OPS-003 — Read-only phase not explicitly declared — `partial`

**Observed.** The server is unambiguously Phase 1 (read-only) and behaves so,
but no README phase declaration or roadmap file states this intentionally.

**Remediation.** Declare "Phase 1 — read-only" in the README and add a short
`ROADMAP.md` describing the path to any future write/federation phases.
Effort: **S**.

### Medium (summary)

| ID | Observed | Remediation | Effort |
|---|---|---|---|
| ARCH-002 | Descriptions are adequate length but lack `<use_case>` / `<important_notes>` / `<example>` tags | Add structured use-case tags to tool descriptions | M |
| ARCH-003 | No-match paths return empty lists / `[{"error": ...}]` with no fuzzy fallback or suggestions | Return `{results, match_type, note}` with fuzzy matching + popular-name hints | M |
| ARCH-012 | `protocolVersion` not pinned in `FastMCP(...)`; `CHANGELOG.md` has duplicated `## [1.0.0]` headers with conflicting dates (2026-03-23 / 2026-03-12) and a stray empty `## [Unreleased]`; no Dependabot | Pin `protocolVersion`, repair the CHANGELOG, add Dependabot | S |
| SDK-002 | Tools return bare `dict` / `list[dict]`; pydantic v2 is available but unused for returns | Annotate returns with pydantic v2 models / TypedDict | M |
| SDK-003 | No `ctx: Context` parameter; no progress reporting in long CSV-fetching tools | Inject `Context`, emit progress + logging | M |
| SEC-014 | No MCP-gateway tool allow-listing | Front cloud deployment with a gateway allow-list (enterprise-scope; defer) | L |
| SEC-015 | No pre-flight tool-poisoning detection | Gateway-level detection on `tools/list` (enterprise-scope; defer) | L |
| SCALE-004 | No Dockerfile / multi-stage build | Add multi-stage Dockerfile, non-root user, HEALTHCHECK (shared with SEC-007) | M |
| SCALE-006 | No container resource limits | Set memory/CPU/FD limits in the deployment manifest | S |
| OBS-003 | No logging anywhere — no `logging`/structlog import | Add structured logging (structlog) with RFC 5424 severities, to stderr | M |
| OBS-006 | No OpenTelemetry tracing | Add OTel SDK + OTLP exporter + httpx instrumentation | M |
| CH-004 | Tool returns omit a `source` attribution field (only `blv_get_dataset_info` exposes `license`); README has Data Sources + License sections | Add a `source` / provenance field to tool return payloads (CC BY 4.0 attribution) | M |

---

## Step 6 — Remediation Plan

**Gate 1 — unblock production (must fix before any networked deployment)**

1. **SEC-016** — default bind to `127.0.0.1` (effort S). *Single hard blocker.*
2. **SEC-018** — escape the SPARQL query, clamp all `limit` values, switch to
   `defusedxml` (effort M).
3. **OBS-002** — enable `mask_error_details` (effort S).
4. **SDK-004** — configure CORS for the HTTP transport (effort S).

**Gate 2 — high-priority hardening (next iteration)**

5. SEC-004 + SEC-005 + SEC-021 — combined networking hardening: HTTPS
   enforcement, IP/host allow-list, DNS pinning (effort M, do together).
6. ARCH-009 — add tool annotations (effort S).
7. SDK-001 — shared HTTP client via lifespan (effort S).
8. SEC-007 + SCALE-004 — hardened multi-stage Dockerfile (effort M).
9. ARCH-004 — pydantic-settings configuration object (effort M).
10. OBS-001 / OBS-003 — error-handling convention + structured logging (effort M).
11. SCALE-001 — add a Render deployment manifest (effort S).
12. OPS-001 / OPS-003 — live-test marker; phase declaration + roadmap (effort S).

**Gate 3 — quality & medium findings**

ARCH-002, ARCH-003, ARCH-012, SDK-002, SDK-003, SEC-022, SCALE-006, OBS-006,
CH-004. SEC-014 / SEC-015 are enterprise-gateway controls — defer until an
enterprise deployment context exists.

**SEC-002/009/010/011/012 et al.** become applicable the moment authentication
or write capability is added — re-run the audit on any such scope change.

---

## Step 7 — Release Proposal

**Not applicable.** A release proposal requires no open critical or high
findings. With 3 critical and 16 high findings open, no version bump or tag is
proposed. Re-audit after Gate 1 + Gate 2 remediation.
