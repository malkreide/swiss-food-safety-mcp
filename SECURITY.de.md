# Sicherheitsrichtlinie & Sicherheitsstatus

🌐 **[English](SECURITY.md)** | **Deutsch**

`swiss-food-safety-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet. Dieses Dokument fasst den Sicherheitsstatus zusammen und hält die
**akzeptierten Restrisiken** für jene Kontrollen fest, die bewusst auf der
Portfolio-/Gateway-Ebene statt in diesem einzelnen Server behandelt werden.

## Eine Schwachstelle melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie die in `README.md` genannte Maintainerin. Melden Sie
ausnutzbare Schwachstellen nicht über öffentliche Issues.

## Statusübersicht

Dies ist ein **Nur-Lese-**, **PII-freier**, **Public-Open-Data**-MCP-Server.
Alle 11 Tools stellen ausschliesslich HTTP-GET-/SPARQL-`SELECT`-Anfragen an
eine feste Menge von Schweizer Bundes-Open-Data-Endpunkten (opendata.swiss CKAN,
lindas.admin.ch SPARQL, news.admin.ch RSS — siehe `README.md`). Bereits
umgesetzte Härtung:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS zu einer festen Allow-List von Schweizer Bundes-Hosts (`*.admin.ch`, `opendata.swiss`); keine benutzergesteuerten URLs (SEC-004/021) |
| TLS | Zertifikatsprüfung standardmässig aktiv (httpx-Default); nie deaktiviert (SEC-005) |
| Binding | Standardmässig stdio-Transport; der optionale `--http`-Transport bindet an `127.0.0.1`, sofern nicht explizit `--host 0.0.0.0` gesetzt wird (SEC-016 / SDK-004) |
| Origins | `BLV_MCP_ALLOWED_ORIGINS` (kommagetrennt, kein Wildcard) reguliert Browser-Clients; Standardwert `https://claude.ai` |
| Eingaben | Tool-Eingaben werden gegen das von FastMCP aus Typ-Hints generierte Pydantic-Schema validiert (Typ-Coercion), ergänzt um In-Handler-Clamping/Bounds und SPARQL-Literal-Escaping. Schema-Constraints (`ge`/`le`/`max_length`) und `extra="forbid"` sind ein dokumentierter Gap (SEC-018 — partial) |
| Tools | Jedes Tool setzt `readOnlyHint: True`; es existieren keine Schreib-, Mutations- oder Löschpfade (ARCH) |
| Secrets | Keine erforderlich — der Server nutzt keinen API-Key und keine Credentials; nichts Geheimes wird gespeichert oder geloggt (ARCH-005/SEC-013) |
| Fehler | Upstream-Fehlerbodies werden nur nach stderr geloggt; das Modell erhält eine generische, nicht-leckende Meldung (OBS-002) |
| Stdout | Reserviert für den JSON-RPC-Stream; sämtliches Logging auf stderr gepinnt (OBS-004) |
| Resilienz | Ein 30s-Timeout pro Anfrage (`BLV_MCP_TIMEOUT`) begrenzt jeden Upstream-Aufruf (SCALE-002/003) |

Das Audit und seine Reruns (siehe `docs/audit/`) reduzierten die Findings von 31
(3 Critical, 16 High, 12 Medium) im Erstlauf auf 5 im zweiten Reaudit, wobei
**26 Findings geschlossen** wurden. Die verbleibenden Punkte sind entweder
akzeptierte Restrisiken (unten) oder inhärent zum bewussten No-Auth-, Nur-Lese-,
Public-Data-Design. Die Härtungshistorie steht in `CHANGELOG.md`.

## Aktuelle Audit-Scorecard

Re-Audit gegen den MCP-Best-Practice-Katalog (Skill v1.0.0) am 2026-07-26.
Vollständige Scorecard, Evidenz pro Check und Findings unter
[`audits/2026-07-26T094927-Z-swiss-food-safety-mcp/`](audits/2026-07-26T094927-Z-swiss-food-safety-mcp/).

