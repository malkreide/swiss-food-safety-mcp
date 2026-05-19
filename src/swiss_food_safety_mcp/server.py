"""
swiss-food-safety-mcp — server.py
==================================
MCP Server for Swiss Federal Food Safety and Veterinary Office (BLV) open data.

Transport:
  stdio (default)          → Claude Desktop, Cursor, Windsurf
  --http (port 8002)       → Streamable HTTP for cloud / Render.com

Entry point: `swiss-food-safety-mcp` (defined in pyproject.toml)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import ipaddress
import logging
import socket
import sys
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
import httpx
from fastmcp import Context, FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from typing_extensions import TypedDict

SERVER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Logging — to stderr only; stdout is reserved for the MCP protocol (OBS-003)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("swiss-food-safety-mcp")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Runtime configuration — every field is overridable via a BLV_MCP_* env var."""

    model_config = SettingsConfigDict(env_prefix="BLV_MCP_")

    ckan_base: str = "https://opendata.swiss/api/3/action"
    blv_org_id: str = "bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv"
    sparql_endpoint: str = "https://lindas.admin.ch/sparql"
    blv_rss: str = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079"
    timeout: float = 20.0
    http_host: str = "127.0.0.1"
    http_port: int = 8002
    allowed_origins: str = "https://claude.ai"
    otel_endpoint: str = ""  # OTLP/HTTP endpoint; tracing stays off when empty


settings = Settings()

CKAN_BASE = settings.ckan_base
BLV_ORG_ID = settings.blv_org_id
SPARQL_ENDPOINT = settings.sparql_endpoint
BLV_RSS = settings.blv_rss
TIMEOUT = settings.timeout
MAX_RESULTS = 200

# CH-004: provenance attribution attached to structured tool results.
DATA_SOURCE = "opendata.swiss / Federal Food Safety and Veterinary Office (BLV)"
DATA_LICENSE = "CC BY 4.0"

# SEC-021: immutable egress allow-list. Outbound requests may only target
# Swiss federal open-data hosts. Intentionally a frozenset (not configurable).
ALLOWED_EGRESS_SUFFIXES: frozenset[str] = frozenset({"admin.ch", "opendata.swiss"})

# OBS-001: stable execution-error codes (distinct from raised protocol errors).
ERR_NO_DATASET = "no_dataset"
ERR_NO_RESOURCE = "no_resource"
ERR_UPSTREAM = "upstream_unavailable"


# ---------------------------------------------------------------------------
# Typed result shapes (SDK-002)
# ---------------------------------------------------------------------------


class WarningItem(TypedDict):
    """A single BLV public warning / recall."""

    title: str
    link: str
    description: str
    pubDate: str
    source: str


class DatasetSummary(TypedDict):
    """Compact summary of a BLV open dataset."""

    name: str
    title: str
    notes: str
    num_resources: int
    url: str
    source: str


class ResourceInfo(TypedDict):
    """A downloadable resource of a dataset."""

    name: str
    format: str
    url: str
    description: str


class DatasetInfo(TypedDict):
    """Full metadata of a BLV open dataset."""

    name: str
    title: str
    notes: str
    organization: str
    license: str
    num_resources: int
    resources: list[ResourceInfo]
    source: str


class DiseaseCase(TypedDict):
    """A notifiable animal-disease case record."""

    year: str
    canton: str
    disease: str
    cases: str
    source: str


def _error(message: str, code: str, **extra: Any) -> dict[str, Any]:
    """Build a structured execution-error record (OBS-001)."""
    return {"error": message, "code": code, **extra}


# ---------------------------------------------------------------------------
# Observability — OpenTelemetry tracing (OBS-006, opt-in)
# ---------------------------------------------------------------------------


def _setup_telemetry() -> None:
    """Enable OpenTelemetry tracing when BLV_MCP_OTEL_ENDPOINT is configured.

    Tracing is an optional extra (`pip install swiss-food-safety-mcp[otel]`).
    When the endpoint is unset, or the packages are absent, this is a no-op.
    """
    if not settings.otel_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("OpenTelemetry packages not installed; tracing disabled")
        return

    provider = TracerProvider(resource=Resource.create({"service.name": "swiss-food-safety-mcp"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint))
    )
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    logger.info("OpenTelemetry tracing enabled (endpoint=%s)", settings.otel_endpoint)


