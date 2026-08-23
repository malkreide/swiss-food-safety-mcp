# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`allow_headers` stand auf `["*"]`.** Der Kommentar daneben versprach «no
  wildcard» — er galt den Origins; die Header-Liste war eine. Starlette
  schaltet damit auf `allow_all_headers` und spiegelt im Preflight zurück, was
  der Browser ankündigt, also durfte jeder gelistete Origin jeden beliebigen
  Header senden. Die Liste nennt jetzt `Content-Type`, `Mcp-Session-Id` und
  `Last-Event-ID`. Letzterer setzt einen abgerissenen SSE-Strom fort und war
  unter der Wildcard nie geprüft: eine Wildcard kann nicht falsch werden.

  Die Routing-Header der Spec `2026-07-28` stehen bewusst **nicht** darauf.
  fastmcp 3.x pinnt `mcp` 1.x, wo es `mcp.shared.inbound` nicht gibt und
  niemand sie liest. Der zugehörige Test ist an das SDK gebunden statt an eine
  Notiz und fällt, sobald ein Upgrade das Modul hereinzieht.

### Changed

- **`build_cors_middleware` und `build_http_app` aus `main` herausgezogen.**
  Solange die Freigabeliste neben `mcp.run` stand, liess sie sich nur lesen,
  nicht ausprobieren — und eine Liste, die richtig aussieht, kann trotzdem nie
  an der Middleware ankommen. `main` reicht dasselbe Objekt an `mcp.run`
  weiter; am Verhalten ändert sich nichts.

### Hinzugefuegt

- **SessionStart-Hook, der den Rueckstand des Klons meldet**
  (`.claude/hooks/session-start.sh`, registriert in `.claude/settings.json`).
  Liegt der ausgecheckte Stand hinter `origin/<Default-Branch>`, sagt er beim
  Sessionstart wie viele Commits fehlen; liegt er nicht zurueck, schweigt er.

  Grund: Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt,
  deren Ursache nicht im Diff stand — die fehlenden Commits waren jeweils
  genau die, die das Gate einfuehrten, an dem der Branch scheiterte. Man sucht
  den Fehler dann in den Dateien, die man selbst geaendert hat, und findet
  dort nichts. Die Pruefung kostet eine Sekunde.

  Die oberste Zusicherung ist nicht die Meldung, sondern dass der Hook die
  Session **nie** blockiert: kein Netz, kein Remote, kein Git-Repo, detached
  HEAD, fehlende Credentials — alles endet still mit Exit 0, das `fetch` unter
  einem 5-Sekunden-`timeout`. Ein Hook, der bei Netzproblemen die Arbeit
  anhaelt, wird nach dem zweiten Mal abgeschaltet und schuetzt danach gar
  nichts. Deshalb steht im Skript bewusst kein `set -e`.

  Der Default-Branch wird ermittelt (lokaler Symref, ersatzweise
  `ls-remote --symref`), nicht als `main` angenommen: Drei Server im Portfolio
  heissen ihn `master`, und genau diese Annahme hat schon einmal einen Branch
  15 Commits alt werden lassen.

  `tests/test_session_start_hook.py` prueft das gegen echte Wegwerf-Repos, die
  absichtlich auf `master` stehen — gegen ein `main`-Repo waere ein Hook mit
  hartkodiertem `main` von einem korrekten nicht zu unterscheiden. Die
  Gegenprobe hat dabei zwei Fehler in den Tests selbst aufgedeckt:
  `git update-ref -d` dereferenziert Symrefs und loeschte
  `refs/remotes/origin/master` statt `origin/HEAD`, und das haengende
  Ersatz-git erkannte `fetch` nur als `$1` — im Zweig ohne `timeout` steht
  dort `-c`. Beide Tests waren gruen und prueften nichts.

### Entfernt

- **`dist/` mit Wheels der Version 1.1.3 aus der Versionskontrolle
  genommen.** Committete Build-Artefakte, zwei Versionen hinter dem Stand
  von `pyproject.toml` (1.1.5). Wer das Repo klont, bekommt sie mit — und
  hat damit ein Paket im Baum, das nicht dem Quelltext daneben entspricht.

  Vor dem Loeschen geprueft, nicht angenommen: Beide Dateien liegen auf PyPI
  unter derselben Version, und die SHA-256-Summen sind **byte-identisch** mit
  den lokalen. Es geht also nichts verloren, und ein `python -m build`
  erzeugt sie ohnehin neu. Kein Verweis im Repo zeigte auf sie.

  `dist/` stand bereits in der `.gitignore` — die entfernt aber nur, was noch
  nicht getrackt ist.


### Behoben

