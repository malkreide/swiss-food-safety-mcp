"""
swiss-food-safety-mcp — MCP Server for Swiss Federal Food Safety and Veterinary Office (BLV)
Bundesamt für Lebensmittelsicherheit und Veterinärwesen

Data sources (all open, no authentication required):
- opendata.swiss CKAN API (28 BLV datasets)
- lindas.admin.ch SPARQL endpoint (linked data)
- news.admin.ch RSS feed (public warnings & recalls)
- psm.admin.ch (pesticide register)
"""

import json
import csv
import io
import xml.etree.ElementTree as ET
from typing import Optional, List
from enum import Enum

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

CKAN_API_BASE = "https://ckan.opendata.swiss/api/3/action"
BLV_ORG_ID = "bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv"
SPARQL_ENDPOINT = "https://lindas.admin.ch/sparql"
RSS_WARNINGS_DE = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079"
RSS_WARNINGS_FR = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=fr&org-nr=1079"
RSS_WARNINGS_EN = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=en&org-nr=1079"
PSM_API_BASE = "https://www.psm.admin.ch/api/v1"

HTTP_TIMEOUT = 30.0
DEFAULT_LIMIT = 20
MAX_CSV_ROWS = 500

# Known dataset IDs on opendata.swiss (stable)
DATASET_IDS = {
    "tiergesundheitsstatistik": "tiergesundheitsstatistik",
    "fleischkontrollstatistik": "fleischkontrollstatistik",
    "lebensmittelkontrolle": "lebensmittelkontrolle",
    "antibiotikaeinsatz": "antibiotikaeinsatz-in-der-veterinarmedizin",
    "tierseuchenmeldungen": "meldepflichtige-tierseuchen-in-der-schweiz",
    "avian_influenza": "uberwachung-von-wildvogeln-auf-aviare-influenza-ai",
    "menuch_kids": "menuch-kids-fragebogen",
    "pflanzenschutzmittel": "pflanzenschutzmittelverzeichnisw",
    "pfas_milch": "pfas-analysen-in-milch-und-milchprodukten",
    "salz_fertiggerichte": "salz-in-fertiggerichten",
}

# ─────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────

mcp = FastMCP(
    "swiss_food_safety_mcp",
    instructions=(
        "This server provides access to Swiss Federal Food Safety and Veterinary Office (BLV) "
        "open data. Use it to query food recalls, animal disease outbreaks, food control results, "
        "antibiotic usage in veterinary medicine, nutrition surveys, and pesticide registers. "
        "All data is from official Swiss federal sources and requires no authentication. "
        "For the anchor demo question: 'Welche Lebensmittelwarnungen hat das BLV aktuell?"
        " — use blv_get_public_warnings()."
    ),
)

# ─────────────────────────────────────────────
# Shared HTTP client & helpers
# ─────────────────────────────────────────────

def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers={
            "User-Agent": "swiss-food-safety-mcp/1.0.0 (https://github.com/malkreide/swiss-food-safety-mcp)",
            "Accept": "application/json, text/xml, text/csv, */*",
        },
        follow_redirects=True,
    )


def _handle_http_error(e: Exception, context: str = "") -> str:
    """Consistent error formatting across all tools."""
    prefix = f"[{context}] " if context else ""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return f"{prefix}Fehler 404: Ressource nicht gefunden. Bitte Dataset-ID oder URL prüfen."
        if code == 429:
            return f"{prefix}Fehler 429: Rate limit erreicht. Bitte kurz warten und erneut versuchen."
        if code == 503:
            return f"{prefix}Fehler 503: Dienst vorübergehend nicht verfügbar (BLV/opendata.swiss)."
        return f"{prefix}HTTP-Fehler {code}: {e.response.text[:200]}"
    if isinstance(e, httpx.TimeoutException):
        return f"{prefix}Timeout: Die Anfrage hat das Zeitlimit überschritten. Bitte erneut versuchen."
    if isinstance(e, httpx.ConnectError):
        return f"{prefix}Verbindungsfehler: Server nicht erreichbar. Internetverbindung prüfen."
    return f"{prefix}Unerwarteter Fehler: {type(e).__name__}: {str(e)[:200]}"


