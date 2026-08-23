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
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
import httpx
from fastmcp import Context, FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from typing_extensions import TypedDict

from . import __version__

# Der Umbau auf importlib.metadata endete seinerzeit in __init__.py; hier stand
# weiterhin ein eigenes Literal. Es speist den User-Agent, die Ready-Zeile im
# Log und das version=-Feld des MCP-Servers — also genau die Stellen, die nach
# aussen sichtbar sind. Das veroeffentlichte 1.1.4 meldete deshalb immer noch
# 1.1.0, obwohl der Fix als erledigt galt.
#
# Der zweite Name fuer dieselbe Sache ist der Grund, warum es niemand sah:
# weder der Versions-Sync-Check noch die Identity-Probe erkennen
# SERVER_VERSION, beide suchen __version__ oder ein "name/version"-Literal.
# Deshalb kein neues Literal, sondern der eine Wert aus den Paket-Metadaten.
SERVER_VERSION = __version__

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
    # `/sparql` ist die Editor-Oberflaeche, nicht der Abfrage-Endpunkt.
    # Gemessen am 2026-08-08: GET liefert dort HTTP 200 mit `text/html`, POST
    # HTTP 404. Der Endpunkt ist `/query` — er antwortet auf GET **und** POST
    # mit `application/sparql-results+json`.
    #
    # Kontrolle: Ein frei erfundener Pfad unter lindas.admin.ch antwortet mit
    # 404. Ohne sie belegte die Messung nur, dass ICH einen 404 bekomme.
    #
    # Folge des Fehlers: Jede SPARQL-Abfrage schlug fehl und fiel auf den
    # CSV-Pfad zurueck — der seinerseits nie funktionierte (siehe
    # `_fetch_csv`). `blv_search_animal_diseases` hat damit nie Daten
    # geliefert.
    sparql_endpoint: str = "https://lindas.admin.ch/query"
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


def _mehrsprachig(wert: Any) -> str:
    """CKAN liefert `name`, `title` und `format` teils als Sprach-Dictionary."""
    if isinstance(wert, dict):
        for schluessel in ("de", "en", "fr", "it"):
            if wert.get(schluessel):
                return str(wert[schluessel])
        return str(next(iter(wert.values()), "") or "")
    return str(wert or "")


def _ckan_resource_url(package: dict, fmt: str) -> str | None:
    """Return first resource URL matching format (case-insensitive).

    NUR NOCH FUER `blv_get_dataset_info` GEDACHT — nicht mehr fuer die
    Datenwerkzeuge. Warum, steht bei :data:`DATENQUELLEN`: «die erste
    Ressource dieses Formats» ist keine Auswahlregel, sondern eine Wette
    darauf, wie die Quelle ihre Liste sortiert.
    """
    for r in package.get("resources", []):
        if _mehrsprachig(r.get("format")).upper() == fmt.upper():
            return _mehrsprachig(r.get("url")) or None
    return None


@dataclass(frozen=True)
class Datenquelle:
    """Ein gepinnter Datensatz samt der Ressource, die die Daten traegt."""

    slug: str
    ressource: str
    format: str = "CSV"
    warum: str = ""


