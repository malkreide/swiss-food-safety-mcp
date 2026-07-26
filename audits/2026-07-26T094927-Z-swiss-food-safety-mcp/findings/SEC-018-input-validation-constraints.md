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