# ---------------------------------------------------------------------------
# Networking — SSRF-guarded shared HTTP client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _host_allowed(host: str) -> bool:
    """True if host equals or is a subdomain of an allow-listed federal domain."""
    host = (host or "").lower().rstrip(".")
    return any(host == s or host.endswith("." + s) for s in ALLOWED_EGRESS_SUFFIXES)


async def _guard_url(url: str) -> None:
    """SSRF guard — enforce HTTPS, the egress allow-list, and public-IP targets.

    Raises ValueError if the URL is not permitted. The allow-list also defeats
    DNS rebinding: an attacker cannot rebind a federal domain they do not own.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Refusing non-HTTPS request")
    host = parsed.hostname or ""
    if not _host_allowed(host):
        raise ValueError("Host not on egress allow-list")
    infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Host resolves to a non-public address")


async def _on_response(response: httpx.Response) -> None:
    """Re-validate every hop — a redirect must not leave the allow-list."""
    if not _host_allowed(response.request.url.host):
        raise ValueError("Redirect target not on egress allow-list")


@asynccontextmanager
async def _lifespan(_app: FastMCP):
    """Hold one pooled, SSRF-guarded HTTP client for the server's lifetime."""
    global _client
    _setup_telemetry()
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": f"swiss-food-safety-mcp/{SERVER_VERSION}"},
        event_hooks={"response": [_on_response]},
    ) as client:
        _client = client
        logger.info("swiss-food-safety-mcp ready (version %s)", SERVER_VERSION)
        try:
            yield
        finally:
            _client = None


async def _get(url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
    """SSRF-guarded async HTTP GET using the pooled client."""
    await _guard_url(url)
    if _client is None:
        raise RuntimeError("HTTP client is not initialized")
    return await _client.get(url, params=params, headers=headers or {})


async def _step(ctx: Context | None, done: int, total: int, message: str) -> None:
    """Emit a progress update and a debug log line (SDK-003).

    Best-effort: a no-op when there is no active MCP session (internal calls,
    tests), and always recorded server-side via the logger regardless.
    """
    logger.debug(message)
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=done, total=total)
        await ctx.debug(message)
    except RuntimeError:
        pass  # no active MCP session


async def _ctx_log(ctx: Context | None, level: str, message: str) -> None:
    """Best-effort client-facing log via the MCP context; always logs server-side."""
    getattr(logger, level)(message)
    if ctx is None:
        return
    try:
        await getattr(ctx, level)(message)
    except RuntimeError:
        pass  # no active MCP session


# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="swiss-food-safety-mcp",
    version=SERVER_VERSION,
    mask_error_details=True,
    lifespan=_lifespan,
    instructions=(
        "Tools for Swiss Federal Food Safety and Veterinary Office (BLV) open data. "
        "Covers food recalls, animal disease surveillance, food control results, "
        "antibiotic usage in veterinary medicine, children's nutrition, and the "
        "pesticide register. All data from official Swiss federal sources. No auth needed."
    ),
)

# ARCH-009: every tool is a read-only, idempotent call to an external API.
READ_ONLY_TOOL = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ckan_resource_url(package: dict, fmt: str) -> str | None:
    """Return first resource URL matching format (case-insensitive)."""
    for r in package.get("resources", []):
        if r.get("format", "").upper() == fmt.upper():
            return r.get("url")
    return None


async def _fetch_csv(url: str) -> list[dict]:
    """Download a CSV and return as list of dicts."""
    r = await _get(url)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    return list(reader)


def _sparql_escape(value: str) -> str:
    """Escape a string for safe inclusion inside a SPARQL string literal."""
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


