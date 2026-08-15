# Mitwirken an swiss-food-safety-mcp

🌐 **[English](CONTRIBUTING.md)** | **Deutsch**

Vielen Dank für Ihr Interesse an einem Beitrag! Dieser Server ist Teil des
[Swiss Public Data MCP Portfolios](https://github.com/malkreide).

---

## Probleme melden

Nutzen Sie die [GitHub Issues](https://github.com/malkreide/swiss-food-safety-mcp/issues),
um Fehler zu melden oder Features vorzuschlagen.

Bitte geben Sie an:
- Python-Version und Betriebssystem
- Vollständige Fehlermeldung oder Beschreibung des unerwarteten Verhaltens
- Schritte zur Reproduktion

Beschreiben Sie bei Feature-Vorschlägen den Use Case, idealerweise mit einem
Bezug zu Lebensmittelsicherheit, Veterinärwesen oder dem Schweizer öffentlichen
Gesundheitskontext (Schulverpflegung, Tierseuchenprävention, Kantinenkontrolle
etc.).

---

## Entwicklungsumgebung einrichten

```bash
git clone https://github.com/malkreide/swiss-food-safety-mcp.git
cd swiss-food-safety-mcp

# Mit Dev-Dependencies installieren (uv empfohlen)
uv sync
```

---

## Pull Requests

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feat/mein-feature`
3. Nehmen Sie Ihre Änderungen vor und fügen Sie Tests hinzu
4. Stellen Sie sicher, dass alle Tests bestehen: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Stellen Sie sicher, dass das Linting sauber ist: `ruff check src/ tests/`
6. Committen Sie nach [Conventional Commits](https://www.conventionalcommits.org/): `feat: Stallhaltungsdaten hinzufügen`
7. Pushen Sie und eröffnen Sie einen Pull Request gegen `main`

Pro Feature/Bugfix ein PR, und aktualisieren Sie die Dokumentation **sowohl** auf
Englisch als auch auf Deutsch (`README.md` / `README.de.md`).

---

## Code-Standards

- Python 3.11+, [Ruff](https://docs.astral.sh/ruff/) für Linting und Formatierung
- Docstrings auf Englisch (für internationale Kompatibilität)
- Kommentare und Fehlermeldungen dürfen Deutsch oder Englisch sein
- Alle MCP-Tools müssen `readOnlyHint: True` setzen (nur lesender Zugriff)
- Pydantic-v2-Modelle für alle Tool-Inputs (`extra="forbid"`)
- HTTP-Aufrufe mit `respx` oder `unittest.mock` mocken; Live-API-Tests mit `@pytest.mark.live` markieren

---

## Datenquellen-Richtlinie

Nur offizielle Schweizer Open Government Data (OGD) ist als Datenquelle zulässig:
- [opendata.swiss](https://opendata.swiss/) (BLV-Datensätze)
- [lindas.admin.ch](https://lindas.admin.ch/) (SPARQL-Endpunkt)
- [news.admin.ch](https://www.news.admin.ch/) (RSS-Feeds)

Proprietäre oder nicht öffentlich zugängliche Datenquellen werden nicht akzeptiert.

---

## Tests ausführen

```bash
# Unit-Tests (kein API-Zugriff erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Alle Tests inklusive Live-API-Prüfungen
PYTHONPATH=src pytest tests/
```

---

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** jeden Montag um 05:33 UTC, dazu jederzeit von Hand über *Actions → Live-Tests → Run
workflow*. Siehe [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Label `upstream` und dem stabilen Titel «Live-Tests gegen agriculture.ld.admin.ch rot (<Datum>)». Ein zweiter roter Lauf erkennt das offene Issue am Titelanfang und hängt sich an denselben Thread, statt ein zweites aufzumachen. Wird die Suite wieder grün, schliesst sich das Issue selbst.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das JUnit-XML statt des
Exit-Codes und unterscheidet: `clear` (gelaufen, grün), `finding` (gelaufen,
etwas gefallen) und `unknown` (nicht gelaufen — Installation gescheitert, null
Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst nie ein Issue:
Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über agriculture.ld.admin.ch widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge unter
der [MIT-Lizenz](LICENSE) lizenziert werden.
