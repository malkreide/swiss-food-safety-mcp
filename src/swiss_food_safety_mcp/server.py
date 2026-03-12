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
import csv
import io
import json
import sys
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CKAN_BASE = "https://opendata.swiss/api/3/action"
BLV_ORG_ID = "bundesamt-fur-lebensmittelsicherheit-und-veterinaerwesen-blv"
SPARQL_ENDPOINT = "https://lindas.admin.ch/sparql"
BLV_RSS = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1079"
TIMEOUT = 20.0

# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="swiss-food-safety-mcp",
    instructions=(
        "Tools for Swiss Federal Food Safety and Veterinary Office (BLV) open data. "
        "Covers food recalls, animal disease surveillance, food control results, "
        "antibiotic usage in veterinary medicine, children's nutrition, and the "
        "pesticide register. All data from official Swiss federal sources. No auth needed."
    ),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get(url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
    """Shared async HTTP GET with timeout."""
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        return await client.get(url, params=params, headers=headers or {})


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


# ---------------------------------------------------------------------------
# Tool 1: Public warnings & recalls
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_public_warnings(limit: int = 20) -> list[dict[str, str]]:
    """
    Current BLV food recalls and public health warnings (live RSS feed).

    Args:
        limit: Maximum number of items to return (default 20, max 50).

    Returns:
        List of warning items with title, link, description, pubDate.
    """
    limit = min(limit, 50)
    r = await _get(BLV_RSS)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items = []
    for item in root.findall(".//item")[:limit]:
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
            }
        )
    return items


# ---------------------------------------------------------------------------
# Tool 2: List BLV datasets
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_list_datasets(
    limit: int = 28,
    search: str = "",
) -> list[dict[str, Any]]:
    """
    Browse all BLV open datasets on opendata.swiss (CKAN API).

    Args:
        limit: Maximum datasets to return (default 28 = all BLV datasets).
        search: Optional keyword filter on title/notes.

    Returns:
        List of dataset summaries with name, title, notes, num_resources.
    """
    params: dict[str, Any] = {
        "fq": f"organization:{BLV_ORG_ID}",
        "rows": limit,
        "start": 0,
    }
    if search:
        params["q"] = search

    r = await _get(f"{CKAN_BASE}/package_search", params=params)
    r.raise_for_status()
    data = r.json()
    results = []
    for ds in data.get("result", {}).get("results", []):
        results.append(
            {
                "name": ds.get("name", ""),
                "title": ds.get("title", {}).get("de", ds.get("title", "")),
                "notes": (ds.get("notes", {}).get("de", ds.get("notes", "")) or "")[:200],
                "num_resources": len(ds.get("resources", [])),
                "url": f"https://opendata.swiss/de/dataset/{ds.get('name', '')}",
            }
        )
    return results


# ---------------------------------------------------------------------------
# Tool 3: Dataset info
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_dataset_info(dataset_name: str) -> dict[str, Any]:
    """
    Detailed metadata and resource URLs for a specific BLV dataset.

    Args:
        dataset_name: CKAN dataset name/slug (from blv_list_datasets).

    Returns:
        Full dataset metadata including all resource download URLs and formats.
    """
    r = await _get(f"{CKAN_BASE}/package_show", params={"id": dataset_name})
    r.raise_for_status()
    pkg = r.json().get("result", {})
    resources = [
        {
            "name": res.get("name", ""),
            "format": res.get("format", ""),
            "url": res.get("url", ""),
            "description": res.get("description", ""),
        }
        for res in pkg.get("resources", [])
    ]
    return {
        "name": pkg.get("name", ""),
        "title": pkg.get("title", {}).get("de", ""),
        "notes": pkg.get("notes", {}).get("de", ""),
        "organization": pkg.get("organization", {}).get("name", ""),
        "license": pkg.get("license_title", ""),
        "num_resources": len(resources),
        "resources": resources,
    }