Sieben der elf Werkzeuge wurden am 2026-08-08 zum ersten Mal gegen ihre
Quellen getrieben. Sechs gaben etwas anderes aus, als sie versprachen — und
keines sah dabei nach einem Fehler aus.

- **`blv_search_animal_diseases` hat nie Daten geliefert.** Zwei Fehler
  hintereinander:

  Der SPARQL-Endpunkt war `https://lindas.admin.ch/sparql` — die
  Editor-Oberflaeche. Sie beantwortet GET mit HTTP 200 und `text/html`, POST
  mit 404. Der Abfrage-Endpunkt ist `/query`; der Datensatz bei opendata.swiss
  sagt das selbst, in seiner SPARQL-Ressource steht
  `endpoint=https://lindas.admin.ch/query`. Kontrolle: Ein erfundener Pfad
  unter demselben Host antwortet ebenfalls mit 404, der Befund ist also echt.

  Die Abfrage traf ausserdem die Klasse
  `agriculture.ld.admin.ch/foag/ontology/AnimalDisease`. Die hat **null**
  Instanzen — genau so viele wie eine frei erfundene Klasse, die als Kontrolle
  mitgemessen wurde. Der Namensraum heisst `fsvo`, die Daten liegen als Cube
  vor (57'997 Beobachtungen), und jedes einzelne Praedikat war ein anderes.

  Beides fiel in ein `except Exception` und von dort auf den CSV-Pfad — der an
  einer als `format: CSV` deklarierten ZIP-Datei scheiterte, mit der Meldung
  «new-line character seen in unquoted field». Aus zwei Adressfehlern wurde so
  eine Meldung ueber Zeilenumbrueche.

  Die Abfrage kommt jetzt aus dem Datensatz selbst. Der CSV-Fallback ist
  entfallen: Ein Fallback, der eine kaputte Abfrage verdeckt, ist schlechter
  als keiner.

- **`blv_get_animal_health_stats` gab Antibiotikadaten aus.** Die
  Stichwortsuche «tiergesundheit statistik» traf als ersten Treffer
  `antibiotikaeinsatz-in-der-veterinarmedizin`; `tiergesundheitsstatistik`
  stand auf Platz 3. Zwei Werkzeuge lieferten damit **dieselbe Datei**, und
  fuer eines davon war es die falsche.

- **`blv_get_food_control_results` gab eine Code-Legende aus.** Der Datensatz
  `lebensmittelkontrolle` fuehrt 26 Ressourcen, davon **18 Code-Listen**. «Die
  erste CSV» war «Food establishments codelist administrative measures» — eine
  Liste von Verwaltungsmassnahmen-Codes, ausgegeben als
  Inspektionsergebnisse. Jetzt kommt die neueste Jahresdatei der
  Betriebskontrollen, mit Kanton, Datum, Inspektionsgrund und Benotung.

- **`blv_get_avian_influenza` gab die Feldbeschreibung statt der Daten aus.**
  JSON wurde vor CSV bevorzugt, und die einzige JSON-Ressource ist das
  Frictionless-`datapackage.json`. Zurueck kam
  `{"profile": "tabular-data-package", "resources": [...]}` — eine Antwort mit
  null Faellen darin.

- **`blv_get_meat_inspection_stats` gab eine falsch zerlegte Code-Liste aus.**
  Die Datei ist semikolongetrennt, `csv.DictReader` nahm das Komma, und die
  ganze Zeile landete unter einem einzigen Schluessel:
  `{'\\ufeffID;DE;FR;IT;EN': 'cp1;Kontaminanten;…'}`. Formal ein gueltiges
  Ergebnis.

- **Der UTF-8-BOM stand im Namen der ersten Spalte.** Gelesen wurde
  `response.text`; die BLV-Dateien beginnen mit einem BOM, aus `Year` wurde
  `\\ufeffYear`. Jeder Filter auf `Year` oder `Jahr` lief damit still ins Leere
  und meldete «keine Treffer».

- **`blv_get_nutrition_data_children` versprach Naehrwerte und lieferte
  Fragebogenauszaehlungen.** Der Docstring nannte «nutrient intake by age group
  against dietary recommendations» und bot «Energie», «Zucker», «Eisen» als
  Filterbeispiele. Der einzige menuCH-Kids-Datensatz auf opendata.swiss fuehrt
  Antwortzahlen: `Geschlecht, Sprachregion, Altersgruppe, Frage, Antwort,
  Anzahl`. Ein Filter auf «Eisen» traf nichts und gab eine leere Liste
  zurueck — nicht zu unterscheiden von «fuer diese Altersgruppe gibt es
  nichts».

  Der Docstring nennt jetzt, was das Werkzeug liefert, und der Parameter heisst
  `answer_code` statt `nutrient`. Naehrwertdaten fuer Erwachsene liegen als
  eigener Datensatz vor; ihn hier anzuflanschen waere eine Erfindung.

### Geaendert

- **Datensaetze und Ressourcen sind gepinnt, nicht gesucht** (`DATENQUELLEN`).
  «Der erste Suchtreffer» und «die erste Ressource dieses Formats» sind keine
  Auswahlregeln, sondern Wetten darauf, wie opendata.swiss sortiert — und beide
  Wetten gingen verloren. Ein Stichwortsuchlauf hat zudem die Eigenschaft,
  still auf etwas Plausibles zurueckzufallen; ein gepinnter Slug, den es nicht
  mehr gibt, faellt auf.

  `_daten_ressource()` meldet eine fehlende Ressource als `UpstreamShapeError`
  und nennt dabei, was stattdessen da war. `blv_search_pesticide_products`
  sucht weiterhin — dort ist es bewusst, und der strukturierte Fehler bleibt.

### Hinzugefuegt

- **Aufgezeichnete Messungen** — `scripts/record_fixtures.py`,
  `tests/fixtures/` und ein `PROVENANCE.md` mit Quelle, Datum, Auswahlregel und
  SHA-256 je Datei.

  Aufgezeichnet ist nicht der Datensatz, sondern die **Auswahl**: je Werkzeug
  der gepinnte Slug, die getroffene Ressource und deren Kopfzeile. Die
  Kopfzeile ist der Gegenstand — sie trennt Daten von einer Legende und zeigt,
  ob BOM und Trennzeichen stimmen.

  Der Anlass steht in einer Zeile: Die Mocks nannten jede CKAN-Ressource
  `"name": "CSV"`. Bei der Quelle heisst dasselbe Feld «Food establishments
  2025» oder «Food establishments codelist administrative measures», und genau
  dieser Unterschied entschied ueber die Antwort. Die Mocks konnten die
  Unterscheidung nicht ausdruecken, also konnte kein Test daran scheitern.

  Zwei der Messungen sind **Kontrollen**: ein erfundener Pfad unter
  `lindas.admin.ch` und eine erfundene Klasse im `fsvo`-Namensraum. Ohne sie
  belegte die Messung nur, was ich bekommen habe.

- **`tests/test_datenauswahl.py`** — 21 Tests, die **in** der CI laufen. Dieses
  Repo hatte einen einzigen Live-Test fuer elf Werkzeuge, und der pruefte
  keines davon.

  Gegengeprueft mit sechs gezielten Rueckmutationen: SPARQL-Endpunkt zurueck,
  erste Ressource statt gepinnter, Stichwortsuche statt Pinning, BOM nicht
  entfernen, Trennzeichen fest auf Komma, ZIP-Wache entfernen. Alle sechs
  machen die Suite rot.

## [1.1.5] - 2026-07-31

### Behoben

- **Der User-Agent meldete auch nach 1.1.4 noch 1.1.0.** Der Umbau auf
  `importlib.metadata` endete seinerzeit in `__init__.py`; `server.py` pflegte
  daneben ein eigenes `SERVER_VERSION = "1.1.0"` und speiste damit den
  User-Agent, die Ready-Zeile im Log und das `version=`-Feld des MCP-Servers.
  Der Fix galt als erledigt und erreichte die drei nach aussen sichtbaren
  Stellen nie. Am veroeffentlichten 1.1.4 nachgemessen: installiert 1.1.4,
  gesendet `swiss-food-safety-mcp/1.1.0`.

  `SERVER_VERSION` liest jetzt `__version__` — ein Wert statt zwei.

  Warum es niemandem auffiel: der zweite Name. Der Versions-Sync-Check und die
  Identity-Probe suchen beide nach `__version__` oder einem
  `"name/version"`-Literal; eine Konstante namens `SERVER_VERSION` passt auf
  keins von beidem, und beide meldeten dieses Repo als sauber. Ein Sweep ueber
  alle 33 Portfolio-Repos zeigt, dass nur dieser Server diese Form hat.

## [1.1.4] - 2026-07-31

### Behoben

- **User-Agent meldet wieder die tatsaechliche Paketversion.** Das auf PyPI
  veroeffentlichte `1.1.3` sendete gegenueber jedem Upstream
  `swiss-food-safety-mcp/1.1.0`; die Version stammt jetzt aus den
  Paket-Metadaten und kann nicht mehr getrennt vom Paket driften. Der Umbau lag
  unveroeffentlicht auf `main` — unter derselben Nummer 1.1.3, die PyPI bereits
  auslieferte, weshalb dieser Bump noetig ist.

## [1.1.0] - 2026-05-19

Hardening release — resolves the `mcp-audit-skill` audit findings (see
`docs/audit/`). 26 of 31 findings closed across four remediation gates; no
high-severity finding remains open.

### Security
- HTTP transport now binds to `127.0.0.1` by default instead of `0.0.0.0`;
  external exposure requires an explicit `--host 0.0.0.0` (audit finding SEC-016).
- `blv_search_animal_diseases` escapes caller-supplied `canton`/`disease` values
  before SPARQL interpolation, preventing query injection (SEC-018).
- XML feeds are parsed with `defusedxml` instead of the standard library,
  mitigating XML entity-expansion attacks (SEC-018).
- Result-limit parameters are clamped to documented maximums (SEC-018).
- Error details are masked toward the model via `mask_error_details` (OBS-002).
- Outbound requests are SSRF-guarded: HTTPS-only, restricted to an immutable
  egress allow-list of Swiss federal hosts, with public-IP and redirect-target
  validation (audit findings SEC-004, SEC-005, SEC-021).
- CI verifies a SHA-256 hash of the tool definitions against a committed
  baseline, detecting unintended tool-definition changes (SEC-022).

### Added
- CORS configuration for the HTTP transport exposing the `Mcp-Session-Id`
  header, with an explicit `BLV_MCP_ALLOWED_ORIGINS` env var (SDK-004).
- All tools now carry MCP annotations (`readOnlyHint`, `idempotentHint`,
  `openWorldHint`) (audit finding ARCH-009).
- Multi-stage, non-root `Dockerfile` with a healthcheck (SEC-007, SCALE-004).
- Structured logging to stderr (audit finding OBS-003).
- Optional OpenTelemetry tracing, enabled via `BLV_MCP_OTEL_ENDPOINT` and the
  `otel` install extra (audit finding OBS-006).
- Provenance attribution (`source` / `license`) on structured tool results
  (audit finding CH-004).
- A `live` pytest marker for tests that hit live APIs, excluded from CI
  (audit finding OPS-001).
- `render.yaml` Render Blueprint for reproducible cloud deployment (SCALE-001).
- Dependabot configuration for weekly dependency updates (ARCH-012).
- `ROADMAP.md` declaring the read-only Phase 1 architecture and the
  single-instance scaling constraint (audit findings OPS-003, SCALE-002,
  SCALE-003).
- `docker-compose.yml` with explicit CPU/memory limits for self-hosted
  deployment (audit finding SCALE-006).

### Changed
- Configuration moved to a `pydantic-settings` `Settings` object; all settings
  are overridable via `BLV_MCP_*` environment variables (audit finding ARCH-004).
- The HTTP client is now created once via a FastMCP lifespan and pooled across
  requests instead of being recreated per call (audit finding SDK-001).
- Structured tool results use typed shapes (`TypedDict`); tools accept an
  optional `Context` for progress reporting and logging (SDK-002, SDK-003).
- Execution errors now carry a stable `code` and a remediation `note`
  (audit findings OBS-001, ARCH-003).
- The `fastmcp` dependency is pinned to `>=3.0.0,<4.0.0` (ARCH-012).

## [1.0.0] - 2026-03-23

### Added
- Initial release
- 11 tools covering all major BLV open data domains:
  - `blv_get_public_warnings` — Live RSS feed for food recalls & health warnings
  - `blv_list_datasets` — Browse all 28 BLV datasets on opendata.swiss
  - `blv_get_dataset_info` — Dataset metadata and resource URLs
  - `blv_search_animal_diseases` — Notifiable animal diseases since 1991 (SPARQL + CSV fallback)
  - `blv_get_animal_health_stats` — Annual animal health statistics
  - `blv_get_food_control_results` — Cantonal food inspection results
  - `blv_get_antibiotic_usage_vet` — Veterinary antibiotic usage (ISABV)
  - `blv_get_avian_influenza` — Wild bird avian influenza surveillance with geodata
  - `blv_get_nutrition_data_children` — Children's nutrition survey (menuCH-Kids)
  - `blv_search_pesticide_products` — Swiss approved pesticide register (XML + CSV)
  - `blv_get_meat_inspection_stats` — Slaughterhouse inspection statistics
- 2 resources: `blv://datasets/overview`, `blv://warnings/current`
- 2 prompts: `prompt_food_safety_analysis`, `prompt_animal_disease_report`
- Dual transport: stdio (default) + Streamable HTTP (`--http`, port 8002)
- No authentication required (No-Auth-First philosophy)
- Bilingual documentation (English primary, German secondary)
- GitHub Actions CI: Python 3.11–3.13 matrix