# Welcher Datensatz und welche Ressource zu welchem Werkzeug gehoert.
#
# WARUM DAS GEPINNT IST UND NICHT GESUCHT WIRD. Vorher stand hier ein
# Stichwortsuchlauf, und genommen wurde der **erste** Treffer; die Ressource
# war die **erste** des passenden Formats. Beides ist keine Auswahlregel,
# sondern eine Wette darauf, wie opendata.swiss sortiert. Am 2026-08-08
# gemessen, was diese Wette ergab:
#
# * «tiergesundheit statistik» traf `antibiotikaeinsatz-in-der-veterinarmedizin`
#   statt `tiergesundheitsstatistik` (Platz 3). `blv_get_animal_health_stats`
#   und `blv_get_antibiotic_usage_vet` lieferten deshalb **dieselbe Datei** —
#   zwei Werkzeuge, eine Antwort, und fuer das erste die falsche.
#
# * `lebensmittelkontrolle` fuehrt 26 Ressourcen, davon **18 Code-Listen**.
#   Die erste CSV ist «Food establishments codelist administrative measures».
#   Das Werkzeug versprach «inspection results with canton, year, inspections,
#   violations» und lieferte eine Legende von Verwaltungsmassnahmen-Codes.
#
# * Bei der Vogelgrippe wurde JSON vor CSV bevorzugt, und die JSON-Ressource
#   ist das Frictionless-`datapackage.json` — die **Beschreibung** der Daten,
#   ausgegeben als waeren es die Daten.
#
# Ein Stichwortsuchlauf hat noch eine zweite Eigenschaft, die ihn hier
# untauglich macht: Er faellt still auf etwas Plausibles zurueck. Ein
# gepinnter Slug, den es nicht mehr gibt, faellt auf.
DATENQUELLEN: dict[str, Datenquelle] = {
    "animal_health_stats": Datenquelle(
        slug="tiergesundheitsstatistik",
        ressource="Tiergesundheitsstatistik",
        warum="Die Stichwortsuche traf den Antibiotika-Datensatz.",
    ),
    "food_control_results": Datenquelle(
        slug="lebensmittelkontrolle",
        ressource="Food establishments",
        warum=(
            "18 der 26 Ressourcen sind Code-Listen; die erste CSV ist eine "
            "davon. Genommen wird die neueste Jahresdatei der Betriebskontrollen."
        ),
    ),
    "antibiotic_usage_vet": Datenquelle(
        slug="antibiotikaeinsatz-in-der-veterinarmedizin",
        ressource="ISABV-Amount-Active-Substance",
        warum="Die Wirkstoffmenge ist die Groesse, die der Docstring nennt.",
    ),
    "avian_influenza": Datenquelle(
        slug="uberwachung-von-wildvogeln-auf-aviare-influenza-ai",
        ressource="Wildvögel",
        warum="Die JSON-Ressource ist das datapackage.json, nicht die Daten.",
    ),
    "nutrition_children": Datenquelle(
        slug="menuch-kids-fragebogen",
        ressource="MenuCH-Kids_Questionnaire_aggregated",
        warum="Der einzige menuCH-Kids-Datensatz; er fuehrt Fragebogenauszaehlungen.",
    ),
    "meat_inspection": Datenquelle(
        slug="fleischkontrollstatistik",
        ressource="Fleischkontrollstatistik",
        warum="Die Stichwortsuche traf eine Code-Liste.",
    ),
}


def _daten_ressource(package: dict, quelle: Datenquelle) -> str:
    """Die URL der Ressource, die die Daten traegt — oder ein Fehler.

    Passen mehrere (etwa Jahresdateien), gewinnt die zuletzt einsortierte:
    Das ist bei opendata.swiss die neueste. Passt keine, ist das ein Befund
    ueber den Datensatz und keine leere Antwort.
    """
    treffer = [
        r
        for r in package.get("resources", [])
        if _mehrsprachig(r.get("format")).upper() == quelle.format.upper()
        and quelle.ressource.lower() in _mehrsprachig(r.get("name")).lower()
    ]
    if not treffer:
        vorhanden = [
            f"[{_mehrsprachig(r.get('format'))}] {_mehrsprachig(r.get('name'))}"
            for r in package.get("resources", [])
        ]
        raise UpstreamShapeError(
            f"Im Datensatz '{quelle.slug}' gibt es keine {quelle.format}-Ressource, "
            f"deren Name «{quelle.ressource}» enthaelt. Vorhanden: {vorhanden}. "
            "Das ist eine Aussage ueber den Datensatz — nicht ueber die Daten."
        )
    return _mehrsprachig(treffer[-1].get("url"))


class UpstreamShapeError(RuntimeError):
    """Die Quelle hat geantwortet, aber nicht mit dem, womit sie antwortet.

    Bewusst getrennt von einem Transportfehler: Warten hilft beim einen und
    nie beim anderen.
    """


