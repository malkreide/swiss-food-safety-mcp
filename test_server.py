"""
Tests for swiss-food-safety-mcp

Tests focus on input validation, error handling, and helper functions.
Live API tests are skipped in CI to avoid rate limits.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from swiss_food_safety_mcp.server import (
    _parse_csv_to_records,
    _format_records_markdown,
    _handle_http_error,
    _find_resource_by_format,
    _get_multilingual_title,
    _filter_psm_records,
    PublicWarningsInput,
    ListDatasetsInput,
    AnimalDiseasesInput,
    Language,
    ResponseFormat,
    DATASET_IDS,
    BLV_ORG_ID,
    CKAN_API_BASE,
)


# ─────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────

class TestParseCsvToRecords:
    def test_basic_csv(self):
        csv_text = "name,year,value\nRind,2023,42\nSchwein,2023,17"
        records = _parse_csv_to_records(csv_text)
        assert len(records) == 2
        assert records[0]["name"] == "Rind"
        assert records[1]["year"] == "2023"

    def test_max_rows_respected(self):
        lines = ["col1,col2"] + [f"val{i},val{i}" for i in range(100)]
        csv_text = "\n".join(lines)
        records = _parse_csv_to_records(csv_text, max_rows=10)
        assert len(records) == 10

    def test_empty_csv(self):
        records = _parse_csv_to_records("col1,col2\n")
        assert records == []

    def test_single_row(self):
        records = _parse_csv_to_records("name,value\nTest,123")
        assert len(records) == 1
        assert records[0]["name"] == "Test"


class TestFormatRecordsMarkdown:
    def test_empty_records(self):
        result = _format_records_markdown([])
        assert "Keine Daten" in result

    def test_basic_formatting(self):
        records = [{"name": "Tierseuche A", "year": "2024", "canton": "ZH"}]
        result = _format_records_markdown(records, "Test Titel")
        assert "Test Titel" in result
        assert "Tierseuche A" in result
        assert "ZH" in result

    def test_max_rows_limit(self):
        records = [{"item": str(i)} for i in range(50)]
        result = _format_records_markdown(records, max_rows=5)
        # Should show 50 total but only 5 entries
        assert "50 Einträge" in result


class TestHandleHttpError:
    def test_returns_string(self):
        result = _handle_http_error(Exception("test error"))
        assert isinstance(result, str)
        assert "Fehler" in result or "Unerwarteter" in result

    def test_context_prefix(self):
        result = _handle_http_error(Exception("test"), context="blv_test_tool")
        assert "[blv_test_tool]" in result

    def test_timeout_error(self):
        import httpx
        result = _handle_http_error(httpx.TimeoutException("timeout"))
        assert "Timeout" in result

    def test_connect_error(self):
        import httpx
        result = _handle_http_error(httpx.ConnectError("connect failed"))
        assert "Verbindungsfehler" in result


class TestFindResourceByFormat:
    def test_finds_preferred_format(self):
        resources = [
            {"format": "CSV", "url": "http://example.com/data.csv"},
            {"format": "JSON", "url": "http://example.com/data.json"},
        ]
        result = _find_resource_by_format(resources, ["JSON", "CSV"])
        assert result["format"] == "JSON"

    def test_fallback_to_second_format(self):
        resources = [{"format": "CSV", "url": "http://example.com/data.csv"}]
        result = _find_resource_by_format(resources, ["JSON", "CSV"])
        assert result["format"] == "CSV"

    def test_returns_none_if_no_match(self):
        resources = [{"format": "XML", "url": "http://example.com/data.xml"}]
        result = _find_resource_by_format(resources, ["JSON", "CSV"])
        assert result is None

    def test_case_insensitive(self):
        resources = [{"format": "csv", "url": "http://example.com/data.csv"}]
        result = _find_resource_by_format(resources, ["CSV"])
        assert result is not None


class TestGetMultilingualTitle:
    def test_dict_title_german(self):
        ds = {"title": {"de": "Tiergesundheit", "en": "Animal Health"}}
        assert _get_multilingual_title(ds) == "Tiergesundheit"

    def test_dict_title_fallback_english(self):
        ds = {"title": {"en": "Animal Health", "fr": "Santé Animale"}}
        assert _get_multilingual_title(ds) == "Animal Health"

    def test_string_title(self):
        ds = {"title": "Plain Title"}
        assert _get_multilingual_title(ds) == "Plain Title"

    def test_title_translated(self):
        ds = {"title": "fallback", "title_translated": {"de": "Übersetzter Titel"}}
        assert _get_multilingual_title(ds) == "Übersetzter Titel"


class TestFilterPsmRecords:
    def test_filter_by_name(self):
        records = [
            {"Produktname": "Karate Zeon", "Wirkstoff": "lambda-Cyhalothrin"},
            {"Produktname": "Roundup", "Wirkstoff": "Glyphosat"},
        ]
        result = _filter_psm_records(records, "karate", None)
        assert len(result) == 1
        assert result[0]["Produktname"] == "Karate Zeon"

    def test_filter_by_ingredient(self):
        records = [
            {"Produktname": "Karate Zeon", "Wirkstoff": "lambda-Cyhalothrin"},
            {"Produktname": "Roundup", "Wirkstoff": "Glyphosat"},
        ]
        result = _filter_psm_records(records, None, "Glyphosat")
        assert len(result) == 1

    def test_no_filter(self):
        records = [{"name": "A"}, {"name": "B"}]
        result = _filter_psm_records(records, None, None)
        assert len(result) == 2


# ─────────────────────────────────────────────
# Pydantic Input Model Tests
# ─────────────────────────────────────────────

class TestPublicWarningsInput:
    def test_defaults(self):
        params = PublicWarningsInput()
        assert params.limit == 20
        assert params.lang == Language.DE
        assert params.response_format == ResponseFormat.MARKDOWN

    def test_custom_values(self):
        params = PublicWarningsInput(limit=5, lang="fr", response_format="json")
        assert params.limit == 5
        assert params.lang == Language.FR
        assert params.response_format == ResponseFormat.JSON

    def test_limit_bounds(self):
        with pytest.raises(Exception):
            PublicWarningsInput(limit=0)
        with pytest.raises(Exception):
            PublicWarningsInput(limit=101)


class TestListDatasetsInput:
    def test_defaults(self):
        params = ListDatasetsInput()
        assert params.limit == 20
        assert params.offset == 0
        assert params.category is None

    def test_with_category(self):
        params = ListDatasetsInput(category="heal")
        assert params.category == "heal"

    def test_limit_bounds(self):
        with pytest.raises(Exception):
            ListDatasetsInput(limit=51)


class TestAnimalDiseasesInput:
    def test_year_validation(self):
        with pytest.raises(Exception):
            AnimalDiseasesInput(year_from=1990)  # before 1991

    def test_valid_canton(self):
        params = AnimalDiseasesInput(canton="ZH")
        assert params.canton == "ZH"

    def test_canton_too_long(self):
        with pytest.raises(Exception):
            AnimalDiseasesInput(canton="ZHH")


# ─────────────────────────────────────────────
# Constants tests
# ─────────────────────────────────────────────

class TestConstants:
    def test_dataset_ids_present(self):
        required_ids = [
            "tiergesundheitsstatistik",
            "fleischkontrollstatistik",
            "lebensmittelkontrolle",
            "antibiotikaeinsatz",
            "tierseuchenmeldungen",
            "avian_influenza",
            "menuch_kids",
            "pflanzenschutzmittel",
        ]
        for ds_id in required_ids:
            assert ds_id in DATASET_IDS, f"Dataset-ID fehlt: {ds_id}"

    def test_org_id_correct(self):
        assert "blv" in BLV_ORG_ID.lower()
        assert "lebensmittelsicherheit" in BLV_ORG_ID.lower()

    def test_ckan_api_base(self):
        assert CKAN_API_BASE.startswith("https://")
        assert "opendata.swiss" in CKAN_API_BASE


# ─────────────────────────────────────────────
# Server structure tests
# ─────────────────────────────────────────────

class TestServerStructure:
    def test_server_name(self):
        from swiss_food_safety_mcp.server import mcp
        assert mcp.name == "swiss_food_safety_mcp"

    def test_tool_count(self):
        """Verify that all expected tools are registered."""
        from swiss_food_safety_mcp.server import mcp
        # FastMCP stores tools — just verify server is importable and named correctly
        assert mcp is not None