def _parse_csv_to_records(csv_text: str, max_rows: int = MAX_CSV_ROWS) -> List[dict]:
    """Parse CSV text into list of dicts, respecting max_rows."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        rows.append(dict(row))
    return rows


def _format_records_markdown(records: List[dict], title: str = "", max_rows: int = 20) -> str:
    """Format list of dicts as a readable markdown table (up to max_rows)."""
    if not records:
        return "Keine Daten gefunden."

    display = records[:max_rows]
    keys = list(display[0].keys())

    lines = []
    if title:
        lines.append(f"## {title}\n")
    lines.append(f"**{len(records)} Einträge** (zeige {len(display)})\n")

    # Compact: key-value blocks instead of wide tables
    for i, row in enumerate(display):
        lines.append(f"### Eintrag {i + 1}")
        for k in keys:
            val = row.get(k, "")
            if val and str(val).strip():
                lines.append(f"- **{k}**: {val}")
        lines.append("")

    return "\n".join(lines)


async def _ckan_get_dataset_resources(dataset_id: str) -> dict:
    """Fetch dataset metadata including resource URLs from CKAN."""
    async with _get_client() as client:
        resp = await client.get(
            f"{CKAN_API_BASE}/package_show",
            params={"id": dataset_id},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {})


async def _fetch_csv_resource(url: str, max_rows: int = MAX_CSV_ROWS) -> List[dict]:
    """Fetch and parse a CSV resource URL."""
    async with _get_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return _parse_csv_to_records(resp.text, max_rows)


async def _fetch_json_resource(url: str) -> list | dict:
    """Fetch a JSON resource URL."""
    async with _get_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _find_resource_by_format(resources: list, preferred_formats: list[str]) -> dict | None:
    """Find first matching resource by format preference."""
    for fmt in preferred_formats:
        for r in resources:
            if r.get("format", "").upper() == fmt.upper():
                return r
    return None


# ─────────────────────────────────────────────
# Pydantic Input Models
# ─────────────────────────────────────────────

class Language(str, Enum):
    DE = "de"
    FR = "fr"
    EN = "en"


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class PublicWarningsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    limit: int = Field(default=20, ge=1, le=100, description="Maximale Anzahl Warnungen (1–100)")
    lang: Language = Field(default=Language.DE, description="Sprache: 'de', 'fr' oder 'en'")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' (lesbar) oder 'json' (maschinenlesbar)",
    )


class ListDatasetsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category: Optional[str] = Field(
        default=None,
        description="Kategorie-Filter, z.B. 'heal' (Gesundheit), 'agri' (Landwirtschaft). None = alle",
    )
    search_query: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Suchbegriff im Datensatz-Titel (z.B. 'tierseuche', 'ernaehrung')",
    )
    limit: int = Field(default=20, ge=1, le=50, description="Anzahl Ergebnisse (1–50)")
    offset: int = Field(default=0, ge=0, description="Offset für Paginierung")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DatasetInfoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    dataset_id: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description=(
            "CKAN Dataset-ID auf opendata.swiss, z.B. 'tiergesundheitsstatistik' oder "
            "'meldepflichtige-tierseuchen-in-der-schweiz'"
        ),
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AnimalDiseasesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    species: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Tierart (z.B. 'Rind', 'Schwein', 'Geflügel', 'Schaf'). None = alle",
    )
    canton: Optional[str] = Field(
        default=None,
        max_length=2,
        description="Kantonskürzel (z.B. 'ZH', 'BE', 'SG'). None = ganze Schweiz",
    )
    year_from: Optional[int] = Field(
        default=None,
        ge=1991,
        le=2026,
        description="Startjahr (frühestens 1991)",
    )
    year_to: Optional[int] = Field(
        default=None,
        ge=1991,
        le=2026,
        description="Endjahr",
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AnimalHealthStatsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    year: Optional[int] = Field(
        default=None,
        ge=2000,
        le=2026,
        description="Filterjahr. None = alle verfügbaren Jahre",
    )
    max_rows: int = Field(default=100, ge=1, le=500, description="Maximale Zeilen (1–500)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class FoodControlInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    year: Optional[int] = Field(default=None, ge=2010, le=2026, description="Filterjahr. None = alle")
    canton: Optional[str] = Field(
        default=None, max_length=2, description="Kantonskürzel (z.B. 'ZH'). None = alle"
    )
    max_rows: int = Field(default=100, ge=1, le=500)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AntibioticUsageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    year: Optional[int] = Field(default=None, ge=2010, le=2026, description="Filterjahr. None = alle")
    max_rows: int = Field(default=100, ge=1, le=500)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class NutritionSurveyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    age_group: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Altersgruppe (z.B. '6-17', 'Kinder', 'Jugendliche'). None = alle",
    )
    max_rows: int = Field(default=100, ge=1, le=500)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class PesticideSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    product_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Produktname oder Teilname (z.B. 'Roundup', 'Karate')",
    )
    active_ingredient: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Wirkstoff (z.B. 'Glyphosat', 'Chlorpyrifos')",
    )
    max_rows: int = Field(default=50, ge=1, le=200)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AvianInfluenzaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    year: Optional[int] = Field(default=None, ge=2000, le=2026, description="Filterjahr. None = alle")
    region: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Region oder Kanton (z.B. 'Zürich', 'Bodensee'). None = gesamte Schweiz",
    )
    max_rows: int = Field(default=100, ge=1, le=500)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ─────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────

@mcp.tool(
    name="blv_get_public_warnings",
    annotations={
        "title": "BLV Öffentliche Warnungen und Rückrufe",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def blv_get_public_warnings(params: PublicWarningsInput) -> str:
    """Ruft aktuelle öffentliche Warnungen und Produktrückrufe des BLV ab.

    Enthält Lebensmittelrückrufe, Produktwarnungen (Schwermetalle, Krankheitserreger,
    Fremdkörper) und Tiergesundheitswarnungen. Daten kommen aus dem offiziellen
    RSS-Feed des Bundesamts für Lebensmittelsicherheit und Veterinärwesen (BLV).

    Nützlich für: Schulkantinen-Sicherheit, Beschaffungscontrolling, Krisenmonitoring,
    Elterninformationen, Push-Alerts bei relevanten Rückrufen.

    Args:
        params: PublicWarningsInput mit:
            - limit (int): Maximale Anzahl Warnungen (Standard 20)
            - lang (str): Sprache 'de', 'fr' oder 'en'
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Formatierte Liste aktueller Warnungen mit Titel, Datum, Beschreibung und Link.
    """
    rss_urls = {
        Language.DE: RSS_WARNINGS_DE,
        Language.FR: RSS_WARNINGS_FR,
        Language.EN: RSS_WARNINGS_EN,
    }
    url = rss_urls[params.lang]

    try:
        async with _get_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        if channel is None:
            return "Fehler: RSS-Feed konnte nicht geparst werden."

        items = channel.findall("item")[: params.limit]
        warnings = []

        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()
            # Strip HTML tags from description
            import re
            description = re.sub(r"<[^>]+>", "", description).strip()
            if len(description) > 300:
                description = description[:300] + "…"

            warnings.append({
                "title": title,
                "date": pub_date,
                "description": description,
                "link": link,
            })

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(warnings), "warnings": warnings}, ensure_ascii=False, indent=2)

        # Markdown output
        lines = [
            f"# BLV Öffentliche Warnungen und Rückrufe\n",
            f"**{len(warnings)} aktuelle Meldungen** | Quelle: news.admin.ch (BLV RSS)\n",
        ]
        for w in warnings:
            lines.append(f"## {w['title']}")
            if w["date"]:
                lines.append(f"📅 {w['date']}")
            if w["description"]:
                lines.append(f"\n{w['description']}")
            if w["link"]:
                lines.append(f"\n🔗 [Meldung lesen]({w['link']})")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return _handle_http_error(e, "blv_get_public_warnings")


@mcp.tool(
    name="blv_list_datasets",
    annotations={
        "title": "BLV Open Data Datensätze auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_list_datasets(params: ListDatasetsInput) -> str:
    """Listet alle Open Data Datensätze des BLV auf opendata.swiss auf.

    Gibt Überblick über verfügbare Datensätze inkl. Titel, Beschreibung, Formate
    und Aktualisierungsdatum. Nutzt die CKAN API von opendata.swiss.

    Aktuell ca. 28 Datensätze in Kategorien: Gesundheit, Landwirtschaft,
    Wissenschaft, Wirtschaft, Bevölkerung.

    Args:
        params: ListDatasetsInput mit:
            - category (str, optional): CKAN-Kategoriefilter ('heal', 'agri', 'tech', 'econ', 'soci')
            - search_query (str, optional): Suchbegriff im Titel
            - limit (int): Anzahl Ergebnisse
            - offset (int): Offset für Paginierung
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Datensatzliste mit Titel, Beschreibung, Formaten und URLs.
    """
    params_ckan: dict = {
        "fq": f"organization:{BLV_ORG_ID}",
        "rows": params.limit,
        "start": params.offset,
        "include_private": False,
    }
    if params.category:
        params_ckan["fq"] += f" groups:{params.category}"
    if params.search_query:
        params_ckan["q"] = params.search_query

    try:
        async with _get_client() as client:
            resp = await client.get(f"{CKAN_API_BASE}/package_search", params=params_ckan)
            resp.raise_for_status()

        data = resp.json()
        result = data.get("result", {})
        total = result.get("count", 0)
        datasets = result.get("results", [])

        if not datasets:
            return "Keine Datensätze gefunden. Suchkriterien anpassen."

        if params.response_format == ResponseFormat.JSON:
            simplified = [
                {
                    "id": ds.get("name"),
                    "title": _get_multilingual_title(ds),
                    "description": _get_multilingual_description(ds, max_chars=200),
                    "formats": [r.get("format", "").upper() for r in ds.get("resources", [])],
                    "last_modified": ds.get("metadata_modified", ""),
                    "groups": [g.get("name") for g in ds.get("groups", [])],
                }
                for ds in datasets
            ]
            return json.dumps(
                {"total": total, "count": len(simplified), "offset": params.offset, "datasets": simplified},
                ensure_ascii=False, indent=2,
            )

        lines = [
            f"# BLV Open Data Datensätze\n",
            f"**{total} Datensätze total** | Zeige {params.offset + 1}–{params.offset + len(datasets)}\n",
        ]
        for ds in datasets:
            title = _get_multilingual_title(ds)
            desc = _get_multilingual_description(ds, max_chars=150)
            formats = ", ".join(set(r.get("format", "?").upper() for r in ds.get("resources", [])))
            modified = ds.get("metadata_modified", "")[:10]
            ds_id = ds.get("name", "")
            lines += [
                f"## {title}",
                f"- **ID**: `{ds_id}`",
                f"- **Formate**: {formats}",
                f"- **Aktualisiert**: {modified}",
            ]
            if desc:
                lines.append(f"- **Beschreibung**: {desc}")
            lines.append(f"- **Link**: https://opendata.swiss/de/dataset/{ds_id}")
            lines.append("")

        if total > params.offset + len(datasets):
            next_offset = params.offset + params.limit
            lines.append(f"*Weitere Datensätze verfügbar. Offset {next_offset} verwenden.*")

        return "\n".join(lines)

    except Exception as e:
        return _handle_http_error(e, "blv_list_datasets")


@mcp.tool(
    name="blv_get_dataset_info",
    annotations={
        "title": "BLV Datensatz-Details und Ressource-URLs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_dataset_info(params: DatasetInfoInput) -> str:
    """Gibt detaillierte Metadaten und Download-URLs für einen BLV-Datensatz zurück.

    Enthält alle verfügbaren Ressourcen (CSV, JSON, PARQUET, SPARQL, XML) mit
    direkten Download-URLs. Nützlich um die richtigen Ressource-URLs für
    nachfolgende Datenabfragen zu ermitteln.

    Bekannte Dataset-IDs:
    - tiergesundheitsstatistik
    - fleischkontrollstatistik
    - lebensmittelkontrolle
    - antibiotikaeinsatz-in-der-veterinarmedizin
    - meldepflichtige-tierseuchen-in-der-schweiz
    - uberwachung-von-wildvogeln-auf-aviare-influenza-ai
    - menuch-kids-fragebogen
    - pflanzenschutzmittelverzeichnisw
    - pfas-analysen-in-milch-und-milchprodukten
    - salz-in-fertiggerichten

    Args:
        params: DatasetInfoInput mit:
            - dataset_id (str): CKAN Dataset-ID (z.B. 'tiergesundheitsstatistik')
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Datensatz-Metadaten inkl. aller Ressource-URLs und Formate.
    """
    try:
        ds = await _ckan_get_dataset_resources(params.dataset_id)
        if not ds:
            return f"Datensatz '{params.dataset_id}' nicht gefunden."

        title = _get_multilingual_title(ds)
        desc = _get_multilingual_description(ds, max_chars=500)
        resources = ds.get("resources", [])
        modified = ds.get("metadata_modified", "")[:10]
        groups = [g.get("display_name", {}).get("de", g.get("name", "")) for g in ds.get("groups", [])]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "id": ds.get("name"),
                    "title": title,
                    "description": desc,
                    "last_modified": modified,
                    "categories": groups,
                    "resources": [
                        {
                            "id": r.get("id"),
                            "name": r.get("name", ""),
                            "format": r.get("format", "").upper(),
                            "url": r.get("url", ""),
                            "description": r.get("description", ""),
                        }
                        for r in resources
                    ],
                },
                ensure_ascii=False, indent=2,
            )

        lines = [
            f"# {title}\n",
            f"**Kategorien**: {', '.join(groups)}",
            f"**Zuletzt aktualisiert**: {modified}",
            f"**opendata.swiss**: https://opendata.swiss/de/dataset/{ds.get('name', '')}",
        ]
        if desc:
            lines += [f"\n{desc}"]

        lines.append("\n## Verfügbare Ressourcen\n")
        for r in resources:
            fmt = r.get("format", "?").upper()
            name = r.get("name", r.get("id", ""))[:80]
            url = r.get("url", "")
            rdesc = (r.get("description", "") or "")[:100]
            lines.append(f"### {fmt} — {name}")
            if rdesc:
                lines.append(f"_{rdesc}_")
            lines.append(f"URL: `{url}`")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return _handle_http_error(e, "blv_get_dataset_info")


@mcp.tool(
    name="blv_search_animal_diseases",
    annotations={
        "title": "Tierseuchen-Meldungen Schweiz (InfoSM, seit 1991)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_search_animal_diseases(params: AnimalDiseasesInput) -> str:
    """Durchsucht die Tierseuchenmeldungen der Schweiz seit 1991 (InfoSM-Datenbank).

    Enthält alle Ausbrüche meldepflichtiger Tierseuchen (Maul-und-Klauenseuche,
    Klassische Schweinepest, Blauzungenkrankheit, etc.) nach Tierart, Kanton und Jahr.
    Daten stammen aus dem SPARQL-Endpoint des BLV auf lindas.admin.ch.

    Demo-Anwendungsfall für KI-Fachgruppe:
    'Welche Tierseuchen gab es in Zürich in den letzten 5 Jahren?'
    'Gibt es aktuell Rinderseuchen in der Nähe von Schulbauernhöfen?'

    Args:
        params: AnimalDiseasesInput mit:
            - species (str, optional): Tierart (z.B. 'Rind', 'Schwein', 'Geflügel')
            - canton (str, optional): Kantonskürzel 2-stellig (z.B. 'ZH')
            - year_from (int, optional): Startjahr (frühestens 1991)
            - year_to (int, optional): Endjahr
            - limit (int): Maximale Anzahl Ergebnisse
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Tierseuchenmeldungen mit Tierart, Kanton, Datum, Seuche und Anzahl Fälle.
    """
    # Build SPARQL query against LINDAS
    # Graph: https://ld.admin.ch/graph/blv/tierseuchen (InfoSM dataset)
    filters = []
    if params.species:
        filters.append(f'FILTER(CONTAINS(LCASE(STR(?tierart)), LCASE("{params.species}")))')
    if params.canton:
        filters.append(f'FILTER(CONTAINS(STR(?kanton), "{params.canton.upper()}"))')
    if params.year_from:
        filters.append(f"FILTER(YEAR(?datum) >= {params.year_from})")
    if params.year_to:
        filters.append(f"FILTER(YEAR(?datum) <= {params.year_to})")

    filter_str = "\n  ".join(filters)

    sparql_query = f"""
