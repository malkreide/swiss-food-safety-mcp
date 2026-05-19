# MCP Re-Audit Report #2 — swiss-food-safety-mcp

| | |
|---|---|
| **Run-ID** | `2026-05-19T173000+0200-swiss-food-safety-mcp-reaudit-2` |
| **Audit date** | 2026-05-19 |
| **Skill** | `malkreide/mcp-audit-skill` (catalog `main`, 68 checks) |
| **Audited revision** | `main` (Gates 1–4 merged: PRs #2, #3, #4, #10) |
| **Prior runs** | initial `2026-05-19-swiss-food-safety-mcp.md`; re-audit #1 `2026-05-19-reaudit-swiss-food-safety-mcp.md` |

---

## Executive Summary

Third pass of the `mcp-audit-skill` audit, after Gate 4 closed the remaining
scaling and phase-architecture findings. Result: **39 pass · 3 partial · 2
fail** of 44 applicable checks — **5 findings: 1 critical · 0 high · 4
medium**.

**No high-severity finding remains open.** The server is **production-ready**.
The single critical finding (SEC-009) is a `partial` with documented nil
practical impact for this no-auth, read-only, public-data profile.

### Trend across all three runs

| | Initial | Re-audit #1 | Re-audit #2 |
|---|---|---|---|
| pass / partial / fail | 13 / 12 / 19 | 35 / 5 / 4 | **39 / 3 / 2** |
| Critical findings | 3 | 1 | **1** (partial) |
| High findings | 16 | 3 | **0** |
| Medium findings | 12 | 5 | **4** |
| **Total findings** | **31** | **9** | **5** |

---

## Step 4 — Verification Results

44 of 68 checks applicable. **39 pass · 3 partial · 2 fail.**

### Resolved since re-audit #1 (4)

| Check | Was | Now | Fix (PR #10) |
|---|---|---|---|
| SCALE-002 | fail (high) | **pass** | Single-instance constraint documented (`ROADMAP.md`, README) — the audit's sanctioned current-state resolution |
| SCALE-003 | fail (high) | **pass** | `Mcp-Session-Id` affinity requirement documented as a scaling prerequisite |
| OPS-003 | partial (high) | **pass** | `ROADMAP.md` declares the read-only Phase 1 architecture; README "Deployment & Scaling" section |
| SCALE-006 | partial (medium) | **pass** | `docker-compose.yml` with explicit `cpus` / `memory` limits and reservations |

### Still open (5 findings)

| ID | Severity | Status | Notes |
|---|---|---|---|
| SEC-009 | critical | partial | Sessions not bound to a user identity. Inherent to the no-auth design; on a read-only public-data server a hijacked session grants no privilege and exposes no confidential data — **nil practical impact**. No action needed unless authentication or write capability is added. |
| SEC-014 | medium | fail | MCP-gateway tool allow-listing — deferred (enterprise-context control, not meaningful for this deployment). |
| SEC-015 | medium | fail | Pre-flight tool-poisoning detection — deferred (enterprise-context control). |
| ARCH-002 | medium | partial | Tool descriptions carry use-case prose, but not the literal `<use_case>` / `<important_notes>` tag convention. Low value; left as-is. |
| ARCH-003 | medium | partial | No-match paths return a structured `code` + remediation `note`, but no fuzzy-match `match_type` heuristic. |

---

## Step 6 — Findings Summary

**5 findings: 1 critical (partial) · 0 high · 4 medium.** Down from 31 at the
initial audit. 26 of the 31 original findings are fully resolved; the 5 that
remain are all either inherent to the server's deliberate no-auth design
(SEC-009), enterprise-only controls out of scope for this deployment
(SEC-014, SEC-015), or low-value convention polish (ARCH-002, ARCH-003).

---

## Step 7 — Release Proposal

No high-severity finding is open. The audit's strict release gate ("no open
critical/high findings") is met **except** for SEC-009, which is critical by
catalog severity but a `partial` with documented nil practical impact for a
no-auth, read-only, public-data server.

**Recommendation: the server is ready for a `1.1.0` release.** This requires
one human decision — formally accepting SEC-009 as a known, no-impact item for
this profile (it cannot be "fixed" without adding an authentication model the
server intentionally does not have). With that accepted:

1. Bump the version to `1.1.0` in `pyproject.toml`, `__init__.py` and the
   `SERVER_VERSION` constant.
2. Promote the CHANGELOG `[Unreleased]` section to `[1.1.0]`.
3. Tag and publish (the existing `publish.yml` handles PyPI via OIDC).

SEC-014 / SEC-015 stay deferred until an enterprise deployment context exists.
ARCH-002 / ARCH-003 are optional polish and do not block a release.