# Die ersten Bytes einer ZIP-Datei. opendata.swiss deklariert mindestens eine
# Ressource als `format: CSV`, die in Wahrheit ein ZIP ist
# (`animal_disease_report.zip`). `csv.DictReader` liest das als Text und
# scheitert mit «new-line character seen in unquoted field» — eine Meldung,
# aus der niemand auf ein ZIP schliesst.
_ZIP_MAGIC = b"PK\x03\x04"


async def _fetch_csv(url: str) -> list[dict]:
    """Download a CSV and return as list of dicts.

    DREI DINGE, DIE HIER VORHER FEHLTEN — alle am 2026-08-08 gemessen:

    1. **Der BOM.** Gelesen wurde ``r.text``; die BLV-Dateien beginnen mit
       einem UTF-8-BOM, und der landet im Namen der ersten Spalte. Aus `Year`
       wurde `\\ufeffYear`. Jeder Filter auf `Year` oder `Jahr` lief damit ins
       Leere — und zwar still: Er fand nichts und meldete «keine Treffer».

    2. **Das Trennzeichen.** Mindestens eine BLV-Datei ist
       semikolongetrennt. `csv.DictReader` nimmt ohne Angabe das Komma, und
       dann steht die ganze Zeile unter einem einzigen Schluessel:
       ``{'\\ufeffID;DE;FR;IT;EN': 'cp1;Kontaminanten;…'}``. Formal ein
       gueltiges Ergebnis, inhaltlich unbrauchbar.

    3. **Die ZIP-Datei mit `format: CSV`.** Sie erzeugte eine
       csv-Fehlermeldung ueber Zeilenumbrueche, aus der niemand auf ein
       Archiv schliesst.
    """
    r = await _get(url)
    r.raise_for_status()

    if r.content.startswith(_ZIP_MAGIC):
        raise UpstreamShapeError(
            f"Die Ressource {url} ist als CSV deklariert, beginnt aber mit der "
            "ZIP-Signatur. Sie laesst sich nicht als CSV lesen — das ist eine "
            "Aussage ueber die Deklaration bei opendata.swiss, nicht ueber die "
            "Daten."
        )

    # `utf-8-sig` entfernt den BOM, falls einer da ist, und verhaelt sich
    # sonst wie `utf-8`.
    text = r.content.decode("utf-8-sig", errors="replace")
    kopf = text[: text.find("\n") if "\n" in text else len(text)]
    trenner = ";" if kopf.count(";") > kopf.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=trenner)
    zeilen = list(reader)

    if zeilen and len(zeilen[0]) == 1 and any(z in next(iter(zeilen[0])) for z in ";\t|"):
        raise UpstreamShapeError(
            f"Die Ressource {url} hat nach dem Zerlegen genau eine Spalte, und "
            f"deren Name enthaelt ein Trennzeichen: {next(iter(zeilen[0]))!r}. "
            "Das Trennzeichen wurde falsch erkannt — die Zeilen waeren formal "
            "gueltig und inhaltlich unbrauchbar."
        )
    return zeilen


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

    # DIE ABFRAGE KOMMT AUS DEM DATENSATZ SELBST, NICHT AUS EINER ANNAHME.
    #
    # Hier stand eine Abfrage auf die Klasse
    # `agriculture.ld.admin.ch/foag/ontology/AnimalDisease`. Die gibt es in
    # LINDAS nicht: Sie hat **null** Instanzen — genau so viele wie eine frei
    # erfundene Klasse, die als Kontrolle mitgemessen wurde. Der Namensraum
    # heisst `fsvo`, nicht `foag`, und die Daten liegen als Cube vor, nicht als
    # Instanzen eines Typs; auch jedes einzelne Praedikat war ein anderes.
    #
    # Zusammen mit dem falschen Endpunkt (siehe `Settings.sparql_endpoint`)
    # heisst das: Dieses Werkzeug hat nie Daten geliefert. Der Fehler fiel in
    # ein `except Exception` und von dort auf den CSV-Pfad, der seinerseits an
    # einer als CSV deklarierten ZIP-Datei scheiterte.
    #
    # Die Abfrage unten ist die, die der Datensatz
    # `meldepflichtige-tierseuchen-in-der-schweiz` bei opendata.swiss selbst
    # als SPARQL-Ressource mitliefert — dieselbe Quelle, aus der auch der
    # Endpunkt `/query` stammt.
    filter_kanton = f"FILTER(CONTAINS(STR(?canton), '{canton_esc}'))" if canton else ""
    filter_seuche = (
        f"FILTER(CONTAINS(LCASE(STR(?diseases)), LCASE('{disease_esc}')))" if disease else ""
    )
    sparql_query = f"""
    PREFIX schema: <http://schema.org/>
    PREFIX cube: <https://cube.link/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX disease: <https://agriculture.ld.admin.ch/fsvo/animal-disease/>

    SELECT ?date ?canton ?town ?diseasesGroup ?diseases ?species
           (COUNT(DISTINCT ?obs) AS ?count)
    WHERE {{
      <https://agriculture.ld.admin.ch/fsvo/animal-disease/observation/>
        cube:observation ?obs .
      ?obs disease:epidemics/schema:name ?diseases ;
           disease:animal-specie/schema:name ?species ;
           schema:containedInPlace/schema:name ?town ;
           disease:internet-publication ?date ;
           disease:canton/schema:alternateName ?canton .
      ?diseasesIRI schema:name ?diseases ;
                   skos:broader/schema:name ?diseasesGroup .
      FILTER (LANG(?species) = "de")
      FILTER (LANG(?diseases) = "de")
      FILTER (LANG(?diseasesGroup) = "de")
      FILTER (YEAR(?date) >= {year_from} && YEAR(?date) <= {year_to})
      {filter_kanton}
      {filter_seuche}
    }}
    GROUP BY ?date ?canton ?town ?diseasesGroup ?diseases ?species
    ORDER BY DESC(?date)
    LIMIT {limit}
    """

    await _step(ctx, 1, 2, "Querying the LINDAS SPARQL endpoint")
    r = await _get(
        SPARQL_ENDPOINT,
        params={"query": sparql_query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
    )
    r.raise_for_status()
    nutzlast = r.json()
    if "results" not in nutzlast or "bindings" not in nutzlast.get("results", {}):
        # Kein stilles `[]`: Eine andere Antwortform ist keine leere
        # Treffermenge, und die Verwechslung war hier bereits einmal der Fehler.
        raise UpstreamShapeError(
            f"Die SPARQL-Antwort fuehrt kein `results.bindings`. Vorhanden: "
            f"{sorted(nutzlast) if isinstance(nutzlast, dict) else type(nutzlast).__name__}."
        )
    bindings = nutzlast["results"]["bindings"]
    await _step(ctx, 2, 2, f"{len(bindings)} Meldungen erhalten")
    return [
        {
            "date": b.get("date", {}).get("value", ""),
            "canton": b.get("canton", {}).get("value", ""),
            "town": b.get("town", {}).get("value", ""),
            "diseases_group": b.get("diseasesGroup", {}).get("value", ""),
            "disease": b.get("diseases", {}).get("value", ""),
            "species": b.get("species", {}).get("value", ""),
            "cases": b.get("count", {}).get("value", ""),
            "source": DATA_SOURCE,
        }
        for b in bindings
    ]


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
    quelle = DATENQUELLEN["animal_health_stats"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _daten_ressource(info, quelle)
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
    quelle = DATENQUELLEN["food_control_results"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _daten_ressource(info, quelle)
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
    quelle = DATENQUELLEN["antibiotic_usage_vet"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _daten_ressource(info, quelle)
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
    quelle = DATENQUELLEN["avian_influenza"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    data_url = _daten_ressource(info, quelle)
    await _step(ctx, 2, 2, "Downloading avian influenza data")
    # Der JSON-Zweig ist bewusst weg. Vorher wurde JSON vor CSV bevorzugt —
    # und die einzige JSON-Ressource dieses Datensatzes ist das Frictionless
    # `datapackage.json`, also die Feldbeschreibung. Ausgegeben wurde damit die
    # Beschreibung der Daten, als waeren es die Daten:
    # `{"profile": "tabular-data-package", "resources": [...]}`. Das sieht wie
    # eine Antwort aus und enthaelt keinen einzigen Fall.
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
    answer_code: str = "",
    ctx: Context | None = None,
) -> list[dict[str, Any]]:
    """
    Swiss national children's nutrition survey — questionnaire tallies (menuCH-Kids).

    Use case: how often each answer was given, broken down by sex, language
    region and age group.

    NOT nutrient intake. The docstring here promised "nutrient intake by age
    group against dietary recommendations" and named "Energie", "Zucker",
    "Eisen" as filter examples. The only menuCH-Kids dataset published on
    opendata.swiss is the questionnaire, and it carries answer counts:
    ``Geschlecht, Sprachregion, Altersgruppe, Frage, Antwort, Anzahl``.
    Measured on 2026-08-08. A filter on "Eisen" therefore matched nothing and
    returned an empty list — indistinguishable from "no such data for this age
    group".

    Nutrient intake for adults exists as a separate dataset
    (``menuch_lebensmittelkonsum``); this tool does not cover it, and inventing
    a mapping would be worse than the missing feature.

    Args:
        age_group: Filter by age group as the source spells it (e.g. "10bis13").
        answer_code: Filter by question or answer code (e.g. "c09B_12", "a78").

    Returns:
        Questionnaire records: sex, language region, age group, question code,
        answer code, count.
    """
    quelle = DATENQUELLEN["nutrition_children"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _daten_ressource(info, quelle)
    await _step(ctx, 2, 2, "Downloading nutrition survey data")
    rows = await _fetch_csv(csv_url)

    if age_group:
        rows = [r for r in rows if age_group in str(r)]
    if answer_code:
        rows = [r for r in rows if answer_code.lower() in str(r).lower()]
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
    quelle = DATENQUELLEN["meat_inspection"]
    slug = quelle.slug
    await _step(ctx, 1, 2, f"Loading dataset metadata for '{slug}'")
    info = await blv_get_dataset_info(slug)
    csv_url = _daten_ressource(info, quelle)
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


# `allow_headers` stood at `["*"]`. Starlette switches to `allow_all_headers`
# on a wildcard and mirrors back whatever a browser announces, so every listed
# origin could send any header at all — that is not an allow-list, it is the
# absence of one. It also hides every drift, because a wildcard cannot become
# wrong: drop a header the protocol needs and nothing turns red.
#
# `Last-Event-ID` is how a client resumes a dropped SSE stream
# (`LAST_EVENT_ID_HEADER` in `mcp.server.streamable_http`). Omitting it breaks
# only reconnection after packet loss — the worst way to find a bug.
#
# The `Mcp-Method` / `Mcp-Name` / `Mcp-Protocol-Version` routing headers of spec
# 2026-07-28 are deliberately **absent**: fastmcp 3.x pins `mcp` 1.x, where
# `mcp.shared.inbound` does not exist and nothing reads them. Listing headers
# this server never reads would be the same guesswork the wildcard was.
# `test_die_routing_header_gehoeren_hierher_sobald_das_sdk_sie_liest` fails the
# day that changes.
CORS_ALLOW_HEADERS = [
    "Content-Type",
    "Mcp-Session-Id",
    "Last-Event-ID",
]


def configured_origins() -> list[str]:
    """Parse `BLV_MCP_ALLOWED_ORIGINS` into a list. No wildcard."""
    return [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]


def build_cors_middleware(origins: list[str] | None = None) -> Middleware:
    """The CORS layer, as one object both `main` and the tests use.

    Pulled out of `main` so the allow-list can be exercised: while it sat inline
    next to `mcp.run`, the list could only be read, never tried — and a list
    that reads correctly can still never reach the middleware.
    """
    return Middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else configured_origins(),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=CORS_ALLOW_HEADERS,
        expose_headers=["Mcp-Session-Id"],
    )


def build_http_app(origins: list[str] | None = None):
    """The streamable-HTTP app with the CORS layer above, without binding a port.

    `main` hands the same middleware object to `mcp.run`, which builds an
    equivalent app internally; this function is how a test reaches it.
    """
    return mcp.http_app(transport="http", middleware=[build_cors_middleware(origins)])


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
        cors = build_cors_middleware()
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
