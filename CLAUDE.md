# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — dieses Repo

**ruff:** genau eine Quelle — `ruff==0.16.1` im `[dev]`-Extra von
`pyproject.toml`. Ein dev-Install reicht also, lokal wie in der CI. Keine
zweite Version in die Workflows schreiben: ein solcher Schritt läuft nach dem
Install und überstimmt den Pin still (`ci.yml` hatte einen;
`test_werkzeug_versionen.py` hält beides fest). Eine `.pre-commit-config.yaml`
gibt es nicht.

**Gates, wörtlich aus der CI:**

```bash
python -m py_compile src/swiss_food_safety_mcp/server.py
python -c "from swiss_food_safety_mcp.server import mcp; print('Import OK')"
pytest tests/ -v -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
```

Die ruff-Gates laufen zweimal: im Job `test` und noch einmal im Job `lint`.
**Der `lint`-Job installiert das Projekt** — er muss es, sonst fehlt ihm ruff;
er hatte früher nur einen eigenen `pip install ruff==…`. Kein `include` unter
`[tool.ruff]` setzen — der Umfang stimmt (9 Dateien über alle drei
Verzeichnisse, nachgemessen; eine Sonde in `tests/` lässt beide Gates fallen).

**Live-Tests:** eigener Job in `ci.yml`, wöchentlich per Cron (`33 5 * * 1`, montags).
Der Lauf wird eingeordnet statt am Exit-Code gemessen; ein Befund öffnet oder
schliesst ein Issue. DRIFT-005 ist erfüllt.