| Kennzahl | Wert |
|---|---|
| Anwendbare Checks | 40 |
| Pass | 25 |
| Partial | 15 |
| Fail | 0 |
| Blockierend (Critical/High-Fails) | 0 |
| **Produktionsreif** | **ja** |

Es gibt keine fehlgeschlagenen Checks. Die 15 Partials sind Verbesserungspunkte
oder dokumentierte akzeptierte Restrisiken; keiner blockiert die Produktion.
Offene (nicht akzeptierte) Kernpunkte: SEC-005 (DNS-Pinning), SEC-018
(Schema-Constraints), SEC-021 (Network-Layer-Egress + Doku), OPS-001 (respx-Tests
+ Live-Tests pro Tool), ARCH-005 (`.gitignore`/`.env.example`/CI-Secret-Scan-Hygiene)
und ARCH-012 (`protocolVersion`-Pinning). Akzeptierte Restrisiken (SEC-009,
SEC-014, SEC-015, SCALE-002, SCALE-003) bleiben wie im Abschnitt unten.

## Akzeptierte Restrisiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Audit-Checks sind bewusst **nicht** innerhalb dieses Servers
umgesetzt. Es handelt sich um portfolioweite Belange, die am besten auf einer
MCP-Gateway-/Host-Ebene durchgesetzt werden; das Restrisiko ist hier gering,
weil der Server nur lesend arbeitet und nur eine kleine Menge vertrauenswürdiger
Schweizer Bundes-Open-Data-Anbieter erreicht.

### SEC-009 — Keine Authentifizierung auf dem HTTP-Transport

**Status:** akzeptiertes Risiko — inhärent zum No-Auth-Design.
Dieser Server folgt bewusst einer **No-Auth-First**-Philosophie: Er stellt nur
Nur-Lese-Abfragen auf öffentliche Open Data bereit und speichert keine Secrets
oder PII. Es gibt daher kein Authentifizierungsmodell, das umgangen werden
könnte, und keinen praktischen Impact. Falls jemals ein Authentifizierungsmodell
hinzukommt, müssen gebundene, TTL-versehene, serverseitig invalidierbare
Session-IDs implementiert und der Server vor dem Merge neu auditiert werden.

### SEC-014 — Tool-Allow-Listing über ein MCP-Gateway

**Status:** akzeptiertes Risiko (Portfolio-Ebene).
Eine Tool-bezogene Allow-List gehört zum MCP-Host/-Gateway, das mehrere Server
aggregiert, nicht zu einem einzelnen Server mit festem, nur lesendem Tool-Set.
Sobald ein zentrales Gateway für das Portfolio eingeführt wird, sollte das
Tool-Allow-Listing dort konfiguriert werden. Bis dahin ist das Risiko begrenzt:
Jedes Tool ist nur lesend und auf die obigen festen Endpunkte beschränkt.

### SEC-015 — Pre-Flight-Erkennung von Tool-Poisoning

**Status:** akzeptiertes Risiko (Portfolio-Ebene) — mit lokaler Absicherung.
Tool-Poisoning (bösartige Tool-Beschreibungen / Rug-Pulls) ist ein
Supply-Chain- und Host-seitiges Thema. Die Tool-Definitionen dieses Servers sind
versionskontrolliert, im Repo verfasst und via PR reviewt; es gibt keine
dynamische oder entfernte Tool-Registrierung, und die Tool-Hashes sind in
`tools/tool-hashes.json` fixiert. Server-übergreifende Poisoning-Erkennung bleibt
eine Gateway-/Host-Verantwortung auf Portfolio-Ebene.

## Trigger für eine Neubewertung

Diese Akzeptanzen sollten neu bewertet werden, falls der Server jemals:

- **Schreib**-Fähigkeit erhält oder **PII** verarbeitet, oder
- ein **Authentifizierungs**-Modell erhält (dann gebundene, TTL-versehene,
  serverseitig invalidierbare Session-IDs implementieren und vor dem Merge neu
  auditieren), oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann das
  Tool-Allow-Listing und die Tool-Poisoning-Erkennung des Gateways aktivieren).
