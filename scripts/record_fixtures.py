#!/usr/bin/env python3
"""Zeichnet auf, welchen Datensatz und welche Ressource jedes Werkzeug trifft.

    python scripts/record_fixtures.py

WARUM ES DAS GIBT. Ein handgeschriebener Mock kodiert die Annahme seines
Autors und kann sie deshalb prinzipiell nicht widerlegen: Produktivcode und
Fixture stammen aus demselben Kopf, derselben Stunde, derselben Lektuere der
Doku. Wo beide irren, irren beide gleich, und die Suite bleibt dauerhaft
gruen.

Dieses Repo hatte den Fall in Reinform. Die Mocks nannten jede Ressource
schlicht ``"name": "CSV"``. Bei opendata.swiss heisst sie «Food establishments
2025» oder «Food establishments codelist administrative measures» — und genau
dieser Unterschied entschied, ob ein Werkzeug Inspektionsergebnisse oder eine
Code-Legende ausgab.

WAS DER ERSTE VERGLEICH AM 2026-08-08 ERGAB.

1. **Der SPARQL-Endpunkt war die Editor-Oberflaeche.** `/sparql` antwortet auf
   GET mit HTTP 200 und `text/html`, auf POST mit 404. Der Endpunkt ist
   `/query`. Der Datensatz bei opendata.swiss sagt das selbst: In seiner
   SPARQL-Ressource steht `endpoint=https://lindas.admin.ch/query`.

2. **Die SPARQL-Abfrage traf eine Klasse, die es nicht gibt.**
   `agriculture.ld.admin.ch/foag/ontology/AnimalDisease` hat null Instanzen —
   genauso viele wie eine frei erfundene Klasse (Kontrolle). Der Namensraum
   heisst `fsvo`, und die Daten liegen als Cube vor.

3. **«Die erste Ressource dieses Formats» ist keine Auswahlregel.**
   `lebensmittelkontrolle` fuehrt 26 Ressourcen, davon 18 Code-Listen; die
   erste CSV ist eine davon.

4. **«Der erste Suchtreffer» ebensowenig.** «tiergesundheit statistik» traf
   den Antibiotika-Datensatz, nicht `tiergesundheitsstatistik` (Platz 3).

AUFGEZEICHNET WIRD DESHALB DIE AUSWAHL SELBST: je Werkzeug der gepinnte Slug,
die getroffene Ressource und die Kopfzeile der Datei. Ein Datensatz, der
umbenannt wird, faellt damit auf — statt still auf etwas Plausibles
zurueckzufallen.

Ohne Aufzeichnungsdatum ist «gemessen» nach zwei Jahren von «angenommen» nicht
mehr zu unterscheiden. Es steht je Eintrag in `tests/fixtures/PROVENANCE.md`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))

# Alles kommt aus dem Produktivcode. Ein Aufzeichnungsskript, das eine andere
# Adresse fragt als der Server, misst den falschen Gegenstand — und das faellt
# niemandem auf, weil das Ergebnis plausibel aussieht.
from swiss_food_safety_mcp import server as S  # noqa: E402

INFO = getattr(S.blv_get_dataset_info, "fn", S.blv_get_dataset_info)

KONTROLL_KLASSE = "<https://agriculture.ld.admin.ch/fsvo/animal-disease/DieseKlasseGibtEsNicht>"
ECHTE_KLASSE = "<https://agriculture.ld.admin.ch/fsvo/animal-disease/observation/>"


async def record() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict] = []

    def write(name: str, payload: object, url: str, rule: str) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        (FIXTURES / name).write_text(text, encoding="utf-8")
        entries.append(
            {
                "name": name,
                "url": url,
                "rule": rule,
                "bytes": len(text.encode("utf-8")),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        print(f"ok  {name:<28} {len(text.encode('utf-8')):>7} B")

    async with httpx.AsyncClient(
        timeout=90.0,
        follow_redirects=True,
        headers={"User-Agent": f"swiss-food-safety-mcp/{S.SERVER_VERSION}"},
    ) as c:
        S._client = c

        # -- 1) Welche Ressource jedes Werkzeug trifft -----------------------
        auswahl: dict[str, dict] = {}
        for schluessel, quelle in S.DATENQUELLEN.items():
            info = await INFO(quelle.slug)
            alle = [
                {
                    "format": S._mehrsprachig(r.get("format")),
                    "name": S._mehrsprachig(r.get("name")),
                }
                for r in info.get("resources", [])
            ]
            url = S._daten_ressource(info, quelle)
            r = await c.get(url)
            r.raise_for_status()
            kopf = r.content.decode("utf-8-sig", errors="replace").splitlines()[:1]
            auswahl[schluessel] = {
                "slug": quelle.slug,
                "ressource_muster": quelle.ressource,
                "warum": quelle.warum,
                "getroffene_url": url,
                "kopfzeile": kopf[0][:300] if kopf else "",
                "ressourcen_im_datensatz": len(alle),
                "code_listen_darunter": sum(1 for a in alle if "codelist" in a["name"].lower()),
            }
            print(f"    {schluessel:<22} {quelle.slug}")

        # Die Kopfzeile ist der Gegenstand: Sie unterscheidet Daten von einer
        # Code-Liste, und sie zeigt, ob BOM und Trennzeichen stimmen.
        for schluessel, a in auswahl.items():
            if not a["kopfzeile"]:
                raise SystemExit(
                    f"{schluessel}: leere Kopfzeile — die Ressource traegt keine Daten."
                )
            if a["kopfzeile"].startswith("﻿"):
                raise SystemExit(
                    f"{schluessel}: die Kopfzeile beginnt mit einem BOM. `_fetch_csv` "
                    "soll ihn entfernen — wenn er hier ankommt, tut es das nicht."
                )
        write(
            "datenauswahl.json",
            {"recorded_at": recorded_at, "auswahl": auswahl},
            f"{S.CKAN_BASE}/package_show",
            "je Werkzeug der gepinnte Datensatz, die getroffene Ressource und "
            "deren Kopfzeile. Die Kopfzeile ist der Gegenstand: Sie trennt "
            "Daten von einer Code-Liste. Vorher wurde «die erste CSV» genommen "
            "— bei 26 Ressourcen, davon 18 Code-Listen, war das eine Wette auf "
            "die Sortierung der Quelle",
        )

        # -- 2) Der SPARQL-Endpunkt, mit Kontrolle --------------------------
        endpunkte: dict[str, dict] = {}
        proben = [
            ("gebaut_frueher", "https://lindas.admin.ch/sparql"),
            ("gebaut_jetzt", S.SPARQL_ENDPOINT),
            ("kontrolle_erfunden", "https://lindas.admin.ch/diesen-pfad-gibt-es-nicht"),
        ]
        for label, url in proben:
            r = await c.post(
                url,
                data={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"},
                headers={"Accept": "application/sparql-results+json"},
            )
            endpunkte[label] = {
                "url": url,
                "post_status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
            }
            print(f"    POST {r.status_code}  {label:<22} {url}")

        if endpunkte["gebaut_jetzt"]["post_status"] != 200:
            raise SystemExit(
                f"Der Abfrage-Endpunkt antwortet mit "
                f"{endpunkte['gebaut_jetzt']['post_status']} statt 200. Neu messen."
            )
        if endpunkte["kontrolle_erfunden"]["post_status"] != 404:
            raise SystemExit(
                "Ein erfundener Pfad antwortet nicht mehr mit 404 — ohne diese "
                "Kontrolle belegt die Messung nichts."
            )
        if endpunkte["gebaut_frueher"]["post_status"] == 200:
            raise SystemExit(
                "`/sparql` beantwortet jetzt auch POST — dann ist der Befund "
                "ueberholt und gehoert neu geschrieben, nicht weitergetragen."
            )

        # -- 3) Die Klasse, die es nicht gab — mit Kontrolle ----------------
        async def anzahl(muster: str) -> int:
            r = await c.post(
                S.SPARQL_ENDPOINT,
                data={"query": f"SELECT (COUNT(*) AS ?n) WHERE {{ {muster} }}"},
                headers={"Accept": "application/sparql-results+json"},
            )
            r.raise_for_status()
            return int(r.json()["results"]["bindings"][0]["n"]["value"])

        klassen = {
            "foag_AnimalDisease_frueher": await anzahl(
                "?s a <https://agriculture.ld.admin.ch/foag/ontology/AnimalDisease>"
            ),
            "kontrolle_erfundene_klasse": await anzahl(f"?s a {KONTROLL_KLASSE}"),
            "fsvo_cube_beobachtungen": await anzahl(
                f"{ECHTE_KLASSE} <https://cube.link/observation> ?s"
            ),
        }
        if klassen["kontrolle_erfundene_klasse"] != 0:
            raise SystemExit("Die erfundene Klasse liefert Instanzen — die Kontrolle traegt nicht.")
        if klassen["fsvo_cube_beobachtungen"] == 0:
            raise SystemExit(
                "Der fsvo-Cube fuehrt keine Beobachtungen mehr — dann liefert "
                "`blv_search_animal_diseases` nichts, und das gehoert behoben."
            )
        if klassen["foag_AnimalDisease_frueher"] != 0:
            raise SystemExit(
                "Die frueher abgefragte foag-Klasse hat wieder Instanzen — dann "
                "ist der Befund ueberholt."
            )
        write(
            "lindas_endpunkt.json",
            {"recorded_at": recorded_at, "endpunkte": endpunkte, "klassen": klassen},
            "https://lindas.admin.ch/…",
            "der Abfrage-Endpunkt und die abgefragte Klasse, je mit Kontrolle. "
            "Ohne den erfundenen Pfad hiesse der Befund nur «ich bekomme einen "
            "404»; ohne die erfundene Klasse nur «ich bekomme null Zeilen». "
            "Erst die Paare zeigen, dass `/sparql` kein Abfrage-Endpunkt ist "
            "und die foag-Klasse nicht existiert",
        )

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von `opendata.swiss` und `lindas.admin.ch`.",
        "",
        "Ohne Datum ist «gemessen» nach zwei Jahren von «angenommen» nicht mehr",
        "zu unterscheiden — die Datei sieht gleich aus.",
        "",
        "## Aufgezeichnet ist die Auswahl, nicht der Datensatz",
        "",
        "Die Rohdaten sind zu gross und aendern sich taeglich. Aufgezeichnet ist",
        "deshalb, **welchen Datensatz und welche Ressource jedes Werkzeug",
        "trifft** — und die Kopfzeile der getroffenen Datei. Genau daran hing",
        "der Befund: «die erste CSV» eines Datensatzes mit 26 Ressourcen, davon",
        "18 Code-Listen, ist keine Auswahlregel, sondern eine Wette auf die",
        "Sortierung der Quelle.",
        "",
        "## Ohne die Kontrollen belegt nichts davon etwas",
        "",
        "| Kontrolle | Antwort | Was sie traegt |",
        "|---|---|---|",
        "| erfundener Pfad unter `lindas.admin.ch` | POST 404 | der 404 auf `/sparql` ist echt |",
        "| erfundene Klasse im fsvo-Namensraum | 0 Instanzen | die foag-Klasse gibt es nicht |",
        "",
        "Das Skript bricht ab, wenn eine Kontrolle nicht mehr traegt, wenn eine",
        "gepinnte Ressource verschwindet, wenn eine Kopfzeile leer ist oder mit",
        "einem BOM beginnt, oder wenn einer der Befunde ueberholt ist. Ein",
        "Befund, der still veraltet, ist schlimmer als keiner.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Quelle:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']}",
            f"- **Groesse:** {e['bytes']} B",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(record()))
    except httpx.HTTPError as exc:
        print(f"FEHLER: Quelle nicht erreichbar: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
