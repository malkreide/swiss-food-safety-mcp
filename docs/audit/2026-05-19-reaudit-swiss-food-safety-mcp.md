# MCP Re-Audit Report — swiss-food-safety-mcp

| | |
|---|---|
| **Run-ID** | `2026-05-19T160000+0200-swiss-food-safety-mcp-reaudit` |
| **Audit date** | 2026-05-19 |
| **Skill** | `malkreide/mcp-audit-skill` (catalog `main`, 68 checks) |
| **Audited revision** | `main` @ `4b9efeb` (Gates 1–3 merged: PRs #2, #3, #4) |
| **Baseline** | initial audit `2026-05-19-swiss-food-safety-mcp.md` |

---

## Executive Summary

This is the second pass of the `mcp-audit-skill` audit, after the three
remediation gates were merged. The server has improved markedly: of the **31
findings** in the initial audit, **22 are fully resolved** and the remaining
**9 are open** (several downgraded from `fail` to `partial`). The re-audit
result is **1 critical · 3 high · 5 medium** — down from 3 / 16 / 12.

**Production-ready: YES, for the intended single-instance deployment.** No
production-blocking `fail` at critical severity remains. The one critical
finding (SEC-009) is a `partial` with documented nil practical impact for this
no-auth, read-only, public-data profile. **Caveat:** the two open `high`
findings (SCALE-002, SCALE-003) mean the server must **not** be horizontally
scaled until session affinity is in place — a single Render instance is fine.

### Honest note on remediation scope

Four findings named in the initial audit's remediation plan were **not**
implemented by any gate and remain open: **SCALE-002, SCALE-003** (high),
**SCALE-006, OPS-003**. They fell between the gate scopes. The earlier
session claim of "29 resolved" was inaccurate — the verified figure is **22
resolved, 9 open**.

---

## Step 1 — Profile Snapshot (unchanged)

| Field | Value |
|---|---|
| Transport | dual (stdio default, Streamable HTTP via `--http`) |
| Auth-Model | none |
| Data Class | Public Open Data |
| Write Access | read-only |
| Deployment | local-stdio + Render.com (now with `Dockerfile` + `render.yaml`) |
| SDK language | Python (fastmcp `>=3,<4`) |

---

## Step 4 — Verification Results

44 of 68 checks applicable (filter unchanged). **35 pass · 5 partial · 4 fail.**

### Resolved since the initial audit (22)

| Check | Was | Now | Fix |
|---|---|---|---|
| SEC-016 | fail (critical) | **pass** | HTTP binds `127.0.0.1` by default |
| SEC-004 | partial (critical) | **pass** | SSRF guard: HTTPS + egress allow-list + public-IP check |
| ARCH-009 | fail (high) | **pass** | All tools annotated readOnly/idempotent/openWorld |
| ARCH-004 | partial (high) | **pass** | `pydantic-settings` Settings object |
| SDK-001 | fail (high) | **pass** | Pooled HTTP client via FastMCP lifespan |
| SDK-004 | fail (high) | **pass** | CORS middleware exposes `Mcp-Session-Id` |
| SEC-005 | fail (high) | **pass** | Allow-list defeats rebinding; public-IP validation |
| SEC-007 | fail (high) | **pass** | Multi-stage non-root Dockerfile + healthcheck |
| SEC-018 | fail (high) | **pass** | SPARQL escaping, `defusedxml`, limit clamping |
| SEC-021 | fail (high) | **pass** | Immutable egress allow-list (frozenset) |
| SEC-022 | partial (high) | **pass** | Tool-definition SHA-256 baseline + CI check |
| SCALE-001 | partial (high) | **pass** | `render.yaml` Render Blueprint |
| OBS-001 | partial (high) | **pass** | Error codes + logged fallback handling |
| OBS-002 | fail (high) | **pass** | `mask_error_details=True` |
| SDK-002 | partial (medium) | **pass** | `TypedDict` result shapes |
| SDK-003 | fail (medium) | **pass** | `Context` injection + progress reporting |
| ARCH-012 | fail (medium) | **pass** | CHANGELOG repaired, version set, Dependabot, pinned deps |
| SCALE-004 | fail (medium) | **pass** | Multi-stage Docker build |
| OBS-003 | fail (medium) | **pass** | Stderr logging (stdlib `logging`, leveled) |
| OBS-006 | fail (medium) | **pass** | Opt-in OpenTelemetry tracing (`otel` extra) |
| CH-004 | partial (medium) | **pass** | `source` / `license` provenance on structured results |
| OPS-001 | partial (high) | **pass** | `live` pytest marker; CI runs `-m "not live"` |

### Still open (9 findings)

| ID | Severity | Status | Notes |
|---|---|---|---|
| SEC-009 | critical | partial | Sessions not bound to a user identity. Inherent to the no-auth design; on a read-only public-data server a hijacked session grants no privilege and exposes no confidential data — **nil practical impact**. Not a production blocker for this profile. |
| SCALE-002 | high | **fail** | No stateful load balancing / shared session store. **Not addressed.** Breaks correctness only under multi-instance scaling. |
| SCALE-003 | high | **fail** | No `Mcp-Session-Id` edge-LB affinity. **Not addressed.** Same scope as SCALE-002. |
| OPS-003 | high | partial | Server is unambiguously Phase 1 (read-only) but no explicit phase declaration / `ROADMAP.md`. **Not addressed.** Documentation-only gap. |
| SEC-014 | medium | fail | MCP-gateway tool allow-listing — deferred (enterprise-context control). |
| SEC-015 | medium | fail | Pre-flight tool-poisoning detection — deferred (enterprise-context control). |
| SCALE-006 | medium | partial | No explicit container resource limits. `render.yaml` `plan: free` implies platform limits but sets none explicitly. |
| ARCH-002 | medium | partial | Tool descriptions carry use-case prose, but not the literal `<use_case>` / `<important_notes>` tag convention. |
| ARCH-003 | medium | partial | No-match paths now return a structured `code` + remediation `note`, but no fuzzy-match `match_type` heuristic. |

---

## Step 6 — Findings Summary

| Severity | Initial audit | Re-audit |
|---|---|---|
| Critical | 3 | 1 (partial, nil impact) |
| High | 16 | 3 |
| Medium | 12 | 5 |
| **Total** | **31** | **9** |

---

## Step 7 — Release Proposal

The skill gates a release on zero open critical/high `fail` findings. Two high
`fail` findings remain (SCALE-002, SCALE-003), so a **release is not yet
proposed**. However, these only affect horizontally-scaled deployments.

**Recommendation:** for the documented single-instance Render / local
deployment the server is production-ready now. To clear a formal release:

1. **SCALE-002 / SCALE-003** — document single-instance as a constraint, or
   add `Mcp-Session-Id` sticky routing + a shared session store before scaling.
2. **OPS-003** — declare "Phase 1 — read-only" in the README and add a
   `ROADMAP.md` (effort: S).
3. **SCALE-006** — set explicit memory/CPU limits in `render.yaml` (effort: S).
4. **ARCH-002 / ARCH-003** — optional polish (literal use-case tags, fuzzy
   match heuristics).
5. **SEC-009** — no action needed unless auth or write capability is added.
6. **SEC-014 / SEC-015** — keep deferred until an enterprise deployment exists.
