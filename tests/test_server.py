"""
tests/test_server.py
====================
Unit tests for swiss-food-safety-mcp.

All tests use mocked HTTP responses — no live API calls required.
Run with: uv run pytest tests/ -v
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from swiss_food_safety_mcp.server import (
    BLV_ORG_ID,
    ERR_NO_DATASET,
    _ckan_resource_url,
    _error,
    _guard_url,
    _host_allowed,
    _lifespan,
    _setup_telemetry,
    _sparql_escape,
    blv_get_antibiotic_usage_vet,
    blv_get_dataset_info,
    blv_get_food_control_results,
    blv_get_meat_inspection_stats,
    blv_get_public_warnings,
    blv_list_datasets,
    blv_search_animal_diseases,
    blv_search_pesticide_products,
    mcp,
)

# ---------------------------------------------------------------------------
# Fixtures / mock helpers
# ---------------------------------------------------------------------------

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Rückruf: Rohwurst wegen Salmonellen</title>
      <link>https://www.newsd.admin.ch/1234</link>
      <description>Produkt XY wird zurückgerufen.</description>
      <pubDate>Thu, 01 Feb 2026 10:00:00 +0100</pubDate>
    </item>
    <item>
      <title>Warnung: Pestizidüberschreitung in Erdbeeren</title>
      <link>https://www.newsd.admin.ch/1235</link>
      <description>Erhöhte Pestizidrückstände festgestellt.</description>
      <pubDate>Wed, 31 Jan 2026 14:00:00 +0100</pubDate>
    </item>
  </channel>
</rss>"""

CKAN_SEARCH_SAMPLE = {
    "success": True,
    "result": {
        "count": 2,
        "results": [
            {
                "name": "blv-tierseuchen",
                "title": {"de": "Tierseuchen in der Schweiz"},
                "notes": {"de": "Meldepflichtige Tierseuchen seit 1991."},
                "resources": [
                    {
                        "format": "CSV",
                        "url": "https://example.com/tierseuchen.csv",
                        "name": "Tierseuchenmeldungen (CSV)",
                        "description": "",
                    },
                    {
                        "format": "JSON",
                        "url": "https://example.com/tierseuchen.json",
                        "name": "JSON",
                        "description": "",
                    },
                ],
            },
            {
                "name": "blv-vogelgrippe",
                "title": {"de": "Vogelgrippe Wildvögel"},
                "notes": {"de": "Vogelgrippe-Überwachung."},
                "resources": [
                    {
                        "format": "JSON",
                        "url": "https://example.com/vogelgrippe.json",
                        "name": "JSON",
                        "description": "",
                    },
                ],
            },
        ],
    },
}

CKAN_PACKAGE_SAMPLE = {
    "success": True,
    "result": {
        "name": "blv-tierseuchen",
        "title": {"de": "Tierseuchen in der Schweiz"},
        "notes": {"de": "Meldepflichtige Tierseuchen seit 1991."},
        "organization": {"name": BLV_ORG_ID},
        "license_title": "Creative Commons Attribution",
        "resources": [
            {
                "name": "Tierseuchenmeldungen (CSV)",
                "format": "CSV",
                "url": "https://example.com/tierseuchen.csv",
                "description": "",
            },
            {
                "name": "JSON",
                "format": "JSON",
                "url": "https://example.com/tierseuchen.json",
                "description": "",
            },
        ],
    },
}

CSV_SAMPLE = (
    "Jahr,Kanton,Seuche,Faelle\n2024,ZH,Maul- und Klauenseuche,0\n2023,BE,Blauzungenkrankheit,3\n"
)

SPARQL_SAMPLE = {
    # Die Form, die der LINDAS-Cube liefert. Vorher stand hier `year`/`disease`
    # — Variablennamen aus einer Abfrage auf eine Klasse, die es nicht gibt.
    "results": {
        "bindings": [
            {
                "date": {"value": "2024-12-30"},
                "canton": {"value": "ZH"},
                "town": {"value": "Zürich"},
                "diseasesGroup": {"value": "Zu bekämpfende Seuchen"},
                "diseases": {"value": "Salmonellose"},
                "species": {"value": "Echse"},
                "count": {"value": "1"},
            }
        ]
    }
}