PREFIX schema: <http://schema.org/>
PREFIX blv: <https://ld.admin.ch/blv/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-syntax-ns#>

SELECT ?ausbruch ?seuche ?tierart ?kanton ?datum ?anzahlFaelle
WHERE {{
  GRAPH <https://lindas.admin.ch/foag/tierseuchen> {{
    ?ausbruch a <https://schema.ld.admin.ch/AnimalDisease> ;
              schema:name ?seuche ;
              schema:about ?tierart ;
              schema:spatialCoverage ?kanton ;
              schema:startDate ?datum .
    OPTIONAL {{ ?ausbruch schema:numberOfItems ?anzahlFaelle }}
  }}
  {filter_str}
}}
ORDER BY DESC(?datum)
LIMIT {params.limit}
"""

    try:
        async with _get_client() as client:
            resp = await client.post(
                SPARQL_ENDPOINT,
                data={"query": sparql_query},
                headers={"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"},
            )

            # Fallback: use CKAN CSV if SPARQL fails
            if resp.status_code != 200:
                return await _animal_diseases_from_csv(params)

        sparql_data = resp.json()
        bindings = sparql_data.get("results", {}).get("bindings", [])

        if not bindings:
            # Fallback to CSV
            return await _animal_diseases_from_csv(params)

        records = [
            {
                "seuche": b.get("seuche", {}).get("value", ""),
                "tierart": b.get("tierart", {}).get("value", "").split("/")[-1],
                "kanton": b.get("kanton", {}).get("value", "").split("/")[-1],
                "datum": b.get("datum", {}).get("value", "")[:10],
                "anzahl_faelle": b.get("anzahlFaelle", {}).get("value", "—"),
            }
            for b in bindings
        ]

        return _format_disease_response(records, params.response_format, len(records))

    except Exception:
        # Graceful fallback to CSV data
        try:
            return await _animal_diseases_from_csv(params)
        except Exception as e2:
            return _handle_http_error(e2, "blv_search_animal_diseases")


async def _animal_diseases_from_csv(params: AnimalDiseasesInput) -> str:
    """Fallback: fetch animal disease data from CKAN CSV resource."""
    ds = await _ckan_get_dataset_resources(DATASET_IDS["tiergesundheitsstatistik"])
    resources = ds.get("resources", [])
    resource = _find_resource_by_format(resources, ["JSON", "CSV", "PARQUET"])
    if not resource:
        return "Fehler: Keine CSV/JSON-Ressource für Tiergesundheitsstatistik gefunden."

    url = resource["url"]
    fmt = resource.get("format", "CSV").upper()

    if fmt == "JSON":
        data = await _fetch_json_resource(url)
        if isinstance(data, list):
            records_raw = data
        else:
            records_raw = data.get("records", data.get("results", []))
    else:
        records_raw = await _fetch_csv_resource(url, max_rows=params.limit * 3)

    # Filter
    records = _filter_records(records_raw, {
        "year": params.year_from,
        "year_to": params.year_to,
    })
    if params.species:
        records = [r for r in records if params.species.lower() in str(r).lower()]
    if params.canton:
        records = [r for r in records if params.canton.upper() in str(r).upper()]

    records = records[: params.limit]
    return _format_disease_response(records, params.response_format, len(records))


def _filter_records(records: list, filters: dict) -> list:
    """Apply year and other filters to records list."""
    result = records
    if filters.get("year"):
        result = [r for r in result if str(filters["year"]) in str(r)]
    if filters.get("year_to"):
        # Keep only records up to year_to
        result = [r for r in result if not any(
            str(y) in str(r) for y in range(filters["year_to"] + 1, 2027)
        )]
    return result


def _format_disease_response(records: list, fmt: ResponseFormat, total: int) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps({"total": total, "records": records}, ensure_ascii=False, indent=2)
    return _format_records_markdown(records, "Tierseuchenmeldungen Schweiz", max_rows=len(records))


@mcp.tool(
    name="blv_get_animal_health_stats",
    annotations={
        "title": "Tiergesundheitsstatistik Schweiz",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_animal_health_stats(params: AnimalHealthStatsInput) -> str:
    """Ruft die jährliche Tiergesundheitsstatistik des BLV ab.

    Enthält Auftreten meldepflichtiger Tierseuchen basierend auf gesetzlichen Vorgaben.
    Veröffentlicht als CSV, JSON und Parquet auf opendata.swiss.

    Nützlich für: Jahresberichte, Trendanalysen, Schulausflug-Risikobeurteilung,
    veterinärmedizinische Forschung.

    Args:
        params: AnimalHealthStatsInput mit:
            - year (int, optional): Filterjahr
            - max_rows (int): Maximale Anzahl Zeilen (Standard 100)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Tiergesundheitsdaten mit Seuchenname, Tierart, Jahr, Anzahl Fälle.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["tiergesundheitsstatistik"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["JSON", "CSV"])
        if not resource:
            return "Fehler: Keine JSON/CSV-Ressource gefunden."

        url = resource["url"]
        fmt = resource.get("format", "CSV").upper()

        if fmt == "JSON":
            raw = await _fetch_json_resource(url)
            records = raw if isinstance(raw, list) else raw.get("records", [])
        else:
            records = await _fetch_csv_resource(url, max_rows=params.max_rows * 2)

        if params.year:
            records = [r for r in records if str(params.year) in str(r)]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Tiergesundheitsstatistik Schweiz", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_get_animal_health_stats")


