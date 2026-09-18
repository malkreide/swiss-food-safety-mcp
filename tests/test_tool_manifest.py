"""Der Rug-Pull-Waechter misst die Drahtform, nicht die Python-Schreibweise.

`tools/tool_manifest.py` hasht jede Werkzeugdefinition und vergleicht gegen eine
committete Basislinie (SEC-022). Womit der Hash gebildet wird, entscheidet
darueber, ob er ueberhaupt etwas bewacht.

Beim Umstieg auf `mcp` 2.x hat sich das gezeigt: Das SDK hat jede
Annotations-Eigenschaft umbenannt (`readOnlyHint` -> `read_only_hint`), und das
blosse `model_dump()`, das dort stand, aenderte den Digest von `da85755…` auf
`80cf836…` — **ohne dass sich eine einzige Definition bewegt hatte**. Der
Waechter meldete also die eine Aenderung, die keinen Client erreicht.

Die Gefahr ist nicht der Fehlalarm, sondern was er ausloest: Wer auf dieses
Signal hin `--update` faehrt, pinnt die Basislinie neu und winkt alles durch,
was im selben Commit mitfuhr. Der Test haelt deshalb die Ursache fest statt das
Ergebnis.
"""

from __future__ import annotations

import json

from tools.tool_manifest import BASELINE, _entries, _manifest


def test_der_digest_haengt_an_der_committeten_basislinie() -> None:
    """Dasselbe, was die CI faehrt — hier, damit ein Bruch im Testlauf auffaellt
    und nicht erst im Gate danach."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert _manifest()["sha256"] == baseline["sha256"]


def test_die_annotationen_werden_in_der_drahtform_gehasht() -> None:
    """Die eigentliche Zusicherung: Alias-Schreibweise, nicht Feldname.

    Ohne sie bliebe der Test darueber gruen, sobald jemand `by_alias=True`
    entfernt **und** die Basislinie neu pinnt — also genau in dem Ablauf, den
    der Modulkopf beschreibt. Diese Zusicherung ist die einzige hier, die
    zwischen «Digest stimmt» und «Digest misst das Richtige» unterscheidet.

    **Gemessen wird `_entries()`, also genau das Objekt, das gehasht wird.**
    Die erste Fassung dieses Tests baute die Annotationen selbst noch einmal mit
    `by_alias=True` auf und pruefte das Ergebnis — der Gegenprobe hielt das
    nicht stand: mit entferntem `by_alias=True` im Manifest blieb sie gruen,
    weil sie ueber pydantic urteilte statt ueber den Waechter. Ein Test, der
    seine eigene Antwort herstellt, kann sie nicht widerlegen.
    """
    annotiert = {
        name: eintrag["annotations"]
        for name, eintrag in _entries().items()
        if eintrag["annotations"] is not None
    }
    assert annotiert, "kein Werkzeug traegt Annotationen — die Probe waere leer"

    for name, keys in annotiert.items():
        assert "readOnlyHint" in keys, (
            f"{name}: Annotationen werden nicht in der Drahtform gehasht. Gefunden: {sorted(keys)}"
        )
        assert "read_only_hint" not in keys, (
            f"{name}: Feldname statt Alias gehasht — `by_alias=True` fehlt."
        )
