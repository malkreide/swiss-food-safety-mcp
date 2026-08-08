"""Welchen Datensatz und welche Ressource jedes Werkzeug trifft.

Ohne Netz. Grundlage ist `tests/fixtures/`, aufgezeichnet am 2026-08-08 von
`scripts/record_fixtures.py`.

Diese Datei laeuft **in** der CI. Das ist der Punkt: Dieses Repo hatte einen
einzigen Live-Test fuer acht Werkzeuge, und der pruefte keines davon. Was
dauerhaft gelten soll, gehoert nicht hinter `-m live`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from swiss_food_safety_mcp.server import (
    DATENQUELLEN,
    SPARQL_ENDPOINT,
    UpstreamShapeError,
    _daten_ressource,
    _mehrsprachig,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture(name: str) -> dict:
    pfad = FIXTURES / name
    if not pfad.is_file():
        raise FileNotFoundError(
            f"Keine Fixture unter {pfad}. Neu aufzeichnen mit `python scripts/record_fixtures.py`."
        )
    return copy.deepcopy(json.loads(pfad.read_text(encoding="utf-8")))


def _auswahl() -> dict:
    return _fixture("datenauswahl.json")["auswahl"]


class TestJedesWerkzeugTrifftDaten:
    """Die Kopfzeile ist der Gegenstand — sie trennt Daten von einer Legende."""

    def test_jede_gepinnte_quelle_ist_aufgezeichnet(self):
        assert set(_auswahl()) == set(DATENQUELLEN), (
            "Eine gepinnte Quelle ohne Aufzeichnung ist unbelegt, eine "
            "Aufzeichnung ohne Quelle misst etwas, das niemand aufruft."
        )

    def test_keine_kopfzeile_ist_leer(self):
        for name, a in _auswahl().items():
            assert a["kopfzeile"], name

    def test_keine_kopfzeile_traegt_einen_bom(self):
        """`\\ufeffYear` statt `Year` — der Fehler, der jeden Jahresfilter still
        leerlaufen liess."""
        for name, a in _auswahl().items():
            assert not a["kopfzeile"].startswith("﻿"), name

    def test_keine_kopfzeile_ist_eine_einzelne_spalte_mit_semikolon(self):
        """Der Fleischkontroll-Fall: semikolongetrennt, als Komma gelesen.

        Herausgekommen war ``{'\\ufeffID;DE;FR;IT;EN': 'cp1;Kontaminanten;…'}``
        — formal ein gueltiges Ergebnis, inhaltlich unbrauchbar.
        """
        for name, a in _auswahl().items():
            kopf = a["kopfzeile"]
            assert not (kopf.count(",") == 0 and ";" in kopf), f"{name}: {kopf[:80]}"

    def test_die_kontrollergebnisse_sind_keine_code_listen_mehr(self):
        """Der Befund in einer Zusicherung.

        `blv_get_food_control_results` gab «Code, NAME DE, NAME FR, NAME IT,
        NAME EN» aus — die Legende der Verwaltungsmassnahmen. Versprochen
        waren Inspektionsergebnisse nach Kanton und Jahr.
        """
        kopf = _auswahl()["food_control_results"]["kopfzeile"]
        assert "Kanton" in kopf
        assert "Inspektion" in kopf or "InspektionsID" in kopf
        assert not kopf.startswith("Code,NAME")

    def test_die_vogelgrippe_liefert_faelle_und_keine_feldbeschreibung(self):
        """Vorher kam das Frictionless-`datapackage.json` zurueck.

        `{"profile": "tabular-data-package", "resources": [...]}` — die
        Beschreibung der Daten, ausgegeben als waeren es die Daten.
        """
        kopf = _auswahl()["avian_influenza"]["kopfzeile"]
        assert "Kanton" in kopf and "Vogelart" in kopf
        assert "tabular-data-package" not in kopf

    def test_tiergesundheit_und_antibiotika_sind_verschiedene_daten(self):
        """Beide Werkzeuge lieferten dieselbe Datei.

        «tiergesundheit statistik» traf per Stichwortsuche den
        Antibiotika-Datensatz; `tiergesundheitsstatistik` stand auf Platz 3.
        """
        a = _auswahl()
        assert a["animal_health_stats"]["slug"] != a["antibiotic_usage_vet"]["slug"]
        assert a["animal_health_stats"]["kopfzeile"] != a["antibiotic_usage_vet"]["kopfzeile"]

    def test_der_datensatz_mit_den_code_listen_ist_der_erwartete(self):
        """Ohne diese Zahl liest sich der Befund wie eine Kleinigkeit."""
        a = _auswahl()["food_control_results"]
        assert a["ressourcen_im_datensatz"] >= 20
        assert a["code_listen_darunter"] >= 15, (
            "Wenn die Code-Listen verschwinden, ist «die erste CSV» nicht mehr "
            "zwangslaeufig eine — dann traegt der Befund anders."
        )


class TestAuswahlregel:
    """`_daten_ressource` statt «die erste Ressource dieses Formats»."""

    def test_eine_fehlende_ressource_ist_ein_fehler_keine_leere_antwort(self):
        quelle = DATENQUELLEN["food_control_results"]
        with pytest.raises(UpstreamShapeError) as exc:
            _daten_ressource(
                {"resources": [{"format": "CSV", "name": "Irgendwas anderes", "url": "u"}]},
                quelle,
            )
        assert "Food establishments" in str(exc.value)
        assert "Irgendwas anderes" in str(exc.value)

    def test_die_zuletzt_einsortierte_passende_gewinnt(self):
        quelle = DATENQUELLEN["food_control_results"]
        url = _daten_ressource(
            {
                "resources": [
                    {"format": "CSV", "name": "Food establishments 2022", "url": "alt"},
                    {"format": "CSV", "name": "Food establishments 2025", "url": "neu"},
                ]
            },
            quelle,
        )
        assert url == "neu"

    def test_mehrsprachige_felder_werden_gelesen(self):
        """CKAN liefert `name` und `format` teils als Sprach-Dictionary.

        Ein `str(...)` darauf ergibt `"{'de': 'CSV'}"` — und der Vergleich mit
        `"CSV"` scheitert still.
        """
        assert _mehrsprachig({"de": "Tiergesundheitsstatistik"}) == "Tiergesundheitsstatistik"
        assert _mehrsprachig("CSV") == "CSV"
        assert _mehrsprachig(None) == ""


class TestFetchCsv:
    """Was `_fetch_csv` mit einer echten BLV-Datei macht.

    Die Klasse oben prueft die Aufzeichnung. Sie bliebe gruen, wenn der Code
    den BOM wieder stehen liesse — sie liest ja die Datei nicht. Das hier ist
    der fehlende Teil; gegengeprueft mit einer Rueckmutation auf `utf-8`.
    """

    @staticmethod
    def _antwort(inhalt: bytes):
        from unittest.mock import MagicMock

        r = MagicMock()
        r.content = inhalt
        r.raise_for_status = MagicMock()
        return r

    @pytest.mark.asyncio
    async def test_der_bom_landet_nicht_im_spaltennamen(self):
        from unittest.mock import AsyncMock, patch

        from swiss_food_safety_mcp.server import _fetch_csv

        inhalt = "﻿Year,Canton,Count\n2024,ZH,7\n".encode()
        with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as g:
            g.return_value = self._antwort(inhalt)
            zeilen = await _fetch_csv("https://x/a.csv")

        assert list(zeilen[0]) == ["Year", "Canton", "Count"], (
            "Der BOM steht im Namen der ersten Spalte. Aus `Year` wird "
            "`\\ufeffYear`, und jeder Filter darauf laeuft still ins Leere."
        )
        assert zeilen[0]["Year"] == "2024"

    @pytest.mark.asyncio
    async def test_semikolon_wird_erkannt(self):
        from unittest.mock import AsyncMock, patch

        from swiss_food_safety_mcp.server import _fetch_csv

        inhalt = "﻿ID;DE;EN\ncp1;Kontaminanten;Contaminants\n".encode()
        with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as g:
            g.return_value = self._antwort(inhalt)
            zeilen = await _fetch_csv("https://x/b.csv")

        assert list(zeilen[0]) == ["ID", "DE", "EN"]
        assert zeilen[0]["DE"] == "Kontaminanten"

    @pytest.mark.asyncio
    async def test_eine_zip_datei_wird_als_solche_gemeldet(self):
        from unittest.mock import AsyncMock, patch

        from swiss_food_safety_mcp.server import _fetch_csv

        with patch("swiss_food_safety_mcp.server._get", new_callable=AsyncMock) as g:
            g.return_value = self._antwort(b"PK\x03\x04irgendwas")
            with pytest.raises(UpstreamShapeError) as exc:
                await _fetch_csv("https://x/animal_disease_report.zip")

        # Vorher kam «new-line character seen in unquoted field» — eine
        # Meldung, aus der niemand auf ein Archiv schliesst.
        assert "ZIP" in str(exc.value)


class TestLindasEndpunkt:
    def test_der_gebaute_endpunkt_beantwortet_post(self):
        e = _fixture("lindas_endpunkt.json")["endpunkte"]
        assert e["gebaut_jetzt"]["post_status"] == 200
        assert "sparql-results+json" in e["gebaut_jetzt"]["content_type"]
        assert SPARQL_ENDPOINT == e["gebaut_jetzt"]["url"]

    def test_der_frueher_gebaute_endpunkt_beantwortet_post_nicht(self):
        e = _fixture("lindas_endpunkt.json")["endpunkte"]
        assert e["gebaut_frueher"]["post_status"] == 404
        assert e["gebaut_frueher"]["url"].endswith("/sparql")

    def test_die_kontrolle_traegt_diesen_befund(self):
        """Ohne sie hiesse er nur «ich bekomme einen 404»."""
        e = _fixture("lindas_endpunkt.json")["endpunkte"]
        assert e["kontrolle_erfunden"]["post_status"] == 404

    def test_die_frueher_abgefragte_klasse_hat_keine_instanzen(self):
        k = _fixture("lindas_endpunkt.json")["klassen"]
        assert k["foag_AnimalDisease_frueher"] == 0

    def test_die_kontrollklasse_hat_ebenfalls_keine(self):
        """Das ist der Vergleich, der den Befund traegt.

        «Null Zeilen» allein koennte heissen, dass es gerade keine Faelle gibt.
        Dass eine frei erfundene Klasse dieselbe Null liefert, zeigt: Die
        abgefragte Klasse existiert nicht.
        """
        k = _fixture("lindas_endpunkt.json")["klassen"]
        assert k["kontrolle_erfundene_klasse"] == 0

    def test_der_richtige_cube_traegt_beobachtungen(self):
        k = _fixture("lindas_endpunkt.json")["klassen"]
        assert k["fsvo_cube_beobachtungen"] > 1000, (
            f"Nur {k['fsvo_cube_beobachtungen']} Beobachtungen — am 2026-08-08 waren es 57'997."
        )


class TestKeineStilleAuswahlMehr:
    def test_kein_datenwerkzeug_sucht_seinen_datensatz_noch_per_stichwort(self):
        """Ein Stichwortsuchlauf faellt still auf etwas Plausibles zurueck.

        Genau das ist zweimal passiert. `blv_search_pesticide_products` sucht
        weiterhin — dort ist es bewusst und der strukturierte Fehler bleibt.
        """
        from swiss_food_safety_mcp import server

        code = Path(server.__file__).read_text(encoding="utf-8")
        suchen = [
            z.strip()
            for z in code.split("\n")
            if "_find_dataset(ctx," in z and "pflanzenschutzmittel" not in z
        ]
        assert not suchen, f"Diese Werkzeuge suchen noch statt zu pinnen: {suchen}"