@mcp.tool(
    name="blv_get_food_control_results",
    annotations={
        "title": "Lebensmittelkontrolle Schweiz (Kantonale Ergebnisse)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_food_control_results(params: FoodControlInput) -> str:
    """Ruft Ergebnisse der kantonalen Lebensmittelkontrollen ab.

    Die kantonalen Lebensmittelvollzugsbehörden kontrollieren Betriebe und Lebensmittel
    und melden die Ergebnisse an das BLV. Enthält Anzahl Kontrollen, Beanstandungen
    und Massnahmen nach Kanton und Jahr.

    Relevant für: Schulkantinen-Compliance, Beschaffungsentscheide, Risikokommunikation,
    Vergleiche zwischen Kantonen.

    Args:
        params: FoodControlInput mit:
            - year (int, optional): Filterjahr
            - canton (str, optional): Kantonskürzel (z.B. 'ZH')
            - max_rows (int): Maximale Zeilen
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Kontrollresultate nach Kanton, Jahr, Betriebstyp, Beanstandungsquote.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["lebensmittelkontrolle"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["CSV", "JSON"])
        if not resource:
            return "Fehler: Keine CSV-Ressource für Lebensmittelkontrolle gefunden."

        records = await _fetch_csv_resource(resource["url"], max_rows=params.max_rows * 2)

        if params.year:
            records = [r for r in records if str(params.year) in str(r)]
        if params.canton:
            records = [r for r in records if params.canton.upper() in str(r).upper()]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Lebensmittelkontrolle Schweiz", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_get_food_control_results")


@mcp.tool(
    name="blv_get_antibiotic_usage_vet",
    annotations={
        "title": "Antibiotikaverbrauch in der Veterinärmedizin (ISABV)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_antibiotic_usage_vet(params: AntibioticUsageInput) -> str:
    """Ruft Daten zum Antibiotikaverbrauch in der Veterinärmedizin ab (ISABV-System).

    Das Informationssystem Antibiotika in der Veterinärmedizin (ISABV) erfasst
    detaillierte Daten zum Antibiotikaverbrauch durch Tierärzte und Tierarztpraxen.
    Wichtig für Antibiotikaresistenz-Monitoring und One-Health-Perspektive.

    Relevant für: Öffentliche Gesundheit, One-Health-Initiativen, Forschung,
    KI-Fachgruppe-Demos zur Verknüpfung von Human- und Tiermedizindaten.

    Args:
        params: AntibioticUsageInput mit:
            - year (int, optional): Filterjahr
            - max_rows (int): Maximale Zeilen
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Antibiotikaverbrauchsdaten nach Wirkstoffklasse, Tierart, Jahr und Region.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["antibiotikaeinsatz"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["CSV", "JSON"])
        if not resource:
            return "Fehler: Keine CSV-Ressource für Antibiotikaverbrauch gefunden."

        records = await _fetch_csv_resource(resource["url"], max_rows=params.max_rows * 2)

        if params.year:
            records = [r for r in records if str(params.year) in str(r)]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Antibiotikaverbrauch Veterinärmedizin (ISABV)", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_get_antibiotic_usage_vet")


@mcp.tool(
    name="blv_get_avian_influenza",
    annotations={
        "title": "Aviäre Influenza (Vogelgrippe) Wildvogel-Überwachung",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_avian_influenza(params: AvianInfluenzaInput) -> str:
    """Ruft Überwachungsdaten zur Aviären Influenza (Vogelgrippe) bei Wildvögeln ab.

    Die Aviäre Influenza ist eine hochansteckende Viruserkrankung. Wildvögel gelten
    als natürliches Reservoir. Das BLV überwacht systematisch gefundene tote Wildvögel
    und veröffentlicht Positiv-Nachweise. Daten inkl. KML-Geodaten verfügbar.

    Relevant für: Schulausflüge an Gewässern, Naturpädagogik, Risikobeurteilung,
    Geodaten-Kombination mit zurich-opendata-mcp für räumliche Analysen.

    Geo-Kombination: Kombination mit zurich-opendata-mcp Geodaten möglich um
    Risikogebiete in der Nähe von Schulstandorten zu identifizieren.

    Args:
        params: AvianInfluenzaInput mit:
            - year (int, optional): Filterjahr
            - region (str, optional): Regionsname oder Kanton
            - max_rows (int): Maximale Zeilen
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Vogelgrippe-Nachweise mit Datum, Ort, Vogelart, Virustyp.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["avian_influenza"])
        resources = ds.get("resources", [])
        # Prefer JSON or CSV over SPARQL/KML for simplicity
        resource = _find_resource_by_format(resources, ["JSON", "CSV"])
        if not resource:
            resource = _find_resource_by_format(resources, ["KML", "SPARQL"])
        if not resource:
            return "Fehler: Keine geeignete Ressource für Aviäre Influenza-Daten gefunden."

        fmt = resource.get("format", "CSV").upper()
        url = resource["url"]

        if fmt == "JSON":
            raw = await _fetch_json_resource(url)
            records = raw if isinstance(raw, list) else raw.get("records", [])
        elif fmt == "CSV":
            records = await _fetch_csv_resource(url, max_rows=params.max_rows * 2)
        else:
            # KML or SPARQL — fetch as text and return info
            async with _get_client() as client:
                resp = await client.get(url)
            return f"Aviäre Influenza Daten verfügbar als {fmt}. URL: {url}\n\nFür strukturierte Daten bitte blv_get_dataset_info('uberwachung-von-wildvogeln-auf-aviare-influenza-ai') nutzen."

        if params.year:
            records = [r for r in records if str(params.year) in str(r)]
        if params.region:
            records = [r for r in records if params.region.lower() in str(r).lower()]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Aviäre Influenza — Wildvogel-Überwachung", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_get_avian_influenza")


@mcp.tool(
    name="blv_get_nutrition_data_children",
    annotations={
        "title": "Ernährungserhebung Kinder & Jugendliche (menuCH-Kids)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_nutrition_data_children(params: NutritionSurveyInput) -> str:
    """Ruft Daten der nationalen Ernährungserhebung für Kinder und Jugendliche (menuCH-Kids) ab.

    Erstmalige nationale Erhebung der Ernährung von Kindern und Jugendlichen in der Schweiz.
    Enthält Verzehrsdaten, Nährstoffzufuhr, Lebensmittelgruppen nach Altersgruppe,
    Geschlecht und Region.

    Für Schulamt besonders relevant:
    - Vergleich städtischer vs. ländlicher Ernährungsgewohnheiten
    - Grundlage für Schulverpflegungskonzepte
    - Kombination mit swiss-statistics-mcp: Soziodemographie nach Schulkreis
    - Kombination mit global-education-mcp: CH vs. OECD-Vergleich

    Args:
        params: NutritionSurveyInput mit:
            - age_group (str, optional): Altersgruppe-Filter
            - max_rows (int): Maximale Zeilen
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ernährungsdaten mit Altersgruppe, Lebensmittelgruppe, Verzehrsmengen.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["menuch_kids"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["CSV", "JSON"])
        if not resource:
            return "Fehler: Keine CSV-Ressource für menuCH-Kids gefunden."

        records = await _fetch_csv_resource(resource["url"], max_rows=params.max_rows * 2)

        if params.age_group:
            records = [r for r in records if params.age_group.lower() in str(r).lower()]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)

        lines = [
            "# Ernährungserhebung Kinder & Jugendliche (menuCH-Kids)\n",
            "**Quelle**: BLV / opendata.swiss | Erste nationale Ernährungserhebung für Kinder in der Schweiz\n",
        ]
        lines.append(_format_records_markdown(records, "", max_rows=len(records)))
        return "\n".join(lines)

    except Exception as e:
        return _handle_http_error(e, "blv_get_nutrition_data_children")


@mcp.tool(
    name="blv_search_pesticide_products",
    annotations={
        "title": "Pflanzenschutzmittelverzeichnis (PSM) durchsuchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_search_pesticide_products(params: PesticideSearchInput) -> str:
    """Durchsucht das offizielle Schweizer Pflanzenschutzmittelverzeichnis (BLV/BLW).

    Enthält alle in der Schweiz zugelassenen Pflanzenschutzmittel mit Wirkstoffen,
    zugelassenen Kulturen, Auflagen und Zulassungsstatus. Abfrage über das
    Pflanzenschutzmittel-Verzeichnis psm.admin.ch.

    Relevant für: Schulgärten, Liegenschaften der Stadt, Beschaffung,
    Umweltbildung (Pestizidreduktion), Rechtskonformität.

    Kombination mit fedlex-mcp: Verknüpfung mit Pflanzenschutzgesetz (PflSchG)
    und Zulassungsverordnungen.

    Args:
        params: PesticideSearchInput mit:
            - product_name (str, optional): Produktname (z.B. 'Karate', 'Copper')
            - active_ingredient (str, optional): Wirkstoff (z.B. 'Kupfer', 'Spinosad')
            - max_rows (int): Maximale Anzahl Ergebnisse
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Pflanzenschutzmittel mit Produktname, Wirkstoffen, Kulturen, Zulassungsstatus.
    """
    try:
        # Fetch XML dataset from CKAN
        ds = await _ckan_get_dataset_resources(DATASET_IDS["pflanzenschutzmittel"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["XML", "CSV", "JSON"])

        if not resource:
            return "Fehler: Keine XML/CSV-Ressource für Pflanzenschutzmittelverzeichnis gefunden."

        url = resource["url"]
        fmt = resource.get("format", "").upper()

        async with _get_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()

        if fmt == "XML":
            records = _parse_psm_xml(resp.text, params.product_name, params.active_ingredient, params.max_rows)
        elif fmt == "CSV":
            records_raw = _parse_csv_to_records(resp.text, max_rows=params.max_rows * 5)
            records = _filter_psm_records(records_raw, params.product_name, params.active_ingredient)
            records = records[: params.max_rows]
        else:
            return f"Format {fmt} nicht unterstützt. Ressource-URL: {url}"

        if not records:
            filters = []
            if params.product_name:
                filters.append(f"Produktname: '{params.product_name}'")
            if params.active_ingredient:
                filters.append(f"Wirkstoff: '{params.active_ingredient}'")
            return f"Keine Pflanzenschutzmittel gefunden für: {', '.join(filters) or 'alle'}."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "products": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Pflanzenschutzmittelverzeichnis (PSM)", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_search_pesticide_products")


def _parse_psm_xml(xml_text: str, name_filter: str | None, ingredient_filter: str | None, max_rows: int) -> list:
    """Parse PSM XML response into records list."""
    try:
        root = ET.fromstring(xml_text)
        records = []
        # Handle various XML structures
        products = root.findall(".//product") or root.findall(".//Produkt") or root.findall(".//PSM")
        for prod in products:
            if len(records) >= max_rows:
                break
            record = {}
            for child in prod:
                record[child.tag] = (child.text or "").strip()

            # Name filter
            prod_name = str(record).lower()
            if name_filter and name_filter.lower() not in prod_name:
                continue
            if ingredient_filter and ingredient_filter.lower() not in prod_name:
                continue
            records.append(record)
        return records
    except ET.ParseError:
        return []


def _filter_psm_records(records: list, name_filter: str | None, ingredient_filter: str | None) -> list:
    """Filter PSM records by name and/or ingredient."""
    result = records
    if name_filter:
        result = [r for r in result if name_filter.lower() in str(r).lower()]
    if ingredient_filter:
        result = [r for r in result if ingredient_filter.lower() in str(r).lower()]
    return result


@mcp.tool(
    name="blv_get_meat_inspection_stats",
    annotations={
        "title": "Fleischkontrollstatistik Schweiz",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def blv_get_meat_inspection_stats(params: AnimalHealthStatsInput) -> str:
    """Ruft die Fleischkontrollstatistik der Schweiz ab.

    Alle Tiere, die in einem bewilligten Schlachtbetrieb geschlachtet werden,
    müssen vor und nach der Schlachtung untersucht werden. Enthält Anzahl
    Schlachtungen, Beanstandungen und Befunde nach Tierart, Kanton und Jahr.

    Relevant für: Lebensmittelsicherheits-Berichte, Schulverpflegung (Fleischqualität),
    Gemeinschaftsgastronomie, Beschaffungsentscheide städtischer Küchen.

    Args:
        params: AnimalHealthStatsInput mit:
            - year (int, optional): Filterjahr
            - max_rows (int): Maximale Zeilen
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Fleischkontrolldaten mit Tierart, Schlachtbetrieb, Anzahl, Befunde.
    """
    try:
        ds = await _ckan_get_dataset_resources(DATASET_IDS["fleischkontrollstatistik"])
        resources = ds.get("resources", [])
        resource = _find_resource_by_format(resources, ["JSON", "CSV", "PARQUET"])
        if not resource:
            return "Fehler: Keine geeignete Ressource für Fleischkontrollstatistik gefunden."

        fmt = resource.get("format", "CSV").upper()
        url = resource["url"]

        if fmt == "JSON":
            raw = await _fetch_json_resource(url)
            records = raw if isinstance(raw, list) else raw.get("records", [])
        else:
            records = await _fetch_csv_resource(url, max_rows=params.max_rows * 2)

        if params.year:
            records = [r for r in records if str(params.year) in str(r)]
        records = records[: params.max_rows]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2)
        return _format_records_markdown(records, "Fleischkontrollstatistik Schweiz", max_rows=len(records))

    except Exception as e:
        return _handle_http_error(e, "blv_get_meat_inspection_stats")


# ─────────────────────────────────────────────
# Multilingual helpers (CKAN datasets)
# ─────────────────────────────────────────────

def _get_multilingual_title(ds: dict) -> str:
    """Extract German title from CKAN dataset, fallback to English/any."""
    title = ds.get("title", {})
    if isinstance(title, dict):
        return title.get("de", title.get("en", title.get("fr", str(title))))
    title_translated = ds.get("title_translated", {})
    if isinstance(title_translated, dict):
        return title_translated.get("de", title_translated.get("en", ds.get("title", "")))
    return str(title)


def _get_multilingual_description(ds: dict, max_chars: int = 300) -> str:
    """Extract German description from CKAN dataset."""
    notes = ds.get("notes", {})
    if isinstance(notes, dict):
        desc = notes.get("de", notes.get("en", ""))
    else:
        notes_translated = ds.get("notes_translated", {})
        if isinstance(notes_translated, dict):
            desc = notes_translated.get("de", notes_translated.get("en", str(notes or "")))
        else:
            desc = str(notes or "")
    if desc and len(desc) > max_chars:
        desc = desc[:max_chars] + "…"
    return desc


# ─────────────────────────────────────────────
# MCP Resources
# ─────────────────────────────────────────────

@mcp.resource("blv://datasets/overview")
async def get_datasets_overview() -> str:
    """Übersicht aller verfügbaren BLV-Datensätze als strukturierte Ressource."""
    return json.dumps(DATASET_IDS, ensure_ascii=False, indent=2)


@mcp.resource("blv://info/server")
async def get_server_info() -> str:
    """Server-Metadaten und Quellenübersicht."""
    return json.dumps(
        {
            "server": "swiss-food-safety-mcp",
            "version": "1.0.0",
            "author": "malkreide",
            "data_sources": {
                "opendata_swiss_ckan": CKAN_API_BASE,
                "sparql_lindas": SPARQL_ENDPOINT,
                "rss_warnings_de": RSS_WARNINGS_DE,
            },
            "tools": [
                "blv_get_public_warnings",
                "blv_list_datasets",
                "blv_get_dataset_info",
                "blv_search_animal_diseases",
                "blv_get_animal_health_stats",
                "blv_get_food_control_results",
                "blv_get_antibiotic_usage_vet",
                "blv_get_avian_influenza",
                "blv_get_nutrition_data_children",
                "blv_search_pesticide_products",
                "blv_get_meat_inspection_stats",
            ],
            "authentication": "none_required",
            "license": "open_government_data",
        },
        ensure_ascii=False, indent=2,
    )


# ─────────────────────────────────────────────
# MCP Prompts
# ─────────────────────────────────────────────

@mcp.prompt(name="food_safety_brief")
async def food_safety_brief() -> str:
    """Erstellt einen aktuellen Lebensmittelsicherheits-Brief für Schulkantinen."""
    return (
        "Erstelle einen strukturierten Sicherheits-Brief für städtische Schulkantinen. "
        "Nutze folgende Tools in dieser Reihenfolge:\n"
        "1. blv_get_public_warnings() — aktuelle Rückrufe und Warnungen\n"
        "2. blv_get_food_control_results(year=2024) — Beanstandungsquoten\n"
        "3. blv_get_meat_inspection_stats(year=2024) — Fleischkontrollresultate\n\n"
        "Struktur des Briefs: Zusammenfassung → Aktuelle Warnungen → Massnahmenempfehlungen → Quellen."
    )


@mcp.prompt(name="animal_disease_risk_assessment")
async def animal_disease_risk_assessment() -> str:
    """Risikobeurteilung Tierseuchen für Schulausflüge auf Bauernhöfe."""
    return (
        "Erstelle eine Risikobeurteilung für Schulausflüge auf Bauernhöfe im Kanton Zürich.\n"
        "1. blv_search_animal_diseases(canton='ZH', year_from=2023) — aktuelle Seuchenlagen\n"
        "2. blv_get_avian_influenza(year=2024) — Vogelgrippe-Situation\n"
        "3. blv_get_public_warnings() — aktuelle Tierseuchen-Warnungen\n\n"
        "Bewerte: Risikostufe (tief/mittel/hoch), empfohlene Schutzmassnahmen, "
        "Empfehlung für/gegen Ausflug."
    )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main():
    import sys
    transport = "streamable_http" if "--http" in sys.argv else "stdio"
    port = 8002
    if transport == "streamable_http":
        mcp.run(transport=transport, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
