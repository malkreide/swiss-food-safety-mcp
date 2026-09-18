"""SDK-004: Die CORS-Freigabeliste nennt jetzt Header statt einer Wildcard.

`allow_headers` stand auf `["*"]`. Starlette schaltet damit auf
`allow_all_headers` und spiegelt im Preflight zurück, was der Browser
ankündigt — jeder gelistete Origin durfte also jeden beliebigen Header senden.

Die zu weite Freigabe ist nur die eine Hälfte. Eine Wildcard kann auch nicht
falsch werden: fällt ein Header weg, den das Protokoll braucht, bleibt alles
grün. Die Liste ist prüfbar, die Wildcard nicht.

Geprüft wird mit echten Preflights gegen die zusammengebaute App. Dafür musste
`build_cors_middleware` aus `main` heraus — solange der Aufbau neben `uvicorn.run`
stand, liess sich die Liste nur lesen, nicht ausprobieren, und eine Liste, die
richtig aussieht, kann trotzdem nie an der Middleware ankommen.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swiss_food_safety_mcp.server import CORS_ALLOW_HEADERS, build_http_app

ORIGIN = "https://client.example"

# Beide Netz-Transporte. Eine Kontrolle, die auf einem hält und auf dem anderen
# nicht, ist schlimmer als eine fehlende: sie sieht nach Durchsetzung aus.
PFAD = "/mcp/"


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_http_app([ORIGIN]))


def preflight(client: TestClient, request_headers: str, method: str = "POST"):
    """Sende einen Preflight.

    `request_headers` ist, was der Browser anzukündigen vorgibt. Das muss auf
    der Anfrage reiten und nicht bloss von der Antwort abgelesen werden:
    Starlette beantwortet einen Preflight, der einen nicht freigegebenen Header
    nennt, mit **400 und ohne `Access-Control-Allow-Origin`**.
    """
    return client.options(
        PFAD,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": request_headers,
        },
    )


@pytest.mark.parametrize("header", CORS_ALLOW_HEADERS)
def test_jeder_freigegebene_header_passiert_den_preflight(client: TestClient, header: str) -> None:
    """Einzeln parametrisiert: ein Sammelaufruf bliebe grün, wenn nur einer der
    Header freigegeben wäre und Starlette den Rest durchwinkte."""
    resp = preflight(client, header)
    assert resp.status_code == 200, f"Preflight mit {header} abgewiesen"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_die_header_zusammen(client: TestClient) -> None:
    """Was ein Browser tatsächlich schickt: alle auf derselben Anfrage."""
    resp = preflight(client, ", ".join(h.lower() for h in CORS_ALLOW_HEADERS))
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_ein_nicht_freigegebener_header_wird_abgewiesen(client: TestClient) -> None:
    """Die Gegenkontrolle — und der eigentliche Befund.

    Ohne sie wären die Tests darüber gegen die alte Wildcard genauso grün. Sie
    ist die einzige Zusicherung hier, die zwischen «Liste» und «alles erlaubt»
    unterscheidet.
    """
    resp = preflight(client, "x-beliebiger-header")
    assert resp.status_code == 400, "die Freigabeliste winkt weiterhin alles durch"


def test_die_liste_nennt_den_session_header() -> None:
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_die_liste_nennt_den_wiederaufnahme_header() -> None:
    """`Last-Event-ID` setzt einen abgerissenen SSE-Strom fort. Fehlt er, bricht
    ausschliesslich die Wiederaufnahme nach Paketverlust — unter Last, in
    Produktion, ohne dass ein Test etwas dazu sagt."""
    from mcp.server.streamable_http import LAST_EVENT_ID_HEADER

    assert LAST_EVENT_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_keine_wildcard_in_der_freigabeliste() -> None:
    """Die Regression, die dieser Test abfängt, war genau ein Zeichen."""
    assert "*" not in CORS_ALLOW_HEADERS


def test_die_routing_header_gehoeren_hierher_sobald_das_sdk_sie_liest() -> None:
    """Die drei Routing-Header der Spec `2026-07-28`, gegen das SDK gehalten.

    Dieser Test stand hier, solange die Header **nicht** freigegeben waren: er
    war an `mcp.shared.inbound` gebunden statt an eine Notiz im Kommentar, und
    er ist beim Upgrade auf fastmcp 4.x / `mcp` 2.x gefallen — genau dafür war
    er da. Die Liste ist nachgezogen; der Test bleibt, weil er jetzt die andere
    Richtung hält: benennt eine SDK-Version einen dieser Header um, fällt er
    wieder, statt dass Browser-Clients still am Preflight scheitern.

    Nicht gegen abgeschriebene Zeichenketten geprüft, sondern gegen die
    Konstanten, die das SDK beim Einordnen der Anfrage tatsächlich liest.
    """
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    erlaubt = {h.lower() for h in CORS_ALLOW_HEADERS}
    noetig = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert noetig <= erlaubt, (
        f"Das SDK liest Routing-Header, die Freigabeliste nennt sie nicht: "
        f"{sorted(noetig - erlaubt)}"
    )


async def test_kein_mcp_param_header_ohne_x_mcp_header() -> None:
    """Die Gegenprobe zur Freigabeliste: was **nicht** hineingehört.

    Spec `2026-07-28` prägt `Mcp-Param-{Name}`-Header nur für Parameter, die
    ein Werkzeug mit `x-mcp-header` auszeichnet — für Server optional. Solange
    kein Werkzeug hier das tut, schickt kein Client solche Header, und ein
    Eintrag dafür wäre geraten statt gemessen.

    Der Test misst deshalb die Voraussetzung, nicht die Liste: Bekommt ein
    Werkzeug eines Tages ein `x-mcp-header`, fällt er und verlangt den
    passenden Eintrag. Andersherum — nur zu prüfen, dass kein `Mcp-Param-` in
    der Liste steht — bliebe grün, gerade wenn die Auszeichnung dazukommt.
    """
    import json

    from fastmcp import Client

    from swiss_food_safety_mcp.server import mcp

    async with Client(mcp) as client:
        ausgezeichnet = [
            t.name
            for t in await client.list_tools()
            if "x-mcp-header" in json.dumps(t.input_schema or {})
        ]

    if ausgezeichnet:
        praefix = {h for h in CORS_ALLOW_HEADERS if h.lower().startswith("mcp-param-")}
        pytest.fail(
            f"Werkzeuge zeichnen jetzt Parameter mit `x-mcp-header` aus "
            f"({sorted(ausgezeichnet)}); die Freigabeliste braucht die zugehörigen "
            f"`Mcp-Param-*`-Header. Bisher gelistet: {sorted(praefix) or 'keine'}."
        )

    assert not [h for h in CORS_ALLOW_HEADERS if h.lower().startswith("mcp-param-")], (
        "Die Liste nennt `Mcp-Param-*`-Header, obwohl kein Werkzeug `x-mcp-header` "
        "auszeichnet — das ist geraten, nicht gemessen."
    )


def test_ein_fremder_origin_wird_weiterhin_abgewiesen(client: TestClient) -> None:
    """Die Header-Liste ändert nichts an der Origin-Prüfung."""
    resp = client.options(
        PFAD,
        headers={
            "Origin": "https://fremd.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


def test_ohne_konfigurierte_origins_gibt_es_keine_freigabe() -> None:
    """Fail-closed: ohne `BLV_MCP_ALLOWED_ORIGINS` ist die Origin-Liste leer, ein
    Preflight bekommt also keine Freigabe."""
    # Als Kontextmanager, damit der Lifespan laeuft: ohne CORS-Schicht gibt es
    # keine Kurzschluss-Antwort, der OPTIONS erreicht also die App selbst.
    with TestClient(build_http_app([])) as client:
        resp = client.options(
            PFAD,
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert "access-control-allow-origin" not in resp.headers
