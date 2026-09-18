"""Die MCP-Protokollrevisionen, die dieser Server tatsaechlich spricht.

Bis fastmcp 3.x stand hier **eine** Revision, und das war richtig: `mcp` 1.x
kannte nur eine. Mit fastmcp 4.x kommt `mcp` 2.x, und damit die Zwei-Aeren-Welt,
vor der die Vorgaengerfassung dieses Moduls gewarnt hat — ihr
`test_das_sdk_kennt_hier_nur_eine_aera` ist genau an diesem Upgrade gefallen und
hat die Erweiterung verlangt, die jetzt hier steht.

**Was sich strukturell aendert und nicht bloss in der Zahl.** Die moderne Aera
`2026-07-28` hat keinen `initialize`-Handshake mehr. Sie ermittelt die
Server-Metadaten ueber `server/discover`, und ein `InitializeResult` gibt es
dort nicht mehr — `Client.initialize()` wirft in diesem Modus. Ein Test, der
weiter ueber `initialize_result.protocolVersion` misst, pruefte damit nur noch
die Legacy-Haelfte und saehe von der Aera, die dieser Server neu spricht,
nichts. Deshalb wird jede Aera ueber ihren eigenen Weg gemessen.

**Warum beide Aeren gepinnt sind und nicht nur die moderne.** Der Server
bedient beide gleichzeitig: ein Client von heute bekommt `2026-07-28`, ein
aelterer faellt auf den Handshake mit `2025-11-25` zurueck. Nur die moderne zu
pinnen liesse den Rueckfallpfad ungeprueft — und der ist der, ueber den die
Clients kommen, die noch nicht umgestellt haben.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastmcp import Client

from swiss_food_safety_mcp.server import mcp

# Die beiden Revisionen, gegen die dieser Server gebaut und geprueft ist. Sie
# stehen hier und in beiden READMEs; `test_beide_readmes_nennen_beide_revisionen`
# haelt sie gegeneinander, damit die Doku nicht davonlaeuft.
DOCUMENTED_MODERN_VERSION = "2026-07-28"
DOCUMENTED_HANDSHAKE_VERSION = "2025-11-25"

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_die_dokumentierte_moderne_revision_ist_die_des_sdk() -> None:
    """Gegen die SDK-Konstante gehalten, nicht gegen abgeschriebenen Spec-Text."""
    from mcp.types.version import LATEST_MODERN_VERSION

    assert LATEST_MODERN_VERSION == DOCUMENTED_MODERN_VERSION, (
        f"Das SDK spricht modern {LATEST_MODERN_VERSION}, dokumentiert ist "
        f"{DOCUMENTED_MODERN_VERSION}. READMEs und diese Konstante nachziehen."
    )


def test_die_dokumentierte_handshake_revision_ist_die_des_sdk() -> None:
    """Die Obergrenze des alten Handshakes — der Pfad aelterer Clients.

    Eigene Zusicherung statt einer gemeinsamen mit der modernen: faellt hier
    etwas, ist es der Rueckfallpfad und nicht die neue Aera, und die
    Fehlermeldung soll das sagen koennen.
    """
    from mcp.types.version import LATEST_HANDSHAKE_VERSION

    assert LATEST_HANDSHAKE_VERSION == DOCUMENTED_HANDSHAKE_VERSION, (
        f"Das SDK handelt {LATEST_HANDSHAKE_VERSION} aus, dokumentiert ist "
        f"{DOCUMENTED_HANDSHAKE_VERSION}."
    )


def test_die_moderne_revision_gilt_dem_sdk_als_bekannt_und_unterstuetzt() -> None:
    """Gepinnt ist wertlos, wenn das SDK die Revision gar nicht bedient.

    `LATEST_MODERN_VERSION` sagt, was das SDK fuer neu haelt;
    `SUPPORTED_PROTOCOL_VERSIONS` sagt, was es tatsaechlich annimmt. Ein Bump,
    der das eine ohne das andere verschoebe, kaeme sonst durch.
    """
    from mcp.types.version import MODERN_PROTOCOL_VERSIONS, SUPPORTED_PROTOCOL_VERSIONS

    assert DOCUMENTED_MODERN_VERSION in SUPPORTED_PROTOCOL_VERSIONS
    assert DOCUMENTED_MODERN_VERSION in MODERN_PROTOCOL_VERSIONS


async def test_ein_echter_client_bekommt_die_moderne_revision() -> None:
    """Gemessen statt aus der Konstante geschlossen.

    Die Zusicherungen darueber vergleichen SDK-Konstanten mit Text in dieser
    Datei; sie sagen nichts darueber, worauf sich Client und *dieses*
    `mcp`-Objekt einigen. Erst eine echte Verbindung tut das.
    """
    async with Client(mcp) as client:
        ausgehandelt = client.protocol_version
    assert ausgehandelt == DOCUMENTED_MODERN_VERSION


async def test_die_moderne_aera_kennt_kein_initialize_result() -> None:
    """Der strukturelle Teil des Umstiegs, nicht bloss die geaenderte Zahl.

    Ohne diese Zusicherung koennte `protocol_version` oben `2026-07-28` melden,
    waehrend darunter weiter der alte Handshake liefe — die Revision waere
    angeschrieben und die Mechanik die alte. `server/discover` statt
    `initialize` ist der eigentliche Unterschied der Aera.
    """
    async with Client(mcp) as client:
        assert client.initialize_result is None
        with pytest.raises(RuntimeError, match="modern protocol era"):
            await client.initialize()


async def test_ein_legacy_client_bekommt_weiterhin_den_handshake() -> None:
    """Der Rueckfallpfad, gemessen.

    Ein Server, der nur noch die moderne Aera bedient, faellt genau hier auf —
    und sonst nirgends, weil jeder Test im Portfolio mit einem aktuellen Client
    misst und der nie auf den alten Pfad geht.
    """
    async with Client(mcp, mode="legacy") as client:
        assert client.protocol_version == DOCUMENTED_HANDSHAKE_VERSION
        assert client.initialize_result is not None


@pytest.mark.parametrize("modus", ["modern", "legacy"])
async def test_beide_aeren_liefern_dieselben_werkzeuge(modus: str) -> None:
    """Eine ausgehandelte Revision sagt nichts darueber, ob darunter etwas geht.

    Beide Aeren muessen denselben Server zeigen; einen Umstieg, der die moderne
    Aera anschreibt und dabei die Werkzeugliste einer der beiden leert, faengt
    keine der Zusicherungen darueber.
    """
    kwargs = {} if modus == "modern" else {"mode": "legacy"}
    async with Client(mcp, **kwargs) as client:
        namen = {t.name for t in await client.list_tools()}
    assert namen, f"{modus}: keine Werkzeuge"
    assert all(n.startswith("blv_") for n in namen), sorted(namen)


@pytest.mark.parametrize("datei", ["README.md", "README.de.md"])
def test_beide_readmes_nennen_beide_revisionen(datei: str) -> None:
    """Eine Doku, die weniger oder anderes sagt als der Server tut, ist die
    teurere Haelfte des Problems: sie sieht geprueft aus.

    Beide Sprachen einzeln parametrisiert. Nur die englische zu pruefen waere
    genau die Luecke, an der die zwei schon anderswo im Portfolio
    auseinandergelaufen sind — eine README wandert, die andere bleibt stehen,
    und niemand merkt es, weil der Test die stehengebliebene nie ansieht.
    """
    text = (_ROOT / datei).read_text(encoding="utf-8")
    revisionen = set(re.findall(r"`(20\d\d-\d\d-\d\d)`", text))
    fehlend = {DOCUMENTED_MODERN_VERSION, DOCUMENTED_HANDSHAKE_VERSION} - revisionen
    assert not fehlend, f"{datei} nennt {sorted(revisionen)}, es fehlen {sorted(fehlend)}"


def test_das_sdk_fuehrt_weiterhin_zwei_aeren() -> None:
    """Die Umkehrung des Tests, der diese Datei hierher gebracht hat.

    Vorher stand hier ein Waechter, der anschlug, sobald das SDK von einer auf
    zwei Aeren ging. Jetzt ist der Pin auf ein Paar erweitert — und damit ist
    die offene Flanke die andere Richtung: verschwaende eine Aera wieder oder
    zoege ein Downgrade `mcp` 1.x herein, waere die Haelfte der Zusicherungen
    oben nur noch ein `ImportError` in einem Modul, das niemand liest.
    """
    try:
        import mcp.types.version as sdk_version
    except ModuleNotFoundError:  # pragma: no cover - nur bei einem Downgrade
        pytest.fail(
            "`mcp.types.version` fehlt — das deutet auf `mcp` 1.x. Dieser Server "
            "ist auf die Zwei-Aeren-Welt von `mcp` 2.x gebaut; der Pin in "
            "pyproject.toml (`fastmcp>=4`) muss zurueckgerollt worden sein."
        )

    assert sdk_version.LATEST_HANDSHAKE_VERSION != sdk_version.LATEST_MODERN_VERSION, (
        "Handshake- und moderne Revision sind wieder identisch. Dann bedient das "
        "SDK nur noch eine Aera und dieser Pin behauptet eine Trennung, die es "
        "nicht mehr gibt."
    )