async def _find_dataset(ctx: Context | None, search: str) -> str | None:
    """Resolve a dataset slug from a keyword search, or None if nothing matches."""
    datasets = await blv_list_datasets(search=search)
    if not datasets:
        await _ctx_log(ctx, "warning", f"No BLV dataset matched search '{search}'")
        return None
    return datasets[0]["name"]


# ---------------------------------------------------------------------------
# Tool 1: Public warnings & recalls
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_public_warnings(limit: int = 20, ctx: Context | None = None) -> list[WarningItem]:
    """
    Current BLV food recalls and public health warnings (live RSS feed).

    Use case: answer questions about food safety alerts currently active in
    Switzerland, e.g. "which products have been recalled recently?".

    Args:
        limit: Maximum number of items to return (default 20, max 50).

    Returns:
        List of warning items with title, link, description, pubDate, source.
    """
    limit = max(1, min(limit, 50))
    await _step(ctx, 1, 1, f"Fetching BLV warnings feed (limit={limit})")
    r = await _get(BLV_RSS)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items: list[WarningItem] = []
    for item in root.findall(".//item")[:limit]:
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "source": DATA_SOURCE,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Tool 2: List BLV datasets
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_list_datasets(
    limit: int = 28,
    search: str = "",
    ctx: Context | None = None,
) -> list[DatasetSummary]:
    """
    Browse all BLV open datasets on opendata.swiss (CKAN API).

    Use case: discover which datasets exist before drilling into one with
    blv_get_dataset_info, or to map a topic to a concrete dataset slug.

    Args:
        limit: Maximum datasets to return (default 28 = all BLV datasets).
        search: Optional keyword filter on title/notes.

    Returns:
        List of dataset summaries with name, title, notes, num_resources, source.
    """
    limit = max(1, min(limit, 100))
    params: dict[str, Any] = {
        "fq": f"organization:{BLV_ORG_ID}",
        "rows": limit,
        "start": 0,
    }
    if search:
        params["q"] = search

    await _step(ctx, 1, 1, f"Searching BLV datasets (search='{search}', limit={limit})")
    r = await _get(f"{CKAN_BASE}/package_search", params=params)
    r.raise_for_status()
    data = r.json()
    results: list[DatasetSummary] = []
    for ds in data.get("result", {}).get("results", []):
        results.append(
            {
                "name": ds.get("name", ""),
                "title": ds.get("title", {}).get("de", ds.get("title", "")),
                "notes": (ds.get("notes", {}).get("de", ds.get("notes", "")) or "")[:200],
                "num_resources": len(ds.get("resources", [])),
                "url": f"https://opendata.swiss/de/dataset/{ds.get('name', '')}",
                "source": DATA_SOURCE,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Tool 3: Dataset info
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_dataset_info(dataset_name: str, ctx: Context | None = None) -> dict[str, Any]:
    """
    Detailed metadata and resource URLs for a specific BLV dataset.

    Use case: obtain the concrete download URLs and formats of a dataset found
    via blv_list_datasets, including its open-data licence.

    Args:
        dataset_name: CKAN dataset name/slug (from blv_list_datasets).

    Returns:
        Full dataset metadata including all resource download URLs and formats.
    """
    r = await _get(f"{CKAN_BASE}/package_show", params={"id": dataset_name})
    r.raise_for_status()
    pkg = r.json().get("result", {})
    if not pkg:
        await _ctx_log(ctx, "warning", f"Dataset '{dataset_name}' not found")
        return _error(
            f"Dataset '{dataset_name}' not found",
            ERR_NO_DATASET,
            note="Call blv_list_datasets() to see valid dataset slugs.",
        )
    resources: list[ResourceInfo] = [
        {
            "name": res.get("name", ""),
            "format": res.get("format", ""),
            "url": res.get("url", ""),
            "description": res.get("description", ""),
        }
        for res in pkg.get("resources", [])
    ]
    result: DatasetInfo = {
        "name": pkg.get("name", ""),
        "title": pkg.get("title", {}).get("de", ""),
        "notes": pkg.get("notes", {}).get("de", ""),
        "organization": pkg.get("organization", {}).get("name", ""),
        "license": pkg.get("license_title", "") or DATA_LICENSE,
        "num_resources": len(resources),
        "resources": resources,
        "source": DATA_SOURCE,
    }
    return result


# ---------------------------------------------------------------------------
# Tool 4: Animal disease search (SPARQL + CSV fallback)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_search_animal_diseases(
    canton: str = "",
    disease: str = "",
    year_from: int = 2020,
    year_to: int = 2024,
    limit: int = 50,
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Search notifiable animal disease cases in Switzerland since 1991 (InfoSM).

    Use case: report on disease occurrence by canton and year, e.g. "were there
    avian influenza cases in Bern in 2024?".

    Args:
        canton: Two-letter canton abbreviation (e.g. "ZH", "BE"). Empty = all cantons.
        disease: Disease name filter (partial match, e.g. "Maul", "Vogelgrippe"). Empty = all.
        year_from: Start year (default 2020).
        year_to: End year (default 2024).
        limit: Maximum results (default 50).

    Returns:
        List of disease case records with year, canton, disease, cases, source.
    """
    limit = max(1, min(limit, MAX_RESULTS))
    canton_esc = _sparql_escape(canton)
    disease_esc = _sparql_escape(disease)

    sparql_query = f"""
    PREFIX schema: <http://schema.org/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?year ?canton ?disease ?cases WHERE {{
      ?record a <https://agriculture.ld.admin.ch/foag/ontology/AnimalDisease> ;
              schema:temporalCoverage ?year ;
              schema:spatialCoverage ?canton ;
              schema:name ?disease ;
              schema:value ?cases .
      FILTER(?year >= {year_from} && ?year <= {year_to})
      {"FILTER(CONTAINS(STR(?canton), '" + canton_esc + "'))" if canton else ""}
      {"FILTER(CONTAINS(LCASE(STR(?disease)), LCASE('" + disease_esc + "')))" if disease else ""}
    }}
    ORDER BY DESC(?year) ?canton
    LIMIT {limit}
    """

    try:
        await _step(ctx, 1, 2, "Querying the LINDAS SPARQL endpoint")
        r = await _get(
            SPARQL_ENDPOINT,
            params={"query": sparql_query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        r.raise_for_status()
        bindings = r.json().get("results", {}).get("bindings", [])
        cases: list[dict[str, Any]] = [
            {
                "year": b.get("year", {}).get("value", ""),
                "canton": b.get("canton", {}).get("value", ""),
                "disease": b.get("disease", {}).get("value", ""),
                "cases": b.get("cases", {}).get("value", ""),
                "source": DATA_SOURCE,
            }
            for b in bindings
        ]
        return cases
    except Exception as exc:
        # SPARQL endpoint unavailable — fall back to the CKAN CSV dataset.
        logger.warning("SPARQL query failed (%s); using CSV fallback", exc)
        await _ctx_log(ctx, "info", "SPARQL endpoint unavailable — using CSV fallback")
        slug = await _find_dataset(ctx, "tierseuchen infosm")
        if slug is None:
            return [
                _error(
                    "SPARQL unavailable and no CSV fallback dataset found",
                    ERR_UPSTREAM,
                    note="Try again later, or browse datasets with blv_list_datasets().",
                )
            ]
        info = await blv_get_dataset_info(slug)
        csv_url = next(
            (r["url"] for r in info.get("resources", []) if r["format"].upper() == "CSV"),
            None,
        )
        if not csv_url:
            return [_error("No CSV resource in the fallback dataset", ERR_NO_RESOURCE)]
        await _step(ctx, 2, 2, "Downloading the CSV fallback dataset")
        rows = await _fetch_csv(csv_url)
        return rows[:limit]


# ---------------------------------------------------------------------------
# Tool 5: Animal health statistics
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_animal_health_stats(
    year: int | None = None, ctx: Context | None = None
) -> list[dict[str, Any]]:
    """
    Annual animal health statistics from BLV (opendata.swiss CSV/JSON).

    Use case: track year-over-year animal health indicators across Switzerland.

    Args:
        year: Filter by year (e.g. 2023). None returns all available years.

    Returns:
        List of annual statistics records.
    """
    slug = await _find_dataset(ctx, "tiergesundheit statistik")
    if slug is None:
        return [
            _error(
                "No animal health statistics dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _ckan_resource_url(info, "CSV") or _ckan_resource_url(info, "JSON")
    if not csv_url:
        return [_error("No CSV/JSON resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading statistics data")
    rows = await _fetch_csv(csv_url)
    if year:
        rows = [r for r in rows if str(year) in str(r.get("Jahr", r.get("year", "")))]
    return rows[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Tool 6: Food control results
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_food_control_results(
    canton: str = "",
    year: int | None = None,
    limit: int = 100,
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Cantonal food inspection results and violation rates (Lebensmittelkontrolle).

    Use case: compare inspection volumes and violation rates between cantons or
    across years.

    Args:
        canton: Two-letter canton abbreviation (e.g. "ZH"). Empty = all.
        year: Filter by year. None = all available.
        limit: Maximum rows to return (default 100).

    Returns:
        List of inspection result records with canton, year, inspections, violations.
    """
    limit = max(1, min(limit, MAX_RESULTS))
    slug = await _find_dataset(ctx, "lebensmittelkontrolle kantone")
    if slug is None:
        return [
            _error(
                "No food control dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [_error("No CSV resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading food control data")
    rows = await _fetch_csv(csv_url)

    if canton:
        rows = [r for r in rows if canton.upper() in str(r).upper()]
    if year:
        rows = [r for r in rows if str(year) in str(r)]
    return rows[:limit]


# ---------------------------------------------------------------------------
# Tool 7: Antibiotic usage veterinary (ISABV)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_antibiotic_usage_vet(
    year: int | None = None,
    animal_species: str = "",
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Veterinary antibiotic usage data from the Swiss ISABV monitoring system.

    Use case: analyse antibiotic consumption trends by livestock species, e.g.
    for antimicrobial-resistance reporting.

    Args:
        year: Filter by year (e.g. 2022). None = all years.
        animal_species: Filter by species (e.g. "Rind", "Schwein", "Geflügel"). Empty = all.

    Returns:
        Antibiotic usage records with year, species, substance class, quantity (kg).
    """
    slug = await _find_dataset(ctx, "antibiotika tierarzneimittel isabv")
    if slug is None:
        return [
            _error(
                "No ISABV antibiotic usage dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [_error("No CSV resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading antibiotic usage data")
    rows = await _fetch_csv(csv_url)

    if year:
        rows = [r for r in rows if str(year) in str(r)]
    if animal_species:
        rows = [r for r in rows if animal_species.lower() in str(r).lower()]
    return rows[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Tool 8: Avian influenza monitoring
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_avian_influenza(
    year: int | None = None,
    canton: str = "",
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Wild bird avian influenza (H5N1 / HPAI) surveillance data with geodata.

    Use case: locate and date wild-bird avian influenza detections, optionally
    narrowed to one canton.

    Args:
        year: Filter by year (e.g. 2024). None = all.
        canton: Two-letter canton code (e.g. "ZH"). Empty = all Switzerland.

    Returns:
        Avian influenza case records with date, location, species, result, coordinates.
    """
    slug = await _find_dataset(ctx, "vogelgrippe aviäre influenza wildvögel")
    if slug is None:
        return [
            _error(
                "No avian influenza dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    data_url = _ckan_resource_url(info, "JSON") or _ckan_resource_url(info, "CSV")
    if not data_url:
        return [_error("No JSON/CSV resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading avian influenza data")
    if data_url.endswith(".json") or "json" in data_url.lower():
        r = await _get(data_url)
        r.raise_for_status()
        rows = r.json() if isinstance(r.json(), list) else [r.json()]
    else:
        rows = await _fetch_csv(data_url)

    if year:
        rows = [r for r in rows if str(year) in str(r)]
    if canton:
        rows = [r for r in rows if canton.upper() in str(r).upper()]
    return rows[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Tool 9: Children's nutrition survey (menuCH-Kids)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_nutrition_data_children(
    age_group: str = "",
    nutrient: str = "",
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Swiss national children's nutrition survey data (menuCH-Kids).

    Use case: examine children's nutrient intake by age group against dietary
    recommendations.

    Args:
        age_group: Filter by age group (e.g. "6-9", "10-12"). Empty = all.
        nutrient: Filter by nutrient name (e.g. "Energie", "Zucker", "Eisen"). Empty = all.

    Returns:
        Nutrition intake records with age group, nutrient, mean intake, unit, recommendation.
    """
    slug = await _find_dataset(ctx, "menuCH kids Kinder Ernährung")
    if slug is None:
        return [
            _error(
                "No children's nutrition dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [_error("No CSV resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading nutrition survey data")
    rows = await _fetch_csv(csv_url)

    if age_group:
        rows = [r for r in rows if age_group in str(r)]
    if nutrient:
        rows = [r for r in rows if nutrient.lower() in str(r).lower()]
    return rows[:300]


# ---------------------------------------------------------------------------
# Tool 10: Pesticide register
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_search_pesticide_products(
    product_name: str = "",
    active_ingredient: str = "",
    status: str = "bewilligt",
    limit: int = 50,
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Search the Swiss approved pesticide register (Pflanzenschutzmittelverzeichnis).

    Use case: check whether a plant-protection product or active ingredient is
    approved (or revoked) in Switzerland.

    Args:
        product_name: Filter by product name (partial match). Empty = all.
        active_ingredient: Filter by active ingredient, e.g. "Kupfer", "Glyphosat". Empty = all.
        status: Authorization status — "bewilligt" (approved), "widerrufen" (revoked), or "".
        limit: Maximum results (default 50).

    Returns:
        Pesticide product records with name, authorization number, active ingredients, status.
    """
    limit = max(1, min(limit, MAX_RESULTS))
    slug = await _find_dataset(ctx, "pflanzenschutzmittel pestizid register")
    if slug is None:
        return [
            _error(
                "No pesticide register dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    xml_url = _ckan_resource_url(info, "XML") or _ckan_resource_url(info, "CSV")
    if not xml_url:
        return [_error("No XML/CSV resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading the pesticide register")
    if xml_url.endswith(".xml") or "xml" in xml_url.lower():
        r = await _get(xml_url)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        results: list[dict[str, Any]] = []
        for product in root.iter("product"):
            name = product.findtext("name", "")
            auth_nr = product.findtext("authorisation_number", "")
            ingredients = [ai.text for ai in product.findall(".//active_ingredient") if ai.text]
            prod_status = product.findtext("status", "")

            if product_name and product_name.lower() not in name.lower():
                continue
            if active_ingredient and not any(
                active_ingredient.lower() in ai.lower() for ai in ingredients
            ):
                continue
            if status and status.lower() not in prod_status.lower():
                continue

            results.append(
                {
                    "name": name,
                    "authorisation_number": auth_nr,
                    "active_ingredients": ingredients,
                    "status": prod_status,
                }
            )
            if len(results) >= limit:
                break
        return results
    else:
        rows = await _fetch_csv(xml_url)
        if product_name:
            rows = [r for r in rows if product_name.lower() in str(r).lower()]
        if active_ingredient:
            rows = [r for r in rows if active_ingredient.lower() in str(r).lower()]
        if status:
            rows = [r for r in rows if status.lower() in str(r).lower()]
        return rows[:limit]


# ---------------------------------------------------------------------------
# Tool 11: Meat inspection statistics
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY_TOOL)
async def blv_get_meat_inspection_stats(
    year: int | None = None,
    animal_type: str = "",
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Slaughterhouse meat inspection statistics (Fleischuntersuchung).

    Use case: review slaughter counts and condemnation rates by animal type and
    year.

    Args:
        year: Filter by year (e.g. 2023). None = all.
        animal_type: Filter by animal type (e.g. "Rind", "Schwein", "Geflügel"). Empty = all.

    Returns:
        Inspection statistics with year, animal type, slaughter count, condemnation rate.
    """
    slug = await _find_dataset(ctx, "fleischuntersuchung schlachttier kontrolle")
    if slug is None:
        return [
            _error(
                "No meat inspection dataset found",
                ERR_NO_DATASET,
                note="Browse available datasets with blv_list_datasets().",
            )
        ]

    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _ckan_resource_url(info, "CSV") or _ckan_resource_url(info, "JSON")
    if not csv_url:
        return [_error("No CSV/JSON resource found", ERR_NO_RESOURCE, dataset=slug)]

    await _step(ctx, 2, 2, "Downloading meat inspection data")
    rows = await _fetch_csv(csv_url)

    if year:
        rows = [r for r in rows if str(year) in str(r)]
    if animal_type:
        rows = [r for r in rows if animal_type.lower() in str(r).lower()]
    return rows[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("blv://datasets/overview")
async def resource_datasets_overview() -> str:
    """Overview of all 28 BLV datasets on opendata.swiss."""
    datasets = await blv_list_datasets(limit=28)
    lines = [f"# BLV Open Datasets ({len(datasets)} total)\n"]
    for ds in datasets:
        lines.append(f"## {ds['title']}")
        lines.append(f"- Name: `{ds['name']}`")
        lines.append(f"- Resources: {ds['num_resources']}")
        lines.append(f"- URL: {ds['url']}\n")
    return "\n".join(lines)


@mcp.resource("blv://warnings/current")
async def resource_current_warnings() -> str:
    """Current BLV public warnings and food recalls."""
    warnings = await blv_get_public_warnings(limit=10)
    lines = ["# Current BLV Public Warnings & Recalls\n"]
    for w in warnings:
        lines.append(f"## {w['title']}")
        lines.append(f"Date: {w['pubDate']}")
        lines.append(f"Link: {w['link']}")
        lines.append(f"{w['description']}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def prompt_food_safety_analysis(topic: str = "Lebensmittelrückrufe") -> str:
    """Generate a food safety analysis prompt for a given topic."""
    return (
        f"Analysiere die aktuelle Situation bezüglich '{topic}' in der Schweiz. "
        f"Nutze die verfügbaren BLV-Daten: Öffentliche Warnungen (blv_get_public_warnings), "
        f"Lebensmittelkontrollen (blv_get_food_control_results) und weitere relevante Werkzeuge. "
        f"Fasse die wichtigsten Erkenntnisse zusammen und identifiziere Trends."
    )


@mcp.prompt()
def prompt_animal_disease_report(canton: str = "ZH", year: int = 2024) -> str:
    """Generate an animal disease situation report for a canton."""
    return (
        f"Erstelle einen Tiergesundheitsbericht für den Kanton {canton} im Jahr {year}. "
        f"Verwende blv_search_animal_diseases(canton='{canton}', year_from={year}, year_to={year}) "
        f"und blv_get_avian_influenza(year={year}, canton='{canton}'). "
        f"Fasse die Lage zusammen und vergleiche mit dem Vorjahr falls Daten vorhanden."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point — supports stdio (default) and --http (Streamable HTTP)."""
    parser = argparse.ArgumentParser(description="swiss-food-safety-mcp: BLV open data MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run as Streamable HTTP server on port 8002 (for cloud/Render.com)",
    )
    parser.add_argument(
        "--port", type=int, default=settings.http_port, help="HTTP port (default: 8002)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.http_host,
        help=(
            "HTTP bind address (default: 127.0.0.1, loopback only). "
            "Set explicitly to 0.0.0.0 only when external exposure is intended "
            "(e.g. behind the Render.com TLS proxy)."
        ),
    )
    args = parser.parse_args()

    if args.http:
        # CORS: browser MCP clients need Mcp-Session-Id exposed. Origins are
        # explicit (no wildcard) via the BLV_MCP_ALLOWED_ORIGINS env var.
        allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
        cors = Middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["Mcp-Session-Id"],
        )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            middleware=[cors],
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