# ---------------------------------------------------------------------------
# Tool 4: Animal disease search (SPARQL + CSV fallback)
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_search_animal_diseases(
    canton: str = "",
    disease: str = "",
    year_from: int = 2020,
    year_to: int = 2024,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Search notifiable animal disease cases in Switzerland since 1991 (InfoSM).

    Args:
        canton: Two-letter canton abbreviation (e.g. "ZH", "BE"). Empty = all cantons.
        disease: Disease name filter (partial match, e.g. "Maul", "Vogelgrippe"). Empty = all.
        year_from: Start year (default 2020).
        year_to: End year (default 2024).
        limit: Maximum results (default 50).

    Returns:
        List of disease case records with year, canton, disease, count.
    """
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
      {"FILTER(CONTAINS(STR(?canton), '" + canton + "'))" if canton else ""}
      {"FILTER(CONTAINS(LCASE(STR(?disease)), LCASE('" + disease + "')))" if disease else ""}
    }}
    ORDER BY DESC(?year) ?canton
    LIMIT {limit}
    """

    try:
        r = await _get(
            SPARQL_ENDPOINT,
            params={"query": sparql_query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        r.raise_for_status()
        bindings = r.json().get("results", {}).get("bindings", [])
        return [
            {
                "year": b.get("year", {}).get("value", ""),
                "canton": b.get("canton", {}).get("value", ""),
                "disease": b.get("disease", {}).get("value", ""),
                "cases": b.get("cases", {}).get("value", ""),
            }
            for b in bindings
        ]
    except Exception:
        # Fallback: try CKAN CSV dataset
        datasets = await blv_list_datasets(search="tierseuchen infosm")
        if not datasets:
            return [{"error": "SPARQL unavailable and no CSV fallback found"}]
        info = await blv_get_dataset_info(datasets[0]["name"])
        csv_url = next((r["url"] for r in info["resources"] if r["format"].upper() == "CSV"), None)
        if not csv_url:
            return [{"error": "No CSV resource found in fallback dataset"}]
        rows = await _fetch_csv(csv_url)
        return rows[:limit]


# ---------------------------------------------------------------------------
# Tool 5: Animal health statistics
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_animal_health_stats(year: int | None = None) -> list[dict[str, Any]]:
    """
    Annual animal health statistics from BLV (opendata.swiss CSV/JSON).

    Args:
        year: Filter by year (e.g. 2023). None returns all available years.

    Returns:
        List of annual statistics records.
    """
    datasets = await blv_list_datasets(search="tiergesundheit statistik")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    csv_url = _ckan_resource_url(info, "CSV") or _ckan_resource_url(info, "JSON")
    if not csv_url:
        return [{"error": "No CSV/JSON resource found", "dataset": datasets[0]["name"]}]

    rows = await _fetch_csv(csv_url)
    if year:
        rows = [r for r in rows if str(year) in str(r.get("Jahr", r.get("year", "")))]
    return rows[:200]


# ---------------------------------------------------------------------------
# Tool 6: Food control results
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_food_control_results(
    canton: str = "",
    year: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Cantonal food inspection results and violation rates (Lebensmittelkontrolle).

    Args:
        canton: Two-letter canton abbreviation (e.g. "ZH"). Empty = all.
        year: Filter by year. None = all available.
        limit: Maximum rows to return (default 100).

    Returns:
        List of inspection result records with canton, year, inspections, violations.
    """
    datasets = await blv_list_datasets(search="lebensmittelkontrolle kantone")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [{"error": "No CSV resource found"}]

    rows = await _fetch_csv(csv_url)

    if canton:
        rows = [r for r in rows if canton.upper() in str(r).upper()]
    if year:
        rows = [r for r in rows if str(year) in str(r)]
    return rows[:limit]


# ---------------------------------------------------------------------------
# Tool 7: Antibiotic usage veterinary (ISABV)
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_antibiotic_usage_vet(
    year: int | None = None,
    animal_species: str = "",
) -> list[dict[str, Any]]:
    """
    Veterinary antibiotic usage data from the Swiss ISABV monitoring system.

    Args:
        year: Filter by year (e.g. 2022). None = all years.
        animal_species: Filter by species (e.g. "Rind", "Schwein", "Geflügel"). Empty = all.

    Returns:
        Antibiotic usage records with year, species, substance class, quantity (kg).
    """
    datasets = await blv_list_datasets(search="antibiotika tierarzneimittel isabv")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [{"error": "No CSV resource found"}]

    rows = await _fetch_csv(csv_url)

    if year:
        rows = [r for r in rows if str(year) in str(r)]
    if animal_species:
        rows = [r for r in rows if animal_species.lower() in str(r).lower()]
    return rows[:200]


# ---------------------------------------------------------------------------
# Tool 8: Avian influenza monitoring
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_avian_influenza(
    year: int | None = None,
    canton: str = "",
) -> list[dict[str, Any]]:
    """
    Wild bird avian influenza (H5N1 / HPAI) surveillance data with geodata.

    Args:
        year: Filter by year (e.g. 2024). None = all.
        canton: Two-letter canton code (e.g. "ZH"). Empty = all Switzerland.

    Returns:
        Avian influenza case records with date, location, species, result, coordinates.
    """
    datasets = await blv_list_datasets(search="vogelgrippe aviäre influenza wildvögel")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    # Prefer JSON, fall back to CSV
    data_url = _ckan_resource_url(info, "JSON") or _ckan_resource_url(info, "CSV")
    if not data_url:
        return [{"error": "No JSON/CSV resource found"}]

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
    return rows[:200]


# ---------------------------------------------------------------------------
# Tool 9: Children's nutrition survey (menuCH-Kids)
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_get_nutrition_data_children(
    age_group: str = "",
    nutrient: str = "",
) -> list[dict[str, Any]]:
    """
    Swiss national children's nutrition survey data (menuCH-Kids).

    Args:
        age_group: Filter by age group (e.g. "6-9", "10-12"). Empty = all.
        nutrient: Filter by nutrient name (e.g. "Energie", "Zucker", "Eisen"). Empty = all.

    Returns:
        Nutrition intake records with age group, nutrient, mean intake, unit, recommendation.
    """
    datasets = await blv_list_datasets(search="menuCH kids Kinder Ernährung")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    csv_url = _ckan_resource_url(info, "CSV")
    if not csv_url:
        return [{"error": "No CSV resource found"}]

    rows = await _fetch_csv(csv_url)

    if age_group:
        rows = [r for r in rows if age_group in str(r)]
    if nutrient:
        rows = [r for r in rows if nutrient.lower() in str(r).lower()]
    return rows[:300]


# ---------------------------------------------------------------------------
# Tool 10: Pesticide register
# ---------------------------------------------------------------------------


@mcp.tool()
async def blv_search_pesticide_products(
    product_name: str = "",
    active_ingredient: str = "",
    status: str = "bewilligt",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Search the Swiss approved pesticide register (Pflanzenschutzmittelverzeichnis).

    Args:
        product_name: Filter by product name (partial match). Empty = all.
        active_ingredient: Filter by active ingredient, e.g. "Kupfer", "Glyphosat". Empty = all.
        status: Authorization status — "bewilligt" (approved), "widerrufen" (revoked), or "".
        limit: Maximum results (default 50).

    Returns:
        Pesticide product records with name, authorization number, active ingredients, status.
    """
    datasets = await blv_list_datasets(search="pflanzenschutzmittel pestizid register")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    xml_url = _ckan_resource_url(info, "XML") or _ckan_resource_url(info, "CSV")
    if not xml_url:
        return [{"error": "No XML/CSV resource found"}]

    if xml_url.endswith(".xml") or "xml" in xml_url.lower():
        r = await _get(xml_url)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        results = []
        for product in root.iter("product"):
            name = product.findtext("name", "")
            auth_nr = product.findtext("authorisation_number", "")
            ingredients = [ai.text for ai in product.findall(".//active_ingredient") if ai.text]
            prod_status = product.findtext("status", "")

            # Filters
            if product_name and product_name.lower() not in name.lower():
                continue
            if active_ingredient and not any(active_ingredient.lower() in ai.lower() for ai in ingredients):
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


@mcp.tool()
async def blv_get_meat_inspection_stats(
    year: int | None = None,
    animal_type: str = "",
) -> list[dict[str, Any]]:
    """
    Slaughterhouse meat inspection statistics (Fleischuntersuchung).

    Args:
        year: Filter by year (e.g. 2023). None = all.
        animal_type: Filter by animal type (e.g. "Rind", "Schwein", "Geflügel"). Empty = all.

    Returns:
        Inspection statistics with year, animal type, slaughter count, condemnation rate.
    """
    datasets = await blv_list_datasets(search="fleischuntersuchung schlachttier kontrolle")
    if not datasets:
        return [{"error": "No matching dataset found"}]

    info = await blv_get_dataset_info(datasets[0]["name"])
    csv_url = _ckan_resource_url(info, "CSV") or _ckan_resource_url(info, "JSON")
    if not csv_url:
        return [{"error": "No CSV/JSON resource found"}]

    rows = await _fetch_csv(csv_url)

    if year:
        rows = [r for r in rows if str(year) in str(r)]
    if animal_type:
        rows = [r for r in rows if animal_type.lower() in str(r).lower()]
    return rows[:200]


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
    parser = argparse.ArgumentParser(
        description="swiss-food-safety-mcp: BLV open data MCP server"
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run as Streamable HTTP server on port 8002 (for cloud/Render.com)",
    )
    parser.add_argument("--port", type=int, default=8002, help="HTTP port (default: 8002)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP host (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
