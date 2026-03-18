# Beitragen / Contributing

> 🇩🇪 [Deutsch](#deutsch) · 🇬🇧 [English](#english)

---

## Deutsch

Vielen Dank für Ihr Interesse an diesem Projekt! Beiträge sind willkommen.

### Wie kann ich beitragen?

**Fehler melden:** Erstellen Sie ein [Issue](../../issues) mit einer klaren Beschreibung des Problems, Schritten zur Reproduktion und der erwarteten vs. tatsächlichen Ausgabe.

**Feature vorschlagen:** Beschreiben Sie den Use Case, idealerweise mit einem Bezug zu Lebensmittelsicherheit, Veterinärwesen oder dem Schweizer öffentlichen Gesundheitskontext (Schulverpflegung, Tierseuchenprävention, Kantinenkontrolle etc.).

**Code beitragen:**

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feature/mein-feature`
3. Installieren Sie die Dev-Abhängigkeiten: `uv sync`
4. Schreiben Sie Tests für Ihre Änderungen
5. Lint prüfen: `ruff check src/ tests/`
6. Commit mit aussagekräftiger Nachricht gemäss [Conventional Commits](https://www.conventionalcommits.org/):
   `git commit -m "feat: Stallhaltungsdaten hinzufügen"`
7. Pull Request erstellen

### Code-Standards

- Python 3.11+, [Ruff](https://docs.astral.sh/ruff/) für Linting und Formatierung
- Docstrings auf Englisch (für internationale Kompatibilität)
- Kommentare und Fehlermeldungen dürfen Deutsch oder Englisch sein
- Alle MCP-Tools müssen `readOnlyHint: True` setzen (nur lesender Zugriff)
- Pydantic v2-Modelle für alle Tool-Inputs
- Tests mit `respx` oder `unittest.mock` mocken; Live-API-Tests mit `@pytest.mark.live` markieren

### Datenquellen-Richtlinie

Nur offizielle Schweizer Open Government Data (OGD) ist als Datenquelle zulässig:
- [opendata.swiss](https://opendata.swiss/) (BLV-Datensätze)
- [lindas.admin.ch](https://lindas.admin.ch/) (SPARQL-Endpunkt)
- [news.admin.ch](https://www.news.admin.ch/) (RSS-Feeds)

Proprietäre oder nicht öffentlich zugängliche Datenquellen werden nicht akzeptiert.

### Tests ausführen

```bash
# Unit-Tests (kein API-Zugriff erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Alle Tests
PYTHONPATH=src pytest tests/
```

---

## English

Thank you for your interest in this project! Contributions are welcome.

### How can I contribute?

**Report bugs:** Create an [Issue](../../issues) with a clear description, reproduction steps, and expected vs. actual output.

**Suggest features:** Describe the use case, ideally with a reference to food safety, veterinary medicine, or the Swiss public health context (school catering, animal disease prevention, cantonal food inspection, etc.).

**Contribute code:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `uv sync`
4. Write tests for your changes
5. Run linter: `ruff check src/ tests/`
6. Commit with a clear message following [Conventional Commits](https://www.conventionalcommits.org/):
   `git commit -m "feat: add livestock data tool"`
7. Create a Pull Request

### Code Standards

- Python 3.11+, [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Docstrings in English (for international compatibility)
- Comments and error messages may be in German or English
- All MCP tools must set `readOnlyHint: True` (read-only access)
- Pydantic v2 models for all tool inputs
- Mock HTTP calls with `respx` or `unittest.mock`; mark live API tests with `@pytest.mark.live`

### Data Source Policy

Only official Swiss Open Government Data (OGD) is accepted as a data source:
- [opendata.swiss](https://opendata.swiss/) (BLV datasets)
- [lindas.admin.ch](https://lindas.admin.ch/) (SPARQL endpoint)
- [news.admin.ch](https://www.news.admin.ch/) (RSS feeds)

Proprietary or non-publicly accessible data sources will not be accepted.

### Running Tests

```bash
# Unit tests (no live API access required)
PYTHONPATH=src pytest tests/ -m "not live"

# All tests
PYTHONPATH=src pytest tests/
```

---

## Lizenz / License

MIT – see [LICENSE](LICENSE)