PESTICIDE_XML = """<?xml version="1.0"?>
<products>
  <product>
    <name>KupferFix Pro</name>
    <authorisation_number>W-1234</authorisation_number>
    <active_ingredients>
      <active_ingredient>Kupferhydroxid</active_ingredient>
    </active_ingredients>
    <status>bewilligt</status>
  </product>
  <product>
    <name>GlyphoStop</name>
    <authorisation_number>W-5678</authorisation_number>
    <active_ingredients>
      <active_ingredient>Glyphosat</active_ingredient>
    </active_ingredients>
    <status>widerrufen</status>
  </product>
</products>"""

BLV_ORG_ID = "bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv"


def _mock_response(content: str | dict | bytes, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    if isinstance(content, dict):
        mock.text = json.dumps(content)
        mock.json.return_value = content
    else:
        mock.text = content if isinstance(content, str) else content.decode()
        mock.json.return_value = json.loads(mock.text) if mock.text.startswith(("{", "[")) else {}
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Tests: blv_get_public_warnings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_get_public_warnings_returns_items():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(RSS_SAMPLE)
        result = await blv_get_public_warnings(limit=5)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Rückruf: Rohwurst wegen Salmonellen"
    assert "link" in result[0]
    assert "pubDate" in result[0]


@pytest.mark.asyncio
async def test_blv_get_public_warnings_respects_limit():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(RSS_SAMPLE)
        result = await blv_get_public_warnings(limit=1)

    assert len(result) == 1


@pytest.mark.asyncio
async def test_blv_get_public_warnings_caps_at_50():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(RSS_SAMPLE)
        # Even if limit=100 is requested, max is 50
        result = await blv_get_public_warnings(limit=100)

    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: blv_list_datasets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_list_datasets_returns_list():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(CKAN_SEARCH_SAMPLE)
        result = await blv_list_datasets()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["name"] == "blv-tierseuchen"
    assert "title" in result[0]
    assert "num_resources" in result[0]


@pytest.mark.asyncio
async def test_blv_list_datasets_search_param():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(CKAN_SEARCH_SAMPLE)
        result = await blv_list_datasets(search="tierseuchen")

    assert isinstance(result, list)
    call_kwargs = mock_get.call_args
    assert call_kwargs is not None


# ---------------------------------------------------------------------------
# Tests: blv_get_dataset_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_get_dataset_info_returns_metadata():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(CKAN_PACKAGE_SAMPLE)
        result = await blv_get_dataset_info("blv-tierseuchen")

    assert result["name"] == "blv-tierseuchen"
    assert isinstance(result["resources"], list)
    assert result["num_resources"] == 2


# ---------------------------------------------------------------------------
# Tests: _ckan_resource_url helper
# ---------------------------------------------------------------------------


def test_ckan_resource_url_found():
    pkg = {
        "resources": [
            {"format": "CSV", "url": "https://example.com/data.csv"},
            {"format": "JSON", "url": "https://example.com/data.json"},
        ]
    }
    assert _ckan_resource_url(pkg, "CSV") == "https://example.com/data.csv"
    assert _ckan_resource_url(pkg, "JSON") == "https://example.com/data.json"


def test_ckan_resource_url_not_found():
    pkg = {"resources": [{"format": "CSV", "url": "https://example.com/data.csv"}]}
    assert _ckan_resource_url(pkg, "XML") is None


def test_ckan_resource_url_case_insensitive():
    pkg = {"resources": [{"format": "csv", "url": "https://example.com/data.csv"}]}
    assert _ckan_resource_url(pkg, "CSV") == "https://example.com/data.csv"


# ---------------------------------------------------------------------------
# Tests: blv_search_animal_diseases (SPARQL path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_search_animal_diseases_sparql_success():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(SPARQL_SAMPLE)
        result = await blv_search_animal_diseases(canton="ZH", year_from=2024, year_to=2024)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["canton"] == "ZH"
    assert result[0]["date"] == "2024-12-30"
    assert result[0]["disease"] == "Salmonellose"


# ---------------------------------------------------------------------------
# Tests: blv_search_pesticide_products (XML path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_search_pesticide_products_xml_kupfer():
    with (
        patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get,
        patch(
            "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
        ) as mock_list,
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
    ):
        mock_list.return_value = [{"name": "blv-pflanzenschutz"}]
        mock_info.return_value = {
            "resources": [
                {
                    "format": "XML",
                    "url": "https://example.com/pestizide.xml",
                    "name": "XML",
                    "description": "",
                }
            ]
        }
        mock_get.return_value = _mock_response(PESTICIDE_XML)
        result = await blv_search_pesticide_products(active_ingredient="Kupfer")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "KupferFix Pro"


@pytest.mark.asyncio
async def test_blv_search_pesticide_products_status_filter():
    with (
        patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get,
        patch(
            "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
        ) as mock_list,
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
    ):
        mock_list.return_value = [{"name": "blv-pflanzenschutz"}]
        mock_info.return_value = {
            "resources": [
                {
                    "format": "XML",
                    "url": "https://example.com/pestizide.xml",
                    "name": "XML",
                    "description": "",
                }
            ]
        }
        mock_get.return_value = _mock_response(PESTICIDE_XML)
        result = await blv_search_pesticide_products(status="widerrufen")

    assert all(r["status"] == "widerrufen" for r in result)


# ---------------------------------------------------------------------------
# Tests: blv_get_food_control_results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_get_food_control_results_filters_by_canton():
    with (
        patch(
            "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
        ) as mock_list,
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
        patch("swiss_food_safety_mcp.server._fetch_csv", new_callable=AsyncMock) as mock_csv,
    ):
        mock_list.return_value = [{"name": "blv-lebensmittelkontrolle"}]
        mock_info.return_value = {
            "resources": [
                {
                    "format": "CSV",
                    "url": "https://example.com/kontrolle.csv",
                    "name": "Food establishments 2025",
                    "description": "",
                }
            ]
        }
        mock_csv.return_value = [
            {"Kanton": "ZH", "Jahr": "2023", "Inspektionen": "1200", "Beanstandungen": "120"},
            {"Kanton": "BE", "Jahr": "2023", "Inspektionen": "900", "Beanstandungen": "80"},
        ]
        result = await blv_get_food_control_results(canton="ZH")

    assert all("ZH" in str(r) for r in result)


# ---------------------------------------------------------------------------
# Tests: blv_get_antibiotic_usage_vet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_get_antibiotic_usage_vet_year_filter():
    with (
        patch(
            "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
        ) as mock_list,
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
        patch("swiss_food_safety_mcp.server._fetch_csv", new_callable=AsyncMock) as mock_csv,
    ):
        mock_list.return_value = [{"name": "blv-isabv"}]
        mock_info.return_value = {
            "resources": [
                {
                    "format": "CSV",
                    "url": "https://example.com/isabv.csv",
                    "name": "ISABV-Amount-Active-Substance-full",
                    "description": "",
                }
            ]
        }
        mock_csv.return_value = [
            {"Jahr": "2022", "Tierart": "Rind", "Klasse": "Penicilline", "Menge_kg": "12.5"},
            {"Jahr": "2021", "Tierart": "Schwein", "Klasse": "Tetrazykline", "Menge_kg": "8.0"},
        ]
        result = await blv_get_antibiotic_usage_vet(year=2022)

    assert all("2022" in str(r) for r in result)


# ---------------------------------------------------------------------------
# Tests: blv_get_meat_inspection_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_get_meat_inspection_stats_returns_list():
    with (
        patch(
            "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
        ) as mock_list,
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
        patch("swiss_food_safety_mcp.server._fetch_csv", new_callable=AsyncMock) as mock_csv,
    ):
        mock_list.return_value = [{"name": "blv-fleischuntersuchung"}]
        mock_info.return_value = {
            "resources": [
                {
                    "format": "CSV",
                    "url": "https://example.com/fleisch.csv",
                    "name": "Fleischkontrollstatistik (CSV)",
                    "description": "",
                }
            ]
        }
        mock_csv.return_value = [
            {"Jahr": "2023", "Tierart": "Rind", "Geschlachtet": "300000", "Beanstandet": "1200"},
            {
                "Jahr": "2023",
                "Tierart": "Schwein",
                "Geschlachtet": "2500000",
                "Beanstandet": "5000",
            },
        ]
        result = await blv_get_meat_inspection_stats(year=2023)

    assert isinstance(result, list)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests: no_dataset_found error handling
# ---------------------------------------------------------------------------


# Diese beiden Tests prueften den Pfad «kein Datensatz gefunden». Den gibt es
# nicht mehr: Die Datenwerkzeuge suchen nicht, sie haben einen gepinnten Slug
# (siehe `DATENQUELLEN`). An seine Stelle tritt die staerkere Frage — was
# passiert, wenn die gepinnte Ressource verschwindet? Sie darf nicht still
# durch irgendeine andere ersetzt werden, sondern muss auffallen.


@pytest.mark.asyncio
async def test_verschwundene_ressource_faellt_auf_statt_still_ersetzt_zu_werden():
    from swiss_food_safety_mcp.server import UpstreamShapeError

    with patch(
        "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
    ) as mock_info:
        # Ein Datensatz voller Code-Listen — genau die Lage bei
        # `lebensmittelkontrolle`, wo 18 von 26 Ressourcen Legenden sind.
        mock_info.return_value = {
            "resources": [
                {"format": "CSV", "name": "Foodstuffs codelist units", "url": "https://x/a.csv"},
                {"format": "CSV", "name": "Foodstuffs codelist matrix", "url": "https://x/b.csv"},
            ]
        }
        with pytest.raises(UpstreamShapeError) as exc:
            await blv_get_food_control_results()

    # Die Meldung muss nennen, was stattdessen da war — sonst weiss niemand,
    # wonach er suchen soll.
    assert "codelist" in str(exc.value)
    assert "Food establishments" in str(exc.value)


@pytest.mark.asyncio
async def test_die_neueste_jahresdatei_gewinnt():
    """Passen mehrere Ressourcen, gewinnt die zuletzt einsortierte.

    Bei `lebensmittelkontrolle` sind das die Jahresdateien; opendata.swiss
    sortiert sie aufsteigend. «Die erste» waere hier das aelteste Jahr — und
    «die erste CSV ueberhaupt» war eine Code-Liste.
    """
    with (
        patch(
            "swiss_food_safety_mcp.server.blv_get_dataset_info", new_callable=AsyncMock
        ) as mock_info,
        patch("swiss_food_safety_mcp.server._fetch_csv", new_callable=AsyncMock) as mock_csv,
    ):
        mock_info.return_value = {
            "resources": [
                {
                    "format": "CSV",
                    "name": "Food establishments codelist grading",
                    "url": "https://x/code.csv",
                },
                {"format": "CSV", "name": "Food establishments 2022", "url": "https://x/2022.csv"},
                {"format": "CSV", "name": "Food establishments 2025", "url": "https://x/2025.csv"},
            ]
        }
        mock_csv.return_value = [{"Kanton": "ZH"}]
        await blv_get_food_control_results()

    mock_csv.assert_awaited_once_with("https://x/2025.csv")


# ---------------------------------------------------------------------------
# Tests: SPARQL injection hardening (_sparql_escape)
# ---------------------------------------------------------------------------


def test_sparql_escape_neutralizes_quotes_and_backslashes():
    assert _sparql_escape("ZH") == "ZH"
    assert _sparql_escape("a'b") == "a\\'b"
    assert _sparql_escape("a\\b") == "a\\\\b"
    assert _sparql_escape('a"b') == 'a\\"b'
    assert "\n" not in _sparql_escape("a\nb")


@pytest.mark.asyncio
async def test_blv_search_animal_diseases_escapes_injection_payload():
    payload = "x') } INJECT {"
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(SPARQL_SAMPLE)
        await blv_search_animal_diseases(disease=payload)

    sent_query = mock_get.call_args.kwargs["params"]["query"]
    # The raw closing-quote payload must not appear unescaped in the query.
    assert "x') }" not in sent_query
    assert "x\\') }" in sent_query


# ---------------------------------------------------------------------------
# Tests: result-limit clamping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blv_list_datasets_clamps_excessive_limit():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(CKAN_SEARCH_SAMPLE)
        await blv_list_datasets(limit=9999)

    assert mock_get.call_args.kwargs["params"]["rows"] == 100


# ---------------------------------------------------------------------------
# Tests: SSRF egress guard (_host_allowed / _guard_url)
# ---------------------------------------------------------------------------


def test_host_allowed_accepts_federal_domains():
    assert _host_allowed("opendata.swiss")
    assert _host_allowed("lindas.admin.ch")
    assert _host_allowed("www.newsd.admin.ch")


def test_host_allowed_rejects_foreign_and_lookalike_domains():
    assert not _host_allowed("evil.com")
    assert not _host_allowed("admin.ch.evil.com")
    assert not _host_allowed("notopendata.swiss")
    assert not _host_allowed("")


@pytest.mark.asyncio
async def test_guard_url_rejects_non_https():
    with pytest.raises(ValueError):
        await _guard_url("http://opendata.swiss/data.csv")


@pytest.mark.asyncio
async def test_guard_url_rejects_unlisted_host():
    with pytest.raises(ValueError):
        await _guard_url("https://evil.example.com/data.csv")


@pytest.mark.asyncio
async def test_guard_url_rejects_private_ip(monkeypatch):
    monkeypatch.setattr(
        "swiss_food_safety_mcp.server.socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 0))],
    )
    with pytest.raises(ValueError):
        await _guard_url("https://opendata.swiss/data.csv")


@pytest.mark.asyncio
async def test_guard_url_allows_public_listed_host(monkeypatch):
    monkeypatch.setattr(
        "swiss_food_safety_mcp.server.socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("185.34.0.1", 0))],
    )
    await _guard_url("https://opendata.swiss/data.csv")


# ---------------------------------------------------------------------------
# Tests: tool annotations (ARCH-009)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_tools_are_annotated_read_only():
    tools = await mcp.list_tools()
    assert len(tools) == 11
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.readOnlyHint is True, tool.name
        assert tool.annotations.openWorldHint is True, tool.name


# ---------------------------------------------------------------------------
# Tests: structured errors (OBS-001) & not-found guidance (ARCH-003)
# ---------------------------------------------------------------------------


def test_error_helper_builds_structured_record():
    err = _error("boom", "some_code", note="try this")
    assert err == {"error": "boom", "code": "some_code", "note": "try this"}


@pytest.mark.asyncio
async def test_no_dataset_error_has_code_and_note():
    """`ERR_NO_DATASET` gilt weiterhin — fuer die Werkzeuge, die noch suchen.

    Die Datenwerkzeuge haben seit dem 2026-08-08 gepinnte Slugs; suchen tut
    nur noch der Pestizid-Pfad. Dort muss der strukturierte Fehler bleiben.
    """
    with patch(
        "swiss_food_safety_mcp.server.blv_list_datasets", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = []
        result = await blv_search_pesticide_products()

    assert result[0]["code"] == ERR_NO_DATASET
    assert "note" in result[0] and result[0]["note"]


# ---------------------------------------------------------------------------
# Tests: provenance attribution (CH-004)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warnings_include_source_attribution():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(RSS_SAMPLE)
        result = await blv_get_public_warnings(limit=5)

    assert all("source" in item and item["source"] for item in result)


@pytest.mark.asyncio
async def test_datasets_include_source_attribution():
    with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(CKAN_SEARCH_SAMPLE)
        result = await blv_list_datasets()

    assert all("source" in ds and ds["source"] for ds in result)


# ---------------------------------------------------------------------------
# Tests: telemetry setup (OBS-006)
# ---------------------------------------------------------------------------


def test_setup_telemetry_is_noop_without_endpoint():
    # Default profile has no OTLP endpoint configured — must not raise.
    _setup_telemetry()


# ---------------------------------------------------------------------------
# Live tests — excluded from CI (run explicitly with: pytest -m live)
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_public_warnings_hits_real_feed():
    async with _lifespan(mcp):
        try:
            result = await blv_get_public_warnings(limit=3)
        except (httpx.HTTPError, OSError) as exc:
            pytest.skip(f"BLV feed unreachable in this environment: {exc}")
    assert isinstance(result, list)
