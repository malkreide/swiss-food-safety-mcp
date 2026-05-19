# Roadmap

swiss-food-safety-mcp follows the phased MCP server architecture — read-only
first, then write, then multi-agent (audit finding OPS-003).

## Phase 1 — Read-only (current)

All 11 tools are read-only queries against official Swiss federal open data.
No authentication, no write operations, no side effects. This is the current
and intended state of the server.

## Phase 2 — Federation (not planned here)

Cross-referencing with related Swiss public-sector MCP servers (e.g.
`fedlex-mcp`, `zurich-opendata-mcp`) belongs at the MCP host/client level, by
combining servers — not inside this server. No write capability is planned.

## Phase 3 — Write / multi-agent (out of scope)

The BLV data sources are read-only open data; there is no write surface to
expose. Should that ever change, it would require a fresh security audit
(authentication model, idempotency keys, human-in-the-loop confirmation)
before any write-capable tool ships.

## Scaling

The Streamable HTTP transport keeps per-session state, so the server is
designed to run as a **single instance**. Horizontal scaling would require:

- `Mcp-Session-Id` sticky routing at the load balancer (audit finding SCALE-003), and
- a shared session store across instances (audit finding SCALE-002).

Neither is implemented — by design, for a server of this scope. A single
Render instance, or one container, is the supported deployment. Container
resource limits for self-hosting are defined in `docker-compose.yml`.
