# Contributing to swiss-food-safety-mcp

🌐 **English** | **[Deutsch](CONTRIBUTING.de.md)**

Thank you for your interest in contributing! This server is part of the
[Swiss Public Data MCP Portfolio](https://github.com/malkreide).

---

## Reporting Issues

Use [GitHub Issues](https://github.com/malkreide/swiss-food-safety-mcp/issues) to
report bugs or request features.

Please include:
- Python version and OS
- Full error message or description of unexpected behaviour
- Steps to reproduce

For feature requests, describe the use case, ideally with a reference to food
safety, veterinary medicine, or the Swiss public health context (school
catering, animal disease prevention, cantonal food inspection, etc.).

---

## Setting Up the Development Environment

```bash
git clone https://github.com/malkreide/swiss-food-safety-mcp.git
cd swiss-food-safety-mcp

# Install with dev dependencies (uv recommended)
uv sync
```

---

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Ensure linting is clean: `ruff check src/ tests/`
6. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `feat: add livestock data tool`
7. Push and open a Pull Request against `main`

Keep one PR per feature/bugfix, and update documentation in **both** English
and German (`README.md` / `README.de.md`).

---

## Code Standards

- Python 3.11+, [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Docstrings in English (for international compatibility)
- Comments and error messages may be in German or English
- All MCP tools must set `readOnlyHint: True` (read-only access)
- Pydantic v2 models for all tool inputs (`extra="forbid"`)
- Mock HTTP calls with `respx` or `unittest.mock`; mark live API tests with `@pytest.mark.live`

---

## Data Source Policy

Only official Swiss Open Government Data (OGD) is accepted as a data source:
- [opendata.swiss](https://opendata.swiss/) (BLV datasets)
- [lindas.admin.ch](https://lindas.admin.ch/) (SPARQL endpoint)
- [news.admin.ch](https://www.news.admin.ch/) (RSS feeds)

Proprietary or non-publicly accessible data sources will not be accepted.

---

## Running Tests

```bash
# Unit tests (no live API access required)
PYTHONPATH=src pytest tests/ -m "not live"

# All tests including live API checks
PYTHONPATH=src pytest tests/
```

---

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
